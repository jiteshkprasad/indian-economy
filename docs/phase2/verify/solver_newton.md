# Verification: the SAM balancing solver (dual Newton, DECISIONS D2-1)

Verifier: independent agent (wave B), 2026-09-30. Scope: `pipeline/sam/balance.py` as it stands after the Wave A fixes (M-F1 to M-F11 in `docs/phase2/FRAMEWORK_REQUESTS.md`). That means the phase-0 pre-check, the phase-1 minimum-slack LP and widening, the dual Newton method with its proximal fallback, the KKT certificate, the polish, GRAS and BLAS pinning. The framework code was not changed.

Regression test: `tests/verify/test_sam_solver_certificate.py`. It has 17 passing checks and 4 strict xfails for the confirmed defects below, and runs in about 45 s. The throwaway probes are in the session scratchpad, not in the repo.

**Verdict: sound for the problems it certifies, but it needs fixes before the first full run.**

- **Every answer the solver called optimal was optimal.** I checked this with my own certificate and my own dual function, and against Clarabel and SCS where they are reliable. This held on 60+ problems, from textbook size up to 8,000 entries with 1,500 bands. The phase-1 slack is exactly the independent LP minimum.
- **Results are byte-identical** across hash seeds and thread counts, including on the proximal-fallback path.
- **Nothing is silently wrong.** Every failure I provoked failed the run loudly.

The defects are robustness defects: the solver fails on problems it should solve.

- **S-1 (major).** A realistic pattern fails the whole run: a constraint over a single anchored entry whose interval meets the entry's box only narrowly. Phase 1 creates exactly this geometry whenever such a constraint conflicts with the box. The real blocks already declare single-entry constraints over anchored entries (taxes `t1.cit`, `t1.pit`).
- **S-2 and S-3 (minor).** Two tolerance inconsistencies can fail feasible or near-feasible problems.
- **S-4 to S-7 (minor).** Diagnostics and latent issues.

## How this was checked

### 1. An independent KKT certificate

I wrote my own certificate, `_certificate` in the test file. It does not use the solver's multipliers. It works only from x and the problem:

- **Primal feasibility.**
  - Fixed entries are unchanged, bit for bit.
  - No sign flips.
  - The balance of *every* account holds, including the dropped "sink" equations, within ₹0.01 crore.
  - Anchored boxes hold within 1e-5 crore.
  - Bands hold within 1e-4 crore.
- **Multiplier recovery.** λ (per account) and μ (per band found active) are recovered by least squares from the entries strictly inside their bounds. The equation used is `ln z_e + s_e (λ_row − λ_col + Σ_k μ_k) / w_e = 0`, which is the stationarity form z = exp(−s(Δλ+Σμ)/w).
- **Dual feasibility and complementarity:**
  - the stationarity residual on interior entries;
  - the sign of the derivative at entries on a box bound (≤ 0 at the upper bound, ≥ 0 at the lower);
  - the sign of each band multiplier against the side the band sum sits on (μ > 0 only at hi, μ < 0 only at lo, 0 inside).
- **Duality gap.** I evaluate my own dual function q(λ, μ) = Σ_e min over the box of [c φ(z) + t_e z] + λ·b − σ(μ). For any multipliers this is a lower bound on the optimum, so f(x) − q ≤ 1e-8·f is a proof of optimality.

### 2. Independent solvers

- **Clarabel and SCS** (cvxpy, primal z-form, tolerances 1e-12 and 1e-10). I used them on 40 small problems: 6–19 accounts, 20–180 entries, values ₹1–1e4 crore, 0–19 bands of every kind, negative entries, and anchored at n crore and at 2%. On larger problems or wider value ranges they are unreliable, as the Wave A review showed and as I confirmed (S-7).
- **scipy `trust-constr`** on the same problems. It is less precise (1e-7) and once returned an infeasible point, so it is corroboration only.
- **An independent phase-1 LP** in cvxpy + HiGHS.
- **A dense weighted-least-squares solve** for the polish.
- **A Clarabel entropy minimiser** for GRAS.

### 3. Realistic-size problems

My own generator, `gen`, uses the tests' truth balancer only to build a feasible truth. Each problem has:

- 128 accounts and 6,000–8,000 entries, log-uniform from ₹0.01 to ₹3e7 crore;
- 5% negative entries and 10 diagonal entries;
- 10% fixed and 45% anchored. Of the anchored entries, most have tol = 1–5 crore per cell, 10% have 2%, and 2% are loose (tol 1.5, so the lower bound is z = 0). The rest are free, with mixed confidence.
- 0–500 bands:
  - account-row subsets at ±n crore, with nested tighter sub-bands;
  - one-sided min and max bands, some binding at the truth;
  - cross-account totals at ±max(1, 1e-4·|t|);
  - duplicate selections with different tolerances;
  - single-entry bands;
  - ±₹0.01 crore near-equality column blocks.

A stress sweep (`t5`; 11 cases completed before it was stopped for time) also varied accounts (20–128), entries (300–8,000), band density (up to 1,500 bands), value range, tightness and prior noise.

### 4. Hand-built edge cases

- a band equal to an account's balance;
- duplicates that differ only in fixed members;
- an all-fixed band;
- optima on the boundary (z = 0) and near it;
- anchored conflicts of 5e-7 to 0.02 crore around `LP_ZERO`;
- contradictory min/max and nested bands;
- sign locks;
- negative-heavy accounts;
- an equality band with lo = hi over a diagonal entry;
- loose anchored entries driven to their low end.

### 5. Determinism

The same problems were run in subprocesses with PYTHONHASHSEED 0, 1, 7 and 123, and OPENBLAS/OMP/MKL/POLARS threads at 1, 4 and 8.

### 6. Polish, GRAS and the cvxpy override

Each was checked against the independent references above.

## Findings

### S-1 (major): a single-entry constraint that meets its anchored entry's box only narrowly does not converge, and phase 1 creates exactly that case

**Where:** `balance.py`, in `_widen` (WIDEN_MARGIN = ₹0.001 crore), `_dual_newton` (the ε-active set) and `_proximal_path`.

**Evidence:**

- **Feasible case, no slack at all** (`t10`, realistic 6,000-entry problems with 300 bands). Three single-entry bands each overlap their anchored entry's ±n-crore box only in its top ₹0.0005 crore. The run ends `not_converged` after dual Newton (100 steps), the proximal path (60 outer steps) and Newton again (500 steps), 3,900 steps in all. This happened in 4 of 6 cases. With a ₹0.01 crore overlap it converges, but only through the proximal fallback (141–857 steps). With ₹1 crore it converges directly.
- **Infeasible case, where the run should succeed and report slack** (`t8`, `t9`, `t12`). A single-entry band conflicts with its entry's anchored box, for example by ₹20–25 crore. Phase 1 finds the right minimum slack (it equals my independent LP) and widens either the box or the band by slack + ₹0.001 crore. Either way the entry is left with a ₹0.001 crore feasible window.
  - Realistic seed 0: `not_converged` whenever that constraint is present. It passes without it, and passes with `WIDEN_MARGIN` = ₹1 crore.
  - Small problems (10–40 accounts, 60–600 entries, `t12`, both the sliver and the conflict variant): 7 of about 200 cases failed. Failures occurred with both LP placements.
- **Mechanism** (`t14`, seed 17):
  - The entry is clipped at its box bound and the band sum is strictly inside the band.
  - Yet the band's multiplier sits at μ ≈ −143 and moves back towards 0 by only about 0.009 per step, a damped gradient crawl. The dual is linear in μ while the entry is clipped.
  - A balance equation stays ₹0.0005 crore off, against a tolerance of 1.9e-5.
  - The ε-active-set rule never releases μ to 0, and the proximal path does not recover.
- **Relevance.** Real blocks already declare single-entry constraints over anchored entries. `taxes` has 9 single-entry constraints, 2 of them over anchored entries (`t1.cit`, `t1.pit`). A constraint that selects one SUT cell (production) or one BoP cell (rest of the world) is the same pattern. So is a block constraint on a cell that another block wrote as anchored, which is allowed (SAM_GUIDE s.6).
  - When band and box coincide exactly, as today in taxes, it solves fine: I checked 30 such bands on entries at their box bounds (`t11`).
  - The failure needs the band to be offset from the box, which is exactly what a disagreement between two sources produces.
- **Nothing is silently wrong.** The run fails loudly, with `not_converged`, a failed certificate and the "smallest z" hint. That hint points at WA-1 ("degenerate, heavily constrained problem"), which is misleading here: the problem has one band.

**Fix (proposed; framework owner):**

1. **Fold single-entry bands into the entry's box.** A band whose variable members are exactly one entry (plus fixed members) is an exact bound on that entry's z. In `_core`, intersect it into `zlo`/`zhi` instead of adding a band row. An empty intersection goes to phase 1 as slack on the band's side, and the widened box then becomes a clip, not a degenerate dual direction. This also shrinks K.
2. **Make the widening margin scale-aware,** for example max(₹0.001 crore, 1e-3 × the slack), so that a widened bound never leaves a sliver narrower than about 1e-6 of the entry.
3. **In `_dual_newton`,** set to 0 any band multiplier whose members are all clipped at box bounds while the band sum is strictly inside the band. The dual is linear in μ there, and the maximiser along μ is at 0 or at a kink.

Keep `test_single_entry_band_against_an_anchored_box_converges` (strict xfail) as the acceptance test.

### S-2 (minor): Newton can stop at a point its own certificate rejects

**Where:** `_dual_newton` stops when `_merit` ≤ 1 (the balance and band residuals within NEWTON_TOL_ABS + NEWTON_TOL_REL·gross). `kkt_certificate` then also requires a duality gap ≤ 1e-8·max(1, |f|). The gap equals −λ·residual, so a stop anywhere inside the residual tolerance does not imply the gap test.

**Evidence** (`t3` 4c/4d, `t4`). The problem is strictly feasible with an interior optimum: a free entry must be ₹0.001 crore (z = 2e-4). Newton stops after 11 steps with a 5.4e-7 crore residual. The gap is 9.2e-7, so the run fails with "KKT certificate FAILED". Continuing Newton for 2 more steps, from the same point and with the same code, reaches a gap of 1.2e-15 and the certificate passes.

This was never observed at realistic size: across 60+ realistic runs the final Newton step overshoots quadratically, the residuals were ≤ 3e-5 crore and the gaps ≤ 1e-12. The risk grows when the objective is small (a nearly balanced prior) or the multipliers are large.

**Fix.** After the merit test passes, keep taking full Newton steps until the certificate's gap test holds as well (typically 1–2 steps), or stop on the certificate's own conditions. Strict xfail: `test_newton_stops_only_where_the_certificate_holds`.

### S-3 (minor): phase-1 slack at or below LP_ZERO is neither widened nor tolerated

**Where:** `_phase1` and `_widen` treat slack ≤ LP_ZERO (₹1e-6 crore) as noise. The certificate's gap test then fails on the resulting infeasibility.

**Evidence** (`t3` case 5). An anchored bound is infeasible by ₹5e-7 or ₹9e-7 crore (₹50–90). Phase 1 reports the slack (5.000001e-7, matching my independent LP) but does not widen. Newton "converges" with the residual inside its tolerance, but the certificate gap is 1.2e-8 and 2.7e-8 against a limit of 1e-8, so the run fails. At ₹2e-6 crore the bound is widened and the run succeeds.

HiGHS returned exactly 0 slack on every feasible realistic problem, so a noise threshold is not needed at that level.

**Fix.** Widen any positive slack (by slack + WIDEN_MARGIN), or set LP_ZERO far below the Newton tolerance (for example 1e-9). Report as a finding only above SLACK_REPORT_TOL, as now. Strict xfail: `test_slack_below_lp_zero_does_not_fail_the_run`.

### S-4 (minor): a boundary optimum fails with an unexplained certificate failure

Suppose balance or a band forces a free entry to exactly zero. Examples:

- an account whose fixed receipts and payments already match, plus one free receipt;
- a `max 0` band over a positive entry.

The primal optimum is then z = 0, where the dual optimum does not exist. Phase 1 reports zero slack. Newton "converges" to z ≈ 1e-7, and the run fails with `status: optimal` and "KKT certificate FAILED" and nothing more (`t3` 4, 4e). Failing is right, because the entry would have to become a structural zero. But the "smallest z" diagnostic is printed only when Newton does not converge.

**Fix.** On a certificate failure, also print the entries with the smallest z and say that the constraints force them to zero (a sign lock at the boundary).

### S-5 (minor, latent): the polish ignores bands, and its band moves are then reported as slack

`polish()` is exactly the minimum weighted-least-squares step on free entries. It matches my dense KKT solve to 1e-9, touches no other entries, and refuses sign flips. But it ignores constraint bands. When it runs, it pushes binding bands out of their interval by up to its own adjustment:

- 0.005–0.08 crore for 0.1-crore residuals (`t6`);
- 0.014 crore in an in-run test with a deliberately loose Newton stop.

`band_violations()` then reports these as slack findings, which BALANCING.md presents as infeasibilities. The problem is latent: the polish never ran in any realistic solve, because Newton's residual (≤ 3e-5 crore) is below POLISH_TRIGGER (1e-4).

**Fix.** Add the binding bands as equality rows to the polish WLS, or report polish-induced band moves separately from phase-1 slack.

### S-6 (minor): a constraint over fixed entries only is outside phase 1

`_core` skips a band with no variable members. If it is violated, it appears in `band_violation`, which feeds BALANCING.md. However:

- `phase1.total_slack` excludes it;
- no phase-1 message is written;
- `ok` stays True.

In `t3` case 3, a ₹3 crore violation was reported only in `band_violation`. This is known without any solve.

**Fix.** Report it in the pre-check, alongside the fixed-component check, as a named conflict between fixed data and a constraint.

### S-7 (note): the cvxpy override practically never passes the certificate

At realistic size Clarabel's answers are still off by up to 234% on some entries (`t15`). Even on a 150-entry problem at 1e-10 tolerances, the recovered-multiplier certificate fails, because the objective differs by 1.4e-8 relative and x by 3.9e-6. The run then fails loudly, which is safe and documented, but the override is not a usable fallback.

### Known limit WA-1, confirmed and still loud

In the over-constrained regime (bands ≥ 1.5 × entries: 600 and 401 bands on 266 entries), the solver ends `not_converged` and the run fails. It does not certify a wrong answer.

At the upper end of the realistic range, 1,500 bands on 8,000 entries needed the proximal fallback: 591 steps, 250 s on a loaded machine. The result was certified.

## What was verified and holds

- **Optimality at realistic size.** I ran 20 problems (seeds 0–4 × 0/150/300/500 bands; 6,000–8,000 entries; ₹0.01–3e7 crore) plus the stress sweep. Every `ok` answer passes my independent certificate:
  - stationarity ≤ 2e-14;
  - correct signs at box bounds and bands;
  - no wrong-sign multipliers;
  - my own duality gap |f − q|/f ≤ 1e-12;
  - every account (sinks included) balanced within 3e-5 crore;
  - fixed entries unchanged.

  On these feasible problems phase-1 slack is exactly 0, there are no band or anchored violations, and the objective is below the truth's. The iteration counts were 4 steps with no bands and 7–82 steps with 150–500 bands (0.05–2.9 s). A problem with 600 near-equality bands on 3,000 entries (the proximal path) was also certified.
- **Agreement with independent solvers.** On 40 small problems, Clarabel and SCS agree with Newton's objective to ≤ 3.1e-10 relative (typically 1e-12) and on every entry to ≤ 2e-8 relative. Where they report `optimal_inaccurate` they are the ones that drift, by up to 1.6e-3.
- **Infeasible problems:**
  - The phase-1 minimum total slack equals my independent LP exactly: 125.000000 and 126.000000 crore on realistic problems, and 5, 10 and 12.5 crore on small ones.
  - The reported violations add up to that minimum plus the ₹0.001 crore margin.
  - The answer is certified optimal for the widened problem, and the feasible remainder is solved exactly.
  - A sign-locked account is named on its own.
  - A tie between placing slack on a nested band or on an anchored box is resolved by the LP, as documented.
- **Structure edge cases:**
  - a band dependent with an account's balance;
  - duplicate selections that differ only in fixed members;
  - an equality band with lo = hi over a diagonal entry;
  - a ₹3e7 and a ₹0.01 crore entry in one ±₹0.01 crore band;
  - negative-heavy accounts;
  - loose anchored entries driven towards z = 0.

  All are certified, and they match Clarabel to ≤ 2.3e-5 crore on entries up to ₹3e7 crore (Clarabel reports `optimal_inaccurate` on the two largest differences).
- **Determinism.** Output was byte-identical, as one sha256 over three problems (including a proximal-fallback one) and their GRAS, for PYTHONHASHSEED 0/1/7/123 with threads 1/4/8 (OPENBLAS, OMP, MKL, POLARS). `single_threaded_blas()` finds and pins both bundled OpenBLAS libraries.
- **Polish.** It is exactly the weighted-least-squares step on free entries, leaves exact balance (≤ 6e-9), touches no fixed or anchored entry, refuses a sign flip (and returns x unpolished) and refuses a residual above POLISH_MAX.
- **GRAS:**
  - It matches an independent entropy minimiser to ≤ 4e-7 where Clarabel is accurate (3e-5 where Clarabel says `optimal_inaccurate`).
  - It keeps signs with negative cells.
  - `gras_sam` holds fixed entries and hits the mean targets to 8e-7 at 6,000 entries in 88 iterations.
- **The framework's certificate is sound.** Every solve it passed also passed mine. It rejects the defective cases above rather than accepting them. Its stationarity test is trivially met by the dual method (z is computed from y), so its real content is primal feasibility, complementarity and the duality gap. That is the correct proof for a dual method, and my independent gap agrees with it.

## Re-verification (wave C close-out, 2026-10-01)

Re-verifier: an agent that wrote neither the solver nor this regression test (SPEC rule 3). Scope:

- the Wave B and Wave C solver changes in `pipeline/sam/balance.py`: C-1 (a band multiplier at zero), the interior-point fallback of DECISIONS D2-23 (C-3, C-4), C-5 and the per-block explanation files (C-6);
- the edits that the framework owner made to `tests/verify/test_sam_solver_certificate.py` after this report: the Wave B dispositions and the Wave C additions.

The test file is untracked. The scratchpad holds a copy taken before Wave C (`orig/test_sam_solver_certificate.py`, 01:37) and the Wave C starting point of `balance.py` (`fw_wavec/balance_orig.py`, 01:47). I diffed both against the current files.

**Code checks.**

- **C-1** is the one-line change claimed. In `_newton_direction`, `cross` no longer requires `nu != 0`. So a multiplier already at 0 whose Newton step points to the forbidden side is now held at 0 and the rest is re-solved. Before, the line search's projection held it at 0 anyway, so the direction it came from was inconsistent. The change is correct: the reduced system is then exactly the Newton system of the active face.
- **The certificate did not change.** `kkt_certificate` is byte-identical to the pre-Wave C version (same md5). `spec.py` keeps KKT_TOL 1e-8, NEWTON_TOL_ABS 1e-6, NEWTON_TOL_REL 1e-12 and BOUNDARY_Z. The only new constants are `RHO_CAP` and `IPM_*`, as stated.
- **D2-23 is respected.** An interior-point answer is accepted only through that certificate.

**The real problem, judged by this file's own certificate (`_certificate`, not the framework's).**

| Run | Path | Steps | Verifier certificate | Same optimum as the published SAM |
|---|---|---:|---|---|
| Real prior (`sam_entries_prior.parquet` + `constraints.parquet`), as run | interior-point fallback | 249 | passes | max \|dx\| 5e-7 crore (6-decimal rounding) |
| Same, fallback forced (`NEWTON_FIRST_TRY = 1`) | interior-point fallback | 150 | passes | 5e-7 |
| Same, plain dual Newton allowed 2,000 steps | direct | 105 | passes | 6.75e-7 |

So after C-1 the direct method solves the final problem by itself, in 105 steps. The fallback was used only because the first-try budget is 100 (balanced_sam.md RV-C-4). A separate certificate, which I wrote and which reads only the published Parquet, gives a duality gap of 5.7e-12 relative and recovers the run's counts: 174 binding bands, 8 entries at their bounds, 0 multipliers on the wrong side (balanced_sam.md, Re-verification s.1).

**Generator problems (3,000 entries, 300 bands).**

- Seeds 3, 4, 6 and 7 with the fallback forced: each passes this file's certificate and equals the direct optimum, with objectives within 2.1e-13 relative.
- Seeds 8, 9 and 10 converge directly.
- Seeds 1 and 11 fail loudly on both paths, as boundary optima. Their phase-1 slack is 5.66 and 1,317 crore, and the certificate reports `entries_forced_to_zero` 1 and 2. This is consistent with Wave C's "10 certified, the same 2 fail loudly".
- Seed 2, the Wave B proximal-path problem, now converges directly in 38 steps, as the re-pointed determinism test says.

**Edits to this file, each confirmed.**

| Edit | Verdict |
|---|---|
| Wave B: strict xfails removed from `test_single_entry_band_against_an_anchored_box_converges` (17 sliver, 2 conflict), `test_newton_stops_only_where_the_certificate_holds` and `test_slack_below_lp_zero_does_not_fail_the_run` | **Confirmed.** The cases are the report's (t14 seed 17; t3 4c/4d, a free entry forced to 0.001 crore; t3 case 5, 5e-7 crore of slack). Each assertion is what the strict xfail asserted (`s.ok`), and all three pass |
| Wave B: polish reference adds the bands the polish reports as held (S-5) | **Confirmed sound.** The held set comes from the framework. But the test independently requires every band at or outside a bound to be in it, a held band's sum not to move, and every other band to stay inside its interval. So a wrong held set cannot pass, and the reference stays its own dense KKT solve |
| Wave B, then Wave C: the determinism problem was re-chosen twice | **Confirmed.** gen(5) takes the interior-point fallback. gen(2) converges directly now, so it reaches the proximal path only with `NEWTON_FIRST_TRY = 20` and `IPM_FINISH = 0`. The output is byte-identical for PYTHONHASHSEED 0 and 123 and for 1 and 8 threads |
| Wave C: new `test_an_interior_point_fallback_answer_passes_the_independent_certificate` | **Confirmed.** It uses this file's certificate. My extra seeds (above) agree with it |
| Header docstring (interior-point and proximal fallbacks) | Accurate |

No expectation needed reverting and the file is not changed by this re-verification. `uv run python -m pipeline test tests/verify/test_sam_solver_certificate.py`: **22 passed** (17 + the 3 former xfails with 4 cases + 1 new). The framework's own Wave C tests also pass: 14 passed (`tests/sam/test_sam_balance.py`, `test_sam_pipeline.py`: zero multiplier, fallback, boundary optimum, real prior, explanation files).

**Findings.** None against the solver. The answer it certified is optimal by an independent proof. The Wave C changes do what FRAMEWORK_REQUESTS says, and every failure I provoked was loud and named. Two framework notes are recorded in balanced_sam.md:

- RV-C-3 (minor): the run record rounds the certificate and its tolerances to 6 decimals, so it prints a tolerance of 0.0.
- RV-C-4 (note): on this problem the fallback was triggered by the step budget, not needed for convergence.

Known limit WA-1 is unchanged. The adversarial probes were not re-run.
