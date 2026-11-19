# government: Phase 2 issues

Block `pipeline/sam/blocks/government/` (package: `__init__.py` contract, `deps.py` dependency reads, `parts.py`
entries/constraints/satellites/checks, `core.py` pure helpers). Plan: `docs/phase2/plans/government.md` (its s.8
and DECISIONS D2-x override the body). Amounts are Rs crore, current prices, FY 2023-24. Values marked
*(prior)* are before balancing; values that depend on another block (F4b CFC, taxes' income taxes) are from the
dependency outputs built on 2026-09-30 (see "Integration status"). The block was revised on 2026-10-01 after
the independent verification (`docs/phase2/verify/government.md`): see "Verification dispositions". It was
repaired again on 2026-10-01 (second pass, after the first full balancing attempt failed): DECISIONS D2-20 (R9b =
0) and the K3a saving bridge (no CFC step, departmental enterprises out of the Centre, urban local bodies' revenue
surplus in the States, remainder by the NVA of the units outside the treasuries); see "Repair of 2026-10-01 (second
pass)" below, which also gives GG, G_CEN, G_STA and Z before and after.

| # | Severity | Issue | Impact / what the block does | Status |
|---|---|---|---|---|
| government-1 | major | **R9b, DECISIONS D2-5 evidence test, now D2-20.** GG net distributive flows implied by the prior (R6 + R7 + R7x + income taxes G <- T_PIT/T_CIT - GG interest paid outside GG - R9a - R10 - R18 + R9b) vs the NAS requirement GG GDI - CFC - net taxes on production and imports = **-1,83,400.52**. *Current build (refreshed at the close-out, V-GOV-15; after Wave C's PM-KISAN move):* delivered without R9b -1,80,639.16 (gap **+2,761**); Centre only (R9b 1,86,545.42): +5,906.26 (gap **+1,89,307**); Centre + States (4,27,232.75): +2,46,593.59 (gap **+4,29,994**). *At the second pass (before Wave C):* -1,29,022.25 (+54,378), +57,523.17 (+2,40,924), +2,98,210.49 (+4,81,611). | **Since 2026-10-01 (second pass) R9b = 0 is written ("none"), as DECISIONS D2-20 (amending D2-5) allows: it is the variant with the smallest gap.** No R9b entry exists; the Centre-only (G_CEN 1,86,545.42) and Centre + States (G_CEN 1,86,545.42 + G_STA 2,40,687.33) values are kept as memo rows (`memo.*`) of satellite `gov_r9b_sensitivity`, next to the variant table. Effect on the assembled prior: G_CEN and GG imbalance -1,86,545.42, household income +1,86,545.42, Z -11,44,073.44 -> -9,57,528.03; the check `gg_gdi_sketch` now passes (+2,761.36 against a 1,40,132 tolerance in the current build; +54,378.27 at the second pass). The proxy-based evidence is unchanged; on the assembled prior the SAM GG GDI is 29,54,121 vs NAS 28,02,643 (+1,51,478 on the close-out prior, re-verifier's figure; +2,00,606 at the second pass), all of it distributive flows, see "Prior account imbalances". Reading: NAS 2026 GG GDI appears not to include D612 imputed contributions (it contradicts the gap-map design, where R9b returns the imputed CE). The balancing failure of 2026-10-01 (BALANCING.md) named the R9b entries among the entries dual Newton was shrinking (z about 0.42), which fits the same reading | DONE (D2-20); NAD question and Checkpoint B flag stay |
| government-2 | major | **K3a saving bridge (repaired 2026-10-01, second pass).** Bridge: Centre -3,44,473.14 = -(AFS revenue deficit 7,65,907.57) + 797 transfers 4,97,014.59 + 'met from' deducts -3,21,200.31 + GCCA 3,03,915.55 - T2b(ii) 78,104.00 - departmental enterprises' net revenue (-19,808.60: Railways MH 1001-1003 receipts 2,56,093.42 less MH 3001-3003 2,52,833.73, Posts MH 1201 11,321.36 less MH 3201 34,389.64); States -3,489.98 = RBI SF revenue balance -93,436.89 - R2k 1,23,957.73 + T2b(ii) 78,104.00 + sinking fund 17,463.85 + **urban local bodies' revenue surplus 1,18,336.79** (FC16 cityfinance dump 2023-24, 4,620 ULBs: total revenues 2,78,052.97 - revenue expenditure 1,58,236.94 - IGAS-2 capital grants to ULBs 1,479.24); NAS 1.9 GG saving -3,18,384.38 | **Unexplained remainder +29,578.74** (was -2,07,786.88 with the plan's CFC step), allocated by the NVA (NAS 4.1) of the GG units outside the treasury accounts as F4b splits them: Centre 51,351.67 (autonomous bodies F4b gives the Centre), States 3,19,945.58 (local bodies 2,18,133.04 + other autonomous institutions 1,01,812.54): Centre share 0.1383. *Priors:* G_CEN **-3,40,382.30**, G_STA **+21,997.92** (plan: -3,55,034.83 / +36,650.45; within 50,000 of zero: sign fragile, warned). Pairs: margins 4,090.84 (Centre) and 79,596.63 (States = remainder share 25,487.90 + the ULB grants for the Centre's initiatives 54,108.73, whose capital part is unknown). Satellite `gov_fiscal_bridge` has every step and six sensitivities: the plan's bridge (reproduces the old priors exactly), no CFC with revenue-expenditure allocation (V-GOV-3: -2,82,310.97 / -36,073.41), no CFC with the NVA key (-3,41,229.82 / +22,845.44), remainder by revenue expenditure (-3,30,002.16 / +11,617.78), remainder all to the States (-3,44,473.14 / +26,088.76), ULB surplus without the Centre's-initiative grants (-3,32,898.88 / +14,514.49). Every rule puts the Centre at -2.8 to -3.6 lakh and the States at -0.4 to +0.4 lakh: the prior split is robust, so the Centre/State imbalances (government-27) sit in the SAM's flows, not in the bridge. Not bridged (no 2023-24 clean data): panchayats' surplus (RBI PRI panel 2022-23: receipts 35,354 vs revenue expenditure 20,712 on a partial panel), CSS implementing agencies outside treasuries, autonomous bodies' own saving, State departmental enterprises inside the RBI SF accounts; they are in the remainder. **Close-out (V-GOV-11, 2026-10-01):** MH 3006 'Appropriations from Railway Surplus' (00.102 Railway Development Fund 1,500.00 + 00.797 1,759.68 = 3,259.68, the Railways' surplus appropriated to the Railways' own funds) is now a departmental-enterprise head and its 797 line leaves the fund-transfer sum: departmental net -23,068.28, 797 transfers 4,95,254.91, **Centre -3,42,973.14** (+1,500.00), **remainder +28,078.74**, *priors* **G_CEN -3,39,089.75, G_STA +20,705.37**, margins 3,883.38 / 78,304.09; the GG total is unchanged | OPEN (remainder 28,079 unexplained; Checkpoint B) |
| government-3 | major | **Spectrum and telecom receipts (R7x).** MH 1275: WPC receipts 56,317.40 (spectrum auction instalments + usage charges), licence fee 13,640.76, universal access levy 22,722.41, other 345.70, refunds -2,367.01 | Licence fee + USO levy (**36,363.17**) written as rent D45 (assumption A-R7x-3: annual charges on AGR); WPC, other and refunds (net **54,296.09**) **excluded** (SNA: sale of a non-produced asset if the licence is long-term; NAS treatment unknown). NAD question. If NAS treats WPC as rent, GG income is 54k higher and the government-1 gaps move by +54k | OPEN (NAD) |
| government-4 | minor | **States' interest receipts** (RBI SF ii.c.1, 28,493.58) have no payer detail, and they include the interest on the States' cash-balance investment in the Centre's 14-day intermediate treasury bills (intra-GG) | **ITB part fixed 2026-10-01 (V-GOV-1):** it is Union MH 2049.01.116 (1,976.32; 14-day ITBs are issued only to State governments), which fincorp books as R3 `itb_14d` G_STA <- G_CEN, so it is taken out of R7x `interest_states` (now **26,517.26**, listed as excluded in `gov_r7x_items`) and out of the D2-5 interest-paid proxy. The rest goes to E_NFPU (assumption A-R7x-4: loans to State PSUs dominate) | OPEN (payer detail) |
| government-5 | minor | **R7x exclusions** (Union MH 0049.03 / 0802, in satellite `gov_r7x_items`) | Excluded: interest on investment of cash balances 9,643.04 (intra-G_CEN), SDR interest 5,411.10 (RoW, rest_of_world R13), premium + interest on market loans 38,778.00 (accrued-interest offsets, fincorp R3b), foreign governments + IFIs 339.67 (RoW), other receipts / grantee balances / refunds 1,151.78 (payer unknown), interest from States and UTs 13,641.26 (intra-GG, fincorp R3), Petroleum Act receipts and other 1,933.66 (fees / unknown). Included Union: PSU + DCU interest 9,286.80, other parties + co-ops 358.67, government servants 63.80, petroleum rents 15,418.78, telecom 36,363.17 (Union total **61,491.21**); States: interest 26,517.26 (ii.c.1 28,493.58 less the 14-day ITB interest 1,976.32, intra-GG, V-GOV-1), mining royalties 1,26,178.52, petroleum royalties 7,269.85 (States total **1,59,965.63**). Each total held by a +-5% band (`gov.r7x.g_cen`, `gov.r7x.g_sta`) | OPEN |
| government-6 | major | **Centre/State boundary (D2-8 institutional).** CSS released outside State treasuries = Statement 18 III CSS (revenue) 4,25,295.58 - MH 3601.06 net releases 2,57,208.27 = **1,68,087.31** (IGAS-2 'Others' grantees 1,73,699.15: -3.2%, check passes) | Written as R2 `css_outside_treasury` 1,48,479.11 (current) and R2k `css_outside_treasury` 19,608.20 (capital, by the IGAS-2 'Others' capital share 0.1167, assumption A-R2-1; the State+UT capital share 0.2717 would give about 45,675). Not bridged: St 18 III 'other categories' 1,30,950.54 and 'central sector schemes' 15,096.05 vs MH 3601.08 releases (65,888), and Union direct grants to ULBs (ULB dump 54,108.73, an upper bound; not added because the same scheme money reaches ULBs through the CSS releases: double-count risk). The treasury view (without these components) is the sensitivity; GG totals are unaffected | OPEN |
| government-7 | minor | **C2a Centre share.** F4b key 0.29566 x own-output GFCE 29,57,055.38 = 8,74,271.58 for the Centre's own output; with free grain the Centre has 10,38,243 (33.3%) of GFCE *(prior)* | Assumption A-C2a-2 (non-CE costs proportional to CE) probably understates the Centre (defence IC). Band constraint `gov.c2a.centre_own_output` +-10% keeps balancing from moving lakhs between levels. RAS (since 2026-10-01 public works are seeded once, in CNST, V-GOV-2): Centre shares PADM 0.4427, EDUC 0.0695, HLTH 0.0832, CNST 0.1251, UTIL 0 (2026-09-30: 0.4415, 0.0714, 0.0854, 0.1282) | OPEN |
| government-8 | minor | **Group keys are proxies** (no microdata, D1-2) | R9a, R9d and R7x (government servants) use factors' `public_sector_wage_key` (R9b would too, but D2-20 writes none); R10 uses population; R7x household mining royalties use F2 non-farm mixed income. All free, low. Since factors' D2-19 (k = q) the key rises with the group (H_U4 0.1278, H_U5 0.3307; R9a H_U4 85,828, H_U5 2,22,118): the U4/U5 near-tie of the crosswalk key is gone | OPEN |
| government-9 | minor | **Check `cofog_current_transfers` fails:** R9a + R10 + R18 = 9,39,871.58 vs NAS 4.2 COFOG current transfers 10,05,630.22 (-65,758.64, -6.5%; tolerance 5%) | Not declared as a constraint. Investigated 2026-10-01 (second pass): NAS 4.2 GG "current expenditure" excludes interest and is consumption excl. CFC 27,45,349.53 + subsidies 9,18,559.13 + current transfers 10,05,630.22; the SAM's GFCE excl. CFC (27,45,347.98) and subsidies (P9a + P10a gross, 9,18,559.18, taxes derives D39 from this NAS 4.2 total) match it, so the whole shortfall is in current transfers. The best-evidenced candidate is **PM-KISAN** (government-30): NAS 4.2 books 04.agri current transfers 58,325.32, while taxes books PM-KISAN (FA 2401.00.130, 51,616.91) as a Union D39 subsidy inside the NAS 4.2 subsidy total. Reclassified, the check would read -14,141.73 (-1.4%, passes). Not changed here: P10a is taxes' ref, and writing R10 while taxes keeps P10a would count PM-KISAN twice. The earlier scope doubts (COFOG 10 below pensions alone) are moot at the total: pensions must be inside the 10,05,630 for the totals to match within 1.4% | FIXED 2026-10-01 (Wave C: PM-KISAN moved to R10, government-30; `gov.cofog.current_transfers` declared; see 'Wave C audit') |
| government-10 | minor | **Departmental enterprises.** R9d Railways = AFS Railway Funds disbursements 59,801.66 (assumption A-R9d-1: dominated by the Railway Pension Fund; the Railways appropriated 59,800.00 to funds in MH 3002/3003 .12 the same year; DRF/DF withdrawals may be inside). Posts = MH 3201.07 pensions 11,674.49 - NPS 986.20 = 10,688.30 | R9d written HH <- E_NFPU (free, low, public-sector wage key). The Union revenue balance in the K3a bridge still contains the Railways' and Posts' operating accounts (NAS puts them in E_NFPU); not removed, so part of government-2's remainder | OPEN |
| government-11 | minor | **R10 Centre `social_security` 18,603.44 (FC16 Union)** may include NSAP money released through MH 3601 or outside treasuries | Double-count risk with States' `cash_schemes` (2,14,324.92) and, under D2-8, with `css_outside_treasury`. No clean NSAP split (Union MH 2235.03 is 7.57). LPG DBT = St 7 LPG 12,240 - production P9 on C_RPET 2,280 = 9,960. States: FC16 cash transfers + social security, 21 reporting States 2,06,386.82 x g1 1.01319 (MH 2235, 28 / 21 States) x g2 1.02494 (RBI SF social security and welfare / MH 2235) | OPEN |
| government-12 | minor | **R18 coverage.** Written: PSU revenue grants 24,017.45 (IGAS-2 total - capital), co-op revenue grants 1,192.57 (to **E_NFPR**: co-operatives are private corporations in NAS, assumption A-R18-1; the plan said E_NFPU), LIC senior-citizen pension subsidy 134.96 | Not written: statutory bodies' revenue grants 10,761.31 (assumption A-K6-4: statutory bodies and development authorities are GG autonomous institutions, so the grant is intra-G_CEN; since 2026-10-01 their capital grants, 1,594.81, get the same class, V-GOV-7; if NAS puts some of them in corporations, both parts should be written, as R18 and K6), NGO revenue grants 1,600.95 (NPISHs; small), any State transfers to corporations (no data). Satellite `gov_transfer_classification` lists every St 7 / FC16 / IGAS-2 line and where it is booked, one row per source line (the LIC subsidy was listed twice until 2026-10-01, V-GOV-8) | OPEN |
| government-13 | minor | **K6 domestic.** NAS 4.2 COFOG capital transfers 1,76,709.98 by recipient; COFOG 01 GPS (11,775.98) assumed to include the BoP grants to the RoW (8,557, assumption A-K6-3); 05 environment -436.19 dropped (a negative capital transfer has no recipient) | Written: Centre = IGAS-2 capital to PSUs 16,434.16 (K_NFPU, component `igas2_psu`), NGOs 130.95 (K_HH), co-ops 159.15 (K_NFPR); States residual K_HH 89,809.14, K_NFPU 62,055.77. Since 2026-10-01 the statutory bodies' capital grants (1,594.81) are intra-G_CEN (A-K6-4, V-GOV-7), so the States' K_NFPU residual rose by that amount (the COFOG total is unchanged). D2-6: capital transfers to households are in K6 (K_HH total 89,940.09 + RoW 1,555.69), so capital_financial's K9_HH shows the NAS household-saving inconsistency. Not written: States' loan waivers (FC16 24,505.30; COFOG 04.agri capital is only 3,746.05, so NAS may treat them differently) | OPEN |
| government-14 | minor | **K8e is conditional** on capital_financial writing the FSF Centre -> State loan flow net of it (41,791.65 + 78,104.00 = 1,19,895.65) | K8e written (-78,104.00 on K_GSTA <- I_LOAN and I_LOAN <- K_GCEN, fixed). **Integration checked 2026-09-30:** capital_financial reads K8e and writes the FSF pair net of it (satellite `s4_fwtw_sam` `fwtw.i_loan.k_gcen.k_gsta` = 1,19,895.65; its check `centre_state_loans.afs` FSF 41,791.65 = Union AFS 41,791.66; capital_financial-16 DONE) | CLOSED |
| government-15 | minor | R7 payer mapping: MH 0050.101 'public undertakings' (63,827.41) includes financial PSUs' dividends | All to E_NFPU (assumption A-R7-1); 108 nationalised banks + 109 IDBI -> E_BANK 14,295.56; 107 LIC -> E_INSP 4,272.54; States 6,914.54 -> E_NFPU. FA total 1,70,890.51 vs Receipt Budget 1,70,876.97 (+13.54, check passes). **Label fixed 2026-10-01 (V-GOV-6):** `public_undertakings` (A-R7-1) and the States' `state_enterprises` (A-R7-2, same rule) are `derived` (a published total put on one payer by assumption), still `fixed`: the Union total is exact and held by `gov.r7.union` with the banks and LIC entries fixed, so `anchored` would give balancing no freedom, and no alternative payer entry can be seeded from clean data | OPEN |
| government-16 | minor | T2b(ii) 78,104.00 class: current (DECISIONS D2-13) vs capital (SNA 2008 s.10.201) | Current. Moving it to capital changes only the K3a split (+-78,104). Checkpoint B flag | OPEN (Checkpoint B) |
| government-17 | minor | **R15 and R16 not implemented** (no entries; `refs_not_implemented` in the catalog) | R15: NAS 6.1 books GG transfers with the RoW as capital (BoP BPM6 1.C.2 1,463 / 7,820 would double count 6,357-7,000 with K6). R16: fees are sales of non-market output (already in PFCE/net GFCE), vehicle tax is a product tax (D2-4: taxes T_OPRT 1,10,326.52), old-base NAS households pay no D59/D7 to GG, fines are tiny (Union 23.39) | CLOSED (reasoned) |
| government-18 | minor | R6 is cash (87,416.22, D0-7/D2-16); the accrued 2023-24 surplus 2,10,873.99 is capital_financial's K9b timing item | The SNA 7.131 super-dividend test is not applied (RBI 2022-23 income includes FX gains; applying it would move the whole 87,416 to I_EQTY). NAD question | OPEN (NAD) |
| government-19 | minor | **Interest proxy in the D2-5 evidence**: Union MH 2049 11,01,867.87 - interest on reserve funds 1,111.55 - interest on 14-day treasury bills 1,976.32 (paid to the States, intra-GG; deducted since 2026-10-01 with V-GOV-1) - premium/interest received on market loans 38,778.00 = 10,60,002.00; States' interest 5,07,175.37 - interest on Central loans 15,072.31 = 4,92,103.06; total 15,52,105.06 (15,54,081.38 before V-GOV-1) | fincorp (which depends on government) writes the SAM interest entries; its planned NAS-concept targets are 10,86,513.09 + 4,95,569.04 = 15,82,082.13 (28,001 more), which would lower every gap in government-1 by 28,001 without changing the ranking. closure re-runs the GG GDI test on the balanced SAM. **As built (integration 2026-09-30):** fincorp's entries total 10,87,704.16 on the Union column and 4,94,613.30 on the States column (its NAS-concept bands hold), but 65,149.08 of that is intra-GG R3 (Centre <- States 44,658.27, States <- Centre 20,490.81, versus the 15,072.31 the proxy removed), so GG interest paid to non-GG units is R3a 11,47,662.35 + R8a 2,52,628.85 + R9c 73,054.64 = 14,73,345.84, plus rest_of_world R14 on G_* 43,822.54 = **15,17,168.38**, i.e. **34,936.68 below the proxy** (36,913.00 before the ITB line left the proxy). This raises every government-1 gap by 34,937 (it does not lower them as expected), ranking unchanged. The proxy still includes the debt-management fee MH 2049.01.305 (2,921.79), a purchase in CROSS_REVIEW (verifier note); not changed: it feeds only the logged evidence and shifts all three proxy gaps equally | OPEN |
| government-20 | minor | GST compensation grants: Union 44,945.51 (= KFI 28 States) vs RBI SF 45,464.24 | Union control (T2b(i), fixed); the 518.72 difference is absorbed by R2 `css_and_other` (anchored +-10%), which equals RBI SF grants - FC - T2b(i) - R2k = 2,15,110.62 | CLOSED |
| government-21 | minor | Free grain C_CROP <- G_CEN = SUT GFCE 1,63,971.75 (fixed; component `food_subsidy`, XR-19) | Cross-checks only: St 7 food subsidy 2,11,814.39, FC16 Union food 2,30,755.71, FA 2408.01.102 1,84,468.93 (TAX-11) | CLOSED |
| government-22 | minor | States' pensions: RBI SF 4,90,983.18 (States + UTs, control) vs FC16 KFI 4,94,938.72 (28 States; check within 1% passes, -0.8%) | R9 States net = 4,90,983.18 - PFRDA State employer NPS 43,992.43 = 4,46,990.75 (assumption A-R9-1: the NPS contribution is booked in the pension head); Centre = MH 2071 2,38,328.30 - NPS 9,398.08 - CGHS 4,282.72 = 2,24,647.49. Bands +-3% / +-2% | OPEN |
| government-23 | minor | Mining royalties: FC16 State accounts MH 0853 1,26,178.52 (sum of the States reported; UTs missing) vs RBI SF 'industries' 1,27,121.53 (all States + UTs, but includes non-mining receipts) | MH 0853 used (concept-exact). Payers by NAS mining OS(+MI) + CFC: public 7.1A 2,11,638.09 (49.6%), private 7.1B 87,628.23 (20.5%), households 7.1C 1,27,756.39 (29.9%, minor-mineral quarrying), households to groups by F2 non-farm mixed income | OPEN |
| government-24 | minor | Institutional view vs capital_financial's GFCF key | capital_financial's plan uses the treasury view for I1a; under D2-8 the outside-treasury CSS capital (R2k component) is G_STA's. Flagged for capital_financial. **Integration checked 2026-09-30:** capital_financial moved to the institutional view as far as clean data allow (capital_financial-11: ULB capital grants in the States, central autonomous bodies in the Centre, Centre share 0.454742) and logs that the GFCF of CSS societies financed outside State treasuries is not identifiable (R2k `css_outside_treasury` 19,608.20 is the transfer, not the GFCF); only the GG GFCF total is constrained | CLOSED (limitation logged as capital_financial-11) |
| government-25 | major | **K3a bridge added CFC to cash revenue balances (plan s.2.8), a double count.** SNA algebra: gross saving = GDI - GFCE, GDI contains GG's GOS (= CFC) and GFCE contains CFC as a cost, so CFC cancels and gross saving is the current (revenue) balance on a NAS-coverage basis | **Fixed 2026-10-01 (second pass)**: the CFC step is gone (CFC is kept as memo rows `memo.cfc_f4b_*` of `gov_fiscal_bridge`). The earlier objection (dropping it moved the split away from the evidence) is answered by the rest of the repair: with the NAS-coverage items that the treasury balances miss (departmental enterprises out of the Centre, urban local bodies' surplus in the States, government-2) the remainder falls from -2,07,787 to +29,579 and the priors land where the plan's did (-3,40,382 / +21,998 vs -3,55,035 / +36,650). V-GOV-3's strict xfail is an ordinary test now | CLOSED |
| government-26 | minor | **GG interest received from banks (fincorp R4, `deposits`): G_CEN 26,956.05, G_STA 83,375.64 (free)** from FSF deposit stocks x cost of deposits | Not in any government bridge: treasury cash shows no such receipt except States' interest receipts 28,493.58, which R7x books wholly from E_NFPU (A-R7x-4). New evidence (2026-10-01): the 4,620 urban local bodies report interest income of only 3,158.31 in 2023-24 (FC16 cityfinance dump), so the deposit holders inside G_STA the R4 entry would need are not visible in clean data. It is 1.10 lakh of the GG excess of +2.01 lakh (government-27) and 83k of the States' surplus; for fincorp / Checkpoint B | OPEN (fincorp) |
| government-27 | major | **Prior G_CEN / G_STA imbalances: the GG total and the Centre/State split are both off** (assembled prior after the 2026-10-01 second pass: government, fincorp, capital_financial, closure rebuilt): G_CEN **-2,98,136.03**, G_STA **+4,98,742.38**, GG **+2,00,606.36** (before the pass: -96,938.08 / +4,84,089.85 / +3,87,151.78) | GG: +2,00,606 = D2-5 baseline gap 54,378 (proxy-based) + GG interest paid below the proxy 34,937 (fincorp / rest_of_world) + fincorp's R4 deposit interest to GG 1,10,332 (government-26) + RoW R13 960; R9b is gone (D2-20). Split: the Centre's SAM saving-equivalent is -6,38,518 against its prior -3,40,382, the States' +5,20,740 against +21,998. The repaired bridge shows this is not a bridge artefact (government-2: every allocation rule gives about -3.4 / +0.2 lakh). Traced against the cash accounts (see "Prior account imbalances"): Centre receipts 1.60 lakh below and payments 1.34 lakh above the bridge (largest identified items: C2a own-output GFCE excl. CFC 1,14,064 above the Centre's cash functional seed, WPC spectrum excluded 54,296, interest items); States: CSS released outside treasuries 1,48,479 received with no identifiable agency spending, R4 83,376, and States' other current outlays about 3.3 lakh below their treasury revenue expenditure. Independent FSF evidence (capital_financial `k9_decomposition` term `nas_vs_fsf`) points the same way (States 1,97,779 higher, Centre 1,42,584 lower than the new priors); its GG GFCF key leaves out local bodies' own capital formation (ULB capital expenditure 1,07,403.84 in the same cityfinance dump), which would raise the FSF-implied States saving further (for capital_financial). Balancing can move the split through the K3a pairs (free, low), the C2a band (+-87,427) and free entries; explanations are due after the full run | OPEN (finding for BALANCING.md / Checkpoint B); close-out prior: G_CEN -2,98,948, G_STA +4,50,426, GG +1,51,478 ("Prior account imbalances") |
| government-28 | minor | **Possible overlap: R18 `psu_revenue_grants` vs taxes' P10a FC16 Union 'business' subsidies** (verifier V-GOV-10(b)) | R18 writes the IGAS-2 grants-in-aid to PSUs less their capital part (24,017.45, E_NFPU <- G_CEN); taxes books the FC16 Union 'business' subsidies (52,325.27) as P10a other subsidies on production (its `tax_classification`). Operating support to PSUs may sit in both; no clean line-level data maps IGAS-2 grantees to FC16 categories, so the overlap cannot be measured (upper bound 24,017.45). Not changed; raised with taxes and for Checkpoint B. (V-GOV-10(a), R10 Centre social security vs NSAP, is government-11.) | OPEN (Checkpoint B; R18 now banded +-10%, audit BS-11) |
| government-29 | minor | **Interest on GG-held bank and NBFC debt is written by no block** (fincorp's verifier V-FIN-4, 2026-10-01; fincorp-20 says government's R7x takes it) | R7x books only fiscal cash lines (Union MH 0049.03 by minor head, RBI SF App. I ii.c.1) with non-financial payers (A-R7x-2, A-R7x-4); no clean data splits Union .190 'public sector and other undertakings' between non-financial and financial PSUs, and interest on securities held in Public Account funds (e.g. NSSF) does not pass through MH 0049. So R7x does not take the FSF-based interest on GG's holdings of bank and OFC bonds and loans; government's position is that it belongs in fincorp's interest matrix (R4, a fincorp cell), with the risk that part of it is already inside R7x `interest_psu` (E_NFPU). For fincorp / Checkpoint B | OPEN (fincorp) |
| government-30 | minor | **PM-KISAN is a current transfer in NAS 4.2, a subsidy in taxes' P10a** (found 2026-10-01 while investigating government-9) | NAS 4.2 04.agri current transfers 58,325.32 (2023-24) against taxes' `p10a_items` `pm_kisan` 51,616.91 (FA 2401.00.130) inside the Union's gross D39 1,09,907.78, which taxes carves out of the NAS 4.2 subsidy total (so the States' D39 residual, 2,32,228.97, is 51,616.91 too low if PM-KISAN is a transfer). Proposed joint change: taxes drops `pm_kisan` from P10a (the States' residual rises by the same amount, total D39 unchanged); government writes R10 `pm_kisan` H_* <- G_CEN (FA 2401.00.130; a farm-household key). Effect: GG GDI -51,617 (GG gap +2.01 -> +1.49 lakh), G_STA imbalance -51,617, Centre unchanged, household income +51,617 (Z better by the same), `cofog_current_transfers` passes (-1.4%). Not done here (taxes' ref; writing R10 alone would double count) | DONE 2026-10-01 (Wave C, jointly with taxes-28) |
| government-31 | **major (finding; Checkpoint B)** | **Balancing put the States' excess into R10 beyond NAS 4.2 COFOG** (balanced run of 2026-10-01). R10 `cash_schemes` (G_STA -> H_*, free, low) 2,14,324.92 -> 3,72,073.23 (+1,57,748.31, +73.6%; every group z 1.73-1.75); GRAS on the same prior gives 2,25,186.33 (+5.1%). Balanced R9a + R10 + R18 = **11,06,002.30 vs NAS 2026 St 4.2 COFOG current transfers 10,05,630.22 (+1,00,372.08, +9.98%)**; against the like-for-like 9,54,013.31 (PM-KISAN 51,616.91 sits in taxes' P10a, government-30) +1,51,988.99 (+15.9%). The prior was 9,39,871.58 (-6.5%, government-9). FC16 cash transfers + social security of the 21 reporting States are 2,06,386.82 | Cause: `gov.cofog.current_transfers` is not declared (government-9), and R10 `cash_schemes` is the largest low-weight G_STA -> household flow, so cross-entropy sent there most of the States' prior excess (G_STA +5,00,750.13: government-27) and of Z (-4,36,163.72) that the binding K4 constraint had to close. The direction is documented (closure `institution_gaps`; RBI SF revenue expenditure about 3.3 lakh above the States' outlays the SAM writes; households' transfers about 2.8 lakh below the old-base D6+D7 share, fincorp), the level is not: the 20 R10 items in `pipeline/sam/explanations/government.yaml` (10 entries, 10 H_g <- G_STA cells) say "level unexplained". Proposal for the next government pass (not done here: code): settle PM-KISAN with taxes (government-30), then declare the COFOG current-transfer band so the States' excess has to leave through GG income (fincorp's R4 deposit interest, government-26) or the outside-treasury CSS transfer (government-34), or show as slack | BOUNDED 2026-10-01 (Wave C, audit BS-5); the level stays a Checkpoint B finding |
| government-32 | major | **R7x published line totals are held only through each government's R7x total** (`gov.r7x.g_cen` / `.g_sta`, +-5%; the method text says so: "the payer split is a key; the total is held by the gov.r7x.* band"). In the balanced run both bands bind (G_CEN 61,491.21 -> 64,565.77, top; G_STA 1,59,965.63 -> 1,51,967.35, bottom) and the lines move with the payer-cell multipliers: `interest_psu` 9,286.80 -> 13,085.62 (+40.9%, one payer, Union MH 0049.03.190 + .103), `petroleum_rent` 15,418.78 -> 19,016.85 (+23.3%), `interest_states` 26,517.26 -> 30,869.57 (+16.4%, one payer, RBI SF ii.c.1 less the ITB interest), `petroleum_royalties` 7,269.85 -> 7,407.77 (+1.9%), `mining_royalties` 1,26,178.52 -> 1,13,690.01 (-9.9%), `telecom_licence` 36,363.17 -> 32,124.89 (-11.7%), `interest_other_parties` 358.67 -> 290.17 (-19.1%, one payer) | The payer shifts themselves are explainable (the payer keys are NAS 7.1 OS(+MI) + CFC proxies, government-23; E_NFPU keeps +3,12,829 too much and E_NFPR pays out 1,13,892 too much, closure `institution_gaps`), but a published cash line should not move beyond the cash-accrual tolerance. Proposal (not done here: code): a +-5% band per R7x line, and `anchored` single-payer lines (`interest_psu`, `interest_states`, `interest_other_parties`), so that only the payer split moves. In the explanations file the two single-payer entries over the threshold say "level unexplained"; the payer-split entries and the four payer cells are explained, with the line drift cited | FIXED 2026-10-01 (Wave C: a band per line and per payer sector) |
| government-33 | **major (finding; Checkpoint B; NAD question)** | **R9d nearly doubles in balancing.** 70,489.96 -> 1,31,327.12 (+86.3%: `railways` 59,801.66 -> 1,11,414.17, `posts` 10,688.30 -> 19,912.95); every free, low E_NFPU -> household entry moved by z 1.86-1.88 (fincorp's R8a in the same cells alike); GRAS gives 95,534.60 (+35.5%). No source supports the level: AFS Railway Funds disbursements 59,801.66 (A-R9d-1) and MH 3201.07 Posts pensions 11,674.49 less NPS 986.20. Old-base NAS 2024 St 2.1A (public NFC departmental enterprises, 2022-23) has D6+D7 uses of 1,48,177.21, but that is 95.6% of their balance of primary incomes (1,54,997.52; saving 6,820.30), the pattern of a surplus passed on to GG; it does not split D62 from D7 and bounds R9d without supporting it | Cause: E_NFPU keeps +3,12,829.18 over NAS 1.9 public NFC saving (closure `institution_gaps`; fincorp: its taxes and D6/D7 payouts are 1.18 lakh in the SAM against 3.71 lakh by the old-base St 2.1 structure), and R9d is the only low-confidence flow from E_NFPU to households. The 16 R9d entry items and 10 H_g <- E_NFPU cell items say "level unexplained". Also noted: the SAM has no departmental-enterprise -> GG transfer of surplus, which St 2.1A suggests the old base records (up to 1.48 lakh); if the new base does too, part of E_NFPU's surplus is GG income, which would enlarge the GG excess (government-27). Proposal: anchor R9d (say +-10%) or raise its confidence, and ask NAD how the 2022-23 base records departmental enterprises' pensions and surplus | BOUNDED 2026-10-01 (Wave C, audit BS-6); the NAD question stays (Checkpoint B; fincorp-37) |
| government-34 | major (finding; Checkpoint B) | **R2 `css_outside_treasury` cut 40% in balancing.** 1,48,479.11 -> 88,917.86 (z 0.599); with R2k 19,608.20 -> 17,349.05 the outside-treasury CSS money is 1,06,266.91 against the St 18 III - MH 3601.06 derivation 1,68,087.31 and IGAS-2 'Others' grantees 1,73,699.15 (-38.8%; the build check `css_outside_vs_igas2_others`, 5%, reads the prior, not the balanced SAM). GRAS: 1,33,046.88 (-20.8%) | Cause: under D2-8 the money is a States' receipt, but no block writes the outside-treasury agencies' spending (government-6, -27), so balancing cut the receipt instead: the balanced value is the transfer net of those agencies' unwritten outlays, not the transfer. The R2 / R2k entries and the G_STA <- G_CEN cell are explained on that basis ("compensating"). Proposal: write the agencies' outlays (GFCE and transfers inside G_STA) from the IGAS-2 'Others' grantee data, or book the money in the treasury view with the institutional view as a sensitivity | BOUNDED 2026-10-01 (Wave C, audit BS-7); the agencies' outlays: OPEN (Checkpoint B) |
| government-35 | **major (finding; Checkpoint B)** | **After the Wave C constraints the GG saving split carries the States' prior excess.** K3a Centre -3,40,382 -> -4,28,507, States +21,998 -> +1,10,123 (88,125 moved; the audited run moved 48,409), the GG total held at NAS 1.9 by `gov.k3.gg_saving`. | The published transfer totals (NAS 4.2 COFOG current transfers, R9d, R18, the outside-treasury CSS money, the Union's R10 lines, R7x lines) are now held, so the prior's G_CEN -2,97,655 / G_STA +4,49,133 split leaves mainly through K3a (and C2a, at the -10% edge of `gov.c2a.centre_own_output`). The direction is independently supported by FSF: capital_financial `k9_decomposition` nas_vs_fsf is +1,42,584 for the Centre and -1,97,779 for the States, i.e. FSF net lending puts the Centre's saving lower and the States' higher; the balanced split covers 62% and 45% of those terms. The level is not evidenced (the treasury bridge, government-2, gives the prior). Explained in `pipeline/sam/explanations/government.yaml` (verdict Explained). | OPEN (finding; Checkpoint B) |
| government-36 | minor | **The Union's R10 lines end at the lower edges of their new bands** (Wave C): PM-KISAN 51,616.91 -> 49,036.06 (-5%), LPG DBT 9,960.00 -> 9,462.00 (-5%), FC16 Union social security 18,603.44 -> 16,743.10 (-10%); R9a Centre at the -2% edge of `gov.r9.centre` (2,20,154.54). | G_CEN's prior shortfall (-2,97,655) pulls every Centre payment down to its band edge; the bands are the published totals' cash-vs-accrual tolerances (social security 10% because it may include NSAP money, government-11). The time series flow F27 is re-registered for the move (timeseries explanations). | NOTE |

## Control totals vs sources

Checks (`government_checks.parquet`; targets read from clean data):

| check | SAM | target | diff | tol | result |
|---|---:|---:|---:|---:|---|
| r1_vs_afs (AFS States' share) | 11,29,493.71 | 11,29,493.71 | 0.00 | 0.05 | ok |
| r1_vs_rbi_sf (0.05%) | 11,29,493.71 | 11,29,761.46 | -267.75 | 564.88 | ok |
| r1_vs_kfi (28 States, 0.05%) | 11,29,493.71 | 11,29,396.72 | +96.99 | 564.70 | ok |
| grants_state_receipts | 5,27,931.05 | 5,27,931.05 | 0.00 | 0.5 | ok |
| h9_union_net_releases (0.1%) | 5,28,103.46 | 5,27,931.05 | +172.42 | 527.93 | ok |
| h9_igas2_plus_fc_local (0.1%) | 4,71,798.77 | 4,71,618.62 | +180.15 | 471.62 | ok |
| css_outside_vs_igas2_others (5%) | 1,68,087.31 | 1,73,699.15 | -5,611.84 | 8,684.96 | ok |
| r6_vs_rbi_timing | 87,416.2162 | 87,416.22 | -0.0038 | 0.01 | ok |
| r6_r7_vs_fa_0050 | 1,70,890.51 | 1,70,890.51 | 0.00 | 0.01 | ok |
| r6_r7_vs_receipt_budget | 1,70,890.51 | 1,70,876.97 | +13.54 | 20 | ok |
| r9_states_vs_kfi (1%) | 4,90,983.18 | 4,94,938.72 | -3,955.54 | 4,949.39 | ok |
| c2a_total_vs_nas | 31,21,027.14 | 31,21,027.37 | -0.24 | 1 | ok |
| k6_row_gg_net | -6,999.68 | -6,999.68 | 0.00 | 0.01 | ok |
| k6_vs_cofog (5%) | 1,77,146.17 | 1,76,709.98 | +436.19 | 8,835.50 | ok |
| k3a_vs_nas_saving | -3,18,384.38 | -3,18,384.38 | 0.00 | 0.5 | ok |
| cofog_current_transfers (5%) | 9,91,488.49 | 10,05,630.22 | -14,141.73 | 50,281.51 | passes since Wave C (PM-KISAN in R10; was 9,39,871.58, -6.5%, government-9, -30); also a constraint now (+-5%) |
| gg_gdi_sketch (5%), R9b none since D2-20 | 28,05,404.35 | 28,02,642.99 | +2,761.36 | 1,40,132.15 | ok (close-out build; +54,378.27 before Wave C moved PM-KISAN to R10; failed at +2,40,923.69 with Centre-only R9b) |

Constraints declared: **38** since Wave C (4 equal, 34 band; the 26 Wave C constraints are listed under "Wave C audit" and in `government_constraints.parquet`, among them `gov.cofog.current_transfers`, NAS 4.2 +-5%). The original 12: `gov.c2.total` (NAS 1.14 GFCE +-1), `gov.c2a.centre_own_output` (band +-10%),
`gov.r1.devolution`, `gov.grants.state_receipts` (RBI SF grants +-0.5%, components filter: treasury parts only,
XR-20), `gov.t2b.cess_uses`, `gov.r7.union`, `gov.r7x.g_cen` / `gov.r7x.g_sta` (+-5%), `gov.r9.centre` (+-2%) /
`gov.r9.states` (+-3%) on refs [R9a] (XR-11), `gov.k3.gg_saving` (NAS 1.9, +-0.5), `gov.cofog.capital_transfers`
(+-5%). Production's `gfce.*` targets are not re-declared (XR-15). `gov.cofog.current_transfers` was not declared
before Wave C (government-9); it is now.

## Assumptions (each also a provenance record)

- A-C2a-1: all SUT GFCE grain (C_CROP) is the Centre's free PDS grain (FCI is inside G_CEN).
- A-C2a-2: non-CE costs of own output are proportional to CE across levels (the F4b key applies to GFCE).
- A-R2-1: the outside-treasury CSS agencies are the IGAS-2 'Others' grantees; their capital share (0.1167) splits
  the outside-treasury CSS into current (R2) and capital (R2k).
- A-R7-1: MH 0050.101 public undertakings and .200 other investments -> E_NFPU (entry `derived`, fixed; V-GOV-6).
- A-R7-2: States' dividends and profits (RBI SF App. I ii.c.2) -> E_NFPU (entry `derived`, fixed).
- A-R7x-2: Union interest from 'other parties' and co-operatives -> E_NFPR.
- A-R7x-3: telecom licence fee and universal access levy are rent (D45); WPC receipts excluded.
- A-R7x-4: States' interest receipts, less the interest on the Centre's 14-day treasury bills (Union MH 2049.01.116, intra-GG, V-GOV-1), -> E_NFPU.
- Payer keys for resource rents: NAS 2026 St 7.1A/7.1B/7.1C mining (royalties) and communication (telecom)
  OS(+MI) + CFC; petroleum rents paid by corporations only.
- A-R9-1: the PFRDA State-sector employer NPS contribution is inside the States' pension head.
- A-R9d-1: AFS Railway Funds disbursements are Railway pensions.
- R9b parameters: NPS start 2005-06 (k = 18 in 2023-24), career 39 years (S&M 2026 s.3.1.1 via DESIGN_REVIEW
  row 54); defence unadjusted. Used for the memo only since D2-20 (R9b = 0 written).
- A-R18-1: co-operatives are private corporations (E_NFPR).
- A-K6-1: RoW capital transfers to non-GG residents (NAS 6.1, 1,555.69) all to K_HH.
- A-K6-2: NPNFA acquired from the RoW (1,666.26) paid by K_NFPR.
- A-K6-3: COFOG 01 capital transfers include the BoP grants to the RoW (8,557), so K6 domestic 01 = 3,218.98.
- A-K6-4: statutory bodies and development authorities (IGAS-2 grantee class) are GG autonomous institutions (NAS 4.1): Union grants to them, revenue and capital, are intra-G_CEN and not written (V-GOV-7).
- C2a seed rule (a correction, not an assumption): public works (Centre MH 2059, States App. II ii.d.iv) are seeded in CNST only, not also inside the PADM aggregates (V-GOV-2).
- K3a (repaired 2026-10-01): gross saving = revenue balance on a NAS-coverage basis (no CFC step); Railways and
  Posts (departmental enterprises, public NFCs in NAS) leave the Centre's balance with their own fund lines; the
  urban local bodies' revenue surplus (cityfinance: total revenues - revenue expenditure - IGAS-2 capital grants to
  ULBs) is the States' (D2-8); grants routed through State treasuries are intra-G_STA, so the ULB grants for the
  Centre's initiatives stay in (their capital part left at the State boundary as R2k; the sensitivity without them
  is in `gov_fiscal_bridge`). The unexplained remainder is allocated by the NAS 4.1 NVA of the GG units outside the
  treasury accounts, as F4b splits them. Pair margins: each government's share of the remainder, the States' plus
  the ULB grants for the Centre's initiatives.

## Repair of 2026-10-01 (second pass)

Asked for by the orchestrator after the first full balancing attempt failed (BALANCING.md; DECISIONS D2-19..D2-23).
What changed in the block, and why:

1. **R9b = 0 (DECISIONS D2-20).** `R9B_VARIANTS_ALLOWED` now includes "none"; the D2-5 evidence picks it (gap
   +54,378 vs +2,40,924 Centre only and +4,81,611 Centre + States), so no R9b entry is written. The two non-zero
   variants are memo rows of `gov_r9b_sensitivity` (government-1).
2. **K3a bridge algebra (government-25, V-GOV-3).** No CFC is added to the cash balances: gross saving = GDI -
   GFCE and CFC cancels.
3. **NAS coverage of the bridge (government-2).** Railways and Posts revenue accounts leave the Centre (public NFC
   departmental enterprises in NAS 1.9 and 8.16): +19,808.60 to the Centre. The urban local bodies' revenue surplus
   (FC16 cityfinance dump 2023-24) is the States': +1,18,336.79. Both are clean-data items the treasury balances
   miss.
4. **Remainder rule.** The remainder (now +29,578.74, was -2,07,786.88) is allocated by the NAS 4.1 NVA of the GG
   units outside the treasury accounts (F4b split: Centre 13.83%), instead of by revenue expenditure: the
   remainder is the saving of those units. Read from factors' `gg_centre_state_key` (deps.py).
5. **Centre/State split of flows.** Investigated (below and government-27); nothing in government's own flows can
   be moved on clean-data evidence without another block: the identified causes are C2a's F4b key (factors), R4
   (fincorp), PM-KISAN (taxes, government-30) and the outside-treasury CSS agencies' spending (no data). They stay
   findings with their sizes.

Closure's `institution_gaps` and Z, assembled prior (`sam government fincorp capital_financial closure
--no-balance`), before (01:34 build) and after (this pass):

| account / measure | before | after | change |
|---|---:|---:|---:|
| GG imbalance (G_CEN + G_STA) | +3,87,151.78 | +2,00,606.36 | -1,86,545.42 (R9b) |
| GG gap vs NAS required net flows | +3,87,151.65 | +2,00,606.24 | -1,86,545.42 |
| G_CEN imbalance | -96,938.08 | -2,98,136.03 | -2,01,197.95 = -R9b 1,86,545.42 - prior change 14,652.53 |
| G_STA imbalance | +4,84,089.85 | +4,98,742.38 | +14,652.53 (prior +36,650.45 -> +21,997.92) |
| K3a priors G_CEN / G_STA | -3,55,034.83 / +36,650.45 | -3,40,382.30 / +21,997.92 | +14,652.53 / -14,652.53 |
| households' gap (delivered - required) | -11,44,072.91 | -9,57,527.49 | +1,86,545.42 |
| **Z** (sum of K4a vs NAS 1.9) | **-11,44,073.44** | **-9,57,528.03** | +1,86,545.42 |

The bridge repair moves only the split (the GG total is pinned by `gov.k3.gg_saving`), and by 14,652.53, towards
the treasury view and away from the SAM flows and the FSF: an honest result of better algebra, not a fit.

## Prior account imbalances (assembled prior, 2026-10-01, second pass)

*Historical (second pass). On the close-out prior (2026-10-01, after Wave C and the V-GOV-11 fix): G_CEN -2,98,947.95, G_STA +4,50,425.77, GG **+1,51,477.82** (re-verifier: SAM GG GDI 29,54,120.57 vs NAS 28,02,642.99, +1,51,477.58); E_NFPU +3,12,829.18, K_HH -3,84,546.82 (Z). The +2,00,606 figures below are the second pass's.*

Assembled from the built blocks' entries (closure's `prior_imbalance` / `institution_gaps`, imbalance = row total -
column total). Largest: K_HH -9,57,528.03 (= Z); E_NFPR +6,45,250.16; **G_STA +4,98,742.38**; **G_CEN
-2,98,136.03**; E_NFPU +2,43,838.89; E_NBFC +1,74,533.95; E_BANK -1,72,130.87; E_INSP -1,60,216.14; E_RBI
+25,645.50. The ten H_* accounts close (closure's K4a residual); K_GCEN / K_GSTA close through capital_financial's
K9 pairs (K9 K_GCEN +4,378.63, K_GSTA -2,15,746.72 after this pass). Every constraint government declares holds on
the prior (12/12).

**GG total, +2,00,606.36.** GFCE (C2a) equals NAS 1.14 GFCE (to Rs 0.24) and K3a equals NAS 1.9 saving, so the GG
imbalance is SAM GG GDI (30,03,249) - NAS 1.14 GG GDI (28,02,642.99). All of it is distributive flows:

| component | Rs crore | owner |
|---|---:|---|
| D2-5 evidence gap without R9b, with the cash interest proxy | +54,378.27 | government (R6, R7, R7x, R9a, R10, R18) + taxes (income taxes) |
| GG interest paid to non-GG units below the proxy (government-19) | +34,936.68 | fincorp / rest_of_world |
| GG interest on bank deposits, fincorp R4 (G_CEN 26,956.05, G_STA 83,375.64; government-26) | +1,10,331.69 | fincorp |
| RoW property income to G_CEN, rest_of_world R13 | +959.61 | rest_of_world |
| rounding | +0.11 | |

Evidence on the GG total from NAS 4.2 (non-interest current expenditure: consumption excl. CFC + subsidies + current
transfers = 46,69,538.88): the SAM has 46,03,778.74, only 65,760 below, all in current transfers (government-9;
PM-KISAN, government-30, would close 51,617 of it). So the +2.01 lakh GG excess sits on the income side (R4 and
interest paid), not in government's outlays.

**Centre vs States.** Each government's SAM saving-equivalent (receipts - payments other than K3a; CFC cancels)
against its K3a prior and against the repaired cash bridge:

| | Centre | States |
|---|---:|---:|
| SAM receipts - payments (excl. K3a), R9b none | -6,38,518.32 | +5,20,740.30 |
| cash bridge subtotal (`gov_fiscal_bridge`) | -3,44,473.14 | -3,489.98 |
| SAM - bridge | **-2,94,045.18** | **+5,24,230.28** |
| remainder share (prior - bridge) | +4,090.84 | +25,487.90 |
| imbalance = SAM - prior | -2,98,136.03 | +4,98,742.38 |

Traced (gross of devolution and of subsidies, CFC excluded, departmental enterprises excluded on the cash side):
- Centre receipts: SAM 37,90,013.66 (taxes 34,84,646.27, property income 3,04,955.63 incl. fincorp's R3 from the
  States 44,658.27 and R4 26,956.05, production taxes 411.76) vs cash 39,50,253.58 (AFS revenue receipts
  30,88,174.64 + devolution 11,29,493.71 - Railways/Posts 2,67,414.77): **-1,60,239.92**. Identified: WPC spectrum
  excluded (government-3) -54,296; Union interest lines excluded from R7x (government-5) -57,257; intra-GG interest
  from the States above the cash line (+31,017) and R4 (+26,956); the rest (-1.07 lakh) is fees and sales, which NAS
  nets inside GFCE, and tax-classification differences (taxes block).
- Centre payments: SAM 44,28,531.99 (GFCE excl. CFC 9,27,171.48, devolution + grants 17,60,050.14, interest
  10,87,704.16, R9a + R10 + R18 2,78,555.91, subsidies 3,75,050.30) vs bridge-adjusted cash 42,94,726.71: **+1,33,805.28**.
  Identified: C2a own-output GFCE excl. CFC 7,63,199.73 vs the Centre's cash functional seed 6,49,136.44 (+1,14,063;
  factors' F4b CE key, assumption A-C2a-2); interest -14,164 vs MH 2049; pensions -13,681 vs MH 2071 (NPS and CGHS
  are CE); the rest +47.6k.
- States: SAM receipts 40,38,355 vs RBI SF revenue receipts 39,30,240 (+1,08,115: CSS outside treasuries +1,48,479
  under D2-8, T2b(ii) +78,104 and R2k -1,23,958 as in the bridge, R4 +83,376, taxes incl. production taxes +56,722,
  other property income 1,87,371 vs own non-tax revenue 3,21,711, -1,34,340, mostly fees and sales that NAS nets
  inside GFCE); SAM payments 35,17,614 vs RBI SF revenue expenditure 40,23,677 (-5,06,063: grants to
  local bodies -1,19,510, intra-G_STA; the NPS employer contribution -43,992, CE inside GFCE; interest -12,562; and
  **about -3.3 lakh on all other current outlays**). The bridge adds the ULB surplus (+1.18 lakh), so relative to
  the institutional bridge the States in the SAM (i) receive 1.48 lakh of outside-treasury CSS money whose agencies'
  spending no block writes, (ii) receive R4 83k that ULB data do not support, (iii) spend about 3.3 lakh less than
  their treasuries on other current outlays (candidate causes: C2a's CE key for the States' own output, the States'
  current transfers no block writes, government-12, and PM-KISAN in taxes' D39 residual, government-30).

What balancing will do: the GG excess must leave GG income (R4, R7x, taxes' income taxes) or become GG outlay
(R10, R9a keys), because GFCE and saving are pinned; the split moves through the K3a pairs (free, low; margins
4,091 / 79,597), the C2a band (+-87,427) and fincorp's free interest entries. The explanations must cite this table
and government-27.

## Integration status (2026-10-01)

- All four dependencies are built and read: production, households (`hh_keys` pop_persons), factors (F4b, F2
  `nonfarm`, `factor_income_keys` public_sector_wage_key), taxes (G_* <- T_PIT/T_CIT: 10,44,763.68 + 9,11,055.01
  to G_CEN, 7,873.82 to G_STA).
- **2026-10-01 00:15, rebuilt with the verification fixes** (`uv run python -m pipeline sam government`, after
  taxes' 23:48 rebuild, V-GOV-9): 158 entries, 12 constraints, 6 satellites, 17 checks (2 fail, both logged:
  government-1, government-9), 53 provenance records, no stale warning for government. What moved: R7x
  `interest_states` -1,976.32 (V-GOV-1); the C2a Centre/State split within each commodity (Centre PADM +2,219.98,
  EDUC -1,364.00, HLTH -498.19, CNST -357.79, States the mirror; column and row totals unchanged, V-GOV-2); K6
  1,594.81 from the Centre (`igas2_psu_statutory` -> `igas2_psu`) to the States' K_NFPU residual (V-GOV-7); R7
  statuses (V-GOV-6); the classification satellite (V-GOV-8). Every constraint target is unchanged except
  `gov.r7x.g_sta` (1,59,965.63).
- **Dependents to rebuild:** fincorp (reads R6/R7; its records cite government's R7 records, whose ids changed with
  the status fix) and capital_financial (reads K8e, K3a, K6, R2k; its records cite the K6 records, and its K9
  residual pairs must absorb the K6 shift) are stale: `uv run python -m pipeline sam fincorp capital_financial`
  (then closure, which reads both). Until then `tests/sam/test_sam_audit.py::test_every_sam_provenance_input_resolves`,
  `test_sam_fincorp.py::test_built_outputs_equal_a_fresh_build`, `test_sam_capital_financial.py::
  test_built_outputs_equal_a_fresh_build` and `::test_built_k_accounts_close_and_markets_clear` fail; no value
  fincorp reads from government changed (R6, R7 values are identical). In-memory builds of both (`write=False`,
  nothing written) succeed against the new government outputs: fincorp's 455 entries are unchanged;
  capital_financial's only moves are its K9 residual pairs, I_OTHR <- K_GCEN `residual_pos` +1,594.81 and
  I_OTHR <- K_GSTA `residual_neg` -1,594.81. Government did not rebuild them (other blocks' outputs).
- **2026-10-01, second pass** (`uv run python -m pipeline sam government fincorp capital_financial closure
  --no-balance`): government 148 entries (158 - the 10 R9b entries), 12 constraints, 6 satellites, 17 checks (1
  fails, logged: government-9 / -30), 53 provenance records; warnings: the G_STA K3a sign (+21,998, within 50,000
  of zero) and `cofog_current_transfers`. fincorp, capital_financial and closure rebuilt on it (fincorp's own
  `k2a.rbi_prior_vs_nas` failure predates this pass). What moved: R9b (removed), the K3a pairs and
  `gov_fiscal_bridge` / `gov_r9b_sensitivity`; capital_financial's K9 pairs for K_GCEN / K_GSTA; closure's K4a
  (every group +R9b share) and Z.
- Tests after the second pass: `tests/sam/test_sam_government.py` 28 passed (new: `test_r9b_is_none_on_the_real_evidence`,
  `test_k3a_bridge_has_no_cfc_step_and_adds_the_ulb_surplus`; `test_r9b_formula_and_variant` checks the memo and
  the written variant; `test_checks_that_must_pass` no longer excuses `gg_gdi_sketch`); the verifier's
  `tests/verify/test_sam_government_spotcheck.py` 22 passed (updated only where D2-20 and the K3a repair change
  the pinned behaviour: R9b census, K3a recomputation, D2-5 ranking around what is written, entry count 148; the
  V-GOV-3 strict xfail is an ordinary test). `uv run python -m pipeline test -k government`: 75 passed, 9 errors
  (`test_sam_identities.py` tax-receipt tests: no balanced SAM exists). `tests/sam`: 446 passed, 12 failed, 42
  errors, none in government's files: `test_sam_audit.py` (6) and `test_sam_identities.py` (42 errors) need a
  successful balancing run; `test_sam_balance.py::test_the_interior_point_fallback_reaches_the_same_certified_optimum`
  (6) fails in `pipeline/sam/balance.py`, which another agent was editing (D2-23) during this pass. The dependents'
  spot-checks pass except the known fincorp census pin (118 vs 121 entries of at least 10,000, fincorp's verifier).
- Remaining integration items, checked on 2026-09-30: capital_financial nets K8e out of the FSF Centre -> States
  loans (government-14, CLOSED); closure's household whitelist has R9a, R9d (resources) and R7x, R9b (uses)
  (closure-5); capital_financial's I1a key follows the institutional view as far as data allow (government-24,
  CLOSED); government-1 and government-19 updated with fincorp's entries.
- Explanations: written 2026-10-01 for the balanced run in `pipeline/sam/explanations/government.yaml`
  (DECISIONS D2-22); see "Balancing explanations" below.
- Warnings in the run (second pass), all logged above: K3a G_STA sign (government-2) and the failed check
  `cofog_current_transfers` (government-9, -30). The R9b variant warning is gone (D2-20).

## Balancing explanations (balanced run of 2026-10-01)

Run: `uv run python -m pipeline sam` (NEWTON, direct path, status optimal, KKT certificate passed, no slack).
`pipeline/sam/explanations/government.yaml` holds **86 items**: the 58 government entries with
`explanation_required` (all free) and the 28 multi-entry cells whose largest absolute mover is a government entry
(22 of them shared with fincorp). `uv run python -m pipeline sam-report` picks up all 86 (no stale item, no
government entry or cell left unexplained). Each `why` starts with a verdict:

| Verdict | Items | What they are |
|---|---:|---|
| Explained | 38 | C2a Centre -> States shift (7 entries: 69,162 of GFCE, Centre own output 8,74,272 -> 8,05,110, inside the +-10% band; the F4b CE key puts the Centre's own output above its cash functional seeds, government-7, -27); K3a pairs (3 entries, 2 cells: 48,409 of saving from the Centre to the States, toward the FSF evidence, government-2, -27); R18 PSU grants -44% (possible overlap with P10a, government-28) and its E_NFPU <- G_CEN cell; R2 / R2k `css_outside_treasury` and the G_STA <- G_CEN cell ("compensating", government-34); 17 R7x payer-split entries and the 4 payer cells (weak payer keys, government-23; line drift government-32) |
| Explained in direction; level unexplained | 48 | R10 `cash_schemes` (10 entries + 10 H_g <- G_STA cells; government-31), R9d (16 entries + 10 H_g <- E_NFPU cells; government-33), R7x `interest_psu` and `interest_states` (single published payer lines; government-32). The account-level gaps that drove them are documented (closure `institution_gaps`: G_STA +5,00,750, G_CEN -2,97,655, E_NFPU +3,12,829, E_NFPR -1,13,892, Z -4,36,164), but no source supports the balanced level of these entries and their own sources contradict it |
| Unexplained in direction | 0 | |

Mechanism behind most moves: cross-entropy moves all free entries of one cell with the same constraint membership
by one factor z (set by the account and constraint multipliers), so the low-confidence entries (weight 0.25) of the
accounts with the largest prior gaps move most (R10 z 1.73-1.75, R9d z 1.86-1.88, R2 `css_outside_treasury` z
0.599). GRAS on the same prior spreads the same gaps differently (R10 States +5.1%, R9d +35.5%, R2 + R2k
`css_outside_treasury` -20.8%), which confirms that these levels come from the weights, not from evidence.

## Wave C audit (docs/phase2/verify/balanced_sam.md, 2026-10-01)

The independent audit of the balanced SAM gave government four major and one minor finding. Each was reproduced
on the 03:00 run, fixed in this block (with taxes for PM-KISAN), and the full `sam` was re-run (NEWTON, interior-
point fallback then Newton, KKT certificate passed, no slack; 429 constraints). Figures below are from that run.

| Finding | Reproduced (03:00 run) | Disposition (Wave C run) | Status |
|---|---|---|---|
| BS-5 GG current transfers +10% over NAS 4.2 | yes: R9a + R10 + R18 = 11,06,002 vs NAS 4.2 COFOG current transfers 10,05,630 (+9.98%); R10 `cash_schemes` +73.6% | PM-KISAN (FA 2401.00.130, 51,616.91) moved from taxes' P10a to R10 `pm_kisan` G_CEN -> H_* by factors' F2 farm mixed income (assumption A-R10-2; government-30, taxes-28), so the prior is 9,91,488 (-1.4%). Declared `gov.cofog.current_transfers` (R9a + R10 + R18, +-5%) and one band per Union R10 line (`gov.r10.pm_kisan` +-5%, `lpg_dbt` +-5%, `social_security` +-10%). Balanced: 10,55,912 (+5.0%, upper edge); States' `cash_schemes` 2,14,325 -> 2,77,356 (+29.4%, every group z 1.28-1.30). The audit's strict xfail `test_gg_current_transfers_within_5pct_of_nas_4_2` passes and its xfail marker is removed. The level of `cash_schemes` (+29% over the FC16 figure) stays a Checkpoint B finding (government-31) | FIXED (bounded); level OPEN (Checkpoint B) |
| BS-6 R9d nearly doubles | yes: railways 59,801.66 -> 1,11,414 | Declared `gov.r9d.railways` and `gov.r9d.posts` (+-10% of the AFS Railway Funds disbursements and MH 3201.07 less NPS). Balanced: railways 65,781.83, posts 11,757.13 (both +10%, upper edge). The audit's strict xfail `test_r9d_railway_pensions_within_10pct_of_the_afs` passes; marker removed. E_NFPU's prior surplus (+3,12,829) now lands on fincorp's flows: fincorp-37 (the departmental-enterprise surplus is a NAD question, government-33) | FIXED; E_NFPU OPEN (Checkpoint B) |
| BS-7 R2 `css_outside_treasury` cut 40% | yes: R2 88,918 + R2k 17,349 = 1,06,267 (-38.8% against IGAS-2 'Others') | Declared `gov.r2.css_outside_treasury` (R2 + R2k `css_outside_treasury`, +-10% of St 18 III - MH 3601.06 = 1,68,087.31). Balanced: 1,51,278.58 (-10%, lower edge): R2 1,19,919, R2k 31,360 (capital share 0.207, inside the 0.117-0.272 range of assumption A-R2-1). **Not done:** writing the outside-treasury agencies' outlays inside G_STA from the IGAS-2 grantee data. IGAS-2 gives what the grantees receive, not how they spend it (GFCE, transfers or GFCF); any split would be a typed assumption, and the GFCE total is fixed, so it would be a Centre -> State GFCE shift that C2a already makes within its band. The treasury view would contradict D2-8. Both are owner decisions | FIXED (bounded); agencies' outlays OPEN (Checkpoint B) |
| BS-11 R18 `psu_revenue_grants` cut 44% | yes: 24,017 -> 13,389 | Declared `gov.r18.psu_revenue_grants` and `gov.r18.coop_revenue_grants` (+-10% of the IGAS-2 grants less their capital part). Balanced: 21,615.70 and 1,073.31 (both -10%, lower edge; 1,073.29 was a transcription slip, V-GOV-15). The possible overlap with taxes' FC16 Union 'business' subsidies (government-28) is still not measurable from clean data | FIXED (bounded); overlap OPEN (Checkpoint B) |
| BS-12 F4b vs C2a (shared with factors) | yes | factors declares `f4b.centre` (+-5%, factors-23); C2a keeps its +-10% band on cash evidence and ends at the -10% edge of `gov.c2a.centre_own_output`. The remaining difference between the two splits is accepted and documented (factors-23) | FIXED / accepted |
| government-32 (not an audit finding, same cause) | R7x lines drifted up to +41% (`interest_psu`) | One band per published R7x line (+-5%, `gov.r7x.<gov>.<line>`) and, for multi-sector lines, one per payer sector (+-25%, `gov.r7x.<gov>.<line>.<sector>`). A trial run without the payer bands moved telecom licence fees from public NFCs 3.1-fold | FIXED |

Consequences and new findings: government-35 (the saving split now carries the States' excess, toward FSF),
government-36 (the Union's R10 lines at their lower edges). The balancing explanations were regenerated for this
run: `pipeline/sam/explanations/government.yaml`, 57 items (39 Explained, 18 "Explained in direction; level
unexplained": the ten R10 `cash_schemes` entries and their eight multi-entry H_g <- G_STA cells; none
"Unexplained"). The section "Balancing explanations (balanced run of 2026-10-01)" above describes the superseded
03:00 run. Tests changed with the design (the verifier's census and constraint tests in
`tests/verify/test_sam_government_spotcheck.py` now recompute the pm_kisan entries and the nine new constraint
families from clean data; they were edited by the fixing agent and need re-verification by a different agent).

For DECISIONS.md (the orchestrator records decisions; blocks may not): (1) PM-KISAN is a current transfer to
households (R10), not a D39 production subsidy, because NAS 4.2 books it in COFOG 04.agri current transfers
(government-30, taxes-28); (2) a published total whose split over accounts is a key is declared as a band on its
own (R9d, R18, the outside-treasury CSS money, the Union's R10 lines, each R7x line, NAS 4.2 COFOG current
transfers), so balancing can move the key but not the published level beyond its cash-vs-accrual tolerance.

## Verification dispositions

Verifier report `docs/phase2/verify/government.md` (2026-09-30, build of 23:37; verdict: every number right, fixes
needed). Each finding was reproduced from clean data before its disposition (2026-10-01).

| finding | severity | reproduced | disposition | what changed |
|---|---|---|---|---|
| V-GOV-1: States' 14-day ITB interest counted twice (R7x `interest_states` and fincorp R3 `itb_14d`) | minor | yes: fincorp `itb_14d` = Union MH 2049.01.116 = 1,976.32 exactly; RBI SF App. I ii.c.1 = 28,493.58 is the States' MH 0049 total, which includes interest on cash-balance investment | **Fixed** (government's side, as the verifier recommends: government reads MH 2049.01.116 from clean data; fincorp keeps the intra-GG entry) | `interest_states` = ii.c.1 - MH 2049.01.116 = 26,517.26; `gov.r7x.g_sta` target 1,59,965.63; `gov_r7x_items` lists the ITB interest as excluded (G_STA); the D2-5 interest-paid proxy also drops MH 2049.01.116 (intra-GG), so the proxy gaps do not move; G_STA prior imbalance -1,976.32, E_NFPU +1,976.32. Test `test_itb_interest_is_intra_gg_not_r7x`; the verifier's strict xfail is now an ordinary test (government-4, -5, -19, -26) |
| V-GOV-2: C2a seeds count public works twice | minor | yes: FA section administrative_services = MH 2051-2070 incl. 2059 (sum exact); App. II ii.d = items i-v incl. ii.d.iv (sum exact) | **Fixed**: public works stay in the CNST seed (the plan's intent) and leave the PADM seeds | Centre PADM seed -2,580.15, States PADM seed -13,849.22; RAS result: Centre PADM +2,219.98, EDUC -1,364.00, HLTH -498.19, CNST -357.79 (States the mirror); every row and column total unchanged, so no constraint moves. Test `test_c2a_seeds_count_each_cash_line_once`; the verifier's strict xfail is now an ordinary test (government-7) |
| V-GOV-3 (= government-25): K3a bridge adds CFC to cash revenue balances | major | yes: without the CFC step remainder +1,67,892.28, priors -2,82,310.97 / -36,073.41 | **Fixed 2026-10-01 (second pass), on the orchestrator's instruction**: the CFC step is dropped and, with it, the remainder rule and the bridge's NAS coverage are repaired (government-2, -25): departmental enterprises out of the Centre, ULB revenue surplus in the States, remainder by the NVA of the units outside the treasuries | `_k3a`; the verifier's strict xfail is an ordinary test; its recomputation follows the repaired bridge |
| V-GOV-4 (= government-1): R9b Centre-only although the evidence favours none | major | yes: gaps +1,91,203 (none), +3,77,748 (Centre only), +6,18,435 (both) on the 2026-10-01 prior | **Fixed 2026-10-01 (second pass) by DECISIONS D2-20**, which amends D2-5: "none" is written; the non-zero variants are a memo | `R9B_VARIANTS_ALLOWED`, `_r9b`; the verifier's census and D2-5 ranking test follow D2-20 |
| V-GOV-5 (= government-27): prior imbalances G_CEN / G_STA | major | yes: -1,05,047.10 / +4,84,771.78 on the 2026-09-30 prior; now -1,05,047.10 / +4,82,795.46 | **No change; Checkpoint B**, plus `explanations.yaml` entries after the full balancing run | numbers updated in government-27 and "Prior account imbalances" |
| V-GOV-6: R7 payer split labelled official/fixed although it rests on an assumption | minor | yes: MH 0050.101 'public undertakings' mixes non-financial and financial PSUs; the Receipt Budget groups do not separate them | **Fixed (label)**; `anchored` **rejected**: `public_undertakings` and, by the same rule, the States' `state_enterprises` are now `derived` (A-R7-1, A-R7-2); they stay `fixed` because `gov.r7.union` (equal, +-0.5) pins the Union total with banks and LIC fixed, so a tolerance would give balancing no freedom, and no alternative payer entry can be seeded from clean data | two records' status; test `test_r7_payer_split_on_mixed_heads_is_derived` (government-15). fincorp cites these records: it must be rebuilt (values unchanged) |
| V-GOV-7: statutory bodies classified two ways | minor | yes: capital grants 1,594.81 were K6 to K_NFPU while revenue grants 10,761.31 were left out as possibly GG | **Fixed: one class, GG** (assumption A-K6-4: statutory bodies and development authorities are autonomous institutions inside GG in NAS 4.1, as factors' F4b treats central autonomous bodies; not writing the revenue grants already implied it) | K6 Centre K_NFPU = PSU capital only (component `igas2_psu`, 16,434.16); States' K_NFPU residual 62,055.77 (+1,594.81); both parts listed as intra-G_CEN in `gov_transfer_classification`; assertions in `test_k6_row_on_the_nas_basis_and_cofog_total`; the verifier's census expectation for these two entries updated (government-12, -13). capital_financial must be rebuilt |
| V-GOV-8: `gov_transfer_classification` lists the LIC pension subsidy twice | minor | yes: `r18.lic_pension_subsidy` and the St 7 line | **Fixed**: one row per source line (the St 7 line, destination R18, account E_INSP) | satellite row removed; assertion in `test_satellites_present` |
| V-GOV-9: build stale against taxes | minor | yes: taxes rebuilt 23:48 after government 23:37 | **Fixed**: rebuilt 2026-10-01 00:15 (no stale warning for government); the values read from taxes are unchanged | outputs |
| V-GOV-10: overlap risks not quantifiable from clean data | minor | (a) logged as government-11; (b) confirmed as a risk: IGAS-2 PSU revenue grants 24,017.45 vs FC16 Union 'business' subsidies 52,325.27 in taxes' P10a | **Logged**: (b) as government-28, raised with taxes and for Checkpoint B; no data to measure it | issues file only |

Notes the verifier raised without a finding: the debt-management fee in the D2-5 proxy (noted in government-19, not
changed); K6 RoW entries `fixed` where the plan said anchored 0.01 (kept: they net exactly to NAS 6.1, XR-14);
fincorp's `gsec_state_reserve_funds` vs R7x (no overlap found; fincorp to confirm); `gov_c2a_keys` labels its
official seeds `estimated` (one status per satellite record; cosmetic, not changed).

## Framework requests

None. The framework expresses everything this block needs (components filter, band constraints, paired
entries for the saving sign).

## Close-out re-verification (2026-10-01)

Re-verifier's report: `docs/phase2/verify/government.md`, "Re-verification (wave C close-out, 2026-10-01)", verdict
**needs_fixes** (26 changed entries, 44 bridge rows, 27 R9b memo rows, 38 constraint targets and 57 records
recomputed; all match except the findings below). The solver/audit re-verification (`docs/phase2/verify/balanced_sam.md`)
raised one major finding owned by government and fincorp, also disposed of here. Each finding was reproduced before
it was disposed of. Rebuilt and rebalanced with the full `uv run python -m pipeline sam` of the close-out.

| Finding | Severity | Reproduced | Disposition | What was done |
|---|---|---|---|---|
| V-GOV-12: PM-KISAN moved from production subsidy to household transfer, reversing D0-5, with no DECISIONS entry | major | Yes: DECISIONS had D2-1..D2-23 only; D0-5 says "farm income support as a production subsidy by default" | **Fixed** | **DECISIONS D2-24** (amends D0-5): PM-KISAN is a current transfer to households (R10); D0-5's default stays for any other scheme; NAD question and Checkpoint B flag kept. The R10 record now cites D2-24 and says the NAS treatment is inferred (NAS 4.2 does not itemise PM-KISAN; see V-TX-8). The strict xfail `test_v_gov_12_*` is an ordinary test and passes. |
| V-GOV-13: most balanced government flows end exactly on a band edge, so their levels are the chosen tolerances | major | Yes: 28 of 38 government constraints bind; every Wave C band ends on an edge (COFOG +5%, R9d +10%, CSS -10%, R18 -10%, Union R10 -5/-5/-10%, R7x line and payer bands) | **OPEN (Checkpoint B)**; owner decision | Not a coding defect: each band is declared and logged (government-31..36) and BALANCING.md lists every binding constraint with its edge ("Acceptance: declared totals after balancing"). For the owner at Checkpoint B: (a) justify each width from evidence or publish a width sensitivity (half and double the widths); (b) label values on a band edge as such in the UI; (c) read the binding pattern as a measure of the unresolved prior imbalance (G_STA +4,50,426, G_CEN -2,98,948, E_NFPU +3,12,829 on the close-out prior), not as estimates. |
| Solver/audit (major, owner government / fincorp): Wave C bands bound the audited flows only at their edges; E_NFPU's surplus moved to the next weak entries (z range 0.155-6.46, objective +56%) | major | Yes: the close-out run (direct dual Newton, 83 steps, certified) has the same pattern; E_NFPU <- E_NFPR R8 z 0.156, E_BANK <- E_NFPU R5 loans +59.5% | **OPEN (Checkpoint B)** | Same root cause as V-GOV-13 and fincorp-37: the E_NFPU and G_CEN/G_STA prior gaps. Adding bands would only move the surplus again. For Checkpoint B: the NAD question on departmental-enterprise surplus (fincorp-37 option 1) and the E_NFPU GOS re-check (option 2). Recorded also in fincorp's close-out section. |
| V-GOV-11: the K3a bridge leaves Railways head MH 3006 in the Centre | minor | Yes: FA St 9 MH 3006 = 00.102 1,500.00 + 00.797 1,759.68 = 3,259.68 = MH 1001-1003 receipts less MH 3001-3003 (3,259.69) | **Fixed** | `is_de` in `parts.py::_k3a` now matches MH 3001-3003, 3006 and 3201, so MH 3006 is a departmental-enterprise head and its 797 line leaves the fund-transfer sum; method text says so. Built: Centre -3,42,973.14, remainder 28,078.74, priors -3,39,089.75 / +20,705.37 (exactly the re-verifier's expected values); GG total unchanged. The K3a explanation items were updated to the new prior and balanced values (Centre -3,39,090 -> -4,27,343, States 20,705 -> 1,08,959; 88,253 moved), and the prior gaps quoted in every explanation file to G_CEN -2,98,948 / G_STA 4,50,426. Spot-check: `test_v_gov_11_*` is an ordinary test, and the recomputation's departmental heads include MH 3006 (`parts()`, `de`); the block test `test_k3a_bridge_has_no_cfc_step_and_adds_the_ulb_surplus` too. |
| V-GOV-14: the PM-KISAN key weights by farm income, but the scheme pays a flat amount per family | minor | Yes: H_R4 32.1%, H_R5 19.6% of R10 pm_kisan by F2 farm mixed income | **Documented; OPEN (Checkpoint B)** | The R10 record now says the income-weighted key overweights the groups with large farms against a count of beneficiary families (assumption A-R10-2 stays, low). A count-based sensitivity (households' `pop_households` for the rural groups) is a Checkpoint B option; not built here because no beneficiary count by group exists in clean data and the choice moves income between groups (an owner decision with factors-19 / -24). |
| V-GOV-15: stale figures after Wave C | minor | Yes | **Fixed** | Refreshed: government-1 (current gaps +2,761 / +1,89,307 / +4,29,994; the second-pass figures kept and labelled), the `gg_gdi_sketch` row (28,05,404.35, +2,761.36), the constraints paragraph (38 declared, `gov.cofog.current_transfers` declared since Wave C), government-27 and "Prior account imbalances" (close-out GG +1,51,478, the +2,00,606 figures labelled as the second pass's), and the Wave C R18 co-op figure (1,073.31). |
