# Phase 2 cross-plan review (all nine block plans + the production block)

Written 2026-09-30 by the cross-plan critic. I read all nine plans in `docs/phase2/plans/` in full, `DESIGN_BRIEF.md`, `SAM_GUIDE.md`, `FRAMEWORK_REQUESTS.md`, `data/gap_map.csv`, `pipeline/sam/accounts.py` / `structure.yaml`, and the built production block (`data/sam/2023-24/blocks/production_*`). I checked the plans against each other, not one by one. Values I re-read from `data/clean` are marked "(checked)". Amounts are ₹ crore, current prices, FY 2023-24.

Each plan now ends with a section "8 Cross-plan review" listing what that block must change or confirm. This file is the consolidated version. The finding ids (XR-n) are used in both places.

---

## 1. Verdict in plain English

The plans fit together well. Every gap-map ref and satellite has exactly one owner (`check_ownership` returns no problems), the double-counting hot spots in DESIGN_BRIEF §4 are each handled by one named block, and most official totals are declared once with the same target. **But the plans are not ready to build as a set.** They need about a dozen fixes, of four kinds:

1. **Two flows have no owner.** Government's property income other than dividends: mining royalties, petroleum royalty, possibly spectrum, and interest from companies. Also pensions paid by departmental enterprises (Railways, Posts). Together these are ₹2.5–4 lakh cr. Without an owner, balancing will push that money into the wrong cells (XR-1, XR-2).
2. **Four places where two blocks would compute the same number differently.**
   - RBI's foreign income: BoP vs RBI Annual Report, ₹25,645 cr apart (XR-4).
   - The household FISIM split between deposits and loans: stock weights vs the reference rate (XR-5).
   - Where deposit-taking NBFCs and HDFC Ltd sit: E_BANK vs E_NBFC (XR-6).
   - The Centre/State boundary: institutional view vs treasury view (XR-7).
3. **Interface names do not match.** Examples: the household keys fincorp and rest_of_world ask for do not exist under those names, and several time-series component names differ from the ones the owning blocks plan (XR-10, XR-19). The ref on some entries also does not match the refs filter in constraints or closure's whitelist (XR-11).
4. **Owner decisions are needed before the build.** They are listed together in §7: vehicle tax, R9b, capital transfers to households, RBI reserve income, Centre/State boundary, the new refs, and the DAG.

None of this needs new data. All of it is decisions and bookkeeping. **Verdict: needs fixes.**

---

## 2. Ownership check (task item 1)

`pipeline.sam.accounts.check_ownership(data/gap_map.csv)` returns `[]` (checked): all 106 cell refs and 9 satellite refs are owned once. The plans implement them as follows.

| Block | Refs with entries | Refs as constraint / satellite only | Not implemented (logged) |
|---|---|---|---|
| production (built) | P1–P6, P8–P10, I3, D4 | P7, V1, V2, C1, C2, I1, (I2 via `valuables.*`); satellite `sut_memo` | P6a, S6 |
| households | C1a, C4a, C4b, C4d | C4c (memo satellite), S8 | — |
| factors | V1a, V2a, V3, V4, F1a, F2, F3a, F3b, F3c, F4, F4b | F1, F3 | — |
| taxes | P7a, P9a, P10a, T1a, T2x, T3 (quasi-corporate part), T3a, T4a | T1, T2, T4; P7b, S7 | — |
| government | C2a, R1, R2, R2k, T2b, R6, R7, R9/R9a (see XR-11), R9b, R10, R18, K3a, K6, K8e | K3 | R15, R16 (no entries, reasoned) |
| fincorp | F4a, R3, R3a, R4, R5, R8, R8a, R9c, R17, K2a | R3b, K2; S9 | — |
| rest_of_world | R11a, R12a, R13, R14, R14a, K5, K8b, K8c, D2 | R11, R12; S1, S2, S3 | — |
| capital_financial | I1a, I2, I2a, I3a, K1, K7, K7a, K7b, K8, K8a, K8d, K9, K9b, D3 | K4; S4, S5 | — |
| closure | K4a, D1 | — | — |

**Cells claimed by two refs, and how the plans settle them.** All are agreed between the two plans. The gap-map text should be updated by the orchestrator:

| Cell | Gap map | Agreed owner |
|---|---|---|
| R_ROW ← G_CEN/G_STA interest | R3a and R14 | rest_of_world, R14 |
| R_ROW ← NFC/FC dividends | R8 and R14 | rest_of_world, R14 |
| G_* ← NFC/FC dividends | R7 and R8 | government, R7 |
| H_* ← G_* interest | R3a (row HH total) | fincorp, R8a (group level) |
| GPF interest to H_* | R3a and R9c | fincorp, R9c only |
| T_PIT ← E_NFPR/E_BANK (firms' income tax) | not in the gap map | taxes, under T3 (component `quasi_corporate`): a gap-map extension |
| G_CEN\|G_STA ← T_OPRT; G_STA ← T_PIT; G_CEN ← T_SVAT/T_SEXC (UTs) | not listed | taxes, under T1a/T2x: a gap-map extension |
| Centre→State I_LOAN | K8 (FSF) and K8e | government K8e (−78,104) plus capital_financial `dom` = FSF − K8e = 1,19,895.65 |
| RBI↔Centre other payables | K8 (FSF F89) and K9b | K9b (1,23,457.77) replaces the FSF pair; −1,810.08 `fsf_f89` remainder |
| RoW counterparties in FSF | K7/K8 | dropped; rebuilt from K8b by K7b (`row_cp`) |

**Flows with no owner (omissions):**
- **XR-1 (critical).** GG property income other than dividends has no ref:
  - interest from non-GG units. Union `fa8.0049.total` 78,674.11 (checked), of which PSUs 7,686.33, DCUs 1,600.47, SDR 5,411.10 (→ R13); States 28,493.58;
  - D45 rent. States' mining royalties MH 0853 1,26,178.5; Union petroleum royalty 17,352.43; telecom licence/spectrum 90,659.26 (rent vs NPNFA disposal is a NAD question).

  The SUT mining production taxes are only ≈2,566, so royalties are not in P10. The payers are NFCs, so E_NFPU/E_NFPR and G_* will be mis-stated by up to ₹2.5–3.5 lakh cr in the prior. **Fix:**
  - add a gap-map ref, e.g. `R7x` "GG property income other than dividends (D41 from non-GG, D45 rent)", rows GOV and cols NFC; FC; HH, owned by `government`;
  - payer keys: royalties by mining GOS (public/private from 7.1A/7.1B), PSU loan interest to E_NFPU;
  - the orchestrator edits `data/gap_map.csv` and `accounts.OWNERSHIP`.
- **XR-2 (major).** Pensions paid by departmental enterprises: HH ← E_NFPU (Railways, via the Railway Pension Fund, AFS "Railway Funds" disbursements 59,801.66; Posts `fa9.3201.07.total` 11,674.49 (checked)). No ref. They are part of what public NFCs must pay out (required net −7,04,183). **Fix:** extend R9/R9a to payer E_NFPU (government), or a new ref `R9d`.
- **XR-29 (minor).** Interest between NFCs (inter-corporate deposits; corporate bonds held by NFCs) has no ref; R5 covers FC ← NFC only. Small; log it in fincorp's issues file, or extend R8 to "distributed income and interest between non-government corporations".

---

## 3. Double counting and omissions across blocks (task item 2)

| Item | Blocks | Status | Action |
|---|---|---|---|
| PPF in I_SSAV vs I_INPE | capital_financial, fincorp, timeseries | **Consistent.** PPF moves to I_SSAV (`ppf`, 1,11,927.46; NSSF net collection 4,21,678.36 = 3,09,750.90 + 1,11,927.46, checked); I_INPE excludes it; PPF interest is in R8a `small_savings`, never R9c | timeseries F41 must add I_SSAV{`ppf`} (it plans to) |
| D44 vs interest | fincorp, closure | **Consistent.** GPF → R9c only; Union MH 2049.03.108 (18,841.04) → R3a E_INSP, then R9c `eps`; NPS pass-through | none |
| Food subsidy | households, government, taxes | **Consistent.** GFCE on grain C_CROP ← G_CEN 1,63,971.75 (fixed); S8 is a satellite; excluded from P9a, R10 and PFCE keys | XR-23: the C_TRAD −1,05,007 product subsidy may be States' food subsidies; P9a should give G_STA at least FC16 States' food 54,463.39 before applying the 0.516 ratio |
| Valuables | households, capital_financial, closure | **Consistent.** Jewellery out of PFCE; I2 1,72,126.57 + I2a 2,04,105.43 on SUT 3,76,232.00; D3 → K_HH = I2a | none |
| GST settlement | taxes, timeseries | **Consistent.** Post-settlement; S7 memo; UTGST in T_CGST (`utgst`) | timeseries F14 must register the +5,497.16 UTGST bridge |
| R9b vs CE | factors, government, closure | Consistent in design (CE keeps the imputed contributions; R9b returns them) but the **size is open**: government recommends Centre only 1,86,545.42; closure's planning range is 4.5–6.8 lakh cr | Decision D-2 (§7) |
| FISIM | households, fincorp, rest_of_world | **Inconsistent** (XR-5, XR-13) | see §4 |
| Reinvested earnings | rest_of_world, capital_financial, timeseries | **Consistent.** R14 `di_distributed` = DI debit − R14a; R14 + R14a = 7,24,611.52; K8b `fdi_reinvested_earnings` = R14a (1,63,704.27, NAS) with the same payer split in K7b | none |
| RBI surplus, cash vs accrual | government, fincorp, capital_financial | Consistent on cash (D0-7). capital_financial Q1 (FSF 2022-23 hints at accrual) is outweighed by fincorp C3: new-base 2023-24 RBI saving on cash matches NAS public FC saving − GOS within ₹122 cr. K9b posts the accrued payable only in the financial account, so its two legs are offset by equal K9_GCEN / K9_RBI residuals | XR-27: close capital_financial Q1 in favour of cash; state the K9 offset in K9b's method |
| X_DISC | closure, rest_of_world, capital_financial, production | **Resolved.** D1 written = D2 + D3 + D4 as written (5,71,133.165 with the SUT CIF); the published 5,71,133.27 is a ±₹1 band constraint. D2 uses the SUT CIF 2,12,499.23649; D3 is the NAS 3,58,633.93 | Close FRAMEWORK_REQUESTS P-15 with this rule (XR-16) |
| HDFC merger | fincorp, capital_financial, timeseries | **Inconsistent boundary** (XR-6) | see §4 |
| GG transfers with RoW | government, rest_of_world | **Consistent.** No R15; K6 on the NAS basis | XR-14: use the NAS net (−6,999.68, checked), not BoP gross 8,557 / 1,558 (net −6,999), or K_ROW misses by ₹0.68 cr |
| Vehicle tax | taxes, government | Consistent *if* taxes' C1 is accepted (T_OPRT on C_TREQ; R16 empty) | Decision D-1 |
| MISS, PM-KISAN, interest equalisation, LPG DBT | taxes, government, factors | **Consistent.** MISS in P9 (C_FINS); PM-KISAN in P10a D39; LPG: 2,280 in P9, 9,960 in R10 | government's COFOG current-transfer band waits for the PM-KISAN class (its C10) |
| Capital transfers to K_HH | government, capital_financial, closure | **Conflict** (XR-3) | Decision D-3 |
| Fees (C_PADM PFCE, C4d) vs R16 | households, government | **Consistent** (R16 empty) | none |
| Management-of-debt fee (2,921.79) | fincorp, government | Consistent: not D41 (fincorp bridge step C); it is inside SUT GFCE | none |
| NPISH (C4c) | households, timeseries | **Consistent.** Embedded, memo only; production's C1 `equal` constraints catch a breach | none |

---

## 4. Interfaces (task item 3)

### 4.1 Conflicts to fix (the same quantity computed twice, or a need nobody publishes)

- **XR-4 (major) RBI foreign income.**
  - rest_of_world writes R13 E_RBI `reserve_asset_income` = BoP 1,31,059 (checked), anchored 2%.
  - fincorp's K2a E_RBI prior (1,01,399.09) and its D0-7 evidence use the RBI AR: `sch13.b.sub_total` 1,03,177.64 + `sch14.b` amortisation 2,235.86 = 1,05,413.50 (checked).
  - In the assembled prior, E_RBI is ≈ ₹25.6k out of balance. Because `fincorp.k2.public` has tol 1, the difference is forced onto other public FCs' saving.
  - **Recommended fix** (orchestrator to confirm):
    - rest_of_world keeps the R13 total (NAS 6.1 item 3), but writes E_RBI in two components: `reserve_asset_income` = RBI AR 1,05,413.50 (anchored 2%) and `reserve_income_unexplained` = 25,645.50 (free, low);
    - fincorp recomputes K2a E_RBI from the SAM entries it reads, not from the AR directly. This needs DEPENDS fincorp += rest_of_world (XR-18).
- **XR-5 (major) Household FISIM: deposits vs loans, and group keys.**
  - households splits PFCE FISIM (6,02,896.96, checked) 0.5412 / 0.4588 by end-March 2024 stocks.
  - fincorp splits each sector's FISIM by (r_L − r*)·L and (r* − r_D)·D with r* = 6.7%, cost of deposits 4.8% and return on advances 9.4%. For households that gives a noticeably different split (roughly even, or loan-heavy).
  - The two blocks also name different keys (`aidis_fin_assets` / `aidis_inst_loans` vs `deposits` / `debt_institutional`).
  - If the C4b components and the SNA adjustments in R8a/R5 differ by group, household income by group is wrong even though the totals match.
  - **Fix:**
    - households computes the split with fincorp's reference-rate formula and the same parameters (RTP `rtp.scb_cost_return.*` vintage 2025-12-29, T52(b) stocks), recording r* once;
    - fincorp **reads** the C4b `fisim_deposits` / `fisim_loans` entries by group and uses them as FISIM_D / FISIM_L for households, with the rate method for other sectors only;
    - test: per group, R8a `deposits_bank` + `deposits_nbfc` adjustment = C4b `fisim_deposits`, and the R5 adjustment = C4b `fisim_loans`.
- **XR-6 (major) E_BANK vs K_BANK boundary.**
  - capital_financial maps FSF ODC (SCBs + co-op banks + deposit-taking NBFCs + deposit-taking HFCs, which includes HDFC Ltd) to K_BANK for the whole year, so the merger is internal to K_BANK.
  - fincorp puts the deposit-taking NBFCs'/HFCs' wage bill (F4a CE residual) and their P&L (R4/R5 RTP NBFC/HFC tables) in E_NBFC, and month-weights HDFC (3 months as an HFC).
  - The current and capital accounts of one institution would then sit in different sub-sectors.
  - **Fix:**
    - one boundary: E_BANK ≡ K_BANK ≡ FSF ODC;
    - fincorp moves the deposit-taking NBFC/HFC share of RTP NBFC/HFC P&L and wage bills to E_BANK (FSF `fc_odc_nbfc_dt`, `fc_odc_hfc_dt` stock shares) and drops the HDFC month weighting;
    - taxes T4a and rest_of_world's FC sub-splits use the same boundary;
    - still log NAS 8.12 S122's coverage (fincorp Q2).
- **XR-7 (major) Centre/State boundary.**
  - F4b and C2a split GG by NAS 4.1 institutional NVA: G_STA includes local bodies and State autonomous bodies, and so the societies that implement CSS.
  - R2, K3a and I1a use the **treasury view**: CSS released outside State treasuries (St 18 CSS 4,25,295.58 − MH 3601.06 net 2,38,795.63 = 1,86,499.95) and Union direct grants to ULBs stay G_CEN.
  - So G_STA consumes, per C2a, money it never receives, per R2. The shortfall lands in the K3a bridge remainder and helps push G_STA saving toward zero (government's sign risk).
  - **Fix** (orchestrator): one view for both. Recommended: the institutional view, matching NAS 4.1 and F4b.
    - Add R2 components `css_outside_treasury` and `ulb_direct` (Union grants to ULBs not routed through State treasuries; `ulb.grants_for_centre_s_initiatives` 54,108.73 in 4,620 ULBs is an upper bound, checked).
    - Keep the treasury view as a logged sensitivity.
    - GG totals are unaffected.
- **XR-11 (major) Refs on entries vs refs in filters and whitelists.**
  - government writes pension entries "R9 (group split = R9a)" but filters its constraints on `[R9]`; closure's whitelist lists R9a, not R9.
  - **Fix:** write the group entries under **R9a**, use refs `[R9a]` in `gov.r9.*` and `[R9a, R10, R18]` in `gov.cofog.current_transfers`, and keep R9 as a constraint-only ref.
  - The same rule for every block: a constraint's refs filter names the refs that entries actually carry.
    - fincorp's R3 payer constraints already list [R3, R3a, R8a, R9c, R14].
    - closure's whitelist must add R5 (uses) and R9a (resources); both are already listed. Add R7x/R9d if created.
- **XR-12 (minor) FPI interest on G-secs.**
  - rest_of_world: average FPI holdings × coupon = 13,630.
  - fincorp: average T107 FPI share (1.36% → 2.34%, checked) × payer line = 13,439.
  - Same flow, two formulas. **Fix:** rest_of_world writes it with fincorp's formula (share × the payer interest line net of the pro-rata re-issue receipts), and fincorp reads R14 G_* entries, allocating only the remainder to domestic holders.
- **XR-13 (minor) RoW FISIM (29,793.73, checked).**
  - fincorp says rest_of_world adjusts its interest cells for it; rest_of_world writes R13/R14 = NAS 6.1 = BoP, unadjusted, as NAS does.
  - **Fix:** follow NAS (no RoW interest adjustment). fincorp's FISIM bridge treats RoW FISIM as exported output with no SAM interest counterpart, and T6 checks domestic FISIM (12,30,782.43) only; logged.
- **XR-10 (major) `hh_keys` names and missing keys.** Consumers ask for keys households does not plan to publish, or under other names. Canonical names are in the interface table (§4.3). Missing keys households should add:
  - `hh_national_quintile_xwalk`: persons of each SAM group by national MPCE quintile. factors (IFPRI priors for F1a/F2/F3c) and taxes (IFPRI saving rates in T3a) both need it, and households already estimates the national cut points for `hh_state_xwalk`;
  - `avg_mpce` per fractile class in `hh_group_map` (taxes T3a);
  - State × area × group **consumption levels** in `hh_state_xwalk` (rest_of_world R11a; government R10);
  - `aidis_noninst_loans` (capital_financial S5);
  - asset-class keys `aidis_deposits`, `aidis_equity`, `aidis_mf`, `aidis_small_savings` = `aidis_fin_assets` × AIDIS press-note R/U asset-class shares (fincorp R8a), labelled low.
  - **Insurance:** HCES has no premium item, so fincorp's `insurance_life` / `insurance_nonlife` keys cannot be HCES-based. Use `aidis_fin_assets` for life and the `c4b_insurance_service` shares for non-life premiums, so R17 and the C4b service charge share a key.
- **XR-19 (minor) Component names the time series relies on.** Rename, or have the time series read the owning block's names; freeze them either way:
  - taxes P10a: split `gross_taxes` into `stamps_registration`, `land_revenue`, `property_tax`, `other_production_taxes`; keep `gross_subsidies` (F20);
  - government C2a: C_CROP ← G_CEN component `food_subsidy` (F29);
  - capital_financial K7a: `coop` → `coop_banks`, `non_banks` → `nonbank_deposits` (F39);
  - K8a: write K_HH ← I_LOAN with NAS 5.3 liability-line components (`banks`, `coop_banks`, `nbfc`, `government`, `insurers`, …), not one `total` (F42).
- **XR-9 (major) Time-series government interest (F25, F26).**
  - The SAM definitions list refs [R3, R3a, R3b, R5, R14] but omit **R8a** (`small_savings` ≈ 2,14,948, `gsec_direct`) and **R9c** (`gpf_union` 18,871.50, `gpf_states` 54,183.14). Those are where fincorp writes government interest to households.
  - The 2023-24 check would miss ₹2.3–2.9 lakh cr. **Fix:** add R8a{`small_savings`, `gsec_direct`} and R9c{`gpf_union`, `gpf_states`} with cols G_CEN/G_STA; R3b has no entries.
- **XR-15 (minor) Duplicate constraints tighter than production's.**
  - Production's C1/C2/I1/I2/P7/V1/V2 constraints carry tol_abs = ₹1 × SUT cells (FRAMEWORK_REQUESTS deviation 1).
  - households (0.01), factors (0.01, refs [V1a]), taxes (0.5, refs [P7a]), government (0.5, refs [C2a]) and capital_financial (0.01) re-declare them more tightly. The tighter one binds, which undoes the rounding allowance and creates noise slack (closure R8).
  - **Fix:** do not re-declare production's per-commodity and per-activity targets. Read them with `ctx.block_constraints("production")` for tests. If a refs-filtered copy is needed, copy production's target and tol_abs exactly.
- **XR-20 (minor)** The components filter now exists (FRAMEWORK_REQUESTS P-1), so the "not expressible" constraints in the plans should be declared:
  - households: FISIM 6,02,896.96, govt_housing 20,056, and the imputed-rent band;
  - factors: the 15 NAS 7.1C household controls (components), the regular-CE floor (`kind="min"`) and the household caps (`kind="max"`);
  - fincorp: the † rows;
  - government: `gov.grants.state_receipts` becomes components ≠ `cess_loan_recovery` with target 5,27,931.05 (drop the +78,104 workaround);
  - rest_of_world: optionally, the BoP type totals.
- **XR-22 (minor) Imputed rent, C4a ↔ F3a** (FRAMEWORK_REQUESTS P-11, not implemented).
  - The two sides are output and surplus, so their levels differ (≈15.96 vs ≈14.3 lakh cr, indicative); link the shares, not the levels.
  - **Fix:** factors declares per-group `band` constraints on F3a at (F3a total × households' `c4a_imputed_rent` share) ± 10%, and households declares the C4a imputed-rent total band. A post-balancing test reports the share drift.

### 4.2 Dependency order (DESIGN_BRIEF §4 DAG): recommended changes (XR-18)

All four additions are acyclic (checked by hand against `accounts.BLOCK_DEPENDS`); each is one line in `pipeline/sam/accounts.py`.

| Change | Why | Requested by |
|---|---|---|
| government += taxes | read `tax_classification` (vehicle tax, MISS, LPG, food subsidies, professions tax) and P9a/P10a, so no transfer is booked twice | taxes FR-3 |
| fincorp += government, rest_of_world | read R6, R7 (dividends to government) and R13/R14 (RoW interest and dividends, E_RBI reserve income) instead of recomputing them. Needed for XR-4 and XR-12 | fincorp FR-2; rest_of_world FR-1 |
| capital_financial += households | `hh_keys` for S5 | capital_financial FR-cf-1 |

Resulting build order: production → households → factors → taxes, rest_of_world (either order) → government → fincorp → capital_financial → closure → (post-SAM) timeseries. The time series needs the post-SAM step and a provenance call without a gap-map ref (FRAMEWORK_REQUESTS P-16/FR2-2, still OPEN); its builder should not start before that exists. No cycle arises: neither government nor rest_of_world needs anything from fincorp. rest_of_world's R_ROW closure test reads V3/V4 values straight from NAS 6.1, so it needs no dependency on factors.

### 4.3 Agreed interface table

"Entries" = SAM entries read with `ctx.block_entries`; everything else is a satellite read with `ctx.satellite`. Names in **bold** are new or renamed by this review.

| Producer | Entry / satellite | Consumers | Meaning (unit) |
|---|---|---|---|
| production | constraints `pfce.*`, `gfce.*`, `gfcf.*`, `valuables.*`, `product_taxes.*`, `ce.*`, `os_mi_cfc.*` | households, government, capital_financial, taxes, factors (tests only; do not re-declare, XR-15) | SUT 2023-24 totals by commodity/activity, tol = ₹1 × cells |
| production | entries P2, P5, P6, P8, P9, P10, I3, C/I use cells | taxes (P7b, T_CUST, P9a, P10a), rest_of_world (D2/R_ROW test), government (P9 C_RPET 2,280 for R10 `lpg_dbt`), timeseries | as published |
| households | entries C1a, C4a {actual_rent, imputed_rent, govt_housing}, C4b {fisim_deposits, fisim_loans, explicit_fees, insurance_service}, C4d | closure, fincorp (C4b, XR-5), factors (C4a split for s_imp) | PFCE by group |
| households | `hh_group_map` (+ **avg_mpce**) | all household-keyed blocks, taxes T3a | 24 HCES classes → 10 groups; persons, households, MPCE |
| households | `hh_keys`: `pop_persons`, `pop_households`, `hces_total/food/nonfood/durables`, `pfce_total`, `c4a_*`, `c4b_*`, `aidis_fin_assets`, `aidis_cash_loans`, `aidis_inst_loans`, **`aidis_noninst_loans`**, `aidis_fixed_assets`, `aidis_valuables`, `aidis_total_assets`, **`aidis_deposits`, `aidis_equity`, `aidis_mf`, `aidis_small_savings`**, **`fisim_params`** | factors (pop, c4a_imputed_rent → F3a, aidis_fixed_assets → F3b), fincorp (R8a, R5, R9c life = aidis_fin_assets, R17 = c4b_insurance_service), government (R9a/R10 pop), rest_of_world (R12a pfce_total), capital_financial (S5), taxes (T3a), closure (pop, pfce_total) | levels and shares by group; share = level/Σ level; consumers normalise the levels |
| households | **`hh_national_quintile_xwalk`** | factors (F1a, F2, F3c IFPRI priors), taxes (T3a IFPRI saving rates) | share of each SAM group's persons in national MPCE quintiles q1..q5 |
| households | `hh_state_xwalk` (+ **consumption levels**) | rest_of_world (R11a), government (R10) | State × R/U × State class → group weights and HCES consumption |
| households | `hh_hces_items`, `s8_food_stik`, `c4c_npish_memo`, `c1a_hces_nas_ratio` | government (C2a check; R16 contingency), methodology page | HCES-scale item values by group; S8 |
| factors | entries F1a, F2 {farm, nonfarm}, F3a, F3b, F3c, F4 (E_NFPU, E_NFPR), F4b | closure, taxes (professions tax), government (K3a CFC) | factor income by group; GOS by sector |
| factors | constraint `factors.f4.fc_gos` (= `fincorp.f4a.fc_gos_total`, same series, tol 1) | fincorp | FC GOS 10,86,708.96 |
| factors | `sector_gos`, `gg_centre_state_key`, `factor_income_keys` (+ **`public_sector_wage_key`** = F_LREG × PLFS t35 public share), `va_split_by_activity`, `v1a_parameters` | fincorp (sector_gos; NPS/GPF keys), government (C2a column target; R9a/R9b key), taxes (T3a), timeseries | shares and levels |
| taxes | entries P7a, T1a, T2x, P9a, P10a {**stamps_registration, land_revenue, property_tax, other_production_taxes**, gross_subsidies}, T3 {quasi_corporate}, T3a {income_tax, professions_tax}, T4a {public/private} | government (revenue), closure, timeseries | tax flows |
| taxes | `tax_classification`, `p7a_precheck`, `p9a_by_commodity`, `p10a_items`, `direct_tax_split`, `t3a_sensitivity`, `p7b_tax_by_use` (P7b), `s7_igst_settlement` (S7) | government (tax_classification), Phase 4 | memo and diagnostics |
| government | entries C2a {total, **food_subsidy**}, R1, R2 {fc_grants, css_and_other, **css_outside_treasury, ulb_direct** if XR-7 adopted}, T2b {compensation_grants, cess_loan_recovery}, R2k, R6, R7, **R9a** (group entries), R9b, R10, R18, K3a {**saving_pos/saving_neg**}, K6, K8e, (**R7x**, **R9d** if created) | fincorp (R6, R7), capital_financial (K3a, K6, R2k, K8e), closure, rest_of_world (K6 RoW test) | government flows |
| government | `gov_grants_bridge` (R2), `gov_fiscal_bridge` (K3a), `gov_c2a_keys` (C2a), `gov_transfer_classification` (R18), `gov_r9b_sensitivity` (R9b) | verifier, closure | memo |
| rest_of_world | entries R11a, R12a, R13 {…, E_RBI split per XR-4}, R14, R14a, K5, K8b (bop tags), K8c, D2 | fincorp (R13/R14, XR-4, XR-12), capital_financial (K8b, R14a), closure (D2), timeseries | RoW flows |
| rest_of_world | `row_property_income`, `row_financial_counterparts`, `s1_goods_by_partner`, `s2_services_by_partner`, `s3_remittance_sources` | fincorp, capital_financial (K7b) | memo / interface |
| fincorp | entries F4a, R3, R3a, R4, R5, R8, R8a, R9c, R17, K2a {public/private} | capital_financial (K2a), closure, timeseries | FC income flows |
| fincorp | `fc_public_private` (GOS; CFC is not available, so capital_financial falls back to GOS), `gov_interest_bridge`, `interest_fisim_bridge`, `dividend_matrix`, `mf_lookthrough`, `d44_by_scheme`, `s9_funded_schemes` (S9) | capital_financial (I1a FC split), rest_of_world (memo only), verifier | memo / interface |
| capital_financial | entries I1a, I2, I2a, I3a, K1, K7, K7a {**coop_banks, nonbank_deposits**, …}, K7b, K8, K8a {**NAS 5.3 lines**}, K8d, K9 {residual_pos/neg}, K9b, D3 | closure (D3 → K_HH = I2a; K9), timeseries | capital and financial accounts |
| capital_financial | S4 (4 tables), S5 `s5_hh_wealth`, `k9_decomposition`, `capital_formation_by_account`, `gg_gfcf_key`, `fsf_instrument_closure` | closure, timeseries, BALANCING.md | memo |
| closure | entries K4a, D1; satellites `hh_saving`, `prior_imbalance`, `constraint_gaps`, `institution_gaps`, `xdisc_identity` | report.py, Checkpoint B | household saving by group; diagnostics |

---

## 5. Official totals: declared once, same target (task item 4)

| Official total | Target (source) | Declared by | Status |
|---|---|---|---|
| Household saving K4 | 58,90,330.446044 (`s1_9.household_sector`) | closure `closure.k4.hh_saving_total` = capital_financial `cf.k4.hh_saving` | Duplicate, same selection and target: OK |
| NFC saving K1 | 4,62,996.25 / 24,10,408.53 (`s1_9`) | capital_financial (fixed entries) | OK |
| FC saving K2 (+ public/private) | 9,91,447.76; 5,35,509.90; 4,55,937.86 | fincorp (components filter now available) | OK |
| GG saving K3 | −3,18,384.38 (`s1_9.general_government`) | government | OK; K3a sign handling per XR-17 |
| FC GOS | 10,86,708.96 | factors = fincorp | Duplicate: the two must compute the same float (tol 1 covers any float-order difference) |
| GG GOS | 3,75,679.16 | factors | OK |
| Household gross OS/MI | 97,71,430.53 | factors | OK |
| CE receivable by residents F1 | 94,74,604.95 | factors | OK |
| PFCE/GFCE/GFCF/valuables/product taxes/CE/OS by commodity/activity | SUT | production (+ re-declarations, XR-15) | Fix the tolerances |
| PFCE total | NAS 1.1 1,64,15,546.52 | households `hh.c1.total` (tol 1) | OK |
| GFCE total | NAS 1.14 31,21,027.37 | government `gov.c2.total` (tol 1) | OK |
| GFCF by sector; CIS by sector | NAS 1.11; 1.14 − 1.11 | capital_financial | OK |
| Household financial assets/liabilities | NAS 5.3 36,02,198.51 / 19,09,286.70 | capital_financial (all-fixed; documentation) | OK. FRAMEWORK_REQUESTS does not yet say that all-fixed constraints are allowed; if they are rejected, make them tests |
| BoP current receipts/disbursements; R11–R14; K8b totals; FPI debt | NAS 6.1 | rest_of_world | OK (cross-block constraints allowed, P-6) |
| Union and State taxes (cash bands); CIT, PIT, P9, P10 nets | Receipt Budget / RBI SF | taxes | OK |
| Devolution, grants, pensions, COFOG transfers | FA / RBI SF / NAS 4.2 | government | OK after XR-11 and XR-20; COFOG current transfers only after the PM-KISAN decision |
| Government interest by payer | Union NAS-concept 10,86,513.09 (band 3%); States 4,95,569.04 | fincorp | OK (rows include R_ROW and refs include R14) |
| D1 published | 5,71,133.27 (band ±1) | closure | OK |
| **GDP three ways, GG GDI, BoP, flow of funds (DESIGN_BRIEF §7 identity tests)** | NAS 1.1 / 1.14 / 6.1 | **nobody yet** (FRAMEWORK_REQUESTS FR2-1) | **XR-33: assign them to closure (post-balancing tests)**. closure T9/T10 already cover household and GG GDI; add GDP three ways and the BoP/FoF closures |

No conflicting targets were found: every total declared twice uses the same series. One inconsistent *derived* target remains: `gov.grants.state_receipts` (+78,104; fixed by XR-20).

---

## 6. Accounting closure: will the prior roughly balance? (task item 5)

| Account(s) | Prior expectation | Note |
|---|---|---|
| ACT, COM, M_TTM | Balance within SUT rounding (anchored ±₹1/cell) | M_TTM is solved by production's anchored P3/P4 (deviation 1). closure should drop its M_TTM request to production (XR-16) |
| F_LREG, F_LCAS, F_MIXD, F_GOSC | Balance (factors); F_GOSC needs fincorp's F4a entries to equal the FC constraint | — |
| H_R1..H_U5 | Balance by construction (K4a = pure residual); Z shows on K_HH | Z is the headline finding |
| E_NFPU | **Likely short on outflows by lakhs.** It must pay out 7,04,183 net (GOS − saving). Identified payments (CIT ≈ 0.6–0.7 lakh, R7 71,821, R5, R8) cover only part of it, because D45 royalties (XR-1), departmental pensions (XR-2) and NFC→GG interest have no owner | XR-30: expect this in `institution_gaps` |
| E_NFPR | Its free, very-low-confidence dividend entries absorb the gap | The R8 prior is weak (no dividend data) |
| E_RBI | Off by ≈ +₹25.6k | XR-4 |
| E_BANK, E_NBFC, E_INSP | Many free entries; E_INSP saving likely too high (fincorp risk) | Boundary per XR-6 |
| G_CEN, G_STA | K3a is not a residual (bridge prior), so both carry prior imbalances; G_STA's sign is fragile | XR-7, XR-8, XR-17 |
| Tax accounts, T_PSUB, T_PROD | Balance (T1a/T2x = P7a row totals; P9a/P10a equal the fixed P9/P10) | — |
| R_ROW | Closes to −₹0.0004 cr with the SUT CIF and R15 = 0 | — |
| K_ROW | Closes exactly if K6 RoW nets to NAS −6,999.68 (XR-14). NAS publishes NPNFA as **+1,666.26** (checked); it enters the identity with a minus sign (India pays) | — |
| K_* domestic | Close by construction via K9; K_HH also needs the XR-3 decision | K9 sign lock: XR-17 |
| I_* | Clear (capital_financial). I_OTHR clears by Walras only if all saving/GCF/K6/RoW totals are NAS-consistent | — |
| X_DISC | Closes exactly under closure's rule | XR-16 |
| **No account has entries on only one side.** K_MUTF has I_MFUN liabilities and asset entries. X_DISC has D1 in and D2/D3/D4 out. Every H_g, E_*, G_*, T_* has both sides | | |

**XR-8 (major) The GG current account needs R9b and XR-1 decided together.** Here is a combined sketch from the plans' numbers. It is planning arithmetic, not data:

1. closure's cash sketch gives GG GDI 28,96,316.
2. Pensions net of NPS/CGHS instead of gross add 57,673, giving 29,53,989.
3. Less R10 (≈2,24,260) and R18 (≈25,345): 27,04,384, against NAS 28,02,643 (−98k).
4. Adding R9b at the Centre-only 1,86,545 gives +88k.
5. Adding D45 royalties and rent (XR-1, 1.4–2.3 lakh) gives +2.3 to +3.2 lakh.

So the prior GG account cannot be judged until both are decided. **Recommend:** build R7x first, then run government's T14 (GG GDI with and without R9b), and take the R9b decision on that evidence, plus the NAD question.

---

## 7. Decisions needed from the orchestrator / owner (before the builders start)

| # | Decision | Recommendation | Affects |
|---|---|---|---|
| D-1 | State motor-vehicle tax (1,10,326.52 + 520.55): product tax (T_OPRT on C_TREQ) or R16/P10a | **Product tax** (taxes C1: D29 has no room; it closes 1,10,847 of the 1,58,230 TAX-1 gap) | taxes, government |
| D-2 | R9b size: Centre only (1,86,545.42) vs the gap-map formula (4,27,232.75) | Centre only as the prior, States as a sensitivity, **after** XR-1 and the T14 test (XR-8); NAD question | government, closure, factors |
| D-3 | Capital transfers to K_HH (COFOG ≈ 89,940 + RoW 1,555.69) | **Write them in K6 and let K9_HH (an I_OTHR asset) show the NAS inconsistency** (NAS household saving is measured from the asset side). This keeps GG capital transfers equal to NAS 4.2 COFOG. Alternative: memo only, and restrict `gov.cofog.capital_transfers` to non-household recipients | government, capital_financial, closure |
| D-4 | RBI reserve income: BoP 1,31,059 vs AR 1,05,413.50 on E_RBI | Split component per XR-4 | rest_of_world, fincorp |
| D-5 | Centre/State boundary: treasury vs institutional | Institutional (XR-7) | government, factors, capital_financial |
| D-6 | New refs R7x (GG property income other than dividends, incl. D45) and R9d (departmental pensions); gap-map extensions for taxes' extra cells | Add them, owned by government; edit `data/gap_map.csv` and `accounts.OWNERSHIP` | government, closure (whitelist) |
| D-7 | DAG additions (XR-18) | Approve all four | framework (`accounts.BLOCK_DEPENDS`) |
| D-8 | Quasi-corporate share of MH 0021 on E_NFPR/E_BANK (≈2.17 lakh cr) | Accept (taxes C3; closure R5 agrees in direction) | taxes, closure, fincorp |
| D-9 | STT in T_PIT (the gap-map default) | Accept; NAD question logged | taxes, timeseries |
| D-10 | T2b(ii) 78,104: current (default) or capital | Current for the build; Checkpoint B flag | government |
| D-11 | Co-operative banks in the private FC sector (a deviation from the gap map) | Accept (NAS 1.9 convention) | fincorp, taxes, capital_financial |
| D-12 | New concordance `data/concordance/hces2324_item_to_sut_product.csv` | Approve (P-12) | households |
| D-13 | Closure of FRAMEWORK_REQUESTS P-15 (X_DISC) with closure's rule, and of capital_financial Q1 (RBI surplus basis) in favour of cash | Approve | closure, capital_financial |

---

## 8. Findings index (severity)

| Id | Severity | One line |
|---|---|---|
| XR-1 | critical | GG D45 rent/royalties and non-GG interest receipts unowned (₹2.5–3.5 lakh cr) |
| XR-2 | major | Departmental-enterprise pensions (HH ← E_NFPU) unowned |
| XR-3 | major | Capital transfers to K_HH: government writes them, capital_financial/closure want memo only |
| XR-4 | major | RBI foreign income: BoP 1,31,059 (R13) vs AR 1,05,413.50 (K2a prior) |
| XR-5 | major | Household FISIM deposit/loan split and keys computed twice, differently |
| XR-6 | major | E_BANK vs K_BANK boundary (deposit-taking NBFC/HFC, HDFC) differs between fincorp and capital_financial |
| XR-7 | major | Centre/State: institutional (F4b, C2a) vs treasury view (R2, K3a, I1a) |
| XR-8 | major | GG current account swings ±3 lakh on R9b × XR-1; decide together |
| XR-9 | major | timeseries F25/F26 omit R8a and R9c government interest |
| XR-10 | major | `hh_keys` names and missing keys (national-quintile crosswalk, State consumption, AIDIS classes, MPCE) |
| XR-11 | major | Pension entries' ref (R9 vs R9a) vs constraint filters and closure whitelist |
| XR-18 | major | DAG additions needed (government+taxes; fincorp+government, rest_of_world; capital_financial+households) |
| XR-12 | minor | FPI G-sec interest: two formulas (13,630 vs 13,439) |
| XR-13 | minor | RoW FISIM 29,793.73 has no interest counterpart; follow NAS |
| XR-14 | minor | K6 RoW gross BoP values net to −6,999, not NAS −6,999.68 (K_ROW −₹0.68) |
| XR-15 | minor | Re-declared production constraints with tighter tolerances |
| XR-16 | minor | X_DISC rule agreed (close P-15); M_TTM already solved by production |
| XR-17 | minor | Sign locks: K3a, K9 and K4a use paired `_pos`/`_neg` components (P-9) |
| XR-19 | minor | Component names for the time series (P10a, C2a, K7a, K8a) |
| XR-20 | minor | Declare the constraints now expressible (components filter, min/max) |
| XR-22 | minor | Imputed rent C4a ↔ F3a: link by per-group share bands |
| XR-23 | minor | P9a C_TRAD row: give G_STA its identified State food subsidies first |
| XR-27 | minor | Close capital_financial Q1 (RBI surplus basis) as cash; K9b offset note |
| XR-29 | minor | NFC↔NFC interest unowned (small) |
| XR-30 | minor | Expect a large E_NFPU prior imbalance until XR-1/XR-2 are fixed |
| XR-33 | minor | DESIGN_BRIEF §7 identity tests have no owner: give them to closure |
