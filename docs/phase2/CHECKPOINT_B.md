# Checkpoint B: the balanced SAM for 2023-24

For: Jitesh (owner). Drafted 2026-10-01 for SPEC §6 Phase 2: "show me the SAM, the balancing report and the biggest surprises in the data. Wait for approval."

Conventions: amounts in **Rs lakh crore** (1 lakh crore = 1,00,000 crore) at current prices, FY 2023-24, and as **% of GDP** (NAS 2026 GDP 2,90,73,287 crore = 290.73 lakh crore). Small items are in Rs crore. Every figure was re-read for this note from `data/sam/2023-24/` (the final certified run), `BALANCING.md`, `data/timeseries/`, the block issues files `docs/phase2/issues/*.md` and `DECISIONS.md`. Nothing is quoted from memory.

**What I need from you:** approval of the SAM as a working base for Phase 3, and a yes, no or "ask NAD first" on each item in section 6. The SAM is balanced and passes every SPEC test. But some of its large flows are set by tolerances I chose rather than by data, and section 6 lists those.

---

## 1. What was built, and the acceptance tests

**What was built.** The SAM is a 128-account social accounting matrix of India for FY 2023-24 on the new 2022-23 GDP base (NAS 2026 vintage). It has 34 activities × 34 commodities, a margins account, 4 factors, 10 household groups (rural and urban MPCE quintiles), 6 corporate accounts, the Centre and the States, 12 tax accounts, the rest of the world (RoW), 11 capital accounts, inventories, 11 financial instruments and a pinned discrepancy account. Nine blocks wrote 3,893 entries from the Phase 1 data. Each entry carries a source record and a status: official, derived or estimated. There are 429 constraints (337 select entries; 92 are empty target-0 placeholders): mostly published totals, plus some floors, caps and judgement bands, each with a tolerance. The prior (the unbalanced SAM) was then balanced by cross-entropy, i.e. the smallest weighted relative change that makes every account's receipts equal its payments while keeping every constraint. An optimality certificate proves the answer is that minimum.

Outputs:
- `data/sam/2023-24/sam_balanced.parquet`: 2,203 cells (2,169 non-zero).
- `sam_balanced_matrix.csv`: the 128 × 128 matrix.
- `sam_entries_balanced.parquet`: every entry with its prior, balanced value and change.
- `balancing_log.parquet`.
- `BALANCING.md`: the generated balancing report.

There is also a 69-flow annual time series from 1950-51 to 2025-26 in `data/timeseries/`.

**Run result** (`balancing_run.json`):
- Status: **BALANCED**. Dual Newton method, 83 iterations, certificate passed.
- Largest account residual: 2.32e-07 crore. Relative duality gap: 3.15e-13.
- No slack: no constraint or anchored box had to be widened.
- Fixed and pinned entries are untouched: 195 entries, including the whole discrepancy account X_DISC.

| SPEC Phase 2 acceptance test | Result | Measured (balanced minus source) |
|---|---|---|
| Every account's row total = column total (tolerance Rs 0.01 crore) | **pass** | Largest gap 0.000000 crore across all 128 accounts |
| GDP by production, income and expenditure vs NAS 1.1 (2,90,73,286.73 crore), only the official discrepancy allowed | **pass** | +0.61 crore on all three. The NAS 2023-24 discrepancy is 0, and the SAM's is 0. |
| GVA at basic prices; product taxes less subsidies | pass | +2.13 crore; -1.52 crore |
| PFCE, GFCE, change in stocks, exports, imports, GFCF + valuables | pass | -1.00, +1.00, -0.04, +0.74, +0.79, +1.04 crore |
| **Government**: GG saving (NAS 1.9), GG GFCE and GDI (NAS 1.14) | pass | +0.50, +1.00, +1.50 crore (each on its band edge) |
| Union taxes vs Finance Accounts / Receipt Budget (cash): corporation tax, income tax, Union excise, compensation cess, customs | pass | -0.00%, +0.01%, **+5.00%**, **+5.00%**, -1.82% (declared bands 0.5%, 0.5%, 5%, 5%, 1%; customs is −0.39% of its band's target, which is cash less export duty, booked as another product tax under D2-12) |
| State taxes vs RBI State Finances: SGST, VAT, State excise, income taxes | pass | -1.40%, -0.62%, -0.46%, -1.00% (bands 5%, 15%, 15%, 1%) |
| Union gross tax, five heads; tax devolution vs Finance Accounts | pass | +1.88% (band 5%); devolution exact (11,29,493.71 crore) |
| **BoP**: RoW current receipts and payments vs NAS 6.1; current-account balance; foreign assets and liabilities | pass | +0.74 and +0.74 crore; -2,08,890.71 crore exact; 6,70,569.37 and 8,86,570.33 crore exact |
| **Flow of funds**: all 11 instrument markets clear; household financial assets, liabilities and net saving vs NAS 5.3 | pass | Largest instrument gap 1e-06 crore; 36,02,198.51 / 19,09,286.70 / 16,92,911.81 crore, all exact |
| Sector saving vs NAS 1.9: households, public NFC, private NFC, FC, national | pass | -0.50, 0, 0, +1.00, +1.00 crore |
| Household GDI vs NAS 1.14; GNDI vs NAS 1.1 | pass | -1.61 crore (the sum of its parts' bands, 2.5); +0.89 crore |
| **No cell moved past the threshold without a logged explanation** (threshold: Rs 5,000 crore, or Rs 500 crore and 10% of the prior) | **pass, with a finding** | 223 entries and 103 cells needed one. All have one: 0 missing, 0 stale. Their verdicts: 224 explained, 90 "explained in direction, level unexplained", and **12 "Unexplained"**, all on public NFCs (section 5.6). |

The independent audit, written by an agent that built nothing, recomputes all of these from Parquet without the pipeline code: `tests/verify/test_sam_balanced_audit.py`, which the suite runs on the final run. Its report, `docs/phase2/verify/balanced_sam.md`, covers the 03:00 run and the re-verified 05:41 run; the close-out changes after it did not change any acceptance figure. The figures in this note were checked separately by another agent (`docs/phase2/verify/checkpoint_b.md`: 883 figures, 22 corrections applied).

**Tests and repro.**
- Offline test suite, on the final close-out run: 4,221 passed, 0 failed, 25 xfailed. The xfails are the 23 Phase 1 cross-source gaps and two Phase 2 findings kept visible on purpose: the 12 "Unexplained" items and premiums = claims by payer.
- `pipeline repro`: 338 files byte-identical across two hash seeds and 1 vs 4 threads, and identical to the manifest. `manifest --check` is up to date.
- I re-ran the offline suite and `manifest --check` for this note, with the same result (run record at the end).

---

## 2. The SAM at a glance

Aggregated from `sam_balanced.parquet`, in Rs lakh crore. Rows **receive** and columns **pay**; each account's row total equals its column total. A "." means zero or under Rs 500 crore.

| Receives ↓ / pays → | Activities | Commodities | Factors | HH rural | HH urban | NFCs | FCs | Centre | States | Taxes | RoW | Capital | Fin. instr. | Discrepancy | **Total** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Activities | . | 575.64 | . | . | . | . | . | . | . | . | . | . | . | . | **575.64** |
| Commodities (incl. margins) | 311.59 | 79.20 | . | 84.90 | 79.26 | . | . | 9.51 | 21.70 | . | 64.79 | 100.04 | . | . | **750.99** |
| Factors | 264.63 | . | . | . | . | . | . | . | . | . | 0.62 | . | . | . | **265.25** |
| HH rural | . | . | 103.36 | . | . | 2.82 | 7.91 | 2.41 | 3.75 | . | 4.66 | . | . | . | **124.92** |
| HH urban | . | . | 89.10 | . | . | 4.96 | 13.98 | 3.34 | 4.27 | . | 5.17 | . | . | . | **120.81** |
| NFCs | . | . | 57.86 | . | . | 2.56 | 4.42 | 0.50 | 0.13 | . | 1.36 | . | . | . | **66.84** |
| FCs | . | . | 10.87 | 3.13 | 4.37 | 10.77 | 4.29 | 7.44 | 3.77 | . | 1.44 | . | . | . | **46.07** |
| Centre | . | . | 1.17 | . | . | 1.26 | 1.34 | . | 0.45 | 32.59 | 0.01 | . | . | . | **36.81** |
| States | . | . | 2.59 | 0.12 | 0.16 | 1.40 | 0.29 | 17.45 | . | 13.15 | . | . | . | . | **35.16** |
| Taxes | -0.57 | 26.68 | . | 2.13 | 6.05 | 9.65 | 1.80 | . | . | . | . | . | . | . | **45.74** |
| RoW | . | 69.47 | 0.31 | . | 1.00 | 4.68 | 2.13 | 0.44 | . | . | . | . | . | 2.12 | **80.15** |
| Capital | . | . | . | 31.74 | 27.16 | 28.73 | 9.91 | -4.27 | 1.09 | . | 2.09 | 7.28 | 135.39 | 3.59 | **242.71** |
| Financial instruments | . | . | . | . | . | . | . | . | . | . | . | 135.39 | . | . | **135.39** |
| Discrepancy (X_DISC) | . | . | . | 2.90 | 2.81 | . | . | . | . | . | . | . | . | . | **5.71** |
| **Total** | **575.64** | **750.99** | **265.25** | **124.92** | **120.81** | **66.84** | **46.07** | **36.81** | **35.16** | **45.74** | **80.15** | **242.71** | **135.39** | **5.71** | **2,532.21** |

How to read a few cells:
- **Centre → Capital = -4.27.** This is the Union's gross saving, which is negative. The States save +1.09, so GG saving is -3.18 lakh (-1.10% of GDP), equal to NAS 1.9.
- **Centre → States = 17.45.** Tax devolution (11.29), grants (4.76), GST compensation (1.23) and interest (0.16).
- **Taxes ← Activities = -0.57.** Other production taxes less production subsidies.
- **Discrepancy row.** NAS's published household residual (5.71 lakh, 1.96% of GDP) is carried visibly (D0-6). It is not balanced away.

**Where the numbers come from.** These are shares of the SAM's absolute value, summed over all 3,893 entries (2,678.11 lakh crore).

| Basis of the value | Share |
|---|---:|
| Official (a published cell or total used as is) | 47.1% |
| Derived (arithmetic on official figures) | 8.4% |
| Estimated (a key, a structure or a model applied to an official total) | 44.5% |
| **Moved by balancing** (sum of absolute changes 28.38 lakh crore, 9.76% of GDP) | **1.06%** of SAM value |
| Entries moved by 10% or more and by at least Rs 1 crore (304 entries) | 2.0% of SAM value |

The moves sit almost entirely on estimated, freely adjustable entries:
- Estimated entries carry 28.22 of the 28.38 lakh: low-confidence ones 19.78 lakh and medium-confidence ones 8.26 lakh.
- Anchored entries (official or derived) moved 12,239 crore in total, each inside its small box.
- No fixed entry moved.

---

## 3. The household picture

Balanced SAM, Rs lakh crore. Receipts are the group's gross receipts. Its outlays are consumption, taxes, interest and premiums paid, transfers, its share of the published household residual (D1), and saving. The saving rate is shown on the IFPRI basis, saving / (consumption + saving), before and after balancing, and also as saving / gross receipts.

| Group | Persons (crore) | Gross receipts | of which labour | mixed income | GOS (mainly imputed rent) | from corporations (interest, dividends, insurance and PF benefits) | from government | from abroad | Consumption (PFCE) | Income tax | Saving | Saving / (cons. + saving), prior → balanced | Saving / receipts | Receipts per person (Rs) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Rural Q1 (poorest) | 17.09 | 11.78 | 4.26 | 5.41 | 0.40 | 0.75 | 0.71 | 0.25 | 7.77 | 0.00 | 3.54 | 29.9% → 31.3% | 30.1% | 68,928 |
| Rural Q2 | 17.09 | 16.36 | 5.40 | 7.83 | 0.68 | 1.17 | 0.86 | 0.42 | 11.17 | 0.00 | 4.45 | 27.2% → 28.5% | 27.2% | 95,690 |
| Rural Q3 | 17.09 | 21.51 | 6.17 | 10.59 | 1.07 | 2.01 | 1.06 | 0.62 | 14.41 | 0.00 | 6.00 | 28.0% → 29.4% | 27.9% | 1,25,850 |
| Rural Q4 | 17.09 | 33.36 | 8.55 | 17.67 | 1.71 | 2.99 | 1.38 | 1.06 | 18.92 | 0.00 | 12.67 | 38.6% → 40.1% | 38.0% | 1,95,137 |
| Rural Q5 (richest) | 17.09 | 41.91 | 15.88 | 14.72 | 3.03 | 3.82 | 2.15 | 2.31 | 32.62 | 2.12 | 5.07 | 12.7% → 13.5% | 12.1% | 2,45,175 |
| Urban Q1 (poorest) | 7.26 | 8.46 | 3.95 | 1.63 | 1.22 | 0.80 | 0.57 | 0.28 | 6.26 | 0.00 | 1.85 | 21.7% → 22.8% | 21.9% | 1,16,617 |
| Urban Q2 | 7.26 | 13.22 | 5.85 | 2.54 | 1.77 | 1.66 | 0.83 | 0.58 | 9.55 | 0.09 | 2.93 | 22.2% → 23.5% | 22.1% | 1,82,171 |
| Urban Q3 | 7.26 | 18.72 | 7.61 | 3.59 | 2.32 | 3.20 | 1.16 | 0.84 | 12.94 | 0.69 | 3.89 | 21.9% → 23.1% | 20.8% | 2,57,970 |
| Urban Q4 | 7.26 | 27.08 | 10.71 | 5.16 | 3.08 | 5.26 | 1.65 | 1.22 | 17.68 | 1.47 | 5.62 | 22.8% → 24.1% | 20.8% | 3,73,109 |
| Urban Q5 (richest) | 7.26 | 53.32 | 26.35 | 8.58 | 4.73 | 8.02 | 3.39 | 2.25 | 32.82 | 3.80 | 12.87 | 26.8% → 28.2% | 24.1% | 7,34,651 |
| **Rural** | 85.47 | 124.92 | 40.27 | 56.21 | 6.88 | 10.74 | 6.17 | 4.66 | 84.90 | 2.13 | 31.74 | 25.9% → 27.2% | 25.4% | 1,46,156 |
| **Urban** | 36.29 | 120.81 | 54.48 | 21.51 | 13.12 | 18.94 | 7.60 | 5.17 | 79.26 | 6.05 | 27.16 | 24.2% → 25.5% | 22.5% | 3,32,902 |
| **All households** | 121.76 | 245.74 | 94.75 | 77.72 | 20.00 | 29.67 | 13.77 | 9.83 | 164.16 | 8.18 | 58.90 | 25.1% → 26.4% | 24.0% | 2,01,814 |

**What it shows:**
- The urban top fifth (6% of persons) receives 21.7% of household gross receipts and does 21.9% of household saving.
- Rural Q4 also does 21.5% of saving.
- Rural Q5's saving rate (13.5%) is the lowest of the ten, below rural Q1's 31.3%. That is the clearest implausibility in the household block (section 5.10).
- For comparison, IFPRI's 2022-23 SAM gives rural 21.3% and urban 24.0%. The SAM has rural 27.2% and urban 25.5%. At IFPRI's rates on the SAM's consumption, households would save 48.0 lakh against NAS's 58.9 lakh, so IFPRI's levels cannot be imposed. Only an ordering could (factors-24).

**Caveats on the keys.** The totals are official. The split across groups is estimated, and you should read it that way.
1. **Consumption.** HCES 2023-24 captures only 44.3% of NAS PFCE: 72.74 lakh at HCES scale against 164.16. Each product's PFCE is spread with HCES shares, which assumes the missing 56% is spread like the captured part. The literature says it is concentrated at the top, so the top groups' consumption is probably understated and their saving overstated. A top-heavy variant needs your rule (households-1).
2. **Factor income** (192.46 lakh, 70-86% of each group's gross receipts) uses IFPRI 2022-23 old-base national-quintile gradients, applied with k = q (D2-19). There is no microdata (D1-2), so within-area gradients are a modelling choice (factors-19, factors-13).
3. **Imputed rent** (15.96 lakh) is keyed by HCES item 539, which puts 73% in urban groups. An AIDIS building-value key would move 2.11 lakh from urban to rural groups (households-2).
4. **Property income** (interest and dividends) is keyed by AIDIS 2019 asset shares. AIDIS's top class holds less than class 4 (households-4).
5. **Income tax by group (T3a)** has no open source at all; CBDT is blocked (taxes-8, ISSUES P1-4).
6. **Transfers.** State cash schemes are keyed by population. PM-KISAN is keyed by farm income, which overweights large farms, because the scheme pays a flat amount per family (V-GOV-14).
7. **Saving by group** is the residual of each group's account. No source measures it. Balancing raised all ten groups' saving by 6.2% to 7.8% to reach NAS's total (closure-19).
8. **Population.** HCES has 121.76 crore persons against about 139.5 crore implied by NAS. The per-person figures use HCES persons (households-15).

---

## 4. The balancing report in brief

**How much the prior was off.** Before balancing, nine accounts were out by more than Rs 10 crore. Everything else was SUT rounding of under Rs 1.5 crore.

| Account | Prior gap (receipts - payments) | % of GDP |
|---|---:|---:|
| States (G_STA) | +4.50 | 1.55% |
| Household capital account (K_HH = Z, the household saving gap) | -3.85 | -1.32% |
| Public NFCs (E_NFPU) | +3.13 | 1.08% |
| Centre (G_CEN) | -2.99 | -1.03% |
| NBFCs (E_NBFC) | +2.33 | 0.80% |
| Insurers and pension funds (E_INSP) | -1.22 | -0.42% |
| Private NFCs (E_NFPR) | -1.14 | -0.39% |
| Banks (E_BANK) | -1.03 | -0.35% |
| RBI (E_RBI) | +0.26 | 0.09% |

Every institution's primary income matches NAS to rounding. So these gaps sit in **distributive flows**, i.e. who pays interest, dividends, taxes and transfers to whom. Old-base structures and keys had to fill these because the new base publishes no institutional sequence of accounts (ISSUES P0-1).

**How far balancing moved things.**
- The sum of absolute changes is 28.38 lakh crore (9.76% of GDP, 1.06% of SAM value).
- 2,229 entries moved by Rs 1 crore or more.
- 174 of the 337 non-empty constraints end on a band edge.

| Block | Gross move (lakh) | Share of the block's prior that moved |
|---|---:|---:|
| fincorp (interest, dividends and FC saving) | 10.03 | 10.6% |
| government | 5.42 | 7.4% |
| closure (household saving K4a) | 3.85 | 6.3% |
| taxes | 3.61 | 3.2% |
| capital_financial | 3.49 | 0.7% |
| rest_of_world | 0.95 | 2.0% |
| factors | 0.79 | 0.2% |
| households | 0.25 | 0.1% |
| production (the SUT) | 152 crore | 0.0001% |

**The largest moves, and why** (from the explanation files):

| Move | Prior → balanced | Why |
|---|---|---|
| Household saving (K4a, 10 groups) | 55.06 → 58.90 (+3.85) | Closes Z. The NAS total binds, and each group rose by 6.2% to 7.8%. The total is evidenced; the split is not (closure-19). |
| Households' property income (R8a) | +2.15 (1.97 from FCs and NFCs, 0.17 from government) | The main outlet for Z, moving toward the old-base household D4 share (closure-3). |
| Centre/State saving split (K3a) | Centre -3.39 → -4.27, States +0.21 → +1.09 (0.88 moved) | The States' prior excess leaves through the saving split. FSF net lending points the same way. Verdict: Explained (government-35). |
| GFCE, Centre to States (C2a; 0.71 of it public administration) | 0.87 moved | The Centre's own output ends at the -10% edge of its cash-based band (government-7, factors-23). |
| Public NFCs' receipts of private NFCs' distributed income (R8) | 1.17 → 0.18 (-84%) | E_NFPU's surplus. About 0.51 lakh of the cut is supported by the old-base structure; the level is not (fincorp-32, -37). |
| Public NFCs' interest to banks and NBFCs (R5) | 2.02 → 3.12 (+54%) | E_NFPU's surplus again. The implied loan rate is far above RBI's return on advances. Verdict: **Unexplained** (fincorp-37). |
| Bank / NBFC saving (K2a) | Banks 4.59 → 4.12; NBFCs 3.38 → 4.05 | The FSF supports the move; RBI's bank-level reports (RTP) oppose it (fincorp-34). |
| GG interest received on bank deposits (R4) | 1.05 → 0.47 | A low-confidence FSF-stock × rate estimate. It may also double count government's own R7x (fincorp-25). |
| State cash transfers to households (R10) | 2.14 → 2.77 (+29%) | GG current transfers end at +5% of NAS 4.2 COFOG (10.56 vs 10.06 lakh, band edge). |

**What is explained only in direction.** The 90 items whose level no source supports are:
- fincorp: 32 items. Interest, distributed income and bank/NBFC saving: about 2.5 lakh of moves.
- rest_of_world: 23 items. RoW property income re-split among domestic payers (rest_of_world-27).
- government: 18 items. State cash transfers (R10) and their cells.
- taxes: 17 items. Union vs State tax receipts and subsidies, and E_NFPU's corporation tax.

The 12 **Unexplained** items (1.45 lakh of moves) are all E_NFPU flows:
- its interest to banks and NBFCs;
- its receipts of bank deposit interest and Union G-sec interest.

The verdict counts per file are in `pipeline/sam/explanations/*.yaml`, and every item is in `BALANCING.md`.

**Cross-check.** GRAS is a plain balancing method with no weights or constraints. For the large moves it often goes the same way but by less: about half the K4a rise, and +0.24 instead of +2.15 lakh on households' R8a. Sometimes it goes further where the cross-entropy run is held by a band (R9d +35% against +10%), and sometimes it takes a different route; for taxes it moves product subsidies instead of GST. 229 entries differ from cross-entropy by more than the threshold. GRAS cannot hold the published totals, so it is a direction check, not an alternative answer.

---

## 5. The biggest surprises in the data (ranked by size)

### 5.1 The household distributive gap Z: Rs 11.44 lakh crore at first (3.94% of GDP), 3.85 lakh after repair (1.32%)

The first full assembly showed households' accounts delivering 11.44 lakh crore less saving than NAS 1.9 says they save. Each household account was balanced on its own, and saving was its residual. Other institutions held the mirror image, keeping too much income. Repairs, each with evidence and a DECISIONS entry:

| Step | Z after it (lakh) |
|---|---:|
| First assembly | -11.44 |
| R9b (imputed OPS contributions) set to none; the evidence test favours it (D2-20) | -9.58 |
| Old-base distributed-income structure for private NFCs (D2-21, 8.21 lakh; fincorp-27) and the other fincorp repairs | -4.36 |
| PM-KISAN moved from production subsidy to household transfer (D2-24) | **-3.85** |

Balancing closed the last 3.85 lakh mostly through property income (+2.15), lower interest paid (+0.85) and State cash transfers (+0.63; R10 net +0.58). The lesson is that with no new-base institutional accounts, **who receives property income is the weakest link in the SAM**. Old-base structures carry it.

### 5.2 Old base vs new base: the structures do not carry over cleanly

New-base / old-base ratios for 2022-23 and 2023-24 (timeseries-5):

| Series | 2022-23 | 2023-24 |
|---|---:|---:|
| PFCE | 0.904 | 0.905 |
| GFCE | 1.064 | 1.005 |
| Inventories | 0.58 | 0.83 |
| Private NFC saving | 0.77 | 0.84 |
| FC saving | 1.14 | 1.31 |
| Household saving | 1.05 | 1.08 |

These breaks are uneven. So the old-base sequence of accounts, the only source for distributive flows by sector (D2-21), is applied to new-base totals that it does not match. Two more checks show the same problem:
- New-base product taxes for 2022-23 are 3.81% below old-base GG taxes on products (Phase 1 TAX-8).
- Old-base GG D5 does not reconcile with cash D5 (taxes-25).

The time series therefore carries the break visibly. Only 10 flows are ratio-linked; the rest stay as two bases (section 8).

### 5.3 NAS vs RBI flow of funds: NFC net lending differs by Rs 5.73 lakh crore (1.97% of GDP)

Phase 1 found NAS and FSF disagreeing on 2023-24 net lending by sector: NFC -5.73 lakh, households +2.95, FC +2.29, GG +1.20 (ISSUES P1-2). In the SAM, NAS saving is the control. FSF is used only for who-holds-what-from-whom, and the difference lands in named residuals (K9, on "other accounts").

- K9 is large: banks -4.91 lakh in the prior (-5.22 balanced) and States -2.17 lakh (capital_financial-1). The sources include co-operative banks' unread "other" liabilities, lender vs borrower loan reports, and the HDFC merger.
- The SAM's NFC borrowing is 27.88 lakh against FSF's own NFC liabilities of 22.17 lakh: +25.7% (timeseries-25). The two are different concepts: the SAM uses holders' reports and the BoP. Anyone comparing them should know that.

### 5.4 Centre vs States: the States hold Rs 4.50 lakh crore too much and the Centre 2.99 lakh too little (1.55% / 1.03% of GDP)

GG as a whole was off by only +1.51 lakh. The split was off by much more. The Centre's treasury bridge (government-2) is robust: every allocation rule gives the Centre -2.8 to -3.6 lakh of saving. So the gap sits in the flows, and it was traced to four items:
- CSS money released outside State treasuries (1.68 lakh) with no agency spending written against it (government-34);
- the Centre's own-output GFCE set above its cash functional spending;
- interest on GG bank deposits;
- States' current outlays about 3.3 lakh below their treasury revenue expenditure (government-27).

Balancing raised the States' saving and lowered the Centre's by 0.88 lakh, and moved 0.87 lakh of GFCE from the Centre to the States. It also moved 0.46 lakh of product-tax receipts the other way, from the States to the Centre. The tax move has no tax evidence behind it: Union CGST, cess and excise all end on their +5% cash ceilings (taxes-26, taxes-30). FSF independently puts the Centre's saving lower and the States' higher. The direction is right; the levels are set by bands.

### 5.5 The States' subsidies come out at 1.96 times RBI State Finances: 6.47 vs 3.30 lakh (2.22% vs 1.13% of GDP)

There are two sources of the problem:
- **The production-subsidy residual.** NAS 4.2 GG subsidies (9.19 lakh) less SUT product subsidies leaves 3.42 lakh of production subsidies, and the identity assumes NAS 4.2 "subsidy" = D31 + D39 (taxes-13). The PM-KISAN move (D2-24) left more of that residual with the States.
- **Unexplained SUT product subsidies.** About 1.05 lakh on trade and 0.62 lakh on pesticides have no payer in any budget (taxes-11, production-9).

In the balanced SAM, States' subsidies are 3.46 lakh product + 3.01 lakh production. RBI St 36 also omits six States, which explains some of the gap (taxes-24). This is a question for NAD on the NAS 4.2 subsidy concept.

### 5.6 Public NFCs keep Rs 3.13 lakh crore more than NAS says they save (1.08% of GDP)

Every evidenced outlet of public NFCs is now held by a published total, and each ends on its edge:
- railway and postal pensions (R9d, +10%);
- PSU grants (R18, -10%);
- E_NFPU's corporation tax (+25%);
- dividends and bond interest bands.

So the rest of the surplus lands on weak entries. Its interest to banks and NBFCs rises by 54%, and its interest receipts on bank deposits and Union G-secs are cut by 37% and 83%: these are the 12 "Unexplained" items. Its receipts of private NFCs' distributed income are cut by 84% ("level unexplained"). The likely cause is that the old base shows departmental enterprises (Railways, Posts) passing 95.6% of their primary income on as D6 + D7, the pattern of a surplus passed to GG, and the new-base SAM writes no such transfer (fincorp-37, government-33). One NAD question could close up to about 0.78 lakh of it and of the Centre's shortfall at once.

### 5.7 Financial corporations: NAS, FSF and RBI's bank data disagree on who saves (up to 2.33 lakh, 0.80% of GDP)

NAS fixes total FC saving (9.91 lakh) and the public/private split. The split by sub-sector is ours, and the prior left NBFCs +2.33, insurers -1.22 and banks -1.03 lakh out.

- **Banks and NBFCs.** Balancing set bank saving at 4.12 lakh and NBFC saving at 4.05 lakh (priors 4.59 and 3.38). The FSF supports that shift. RBI's bank-level business accounts (RTP) put banks near 4.6 and NBFCs near 1.5 lakh, so they oppose it. Two official sources point opposite ways (fincorp-34).
- **Insurers and pension funds.** Their SAM investment income was 1.38 lakh below IRDAI plus the PF schemes' accounts (fincorp-31). Balancing cut insurers' saving from 1.00 to 0.78 lakh instead.
- **RBI.** It ends at 0.97 lakh of saving, the upper edge of its band (0.94 ± 0.025 lakh: the NAS-derived 1.01 lakh less the 0.07 lakh SDR-charge debit the SAM books on the RBI). On the RBI Annual Report basis, which leaves that debit out, that is 1.04 lakh against NAS's 1.01 lakh.

### 5.8 Dwelling depreciation does not fit the household sector (2.03 lakh, 0.70% of GDP)

The SUT's dwelling depreciation exceeds NAS's household figure by at least 2.03 lakh, so part of "ownership of dwellings" must be corporate or government. A depreciation-consistent split would move 4.98 lakh of household surplus between imputed rent and mixed income (totals unchanged). This is a NAD question; the SAM is gross, so no cell changes (factors-1).

### 5.9 Product taxes: SUT vs budgets, 1.61 lakh in Phase 1, now 0.47 lakh

Phase 1 found SUT product taxes 1.61 lakh (5.2%) above Union + State receipts (TAX-1, import duty included). On the taxes block's basis, which leaves customs out of both sides, the gap is 1.58 lakh (5.5%). Booking State motor-vehicle tax (1.11 lakh) as a product tax (D2-4) cuts it to 0.47 lakh (1.60%). The SUT stays the control, and every tax row is scaled 1.016 × cash (taxes-1). State excise still exceeds the SUT's alcohol tax by 0.26 lakh, and non-petrol State VAT has almost nowhere to go (taxes-2, -3).

### 5.10 The rural saving profile is not monotone

Rural Q4 saves 40.1% and rural Q5 13.5%. The cause: households' PFCE, scaled item by item from HCES to NAS, rises more steeply across rural groups than any income gradient does (factors-19, factors-24). Balancing does not fix it, because it spreads Z almost proportionally. Options are in section 6.

### 5.11 Phase 1 cross-source gaps (ISSUES P1-2): how they landed

| Phase 1 gap | Phase 2 outcome |
|---|---|
| FSF vs NAS net lending (NFC -5.73, HH +2.95, FC +2.29, GG +1.20 lakh) | NAS is the control; the differences sit in named K9 residuals (5.3) |
| SUT product taxes vs receipts +1.61 lakh (Phase 1 basis; 1.58 on the taxes block's basis) | 0.47 lakh after D2-4 (5.9) |
| Grants to States: MH 3601 vs IGAS-2 (-1.41 lakh) and vs RBI SF (+0.67 lakh) | Institutional view (D2-8). The 1.68 lakh of CSS released outside treasuries is a States' receipt, banded ±10%; it ends at 1.51 lakh, the lower edge. Agencies' spending is not written (government-34). |
| Product subsidies, SUT vs budgets, +8.1% | The SUT is the control; the States' share is 1.96 × St 36 (5.5) |
| FPI: BoP vs SEBI +8.9% | BoP used; NSDL's terms bar reuse (rest_of_world-16) |
| Interest on Central loans, Union vs States -9.5% | Open (fincorp-10) |

---

## 6. Decisions taken autonomously that you should confirm

### 6a. DECISIONS entries flagged for Checkpoint B

| Decision | Size | Alternative | Effect of the alternative | My suggestion |
|---|---|---|---|---|
| **D2-20** (amends D2-5): imputed pension contributions of government employees (R9b) = none | Alternatives: 1.87 lakh (Centre only) or 4.27 lakh (Centre + States); 0.64% / 1.47% of GDP | Write R9b for the Centre, or for Centre + States | The GG income gap vs NAS rises from +0.03 lakh to +1.89 or +4.30 lakh. Z widens by 1.87 or 4.27 lakh. | Confirm none; ask NAD whether NAS 2026 GG GDI includes D612 |
| **D2-19**: factor-income gradients k = q (rural and urban quintile q uses IFPRI's national quintile q) | Splits 192.46 lakh of household factor income | (a) National-quintile crosswalk; (b) HCES-rescaled | (a) Urban Q5 saving falls to 2.2% of income on the current prior (it was negative, -2.13 lakh, on the first build); rural Q5 14.9%. (b) Rural Q5 saving turns negative (-5.8% of income). | Confirm k = q. Choose whether to impose a rural/urban saving ordering (factors-24, option b). |
| **D2-24** (amends D0-5): PM-KISAN is a household transfer, not a production subsidy | 0.52 lakh (0.18%); 0.49 lakh balanced | Keep D0-5's production subsidy | Z widens back to -4.36 lakh. The States' subsidy gap vs St 36 narrows by about 0.5 lakh. | Confirm (SNA treats a flat per-family payment as a transfer); ask NAD. Separately, choose a count-based key (V-GOV-14). |
| **D2-11**: 21.45% of personal income tax (MH 0021) is paid by quasi-corporations (firms), on the old-base household D5 share | 2.17 lakh prior, 2.34 balanced (0.81%) | IFPRI's household share (0.9017 instead of 0.7855), or all to households | About 1.18 lakh more income tax on households (0.1162 × MH 0021 of 10.11 lakh, derived here and checked independently), or 2.17 lakh; Z widens by the same | Confirm; ask NAD |
| **D2-13**: compensation cess used to repay the GST back-to-back loans is a current transfer | 0.78 lakh (0.27%) | Capital transfer (SNA 2008 §10.201) | Only the Centre/State saving split moves, by ±0.78 lakh (government-16) | Confirm for now; ask NAD |
| **D2-21**: old-base (2022-23) sequence-of-accounts structures as priors for distributive flows with no new-base source | Sets 8.21 lakh (2.82%) of private NFCs' distributed income, plus several interest and dividend splits | No prior (pure balancing) or another holder key | With the receipts paid to households only, Z would be about -1.90 lakh, FCs about -1.16 and E_NFPU about +2.18 lakh (fincorp-27, on the repair build when Z was −4.36 lakh; not recomputed after PM-KISAN) | Confirm; replace when MoSPI publishes new-base sector accounts |
| **D2-4** (NAD question): State motor-vehicle tax is a product tax | 1.11 lakh (0.38%) | Household current tax (D59) | The SUT-vs-receipts gap goes back to 1.58 lakh (5.5%, taxes block's basis); household taxes rise by 1.11 lakh | Confirm |
| **D2-8**: Centre/State boundary on the institutional (NAS) view | 1.68 lakh of CSS released outside treasuries | Treasury view | The money stays with the Centre; the States' prior excess falls by up to 1.68 lakh (government-34) | Confirm; write the agencies' outlays next pass |
| **D2-7** and rest_of_world-26: the Union's IMF income and SDR charges sit on the RBI | 6,929 + 7,118 crore (0.05% of GDP) | Move them to the Centre, as rest_of_world-26 proposes with FSF and yield evidence | The RBI's unexplained reserve income in the prior falls from 25,646 to 18,717 crore (balancing already removes most of it: 7,714 is left in the balanced SAM); the Centre changes by about -389 crore net | Approve the move (it amends D2-7) |

### 6b. Tolerances I chose that now set balanced levels

These are judgements, not data (V-GOV-13; the solver/audit finding). In each case the balanced value sits exactly on the band edge, so the band width, not a source, sets the level. Widening a band moves more of the prior gaps into that flow. Narrowing it pushes them to the next weak entry, or into slack (a visible failure).

| Band | Source total | Balanced (edge) |
|---|---|---|
| GG current transfers within ±5% of NAS 4.2 COFOG | 10.06 lakh | 10.56 lakh (+5%) |
| GG capital transfers ±5% | 1.77 lakh | 1.86 lakh (+5%) |
| Railway and postal pensions (R9d) ±10% of AFS (railways) and MH 3201.07 (posts) | 0.70 lakh | 0.78 lakh (+10%) |
| CSS outside treasuries ±10% | 1.68 lakh | 1.51 lakh (-10%) |
| PSU revenue grants (R18) ±10% | 0.24 lakh | 0.22 lakh (-10%) |
| Union CGST, cess and excise within +5% of cash | | All three on the ceiling (taxes-30) |
| The Centre's share of GG depreciation (`f4b.centre`) ±5% of the NVA key (V-F-10) | Key share 0.2957 | Share 0.3104; 1.17 lakh |
| Public NFCs' corporation tax ±25% of the old-base share (V-TX-6) | 0.75 lakh | 0.94 lakh (+25%) |

In the government block, 28 of 38 constraints bind. **Ask:** accept these widths for now, or ask me to publish a band-width sensitivity (the same run at half and double each width).

### 6c. Other OPEN (Checkpoint B) items that need your call

| Item | Size | The choice |
|---|---|---|
| E_NFPU surplus (fincorp-37) | 3.13 lakh | (1) Ask NAD about departmental enterprises' surplus and write it as a transfer to the Centre (up to about 0.78 lakh); (2) re-check E_NFPU's GOS; or (3) accept the moves, labelled |
| Bank vs NBFC saving (fincorp-34b) | 0.47 lakh moved from banks; 0.67 lakh to NBFCs | Follow FSF (as now) or band banks on RTP evidence |
| Household saving profile (factors-24, closure-19) | about 0.94-1.28 lakh would move from rural to urban groups under equal rates | Impose a rural/urban ordering, adopt a crosswalk variant for the rural top, or accept |
| PFCE top-heaviness (households-1) | 91.4 lakh of PFCE not captured by HCES | Pick a rule for a top-heavy variant, or keep distribution-neutral |
| FISIM on household loans (households-19) | 3.24 lakh loan leg | Keep (binding XR-5) or switch to a published variant (stock weights, or deposits only) |
| Holder key for private NFC distributed income (fincorp-27) | 8.21 lakh | Keep the FSF holder shares, or a household-heavier key |
| ULB capital spending in the GG investment key (capital_financial-30d) | about 0.40 lakh from Centre to States | Adopt at the next rebuild after checking overlap |
| GG saving bridge remainder (government-2) | 0.28 lakh unexplained | Accept as a remainder (by NVA key) |
| R18 PSU grants vs the FC16 "business" subsidies (government-28) | Overlap of at most 0.24 lakh | Accept or exclude |
| RoW property income re-split (rest_of_world-27) | 0.23 lakh more RoW income paid by NBFCs | Bound the FC share of FDI income paid to the FLA range |
| Premiums = claims by payer (V-FIN-9, FRAMEWORK_REQUESTS FR-C-3) | Up to about 10% apart by payer | Needs a framework feature; accept until then |
| Households' fund-held public NFC bond interest banded unevenly (V-FIN-10) | 6,235 crore inside a 30,714 crore band | Accept or split the band |
| Time series: whitelist F39, F42, M11 or M13 for ratio-linking (timeseries-5) | Display only | Keep them refused (my suggestion) |

---

## 7. Open issues, and what would reduce them

The OPEN items are consolidated in `ISSUES.md` under "Phase 2 (2026-10-01): headline issues", with pointers to the block files.

**Questions for MoSPI's National Accounts Division.** One letter would settle most of the judgement calls:
1. New-base institutional sequences of accounts. Even 2022-23 alone would replace the old-base structures (P0-1, D2-21). This is the single biggest lever on Z.
2. How the new base records departmental enterprises' surplus and pensions (fincorp-37, government-33).
3. Whether NAS GG GDI includes imputed pension contributions D612 (D2-20).
4. The NAS 4.2 "subsidies" concept (D31 + D39?), and the trade and pesticide product subsidies (taxes-13, -11; production-9).
5. Classification of PM-KISAN (D2-24), motor-vehicle tax (D2-4), STT (D2-12) and the cess-funded loan repayment (D2-13).
6. Dwelling depreciation by sector (factors-1), and whether imputed rent uses HCES item 539 (households-2).
7. Spectrum receipts and the RBI surplus on an accrual basis (government-3, -18).

**Data access that would reduce estimates:**

| Request | Unlocks |
|---|---|
| CBDT income-tax return distribution | T3a, income tax by household group (none today) |
| Unit-level HCES / PLFS / AIDIS (microdata registration, D1-2) | Within-area income gradients and keys |
| DPE public enterprises survey (keyed API) | Public NFC tax and dividends |
| RBI corporate finances (DBIE) | Private dividends (fincorp-11) |
| RBI credit by purpose | Household FISIM split (households-19) |
| GSTN settlement timing | Narrower GST bands (taxes-30) |
| NSDL FPI data | FPI debt split (rest_of_world-16) |
| IGAS-2 grantee spending | Outside-treasury CSS outlays (government-34) |
| RGI population projections | Population control (households-15) |
| MoSPI's new-base back series (expected Dec 2026) | Replaces the base-break handling in the time series |

Several of these need you: a registration or a permission request (ISSUES P1-4, P1-9).

---

## 8. What Phase 3 (the Map website) can rely on, and what it must label

**Reliable: official totals, held to within a rupee crore or two.**
- GDP and its three approaches, GVA, PFCE, GFCE, GFCF, exports and imports.
- The 34 × 34 production structure (the SUT; balancing moved it by 152 crore in all).
- Devolution, exactly. Taxes by type are close but not to the crore: they sit within cash-vs-accrual bands of up to ±5% of cash (Union CGST, compensation cess and excise at +5%; SGST −1.4%; customs −1.8%).
- Sector saving: households, public and private NFCs, FC, GG, national.
- The RoW current and financial accounts (NAS 6.1 / BoP).
- Household financial saving (NAS 5.3).
- The published discrepancies, shown as such.

**Label "estimated" (with the method one click away):**
- Every split by household group: income, consumption, taxes, transfers, saving.
- Interest, dividends and other property income between institutions. Label these "estimated, old-base structure" where D2-21 applies.
- The FC sub-sector split of saving and income.
- The Centre/State split of GFCE, saving and shared taxes.
- K9 residuals and FSF counterparties.

**Label "balancing-set" or show a range:**
- Flows whose balanced level sits on a band edge (section 6b).
- The 12 "Unexplained" E_NFPU flows.
- The 90 "level unexplained" items.

The site should show the prior, balanced value and change for these, which the entry files already carry.

**Time series** (69 flows: 54 core, 15 memo; 1950-51 to 2025-26; 2,504 rows):
- 633 rows are derived, i.e. computed from official series. For the 10 whitelisted flows (PFCE, GFCF, GDP, GVA, exports and imports, and household liabilities) this includes old-base values ratio-linked at 2022-23. Every other flow shows the base break explicitly.
- The SAM cross-check gives 57 pass, 11 explained, 1 with no check. The 11 explained include seven moved by balancing: Union GST (+5.0% of cash including UTGST, the band ceiling; +5.6% against the Receipt Budget total), SGST, Union excise (+5.0%), grants, Union interest, and Union and State pensions (timeseries-26, -29). They are "explained", not "confirmed".

**Licences:**
- RBI series are for internal processing only. The site may not deep-link or cache them until RBI grants permission.
- MoF, SEBI, GSTN, DGCI&S and CAG permissions are still outstanding (ISSUES P1-9).
- These block the public deploy (Checkpoint C), not the build.

---

*Run record for this note:*
- Final SAM run: certified, 83 Newton iterations, objective 114,127.730687.
- Reruns for this note: the acceptance figures were recomputed with the audit module's own helpers (`tests/verify/test_sam_balanced_audit.py`); the aggregates and household tables were computed from `sam_balanced.parquet` and `sam_entries_balanced.parquet`.
- Offline test suite re-run on 2026-10-01 for this note: 4,221 passed, 0 failed, 25 xfailed, 1 deselected, in 9 min 54 s. `manifest --check`: up to date.
