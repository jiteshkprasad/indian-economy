# Verification: the `government` block (SPEC s.3 rule 3)

Verifier: an independent agent (not the government builder or integrator), 2026-09-30.

Scope: the government block only: refs C2a, R1, R2, R2k, T2b, R6, R7, R7x, R9 (constraint), R9a, R9b, R9d, R10, R18, K3 (constraint), K3a, K6, K8e (R15 and R16 have no entries, by design), its 12 constraints, 17 checks, 6 satellites and 53 provenance records. I recomputed every entry and every constraint target from `data/clean` Parquet with DuckDB SQL, plain Python and numpy (my own 5 x 2 RAS for C2a). I read only the dependency outputs the block is entitled to read (production's P9 entry on C_RPET and `gfce.*` targets, factors' F4b and F2 entries and its `factor_income_keys` / `gg_centre_state_key` satellites, households' `hh_keys`), plus all built blocks' `*_entries.parquet` for the cross-block checks. I did not import or call `pipeline/sam/blocks/government/` or any `pipeline.sam` module; I read the builder's code only to confirm which warnings it raises and that it has no silent fallback.

Regression test: `tests/verify/test_sam_government_spotcheck.py`: **19 passed, 3 strict xfails** (V-GOV-1, V-GOV-2, V-GOV-3). It imports neither `pipeline.sam` nor polars.

Outputs checked: the build of 2026-09-30 23:37 (`government_*`, 158 entries, 12 constraints, 6 satellites, 17 checks, 53 records).

## Verdict

**Every number the block writes is right. Two small defects (V-GOV-1, V-GOV-2), three labelling / logging gaps (V-GOV-6 to V-GOV-8) and a stale-build flag (V-GOV-9) should be fixed; three major design questions the builder already logged (V-GOV-3 to V-GOV-5) are confirmed and belong to Checkpoint B.**

- **Entries: census, 158 of 158** (75 of them are Rs 10,000 crore or more). Same keys, and every value within Rs 0.0002 crore. The largest differences are RAS convergence noise on C2a (C_PADM <- G_STA: 1.7e-4). All other entries agree to below 5e-7.
- **Constraint targets: census, 12 of 12**, same kind, tolerance, refs and components filter. All 12 hold on the assembled prior of the eight built blocks, and production's six non-zero `gfce.*` targets hold on the C2a entries.
- **Satellites:** every row I could recompute matches (the K3a bridge steps, remainder and priors; the H9 grants bridge; the C2a seeds and Centre column target; the R9b formula; the R7x item list, which partitions MH 0049 + 0802 + 1275 exactly).
- **Provenance:** all 53 records resolve; every entry's status equals its record's; every `official` record rests on official inputs; every record cites the clean records of the series it uses (checked for 13 entry groups and for all 48 records behind the Union's 797 / "met from" lines in the K3a bridge).
- **Official totals:** R1 = Union FA minor heads 901 = AFS States' share (11,29,493.71, exact); R2 treasury parts + T2b(i) + R2k = RBI SF grants from the Centre (5,27,931.05, exact); R6 + Union R7 = FA MH 0050 (1,70,890.51, exact); R9a = pensions net of NPS and CGHS (2,24,647.49 / 4,46,990.75); C2a = SUT GFCE (31,21,027.14; NAS 1.14 is 0.24 higher); K3a = NAS 1.9 GG saving (-3,18,384.38, exact); K6 RoW nets to NAS 6.1 (-6,999.68, exact); K6 paid = NAS 4.2 COFOG + 436.19 (the dropped negative COFOG 05).
- **K8e integration:** capital_financial's `fwtw.i_loan.k_gcen.k_gsta` 1,19,895.65 + K8e (-78,104) = FSF Centre -> States loans 41,791.65.
- **Double counting:** no key is written twice; no other block writes a government ref; the cells government shares with other blocks carry different flows (interest by fincorp and rest_of_world, deposits interest, capital_financial's loans net of K8e). PM-KISAN, MISS, fertiliser, State food subsidies and vehicle tax stay in taxes; the LPG subsidy is split once (P9 2,280 + R10 9,960 = St 7 12,240); the RBI surplus is only in R6. One small double count remains across blocks (V-GOV-1).

## 1. Method (what I recomputed, and how)

All values are 2023-24, Rs crore, current prices, latest vintage (Union FA 2024-12-10, AFS / Expenditure Profile 2025-02-01, RBI SF 2026-01-23, FC16 2026-02-03/05, NAS and SUT 2026-08-31, BoP 2026-07-31, PFRDA 2026-09-28).

1. **R1** = - FA 8 minor head 901 of MH 0005, 0020, 0021, 0037, 0038.01, 0044, 0045 (7 entries; MH 0032 is 0).
2. **T2b** (i) = FA 3601.08.112 + 3602.08.106 = 44,945.51; (ii) = AFS GST Compensation Fund disbursements 1,21,159.00 + the two "met from GST Compensation Fund" deducts = 78,104.00. **K8e** = -(ii) on both legs.
3. **R2k** `igas2_capital` = IGAS-2 capital to State + UT governments = 1,23,957.73. **R2** `fc_grants` = RBI SF ii.d.5; `css_and_other` = RBI SF ii.d - ii.d.5 - T2b(i) - R2k = 2,15,110.62.
4. **Outside-treasury CSS (D2-8):** St 18 III CSS (revenue) 4,25,295.58 - MH 3601.06 net releases (total - 797 - "met from" deducts = 2,57,208.27) = 1,68,087.31, split by the IGAS-2 "Others" capital share 0.11666: R2 1,48,479.11, R2k 19,608.20.
5. **R6, R7** from FA MH 0050 by minor head (101 + 200 -> E_NFPU, 108 + 109 -> E_BANK, 107 -> E_INSP); States RBI SF ii.c.2 -> E_NFPU.
6. **R9a** Centre = MH 2071 - (01.117 + 01.902) - 01.118; States = RBI SF ii.e - PFRDA SG employer contribution; groups by factors' `public_sector_wage_key` levels, normalised. **R9b** = (2071.01 net) x 21/39 + 2071.02 = 1,86,545.42, same key. **R9d** Railways = AFS "Railway Funds" disbursements 59,801.66; Posts = 3201.07 total - .110 = 10,688.30; same key.
7. **R10** States = FC16 cash transfers + social security of the 21 reporting States (2,06,386.82) x g1 1.013194 (MH 2235, 28 / 21 States) x g2 1.024940 (RBI SF i.a.9 / MH 2235) = 2,14,324.92; Centre = FC16 Union social security 18,603.44 and St 7 LPG 12,240 + production P9 on C_RPET (-2,280); all by `pop_persons`.
8. **R18** = IGAS-2 PSU and co-operative grants less their capital parts; St 7 LIC pension subsidy.
9. **R7x** Union: MH 0049.03.190 + .103 (E_NFPU), .109 + .195 (E_NFPR), .118 (households, wage key), MH 0802 .102/.103/.106/.107/.109 and MH 1275 .104 + .105 split public/private by NAS 7.1A/7.1B mining or communication OS + CFC; States: RBI SF ii.c.1 (E_NFPU), FC16 MH 0853 (26 States, 1,26,178.52) by 7.1A/B/C mining OS(+MI) + CFC with the household part by factors' F2 non-farm mixed income, RBI SF ii.c.6.xi by 7.1A/B.
10. **C2a:** C_CROP <- G_CEN = SUT GFCE p001 + p002. Own output: my 5 x 2 RAS, rows = SUT GFCE (p151, p152, p153, p127, p130 + p131), Centre column = F4b G_CEN / (G_CEN + G_STA) x own-output total = 8,74,271.58, seeds = FA sections / MH totals and RBI SF App II as in the plan s.2.1.
11. **K3a:** Centre = -AFS revenue deficit + all 2xxx/3xxx minor heads 797 (4,97,014.59) + all "met from" deducts (-3,21,368.46) + St 6 grand total 3,03,915.55 - T2b(ii) + F4b CFC; States = App IV A - R2k + T2b(ii) + App II ii.c.1 + F4b CFC; remainder -2,07,786.88 allocated 0.48924 / 0.51076 by revenue expenditure; each prior written as a +/- pair whose smaller leg is the |remainder share|. Priors -3,55,034.83 / +36,650.45.
12. **K6:** RoW = BoP payments 8,557, receipts 8,557 + NAS -6,999.68, NAS 1,555.69 (K_HH), NAS NPNFA 1,666.26 (K_NFPR); domestic = COFOG by recipient less the Centre's IGAS-2 capital grants to PSUs + statutory bodies, NGOs and co-operatives.
13. **Cross-block:** assembled prior of all eight built blocks (3,840 entries): key uniqueness, foreign writers of government refs, the cells government shares with other blocks, G_CEN / G_STA imbalances and SAM GG disposable income.

## 2. Values checked

| Item | Count | Result |
|---|---:|---|
| Entries (census) | 158 | all match, max diff 1.7e-4 |
| of which >= Rs 10,000 crore | 75 | all in the census |
| Constraint targets (census) | 12 | all match; all hold on the assembled prior |
| Production `gfce.*` targets on C2a | 6 | hold |
| Satellite rows recomputed | 30 | match (fiscal bridge 7 + the two K3a pair sums, grants bridge 6, C2a keys 11, R9b 2, R7x partition 2) |
| Checks | 17 | 15 pass, 2 fail as logged (government-1, government-9); targets are clean records |
| Provenance records | 53 | all resolve; statuses consistent |
| Prior imbalances (assembled prior) | 2 | G_CEN -1,05,047.10, G_STA +4,84,771.78, GG +3,79,724.67: exactly the builder's figures |

The D2-5 evidence, recomputed on the assembled prior: SAM GG disposable income 31,82,367.43 vs NAS 1.14 28,02,642.99; gaps: no R9b +1,93,179, Centre only (written) +3,79,724, Centre and States +6,20,412. The block's own proxy numbers in `gov_r9b_sensitivity` also recompute (NAS requirement -1,83,400.52 = GDI - CFC - (product taxes - product subsidies + NAS 7.1 net production taxes); interest proxy 15,54,081.38).

## 3. Findings

| # | Severity | Finding | Evidence | Recommended fix | Logged by builder? |
|---|---|---|---|---|---|
| V-GOV-1 | minor | **The States' 14-day ITB interest is counted twice.** RBI SF App I ii.c.1 (28,493.58), which R7x `interest_states` books wholly as G_STA <- E_NFPU, contains the interest the States earn on their cash-balance investment in the Centre's 14-day intermediate treasury bills. fincorp books the same money intra-GG (R3 `itb_14d` G_STA <- G_CEN 1,976.32 = Union MH 2049.01.116). G_STA income is overstated and E_NFPU's outlays are too high by 1,976.32 | fincorp R3 `itb_14d` = MH 2049.01.116 exactly; 14-day ITBs are held only by State governments, and States book the interest in MH 0049 | Deduct Union MH 2049.01.116 (clean data government can read) from `interest_states` and say so in the method; or fincorp drops its entry. government-4 says the item "cannot be separated"; it can | Partly (government-4 notes the item, not the double count) |
| V-GOV-2 | minor | **C2a seeds count public works twice.** States: ii.d.iv public works (13,849.22) is inside ii.d administrative services (PADM seed) and again in the CNST seed. Centre: MH 2059 (2,580.15) is inside the "administrative services" section (PADM) and again in CNST. The plan prescribes both seeds, the builder followed it | App II series ids: ii.d.iv is a child of ii.d; FA section administrative services covers MH 2051-2070 | Drop public works from the PADM seeds. Effect on the prior: Centre PADM +2,219.98, EDUC -1,364.00, HLTH -498.19, CNST -357.79 (States mirror); totals unchanged | No |
| V-GOV-3 | major | **The K3a bridge adds CFC to cash revenue balances.** Confirmed: in the SNA gross saving = GDI - GFCE; GG's GOS (= CFC) is in GDI and CFC is a cost inside GFCE, so CFC cancels and gross saving is close to the cash revenue balance on NAS coverage. Adding CFC treats the cash balance as net saving. The GG total is pinned to NAS 1.9, so only the Centre/State split moves: the remainder becomes +1,67,892.28 instead of -2,07,786.88 and the priors -2,82,310.97 / -36,073.41 | my recomputation of the bridge with and without F4b | Checkpoint B decision (plan s.2.8 and the gap map both say "add CFC"). Note that the evidence in government-27 prefers the CFC version's split, which suggests the remainder rule, not the CFC step, is what is off | Yes (government-25) |
| V-GOV-4 | major | **R9b is written for the Centre (1,86,545.42) although the evidence favours none.** Recomputed: gaps vs NAS GG GDI +1,93,179 (none), +3,79,724 (Centre only), +6,20,412 (both). D2-5 only offers the two non-zero variants, so the choice complies with DECISIONS | assembled prior, `gov_r9b_sensitivity` | Checkpoint B / NAD: amend D2-5 to allow "none", or keep Centre only and let balancing shrink it (free, low) | Yes (government-1) |
| V-GOV-5 | major | **Prior imbalances G_CEN -1,05,047.10, G_STA +4,84,771.78** (GG +3,79,724.67). Recomputed exactly. GG part = SAM GDI - NAS GDI (GFCE and saving are pinned); the split mirrors the treasury cash bridge; independent FSF evidence points the same way | assembled prior | Checkpoint B; explanations after the full run | Yes (government-27) |
| V-GOV-6 | minor | **R7 payer split is labelled `official` and `fixed`, but it rests on an assumption.** MH 0050.101 "Public Undertakings" includes dividends of financial PSUs (public NBFCs such as PFC / REC / IRFC and public insurers), all booked on E_NFPU. The published line is exact, the payer is not; `fixed` stops balancing from correcting it. SAM_GUIDE's own V3 example labels a single-account allocation `derived` | FA MH 0050 minor heads; Receipt Budget groups only RBI + nationalised banks + FIs (1,05,495.32) vs PSEs (65,381.65) | Label `public_undertakings` `derived` (assumption A-R7-1) and consider `anchored` with a small tolerance | Assumption logged (government-15); label/role not |
| V-GOV-7 | minor | **Statutory bodies are classified two ways.** Their IGAS-2 capital grants (1,594.81) are written as K6 to K_NFPU (corporations), while their revenue grants (10,761.31) are left out because "GG or corporations is unknown" | K6 `igas2_psu_statutory` = PSU 16,434.16 + statutory 1,594.81; government-12 | Use one class for both, or log the inconsistency | No |
| V-GOV-8 | minor | **`gov_transfer_classification` lists the LIC pension subsidy twice** (`r18.lic_pension_subsidy` and the St 7 line), so the plan's test "assigns every line exactly once" cannot be applied to the satellite as written. No SAM double count | satellite rows | Keep one row per source line (the St 7 line with destination R18) | No |
| V-GOV-9 | minor | **The build is stale against taxes.** taxes was rebuilt at 23:48, after government (23:37); the hashes in `government_block.json` no longer match. The only taxes figures government reads (G_* <- T_PIT/T_CIT 19,63,692.51) are unchanged, and the three taxes records R9b cites still exist, so no number moves | sha256 of `taxes_*.parquet` vs the catalog | Re-run `uv run python -m pipeline sam government` (the builder's own integration item) | n/a |
| V-GOV-10 | minor | **Two overlap risks not quantifiable from clean data.** (a) R10 Centre `social_security` 18,603.44 may include NSAP money that States also pay out in `cash_schemes` (logged, government-11). (b) R18 `psu_revenue_grants` 24,017.45 (IGAS-2 grants to PSUs) and taxes' P10a FC16 Union "business" subsidies 52,325.27 may contain the same payments; no clean line-level data separates them | FC16 Union subsidy categories; IGAS-2 grantee totals | Log (b) in the issues file; ask taxes / Checkpoint B | (a) yes, (b) no |

Notes that are not findings:
- K6 RoW entries are `fixed` where the plan said anchored 0.01; with the NAS-consistent receipts (XR-14) this is harmless.
- fincorp's R3 `gsec_state_reserve_funds` (G_STA <- G_CEN 18,514.50) is interest on States' reserve-fund investments; it usually accrues inside the funds rather than App I ii.c.1, so I found no overlap with R7x, but fincorp may want to confirm.
- The D2-5 interest proxy still includes the debt-management fee (MH 2049.01.305, 2,921.79), which CROSS_REVIEW classes as a purchase; the effect on the variant ranking is nil.
- `gov_c2a_keys` labels its official seeds and targets `estimated` (one status per satellite record); cosmetic.

## 4. Checks against the plan, the gap map and DECISIONS

- Plan s.8 / CROSS_REVIEW: R7x and R9d built (D2-9, XR-1, XR-2); pension entries under R9a with `[R9a]` constraint filters (XR-11); institutional boundary with `css_outside_treasury` (D2-8, XR-7; `ulb_direct` not added, reasoned in government-6); K3a +/- pairs (XR-17); components filter on the receipts constraint (XR-20); K6 RoW nets to NAS (XR-14); capital transfers to K_HH written (D2-6, XR-3); DEPENDS includes taxes (D2-10); component names `food_subsidy`, `compensation_grants`, `cess_loan_recovery` (XR-19); State food subsidies out of C2a and R10 (XR-23); production's `gfce.*` not re-declared (XR-15).
- DECISIONS: D2-4 (no R16 vehicle tax), D2-5 (both variants reported, Centre only written), D2-13 (T2b(ii) current), D2-16 (R6 cash) are respected.
- Every default, conflict and exclusion I found is in `docs/phase2/issues/government.md` except V-GOV-1 (as a double count), V-GOV-2, V-GOV-6 (label/role), V-GOV-7, V-GOV-8 and V-GOV-10(b).

## Re-verification (wave C close-out, 2026-10-01)

Verifier: a different agent from the builder, the fixing agents and the original verifier (SPEC s.3 rule 3). Scope:
the changes made after the original verification and never checked by another agent: the verification fixes
(V-GOV-1, -2, -6, -7, -8), the second-pass repair (DECISIONS D2-20, R9b none with a memo satellite; the K3a bridge
without the CFC step, with the departmental-enterprise, urban-local-body and remainder-key changes) and the Wave C
audit fixes (`docs/phase2/verify/balanced_sam.md` BS-5 PM-KISAN out of P10a into R10 plus the COFOG current-transfer
band, BS-6 R9d bands, BS-7 outside-treasury CSS band, BS-11 R18 bands, BS-12 C2a band kept; government-32 R7x line
and payer bands). Outputs checked: the build of 2026-10-01 05:40 (`government_*`: 158 entries, 38 constraints, 6
satellites, 17 checks, 57 records) and the balanced run of 05:41 (NEWTON, interior-point fallback, KKT certificate
ok, no slack).

Method: my own DuckDB / numpy scripts (no `pipeline.sam` import, no reuse of the builder's code or of the fixers' test
code) recomputed every changed number from `data/clean` Parquet and the DEPENDS outputs (factors F2 / F4b and
`gg_centre_state_key`, production P9 on C_RPET, taxes' entries); the fixer-edited regression test was then diffed
line by line against the original verifier's version (recovered from the session record of 2026-09-30).

### What was recomputed

| Item | Count | Result |
|---|---:|---|
| Changed entries recomputed independently | 26 | all match: R10 `pm_kisan` x10 (FA 2401.00.130 51,616.91 x factors' F2 farm mixed-income shares, max diff 4.5e-7); K3a x4 (exact); C2a x9 (own 5 x 2 RAS with public works seeded only in CNST, max diff 2.2e-4; seeds equal `gov_c2a_keys` exactly); K6 `igas2_psu` 16,434.16 and the States' K_NFPU residual 62,055.77 (V-GOV-7); R7x `interest_states` 26,517.26 (V-GOV-1). No R9b entry exists (D2-20) |
| Entry census (regression test) | 158 | 148 + 10 `pm_kisan`; keys and values match |
| Constraint targets | 38 | the 26 new ones (COFOG current transfers, R9d x2, outside-treasury CSS, R18 x2, Union R10 x3, 8 R7x line bands, 9 R7x payer bands) recomputed from clean data: every target, kind, tolerance, refs and components filter equal (diff 0.000000); the other 12 are unchanged from the original verification |
| Constraints on the assembled prior | 38 | all hold (9 blocks, 3,893 entries) |
| Constraints in the balanced run | 38 | 28 binding (see V-GOV-13); every Wave C figure quoted in the issues file reproduces (COFOG 10,55,911.73 = +5.0%; R9d 65,781.83 / 11,757.13; CSS outside 1,51,278.58 = R2 1,19,918.58 + R2k 31,359.99; R18 21,615.70 / 1,073.31; R10 49,036.06 / 9,462.00 / 16,743.10; R9a Centre 2,20,154.54; K3a Centre -4,28,507.23, States +1,10,123.35; `cash_schemes` 2,77,356.22) |
| `gov_fiscal_bridge` rows | 44 | all recomputed, including the six sensitivities (e.g. plan bridge -3,55,034.83 / +36,650.45 = the original priors; no-CFC remainder by NVA -3,41,229.82 / +22,845.44, consistent with the original +1,67,892.28 remainder) |
| `gov_r9b_sensitivity` rows | 27 | all recomputed: formula (civil 44,452.42 = (MH 2071.01 net of NPS and CGHS) x 21/39, defence 1,42,093.00), memo (Centre 1,86,545.42, States 2,40,687.33), the proxy components from the entries and taxes' income taxes, and the three variants (delivered / gap / GDI) |
| Other satellites | 3 | `gov_r7x_items` ITB row 1,976.32 excluded; `gov_transfer_classification` one row per source line (PM-KISAN -> R10, statutory bodies intra-G_CEN, a single LIC row); `gov_c2a_keys` seeds |
| Provenance records | 57 | all inputs resolve; every entry's status equals its record's; no `official` record over a non-official SAM input; the four new records (R10 PM-KISAN `estimated`, COFOG target `official`, R9d and CSS targets `derived`) are honest |
| Cross-block | | PM-KISAN booked once (R10; no taxes entry carries it); taxes' gross D39 3,42,136.75 = NAS 4.2 subsidies 9,18,559.13 - NAS 1.1 product subsidies 5,76,422.38, unchanged by the move (Centre 58,290.87 + States 2,83,845.88; the States' residual rose by exactly 51,616.91) |

D2-5 / D2-20 evidence after Wave C (PM-KISAN now an R10 outlay): proxy gaps none +2,761.36, Centre only
+1,89,306.78, Centre + States +4,29,994.11 (`gg_gdi_sketch` +2,761.36 against a 1,40,132 tolerance); on the
assembled prior SAM GG GDI 29,54,120.57 vs NAS 28,02,642.99: none +1,51,477.58, Centre only +3,38,023.00, both
+5,78,710.32. "None" still fits best, so D2-20 stands. Prior imbalances: G_CEN -2,97,655.41, G_STA +4,49,133.22, GG
+1,51,477.82 (= the GDI gap less the 0.24 GFCE rounding), E_NFPU +3,12,829.18, K_HH -3,84,546.82.

Checks of the reasoning:
- K3a: the no-CFC algebra is right (gross saving = GDI - GFCE; GG's GOS = CFC cancels). The urban-local-body step
  is consistent (cityfinance total revenues 2,78,052.97 = own revenue + grants + assigned revenue + other revenue to
  Rs 4e-6; revenue + capital expenditure = total expenditure; grants routed through State treasuries cancel inside
  G_STA; the Centre's capital grants to ULBs, 1,479.24, are removed). The remainder key (NAS 4.1 NVA of autonomous
  institutions and local bodies, Centre part = Union IGAS-2 revenue grants to autonomous bodies 51,351.67, as in
  factors' `gg_centre_state_key`) is a stated judgement; with a remainder of 29,579 the six sensitivities keep the
  Centre between -2.82 and -3.55 lakh (-3.30 to -3.44 lakh for the variants with the repaired coverage). One coverage slip: V-GOV-11.
- PM-KISAN: the evidence (NAS 4.2 COFOG 04.agri current transfers 58,325.32 >= FA 2401.00.130 51,616.91; NAS 4.2
  non-interest current expenditure reconciles within 14,142 only with it as a transfer) supports the move, but it
  reverses an accepted Phase 0 default: V-GOV-12.
- COFOG current-transfer band: NAS 4.2 current expenditure 46,69,538.88 = consumption excl. CFC 27,45,349.53 +
  subsidies 9,18,559.13 + current transfers 10,05,630.22 (exact), and the SAM matches the first two, so R9a + R10 +
  R18 against the third is a fair control even though COFOG 10 (4,54,297.28) is below pensions alone (pensions are
  spread across functions in NAS 4.2). Not a constraint chosen to make a number land.
- No constraint was found that exists only to pin a number: each new target is a published line or total; the
  widths are judgements (V-GOV-13).

### Regression test (`tests/verify/test_sam_government_spotcheck.py`)

The file was never committed, so it was compared with the original verifier's version. Every expectation the
fixing agents changed was confirmed by my own recomputation; **none was reverted**: entry count 158; `farm_key` and
the 10 `pm_kisan` expectations; `int_sta` less MH 2049.01.116 (V-GOV-1); the PADM seeds without public works and
the V-GOV-2 test; K6 `igas2_psu` and the residual (V-GOV-7); the K3a recomputation (no CFC, departmental enterprises,
ULB surplus, NVA remainder key, margins); the R9b satellite and census expectations under D2-20; the D2-5 ranking
test; the 26 new constraint targets and the removal of `len(c) == 12` (replaced by a set equality); the four new
`gov_fiscal_bridge` assertions; provenance count 57 and the new citation checks; `class.pm_kisan == 'none'`; the
V-GOV-1/-2/-3 xfails turned into ordinary tests (all three fixes confirmed). The V-GOV-3 test is weak (it compares the
block's remainder with itself and with the recomputation), but the census pins the no-CFC values, so it was kept.
Added: `test_pm_kisan_moves_d39_between_payers_not_its_total`, `test_d25_evidence_satellite_recomputes_from_the_entries`
and two strict xfails, `test_v_gov_11_k3a_departmental_enterprises_include_mh_3006` and
`test_v_gov_12_pm_kisan_reclassification_is_recorded_in_decisions`. Result: **24 passed, 2 strict xfails**.

### Findings

| # | Severity | Owner | Finding | Evidence | Recommended fix |
|---|---|---|---|---|---|
| V-GOV-11 | minor | government | **The K3a bridge leaves one Railways head in the Centre.** It removes MH 1001-1003 receipts and MH 3001-3003 expenditure (Railways surplus 3,259.69) but not MH 3006 "Appropriations from Railway Surplus" (3,259.68 = 1,500.00 to the Railway Development Fund + 1,759.68 transfer to reserve funds), and its 797 line is added back as an intra-GG fund transfer although the fund is the enterprise's. Centre subtotal -3,44,473.14 should be -3,42,973.14; remainder 28,078.74 not 29,578.74; priors -3,39,089.75 / +20,705.37 not -3,40,382.30 / +21,997.92 (GG total unchanged) | Union FA St 9 MH 3006 (00.102 1,500.00, 00.797 1,759.68); receipts MH 1001-1003 less MH 3001-3003 = MH 3006 to Rs 0.01; strict xfail V-GOV-11 | Add MH 3006 to the departmental-enterprise heads (and drop its 797 line from the fund-transfer sum); state it in the method |
| V-GOV-12 | major | orchestrator (DECISIONS) | **PM-KISAN reclassification reverses an accepted decision without a DECISIONS entry.** D0-5 (accepted, owner delegated) and DESIGN_REVIEW B3 set "farm income support as a production subsidy by default"; since Wave C it is R10 (G_CEN -> households, 51,616.91) and taxes dropped it from P10a. The evidence is reasonable (NAS 4.2 04.agri current transfers 58,325.32; the NAS 4.2 current-expenditure reconciliation) but not conclusive (the 58,325 must also hold any other agricultural current transfers), and the issues file only proposes the decision ("For DECISIONS.md") | DECISIONS.md D0-5; issues government-30 and "Wave C audit"; strict xfail V-GOV-12 | Record a D2-24 amending D0-5 (with the NAS 4.2 evidence); keep the NAD question and the Checkpoint B flag |
| V-GOV-13 | major (Checkpoint B) | government / orchestrator | **The balanced government flows sit on band edges, so their levels are the tolerance choices.** 28 of the 38 government constraints bind; every Wave C band ends exactly on an edge: COFOG current transfers +5.0%, R9d railways and posts +10%, outside-treasury CSS -10%, R18 PSU and co-op grants -10%, Union R10 lines -5% / -5% / -10%, R7x line bands +-5% (`interest_psu`, `interest_states`, petroleum +5%) and payer bands +-25% (mining royalties E_NFPU +25%, E_NFPR -25%, households -25%; telecom E_NFPU +25%); also R9a Centre -2%, States +3%, C2a Centre -10%, COFOG capital +5%. The widths (2-25%) are labelled cash-vs-accrual tolerances but no source fixes them; the prior imbalances (G_STA +4.49 lakh, G_CEN -2.98 lakh, E_NFPU +3.13 lakh) press against every published total, and what is left goes to K3a (88,125 moved) and R10 `cash_schemes` (+29.4%). Each move is logged (government-31 to -36), so nothing is hidden, but e.g. R9d railways 65,781.83 is "AFS + 10%", not an estimate | `balancing_constraints.parquet` (binding flags), `sam_entries_balanced.parquet` | Checkpoint B: label edge values as such in BALANCING.md / the UI, justify each width from evidence or publish a width sensitivity (e.g. half and double), and read the binding pattern as a measure of the unresolved prior imbalance |
| V-GOV-14 | minor | government | **PM-KISAN group key is income-weighted for a flat per-family payment.** Farm mixed income gives H_R4 32.1%, H_R5 19.6%, H_R1 9.8%, urban 6.1%; PM-KISAN pays Rs 6,000 per landholding family. Logged as A-R10-2 (low) | factors F2 `farm` | Add a count-based sensitivity (e.g. households' `pop_households` for the rural groups) or say in the method that the key overweights large farms; Checkpoint B |
| V-GOV-15 | minor | government | **The issues file is stale after Wave C.** government-1 and the checks table give `gg_gdi_sketch` +54,378.27 (SAM 28,57,021.26) and gaps +54,378 / +2,40,924 / +4,81,611 (now +2,761.36 / +1,89,306.78 / +4,29,994.11); "Constraints declared (12)" says `gov.cofog.current_transfers` is not declared (38 constraints now); government-27 and "Prior account imbalances" give GG +2,00,606 (now +1,51,478); the Wave C table gives co-op R18 1,073.29 (1,073.31) | `government_checks.parquet`, `gov_r9b_sensitivity`, constraints | Refresh those passages |

Notes (not findings):
- The bridge removes the Posts' operating deficit (23,068.28) from the Centre, but no SAM flow carries the Centre's
  cover of that loss to E_NFPU; whether NAS records it as a subsidy to the departmental enterprise is a NAD
  question. GG total unaffected; the split moves only through the remainder.
- The K3a pair margins are asymmetric (Centre 4,090.84; States 79,596.63, of which 54,108.73 are the ULB grants for
  the Centre's initiatives); larger pair entries are cheaper to move in cross-entropy. Disclosed in the method.
- Within the CSS band, R2k `css_outside_treasury` rose 59.9% (capital share 0.117 -> 0.207, inside the 0.117-0.272
  range of A-R2-1, logged); R18 `lic_pension_subsidy` (St 7, 134.96, unbanded) fell to 70.32 (immaterial).
- D2-20's figures (+54k vs +2.41 lakh) predate Wave C; the ranking still holds, so the decision is unaffected.

### Verdict

Every changed number the block writes recomputes from clean data, and the cited DECISIONS items (D2-8, D2-20) are
followed. One small coverage defect in the K3a bridge (V-GOV-11, 1,500 crore of the Centre/State split), one
governance gap (V-GOV-12: PM-KISAN reverses D0-5 without a DECISIONS entry) and one Checkpoint B observation about
band-edge levels (V-GOV-13). Status: **needs fixes** (V-GOV-11, V-GOV-12, V-GOV-15).
