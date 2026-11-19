# Verification: SAM framework, balancing mathematics and numerics

Verifier: independent agent (math lens), 2026-09-30. Scope: `pipeline/sam/balance.py`, `pipeline/sam/spec.py` (balancing constants), the balancing parts of `pipeline/sam/run.py` and `pipeline/sam/report.py`, and `tests/sam/test_sam_balance.py`. The framework code was not changed.

**Verdict: needs fixes before the first full balancing run.** The formulation on paper is right: signed priors, z ≥ 0, the weighted objective w·|a|·(z ln z − z + 1), exact balance with one redundant equation per component dropped, and GRAS as published. The textbook tests pass (13/13, reproduced). The numerics, though, do not hold at the real problem size. On realistic 5,000-entry SAMs, Clarabel returns answers that it labels `optimal` but that are materially wrong. It invents slack on problems that are feasible, and on other feasible problems it fails outright. The framework has no check that would catch any of this. Balancing is not yet deterministic across thread counts at this size, and the polish can flip signs silently. None of this shows up today, because balancing only runs once all nine blocks exist and the textbook tests are too small to trigger it.

## How this was checked

Throwaway scripts live in the session scratchpad (`mathprobe/`), not in the repo. The main tools were:

- **An independent reference solver.** It is a semismooth Newton method on the concave dual of the same problem: maximise over λ the sum over e of min over z in [lo_e, hi_e] of { w_e|a_e|(z ln z − z + 1) + a_e(λ_row − λ_col) z }, plus λ·b. It handles exact balance plus anchored boxes. At the optimum z_e = clip(exp(−sign(a_e)(λ_row − λ_col)/w_e)). It converges in 4–6 Newton steps, with a balance residual around 1e-7 crore. Any feasible point it finds with a lower objective proves the framework's answer is suboptimal, because the objective is strictly convex.
- **A realistic random SAM generator.** It builds 128 accounts and 5,000 entries with log-uniform values from ₹0.01 to ₹3e7 crore. About 4% are negative, 10% fixed and 45% anchored, with the production rule of ₹1 crore per cell (`tol_rel = 1/|a|`); the rest are free, with mixed confidence. It adds 240 band constraints with ±n crore tolerances. Priors are a balanced "truth" perturbed by 2–30% on the free entries and rounded to whole crore on the anchored ones. So the truth is a known feasible point with zero slack.
- **Real production entries.** The 962 anchored and 102 fixed entries, at their real magnitudes and tolerances, closed with synthetic free entries through one extra account.
- **Edge-case probes.** Fixed-only accounts, sign infeasibility, conflicting bands, anchored-bound conflicts, polish on tiny free links, GRAS with only-negative and fixed-only rows, and determinism across `PYTHONHASHSEED` and each thread variable separately.

## Findings

### F1 (critical): cross-entropy answers labelled `optimal` are materially wrong at realistic size, and nothing checks optimality

**Where:** `balance.py` 138–229 (`_solve`) and 254–260 (a status of `optimal` is accepted as is). `spec.py` 106 and 112 (SCALE and the Clarabel tolerances).

**Evidence (realistic random SAM, seeds 0–3, no bands, 45% anchored at ₹1 crore):**

- Clarabel reports `optimal`, after the automatic retry at default tolerances.
- The objective is 0.1–42% above the reference optimum, and the reference is feasible: balance residual ≤ 1e-7 crore, no anchored violations. Seed 0: 1,732,741 vs 1,674,432. Seed 1: 213,213 vs 150,093.
- Small free entries are blown up. For free entries under ₹100 crore, the maximum z is 272–842, against 1.3–2.3 at the true optimum. In seed 0, 481 of 4,551 variable entries are more than 100% away from the optimum. Example: a ₹0.86 crore low-confidence entry comes out at ₹277 crore (z = 322) where the optimum has z = 1.26.
- Large entries are misallocated by up to ₹380 crore to compensate.
- **The audit cannot see this.** Each distortion is below ₹500 crore, so `needs_explanation` never fires. The over-threshold set is almost identical to the true optimum's (628 vs 627 entries). A balanced SAM with hundreds of cells inflated 100–800× would pass every test in `test_sam_audit.py`.

**The same pattern with real production entries** (962 anchored, closed synthetically): the objective is 98,152 vs a reference of 93,312, and the maximum z on small free entries is 242 vs 1.2.

**Cause.** The objective coefficients w|a| (in ₹ lakh crore) run from about 2.5e-8 to 4.8e3, eleven orders of magnitude. Clarabel's termination tests are dominated by the large terms. The exponential cones of small entries are left near the centre of the barrier, which is why z sits around 300 for all of them. None of the following fixes it:

- tighter tolerances: `optimal_inaccurate` at 1e-10 and at 1e-14
- `max_iter` 1000
- turning equilibration on or off
- a different static regularisation
- rescaling (SCALE 1e-3 to 1e-7: all still wrong)

Recovering z from Clarabel's balance duals does not work either, because the duals are just as inaccurate.

**Fix.** The optimum has the closed form z_e = exp(−s_e(λ_r − λ_c + Σ_k∈e μ_k)/w_e), clipped to the anchored box. This does not depend on |a_e|, so the dual is naturally well scaled. Two changes:

- (a) Make the primary solver a Newton (semismooth / projected) method on the dual over λ (one per account) and μ (one per band). L1-penalised slacks become simple bounds on the multipliers: |μ| ≤ SLACK_PENALTY, and the same kind of bound for the anchored-box multipliers. This is a bound-constrained, smooth, concave problem with about 130 + 2 × (number of constraints) unknowns. The reference version needs 4–6 steps.
- (b) Whatever the solver, add a KKT certificate after solving and fail the run if it does not hold. For every free entry not at a bound, check |w_e ln z_e + s_e(Δλ + Σμ)| ≤ 1e-8. Anchored entries sit at a bound or satisfy the same condition. Constraints are complementary.

Also add a test that solves a realistic-size random SAM (5,000 entries, ₹0.01 to ₹3e7 crore, ₹1 crore anchored tolerances) and compares it with an independent reference, both on the objective and on max relative error per entry.

### F2 (major): slack appears on feasible problems, so "non-zero slack means infeasible" is false as implemented

**Where:** `balance.py` 180–186 and 204–209. `spec.py` 107 (`SLACK_PENALTY = 1e3` per ₹ lakh crore). The `report.py` 132 heading reads "infeasibilities that were not silently absorbed".

**Evidence.** On the random SAM with bands, seed 2, the known truth has zero anchored and zero band violations, and a balance residual of 2.5e-7. Yet `cross_entropy` returns `optimal` with 7 anchored-bound "violations". One entry with a ₹1 crore allowance moves ₹211 crore past its bound; the others move 1.6, 5.6, 6.7, 7.4 and 46.9 crore. Seed 3 gives two violations, of 14.4 and 4.1 crore. BALANCING.md would list these as infeasibilities, and ISSUES.md entries would be demanded for them.

An L1 penalty is exact only if it exceeds the largest optimal multiplier. Tight bands (±n crore on totals of ₹1e7 crore) give large multipliers. Raising the penalty is not a way out with this solver: at 1e5 it returns `optimal_inaccurate`, and at 1e7 `user_limit`.

**Fix.** Solve in two phases, lexicographically:

- **Phase 1** is an LP (HiGHS is already installed): minimise the total slack in ₹ crore, subject to balance, z ≥ 0, the anchored boxes and the bands.
- **Phase 2** is the CE problem with each slack capped at its phase-1 value plus a small tolerance.

Slack then appears only when the problem really is infeasible, and the phase-1 LP names the conflicting constraints. In the dual formulation of F1 this is the same thing as the multiplier bounds, provided they are set from phase 1. Until then, reword the report heading and SAM_GUIDE s.12 to say "slack (infeasibility or penalty not exact)".

### F3 (major): Clarabel fails outright on feasible realistic problems

**Where:** `balance.py` 254–257. The retry happens only on `optimal_inaccurate`, not on `solver_error`.

**Evidence** (random SAMs where the reference solves to a 4e-8 gradient in 4 iterations):

- Free and fixed entries only: `optimal_inaccurate` at both tolerance settings, so the run fails.
- 45% anchored at 2% tolerance (the guide's cash-to-accrual advice): `solver_error` at both settings.
- On every realistic-size problem tried, the tight-tolerance first attempt ends `optimal_inaccurate`, so the "one retry at defaults" path is always taken. Yet `balancing_run.json` records `solver_options` = the tight settings (`run.py` 156), not the settings of the solution it accepted.

**Fix.** The same as F1: the dual Newton method removes the dependence on Clarabel for the main solve. Also record the options actually used, and treat `solver_error` like `optimal_inaccurate` for the one retry.

### F4 (major): `tol_rel` is rounded to 6 decimals on write, so anchored allowances are distorted or zeroed

**Where:** `framework.py` 922: `io.write_parquet(ent, …)` with the default `decimals` for every float column. Balancing reads the rounded file (`assemble.read_entries`).

**Evidence** (`data/sam/2023-24/blocks/production_entries.parquet`): 5 of the 962 anchored entries now have `tol_rel == 0.0`. They are A_CNST←C_CNST (₹69.2 lakh crore), C_TRAD←M_TTM, A_DWEL←C_DWEL, A_FINS←C_FINS and A_ITSV←C_ITSV. These entries are effectively fixed, and any move is reported as slack. When the real production entries were run, all five showed up as "anchored violations" of 0.02–0.06 crore. Another 91 entries have allowances that are no longer whole numbers of cells: A_TRAD←C_TRAD gets ₹3.03 crore, and A_CROP←C_CROP ₹28.78 crore. The contract check "anchored needs tol_rel > 0" (framework.py 705) runs before rounding, so the file on disk breaks it.

**Fix.** Write `tol_rel` without rounding (`decimals={"tol_rel": None}` after rounding it to 12 significant digits), or store the allowance as an absolute `tol_abs` in ₹ crore. Re-validate after writing.

### F5 (major): balancing is not thread-count deterministic at realistic size, and neither the test nor `repro` covers it

**Where:** `tests/sam/test_sam_balance.py` 282–326 (25 accounts, about 300 entries). The full `repro` balances only when all nine blocks exist, which is not the case today.

**Evidence** (5,000-entry random SAM, thread variables changed one at a time):

- `PYTHONHASHSEED` 0 vs 1, and OMP, MKL or POLARS threads set to 4: identical results.
- **`OPENBLAS_NUM_THREADS=4`**: the Clarabel iteration count changes from 38 to 33, all 4,551 variable entries differ, and the largest difference is **₹100 crore**. GRAS stays identical.

`repro` sets every `THREAD_VARS` to 4, so the first full run with all blocks will not be byte-identical. The ₹100 crore sensitivity to rounding order is another symptom of F1.

**Fix.** Fixing F1 (the dual Newton method, sums via bincount, one sparse factorisation) makes the result thread-independent by construction. In the meantime, pin `OPENBLAS_NUM_THREADS=1` inside the balancing call with `threadpoolctl`, and make the determinism test use a 5,000-entry problem.

### F6 (major): the polish can flip signs silently, and its size is not capped

**Where:** `balance.py` 332–376 (the flips are counted at 374 but never enforced), and `Solution.ok` at 99–100.

**Evidence.** A and B are joined by anchored entries, and the only free path A→C→B carries ₹0.02 crore. With a solver residual of ₹0.05 crore, the polish sets both free entries to −0.05 crore. The polish info says `sign_flips 2`, yet `ok` would stay True.

On realistic problems the pre-polish imbalance is **₹0.24–0.31 crore**, and the polish moves 2,400+ entries by up to ₹0.23 crore. The module doc (line 19) says the residual is about 1e-3 crore. Given F1, where default-tolerance solutions are the norm, and the ₹0.01–1 crore free cells that household and tax splits will produce, a flip is plausible. SAM_GUIDE s.5 promises "Signs never flip". The polish also ignores constraint bands, although at this size it does not push them out.

**Fix.** Fail the run, or clamp and re-polish with that entry removed, whenever `sign_flips > 0`. Also fail if `max_imbalance_before` exceeds, say, ₹1 crore, because then the solve itself is wrong. Put `sign_flips == 0` into `Solution.ok`. Log the polish change per entry, as a column in `balancing_log`.

### F7 (minor): the pre-check tolerance is stricter than the balance tolerance, and the resulting failure names no account

**Where:** `balance.py` 172–176 (eps = 1e-9 lakh crore = ₹1e-4 crore) against `BALANCE_TOL` = ₹0.01 crore. `SLACK_REPORT_TOL` = 0.01 is used at 271.

**Evidence** (an X_DISC-like account whose entries are all fixed):

| Published cells miss by | Result |
|---|---|
| ₹0.1075 crore | Fails and names X_DISC, with −0.1084 from a diagnostic that ended `optimal_inaccurate` |
| ₹0.005 or ₹0.0005 crore, both within the acceptance tolerance | Fails with `infeasible`, `balance_slack = {}` and no account named |
| ₹0.00005 crore | Passes |

**Fix.** Use eps = `BALANCE_TOL` (in scaled units) in the pre-check. A fixed-only component within tolerance is then accepted and its residual reported. Alternatively, always name the components whose fixed parts do not sum to zero; they are known exactly without any solve.

### F8 (minor): the infeasibility diagnostic over-names accounts

**Where:** `balance.py` 158–162 and 261–275.

**Evidence.** The sign-infeasible account is D: fixed receipts 2e4, fixed payments 1e4, and one free receipt. The diagnostic reports A +82, B +149, C +9,768 and D −10,000 as accounts that "cannot close". A, B and C can close. Balance slacks always sum to zero, and the L1 counterpart gets spread arbitrarily.

**Fix.** Report the minimum-slack LP solution (as in F2, phase 1), or the Farkas certificate. Word the message as "infeasibility shows at …", and name the account with the largest slack of each sign together with its fixed and sign-locked entries.

### F9 (minor): the over-threshold logic works per entry, but SPEC asks per cell, and explanations are not tied to magnitudes

**Where:** `run.py` 106 and `spec.py` 117–122. SPEC §6 says "no **cell** changes by more than a stated threshold".

- Three components of one cell, each moving ₹4,000 crore (₹12,000 crore in total), need no explanation.
- An explanation is keyed only on (row, col, ref, component). It stays valid when a later run moves the entry ten times further, and stale keys are accepted silently.

**Fix.**

- Apply `needs_explanation` at cell level as well.
- Store the explained prior, balanced value and change in `explanations.yaml`, and require the current change to be within ±20% of it, or ₹500 crore.
- Flag explanations that match no entry that needs one.

### F10 (minor): `binding()` marks most of a narrow band as binding

**Where:** `balance.py` 320–329. eps = 1e-7·max(1, |bound|) + 1e-6.

For a ₹69 lakh crore total with a ±₹1 crore band, eps = ₹0.69 crore, so 69% of the band counts as "at a bound". Production's ±n-crore constraints on large totals will show up in BALANCING.md's "Constraints at a bound" list and in the per-entry `binding` column without really binding.

**Fix.** Use a tolerance tied to the band width, for example min(1e-6·width, 1e-3 crore), or use the solver's multipliers (non-zero dual = binding).

### F11 (minor): GRAS is correct, but its findings are computed even when it has not converged

GRAS matches the published algorithm, as checked:

- The column step s_j = (v_j + √(v_j² + 4p_j n_j))/(2p_j), with p_j = Σ r_i a⁺ and n_j = Σ a⁻/r_i.
- The Temurshoev et al. correction s_j = −n_j/v_j when p_j = 0.
- It agrees with a cvxpy minimiser of Σ|a|(z ln z − z) to 8.6e-5 on a matrix with an all-negative row and an all-negative column.
- Signs are kept and zeros preserved.
- An only-negative row with a positive target, and a fixed-only account whose fixed entries do not balance, are both flagged as not converged.
- It converges in 77 iterations to a 8.3e-7 gap at 5,000 entries.

However, `run.py` 107–108 computes `gras_finding` against a non-converged GRAS x, and `balance.py` 444 records flags only when `it == 1`. A non-converged cross-check would flood BALANCING.md with meaningless "findings".

**Fix.** Skip or label the GRAS findings when `converged` is False.

## What was verified and holds

- **The objective and constraints** match DESIGN_BRIEF s.5.1:
  - x = a·z with z ≥ 0, so signs are kept and zeros stay zero in the solve.
  - The weights are 16 / 4 / 1 / 0.25.
  - `-cp.entr(z) - z + 1` is the convex form, and it is DCP-valid.
  - Dropping one equation per connected component is exact, because the sum over a component of (Bz + b) equals the component's fixed part.
  - Diagonal entries cancel.
  - Anchored bounds work for negative priors.
- **The textbook answers** hold (reproduced):
  - the 2-account closed form 10·0.6^0.2
  - the 4-account KKT solution with negative, fixed and anchored cells, to 1e-4
  - one-sided constraints
  - band conflicts reported as slack with an `optimal` status
  - a negative-cell sign infeasibility fails the run
  - a fixed-only unbalanced account is caught without solving
- **Anchored-bound conflicts** (a tight anchor against a fixed entry) and **contradictory min and max constraints** are both reported. The run stays `ok`, and the audit test then demands an ISSUES.md entry, as the brief intends.
- **The polish algebra** is right: δ = (|x|/w)(μ_row − μ_col) with the grounded weighted Laplacian solved per component gives exact balance (1e-9) when every residual can be reached through free entries.
- **`needs_explanation`** implements the s.5.3 thresholds exactly (≥ 5,000; or ≥ 500 and ≥ 10%).
- **Hash-seed independence** holds, and so does independence from OMP, MKL and POLARS thread counts. Only OpenBLAS threads break it (F5).
