"""Balancing on textbook problems with known answers (DESIGN_BRIEF s.5, s.7): cross-entropy with weights,
negative, fixed and anchored cells; constraint bands; infeasibility reported as slack; GRAS; polish;
determinism across hash seeds and thread counts. Plus the Wave A review (docs/phase2/verify/framework_math.md):
realistic-size SAMs against an independent reference (F1), slack only when infeasible (F2), the cvxpy
override (F3), thread-count determinism at realistic size (F5), polish guards (F6), the pre-check (F7),
infeasibility diagnosis (F8), binding tolerance (F10), GRAS flags (F11). And the Wave B solver review
(docs/phase2/verify/solver_newton.md): narrow windows against anchored boxes (S-1), forced zeros (S-4), the
band-aware polish (S-5), constraints over fixed entries only (S-6), the flat-value line search (WB-8)."""

from __future__ import annotations

import math
import os
import subprocess
import sys
import textwrap

import numpy as np
import pytest
from scipy.optimize import root

from pipeline.core.env import ALLOW_HASHSEED_VAR, ALLOW_THREADS_VAR, REEXEC_VAR, THREAD_VARS, pinned_environ
from pipeline.core.paths import REPO_ROOT
from pipeline.sam import spec
from pipeline.sam.balance import BandConstraint, Problem, cross_entropy, gras, gras_sam, polish

pytestmark = pytest.mark.sam

W = spec.CONFIDENCE_WEIGHTS


def _problem(n, entries, constraints=(), names=None):
    """entries: (row, col, value, role, confidence or tol)."""
    row = np.array([e[0] for e in entries])
    col = np.array([e[1] for e in entries])
    prior = np.array([float(e[2]) for e in entries])
    role = np.array([e[3] for e in entries], dtype=object)
    tol = np.array([e[4] if e[3] == "anchored" else np.nan for e in entries], dtype=float)
    weight = np.array([spec.entry_weight(e[3], e[4] if e[3] == "free" else None) for e in entries])
    return Problem(n, row, col, prior, role, tol, weight, list(constraints), names)


def test_two_accounts_closed_form_with_weights():
    # A <- B = 10 (high, w=4), B <- A = 6 (medium, w=1). KKT: ln z1 = lam/4, ln z2 = -lam, 10 z1 = 6 z2
    # => z1 = 0.6**(1/5): the balanced flow is 10 * 0.6**0.2 = 9.0288...
    p = _problem(2, [(0, 1, 10, "free", "high"), (1, 0, 6, "free", "medium")])
    s = cross_entropy(p, scale=1.0)
    assert s.ok, s.messages
    assert s.x == pytest.approx([10 * 0.6**0.2, 10 * 0.6**0.2], abs=1e-5)
    # equal weights: the geometric mean sqrt(60)
    p = _problem(2, [(0, 1, 10, "free", "medium"), (1, 0, 6, "free", "medium")])
    assert cross_entropy(p, scale=1.0).x == pytest.approx([math.sqrt(60)] * 2, abs=1e-5)


# A 4-account SAM with a negative free cell, a fixed cell and a (non-binding) anchored cell.
FOUR = [
    (0, 1, 50, "free", "medium"),
    (1, 2, 40, "free", "high"),
    (2, 0, 30, "free", "low"),
    (2, 3, 20, "fixed", None),
    (3, 0, 25, "free", "medium"),
    (1, 3, -5, "free", "medium"),
    (0, 2, 10, "anchored", 0.5),
]


def _kkt_answer(entries, n):
    """Independent solution: x_e = a_e exp(sign(a_e) (lam_row - lam_col) / w_e), lam_0 = 0, balance rows 1..n-1."""
    w = np.array([spec.entry_weight(e[3], e[4] if e[3] == "free" else None) for e in entries])

    def x_of(lam_rest):
        lam = np.concatenate([[0.0], lam_rest])
        out = []
        for (r, c, a, role, _), we in zip(entries, w):
            out.append(a if role == "fixed" else a * math.exp(math.copysign(1, a) * (lam[r] - lam[c]) / we))
        return np.array(out)

    def f(lam_rest):
        x = x_of(lam_rest)
        res = np.zeros(n)
        for (r, c, *_), v in zip(entries, x):
            res[r] += v
            res[c] -= v
        return res[1:]

    sol = root(f, np.zeros(n - 1), tol=1e-13)
    assert sol.success
    return x_of(sol.x)


def test_negative_fixed_and_anchored_cells_match_the_kkt_solution():
    p = _problem(4, FOUR)
    s = cross_entropy(p, scale=1.0)
    assert s.ok, s.messages
    want = _kkt_answer(FOUR, 4)
    assert s.x == pytest.approx(want, abs=1e-4)
    assert s.x[3] == 20  # fixed never moves
    assert s.x[5] < 0  # the negative cell keeps its sign
    assert 5 <= s.x[6] <= 15  # the anchored bound (+-50%) is not binding here
    assert np.max(np.abs(p.residual(s.x))) <= 1e-9
    # the working scale does not change the answer
    assert cross_entropy(p, scale=1e-2).x == pytest.approx(want, abs=1e-3)


def test_binding_anchored_bound_and_constraint_band():
    # tight anchor: entry 6 may move only +-1%, so the others take the adjustment
    ent = [*FOUR[:6], (0, 2, 10, "anchored", 0.01)]
    s = cross_entropy(_problem(4, ent), scale=1.0)
    assert s.ok and 9.9 - 1e-6 <= s.x[6] <= 10.1 + 1e-6
    # band: entry 0 (A0 <- A1) held within 47..48
    band = BandConstraint("c0", np.array([0]), 47.0, 48.0)
    s = cross_entropy(_problem(4, FOUR, [band]), scale=1.0)
    assert s.ok and 47 - 1e-6 <= s.x[0] <= 48 + 1e-6 and not s.band_violation


def test_one_sided_constraints():
    import polars as pl

    from pipeline.sam.balance import problem_from_frames

    # the balanced flow of the two-account example is 9.03; a floor at 9.5 and a cap at 8.5 bind, a cap at 12 does not
    ent = pl.DataFrame({"row": ["C_CROP", "H_R1"], "col": ["H_R1", "C_CROP"], "ref": ["C1a", "F3"],
                        "component": ["total", "total"], "value": [10.0, 6.0], "role": ["free", "free"],
                        "tol_rel": [None, None], "confidence": ["high", "medium"]},
                       schema_overrides={"tol_rel": pl.Float64})  # fmt: skip
    for kind, target, lo, hi in (("min", 9.5, 9.5, None), ("max", 8.5, None, 8.5), ("max", 12.0, None, None)):
        cons = pl.DataFrame(
            {"constraint_id": ["c"], "rows": ["C_CROP"], "cols": ["H_R1"], "refs": [None], "components": [None],
             "target": [target], "tol_abs": [0.0], "tol_rel": [0.0], "kind": [kind]},
            schema_overrides={"refs": pl.String, "components": pl.String},
        )  # fmt: skip
        p = problem_from_frames(ent, cons, ["C_CROP", "H_R1"])
        s = cross_entropy(p, scale=1.0)
        assert s.ok and not s.band_violation, s.messages
        want = lo if lo is not None else hi if hi is not None else 10 * 0.6**0.2
        assert s.x[0] == pytest.approx(want, abs=1e-5), kind


def test_infeasible_constraint_reports_slack_instead_of_succeeding_silently():
    # A <- B fixed 10, B <- A free 6: balance forces x = 10, but a band says B <- A <= 8.
    band = BandConstraint("cap", np.array([1]), 0.0, 8.0)
    p = _problem(2, [(0, 1, 10, "fixed", None), (1, 0, 6, "free", "medium")], [band], ["A", "B"])
    s = cross_entropy(p, scale=1.0)
    assert s.status == "optimal"
    assert s.x[1] == pytest.approx(10, abs=1e-6)  # balance is exact ...
    assert s.band_violation == {"cap": pytest.approx(2.0, abs=1e-4)}  # ... and the conflict is reported


def test_infeasible_balance_is_a_failure_that_names_the_accounts():
    # A <- B fixed 10; B <- A is negative (-6) and cannot change sign: B's account can never close.
    p = _problem(2, [(0, 1, 10, "fixed", None), (1, 0, -6, "free", "medium")], names=["A", "B"])
    s = cross_entropy(p, scale=1.0)
    assert not s.ok and s.status.startswith("infeasible")
    assert "B" in s.balance_slack  # A is its component's dropped equation; B is sign-locked
    assert any("account B cannot close" in m for m in s.messages), s.messages
    # a fixed-only unbalanced account is caught without solving
    p = _problem(
        3, [(0, 1, 10, "fixed", None), (1, 2, 5, "free", "medium"), (2, 1, 5, "free", "medium")], names=list("ABC")
    )
    s = cross_entropy(p, scale=1.0)
    assert not s.ok and "A" in s.balance_slack


def test_zero_prior_entries_stay_zero_and_signs_never_flip():
    rng = np.random.default_rng(7)
    n = 8
    ent = []
    for _ in range(40):
        r, c = rng.integers(0, n, 2)
        if r != c:
            v = float(rng.uniform(1, 100)) * (1 if rng.random() > 0.2 else -1)
            ent.append((int(r), int(c), v, "free", ["high", "medium", "low"][int(rng.integers(0, 3))]))
    ent.append((0, 1, 0.0, "free", "medium"))
    p = _problem(n, ent)
    s = cross_entropy(p, scale=1.0)
    assert s.ok, s.messages
    assert s.x[-1] == 0
    assert np.all(np.sign(s.x[:-1]) == np.sign(p.prior[:-1]))


def test_polish_is_exact_and_touches_free_entries_only():
    p = _problem(4, FOUR)
    x = _kkt_answer(FOUR, 4)
    x[0] += 0.3  # a solver-sized residual
    y, info, delta = polish(p, x)
    assert info["applied"] and info["max_imbalance_after"] <= 1e-9 and not info.get("failed")
    assert y[3] == x[3] and y[6] == x[6]  # fixed and anchored untouched
    assert delta == pytest.approx(y - x, abs=1e-12)  # the change per entry is returned (logged by run.py)


def test_constraint_membership_filters_by_refs_and_components():
    import polars as pl

    from pipeline.sam.balance import problem_from_frames

    ent = pl.DataFrame(
        {
            "row": ["C_FINS", "C_FINS", "C_FINS", "C_INSR"],
            "col": ["H_R1", "H_R1", "H_U1", "H_R1"],
            "ref": ["C4b", "C4b", "C1a", "C4b"],
            "component": ["fisim_deposits", "explicit_fees", "total", "insurance_service"],
            "value": [1.0, 2.0, 3.0, 4.0],
            "role": ["free"] * 4,
            "tol_rel": [None] * 4,
            "confidence": ["low"] * 4,
        },
        schema_overrides={"tol_rel": pl.Float64},
    )
    cons = pl.DataFrame(
        {
            "constraint_id": ["a", "b"],
            "rows": ["C_FINS,C_INSR", "C_FINS"],
            "cols": ["H_R1,H_U1", "H_R1,H_U1"],
            "refs": ["C4b", None],
            "components": ["fisim_deposits,insurance_service", None],
            "target": [5.0, 6.0],
            "tol_abs": [0.0, 0.0],
            "tol_rel": [0.0, 0.0],
        }
    )
    p = problem_from_frames(ent, cons, ["C_FINS", "C_INSR", "H_R1", "H_U1"])
    assert p.constraints[0].members.tolist() == [0, 3]
    assert p.constraints[1].members.tolist() == [0, 1, 2]


# ---------------------------------------------------------------------------------------------
# GRAS
# ---------------------------------------------------------------------------------------------


def test_gras_2x2_closed_form():
    # RAS keeps the cross-ratio: x11 x22 / (x12 x21) = (1*4)/(2*3); rows (4, 6), columns (5, 5)
    # => x11 = t with t^2 + 21 t - 40 = 0
    a = np.array([1.0, 2.0, 3.0, 4.0])
    g = gras(np.array([0, 0, 1, 1]), np.array([0, 1, 0, 1]), a, np.array([4.0, 6.0]), np.array([5.0, 5.0]))
    t = (-21 + math.sqrt(601)) / 2
    assert g.converged
    assert g.x == pytest.approx([t, 4 - t, 5 - t, 1 + t], abs=1e-7)


def test_gras_with_negative_cells_equals_the_cross_entropy_minimiser():
    """Temurshoev et al. (2013): GRAS solves min sum |a| (z ln z - z) s.t. row/column totals. Check it
    against cvxpy on a matrix with negative entries (Junius-Oosterhaven style example)."""
    import cvxpy as cp

    A = np.array([[7.0, 3.0, 5.0, -3.0, 2.0], [2.0, 9.0, 8.0, 1.0, -2.0], [-2.0, 0.0, 2.0, 1.0, 0.0],
                  [-9.0, 8.0, 0.0, 0.0, 3.0]])  # fmt: skip
    u = np.array([16.0, 20.0, 1.0, 2.0])  # prior row sums 14, 18, 1, 2
    v = np.array([-1.0, 22.0, 16.0, -1.0, 3.0])  # prior column sums -2, 20, 15, -1, 3
    r, c = np.nonzero(A)
    a = A[r, c]
    g = gras(r, c, a, u, v)
    assert g.converged
    z = cp.Variable(len(a), nonneg=True)
    x = cp.multiply(a, z)
    cons = [cp.sum(cp.multiply(x, (r == i).astype(float))) == u[i] for i in range(4)]
    cons += [cp.sum(cp.multiply(x, (c == j).astype(float))) == v[j] for j in range(5)]
    cp.Problem(cp.Minimize(cp.sum(cp.multiply(np.abs(a), -cp.entr(z) - z))), cons).solve(
        solver="CLARABEL", tol_gap_abs=1e-10, tol_gap_rel=1e-10, tol_feas=1e-10
    )
    assert g.x == pytest.approx(a * z.value, abs=1e-4)
    assert np.all(np.sign(g.x) == np.sign(a))
    assert np.bincount(r, weights=g.x) == pytest.approx(u, abs=1e-6)
    assert np.bincount(c, weights=g.x) == pytest.approx(v, abs=1e-6)


def test_gras_sam_holds_fixed_entries_and_hits_mean_targets():
    # (with FOUR itself the mean targets are infeasible for GRAS: account 3's only variable column entry
    # is negative while its target needs 0; GRAS then reports non-convergence instead of pretending)
    assert not gras_sam(_problem(4, FOUR)).converged
    rng = np.random.default_rng(11)
    ent = [(i, j, float(rng.uniform(10, 100)), "free", "medium") for i in range(5) for j in range(5) if i != j]
    ent[3] = (*ent[3][:2], 20.0, "fixed", None)
    ent[7] = (*ent[7][:2], -6.0, "free", "medium")
    ent[12] = (*ent[12][:2], -9.0, "anchored", 0.1)
    p = _problem(5, ent)
    g = gras_sam(p)
    assert g.converged, g.messages
    assert g.x[3] == 20 and g.x[7] < 0 and g.x[12] < 0
    rs, cs = p.sums(p.prior)
    rg, cg = p.sums(g.x)
    assert rg == pytest.approx((rs + cs) / 2, abs=1e-5) and cg == pytest.approx((rs + cs) / 2, abs=1e-5)


# ---------------------------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------------------------

_SCRIPT = textwrap.dedent(
    """
    import hashlib, sys
    sys.path.insert(0, "tests/sam")
    from _sam_random import random_sam
    from pipeline.sam.balance import cross_entropy, gras_sam
    out = []
    for seed, bands in ((0, 0), (1, 240)):  # realistic size: 5,000 entries, Rs 0.01 to 3e7 crore (review F5)
        p, _ = random_sam(seed, n_bands=bands)
        s = cross_entropy(p)
        assert s.ok, s.messages
        out.append(s.x.tobytes() + gras_sam(p).x.tobytes())
    print(hashlib.sha256(b"".join(out)).hexdigest())
    """
)


def test_balancing_is_identical_across_hash_seeds_and_thread_counts():
    outs = []
    for seed, threads in (("0", "1"), ("1", "1"), ("0", "4"), ("0", "OPENBLAS_NUM_THREADS")):
        extra = {"PYTHONHASHSEED": seed, ALLOW_HASHSEED_VAR: "1", REEXEC_VAR: "1"}
        if threads == "4":
            extra |= {v: threads for v in THREAD_VARS} | {ALLOW_THREADS_VAR: "1"}
        elif threads == "OPENBLAS_NUM_THREADS":  # the variable that broke determinism before (review F5)
            extra |= {"OPENBLAS_NUM_THREADS": "4", ALLOW_THREADS_VAR: "1"}
        env = pinned_environ(extra)
        env.pop(REEXEC_VAR, None)
        r = subprocess.run([sys.executable, "-c", _SCRIPT], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout.strip().splitlines()[-1])
    assert len(set(outs)) == 1, outs
    assert os.environ.get("PYTHONHASHSEED") == "0"


# ---------------------------------------------------------------------------------------------
# Wave A review (docs/phase2/verify/framework_math.md)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_realistic_size_matches_an_independent_reference(seed):
    """F1: 5,000 entries from Rs 0.01 to 3e7 crore (weights w|a| over eleven orders of magnitude), 45%
    anchored at Rs 1 crore. The answer must equal an independent solver's, entry by entry: the old
    interior-point solve inflated small entries 250x and was 4-42% off in objective while saying 'optimal'."""
    from _sam_random import objective, random_sam, reference_solution

    p, _ = random_sam(seed)
    s = cross_entropy(p)
    assert s.ok and s.certificate["ok"], s.messages
    ref = reference_solution(p)
    var = p.variable()
    assert objective(p, s.x) == pytest.approx(objective(p, ref), rel=1e-9)
    rel = np.abs(s.x - ref)[var] / np.abs(p.prior[var])
    assert rel.max() <= 1e-6, rel.max()
    small = var & (p.role == "free") & (np.abs(p.prior) < 100)
    assert np.max(s.x[small] / p.prior[small]) < 5  # no small entry blown up
    assert s.max_imbalance <= 1e-5 and s.polish.get("applied") is False


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_realistic_size_with_tight_bands_is_optimal_and_slack_free(seed):
    """F1/F2: with 240 bands of +-n crore the known 'truth' is feasible, so there must be no slack at all,
    and the certified answer can be no worse than the truth (the objective is strictly convex)."""
    from _sam_random import objective, random_sam

    p, truth = random_sam(seed, n_bands=240)
    s = cross_entropy(p)
    assert s.ok and s.certificate["ok"], s.messages
    assert s.phase1["total_slack"] == 0 and not s.band_violation and not s.anchor_violation
    assert objective(p, s.x) <= objective(p, truth) * (1 + 1e-12)


def test_a_certificate_catches_a_wrong_answer():
    """F1(b): whatever the solver, a KKT certificate decides; a perturbed optimum fails it."""
    from pipeline.sam.balance import _core, _dual_newton, kkt_certificate

    p = _problem(4, FOUR)
    core = _core(p)
    d = _dual_newton(core)
    assert d.converged and kkt_certificate(core, d.z, d.y)["ok"]
    z = d.z.copy()
    z[0] *= 1.01
    assert not kkt_certificate(core, z, d.y)["ok"]


def test_slack_appears_only_on_the_constraints_that_conflict():
    """F2: a feasible problem with tight bands has no slack; two contradictory bands get exactly the
    minimum slack (phase-1 LP), and the rest of the problem is solved exactly."""
    ent = [(0, 1, 100.0, "free", "medium"), (1, 0, 90.0, "free", "medium"), (1, 2, 50.0, "free", "high"),
           (2, 1, 50.0, "free", "low")]  # fmt: skip
    ok = [BandConstraint("tight", np.array([0]), 94.0, 95.0)]
    s = cross_entropy(_problem(3, ent, ok, list("ABC")), scale=1.0)
    assert s.ok and s.phase1["total_slack"] == 0 and not s.band_violation
    bad = [BandConstraint("floor", np.array([0]), 100.0, np.inf), BandConstraint("cap", np.array([0]), -np.inf, 90.0)]
    s = cross_entropy(_problem(3, ent, bad, list("ABC")), scale=1.0)
    assert s.ok and s.phase1["total_slack"] == pytest.approx(10.0, abs=1e-6)
    viol = sum(abs(v) for v in s.band_violation.values())
    assert viol == pytest.approx(10.0, abs=0.01)  # the minimum, placed on the conflicting pair only


def test_cvxpy_override_is_certified_and_records_the_options_used(monkeypatch):
    """F3: `--solver CLARABEL` still works (certificate-gated); a solver_error triggers the one retry at the
    solver's defaults, and the options of the accepted solve are recorded."""
    from pipeline.sam import balance

    p = _problem(4, FOUR)
    s = cross_entropy(p, solver="CLARABEL", scale=1.0)
    assert s.ok and s.solver_options == spec.SOLVER_OPTIONS["CLARABEL"], s.messages
    assert s.x == pytest.approx(cross_entropy(p, scale=1.0).x, abs=1e-3)  # interior point: ~1e-4
    real = balance._cvxpy_solve
    calls = []

    def flaky(core, solver, scale, options):
        calls.append(dict(options))
        return (
            {"status": "solver_error: synthetic", "iterations": 0, "z": None}
            if options
            else real(core, solver, scale, options)
        )

    monkeypatch.setattr(balance, "_cvxpy_solve", flaky)
    s = cross_entropy(p, solver="CLARABEL", scale=1.0)
    assert calls == [spec.SOLVER_OPTIONS["CLARABEL"], {}] and s.solver_options == {}
    assert any("solver_error" in m for m in s.messages)
    # at Clarabel's default tolerances the answer is too rough for the certificate: the run fails, loudly
    assert s.status == "optimal" and s.ok is bool(s.certificate["ok"])
    assert s.ok or any("KKT certificate FAILED" in m for m in s.messages)


def test_polish_refuses_to_flip_a_sign_and_to_hide_a_bad_solve():
    """F6: the only free path A -> C -> B carries 0.02 crore; a 0.07 crore residual would drive it negative:
    refused (the run fails). A residual above POLISH_MAX means the solve is wrong: refused too."""
    ent = [(0, 1, 1000.0, "anchored", 1e-3), (1, 0, 1000.0, "anchored", 1e-3), (0, 2, 0.02, "free", "low"),
           (2, 1, 0.02, "free", "low")]  # fmt: skip
    p = _problem(3, ent, names=list("ABC"))
    x = np.array([1000.0, 999.95, 0.02, 0.02])  # A is 0.07 over: A <- C must fall by 0.07
    y, info, delta = polish(p, x)
    assert info["sign_flips"] > 0 and "flip" in info["failed"] and np.all(y == x) and not delta.any()
    y, info, _ = polish(p, np.array([1000.0, 1003.0, 0.02, 0.02]))
    assert "POLISH_MAX" in info["failed"]


@pytest.mark.parametrize("miss,ok", [(0.1075, False), (0.005, True), (0.0005, True)])
def test_fixed_only_account_within_the_balance_tolerance_passes(miss, ok):
    """F7: an X_DISC-like account whose entries are all fixed: a miss within BALANCE_TOL is accepted and
    reported; a larger one fails and names the account (known exactly, without a solve)."""
    ent = [(0, 1, 2e6, "free", "medium"), (1, 0, 2e6, "free", "medium"), (2, 0, 50_000.0, "fixed", None),
           (1, 2, 30_000.0, "fixed", None), (0, 2, 20_000.0 - miss, "fixed", None), (3, 1, 7e6, "free", "low"),
           (1, 3, 7e6, "free", "high")]  # fmt: skip
    s = cross_entropy(_problem(4, ent, names=["A", "B", "X_DISC", "D"]))
    assert s.ok is ok, s.messages
    # the miss shows at X_DISC (+) and, with the opposite sign, in the component of A, B, D (reported at A)
    if ok:
        assert s.fixed_residuals == {"X_DISC": pytest.approx(miss, abs=1e-9), "A": pytest.approx(-miss, abs=1e-6)}
        assert s.max_imbalance == pytest.approx(miss, abs=1e-6)
    else:
        assert s.balance_slack == {"X_DISC": pytest.approx(miss), "A": pytest.approx(-miss, abs=1e-6)}
        assert s.status == "infeasible" and any("X_DISC" in m for m in s.messages)


def test_infeasibility_diagnosis_names_the_sign_locked_account():
    """F8: only D cannot close (fixed receipts 2e4, fixed payments 1e4, its only variable entry is a
    receipt). The exact sign test names D and nothing else as a cause."""
    ent = [(0, 1, 5e6, "free", "medium"), (1, 0, 4.9e6, "free", "medium"), (1, 2, 3e5, "free", "high"),
           (2, 1, 2.9e5, "free", "low"), (3, 2, 2e4, "fixed", None), (0, 3, 1e4, "fixed", None),
           (3, 0, 3e3, "free", "medium")]  # fmt: skip
    s = cross_entropy(_problem(4, ent, names=list("ABCD")))
    assert not s.ok and s.status == "infeasible"
    causes = [m for m in s.messages if "cannot close" in m]
    assert len(causes) == 1 and causes[0].startswith("account D"), s.messages
    assert "D" in s.balance_slack


def test_binding_uses_a_tolerance_tied_to_the_band_width():
    """F10: a +-1 crore band on a Rs 69 lakh crore total with the sum 0.6 crore inside is not binding."""
    from pipeline.sam.balance import binding

    t = 6_916_804.0
    p = _problem(2, [(0, 1, t, "free", "medium"), (1, 0, t, "free", "medium")],
                 [BandConstraint("c", np.array([0]), t - 1, t + 1)], ["A", "B"])  # fmt: skip
    assert binding(p, np.array([t + 0.4, t + 0.4])) == []
    assert binding(p, np.array([t + 1.0, t + 1.0])) == ["c"]


def test_gras_reports_the_flags_of_its_last_iteration():
    """F11: a non-converged GRAS says why from its last iteration (not only the first)."""
    g = gras_sam(_problem(4, FOUR))
    assert not g.converged and any(m.startswith("last iteration") for m in g.messages), g.messages


# ---------------------------------------------------------------------------------------------
# Wave B solver review (docs/phase2/verify/solver_newton.md)
# ---------------------------------------------------------------------------------------------


def _narrow_band(seed, k, mode):
    """A band over k anchored entries (Rs 1 crore boxes) that meets their boxes only in their top 0.0005
    crore ('sliver', feasible), or lies 20 crore above them ('conflict': phase 1 widens one side by the slack
    + 0.001 crore, which leaves a 0.001 crore window)."""
    from _sam_random import random_sam

    p, _ = random_sam(seed, n=40, m=600)
    es = np.flatnonzero((p.role == "anchored") & (np.abs(p.prior) > 1e4))[:k]
    top = float(sum(max(p.prior[e] * (1 - p.tol_rel[e]), p.prior[e] * (1 + p.tol_rel[e])) for e in es))
    lo, hi = (top - 5e-4, top + 50.0) if mode == "sliver" else (top + 20.0, top + 21.0)
    p.constraints = [BandConstraint("win", es, lo, hi)]
    return p


def _narrow_account(seed, mode):
    """A new account X whose only movable entries are anchored (X <- a1 = p1 +- 1, a2 <- X = p2 +- 1) and a
    fixed payment f: balance p1 z1 = p2 z2 + f leaves a 0.0005 crore window ('sliver'), or is 20 crore
    short ('conflict', widened by phase 1 to a 0.001 crore window)."""
    from _sam_random import random_sam

    p, _ = random_sam(seed, n=40, m=600)
    n = p.n_accounts
    rng = np.random.default_rng(seed)
    a1, a2 = (int(v) for v in rng.choice(n, 2, replace=False))
    p1 = float(np.round(rng.uniform(1e4, 1e6)))
    p2 = float(np.round(p1 * 0.5))
    f = (p1 + 1.0) - (p2 - 1.0) + (-5e-4 if mode == "sliver" else 20.0)
    anch = spec.entry_weight("anchored", None)
    return Problem(
        n + 1, np.r_[p.row, n, a2, a2], np.r_[p.col, a1, n, n], np.r_[p.prior, p1, p2, f],
        np.r_[p.role, np.array(["anchored", "anchored", "fixed"], dtype=object)].astype(object),
        np.r_[p.tol_rel, 1.0 / p1, 1.0 / p2, np.nan], np.r_[p.weight, anch, anch, spec.entry_weight("fixed", None)],
        [], [*p.account_names, "X"],
    )  # fmt: skip


@pytest.mark.parametrize("mode", ["sliver", "conflict"])
@pytest.mark.parametrize("case", ["band1", "band2", "band3", "account"])
@pytest.mark.parametrize("seed", [1, 2])  # before the fix 10 of these 16 failed, 4 needed the proximal path
def test_narrow_windows_against_anchored_boxes_converge(seed, case, mode):
    """S-1 (major): a dual coordinate whose members are all clipped at their anchored boxes got only
    BOUND_CURVATURE curvature in the Newton system: the step overshot (a band multiplier went to -143) and then
    crawled back 0.01 per step, and the run failed after 3,900 steps. Bands over one to three anchored entries
    and an account whose movable entries are all anchored failed alike, feasible or after phase-1 widening.
    Now each such coordinate is first maximised exactly: certified in a few Newton steps, and a conflict gets
    exactly its minimum slack (20 crore, reported with the 0.001 crore margin)."""
    p = _narrow_account(seed, mode) if case == "account" else _narrow_band(seed, int(case[-1]), mode)
    s = cross_entropy(p)
    assert s.ok and s.certificate["ok"], s.messages
    assert s.iterations < 100 and s.solver_options["path"] == "direct", (s.iterations, s.solver_options)
    if mode == "sliver":
        assert s.phase1["total_slack"] == 0 and not s.band_violation and not s.anchor_violation
    else:
        assert s.phase1["total_slack"] == pytest.approx(20.0, abs=1e-6)
        reported = sum(abs(v) for v in s.band_violation.values()) + sum(abs(v) for v in s.anchor_violation.values())
        assert 20.0 - 1e-6 <= reported <= 20.0 + 2 * spec.WIDEN_MARGIN


def test_a_constraint_over_fixed_entries_only_is_reported_at_the_pre_check():
    """S-6: a band over entries none of which can move is violated (or not) exactly, without a solve: it is
    named in the messages, counted in phase 1's total slack and reported as slack; the rest is solved."""
    ent = [(0, 1, 100.0, "free", "medium"), (1, 0, 90.0, "free", "medium"), (0, 2, 10.0, "fixed", None),
           (2, 0, 10.0, "fixed", None)]  # fmt: skip
    s = cross_entropy(_problem(3, ent, [BandConstraint("fx", np.array([2]), 13.0, 14.0)], list("ABC")), scale=1.0)
    assert s.ok and s.band_violation == {"fx": pytest.approx(-3.0)}
    assert s.phase1["fixed_only_bands"] == {"fx": pytest.approx(-3.0)}
    assert s.phase1["total_slack"] == pytest.approx(3.0)
    assert any(m.startswith("constraint fx: none of its 1 entries can move") for m in s.messages), s.messages


def test_an_entry_forced_to_zero_fails_the_run_and_is_named():
    """S-4: C's fixed receipts and payments already match, so its free receipt C <- B must be 0: the optimum is
    on the boundary z = 0, where no dual optimum exists. Newton now closes the duality gap there too (S-2),
    so the certificate refuses such an entry explicitly when it is material (prior >= Rs 1 crore), and the
    message names it and says why; an immaterial one is accepted and listed."""
    ent = [(0, 1, 100.0, "free", "medium"), (1, 0, 100.0, "free", "medium"), (2, 0, 100.0, "fixed", None),
           (0, 2, 100.0, "fixed", None), (2, 1, 5.0, "free", "low")]  # fmt: skip
    s = cross_entropy(_problem(3, ent, names=list("ABC")), scale=1.0)
    assert not s.ok and s.status == "optimal" and s.certificate["entries_forced_to_zero"] == 1
    msg = next(m for m in s.messages if m.startswith("KKT certificate FAILED"))
    assert "entry 4 (C <- B, prior 5)" in msg and "structural zero" in msg
    # below the material-change threshold (Rs 1 crore) the forced zero is accepted, and listed
    s = cross_entropy(_problem(3, [*ent[:4], (2, 1, 0.5, "free", "low")], names=list("ABC")), scale=1.0)
    assert s.ok and s.certificate["immaterial_entries_forced_to_zero"] == 1 and abs(s.x[4]) < 1e-6
    assert any("entry 4 (C <- B, prior 0.5)" in m and "immaterial" in m for m in s.messages), s.messages


def test_polish_holds_the_constraints_at_a_bound():
    """S-5: the polish closes the accounts without moving a band that sits at its bound (it used to push
    binding bands out by up to its own size, which was then reported as slack); a band it would push out
    of its interval is held too."""
    x = _kkt_answer(FOUR, 4)
    band = BandConstraint("b02", np.array([0, 2]), -np.inf, float(x[0] + x[2]))  # binding at its cap
    p = _problem(4, FOUR, [band], list("ABCD"))
    x = x.copy()
    x[1] += 0.3  # a solver-sized residual outside the band
    y, info, delta = polish(p, x)
    assert info["applied"] and not info.get("failed") and info["max_imbalance_after"] <= 1e-9
    assert info["bands_held"] == ["b02"] and not info["band_moves"]
    assert y[0] + y[2] == pytest.approx(x[0] + x[2], abs=1e-12)
    assert np.any(np.abs(delta[[0, 2]]) > 1e-6)  # its members still move, against each other
    y0, _, _ = polish(_problem(4, FOUR, names=list("ABCD")), x)  # without the band: the sum would move
    assert abs((y0[0] + y0[2]) - (x[0] + x[2])) > 1e-3


def test_a_flat_dual_value_does_not_stall_the_line_search():
    """WB-8: near the optimum the dual value changes only by rounding, so the line search judges steps by the
    scaled residual. A full step that cut it from 10.3 to 5.9 was refused (the old rule wanted it halved); the
    damping then grew to its cap and Newton stalled at merit 10, needing the proximal fallback and 3,403 steps.
    The verifier's generator: 3,000 entries, 300 bands of +-n crore."""
    sys.path.insert(0, str(REPO_ROOT / "tests" / "verify"))
    from test_sam_solver_certificate import gen

    p, _ = gen(0, n=128, m=3000, n_bands=300)
    s = cross_entropy(p)
    assert s.ok and s.solver_options["path"] == "direct" and s.iterations < 100, (s.iterations, s.messages)


# ---------------------------------------------------------------------------------------------
# Wave C (the first full balancing run failed: dual Newton not_converged after 2,220 steps; BALANCING.md)
# ---------------------------------------------------------------------------------------------


def test_a_zero_multiplier_whose_step_points_the_wrong_way_is_held():
    """The projected Newton step held a multiplier at 0 when its step crossed zero from a non-zero value, but not
    one that was already 0: the line search's projection then kept it at 0 while every other coordinate moved as
    if it had moved. On the real SAM a violated GFCF band (capital_financial:cf.i1a.gfcf.fc_private) sat at mu = 0
    and the method stalled for 2,220 steps. The verifier's generator problem below needed the proximal fallback
    and 177 steps before the fix; now it converges directly."""
    sys.path.insert(0, str(REPO_ROOT / "tests" / "verify"))
    from test_sam_solver_certificate import gen

    p, _ = gen(2, n=128, m=3000, n_bands=300)
    s = cross_entropy(p)
    assert s.ok and s.solver_options["path"] == "direct" and s.iterations < 100, (s.iterations, s.messages)


def _force_fallback(monkeypatch):
    from pipeline.sam import balance

    monkeypatch.setattr(balance, "NEWTON_FIRST_TRY", 1)  # one direct step, then the interior-point fallback


@pytest.mark.parametrize("case", ["bands0", "bands1", "bands2", "sliver", "conflict", "account"])
def test_the_interior_point_fallback_reaches_the_same_certified_optimum(case, monkeypatch):
    """DECISIONS D2-23: the interior-point fallback (log-barrier path on the dual, then the exact dual Newton method
    from its multipliers) must
    return the same certified optimum as the direct path, entry by entry, on realistic problems with 240 bands,
    and on narrow windows created by a sliver or by phase-1 widening (a conflict)."""
    from _sam_random import objective, random_sam

    if case.startswith("bands"):
        p, _ = random_sam(int(case[-1]), n_bands=240)
    elif case == "account":
        p = _narrow_account(1, "conflict")
    else:
        p = _narrow_band(2, 3, case)
    direct = cross_entropy(p)
    assert direct.ok and direct.solver_options["path"] == "direct", direct.messages
    _force_fallback(monkeypatch)
    s = cross_entropy(p)
    assert s.ok and s.certificate["ok"], s.messages
    assert s.solver_options["path"] == "interior-point fallback", s.messages
    assert any("interior point (log-barrier path on the dual)" in m for m in s.messages), s.messages
    var = p.variable()
    rel = np.abs(s.x - direct.x)[var] / np.abs(p.prior[var])
    assert rel.max() <= 1e-6, rel.max()
    assert objective(p, s.x) == pytest.approx(objective(p, direct.x), rel=1e-9)
    assert s.phase1 == direct.phase1


def test_a_boundary_optimum_still_fails_loudly_on_the_fallback(monkeypatch):
    """The fallback does not weaken the S-4 rule: an entry the constraints force to zero (a Rs 5 crore prior)
    fails the run by name on the interior-point path too."""
    ent = [(0, 1, 100.0, "free", "medium"), (1, 0, 100.0, "free", "medium"), (0, 2, 5.0, "free", "medium"),
           (2, 0, 5.0, "free", "medium")]  # fmt: skip
    p = _problem(3, ent, [BandConstraint("cap", np.array([2]), -np.inf, 0.0)], list("ABC"))
    _force_fallback(monkeypatch)
    s = cross_entropy(p)
    assert not s.ok
    assert s.certificate.get("entries_forced_to_zero", 0) >= 1 or s.status == "not_converged", s.certificate
    assert any("A <- C" in m for m in s.messages), s.messages


def _real_problem():
    """The problem the full `sam` run balances, assembled from the current block outputs (skip unless all nine
    DESIGN_BRIEF blocks are built and assemble)."""
    from pipeline.core.paths import Layout
    from pipeline.sam.accounts import EXPECTED_BLOCKS, Accounts
    from pipeline.sam.assemble import assemble
    from pipeline.sam.balance import problem_from_frames
    from pipeline.sam.framework import SamError, SamPaths

    paths = SamPaths(Layout.default())
    missing = [b for b in EXPECTED_BLOCKS if not paths.built(b)]
    if missing:
        pytest.skip(f"blocks not built: {missing}")
    acc = Accounts.load()
    try:
        asm = assemble(paths, EXPECTED_BLOCKS, acc)
    except SamError as e:
        pytest.skip(f"the block outputs do not assemble (a block is being rebuilt?): {str(e)[:300]}")
    return problem_from_frames(asm.entries, asm.constraints, acc.codes), asm.entries


@pytest.mark.parametrize("z_factor", [1.0, 0.5, 2.0])
def test_the_real_prior_balances_or_fails_for_a_named_data_reason(z_factor):
    """The real SAM (and variants with the household saving gap Z halved and doubled, since block owners are
    repairing the prior): the solver must never end `not_converged`. It certifies an optimum, or fails for a
    reason in the data that it names: infeasible balance (a sign lock) or an entry the constraints force to zero.
    Before Wave C the real prior ended not_converged after 2,220 steps (max imbalance 6.68 crore, 146
    non-complementary bands). Z is changed by scaling the positive household saving entries (K_HH <- H_*, K4a)."""
    p, ent = _real_problem()
    if z_factor != 1.0:
        rows = np.array(ent["row"].to_list(), dtype=object)
        cols = np.array(ent["col"].to_list(), dtype=object)
        refs = np.array(ent["ref"].to_list(), dtype=object)
        z = float(p.prior[rows == "K_HH"].sum() - p.prior[cols == "K_HH"].sum())
        sel = (rows == "K_HH") & (refs == "K4a") & (p.prior > 0)
        assert sel.any()
        p.prior = p.prior.copy()
        p.prior[sel] *= 1.0 + (z_factor - 1.0) * z / p.prior[sel].sum()
    s = cross_entropy(p)
    assert s.status != "not_converged", s.messages
    if s.status == "optimal" and not s.ok:
        assert s.certificate.get("entries_forced_to_zero", 0) > 0, (s.certificate, s.messages)
    if s.ok:
        assert s.max_imbalance <= spec.BALANCE_TOL and s.certificate["ok"]
