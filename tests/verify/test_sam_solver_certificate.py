"""Independent re-verification of the SAM balancing solver (DECISIONS D2-1; wave B).

Report: docs/phase2/verify/solver_newton.md. The solver under test is `pipeline.sam.balance.cross_entropy`
(the framework's dual Newton method with its interior-point and proximal fallbacks, phase-1 LP, polish) and
`gras`.

What is independent here (written by the verifier, not taken from balance.py):
- `_certificate`: a KKT certificate that recovers the multipliers itself (least squares over the entries
  strictly inside their bounds, only for bands found active), then checks primal feasibility (exact account
  balance of *every* account, anchored boxes, bands, fixed entries unchanged, no sign flip), stationarity
  ln z_e + s_e (lambda_row - lambda_col + sum_k mu_k) / w_e = 0, the sign condition at box bounds, the sign
  of each band multiplier against the side it sits on, and the duality gap from its own evaluation of the
  dual function (a lower bound on the optimum for any multipliers, so a small gap proves optimality);
- `_clarabel`: an independent primal formulation solved by cvxpy + Clarabel at tight tolerances, used only
  on small problems with a narrow value range (where an interior-point method is reliable);
- `_min_slack_lp`: an independent phase-1 LP (cvxpy + HiGHS) for the minimum total slack;
- the weighted-least-squares polish step and a GRAS reference, solved directly.
The random generator reuses the tests' truth balancer (`tests/sam/_sam_random._balance_truth`) only to
construct feasible problems.

Confirmed defects were strict xfails, removed when fixed (Wave B disposition by the framework owner,
docs/phase2/FRAMEWORK_REQUESTS.md "Wave B solver review"): a single-entry band whose feasible window against
its entry's anchored box is narrow (<= WIDEN_MARGIN, which phase 1 itself creates when such a band conflicts
with the box) made the method fail to converge (S-1); the Newton stopping rule could stop at a point its own
certificate rejects (S-2); phase-1 slack at or below LP_ZERO was neither widened nor tolerated (S-3). The
polish reference below holds the bands the polish reports as held (S-5 fix), and the proximal-path
determinism problem was re-chosen because the S-1 fix solves the original one directly (see its docstring).
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import numpy as np
import pytest
import scipy.sparse as sp

from pipeline.core.env import ALLOW_HASHSEED_VAR, ALLOW_THREADS_VAR, REEXEC_VAR, THREAD_VARS, pinned_environ
from pipeline.core.paths import REPO_ROOT
from pipeline.sam import spec
from pipeline.sam.balance import BandConstraint as BC
from pipeline.sam.balance import Problem, cross_entropy, gras, polish

pytestmark = [pytest.mark.quality, pytest.mark.sam, pytest.mark.filterwarnings("ignore:Solution may be inaccurate")]

sys.path.insert(0, str(REPO_ROOT / "tests" / "sam"))

INF = np.inf


# ---------------------------------------------------------------------------------------------
# generator (SAM-shaped: 0.01..3e7 crore, ~5% negative, fixed / anchored at n crore per cell or 2% /
# loose anchored / free with mixed confidence, diagonal entries, nested, one-sided, duplicate, single-entry,
# cross-account and near-equality bands around a known feasible 'truth')
# ---------------------------------------------------------------------------------------------


def gen(seed, *, n=128, m=6000, noise=0.08, n_bands=300, tight=1.0, vmin=0.01, vmax=3e7):
    from _sam_random import _balance_truth

    from pipeline.sam.balance import single_threaded_blas

    rng = np.random.default_rng(seed)
    pairs = set()
    for i in range(n):
        pairs.add((i, (i + 1) % n))
        pairs.add(((i + 1) % n, i))
    for i in rng.choice(n, min(10, n // 4), replace=False):
        pairs.add((int(i), int(i)))
    m = min(m, int(0.7 * n * (n - 1)))
    while len(pairs) < m:
        r, c = rng.integers(0, n, 2)
        if r != c:
            pairs.add((int(r), int(c)))
    pl_ = sorted(pairs)
    row = np.array([q[0] for q in pl_])
    col = np.array([q[1] for q in pl_])
    m = len(pl_)
    base = np.exp(rng.uniform(np.log(vmin), np.log(vmax), m)) * np.where(rng.random(m) < 0.05, -1.0, 1.0)
    ring = np.array([abs(r - c) in (1, n - 1) for r, c in pl_])
    base[ring] = np.abs(base[ring]) + (1e5 if vmax > 1e6 else vmax)
    with single_threaded_blas():
        truth = _balance_truth(n, row, col, base)
    k = rng.random(m)
    role = np.where(k < 0.10, "fixed", np.where(k < 0.55, "anchored", "free")).astype(object)
    role[ring] = "free"
    conf = np.array([["high", "medium", "low"][i] for i in rng.integers(0, 3, m)], dtype=object)
    prior = truth.copy()
    fr = role == "free"
    prior[fr] = truth[fr] * np.exp(rng.normal(0, noise, int(fr.sum())))
    an = role == "anchored"
    ncell = rng.integers(1, 6, m).astype(float)
    prior[an] = np.round(truth[an])
    prior[an & (prior == 0)] = np.sign(truth[an & (prior == 0)])
    tol = np.where(an, ncell / np.maximum(np.abs(prior), 1e-12), np.nan)
    sel = an & (rng.random(m) < 0.1)
    prior[sel] = truth[sel] * np.exp(rng.normal(0, 0.01, int(sel.sum())))
    tol[sel] = 0.02
    tol[an & (rng.random(m) < 0.02)] = 1.5
    prior = np.round(prior, 6)
    prior[role == "fixed"] = np.round(truth[role == "fixed"], 6)
    w = np.array([spec.entry_weight(r_, c_ if r_ == "free" else None) for r_, c_ in zip(role, conf)])
    bands: list[BC] = []

    def add(mem, lo, hi, tag):
        bands.append(BC(f"{tag}{len(bands)}", np.array(sorted({int(v) for v in mem})), lo, hi))

    def tsum(mem):
        return float(np.sum(truth[mem]))

    while len(bands) < n_bands:
        kind = rng.random()
        acct = int(rng.integers(0, n))
        if kind < 0.45:
            mem = np.flatnonzero(row == acct)
            mem = mem[rng.random(len(mem)) < 0.6]
            if not len(mem):
                continue
            t, tl = tsum(mem), tight * len(mem)
            add(mem, t - tl, t + tl, "row")
            if len(mem) > 3 and rng.random() < 0.5:
                sub = mem[rng.random(len(mem)) < 0.5]
                if len(sub):
                    t2 = tsum(sub)
                    add(sub, t2 - 0.5 * tight * len(sub), t2 + 0.5 * tight * len(sub), "nest")
        elif kind < 0.6:
            mem = np.flatnonzero(col == acct)
            mem = mem[rng.random(len(mem)) < 0.5]
            if not len(mem):
                continue
            t = tsum(mem)
            if rng.random() < 0.5:
                add(mem, t - rng.choice([0.0, 1.0, 100.0]), INF, "min")
            else:
                add(mem, -INF, t + rng.choice([0.0, 1.0, 100.0]), "max")
        elif kind < 0.75:
            mem = rng.choice(m, int(rng.integers(2, 40)), replace=False)
            t = tsum(mem)
            tl = max(1.0, 1e-4 * abs(t))
            add(mem, t - tl, t + tl, "x")
        elif kind < 0.82 and bands:
            b0 = bands[int(rng.integers(0, len(bands)))]
            add(b0.members, b0.lo - 5 if np.isfinite(b0.lo) else -INF, b0.hi + 5 if np.isfinite(b0.hi) else INF, "dup")
        elif kind < 0.88:
            e = int(rng.integers(0, m))
            add([e], truth[e] - 0.5, truth[e] + 0.5, "one")
        else:
            mem = np.flatnonzero(col == acct)
            mem = mem[rng.random(len(mem)) < 0.3]
            if not len(mem):
                continue
            t = tsum(mem)
            add(mem, t - 0.01, t + 0.01, "eq")
    return Problem(n, row, col, prior, role, tol, w, bands, [f"A{i}" for i in range(n)]), truth


def mk(n, ent, bands=()):
    row = np.array([e[0] for e in ent])
    col = np.array([e[1] for e in ent])
    prior = np.array([float(e[2]) for e in ent])
    role = np.array([e[3] for e in ent], dtype=object)
    tol = np.array([e[4] if e[3] == "anchored" else np.nan for e in ent], dtype=float)
    w = np.array([spec.entry_weight(e[3], e[4] if e[3] == "free" else None) for e in ent])
    return Problem(n, row, col, prior, role, tol, w, list(bands), [chr(65 + i) for i in range(n)])


# ---------------------------------------------------------------------------------------------
# independent certificate, reference solvers
# ---------------------------------------------------------------------------------------------


def _zbounds(p, var):
    lo = np.zeros(len(var))
    hi = np.full(len(var), INF)
    an = p.role[var] == "anchored"
    t = p.tol_rel[var]
    lo[an] = np.maximum(0.0, 1 - t[an])
    hi[an] = 1 + t[an]
    return lo, hi


def _objective(p, x):
    var = np.flatnonzero(p.variable())
    a = p.prior[var]
    z = x[var] / a
    c = p.weight[var] * np.abs(a)
    with np.errstate(divide="ignore", invalid="ignore"):
        zl = np.where(z > 0, z * np.log(z), 0.0)
    return float(np.sum(c * (zl - z + 1)))


def _certificate(p, x, *, zlo=None, zhi=None, blo=None, bhi=None, band_tol=1e-4):
    n = p.n_accounts
    var = np.flatnonzero(p.variable())
    nv = len(var)
    a = p.prior[var]
    s = np.sign(a)
    w = p.weight[var]
    c = w * np.abs(a)
    z = x[var] / a
    lo0, hi0 = _zbounds(p, var)
    zlo = lo0 if zlo is None else zlo
    zhi = hi0 if zhi is None else zhi
    blo = np.array([k.lo for k in p.constraints]) if blo is None else blo
    bhi = np.array([k.hi for k in p.constraints]) if bhi is None else bhi
    const = np.where(p.variable(), 0.0, p.prior)
    out = {
        "fixed_changed": int(np.sum(x[~p.variable()] != p.prior[~p.variable()])),
        "sign_flips": int(np.sum(z < 0)),
        "max_imbalance": float(np.max(np.abs(p.residual(x)))),
        "box_violation": float(np.max(np.maximum(zlo - z, z - zhi) * np.abs(a), initial=0.0)),
    }
    bsum = np.array([float(np.sum(x[k.members])) for k in p.constraints])
    out["band_violation"] = float(np.max(np.maximum(bsum - bhi, blo - bsum), initial=0.0))
    at_hi_b = np.isfinite(bhi) & (bsum >= bhi - band_tol)
    at_lo_b = np.isfinite(blo) & (bsum <= blo + band_tol)
    act = np.flatnonzero(at_hi_b | at_lo_b)
    pos = -np.ones(len(p.prior), dtype=int)
    pos[var] = np.arange(nv)
    with np.errstate(divide="ignore"):
        lnz = np.log(z)
    at_hi = np.isfinite(zhi) & (z >= zhi * (1 - 1e-12))
    at_lo = (zlo > 0) & (z <= zlo * (1 + 1e-12))
    inside = ~at_hi & ~at_lo & (z > 0)
    ri, ci = p.row[var], p.col[var]
    off = ri != ci
    e_idx = np.arange(nv)
    rows, cols, vals = [e_idx[off], e_idx[off]], [ri[off], ci[off]], [(s / w)[off], (-s / w)[off]]
    for j, k in enumerate(act):
        mv = pos[p.constraints[k].members]
        mv = mv[mv >= 0]
        rows.append(mv)
        cols.append(np.full(len(mv), n + j))
        vals.append((s / w)[mv])
    A = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(nv, n + len(act)))
    sol = np.linalg.lstsq(A[inside].toarray(), -lnz[inside], rcond=None)[0]
    lam = sol[:n]
    mu = np.zeros(len(p.constraints))
    mu[act] = sol[n:]
    r = lnz + A @ sol
    out["stationarity"] = float(np.max(np.abs(r[inside]), initial=0.0))
    out["sign_upper"] = float(np.max(r[at_hi], initial=0.0))
    out["sign_lower"] = float(np.max(-r[at_lo], initial=0.0))
    out["wrong_sign_multipliers"] = [
        p.constraints[k].constraint_id
        for k in act
        if (mu[k] > 1e-7 and not at_hi_b[k]) or (mu[k] < -1e-7 and not at_lo_b[k])
    ]
    # own dual function: q(lam, mu) = sum_e min_{z in box} [c phi(z) + t_e z] + lam.b - sigma(mu) <= optimum
    mu[(mu > 0) & ~np.isfinite(bhi)] = 0.0
    mu[(mu < 0) & ~np.isfinite(blo)] = 0.0
    b = np.bincount(p.row, weights=const, minlength=n) - np.bincount(p.col, weights=const, minlength=n)
    band_fix = np.array([float(np.sum(const[k.members])) for k in p.constraints])
    t = np.zeros(nv)
    t[off] += a[off] * (lam[ri[off]] - lam[ci[off]])
    for k in np.flatnonzero(mu != 0):
        mv = pos[p.constraints[k].members]
        mv = mv[mv >= 0]
        t[mv] += a[mv] * mu[k]
    zs = np.clip(np.exp(np.clip(-t / c, -700, 700)), zlo, zhi)
    with np.errstate(divide="ignore", invalid="ignore"):
        phi = np.where(zs > 0, zs * np.log(zs), 0.0) - zs + 1
        sig = np.where(mu > 0, mu * (bhi - band_fix), np.where(mu < 0, mu * (blo - band_fix), 0.0))
    q = float(np.sum(c * phi + t * zs)) + float(np.sum(lam * b)) - float(np.sum(sig))
    f = _objective(p, x)
    out["gap_rel"] = (f - q) / max(1.0, abs(f))
    return out


def _certified(cr, *, stat=1e-6, gap=1e-8):
    bad = {
        k: v
        for k, v in cr.items()
        if (k in ("fixed_changed", "sign_flips") and v)
        or (k == "max_imbalance" and v > spec.BALANCE_TOL)
        or (k == "box_violation" and v > 1e-5)
        or (k == "band_violation" and v > 1e-4)
        or (k in ("stationarity", "sign_upper", "sign_lower") and v > stat)
        or (k == "wrong_sign_multipliers" and v)
        or (k == "gap_rel" and abs(v) > gap)
    }
    return not bad, bad


def _mats(p):
    from scipy.sparse.csgraph import connected_components

    n = p.n_accounts
    var = np.flatnonzero(p.variable())
    a = p.prior[var]
    const = np.where(p.variable(), 0.0, p.prior)
    b = np.bincount(p.row, weights=const, minlength=n) - np.bincount(p.col, weights=const, minlength=n)
    ri, ci = p.row[var], p.col[var]
    off = np.flatnonzero(ri != ci)
    E = sp.csr_matrix(
        (np.concatenate([a[off], -a[off]]), (np.concatenate([ri[off], ci[off]]), np.concatenate([off, off]))),
        shape=(n, len(var)),
    )
    _, lab = connected_components(sp.csr_matrix((np.ones(len(off)), (ri[off], ci[off])), shape=(n, n)), directed=False)
    keep = np.ones(n, bool)
    for k in range(int(lab.max()) + 1):
        keep[np.flatnonzero(lab == k)[0]] = False
    pos = -np.ones(len(p.prior), int)
    pos[var] = np.arange(len(var))
    B = np.zeros((len(p.constraints), len(var)))
    blo, bhi = [], []
    for j, k in enumerate(p.constraints):
        mv = pos[k.members]
        mv = mv[mv >= 0]
        np.add.at(B[j], mv, a[mv])
        fs = float(np.sum(const[k.members]))
        blo.append(k.lo - fs)
        bhi.append(k.hi - fs)
    return var, a, E[keep], -b[keep], B, np.array(blo), np.array(bhi)


def _clarabel(p):
    import cvxpy as cp

    var, a, E, rhs, B, blo, bhi = _mats(p)
    zlo, zhi = _zbounds(p, var)
    z = cp.Variable(len(var), nonneg=True)
    cons = [E @ z == rhs]
    fin = np.isfinite(zhi)
    if fin.any():
        cons += [z[fin] <= zhi[fin], z[fin] >= zlo[fin]]
    if np.isfinite(bhi).any():
        cons.append(B[np.isfinite(bhi)] @ z <= bhi[np.isfinite(bhi)])
    if np.isfinite(blo).any():
        cons.append(B[np.isfinite(blo)] @ z >= blo[np.isfinite(blo)])
    c = p.weight[var] * np.abs(a)
    prob = cp.Problem(cp.Minimize(cp.sum(cp.multiply(c, -cp.entr(z) - z + 1))), cons)
    prob.solve(solver="CLARABEL", tol_gap_abs=1e-12, tol_gap_rel=1e-12, tol_feas=1e-12)
    x = p.prior.copy()
    x[var] = a * np.maximum(z.value, 0.0)
    return x, prob.status


def _min_slack_lp(p):
    import cvxpy as cp

    n = p.n_accounts
    var = np.flatnonzero(p.variable())
    a = p.prior[var]
    const = np.where(p.variable(), 0.0, p.prior)
    x = cp.Variable(len(var))
    ri, ci = p.row[var], p.col[var]
    M = sp.csr_matrix(
        (
            np.r_[np.ones(len(var)), -np.ones(len(var))],
            (np.r_[ri, ci], np.r_[np.arange(len(var)), np.arange(len(var))]),
        ),
        shape=(n, len(var)),
    )
    b = np.bincount(p.row, weights=const, minlength=n) - np.bincount(p.col, weights=const, minlength=n)
    cons = [M @ x + b == 0, x[np.flatnonzero(a > 0)] >= 0, x[np.flatnonzero(a < 0)] <= 0]
    an = np.flatnonzero(p.role[var] == "anchored")
    t = p.tol_rel[var][an]
    lo = np.minimum(a[an] * (1 - t), a[an] * (1 + t))
    hi = np.maximum(a[an] * (1 - t), a[an] * (1 + t))
    lo = np.where(a[an] > 0, np.maximum(lo, 0), lo)
    hi = np.where(a[an] < 0, np.minimum(hi, 0), hi)
    sa, sb = cp.Variable(len(an), nonneg=True), cp.Variable(len(an), nonneg=True)
    cons += [x[an] <= hi + sa, x[an] >= lo - sb]
    obj = cp.sum(sa) + cp.sum(sb)
    pos = -np.ones(len(p.prior), int)
    pos[var] = np.arange(len(var))
    for k in p.constraints:
        mv = pos[k.members]
        mv = mv[mv >= 0]
        if not len(mv):
            continue
        ssum = cp.sum(x[mv]) + float(np.sum(const[k.members]))
        if np.isfinite(k.hi):
            s1 = cp.Variable(nonneg=True)
            cons.append(ssum <= k.hi + s1)
            obj = obj + s1
        if np.isfinite(k.lo):
            s2 = cp.Variable(nonneg=True)
            cons.append(ssum >= k.lo - s2)
            obj = obj + s2
    prob = cp.Problem(cp.Minimize(obj), cons)
    prob.solve(solver="HIGHS")
    return prob.status, prob.value


# ---------------------------------------------------------------------------------------------
# checks that hold
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("seed,m,bands", [(0, 6000, 300), (3, 7500, 500), (4, 8000, 0)])
def test_realistic_solutions_pass_an_independent_kkt_certificate(seed, m, bands):
    """128 accounts, 6,000-8,000 entries from Rs 0.01 to 3e7 crore, 45% anchored, up to 500 bands of every
    kind: the answer is primal feasible (every account, incl. the dropped sinks), stationary, sign-correct at
    bounds and bands, with a duality gap from the verifier's own dual function of <= 1e-8 (proof of
    optimality); the known feasible truth needs no slack."""
    p, truth = gen(seed, m=m, n_bands=bands)
    s = cross_entropy(p)
    assert s.ok and s.status == "optimal", s.messages
    assert s.phase1["total_slack"] == 0 and not s.band_violation and not s.anchor_violation
    ok, bad = _certified(_certificate(p, s.x))
    assert ok, bad
    assert _objective(p, s.x) <= _objective(p, truth)


def test_an_interior_point_fallback_answer_passes_the_independent_certificate():
    """Wave C (DECISIONS D2-23): an answer reached through the interior-point fallback (3,000 entries, 300 bands:
    Newton needs more than its 100 direct steps) is checked by the verifier's own certificate, not only by the
    framework's; and an answer the fallback reaches with Newton's first try cut to one step must be the same
    optimum."""
    from pipeline.sam import balance

    p, truth = gen(5, n=128, m=3000, n_bands=300)
    s = cross_entropy(p)
    assert s.ok and s.solver_options["path"] == "interior-point fallback", s.messages
    ok, bad = _certified(_certificate(p, s.x))
    assert ok, bad
    assert _objective(p, s.x) <= _objective(p, truth)
    q, _ = gen(0, n=128, m=3000, n_bands=300)
    direct = cross_entropy(q)
    assert direct.ok and direct.solver_options["path"] == "direct", direct.messages
    first = balance.NEWTON_FIRST_TRY
    try:
        balance.NEWTON_FIRST_TRY = 1
        fb = cross_entropy(q)
    finally:
        balance.NEWTON_FIRST_TRY = first
    assert fb.ok and fb.solver_options["path"] == "interior-point fallback", fb.messages
    ok, bad = _certified(_certificate(q, fb.x))
    assert ok, bad
    assert _objective(q, fb.x) == pytest.approx(_objective(q, direct.x), rel=1e-9)


@pytest.mark.parametrize("seed", [1, 3, 4, 7, 10, 12, 15, 19])
def test_small_problems_agree_with_clarabel_at_tight_tolerances(seed):
    """Where an interior-point method is reliable (tens of entries, values 1..1e4): same objective to 1e-9
    and the same entries to 1e-6 relative, with nested / one-sided / negative / anchored mixes."""
    rng = np.random.default_rng(1000 + seed)
    n = int(rng.integers(6, 20))
    m = int(rng.integers(3 * n, 10 * n))
    nb = int(rng.integers(0, n))
    p, _ = gen(seed, n=n, m=m, n_bands=nb, vmin=1.0, vmax=1e4, tight=float(rng.choice([1.0, 5.0])))
    s = cross_entropy(p)
    assert s.ok, s.messages
    xc, status = _clarabel(p)
    assert status == "optimal"
    f, fc = _objective(p, s.x), _objective(p, xc)
    assert f == pytest.approx(fc, rel=1e-9)
    var = p.variable()
    assert np.max(np.abs(s.x - xc)[var] / np.abs(p.prior[var])) < 1e-6


@pytest.mark.parametrize("seed", [1, 2])
def test_infeasible_problem_gets_the_minimum_slack_and_a_certified_widened_optimum(seed):
    """Contradictory min/max, a single-entry band off an anchored box, nested sub-floor above a super-cap:
    phase 1's total slack equals an independent LP's, the violations reported add up to it (+ the widening
    margin), and the answer is certified optimal for the widened problem."""
    from pipeline.sam import balance as B

    p, truth = gen(seed, n_bands=300, m=6000)
    mem = np.flatnonzero(p.row == 5)[:6]
    t = float(np.sum(truth[mem]))
    an = np.flatnonzero((p.role == "anchored") & (np.abs(p.prior) > 1e4))[0]
    mem2 = np.flatnonzero(p.col == 9)[:8]
    t2 = float(np.sum(truth[mem2]))
    p.constraints = list(p.constraints) + [
        BC("conf_min", mem, t + 50.0, INF),
        BC("conf_max", mem, -INF, t - 50.0),
        BC("off_anchor", np.array([an]), p.prior[an] + 30.0, p.prior[an] + 31.0),
        BC("sup_cap", mem2, -INF, t2 - 20.0),
        BC("sub_floor", mem2[:3], float(np.sum(truth[mem2[:3]])) + 5.0, INF),
    ]
    s = cross_entropy(p)
    assert s.ok, s.messages
    status, v = _min_slack_lp(p)
    assert status == "optimal" and s.phase1["total_slack"] == pytest.approx(v, abs=1e-6)
    reported = sum(abs(x) for x in s.band_violation.values()) + sum(abs(x) for x in s.anchor_violation.values())
    assert v <= reported <= v + 0.01
    core = B._core(p)  # the widened bounds are the framework's (phase 1 + widen); the certificate is ours
    B._widen(core, B._phase1(core))
    const = np.where(p.variable(), 0.0, p.prior)
    blo = np.array([k.lo for k in p.constraints], float)
    bhi = np.array([k.hi for k in p.constraints], float)
    for j, ks in enumerate(core.band_ids):
        for k in ks:
            fs = float(np.sum(const[p.constraints[k].members]))
            blo[k] = min(blo[k], core.band_lo[j] + fs)
            bhi[k] = max(bhi[k], core.band_hi[j] + fs)
    ok, bad = _certified(_certificate(p, s.x, zlo=core.zlo, zhi=core.zhi, blo=blo, bhi=bhi))
    assert ok, bad


def test_sign_locked_account_is_named_and_boundary_optima_fail_loudly():
    """Infeasible balance names the sign-locked account; a problem whose optimum needs a free entry at
    exactly zero (the dual optimum does not exist) fails the run instead of claiming a certified optimum."""
    e7 = [(0, 1, 5e6, "free", "medium"), (1, 0, 4.9e6, "free", "medium"), (1, 2, 3e5, "free", "high"),
          (2, 1, 2.9e5, "free", "low"), (3, 2, 2e4, "fixed", None), (0, 3, 1e4, "fixed", None),
          (3, 0, 3e3, "free", "medium")]  # fmt: skip
    s = cross_entropy(mk(4, e7))
    assert not s.ok and s.status == "infeasible" and s.balance_slack == {"D": pytest.approx(1e4)}
    e4 = [(0, 1, 100.0, "free", "medium"), (1, 0, 100.0, "free", "medium"), (2, 0, 100.0, "fixed", None),
          (0, 2, 100.0, "fixed", None), (2, 1, 5.0, "free", "low")]  # fmt: skip
    s = cross_entropy(mk(3, e4))
    assert not s.ok and not s.certificate["ok"]


def test_polish_is_the_weighted_least_squares_step_on_free_entries_only():
    """polish(): delta = argmin sum (w/|x|) d^2 over free entries s.t. exact balance and (S-5 fix) unchanged sums
    of the bands it reports as held (dense KKT solve here). Every band at or outside a bound at the input is
    held, a held band's sum does not move, and no other band is pushed out of its interval."""
    for seed in range(3):
        p, _ = gen(seed, n=40, m=600, n_bands=30, vmin=0.01, vmax=1e6)
        s = cross_entropy(p)
        assert s.ok, s.messages
        rng = np.random.default_rng(seed)
        x = s.x.copy()
        free = np.flatnonzero((p.role == "free") & (x != 0) & (p.row != p.col))
        x[rng.choice(free, 5, replace=False)] += rng.uniform(-0.1, 0.1, 5)
        y, info, delta = polish(p, x)
        assert info["applied"] and not info.get("failed")
        assert np.max(np.abs(p.residual(y))) < 1e-7
        assert not np.any(delta[p.role != "free"])
        held = set(info["bands_held"])
        n = p.n_accounts
        A = np.zeros((n, len(free)))
        A[p.row[free], np.arange(len(free))] += 1
        A[p.col[free], np.arange(len(free))] -= 1
        rows = [A]
        for c in p.constraints:
            on = np.isin(free, c.members)
            s0 = float(np.sum(x[c.members]))
            if on.any() and (s0 >= c.hi - 1e-9 or s0 <= c.lo + 1e-9):
                assert c.constraint_id in held, c.constraint_id  # at or outside a bound: held
            if c.constraint_id in held:
                rows.append(on[None, :].astype(float))
                assert abs(float(np.sum(y[c.members])) - s0) < 1e-7
            else:
                s1 = float(np.sum(y[c.members]))
                assert c.lo - 1e-6 <= s1 <= c.hi + 1e-6, c.constraint_id
        C = np.vstack(rows)
        Wi = np.abs(x[free]) / p.weight[free]
        rhs = np.concatenate([p.residual(x), np.zeros(C.shape[0] - n)])
        lam = np.linalg.lstsq((C * Wi) @ C.T, rhs, rcond=None)[0]
        assert np.max(np.abs(delta[free] - (-Wi * (C.T @ lam)))) < 1e-7


def test_gras_matches_an_independent_entropy_minimiser():
    import cvxpy as cp

    rng = np.random.default_rng(5)
    for _ in range(4):
        nr, nc = int(rng.integers(3, 9)), int(rng.integers(3, 9))
        mask = rng.random((nr, nc)) < 0.7
        mask[:, 0] = True
        mask[0, :] = True
        row, col = np.nonzero(mask)
        a = rng.uniform(1, 100, len(row)) * np.where(rng.random(len(row)) < 0.2, -1, 1)
        truth = a * np.exp(rng.normal(0, 0.3, len(a)))
        u, v = np.bincount(row, truth, nr), np.bincount(col, truth, nc)
        g = gras(row, col, a, u, v)
        z = cp.Variable(len(a), nonneg=True)
        R = np.zeros((nr, len(a)))
        R[row, np.arange(len(a))] = a
        C = np.zeros((nc, len(a)))
        C[col, np.arange(len(a))] = a
        pr = cp.Problem(cp.Minimize(cp.sum(cp.multiply(np.abs(a), -cp.entr(z) - z))), [R @ z == u, C @ z == v])
        pr.solve(solver="CLARABEL", tol_gap_abs=1e-12, tol_gap_rel=1e-12, tol_feas=1e-12)
        assert g.converged and np.all(np.sign(g.x) == np.sign(a))
        assert np.max(np.abs(g.x - a * z.value)) < 1e-4


_DET = textwrap.dedent(
    """
    import hashlib, sys
    sys.path.insert(0, "tests/verify")
    from test_sam_solver_certificate import gen
    from pipeline.sam import balance
    from pipeline.sam.balance import cross_entropy
    p, _ = gen(5, n=128, m=3000, n_bands=300)
    s = cross_entropy(p)
    assert s.ok and s.solver_options["path"] == "interior-point fallback", (s.messages, s.solver_options)
    out = [s.x.tobytes()]
    balance.IPM_FINISH = 0  # the interior-point finish disabled: the proximal path is the last resort
    p, _ = gen(2, n=128, m=3000, n_bands=300)
    balance.NEWTON_FIRST_TRY = 20
    s = cross_entropy(p)
    assert s.ok and s.solver_options["path"] == "proximal fallback", (s.messages, s.solver_options)
    out.append(s.x.tobytes())
    print(hashlib.sha256(b"".join(out)).hexdigest())
    """
)


def test_the_fallback_paths_are_deterministic_across_hash_seeds_and_threads():
    """The existing determinism test covers the direct path; these problems take the interior-point fallback (Wave
    C, DECISIONS D2-23) and the proximal fallback, whose results must not depend on PYTHONHASHSEED or thread counts
    either. (Re-chosen twice. Wave B: the original problem, 600 near-equality bands with noise 0.3, converged
    directly after the S-1 fix. Wave C: gen(2), 300 bands of +-n crore on 3,000 entries, needed the proximal
    fallback and 177 steps until the zero-multiplier fix; it now converges directly. gen(5) takes the interior-point
    fallback; gen(2) reaches the proximal path when Newton gets 20 steps and the interior-point finish none.)"""
    outs = []
    for seed, threads in (("0", "1"), ("123", "1"), ("0", "8")):
        extra = {"PYTHONHASHSEED": seed, ALLOW_HASHSEED_VAR: "1", REEXEC_VAR: "1"}
        if threads != "1":
            extra |= {v: threads for v in THREAD_VARS} | {ALLOW_THREADS_VAR: "1"}
        env = pinned_environ(extra)
        env.pop(REEXEC_VAR, None)
        r = subprocess.run([sys.executable, "-c", _DET], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-2000:]
        outs.append(r.stdout.strip().splitlines()[-1])
    assert len(set(outs)) == 1, outs
    assert os.environ.get("PYTHONHASHSEED") == "0"


# ---------------------------------------------------------------------------------------------
# confirmed defects (were strict xfails; fixed in the Wave B disposition, docs/phase2/verify/solver_newton.md)
# ---------------------------------------------------------------------------------------------


def _single_entry_window(seed, mode):
    p, _ = gen(seed, n=40, m=600, n_bands=0)
    e = np.flatnonzero((p.role == "anchored") & (np.abs(p.prior) > 1e5) & (p.tol_rel < 0.5))[0]
    hi_x = max(p.prior[e] * (1 - p.tol_rel[e]), p.prior[e] * (1 + p.tol_rel[e]))
    if mode == "sliver":  # feasible: the band overlaps the box only in its top 0.0005 crore
        p.constraints = [BC("win", np.array([e]), hi_x - 5e-4, hi_x + 50.0)]
    else:  # infeasible by 20 crore: phase 1 widens one side, leaving a WIDEN_MARGIN (0.001 crore) window
        p.constraints = [BC("off", np.array([e]), hi_x + 20.0, hi_x + 21.0)]
    return p


@pytest.mark.parametrize("seed,mode", [(17, "sliver"), (2, "conflict")])
def test_single_entry_band_against_an_anchored_box_converges(seed, mode):
    """A one-entry constraint over an anchored entry whose interval meets the entry's box only in a narrow
    window (<= WIDEN_MARGIN; phase 1 creates exactly this when the band conflicts with the box). Before the
    S-1 fix the band multiplier grew while the entry was clipped at its box and then crept back by ~0.01 per
    step: dual Newton, the proximal path and Newton again all failed (3,900 steps) and the run failed,
    although the problem is feasible (after widening)."""
    s = cross_entropy(_single_entry_window(seed, mode))
    assert s.ok, s.messages


def test_newton_stops_only_where_the_certificate_holds():
    """Strictly feasible, interior optimum (a free entry must be 0.001 crore, z = 2e-4). Before the S-2 fix
    Newton stopped with a 5e-7 crore residual (within its tolerance) and the certificate's duality gap (9e-7
    relative, needs 1e-8) failed the run. Two more Newton steps pass it (gap 1e-15)."""
    e = [(0, 1, 100.0, "free", "medium"), (1, 0, 100.0, "free", "medium"), (2, 0, 100.0, "fixed", None),
         (0, 2, 100.0 + 1e-3, "fixed", None), (2, 1, 5.0, "free", "low")]  # fmt: skip
    s = cross_entropy(mk(3, e))
    assert s.ok, s.messages


def test_slack_below_lp_zero_does_not_fail_the_run():
    """An anchored bound that is infeasible by 5e-7 crore (Rs 50): before the S-3 fix phase 1 found the slack
    but treated it as solver noise (<= LP_ZERO = 1e-6) and did not widen; the entropy problem was then
    infeasible and the certificate failed the run. Slack of 2e-6 was widened and the run succeeded."""
    e = [(0, 1, 1000.0, "anchored", 1e-3), (1, 2, 1000.0, "free", "medium"), (2, 0, 1001.0 + 5e-7, "fixed", None)]
    s = cross_entropy(mk(3, e))
    assert s.ok, s.messages
