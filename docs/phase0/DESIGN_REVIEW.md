# Design review of the Phase 0 SAM design — dispositions

Prepared 2026-09-29 by the SAM architect. Three independent critics reviewed REFERENCE_YEAR.md, ACCOUNT_STRUCTURE.md, GAP_MAP.md and data/gap_map.csv:
- **Critic A:** SAM consistency.
- **Critic B:** data fit and tax/transfer blocks.
- **Critic C:** reference year and household block.

I re-checked each point against the files and the live web (details in "Evidence I re-checked" below) before accepting or rejecting it. WebSearch was unavailable (the session's search quota was used up), so every check used direct fetches, curl or local copies.

---

## Summary for the owner (plain English)

- **44 critique points:**
  - 19 major and 25 minor;
  - no blockers.
- **Outcome:**
  - **37 accepted in full**;
  - **5 accepted with a modification** (the problem was real, but I chose a different fix to keep the design coherent);
  - **2 partly rejected**, where I accepted the problem but rejected one proposed fix because it contradicts NAS 2026:
    - stamp duty as a product tax on construction;
    - food subsidy mapped to the Trade product.
- **The reference year does not change: FY 2023-24 on the new 2022-23 base.** All three critics agreed. What changed is how honestly the summary describes it:
  - new-base institutional income accounts (who pays whom interest, dividends, transfers) exist for no year;
  - the Flow of Funds is old-base.
- **The account structure shrinks from 130 to 128 accounts.**
  - IGST is no longer a separate tax account. NAS records GST after the Centre–State settlement, so IGST money is already inside CGST and SGST. Keeping it separate double-counted the IGST settled to States: several lakh crore by the critics' estimate. I did not size it, because the annual settlement total for 2023-24 was not re-fetched. The IGST route becomes a memo layer for the "GST rupee" story.
  - Stamp duty is no longer a product tax. NAS 2026 says it is a production tax, and the SUT has no room for it on property products.
- **Five design choices contradicted MoSPI's own *Sources and Methods* (Sept 2026), and all are now fixed:**
  - stamp duty is a production tax;
  - food subsidy is government consumption (free grain), and FCI is part of the Union government;
  - GST is on a net, post-settlement basis;
  - part of government pensions is imputed inside salaries, so households now pay that part back;
  - provident-fund and life-insurance flows are saving, not income transfers. Their investment income is now credited to households.
- **Four consistency fixes that change what gets ingested in Phase 1:**
  - an explicit counterparty rule so every financial market still clears when NAS/BoP numbers replace Flow-of-Funds numbers;
  - a public + private split inside each financial sub-sector;
  - the HDFC merger (1 July 2023) treated as a reclassification, not a lending boom;
  - the RBI surplus put on one timing basis.
- **Multiplier engine:** GST will use use-specific rates: zero on exports, and creditable on most business inputs. Otherwise a "GST rate change" or an export shock would produce nonsense revenue.
- **Honest labelling:** cash-basis tax and interest totals are still "official", but their conversion to national-accounts concepts is now labelled "estimated". The count moved from 52 official / 41 estimated to **51 official / 54 estimated / 1 international** SAM cells, plus 9 satellites.

---

## Evidence I re-checked (2026-09-29)

| What | How | Result |
|---|---|---|
| MoSPI *Sources and Methods for Compilation of National Accounts Statistics*, Sept 2026 | `curl -sIL` then GET of https://www.mospi.gov.in/uploads/documents/pressRelease/1789976245319-Sources%20and%20Methods%20for%20Compilation%20of%20National%20Accounts%20Statistics.pdf | HTTP 200, `application/pdf`, 3,801,146 bytes, Last-Modified 21 Sep 2026, sha256 `8bd5f5f9…926e`; 22,726 text lines (same as the critics' `sm.txt`) |
| §4.6.1 tax classes | pdftotext, text lines 4554–4574 | "For instance, land revenue and stamp duties are treated as production taxes." |
| Food subsidy / FCI | lines 15505–15508, 1448 | "Following the reclassification of the Food Corporation of India (FCI) from a market producer to a non-market producer, food subsidy is recorded as a social transfer in kind and consequently forms part of GFCE rather than product subsidies." |
| GST net basis | lines 15080–15084 | "net GST collections are used … net Central GST (CGST), net State GST (SGST), net Integrated GST (IGST), compensation cess" |
| SUT product-tax allocation | §27.6.8, lines 13347–13351 | "GST is distributed among product groups using PFCE and item-specific GST rates" |
| OPS pension imputation | §3.1.1, lines 3283–3306 | "a factor based on an average retirement period, say 39 years, starting from 2005-06 … only the remaining portion will be treated as CE"; "States where OPS is still operational, no adjustments have been made" |
| Household saving formula | lines 21060–21085 | "Provident & Pension Fund = Contribution + Recoveries - Withdrawals + Interest"; "Central & State Govt. provident fund, Public provident fund"; "Increase in Life Fund" |
| EPFO | §7.4.8, lines 5925–5931 | Contribution funds of EPFO, CMPFO, SMPFO, ATEPFO, NPS are Pension Funds; "administration funds … Financial Auxiliaries (S-126)" |
| Autonomous bodies | §4.4 (iv), (viii), (ix) | "Autonomous Bodies (Centre and State)"; separate Centre and State AI estimates |
| Dwellings | lines 9833–9838, 10693–10695 | GVA "actual rent paid and imputed rent"; PFCE housing = "sum of GVO from 'Ownership of Dwellings', and housing services provided by Government" |
| RBI surplus, motor-vehicle tax, PM-KISAN in S&M | grep | **No match**: S&M does not state these treatments (recorded as open questions to NAD) |
| Old-base NAS household and GG sequences | NAS 2024 St 5.0 (sha256 `a24f2ddd…`), St 4.0 (`238fc6bf…`) | Household secondary distribution: uses = D5 only; resources D6+D7 combined; D8 rows empty. GG 2022-23: D29 2,46,133; D39 2,88,983 |
| SUT 2023-24 | local file, sha256 `6fbaa0e9…dfafd` (critics' downloads have the same hash) | Product taxes sum 30,15,341; subsidies −5,76,422. Product 144 dwellings PT 0; 145/146/148/149 PT 24,059 / 9,194 / 4,114 / 18,176 (= 55,543); 127 construction 3,24,456; 65 alcohol 2,33,677; 69 tobacco 57,377; 42 coal 3,062. Subsidies: electricity −1,92,370; fertilisers −1,45,129; trade −1,05,007; pesticides −62,440 (imports 0); paddy −6,691; wheat −4,110. GFCE: paddy 1,01,441; wheat 62,531. Production taxes less subsidies: agriculture −2,03,683 (−6.39% of GVA); communication −27,498; industries 57, 60–64 PT/GVA 0.0380; IT 66,850; CE/GVA 0.7093 for 60–64 |
| Union Receipt Budget 2025-26 | local `allrec.pdf` (sha256 `c73c26d7…`) | 2023-24 actuals: CGST 820,622.09; IGST −4,850.43; comp. cess 141,436.16; total GST 957,207.82 (sums exactly). "IGST revenue is subject to apportionment and fund settlement between Centre and States". "₹78,104 crore was recovered in 2023-24" (back-to-back loans from the GST Compensation Fund) |
| GSTN monthly report (Aug 2026) | local text of the fetched PDF | "Post-Settlement GST is cumulative of the GST revenues of the States/UTs and the SGST portion of the IGST settled to the States/UTs" |
| FC16 KFI 2023-24 | docs/phase0/recon/state_fiscal.md, verify/state_fiscal.md | SGST 8,00,112; State excise 2,49,133; stamps 2,20,289; vehicles 1,06,021; pensions 4,94,939; note "GST compensation loan has been considered as central grants" |
| NAS 2026 statements | local files re-parsed | 1.9 memo reinvested earnings 1,53,752 / 1,63,704 / 1,92,652. 1.13 FISIM only by 10 industries (PADM 0), PFCE 6,02,897, RoW 29,794. 1.14 public FC GVA 7,14,052, saving 5,35,510; private FC 9,44,003 / 4,55,938. 5.3 (2022-23 / 2023-24 / 2024-25): bank advances 11,91,385 / 18,56,521 / 12,12,581; NBFC loans 3,34,556 / −6,423 / 3,27,316; non-bank deposits 67,275 / −59,126 / 55,315. 5.2 GG individual consumption 2023-24 11,85,000. 7.1C 2022-23 real-estate/dwellings/professional PT 1,72,778. 1.1 GDP 2,61,77,001 → 2,90,73,287 (+11.06%) |
| FSF 2023-24 workbook | local `rbi/fsf.xlsx`, sha256 `3de9013d…` | St 4 loans, transactions 2022-23 / 2023-24: ODCs 12,52,313 / 18,77,458 (stock 85,85,251 → 1,04,62,709); OFCs 3,43,354 / 1,208. FSF article: "Liabilities under other accounts payable doubled due to increase in surplus payable to central government" |
| FSF xlsx scripted download | `curl` with a browser UA, https://rbidocs.rbi.org.in/rdocs/content/docs/FSF2023-24_21012026.xlsx | HTTP 200 but `text/html`, 42,904 bytes (bot-challenge page). Not bypassed |
| RBI surplus series | docs/phase0/verify/rbi_core.md (RBI AR 2025-26 Ch. XII) | 30,307.45 / 87,416.22 / 2,10,873.99 / 2,68,590.07 / 2,86,588.46 |
| HDFC merger date | WebFetch https://en.wikipedia.org/wiki/Housing_Development_Finance_Corporation | "Defunct: 1 July 2023 … Merged with HDFC Bank". **Secondary source only**; RBI/HDFC primary confirmation is a Phase 1 task |
| DEA debt reports | `curl` https://dea.gov.in/reports-public-debt-management | HTTP 200; lists "Quarterly Report on Public Debt Management for the quarter January-March 2024" and "Status Paper on Government Debt for 2023-24" |
| HCES A2 / A10F | local xlsx (sha256 `5e87cc21…`, `e8867e5e…`) | A2: Kerala rural 0–5% average MPCE 2,725.07; All-India rural 0–5% 1,676.7 (State-specific cut-offs). A10F: 446 distinct codes incl. 099, 619, 649, 983 "Durables total", 999 "Total Expenditure"; 640 "gold/diamond/platinum jewellery"; free items (061 "rice-free") with value "##" |
| Q1 2026-27 press note / MoSPI FAQ | local text | "publishes the updated Annual Revised Estimates for the FY 2022-23, 2023-24 and 2024-25"; FAQ Q6 "affected both annual and quarterly estimates from FY 2022-23 onwards" |
| NAS 2024 1.1 (old base) | critic's local file | 2022-23 GDP 2,69,49,646, discrepancy −2,95,789 |

---

## Dispositions

Severity is the critic's. "Files" names what changed: RY = REFERENCE_YEAR.md, AS = ACCOUNT_STRUCTURE.md, GM = GAP_MAP.md + data/gap_map.csv (both regenerated from one script).

### Critic A — SAM consistency (18 points)

| # | Sev. | Point | Disposition | Reason / what changed | Files |
|---|---|---|---|---|---|
| A1 | major | IGST counted twice. FC16 SGST is post-settlement, T2a adds IGST settled to States again; Union MH 0005 also holds IGST apportionment; GST row targets exceed the SUT vector; no rule for which margin wins | **Accepted** | Confirmed: GSTN defines post-settlement SGST as including settled IGST; Receipt Budget shows IGST MH 0008 = −4,850 (residual); S&M says NAS uses net CGST/SGST/IGST. **T_IGST removed**; T_CGST = MH 0005 + 0008, T_SGST = post-settlement; IGST route moved to memo S7; T2a deleted. The SUT margin wins; cash–accrual gap logged (T1a, T2x). Phase 1 test: product-tax row targets = 30,15,341 | AS §5, §10; GM P7a, T1/T1a, T2/T2x, S7 |
| A2 | major | Stamp duty is a production tax in NAS; SUT has no room on DWEL/BSRE | **Accepted** | S&M §4.6.1 quoted above; SUT product 144 PT = 0, BSRE 55,543 vs stamps 2,20,289. **T_STMP removed**; stamps and land revenue are inside T_PROD with gross taxes / gross subsidies as sub-rows (P10a). Feasibility: old-base GG D29 2,46,133 and D39 2,88,983 show the gross sizes fit. Motor-vehicle tax: S&M silent, asked of NAD (R16) | AS §5, §10; GM P7a, P10, P10a, T2, R16 |
| A3 | major | Food subsidy is a social transfer in kind in GFCE; FCI non-market | **Accepted** | S&M quote above; SUT paddy/wheat subsidies tiny, GFCE on grain 1.64 lakh cr. Food removed from T_PSUB/P9/P9a; grain GFCE → G_CEN (C2a); **FCI moved to G_CEN** with an FSF→NAS sector bridge in K9; H12 PDS closed; food STiK by group as satellite S8 | AS §4.2, §4.4, §5; GM P9, P9a, C2a, K9, S8 |
| A4 | major | No D8/D44; PF and life flows treated as current transfers; household and FC current accounts cannot both hit NAS | **Accepted with modification** | The problem is confirmed (S&M saving formula; NAS 5.3 puts 13.72 lakh cr of PF/insurance inside household saving; FC saving only 9.91 lakh cr). I adopt the **NAS convention**, not explicit gross D61/D62/D8 cells: funded-scheme contributions, withdrawals, premiums and claims are financial (I_INPE); a **D44 cell** (R9c) credits investment income to households; non-life stays as current transfers (R17). Reason: the old-base NAS household account has no D61 and an empty D8, and explicit D61/D62/D8 cells would net to zero on both accounts while adding three estimated cells. Gross flows are kept for the story in satellite S9. E_INSP closure test added | AS §4.3, §4.5, §7; GM R9, R9c, R17, K2a, K7a, S9 |
| A5 | major | Imputed OPS pension contributions missing (D612), so pensions are double counted; also check HRA housing | **Accepted** | S&M §3.1.1 confirmed. New cell **R9b** HH → G_CEN/G_STA = OPS component of GG CE (1/39 rule; unadjusted for defence and OPS States), keyed like government CE. HRA check resolved: S&M says PFCE on housing includes "housing services provided by Government", so it is in C4a component (ii) | AS §4.5; GM R9, R9b, C4a |
| A6 | major | Flow-of-funds block will not close after swapping in NAS 5.3 and BoP rows; K9 only balances capital accounts; PF & pension includes GPF/PPF | **Accepted** | New **K7b counterparty rule**: every NAS/BoP − FSF difference is posted to the named counterparty in the same instrument before K9. Phase 2 test that every I_* clears. K7a now maps NAS 5.3 components to instruments (GPF → G liabilities in I_INPE, PPF → I_SSAV) with a PPF double-count check | AS §7; GM K7, K7a, K7b, K9 |
| A7 | major | RBI surplus cash-basis in income block (87,416) but accrued in FSF (2,10,874); super-dividend not addressed; R3a note off by a year | **Accepted** | Confirmed from FSF article and RBI AR row. S&M does not state the treatment (searched). Chose the **cash basis** (R6 = 87,416), because NAS builds GG saving from budget documents. The accrued difference of 1,23,458 is an explicit logged timing item in I_OTHR (**K9b**). Super-dividend test in Phase 1; R3a note corrected. To be written into DECISIONS.md at Phase 1 start | AS §7; GM R3a, R6, K2a, K9b |
| A8 | major | FC public/private split mis-specified (AIFIs, public NBFCs, public insurers, EPFO, RRBs straddle); E_BANK current boundary narrower than FSF ODCs | **Accepted** | Each FC sub-account = public part + private part, estimated from ownership data, adding to NAS public/private FC (7,14,052 / 9,44,003 GVA; 5,35,510 / 4,55,938 saving). E_BANK income built on the full ODC boundary | AS §4.3; GM F4a, K2a |
| A9 | major | GST as a fixed share of commodity supply makes export/IC shocks generate phantom GST | **Accepted with modification** (option b) | Confirmed that the SUT spreads GST via PFCE × rates (S&M 27.6.8). New decision **D2a**: the published SAM keeps taxes in commodity columns, and the Phase 4 engine uses use-specific coefficients from a new valuation layer **P7b** (tax by commodity × type × use). Option (a), tax accounts paid by using accounts inside the SAM, is rejected: it would put estimated cells into the published SAM and break the link to the SUT tax vector | AS D2a, §5, §12; GM P7b |
| A10 | major | F_GOSC does not clear (partnership/NPISH GOS has no receiving cell); dwelling PFCE includes actual rent, so tenants' rent is credited to tenants | **Accepted** | S&M confirms dwellings = actual + imputed rent (+ government housing in PFCE). F3 split into **F3a** imputed rent, **F3b** actual rent to landlords (keyed by rented-out property ownership), **F3c** partnerships/NPISH; C4a split into actual rent, government housing and imputed rent. Phase 2 test F_GOSC row = column | AS §3; GM V2a, F3–F3c, C4a |
| A11 | minor | Reinvested earnings on FDI (D43) have no cell | **Accepted** | NAS 1.9 memo 1,63,704 confirmed. New **R14a** ROW ← NFC/FC pinned to it, with a matching `FDI reinvested earnings` tag on RoW → I_EQTY. Whether NAS 6.1 item 8 includes RE is a Phase 1 check (unverified) | AS §4.2, §7, §11; GM R8, R14a, K8b |
| A12 | minor | Autonomous institutions assigned wholly to States | **Accepted** | S&M "Autonomous Bodies (Centre and State)". The 1,53,164 NVA is split by grants-in-aid (estimated) | AS §4.4; GM F4b, C2a |
| A13 | minor | R13 sends RoW property income to factor accounts | **Accepted** | FAC removed from R13; FAC ← ROW is CE only | GM R13, R14 note, block overview |
| A14 | minor | D1 "no technology assumption" misleading for the engine | **Accepted** | D1 reworded: none in the data SAM; the multiplier model assumes a fixed product mix and fixed import shares; both added to §12 assumptions | AS summary, D1, §12 |
| A15 | minor | X_DISC → ROW looks like money paid abroad; X_DISC must be exogenous | **Accepted** | Stated: always exogenous; UI renders its cells as reconciliation items. The alternative (RoW on the NAS 1.1 basis) is to be logged in ISSUES.md (listed in my issues output, since ISSUES.md is outside this task's files) | AS §9, §12; GM D1, D2 |
| A16 | minor | EPFO classification is settled by S&M | **Accepted** | S&M §7.4.8 quoted. Contribution funds in E_INSP; administration funds (S126) in E_NBFC; the "move to G_CEN" contingency dropped | AS §4.3; GM R9 note |
| A17 | minor | HDFC merger may inflate bank vs NBFC flows | **Accepted** (merged with B5) | FSF St 4 break confirmed. Reclassification removed from transactions once confirmed; logged as a volume change | AS §7; GM K8, K8a, R5 |
| A18 | minor | IGST prior ignores imports | **Accepted with modification** (superseded by A1) | T_IGST no longer exists. The GST prior is now PFCE × item rate on imported and domestic supply alike (MoSPI's own method), so imports are covered | GM P7a |

### Critic B — data fit, taxes and transfers (15 points)

| # | Sev. | Point | Disposition | Reason / what changed | Files |
|---|---|---|---|---|---|
| B1 | major | IGST MH 0008 is a residual (−4,850); T2a double counts | **Accepted** (same fix as A1) | Receipt Budget figures reproduced exactly | as A1 |
| B2 | major | P7a priors infeasible: (a) stamp duty on DWEL/BSRE, suggest C_CNST; (b) State excise > SUT alcohol tax; (c) coal cess cannot sit on C_COAL; make "which heads are product taxes" a Phase 1 blocker | **Partly rejected.** (a) **Rejected: the C_CNST prior**; the infeasibility itself is accepted. (b) **Accepted.** (c) **Accepted.** The blocker is **mostly resolved** | (a) S&M says stamp duty is a *production* tax, so putting it on construction as a product tax would contradict NAS; fixed via A2 instead. (b) State excise 2,49,133 > alcohol PT 2,33,677 confirmed: pre-check added, excess placed on HOTL/TRAD as licence fees, logged, asked of NAD. (c) Coal PT 3,062 confirmed: coal cess follows the SUT's PFCE spread. S&M answers the product-vs-production question except for motor-vehicle tax, which stays open with NAD | AS §5; GM P7a, T2x, R16 |
| B3 | major | Farm subsidies double counted (PM-KISAN as D39 inside mixed income and again in R10); T_PROD "pro-rata to GVA" note wrong | **Accepted (as a default, pending NAD)** | Agriculture PTLS −2,03,683 and old-base household D39 1,34,449 confirmed. S&M §4.6.2 says input subsidies to farmers are production subsidies, but does not name PM-KISAN, so routing it via D39 is an inference. Default: farm income support is in T_PROD/F_MIXD, not R10. T_PROD note corrected (ratios differ between groups) | AS §2 CROP, §5 T_PROD; GM P10, P10a, R10 |
| B4 | major | R9 conflicts with NAS (no D61, D8 blank); make EPF/NPS financial only; keep civil pensions; R9 → ESTIMATED | **Accepted with modification** | Same NAS convention as A4, plus the D44 cell (R9c), which B's fix lacked. Without D44, E_INSP would keep investment income that NAS attributes to households, and FC saving would overshoot. R9 is restructured rather than relabelled: it is now government OPS pensions, cash as published (OFFICIAL); the funded-scheme part moved to the financial block, R9b and R9c are ESTIMATED, and S9 holds the gross admin totals | AS §4.5; GM R9, R9a–c, S9 |
| B5 | major | HDFC merger dominates 2023-24 credit; swapping NAS 5.3 into FSF leaves I_DEPO/I_LOAN unbalanced; add a per-instrument residual row in I_OTHR | **Accepted with modification** | Merger pattern confirmed in NAS 5.3 and FSF St 4 (date from a secondary source). Published and merger-adjusted views added (K8a). For clearing, I use A6's **counterparty rule** instead of per-instrument residuals parked in I_OTHR: a residual in I_OTHR cannot make I_DEPO itself clear | AS §7; GM K7b, K8, K8a, R5 |
| B6 | major | Half the 2023-24 cess (78,104) repaid back-to-back loans; T2b should be ESTIMATED | **Accepted** | Receipt Budget text confirmed. T2b → ESTIMATED with grants plus cess-funded loan recovery; new **K8e** for the States' I_LOAN repayment; FC16's "loan as grant" note reconciled; class of the transfer asked of NAD | AS §5 T_GCES; GM T2b, K8e |
| B7 | major | PDS grain is GFCE; C2a would miss it; map food subsidy to C_TRAD; pesticides anomaly; use NAS 5.2 | **Partly rejected**: all accepted except the C_TRAD mapping | Grain GFCE → G_CEN; NAS 5.2 as individual/collective control; Q6 logged; H12 closed; HCES free items excluded from PFCE keys. **Rejected: mapping food subsidy to C_TRAD.** S&M states food subsidy is STiK in GFCE, not a product subsidy, so the −1,05,007 on Trade is something else; logged as Q7 and asked of NAD | AS §2, §5; GM P9, P9a, C1a, C2a, Q6, Q7 |
| B8 | minor | FISIM adjustment in R4/R5 is itself estimated | **Accepted** | NAS 1.13 structure confirmed. Extra steps written into R4/R5; labelled E* | GM R4, R5 |
| B9 | minor | R11a sums State-specific quintiles | **Accepted** (same fix as C1) | HCES A2 confirms State-specific fractiles | GM R11a |
| B10 | minor | SUT group-level ratios (IT CE 70.9%, PT 3.8%) used as if measured | **Accepted** | §2 justifications no longer use them; Q2 extended; group-9 production-tax re-split satellite named | AS §2; GM Q2 |
| B11 | minor | Several OFFICIAL labels include estimation (T1, R3, R2) | **Accepted** | Split into OFFICIAL cash control totals (T1, T2, R3, R2 total) and ESTIMATED NAS-concept cells (T1a, T2x, R3b, R2k); counts recomputed by the build script | GM T1, T1a, T2, T2x, R2, R3, R3b, summary |
| B12 | minor | "~650 HCES items" overstated; jewellery | **Accepted** (with C5) | 446 codes incl. subtotals; leaf codes only; jewellery → valuables | GM C1a |
| B13 | minor | BaTIS and IMTS are calendar-year; ICIO India 2020-22 projected | **Accepted** | FY shares = 0.75 × CY2023 + 0.25 × CY2024, labelled estimated. P6a already says old-base priors; new-base SUT import vector dominates | GM S1, S2 |
| B14 | minor | Reinvested earnings not handled | **Accepted** (same fix as A11) | — | GM R14a, R8 |
| B15 | minor | DEA Jan–Mar 2023/2024 quarterly reports and Status Paper 2023-24 missed | **Accepted** | Listing re-checked live (HTTP 200). Added as R3a/K8d sources; HBS T107 only for SDLs | GM R3a, K8d, §5 |

### Critic C — reference year and household block (11 points)

| # | Sev. | Point | Disposition | Reason / what changed | Files |
|---|---|---|---|---|---|
| C1 | major | R11a sums State quintiles cut on State MPCE | **Accepted** | Each State × fractile cell is placed into national quintiles by its average MPCE, splitting cells that straddle a cut-off; the same rule applies to every State-keyed allocation | GM R11a, H7 |
| C2 | major | Summary says "every block exists", but new-base D4–D7 exist for no year; FSF old-base | **Accepted** | Summary reworded, with the trade-off against 2022-23 stated; §3 table updated (FSF 🟡 old base; D4–D7 missing for all years). The recommendation stands: 2022-23 would avoid only a one-year roll of old-base *ratios*, while being older and having larger residuals | RY summary, §3, §6 |
| C3 | minor | "Final" 2023-24 was revised on 31 Aug 2026 | **Accepted** | Described as "Final (updated 31 Aug 2026)"; press note and FAQ quoted; Phase 1 alert test; re-pin points named | RY summary, §1 |
| C4 | minor | NAS 2024 old-base SoA holds 2022-23 FRE, not Final; vintages mixed | **Accepted** | Label "old base, NAS 2024 vintage (2022-23 FRE)"; compare against NAS 2024 levels | RY §2, §4; GM H6 |
| C5 | minor | A10F: 446 codes with subtotals; free items suppressed; jewellery is valuables | **Accepted** | Confirmed by re-parse. Leaf codes only (test), jewellery → valuables, free items excluded from PFCE keys | GM C1a |
| C6 | minor | F4 derivation from 7.1A/7.1B would double count GG or FC | **Accepted** | Formula written out with the 2022-23 identity check (42,32,624 = 12,58,014 + 6,45,812 + 23,28,798) | GM F4 |
| C7 | minor | Imputed-rent key has no fallback from published tables | **Accepted** | Fallback named (AIDIS R/U owner shares × HCES tenant-rent distribution); microdata marked critical path; band on the site | GM C4a, §5 |
| C8 | minor | FoF counterparty problem | **Accepted** (same fix as A6) | — | AS §7; GM K7b |
| C9 | minor | 10.97% should be 11.06% | **Accepted** | Recomputed from NAS 2026 1.1 | RY §4, §8; GM H4 |
| C10 | minor | "Line by line" validation against old-base SAMs not meaningful | **Accepted** | Now "shares and ratios, not levels" | RY summary, §6 |
| C11 | minor | FSF workbook cannot be fetched by script | **Accepted** | Re-checked (HTML challenge). Manual download added to access requests; file pinned by sha256 | RY §4; GM §5 |

### Tally

| | Major | Minor | Total |
|---|---|---|---|
| Accepted | 13 | 24 | 37 |
| Accepted with modification | 4 | 1 | 5 |
| Partly rejected (problem accepted, one proposed fix rejected) | 2 | 0 | 2 |
| **Total** | **19** | **25** | **44** |

- **With modification:** A4, A9, B4 and B5 (major); A18 (minor).
- **Partly rejected:** B2 (stamp duty on C_CNST as a product-tax prior) and B7 (food subsidy on C_TRAD).
- **Conditional:** B3 is accepted as a default that NAD must confirm.
- **Duplicates across critics**, fixed once: A1 = B1; A6 = B5 = C8; A11 = B14; B9 = C1; B12 = C5; A17 = B5.

---

## How the fixes fit together (coherence check)

- **One tax classification, taken from NAS 2026.** Product taxes = GST (net, post-settlement), excise, customs, sales tax, other. Production taxes = stamps, land revenue, professional/property taxes. Production subsidies include farm input and income support by default. Food subsidy = GFCE.
- **The tax fixes are consistent with each other and with the SUT:**
  - removing stamps and IGST double counting brings the row targets close to the SUT's 30,15,341;
  - the SUT's own PFCE-based GST allocation is used both as the P7a prior and as the basis of the use-specific engine rates (P7b).
- **One convention for pensions, PF and insurance, following NAS's asset-side saving measure:**
  - funded flows are financial;
  - investment income is attributed to households (D44);
  - unfunded OPS pensions appear as imputed CE, which households return as D612, plus benefits paid (D62).

  This makes household disposable income, household saving and FC saving consistent with the same three NAS controls.
- **One timing rule.** Government items use the Union/State cash receipts that NAS uses, and every accrual difference to FSF is an explicit, named I_OTHR item (RBI surplus K9b; HDFC reclassification as a volume change).
- **One market-clearing rule.** Replacement of FSF rows is always paired with a counterparty posting (K7b), and only then is the sector residual computed (K9).
- **Sector boundaries follow NAS 2026:**
  - FCI and the central autonomous bodies are in G_CEN;
  - EPFO contribution funds are in E_INSP, and their administration funds in E_NBFC;
  - each FC sub-account has a public part and a private part.

## Remaining open risks (after this review)

1. **No new-base institutional income accounts.** Interest, dividends and transfers by sector are all built bottom-up. The single biggest estimated block.
2. **NAD confirmations** that could move cells:
   - motor-vehicle tax;
   - State excise licence fees;
   - farm income support as D39;
   - RBI surplus treatment;
   - the Trade and pesticides subsidy rows;
   - cess-funded loan recovery;
   - the FCI sector bridge;
   - the OPS adjustment factor for 2023-24.
3. **Old-base FSF plus the HDFC merger** in the reference year. The bank-vs-NBFC credit story depends on a merger adjustment that is not yet sourced from RBI.
4. **Household distribution keys** (imputed rent, property income, pensions, remittances) rest on AIDIS 2019 and published tables until microdata access is granted.
5. **Vintage churn.** "Final" 2023-24 was already updated once. The Dec 2026 back series and the 26 Feb 2027 release are likely re-pin points.
6. **P7a feasibility.** The pre-check may show that some cash tax totals cannot fit the SUT vector even after reclassification. That gap will be logged, not forced.

## Follow-ups outside the four files I own

- ISSUES.md is to record: SUT quirks Q6–Q8; the X_DISC alternative (A15); the HDFC merger; the FSF bot wall; the FC16 "compensation loan as grant" note.
- DECISIONS.md is to record: net-GST basis; stamp duty; food subsidy; the pension convention; the RBI cash basis; D2a; the counterparty rule.
- The access list is to include the FSF manual download and the NAD question list.
- The gap-map build script (`gapmap_build.py`, session scratchpad) is updated. It now also writes a `ref` column as the first CSV field, so CSV rows can be cited by reference.
