"""Realistic-size random SAMs for balancing tests (Wave A review F1, F2, F5), and an independent reference
solver. Nothing here imports the framework's solver: the reference is a separate dual Newton method
(dense linear algebra, no bands) written for the tests.

The generator follows the math reviewer's probe (docs/phase2/verify/framework_math.md): 128 accounts,
~5,000 entries log-uniform from Rs 0.01 to 3e7 crore, ~4% negative, 10% fixed, 45% anchored with the
production rule of Rs 1 crore per cell (tol_rel = 1/|a|), the rest free with mixed confidence; a balanced
'truth' perturbed on the free entries and rounded on the anchored ones, so the truth is a known feasible
point; optional bands of +-n crore around the truth's sums (so the truth satisfies them too).
"""

from __future__ import annotations

import numpy as np

from pipeline.sam import spec
from pipeline.sam.balance import BandConstraint, Problem, single_threaded_blas


def _balance_truth(n: int, row: np.ndarray, col: np.ndarray, a: np.ndarray) -> np.ndarray:
    """Unweighted entropy balance of a (no bounds), by a dense dual Newton method: a balanced 'truth'."""
    lam = np.zeros(n)
    s = np.sign(a)
    c = np.abs(a)
    for _ in range(200):
        z = np.exp(np.clip(-s * (lam[row] - lam[col]), -50, 50))
        x = a * z
        g = np.bincount(row, x, n) - np.bincount(col, x, n)
        if np.max(np.abs(g)) < 1e-10 * max(1.0, np.max(np.abs(x))):
            break
        h = c * z
        H = np.zeros((n, n))
        np.add.at(H, (row, row), h)
        np.add.at(H, (col, col), h)
        np.add.at(H, (row, col), -h)
        np.add.at(H, (col, row), -h)
        d = np.zeros(n)
        d[1:] = np.linalg.solve(H[1:, 1:], g[1:])  # J = -L (weights |a|z): L d = g
        f0, step = np.max(np.abs(g)), 1.0
        while step > 1e-8:
            ln = lam + step * d
            zz = np.exp(np.clip(-s * (ln[row] - ln[col]), -50, 50))
            gg = np.bincount(row, a * zz, n) - np.bincount(col, a * zz, n)
            if np.max(np.abs(gg)) < f0:
                break
            step /= 2
        lam = lam + step * d
    return a * np.exp(np.clip(-s * (lam[row] - lam[col]), -50, 50))


def random_sam(seed: int, *, n: int = 128, m: int = 5000, noise: float = 0.05, n_bands: int = 0,
               anchored: float = 0.45, fixed: float = 0.10) -> tuple[Problem, np.ndarray]:  # fmt: skip
    rng = np.random.default_rng(seed)
    pairs = set()
    for i in range(n):  # a ring both ways keeps every account connected
        pairs.add((i, (i + 1) % n))
        pairs.add(((i + 1) % n, i))
    while len(pairs) < m:
        r, c = rng.integers(0, n, 2)
        if r != c:
            pairs.add((int(r), int(c)))
    pairs_l = sorted(pairs)
    row = np.array([p[0] for p in pairs_l])
    col = np.array([p[1] for p in pairs_l])
    m = len(pairs_l)
    base = np.exp(rng.uniform(np.log(0.01), np.log(3e7), m)) * np.where(rng.random(m) < 0.04, -1.0, 1.0)
    ring = np.array([abs(r - c) in (1, n - 1) for r, c in pairs_l])
    base[ring] = np.abs(base[ring]) + 1e5
    with single_threaded_blas():  # dense LAPACK: pin BLAS so the truth (and the bands) are thread-independent
        truth = _balance_truth(n, row, col, base)
    k = rng.random(m)
    role = np.where(k < fixed, "fixed", np.where(k < fixed + anchored, "anchored", "free")).astype(object)
    role[ring] = "free"
    conf = np.array([["high", "medium", "low"][i] for i in rng.integers(0, 3, m)], dtype=object)
    prior = truth.copy()
    fr = role == "free"
    prior[fr] = truth[fr] * np.exp(rng.normal(0, noise, int(fr.sum())))
    an = role == "anchored"
    prior[an] = np.round(truth[an])  # a rounded published cell
    prior[an & (prior == 0)] = np.sign(truth[an & (prior == 0)])
    tol = np.where(an, 1.0 / np.maximum(np.abs(prior), 1e-12), np.nan)
    prior = np.round(prior, 6)
    prior[role == "fixed"] = np.round(truth[role == "fixed"], 6)
    w = np.array([spec.entry_weight(r_, c_ if r_ == "free" else None) for r_, c_ in zip(role, conf)])
    bands = []
    for kk in range(n_bands):
        acct = int(rng.integers(0, n))
        mem = np.flatnonzero(row == acct)
        mem = mem[rng.random(len(mem)) < 0.6]
        if len(mem):
            t = float(np.sum(truth[mem]))
            bands.append(BandConstraint(f"c{kk}", mem, t - len(mem), t + len(mem)))
    return Problem(n, row, col, prior, role, tol, w, bands, [f"A{i}" for i in range(n)]), truth


def objective(p: Problem, x: np.ndarray) -> float:
    var = p.variable()
    z = x[var] / p.prior[var]
    with np.errstate(divide="ignore", invalid="ignore"):
        zl = np.where(z > 0, z * np.log(z), 0.0)
    return float(np.sum(p.weight[var] * np.abs(p.prior[var]) * (zl - z + 1)))


def reference_solution(p: Problem, iters: int = 200) -> np.ndarray:
    """Independent reference (no bands): semismooth Newton on the dual in lambda (dense), z clipped to the
    anchored boxes: z_e = clip(exp(-sign(a_e)(lambda_row - lambda_col)/w_e))."""
    assert not p.constraints
    var = np.flatnonzero(p.variable())
    a = p.prior[var]
    w = p.weight[var]
    c = w * np.abs(a)
    s = np.sign(a)
    fixed = np.where(p.variable(), 0.0, p.prior)
    n = p.n_accounts
    b = np.bincount(p.row, fixed, n) - np.bincount(p.col, fixed, n)
    ri, ci = p.row[var], p.col[var]
    lo = np.zeros(len(var))
    hi = np.full(len(var), np.inf)
    an = p.role[var] == "anchored"
    lo[an] = np.maximum(0, 1 - p.tol_rel[var][an])
    hi[an] = 1 + p.tol_rel[var][an]

    def at(lam):
        u = -s * (lam[ri] - lam[ci]) / w
        zu = np.exp(np.clip(u, -700, 700))
        z = np.clip(zu, lo, hi)
        g = np.bincount(ri, a * z, n) - np.bincount(ci, a * z, n) + b
        return z, zu, g

    lam = np.zeros(n)
    for _ in range(iters):
        z, zu, g = at(lam)
        if np.max(np.abs(g)) < 1e-7:
            break
        h = np.where((zu > lo) & (zu < hi), a * a * z / c, 1e-9 * a * a * z / c)
        H = np.zeros((n, n))
        np.add.at(H, (ri, ri), h)
        np.add.at(H, (ci, ci), h)
        np.add.at(H, (ri, ci), -h)
        np.add.at(H, (ci, ri), -h)
        d = np.zeros(n)
        d[1:] = np.linalg.solve(H[1:, 1:] + 1e-12 * np.eye(n - 1) * np.max(np.diag(H)), g[1:])
        f0, step = np.max(np.abs(g)), 1.0
        while step > 1e-12:
            if np.max(np.abs(at(lam + step * d)[2])) < f0:
                break
            step /= 2
        lam = lam + step * d
    z, _, _ = at(lam)
    x = p.prior.copy()
    x[var] = a * z
    return x
