"""Balancing the SAM (DESIGN_BRIEF s.5): cross-entropy (primary), exact polish, and GRAS (cross-check).

The problem, with signed priors a_e and x_e = a_e z_e:

    minimise   sum_e w_e |a_e| (z_e ln z_e - z_e + 1)
    subject to every account: sum(row) - sum(col) = 0
               anchored entries: z_e in [1 - tol_e, 1 + tol_e] (and z_e >= 0)
               free entries:     z_e >= 0
               every constraint: lo_k <= sum(members) <= hi_k

Signs never flip, zeros stay zero, no new cells, fixed entries are constants. It is solved in steps
(Wave A and Wave B reviews, docs/phase2/FRAMEWORK_REQUESTS.md):

0. Pre-check (exact, no solver). Accounts are grouped into components linked by variable entries. The
   sum of a component's balance equations involves fixed entries only; if it exceeds BALANCE_TOL the
   run fails and names the component. Otherwise one equation per component (its first account, the
   'sink') is dropped: the sink carries the component's fixed residual (<= BALANCE_TOL, reported). A
   constraint none of whose entries can move is checked here too: if its fixed sum is outside its band,
   that is a named conflict between fixed data and the constraint, counted as slack (Wave B S-6).
1. Phase 1, minimum slack (LP, HiGHS dual simplex, Rs crore): exact balance, sign locks, and slacks on
   the anchored bounds and constraint bands, minimising their total. If even that is infeasible (a sign
   lock or fixed entries make an account impossible to close) the run fails; a second LP with account
   slacks and an exact per-account sign test say where the infeasibility shows. Every positive slack,
   however small (Wave B S-3), widens its bound by the slack + WIDEN_MARGIN: slack therefore appears only
   when the problem is genuinely infeasible, and it is reported (BALANCING.md, ISSUES.md), never silently
   absorbed (a total at or below LP_ZERO is labelled solver rounding, not a finding).
2. Phase 2, cross-entropy on the (widened) feasible problem. Default solver NEWTON: a semismooth Newton
   method on the concave dual in (lambda per kept account equation, mu per constraint band). The
   optimum has the closed form z_e = clip(exp(-s_e (lambda_row - lambda_col + sum_k mu_k) / w_e),
   box), which does not depend on |a_e|, so the method is well scaled although w|a| spans eleven orders
   of magnitude (an interior-point solver is not: review F1). A dual coordinate whose members are all
   clipped at their boxes (a narrow window between a band or an account's balance and anchored boxes,
   which phase-1 widening creates) is first maximised exactly along that coordinate (Wave B S-1). It
   stops when every residual is within its tolerance and the duality gap is below GAP_STOP (Wave B S-2).
   If it has not converged after NEWTON_FIRST_TRY steps, the interior-point fallback (DECISIONS D2-23,
   Wave C): a log-barrier path-following method on the same dual (every box and band smoothed by a
   logarithmic barrier weighted in the problem's own units, the weight shrunk from IPM_TAU0 to IPM_TAU_END),
   then the exact dual Newton method from its multipliers; if that fails too, the older proximal path.
   The first full run needed this: the real SAM's ~1,000 narrow anchored boxes (median ln-width 7e-4) and
   ~280 tight bands make the exact dual nearly polyhedral. Sums use numpy.bincount and scipy sparse
   products; the Newton systems are solved with SuperLU; no dense BLAS call is made. `--solver <cvxpy
   name>` (e.g. CLARABEL) is an override for diagnosis (review F3: one retry at the solver's defaults on
   optimal_inaccurate or solver_error; the options actually used are recorded); its answers rarely pass
   the certificate (Wave B S-7).
3. KKT certificate (any solver): primal feasibility (balance, bands, boxes), stationarity of every
   entry not at a bound, sign conditions at bounds, complementary band multipliers, duality gap. A
   failed certificate fails the run and names the entries with the smallest z (a tiny z means the
   constraints force an entry to zero: no dual optimum exists, Wave B S-4). For a cvxpy solver the
   multipliers are recovered from x by least squares.
4. Polish: only if a kept account is off by more than POLISH_TRIGGER (NEWTON leaves ~1e-7 crore): the
   minimum weighted-least-squares change on FREE entries (weights w_e/|x_e|) that closes every account and
   holds the sums of the bands at a bound and of any band it would otherwise push out (Wave B S-5).
   A pre-polish imbalance above POLISH_MAX or any sign flip fails the run; the change per entry is logged.

GRAS (Junius & Oosterhaven 2003; Temurshoev, Miller & Bouwmeester 2013 corrections) on the same
prior: fixed entries held, anchored and free entries scaled, each account's row and column target
= mean of its prior row and column sums. Used only as a cross-check.
"""

from __future__ import annotations

import math
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import polars as pl
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import splu

from pipeline.sam import spec

LOG_CAP = 300.0  # |ln z| is capped here inside the Newton iterations (exp overflows near 709)
BOUND_CURVATURE = 1e-6  # share of the unclipped curvature given to an entry at a bound in the Newton system
RHO_CAP = 1e6  # cap of the Levenberg-Marquardt damping in the dual Newton method (reaching it triggers coordinate steps)
NEWTON_FIRST_TRY = 100  # dual Newton steps before falling back to the proximal path (then Newton again)
PROX_WEIGHT = 1.0  # initial proximal weight on a band sum, relative to the inverse curvature the entries give it
PROX_SHRINK = 0.1  # the proximal weight shrinks by this factor per outer step
PROX_FINISH = 15  # exact dual Newton steps tried after each outer step
CERT_GAP = 1e-8  # the certificate's limit on the relative duality gap |f - q| / max(1, |f|)
GAP_STOP = 1e-10  # Newton stops once the residuals are within tolerance AND the gap is below this (Wave B S-2) ...
GAP_EXTRA = 10  # ... or after this many further steps (then the certificate decides)
# an entry balanced to below BOUNDARY_Z of its prior (z = x / prior) is forced to zero by the constraints: the
# optimum is on the boundary z = 0, where no dual optimum exists. The certificate refuses it when its prior is
# material (|prior| >= spec.MATERIAL_CHANGE); a smaller one is accepted and listed in the messages (Wave B S-4)
BOUNDARY_Z = 1e-6
# interior-point fallback (DECISIONS D2-23; _interior_point): log-barrier stages from barrier weight IPM_TAU0 down
# to IPM_TAU_END (x IPM_SHRINK per stage), each Newton on the smooth dual until every balance and band residual is
# within IPM_STAGE_MERIT x its Newton tolerance or IPM_STAGE_STEPS steps (IPM_TAU_END is not smaller because a narrow
# box's barrier distance, ~ tau x its width, then falls below the spacing of doubles); then the exact dual
# Newton method finishes (at most IPM_FINISH steps). Hand-over points, not acceptance tests: the certificate is.
IPM_TAU0 = 0.1
IPM_SHRINK = 0.1
IPM_TAU_END = 1e-10
IPM_STAGE_MERIT = 1e3
IPM_STAGE_STEPS = 50
IPM_MU_ZERO = 1e-9  # a band multiplier at most this large (10 x IPM_TAU_END) is handed over as 0 (_barrier_path)
IPM_FINISH = 200  # dual Newton steps from the interior-point multipliers


def _openblas_handles() -> list[tuple[Any, Any]]:
    """(get, set) thread functions of every OpenBLAS bundled with numpy and scipy (their wheels ship
    scipy-openblas builds; SuperLU and HiGHS inside scipy call the scipy one)."""
    import ctypes
    import glob
    import os

    import scipy

    out = []
    names = (("scipy_openblas_get_num_threads", "scipy_openblas_set_num_threads"),
             ("scipy_openblas_get_num_threads64_", "scipy_openblas_set_num_threads64_"),
             ("openblas_get_num_threads", "openblas_set_num_threads"))  # fmt: skip
    for pkg in (scipy, np):
        base = os.path.dirname(os.path.dirname(pkg.__file__))
        pats = [os.path.join(base, f"{pkg.__name__}.libs", "*openblas*"),
                os.path.join(os.path.dirname(pkg.__file__), ".dylibs", "*openblas*")]  # fmt: skip
        for f in sorted(x for pat in pats for x in glob.glob(pat)):
            try:
                lib = ctypes.CDLL(f)
            except OSError:
                continue
            for g, st in names:
                if hasattr(lib, g) and hasattr(lib, st):
                    out.append((getattr(lib, g), getattr(lib, st)))
                    break
    return out


@contextmanager
def single_threaded_blas():
    """Pin the bundled OpenBLAS libraries to one thread while balancing (review F5: with 4 OpenBLAS threads
    SuperLU's and HiGHS's dense kernels round differently, so the balanced SAM would not be byte-identical
    across thread counts). Restores the previous setting afterwards. What threadpoolctl does, without a new
    dependency; if no library is found, nothing is pinned (the determinism test would show it)."""
    handles = _openblas_handles()
    before = [int(g()) for g, _ in handles]
    for _, st in handles:
        st(1)
    try:
        yield len(handles)
    finally:
        for (_, st), n in zip(handles, before):
            st(n)


@dataclass
class BandConstraint:
    constraint_id: str
    members: np.ndarray  # entry indices
    lo: float  # Rs crore (-inf: no lower bound)
    hi: float  # (+inf: no upper bound)


@dataclass
class Problem:
    """Entry-level balancing problem. Accounts are 0..n_accounts-1; entry e is row[e] <- col[e]."""

    n_accounts: int
    row: np.ndarray
    col: np.ndarray
    prior: np.ndarray
    role: np.ndarray  # 'fixed' | 'anchored' | 'free'
    tol_rel: np.ndarray  # NaN unless anchored
    weight: np.ndarray  # spec.entry_weight
    constraints: list[BandConstraint] = field(default_factory=list)
    account_names: list[str] | None = None

    def name(self, i: int) -> str:
        return self.account_names[i] if self.account_names else str(i)

    def sums(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        n = self.n_accounts
        return (
            np.bincount(self.row, weights=x, minlength=n),
            np.bincount(self.col, weights=x, minlength=n),
        )

    def residual(self, x: np.ndarray) -> np.ndarray:
        r, c = self.sums(x)
        return r - c

    def variable(self) -> np.ndarray:
        return (self.role != "fixed") & (self.prior != 0)


@dataclass
class Solution:
    x: np.ndarray
    status: str
    solver: str
    objective: float | None
    iterations: int | None
    balance_slack: dict[str, float]  # account -> Rs crore that cannot close (non-empty = the run failed)
    band_violation: dict[str, float]  # constraint -> Rs crore outside its band (+ above, - below)
    anchor_violation: dict[int, float]  # entry -> Rs crore outside its anchored bound
    polish: dict[str, Any]
    max_imbalance: float
    messages: list[str]
    certificate: dict[str, Any] = field(default_factory=dict)
    phase1: dict[str, Any] = field(default_factory=dict)
    solver_options: dict[str, Any] = field(default_factory=dict)
    polish_delta: np.ndarray | None = None
    fixed_residuals: dict[str, float] = field(default_factory=dict)  # sink account -> within-tolerance residual
    band_multipliers: dict[str, float] = field(default_factory=dict)  # constraint -> mu (NEWTON; non-zero = binding)

    @property
    def ok(self) -> bool:
        return (
            self.status == "optimal"
            and not self.balance_slack
            and self.max_imbalance <= spec.BALANCE_TOL
            and bool(self.certificate.get("ok"))
            and not self.polish.get("failed")
        )


def problem_from_frames(entries: pl.DataFrame, constraints: pl.DataFrame, accounts: list[str]) -> Problem:
    """Build a Problem from assembled entries (spec.ENTRY_DTYPES columns) and constraints."""
    idx = {a: i for i, a in enumerate(accounts)}
    row = np.array([idx[a] for a in entries["row"].to_list()], dtype=np.int64)
    col = np.array([idx[a] for a in entries["col"].to_list()], dtype=np.int64)
    prior = entries["value"].to_numpy().astype(np.float64)
    role = np.array(entries["role"].to_list(), dtype=object)
    tol = entries["tol_rel"].fill_null(float("nan")).to_numpy().astype(np.float64)
    bad = np.flatnonzero((role == "anchored") & ~(tol > 0))
    if len(bad):
        from pipeline.sam.framework import SamError

        raise SamError(f"{len(bad)} anchored entries without tol_rel > 0 (first: entry {int(bad[0])})")
    weight = np.array(
        [spec.entry_weight(r, c) for r, c in zip(entries["role"].to_list(), entries["confidence"].to_list())]
    )
    rows_arr = np.array(entries["row"].to_list(), dtype=object)
    cols_arr = np.array(entries["col"].to_list(), dtype=object)
    refs_arr = np.array(entries["ref"].to_list(), dtype=object)
    comp_arr = np.array(entries["component"].to_list(), dtype=object)
    cons: list[BandConstraint] = []
    for c in constraints.iter_rows(named=True):
        m = np.isin(rows_arr, c["rows"].split(",")) & np.isin(cols_arr, c["cols"].split(","))
        if c["refs"]:
            m &= np.isin(refs_arr, c["refs"].split(","))
        if c.get("components"):
            m &= np.isin(comp_arr, c["components"].split(","))
        lo, hi = band_of(c)
        cons.append(BandConstraint(c["constraint_id"], np.flatnonzero(m), lo, hi))
    return Problem(len(accounts), row, col, prior, role, tol, weight, cons, list(accounts))


def band_of(c: dict[str, Any]) -> tuple[float, float]:
    """The interval a constraint row allows: target +- max(tol_abs, tol_rel*|target|), one side open for min/max."""
    tol_c = max(c["tol_abs"], c["tol_rel"] * abs(c["target"]))
    kind = c.get("kind") or "equal"
    lo = -math.inf if kind == "max" else c["target"] - tol_c
    hi = math.inf if kind == "min" else c["target"] + tol_c
    return lo, hi


# ---------------------------------------------------------------------------------------------
# the reduced problem (variable entries, kept balance equations, bands over variable entries)
# ---------------------------------------------------------------------------------------------


@dataclass
class _Core:
    p: Problem
    var: np.ndarray  # entry indices of the variable entries
    a: np.ndarray  # their priors, Rs crore
    w: np.ndarray
    s: np.ndarray  # sign(a)
    zlo: np.ndarray  # z bounds (after any phase-1 widening)
    zhi: np.ndarray
    labels: np.ndarray  # account -> component
    sink: np.ndarray  # bool per account: the dropped equation of its component
    eq_of: np.ndarray  # account -> equation index or -1
    b: np.ndarray  # per account: row - col of the constant (non-variable) entries, Rs crore
    gross_fixed: np.ndarray  # per account: sum of |constant entries| touching it
    comp_b: np.ndarray  # per component: sum of b
    band_ids: list[list[int]]  # per band: the indices into p.constraints it merges (same variable members)
    band_lo: np.ndarray  # their bounds minus the constant members' sum (after widening)
    band_hi: np.ndarray
    band_fixed_gross: np.ndarray
    G: sp.csr_matrix  # (m + K) x n: balance rows (+a at row account, -a at col account) then band rows (+a)
    GT: sp.csr_matrix
    x_lp: np.ndarray | None = None  # phase-1 LP solution (x-space), set by _phase1

    @property
    def m(self) -> int:
        return int(np.sum(self.eq_of >= 0))

    @property
    def K(self) -> int:
        return len(self.band_ids)


def _core(p: Problem) -> _Core:
    n = p.n_accounts
    varm = p.variable()
    var = np.flatnonzero(varm)
    a = p.prior[var].astype(np.float64)
    w = p.weight[var].astype(np.float64)
    ri, ci = p.row[var], p.col[var]
    const = np.where(varm, 0.0, p.prior)
    rs, cs = p.sums(const)
    b = rs - cs
    gross_fixed = np.bincount(p.row, weights=np.abs(const), minlength=n) + np.bincount(
        p.col, weights=np.abs(const), minlength=n
    )
    offdiag = ri != ci
    adj = sp.coo_matrix((np.ones(int(offdiag.sum())), (ri[offdiag], ci[offdiag])), shape=(n, n)).tocsr()
    _, labels = connected_components(adj, directed=False)
    ncomp = int(labels.max()) + 1 if n else 0
    first = np.full(ncomp, -1, dtype=np.int64)
    for i in range(n - 1, -1, -1):
        first[labels[i]] = i
    sink = np.zeros(n, dtype=bool)
    sink[first] = True
    eq_of = -np.ones(n, dtype=np.int64)
    keep = np.flatnonzero(~sink)
    eq_of[keep] = np.arange(len(keep))
    comp_b = np.bincount(labels, weights=b, minlength=ncomp)
    zlo = np.zeros(len(var))
    zhi = np.full(len(var), np.inf)
    an = p.role[var] == "anchored"
    t = p.tol_rel[var]
    zlo[an] = np.maximum(0.0, 1.0 - t[an])
    zhi[an] = 1.0 + t[an]
    pos = -np.ones(len(p.prior), dtype=np.int64)
    pos[var] = np.arange(len(var))
    # bands over the same variable entries are one band (their intervals intersected; phase 1 reports an
    # empty intersection as slack): duplicates would leave exactly flat directions in the dual
    groups: dict[tuple[int, ...], int] = {}
    band_ids: list[list[int]] = []
    blo: list[float] = []
    bhi: list[float] = []
    bfg: list[float] = []
    brows: list[int] = []
    bcols: list[int] = []
    for k, c in enumerate(p.constraints):
        mem = c.members
        mv = np.sort(pos[mem[pos[mem] >= 0]])
        if len(mv) == 0:
            continue
        fixed_sum = float(np.sum(const[mem]))
        key = tuple(mv.tolist())
        j = groups.get(key)
        if j is None:
            groups[key] = j = len(band_ids)
            brows.extend([j] * len(mv))
            bcols.extend(mv.tolist())
            band_ids.append([k])
            blo.append(c.lo - fixed_sum)
            bhi.append(c.hi - fixed_sum)
            bfg.append(float(np.sum(np.abs(const[mem]))))
        else:
            band_ids[j].append(k)
            blo[j] = max(blo[j], c.lo - fixed_sum)
            bhi[j] = min(bhi[j], c.hi - fixed_sum)
            bfg[j] = max(bfg[j], float(np.sum(np.abs(const[mem]))))
    m = len(keep)
    e_idx = np.arange(len(var))
    r_eq, c_eq = eq_of[ri], eq_of[ci]
    use_r = (r_eq >= 0) & offdiag
    use_c = (c_eq >= 0) & offdiag
    rows = np.concatenate([r_eq[use_r], c_eq[use_c], m + np.array(brows, dtype=np.int64)])
    cols = np.concatenate([e_idx[use_r], e_idx[use_c], np.array(bcols, dtype=np.int64)])
    vals = np.concatenate([a[use_r], -a[use_c], a[np.array(bcols, dtype=np.int64)]])
    K = len(band_ids)
    G = sp.csr_matrix((vals, (rows, cols)), shape=(m + K, len(var)))
    G.sum_duplicates()
    G.sort_indices()
    return _Core(
        p=p, var=var, a=a, w=w, s=np.sign(a), zlo=zlo, zhi=zhi, labels=labels, sink=sink, eq_of=eq_of, b=b,
        gross_fixed=gross_fixed, comp_b=comp_b, band_ids=band_ids, band_lo=np.array(blo, dtype=np.float64),
        band_hi=np.array(bhi, dtype=np.float64), band_fixed_gross=np.array(bfg, dtype=np.float64), G=G,
        GT=G.T.tocsr(),
    )  # fmt: skip


def _tolerances(core: _Core, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Newton stopping tolerance per kept equation and per band (Rs crore)."""
    gross = abs(core.G) @ z  # G holds +-a_e, z >= 0: sum of |x_e| per equation / band
    m = core.m
    keep = np.flatnonzero(core.eq_of >= 0)
    tb = spec.NEWTON_TOL_ABS + spec.NEWTON_TOL_REL * (gross[:m] + core.gross_fixed[keep])
    tk = spec.NEWTON_TOL_ABS + spec.NEWTON_TOL_REL * (gross[m:] + core.band_fixed_gross)
    return tb, tk


# ---------------------------------------------------------------------------------------------
# step 0 and phase 1: feasibility, minimum slack, diagnosis
# ---------------------------------------------------------------------------------------------


def _component_names(core: _Core, comp: int, limit: int = 12) -> list[str]:
    acc = np.flatnonzero(core.labels == comp)
    return [core.p.name(int(i)) for i in acc[:limit]] + ([f"... ({len(acc)} accounts)"] if len(acc) > limit else [])


def _sign_locked(core: _Core) -> list[tuple[str, float, str]]:
    """Accounts that cannot close whatever the variable entries do (z >= 0, anchored boxes ignored): the
    constant part and the sign-locked variable part leave row - col on one side of zero. Exact."""
    p = core.p
    n = p.n_accounts
    ri, ci = p.row[core.var], p.col[core.var]
    off = ri != ci
    # each variable entry adds a*z (z >= 0) to its row account's (row - col) and -a*z to its column account's
    contrib_acc = np.concatenate([ri[off], ci[off]])
    contrib_sign = np.concatenate([np.sign(core.a[off]), -np.sign(core.a[off])])
    can_up = np.bincount(contrib_acc, weights=(contrib_sign > 0).astype(float), minlength=n) > 0
    can_down = np.bincount(contrib_acc, weights=(contrib_sign < 0).astype(float), minlength=n) > 0
    out = []
    for i in range(n):
        bi = core.b[i]
        if bi > spec.BALANCE_TOL and not can_down[i]:
            why = "no variable entry can lower it" if can_up[i] else "no variable entry"
            out.append((p.name(i), float(bi), why))
        elif bi < -spec.BALANCE_TOL and not can_up[i]:
            why = "no variable entry can raise it" if can_down[i] else "no variable entry"
            out.append((p.name(i), float(bi), why))
    return out


def _xbounds(core: _Core) -> tuple[np.ndarray, np.ndarray]:
    """Bounds on x = a z of the variable entries (Rs crore)."""
    a = core.a
    lo = np.where(a > 0, a * core.zlo, a * core.zhi)
    hi = np.where(a > 0, a * core.zhi, a * core.zlo)
    return lo, hi


def _phase1(core: _Core) -> dict[str, Any]:
    """Minimum total slack (Rs crore) on anchored bounds and constraint bands, subject to exact balance of
    the kept equations and the sign locks. HiGHS dual simplex (a vertex: slack sits on few constraints)."""
    from scipy.optimize import linprog

    n = len(core.var)
    m, K = core.m, core.K
    a = core.a
    an = np.flatnonzero(core.p.role[core.var] == "anchored")
    xlo, xhi = _xbounds(core)
    # variables: x (n) | anchored slack below, above (len(an) each) | band slack below, above (K each)
    na = len(an)
    nv = n + 2 * na + 2 * K
    cost = np.concatenate([np.zeros(n), np.ones(2 * na + 2 * K)])
    # G has +-a_e as coefficients (z-space); in x-space (x = a z) they are +-1
    Gx = sp.csr_matrix((core.G.data / a[core.G.indices], core.G.indices, core.G.indptr), shape=core.G.shape)
    keep = np.flatnonzero(core.eq_of >= 0)
    A_eq = sp.hstack([Gx[:m], sp.csr_matrix((m, nv - n))]).tocsr()
    b_eq = -core.b[keep]
    ub_blocks, ub_rhs = [], []
    if na:
        E = sp.csr_matrix((np.ones(na), (np.arange(na), an)), shape=(na, n))
        Z = sp.csr_matrix((na, 2 * K))
        Ia = sp.identity(na, format="csr")
        Oa = sp.csr_matrix((na, na))
        ub_blocks += [sp.hstack([E, Oa, -Ia, Z]), sp.hstack([-E, -Ia, Oa, Z])]  # x - s_hi <= hi ; -x - s_lo <= -lo
        ub_rhs += [xhi[an], -xlo[an]]
    if K:
        B = Gx[m:]
        Za = sp.csr_matrix((K, 2 * na))
        Ik = sp.identity(K, format="csr")
        Ok = sp.csr_matrix((K, K))
        hi_ok = np.isfinite(core.band_hi)
        lo_ok = np.isfinite(core.band_lo)
        ub_blocks += [
            sp.hstack([B, Za, Ok, -Ik]).tocsr()[np.flatnonzero(hi_ok)],  # B x - s_hi <= hi
            sp.hstack([-B, Za, -Ik, Ok]).tocsr()[np.flatnonzero(lo_ok)],  # -B x - s_lo <= -lo
        ]
        ub_rhs += [core.band_hi[hi_ok], -core.band_lo[lo_ok]]
    A_ub = sp.vstack(ub_blocks).tocsr() if ub_blocks else None
    b_ub = np.concatenate(ub_rhs) if ub_rhs else None
    bounds = [(0.0, None) if ai > 0 else (None, 0.0) for ai in a] + [(0.0, None)] * (nv - n)
    res = linprog(cost, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq if m else None, b_eq=b_eq if m else None, bounds=bounds,
                  method="highs-ds", options={"presolve": True})  # fmt: skip
    out: dict[str, Any] = {"status": int(res.status), "message": str(res.message)}
    if res.status != 0:
        out["feasible"] = False
        return out
    v = res.x
    core.x_lp = v[:n].copy()  # a feasible point of the widened problem (a vertex: often on the boundary)
    s_alo, s_ahi = v[n : n + na], v[n + na : n + 2 * na]
    s_blo, s_bhi = v[n + 2 * na : n + 2 * na + K], v[n + 2 * na + K :]
    out.update(
        feasible=True,
        total_slack=float(np.sum(v[n:])),
        anchored={int(core.var[an[i]]): (float(s_alo[i]), float(s_ahi[i])) for i in range(na)
                  if s_alo[i] > 0.0 or s_ahi[i] > 0.0},
        bands={k: (float(s_blo[k]), float(s_bhi[k])) for k in range(K)
               if s_blo[k] > 0.0 or s_bhi[k] > 0.0},
    )  # fmt: skip
    return out


def _widen(core: _Core, ph1: dict[str, Any]) -> None:
    """Widen every bound phase 1 needed slack on by the slack + WIDEN_MARGIN (rounded up to 1e-6 crore). Any
    positive slack, however small (Wave B review S-3): a slack at or below LP_ZERO left unwidened made the
    entropy problem infeasible by that much, and the certificate's duality gap then failed the run."""
    pos = {int(e): i for i, e in enumerate(core.var)}

    def amount(v: float) -> float:
        return math.ceil((v + spec.WIDEN_MARGIN) * 1e6) / 1e6

    for e, (slo, shi) in ph1.get("anchored", {}).items():
        i = pos[e]
        a = core.a[i]
        # x bounds lo_x = a*zlo (a > 0) ... widen in x-space, then back to z-space
        if slo > 0.0:  # x needed to go below its lower x-bound
            if a > 0:
                core.zlo[i] = max(0.0, core.zlo[i] - amount(slo) / a)
            else:
                core.zhi[i] = core.zhi[i] + amount(slo) / abs(a)
        if shi > 0.0:
            if a > 0:
                core.zhi[i] = core.zhi[i] + amount(shi) / a
            else:
                core.zlo[i] = max(0.0, core.zlo[i] - amount(shi) / abs(a))
    for j, (slo, shi) in ph1.get("bands", {}).items():
        if slo > 0.0:
            core.band_lo[j] -= amount(slo)
        if shi > 0.0:
            core.band_hi[j] += amount(shi)


def _diagnose_balance(core: _Core) -> tuple[dict[str, float], list[str]]:
    """Exact balance is impossible even with every anchored bound and band relaxed. Minimum-slack LP over
    the kept equations (sign locks only) says where the infeasibility shows; the exact sign test names
    the accounts that cannot close on their own."""
    from scipy.optimize import linprog

    n = len(core.var)
    m = core.m
    a = core.a
    Gx = sp.csr_matrix((core.G.data / a[core.G.indices], core.G.indices, core.G.indptr), shape=core.G.shape)[:m]
    keep = np.flatnonzero(core.eq_of >= 0)
    Im = sp.identity(m, format="csr")
    A_eq = sp.hstack([Gx, Im, -Im]).tocsr()  # A x + b + s+ - s- = 0
    cost = np.concatenate([np.zeros(n), np.ones(2 * m)])
    bounds = [(0.0, None) if ai > 0 else (None, 0.0) for ai in a] + [(0.0, None)] * (2 * m)
    res = linprog(cost, A_eq=A_eq, b_eq=-core.b[keep], bounds=bounds, method="highs-ds")
    slack: dict[str, float] = {}
    msgs: list[str] = []
    if res.status == 0:
        v = res.x
        net = v[n + m :] - v[n : n + m]  # the residual row - col that remains at each account
        for j in np.flatnonzero(np.abs(net) > spec.SLACK_REPORT_TOL):
            slack[core.p.name(int(keep[j]))] = float(net[j])
    else:
        msgs.append(f"diagnostic LP failed: {res.message}")
    locked = _sign_locked(core)
    for name, bi, why in locked:
        slack.setdefault(name, bi)
        msgs.append(f"account {name} cannot close: its fixed entries leave row - col = {bi:+,.4f} crore and {why}")
    if slack:
        msgs.append(
            "exact balance is infeasible; minimum-slack diagnosis: the infeasibility shows at (row - col left, "
            "Rs crore) "
            + ", ".join(f"{k} {v:+,.4f}" for k, v in sorted(slack.items()))
            + " (a counterpart account may be named too; the sign-locked accounts named above are the cause)"
        )
    return slack, msgs


# ---------------------------------------------------------------------------------------------
# phase 2: the dual Newton method
# ---------------------------------------------------------------------------------------------


@dataclass
class _Dual:
    z: np.ndarray
    y: np.ndarray  # (lambda per kept equation, mu per band)
    iterations: int
    converged: bool
    message: str
    path: str = "direct"  # direct | interior-point fallback | proximal fallback


def _evaluate(core: _Core, y: np.ndarray) -> dict[str, Any]:
    """The dual function q and what Newton needs at y = (lambda per kept equation, mu per band):
    q = sum_e min_z [c phi(z) + t z] + lambda.b - sum_k sigma_k(mu_k), sigma_k(mu) = hi_k mu (mu > 0),
    lo_k mu (mu < 0); t = G^T y."""
    c = core.w * np.abs(core.a)
    t = core.GT @ y
    u = -t / c
    lnlo = np.full(len(u), -np.inf)
    np.log(core.zlo, out=lnlo, where=core.zlo > 0)
    lnhi = np.log(core.zhi)
    uc = np.clip(np.clip(u, lnlo, lnhi), -LOG_CAP, LOG_CAP)
    z = np.exp(uc)
    interior = (u > lnlo) & (u < lnhi)
    gz = core.G @ z
    m = core.m
    keep = np.flatnonzero(core.eq_of >= 0)
    nu = y[m:]
    sig = np.zeros(len(nu))
    sig[nu > 0] = nu[nu > 0] * core.band_hi[nu > 0]
    sig[nu < 0] = nu[nu < 0] * core.band_lo[nu < 0]
    phi = c * (z * uc - z + 1.0)
    q = float(np.sum(phi + t * z)) + float(np.sum(y[:m] * core.b[keep])) - float(np.sum(sig))
    f = float(np.sum(phi))  # the primal objective at z(y): f - q is the duality gap the certificate tests
    return {"q": q, "f": f, "z": z, "interior": interior, "res": gz[:m] + core.b[keep], "bs": gz[m:], "c": c}


def _band_grad(nu: np.ndarray, bs: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """Optimality residual of each band multiplier: mu > 0 needs the sum at hi, mu < 0 at lo, mu = 0 the sum
    inside [lo, hi]. Zero where the band is optimal."""
    g = np.zeros(len(nu))
    pos, neg = nu > 0, nu < 0
    zero = ~pos & ~neg
    g[pos] = bs[pos] - hi[pos]
    g[neg] = bs[neg] - lo[neg]
    up, dn = zero & (bs > hi), zero & (bs < lo)
    g[up] = bs[up] - hi[up]
    g[dn] = bs[dn] - lo[dn]
    return g


def _merit(core: _Core, ev: dict[str, Any], nu: np.ndarray) -> float:
    tb, tk = _tolerances(core, ev["z"])
    gb = _band_grad(nu, ev["bs"], core.band_lo, core.band_hi)
    return max(float(np.max(np.abs(ev["res"]) / tb, initial=0.0)), float(np.max(np.abs(gb) / tk, initial=0.0)))


def _gap_rel(ev: dict[str, Any]) -> float:
    """Relative duality gap |f - q| / max(1, |f|) at a dual iterate (the certificate's test, CERT_GAP)."""
    return abs(ev["f"] - ev["q"]) / max(1.0, abs(ev["f"]))


def _row_root(
    t0: np.ndarray,
    g: np.ndarray,
    c: np.ndarray,
    lnlo: np.ndarray,
    lnhi: np.ndarray,
    v0: float,
    start: float,
    target: float,
    ftol: float,
) -> float | None:
    """The root of F(v) = S(v) - target on the side of `start` where it lies, for one dual coordinate v whose
    row has coefficients g on members with t = t0 at v = v0: S(v) = sum g exp(clip(-(t0 + g (v - v0))/c)) is
    continuous and non-increasing in v, flat where every member is clipped. Bracketed between the members'
    breakpoints (where one unclips), then safeguarded Newton with bisection. None if no root exists on that
    side (the coordinate cannot close its row: the Newton method and the certificate then say so)."""

    def S(v: float) -> tuple[float, float]:
        u = -(t0 + g * (v - v0)) / c
        uc = np.clip(np.clip(u, lnlo, lnhi), -LOG_CAP, LOG_CAP)
        z = np.exp(uc)
        inside = (u > lnlo) & (u < lnhi)
        return float(np.sum(g * z)) - target, -float(np.sum(np.where(inside, g * g * z / c, 0.0)))

    fa, _ = S(start)
    if abs(fa) <= ftol:
        return start
    direction = 1.0 if fa > 0 else -1.0
    ends = []
    for L in (lnlo, lnhi):
        fin = np.isfinite(L)
        ends.append(v0 + (-L[fin] * c[fin] - t0[fin]) / g[fin])
    e = np.concatenate(ends)
    e = np.sort(e[(e - start) * direction > 0] * direction) * direction  # breakpoints beyond start, nearest first
    va = start
    vb: float | None = None
    fb = 0.0
    lo_i, hi_i = 0, len(e) - 1
    if len(e) and S(float(e[-1]))[0] * direction <= 0:  # binary search: the first breakpoint past the root
        while lo_i < hi_i:
            mid = (lo_i + hi_i) // 2
            if S(float(e[mid]))[0] * direction <= 0:
                hi_i = mid
            else:
                lo_i = mid + 1
        vb = float(e[lo_i])
        fb = S(vb)[0]
        if lo_i > 0:
            va = float(e[lo_i - 1])
            fa = S(va)[0]
    else:  # beyond every breakpoint: only members without a bound on that side move; expand
        base = float(e[-1]) if len(e) else start
        d = max(abs(base - start), abs(start), 1.0)
        if len(e):
            va, fa = base, S(base)[0]
        for _ in range(64):
            v = base + direction * d
            f = S(v)[0]
            if f * direction <= 0:
                vb, fb = v, f
                break
            va, fa = v, f
            d *= 2.0
        if vb is None:
            return None
    if abs(fb) <= ftol:
        return vb
    for _ in range(200):
        width = abs(vb - va)
        p, fp = (va, fa) if abs(fa) < abs(fb) else (vb, fb)
        dp = S(p)[1]
        vn = p - fp / dp if dp < 0 else math.nan
        if not (min(va, vb) < vn < max(va, vb)):
            vn = 0.5 * (va + vb)
        fn = S(vn)[0]
        if abs(fn) <= ftol:
            return vn
        if fn * direction > 0:
            va, fa = vn, fn
        else:
            vb, fb = vn, fn
        if abs(vb - va) > 0.5 * width:  # Newton did not halve the bracket: bisect once
            vm = 0.5 * (va + vb)
            fm = S(vm)[0]
            if abs(fm) <= ftol:
                return vm
            if fm * direction > 0:
                va, fa = vm, fm
            else:
                vb, fb = vm, fm
        if abs(vb - va) <= 4.0 * np.finfo(np.float64).eps * max(abs(va), abs(vb), 1e-300):
            break
    return vb if abs(fb) <= abs(fa) else va


def _coordinate_steps(
    core: _Core, y: np.ndarray, ev: dict[str, Any], Gind: sp.csr_matrix, *, all_rows: bool = False
) -> int:
    """Exact maximisation of the dual along every coordinate whose Newton model is degenerate (Wave B review
    S-1). A kept account equation or band whose variable members are all clipped at their boxes gets only
    BOUND_CURVATURE of their curvature in the Newton system, although along that coordinate the dual is
    linear up to the breakpoint where a member unclips. The Newton step then overshoots far past it (a
    window of 0.001 crore between a band and an anchored box, which phase-1 widening creates, sent a band
    multiplier to -143) and afterwards crawls back (0.01 per step). Along one coordinate the dual is concave
    with a monotone derivative (the row's residual), so its maximiser is found exactly (_row_root). Rows are
    taken in index order and each sees the moves before it (Gauss-Seidel). Updates y in place; returns the
    number of coordinates moved. The dual value never decreases."""
    m = core.m
    G = core.G
    c = ev["c"]
    t = core.GT @ y
    lnlo = np.full(len(t), -np.inf)
    np.log(core.zlo, out=lnlo, where=core.zlo > 0)
    lnhi = np.log(core.zhi)
    n_int = Gind @ ev["interior"].astype(np.float64)
    tb, tk = _tolerances(core, ev["z"])
    grad = np.concatenate([ev["res"], _band_grad(y[m:], ev["bs"], core.band_lo, core.band_hi)])
    tol = np.concatenate([tb, tk])
    keep = np.flatnonzero(core.eq_of >= 0)
    moved = 0
    for r in np.flatnonzero(((n_int == 0) | all_rows) & (np.abs(grad) > tol)):
        s, e = G.indptr[r], G.indptr[r + 1]
        idx, g = G.indices[s:e], G.data[s:e]
        u = -t[idx] / c[idx]
        if not all_rows and np.any((u > lnlo[idx]) & (u < lnhi[idx])):  # an earlier move unclipped a member
            continue
        v0 = float(y[r])
        args = (t[idx], g, c[idx], lnlo[idx], lnhi[idx], v0)
        ftol = 0.1 * float(tol[r])
        v: float | None
        if r < m:
            v = _row_root(*args, v0, -float(core.b[keep[r]]), ftol)
        else:
            k = r - m
            lo, hi = float(core.band_lo[k]), float(core.band_hi[k])
            s0 = float(np.sum(g * np.exp(np.clip(np.clip(-(t[idx] - g * v0) / c[idx], lnlo[idx], lnhi[idx]),
                                                 -LOG_CAP, LOG_CAP))))  # fmt: skip
            if lo <= s0 <= hi:
                v = 0.0  # the band does not bind along this coordinate
            else:
                v = _row_root(*args, 0.0, hi if s0 > hi else lo, ftol)
                if v is not None and (v if s0 > hi else -v) < 0:
                    v = 0.0  # rounding at the kink
        if v is None or v == v0:
            continue
        t[idx] += g * (v - v0)
        y[r] = v
        moved += 1
    return moved


def _dual_newton_path(core: _Core) -> _Dual:
    """The dual Newton method; if it has not converged after NEWTON_FIRST_TRY steps (a heavily constrained
    problem whose dual is nearly polyhedral: narrow anchored boxes and tight bands), the interior-point
    fallback (DECISIONS D2-23): the primal-dual interior-point method (_interior_point) from scratch, then the
    dual Newton method from its multipliers, which identifies the active set and finishes to the certificate's
    accuracy. If that fails too, the proximal path (_proximal_path) from where the first Newton try stopped,
    then the dual Newton method again. Only the final iterate counts, and it is certified whatever the path."""
    d = _dual_newton(core, max_iter=NEWTON_FIRST_TRY)
    if d.converged:
        return d
    first = f"dual Newton did not converge in {NEWTON_FIRST_TRY} steps ({d.message})"
    ip = _interior_point(core)
    df = _dual_newton(core, y0=ip.y, max_iter=IPM_FINISH)
    if df.converged:
        note = f"{first}; {ip.message}; then dual Newton from its multipliers: converged in {df.iterations} steps"
        return _Dual(df.z, df.y, d.iterations + ip.iterations + df.iterations, True, note, "interior-point fallback")
    first += f"; {ip.message}; then dual Newton from its multipliers: {df.message}"
    dp, nb, _ = _proximal_path(core, d.y)
    its = d.iterations + ip.iterations + df.iterations + nb
    if dp.converged:
        return _Dual(dp.z, dp.y, its, True, f"{first}; {dp.message}", "proximal fallback")
    d2 = _dual_newton(core, y0=dp.y, max_iter=spec.NEWTON_MAX_ITER)
    note = f"{first}; {dp.message}; then dual Newton: {d2.message}"
    return _Dual(d2.z, d2.y, its + d2.iterations, d2.converged, note, "proximal fallback")


@dataclass
class _NewtonData:
    """What one Newton direction of _dual_newton needs (see _newton_direction)."""

    m: int
    K: int
    y: np.ndarray
    nu: np.ndarray  # y[m:]
    H0: sp.csr_matrix  # G D G^T at the current iterate
    hd: np.ndarray  # its diagonal
    floor: float
    free: np.ndarray  # bands whose multiplier may move (the others are held and moved to exactly 0)
    orient: np.ndarray  # +1 / -1 / 0 per band
    grad: np.ndarray  # balance residuals, then the oriented band gradients


def _newton_direction(nd: _NewtonData, rho: float) -> tuple[np.ndarray, float, np.ndarray]:
    """The Newton direction of _dual_newton with Levenberg-Marquardt damping rho: balance rows and free bands; a band
    held at zero moves by -mu (to exactly 0), and any multiplier whose step would cross zero is held too and the rest
    re-solved. Returns the direction, its slope along the oriented gradient, and the held bands."""
    m, K, y, nu, hd, floor = nd.m, nd.K, nd.y, nd.nu, nd.hd, nd.floor
    H = (nd.H0 + sp.diags((1e-10 + rho) * hd + floor)).tocsr()
    step_dir = np.zeros(m + K)
    held = ~nd.free  # prescribed: move to 0
    for _ in range(10):
        R = np.concatenate([np.arange(m), m + np.flatnonzero(~held)])
        P = m + np.flatnonzero(held)
        dP = -y[P]
        rhs = nd.grad[R] - (H[R][:, P] @ dP if len(P) else 0.0)
        try:
            dR = splu(H[R][:, R].tocsc(), permc_spec="COLAMD").solve(rhs)
        except RuntimeError:
            dR = rhs / (hd[R] + floor)
        step_dir[:] = 0.0
        step_dir[R] = dR
        step_dir[P] = dP
        nu_new = nu + step_dir[m:]
        # a multiplier whose step would cross zero is held at exactly 0 and the rest re-solved. That includes a
        # multiplier AT zero whose direction points to the wrong side (Wave C: the line search's projection kept it at
        # 0 while every other coordinate moved as if it had moved, so the step was inconsistent; on the real SAM a
        # violated GFCF band stayed at mu = 0 and the method stalled for 2,220 steps)
        cross = (~held) & (nd.orient != 0) & (nu_new * nd.orient < 0)
        if not np.any(cross):
            break
        held |= cross
    slope = float(np.sum(nd.grad * step_dir))
    if not (slope > 0 and np.all(np.isfinite(step_dir))):
        step_dir = np.where(np.concatenate([np.ones(m, dtype=bool), nd.free]), nd.grad / (hd + floor), 0.0)
        slope = float(np.sum(nd.grad * step_dir))
    return step_dir, slope, held


def _dual_newton(core: _Core, *, y0: np.ndarray | None = None, max_iter: int = spec.NEWTON_MAX_ITER) -> _Dual:
    """Maximise the concave dual q(lambda, mu): a projected semismooth Newton method (Bertsekas 1982).

    Each band multiplier lives on one side of zero at a time (its 'orientation': + when the sum presses
    on hi, - on lo). Per iteration: a multiplier within eps of zero whose gradient points at zero is held
    at 0 (epsilon-active set); the Newton direction is solved on the others; any multiplier whose Newton
    step would cross zero is given the move to exactly 0 instead and the direction is re-solved for the
    rest given that move (so no multiplier creeps towards zero over many damped steps); a multiplier at zero
    whose step points to the wrong side is held at zero the same way (Wave C). Backtracking on
    the dual value (Armijo), or on the scaled gradient norm where the value is flat to machine precision.
    Before the Newton step, coordinates whose members are all clipped are maximised exactly
    (_coordinate_steps, Wave B S-1). It stops when the residuals are within tolerance and the duality gap
    is below GAP_STOP, or GAP_EXTRA steps after the residuals first held (Wave B S-2)."""
    m, K = core.m, core.K
    lo_b, hi_b = core.band_lo, core.band_hi
    GB = core.G[m:]
    absGB2 = abs(GB).multiply(abs(GB)).tocsr()
    Gind = core.G.copy()
    Gind.data = np.ones_like(Gind.data)
    y = np.zeros(m + K) if y0 is None else y0.copy()
    ev = _evaluate(core, y)
    msg = ""
    it = 0
    rho = 0.0  # Levenberg-Marquardt / proximal weight (relative to the Hessian diagonal), adapted per step
    extra = 0  # steps taken since the residuals first held while the duality gap did not (S-2)
    for it in range(1, max_iter + 1):
        nu = y[m:]
        merit = _merit(core, ev, nu)
        if merit <= 1.0:
            # the residuals hold; stop once the duality gap the certificate tests holds as well (a stop inside
            # the residual tolerance does not imply it: gap = -lambda.residual). Full Newton steps close it in
            # one or two; after GAP_EXTRA the certificate decides (on a boundary optimum the gap closes only
            # as z -> 0, and the certificate then refuses the forced zero: S-4)
            if _gap_rel(ev) <= GAP_STOP or extra >= GAP_EXTRA:
                return _Dual(ev["z"], y, it - 1, True, "converged")
            extra += 1
        elif _coordinate_steps(core, y, ev, Gind):  # degenerate rows first (S-1), then the Newton step
            ev = _evaluate(core, y)
            nu = y[m:]
            merit = _merit(core, ev, nu)
            if merit <= 1.0 and _gap_rel(ev) <= GAP_STOP:
                return _Dual(ev["z"], y, it, True, "converged")
        z = ev["z"]
        # curvature: interior entries exactly; entries at a bound get BOUND_CURVATURE of it (rows whose
        # entries all sit at bounds stay solvable and get a sensible step scale; negligible elsewhere)
        d = (z / ev["c"]) * np.where(ev["interior"], 1.0, BOUND_CURVATURE)
        gp = ev["bs"] - hi_b  # gradient of q in mu on the + side (-inf without an upper bound)
        gm = ev["bs"] - lo_b  # on the - side (+inf without a lower bound)
        hkk = absGB2 @ d
        est = np.abs(np.where(nu > 0, gp, np.where(nu < 0, gm, 0.0))) / np.maximum(hkk, 1e-300)
        eps = np.minimum(1e-3, np.nan_to_num(est, nan=1e-3, posinf=1e-3))
        near = np.abs(nu) <= eps
        pos = (nu > eps) | (near & (gp > 0))
        neg = ((nu < -eps) | (near & (gm < 0))) & ~pos
        orient = np.where(pos, 1.0, np.where(neg, -1.0, 0.0))
        gb = np.where(pos, gp, np.where(neg, gm, 0.0))
        free = pos | neg
        H0 = (core.G @ sp.diags(d) @ core.GT).tocsr()
        hd = H0.diagonal()
        floor = 1e-12 * float(np.max(hd, initial=1.0))
        grad_all = np.concatenate([ev["res"], gb])
        nd = _NewtonData(m, K, y, nu, H0, hd, floor, free, orient, grad_all)

        # with damping on (rho > 0), the undamped Newton step is tried first: damping is raised after a short step and
        # relaxed only after a full one, so once raised it could trap the method in short gradient-like steps next to
        # a full Newton step that converges (Wave C: from an interior-point start, merit 127.6 -> 0.005 in one plain
        # step, while the damped method crept for 200 steps)
        if rho > 0:
            d0, s0, h0 = _newton_direction(nd, 0.0)
            if s0 > 0 and np.all(np.isfinite(d0)):
                yn = y + d0
                nun = yn[m:]
                nun[h0 | ((orient != 0) & (nun * orient < 0))] = 0.0
                evn = _evaluate(core, yn)
                flat = evn["q"] >= ev["q"] - 1e-12 * max(1.0, abs(ev["q"]))
                if evn["q"] >= ev["q"] + 1e-4 * s0 or (flat and _merit(core, evn, nun) <= 0.75 * merit):
                    y, ev, rho = yn, evn, 0.0
                    continue
        step_dir, slope, held = _newton_direction(nd, rho)
        step = 1.0
        accepted = False
        yn, evn = y, ev
        for _ in range(80):
            yn = y + step * step_dir
            nun = yn[m:]
            # projection: a multiplier stops at zero; so does a held one whose own scaled-gradient step at this step
            # length reaches zero (the projection arc; Wave C: moved linearly with the step, a held 1e-13 multiplier
            # was only halved at every short step and, read as binding, dominated the residual for hundreds of steps)
            nun[(held & (np.abs(nu) <= step * est)) | ((orient != 0) & (nun * orient < 0))] = 0.0
            evn = _evaluate(core, yn)
            # Armijo on the dual value; or, where the value is flat to machine precision (near the optimum: its
            # changes are rounding noise), a step that cuts the scaled gradient norm by a quarter of the step
            # without lowering the value beyond rounding (Wave B: a full step that cut it from 10 to 6 was
            # refused under the old 'halve it' rule, and the method stalled at merit 10)
            flat = evn["q"] >= ev["q"] - 1e-12 * max(1.0, abs(ev["q"]))
            if evn["q"] >= ev["q"] + 1e-4 * step * slope or (
                flat and _merit(core, evn, nun) <= (1.0 - 0.25 * step) * merit
            ):
                accepted = True
                break
            step *= 0.5
        if not accepted:
            msg = f"line search failed at iteration {it} (merit {merit:.3g})"
            break
        # a short accepted step means the Newton model is poor here (a degenerate or kinked region): damp the
        # next direction towards scaled gradient ascent; a full step relaxes the damping again
        rho = min(RHO_CAP, max(4.0 * rho, 1e-3)) if step < 0.25 else (rho / 4.0 if step == 1.0 else rho)
        if rho < 1e-8:
            rho = 0.0
        y, ev = yn, evn
        if rho >= RHO_CAP:
            # the damping is at its cap: the Newton model is useless here (a degenerate cluster: more active bands
            # and boxes than free directions, e.g. a one-entry band and a two-entry band on the same livestock
            # cells, both at a bound after phase-1 widening), and damped steps only creep (Wave C). Exact
            # maximisation of the dual along every row still off its tolerance (Gauss-Seidel, as in S-1, now for
            # any row), which always raises the dual; then Newton again, undamped
            if _coordinate_steps(core, y, ev, Gind, all_rows=True):
                ev = _evaluate(core, y)
            rho = 0.0
    else:
        msg = f"no convergence in {max_iter} iterations"
    ok = _merit(core, ev, y[m:]) <= 1.0
    return _Dual(ev["z"], y, it, ok, "converged" if ok else msg)


def _evaluate_prox(core: _Core, y: np.ndarray, tau: np.ndarray, eps: np.ndarray) -> dict[str, Any]:
    """The dual of the proximal problem: each band sum s_k in [lo_k, hi_k] carries the cost eps_k/2 (s_k -
    tau_k)^2, so its dual term is smooth (s_k = clip(tau_k + mu_k/eps_k, lo_k, hi_k))."""
    ev = _evaluate(core, np.concatenate([y[: core.m], np.zeros(core.K)]))  # entries and balance (mu enters t below)
    c = ev["c"]
    t = core.GT @ y
    u = -t / c
    lnlo = np.full(len(u), -np.inf)
    np.log(core.zlo, out=lnlo, where=core.zlo > 0)
    lnhi = np.log(core.zhi)
    uc = np.clip(np.clip(u, lnlo, lnhi), -LOG_CAP, LOG_CAP)
    z = np.exp(uc)
    interior = (u > lnlo) & (u < lnhi)
    gz = core.G @ z
    m = core.m
    keep = np.flatnonzero(core.eq_of >= 0)
    nu = y[m:]
    s_un = tau + nu / eps
    sk = np.clip(s_un, core.band_lo, core.band_hi)
    inside = (s_un > core.band_lo) & (s_un < core.band_hi)
    q = (float(np.sum(c * (z * uc - z + 1.0) + t * z)) + float(np.sum(y[:m] * core.b[keep]))
         + float(np.sum(0.5 * eps * (sk - tau) ** 2 - nu * sk)))  # fmt: skip
    return {"q": q, "z": z, "interior": interior, "res": gz[:m] + core.b[keep], "bs": gz[m:], "s": sk,
            "inside": inside, "c": c}  # fmt: skip


def _proximal_path(core: _Core, y0: np.ndarray, *, outer: int = 60, inner: int = 40) -> tuple[_Dual, int, str]:
    """Proximal method of multipliers for the bands (a fallback when the active-set Newton method churns on
    a degenerate, heavily constrained problem). Each outer step solves the smooth proximal problem (above)
    by semismooth Newton, warm-started, then moves every centre tau_k to the band sum it found; at the fixed
    point s_k = tau_k the proximal term vanishes and the solution is that of the real problem. eps_k starts
    at the inverse of the entries' curvature of band k (a well-conditioned first problem) and shrinks by
    PROX_SHRINK per outer step (superlinear convergence); after each outer step the exact dual Newton
    method is tried from there for PROX_FINISH steps."""
    m = core.m
    y = y0.copy()
    ev0 = _evaluate(core, y)
    d0 = (ev0["z"] / ev0["c"]) * np.where(ev0["interior"], 1.0, BOUND_CURVATURE)
    GB = core.G[m:]
    hkk = abs(GB).multiply(abs(GB)) @ d0
    eps = PROX_WEIGHT / np.maximum(hkk, 1e-12)
    eps_floor = eps * 1e-8
    tau = np.clip(ev0["bs"], core.band_lo, core.band_hi)
    steps = 0
    for k_out in range(1, outer + 1):
        ev = _evaluate_prox(core, y, tau, eps)
        for _ in range(inner):
            tb, tk = _tolerances(core, ev["z"])
            gb = ev["bs"] - ev["s"]
            mer = max(float(np.max(np.abs(ev["res"]) / tb, initial=0.0)), float(np.max(np.abs(gb) / tk, initial=0.0)))
            if mer <= 1.0:
                break
            d = (ev["z"] / ev["c"]) * np.where(ev["interior"], 1.0, BOUND_CURVATURE)
            H = (core.G @ sp.diags(d) @ core.GT).tocsr()
            hd = H.diagonal()
            extra = np.concatenate([np.zeros(m), np.where(ev["inside"], 1.0 / eps, 0.0)])
            H = H + sp.diags(extra + 1e-10 * hd + 1e-12 * float(np.max(hd, initial=1.0)))
            grad = np.concatenate([ev["res"], gb])
            try:
                dirn = splu(H.tocsc(), permc_spec="COLAMD").solve(grad)
            except RuntimeError:
                dirn = grad / (hd + extra + 1e-300)
            slope = float(np.sum(grad * dirn))
            step, ok = 1.0, False
            for _ in range(60):
                yn = y + step * dirn
                evn = _evaluate_prox(core, yn, tau, eps)
                if evn["q"] >= ev["q"] + 1e-4 * step * slope:
                    ok = True
                    break
                if step == 1.0 and evn["q"] >= ev["q"] - 1e-12 * max(1.0, abs(ev["q"])):
                    tbn, tkn = _tolerances(core, evn["z"])
                    mern = max(float(np.max(np.abs(evn["res"]) / tbn, initial=0.0)),
                               float(np.max(np.abs(evn["bs"] - evn["s"]) / tkn, initial=0.0)))  # fmt: skip
                    if mern <= 0.5 * mer:
                        ok = True
                        break
                step *= 0.5
            steps += 1
            if not ok:
                break
            y, ev = yn, evn
        # the real problem: done when its own (kinked) optimality holds, duality gap included (S-2)
        d_real = _evaluate(core, _real_multipliers(core, y, ev))
        yr = _real_multipliers(core, y, ev)
        if _merit(core, d_real, yr[m:]) <= 1.0 and _gap_rel(d_real) <= GAP_STOP:
            return _Dual(d_real["z"], yr, steps, True, f"proximal path: {k_out} outer steps"), steps, "ok"
        # try to finish with the exact method from here (it converges fast once the active set is right)
        dn = _dual_newton(core, y0=yr, max_iter=PROX_FINISH)
        steps += dn.iterations
        if dn.converged:
            return _Dual(dn.z, dn.y, steps, True, f"proximal path: {k_out} outer steps, then dual Newton"), steps, "ok"
        tau = ev["s"].copy()
        eps = np.maximum(eps * PROX_SHRINK, eps_floor)  # a shrinking proximal weight: superlinear convergence
    ev = _evaluate(core, y)
    return _Dual(ev["z"], y, steps, False, f"proximal path: no convergence in {outer} outer steps"), steps, "no"


def _real_multipliers(core: _Core, y: np.ndarray, ev: dict[str, Any]) -> np.ndarray:
    """A proximal iterate's multipliers as multipliers of the real problem: a band whose sum is strictly
    inside its interval has mu = 0 there."""
    yr = y.copy()
    nu = yr[core.m :]
    nu[ev["inside"]] = 0.0
    return yr


# ---------------------------------------------------------------------------------------------
# the interior-point fallback (DECISIONS D2-23)
# ---------------------------------------------------------------------------------------------


def _interior_point(core: _Core) -> _Dual:
    """The interior-point fallback (DECISIONS D2-23): a log-barrier path-following method, solved on the dual.

    Every box and band gets a logarithmic barrier with weight tau: entry e adds -tau c_e ln(z_e - zlo_e) and
    -tau c_e ln(zhi_e - z_e) (finite bounds only), band k adds -tau g_k ln((s_k - lo_k) / g_k) and
    -tau g_k ln((hi_k - s_k) / g_k) for its sum s_k, g_k being the band's gross flow. The weights put every
    barrier in the problem's own dimensionless units (ln z for an entry, z-like for a band), so objective weights
    spanning eleven orders of magnitude do not matter (review F1). For fixed tau the dual in y = (lambda, mu) is
    smooth and strictly concave: the entries' z_e(y) and the bands' s_k(y) are unique interior points (a scalar
    root per entry, a quadratic per band), so the kinks that ~1,000 narrow anchored boxes and tight bands put into
    the exact dual are gone, and Newton's method with a line search converges from anywhere. tau starts at
    IPM_TAU0 and shrinks by IPM_SHRINK per stage (warm-started) down to IPM_TAU_END; along the way the primal
    point never leaves the interior of the boxes and bands, so no primal infeasibility has to be repaired (a
    primal-dual method in z stalled at step lengths of 1e-9 on the verifier's generator problems for exactly that
    reason). The result is only a starting point: the exact dual Newton method finishes from its multipliers and
    the KKT certificate decides. Floating-point warnings are silenced (a z or a distance to a bound can underflow
    on a boundary optimum); a non-finite dual value ends the stage."""
    with np.errstate(over="ignore", divide="ignore", invalid="ignore", under="ignore"):
        return _barrier_path(core)


@dataclass
class _Barrier:
    """The data of the barrier problem (see _interior_point)."""

    c: np.ndarray  # w |a| per variable entry
    b: np.ndarray  # constant part of each kept balance equation
    zlo: np.ndarray
    zhi: np.ndarray
    hasl: np.ndarray  # entry has a lower bound > 0 (z > 0 is the entropy's own domain)
    hasu: np.ndarray
    lo: np.ndarray  # band bounds (after widening)
    hi: np.ndarray
    we: np.ndarray  # barrier scale of an entry's box (z units): its width, or zhi when only z <= zhi binds
    wk: np.ndarray  # barrier scale of a band (Rs crore): half its width, or 1 crore for a one-sided band
    bl: np.ndarray  # band has a finite lower bound (and is not an equality)
    bu: np.ndarray
    eqb: np.ndarray  # zero-width band: its sum is fixed (no barrier)


def _barrier_data(core: _Core) -> _Barrier:
    lo, hi = core.band_lo, core.band_hi
    bl, bu = np.isfinite(lo), np.isfinite(hi)
    mag = np.maximum(np.abs(np.where(bl, lo, 0.0)), np.abs(np.where(bu, hi, 0.0)))
    eqb = bl & bu & (hi - lo <= 1e-12 * np.maximum(1.0, mag))
    return _Barrier(
        c=core.w * np.abs(core.a), b=core.b[np.flatnonzero(core.eq_of >= 0)], zlo=core.zlo, zhi=core.zhi,
        hasl=core.zlo > 0, hasu=np.isfinite(core.zhi), lo=lo, hi=hi,
        we=np.where((core.zlo > 0) & np.isfinite(core.zhi), core.zhi - core.zlo,
                    np.where(np.isfinite(core.zhi), core.zhi, 1.0)),
        wk=np.where(bl & bu & ~eqb, 0.5 * (hi - lo), spec.MATERIAL_CHANGE), bl=bl & ~eqb, bu=bu & ~eqb, eqb=eqb,
    )  # fmt: skip


def _barrier_z(S: _Barrier, u: np.ndarray, tau: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Per entry: z minimising z ln z - z + u z - tau ln(z - zlo) - tau ln(zhi - z) (finite bounds only), i.e. the
    root of ln z + u - tau / (z - zlo) + tau / (zhi - z) = 0, increasing in z: closed form without bounds,
    otherwise safeguarded Newton inside a shrinking bracket (vectorised). Returns z, 1 / (1/z + tau/dl^2 +
    tau/du^2) (so that dz/dt = that / c), and the distances dl, du to the bounds."""
    z = np.exp(np.clip(-u, -LOG_CAP, LOG_CAP))
    boxed = np.flatnonzero(S.hasl | S.hasu)
    if len(boxed):
        hl, hu = S.hasl[boxed], S.hasu[boxed]
        L = np.where(hl, S.zlo[boxed], 0.0)
        U = np.where(hu, S.zhi[boxed], np.inf)
        ui = u[boxed]
        tw = tau * S.we[boxed]
        zz = z[boxed]
        top = np.where(np.isfinite(U), U, np.maximum(2.0 * zz, 2.0 * L + 1.0))
        zz = np.where((zz > L) & (zz < U), zz, 0.5 * (L + top))
        lo_b, hi_b = L.copy(), U.copy()
        for _ in range(200):
            ulp = np.spacing(zz)
            dl, du = np.maximum(zz - L, ulp), np.maximum(U - zz, ulp)
            F = np.log(zz) + ui - np.where(hl, tw / dl, 0.0) + np.where(hu, tw / du, 0.0)
            Fp = 1.0 / zz + np.where(hl, tw / dl**2, 0.0) + np.where(hu, tw / du**2, 0.0)
            lo_b = np.where(F < 0, zz, lo_b)
            hi_b = np.where(F > 0, zz, hi_b)
            hb = np.where(np.isfinite(hi_b), hi_b, np.maximum(2.0 * zz, 1.0))
            zn = zz - F / Fp
            zn = np.where((zn > lo_b) & (zn < hb) & np.isfinite(zn), zn, 0.5 * (lo_b + hb))
            done = (np.abs(zn - zz) <= 1e-15 * zz) | (F == 0)
            zz = zn
            if np.all(done):
                break
        z[boxed] = zz
    # a distance below the spacing of z is not representable (a 3e-7-wide box at tau = 1e-12 puts z within 1e-19
    # of its bound): floored there, so that the barrier stays finite
    ulp = np.spacing(z)
    dl = np.where(S.hasl, np.maximum(z - S.zlo, ulp), np.inf)
    du = np.where(S.hasu, np.maximum(S.zhi - z, ulp), np.inf)
    tw = tau * S.we
    inv = 1.0 / (1.0 / z + np.where(S.hasl, tw / dl**2, 0.0) + np.where(S.hasu, tw / du**2, 0.0))
    return z, inv, dl, du


def _barrier_s(S: _Barrier, mu: np.ndarray, tau: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Per band: the sum s minimising -mu s - tau g ln((s - lo)/g) - tau g ln((hi - s)/g). With x = (s - lo)/g and
    W = (hi - lo)/g: mu x^2 + (2 tau - mu W) x - tau W = 0 (the root in (0, W), computed without cancellation);
    one-sided: x = -tau/mu (needs mu < 0) or (hi - s)/g = tau/mu (needs mu > 0). An equality band's sum is its
    bound. Returns s, ds/dmu, and the normalised distances to lo and hi."""
    both = S.bl & S.bu
    W = np.where(both, (S.hi - S.lo) / S.wk, 0.0)
    # the distance to the bound the sum presses on is computed directly (no cancellation), the other as W minus it
    disc = np.sqrt(4.0 * tau * tau + (mu * W) ** 2)
    near = 2.0 * tau * W / (2.0 * tau + np.abs(mu) * W + disc)
    x = np.where(mu > 0, W - near, near)  # mu > 0 presses on hi
    only_l, only_u = S.bl & ~S.bu, S.bu & ~S.bl
    xl = np.where(both, x, np.where(only_l, -tau / np.where(only_l, mu, -1.0), np.inf))
    xu = np.where(both, np.where(mu > 0, near, W - near), np.where(only_u, tau / np.where(only_u, mu, 1.0), np.inf))
    s = np.where(S.bl, S.lo + S.wk * xl, np.where(S.bu, S.hi - S.wk * xu, np.where(S.eqb, S.lo, 0.0)))
    fpp = np.where(S.bl, tau / (S.wk * xl**2), 0.0) + np.where(S.bu, tau / (S.wk * xu**2), 0.0)
    ds = np.where(S.eqb | ~(fpp > 0), 0.0, 1.0 / np.where(fpp > 0, fpp, 1.0))
    return s, ds, xl, xu


def _barrier_eval(core: _Core, S: _Barrier, y: np.ndarray, tau: float) -> dict[str, Any]:
    """The smooth dual q_tau(y) and what Newton needs: its gradient (balance residuals; band sum G_B z - s) and the
    curvatures (dz/dt per entry, ds/dmu per band)."""
    m = core.m
    t = core.GT @ y
    z, inv, dl, du = _barrier_z(S, t / S.c, tau)
    mu = y[m:]
    s, ds, xl, xu = _barrier_s(S, mu, tau)
    phi = S.c * (z * np.log(z) - z + 1.0) - tau * S.c * S.we * (np.where(S.hasl, np.log(dl), 0.0)
                                                                + np.where(S.hasu, np.log(du), 0.0))  # fmt: skip
    bar = -tau * S.wk * (np.where(S.bl, np.log(xl), 0.0) + np.where(S.bu, np.log(xu), 0.0))
    q = float(np.sum(phi + t * z)) + float(np.sum(y[:m] * S.b)) + float(np.sum(bar - mu * s))
    gz = core.G @ z
    return {"q": q, "z": z, "D": inv / S.c, "ds": ds, "grad": np.concatenate([gz[:m] + S.b, gz[m:] - s])}


def _barrier_path(core: _Core) -> _Dual:
    m, K = core.m, core.K
    S = _barrier_data(core)
    y = np.zeros(m + K)
    lower_only, upper_only = S.bl & ~S.bu, S.bu & ~S.bl
    y[m:][lower_only] = -IPM_TAU0  # the dual domain of a one-sided band: mu < 0 (a floor) or mu > 0 (a cap)
    y[m:][upper_only] = IPM_TAU0

    def in_domain(v: np.ndarray) -> bool:
        return bool(np.all(v[m:][lower_only] < 0) and np.all(v[m:][upper_only] > 0))

    def merit_of(e: dict[str, Any]) -> float:
        tb, tk = _tolerances(core, e["z"])
        r = np.abs(e["grad"]) / np.concatenate([tb, tk])
        return float(np.max(r, initial=0.0)) if np.all(np.isfinite(r)) else math.inf

    tau, steps, stages, merit = IPM_TAU0, 0, 0, math.inf
    notes: list[str] = []
    while True:
        stages += 1
        final = tau <= IPM_TAU_END
        ev = _barrier_eval(core, S, y, tau)
        for _ in range(IPM_STAGE_STEPS):
            merit = merit_of(ev)
            if merit <= IPM_STAGE_MERIT or not math.isfinite(ev["q"]):
                break
            H = (core.G @ sp.diags(ev["D"]) @ core.GT + sp.diags(np.concatenate([np.zeros(m), ev["ds"]]))).tocsr()
            hd = H.diagonal()
            sc = 1.0 / np.sqrt(np.maximum(hd, 1e-300))
            Hs = (sp.diags(sc) @ H @ sp.diags(sc) + sp.identity(m + K, format="csr") * 1e-13).tocsc()
            try:
                d = sc * splu(Hs, permc_spec="COLAMD").solve(sc * ev["grad"])
            except RuntimeError:
                d = ev["grad"] / np.maximum(hd, 1e-300)
            slope = float(ev["grad"] @ d)
            step, accepted = 1.0, False
            yn, evn = y, ev
            for _ in range(60):
                yn = y + step * d
                if in_domain(yn):
                    evn = _barrier_eval(core, S, yn, tau)
                    # Armijo on the smooth dual; where it is flat to rounding, a cut in the scaled residual
                    flat = evn["q"] >= ev["q"] - 1e-12 * max(1.0, abs(ev["q"]))
                    armijo = evn["q"] >= ev["q"] + 1e-4 * step * slope
                    if math.isfinite(evn["q"]) and (armijo or (flat and merit_of(evn) <= (1.0 - 0.25 * step) * merit)):
                        accepted = True
                        break
                step *= 0.5
            steps += 1
            if not accepted:
                notes.append(f"line search failed at barrier weight {tau:.0e}")
                break
            y, ev = yn, evn
        merit = merit_of(ev)
        if not merit <= IPM_STAGE_MERIT:
            notes.append(f"barrier weight {tau:.0e}: residual {merit:.2g} x its tolerance after {IPM_STAGE_STEPS} "
                         "steps")  # fmt: skip
        if final:
            break
        tau = max(tau * IPM_SHRINK, IPM_TAU_END)
    ok = merit <= IPM_STAGE_MERIT
    # hand-over: a band multiplier this small is the barrier's trace of a band that does not bind (mu = tau w /
    # distance to the bound; a one-sided band's barrier needs mu != 0, the exact problem does not). Handed over as
    # exactly 0; otherwise the exact method reads it as 'binding' and halves it step by step instead of dropping it
    # (seen on the real SAM with Z halved and noise: 1e-13 multipliers on factors' floors and caps held it for 200
    # steps)
    nu = y[m:]
    nu[np.abs(nu) <= IPM_MU_ZERO] = 0.0
    msg = (f"interior point (log-barrier path on the dual): {stages} stages down to barrier weight {tau:.0e}, "
           f"{steps} Newton steps, residual {merit:.2g} x its tolerance"
           + (f" ({'; '.join(notes[:3])})" if notes else ""))  # fmt: skip
    return _Dual(ev["z"], y, steps, ok, msg, "interior-point fallback")


# ---------------------------------------------------------------------------------------------
# the cvxpy override
# ---------------------------------------------------------------------------------------------


def _cvxpy_solve(core: _Core, solver: str, scale: float, options: dict[str, Any]) -> dict[str, Any]:
    import cvxpy as cp

    n, m = len(core.var), core.m
    a = core.a * scale
    keep = np.flatnonzero(core.eq_of >= 0)
    Gs = core.G * scale
    z = cp.Variable(n, nonneg=True)
    cost = core.w * np.abs(a)
    cons = []
    if m:
        cons.append(Gs[:m] @ z + core.b[keep] * scale == 0)
    an = np.flatnonzero(np.isfinite(core.zhi))
    if len(an):
        cons += [z[an] >= core.zlo[an], z[an] <= core.zhi[an]]
    if core.K:
        B = Gs[m:]
        k = np.flatnonzero(np.isfinite(core.band_hi))
        if len(k):
            cons.append(B[k] @ z <= core.band_hi[k] * scale)
        k = np.flatnonzero(np.isfinite(core.band_lo))
        if len(k):
            cons.append(B[k] @ z >= core.band_lo[k] * scale)
    prob = cp.Problem(cp.Minimize(cp.sum(cp.multiply(cost, -cp.entr(z) - z + 1))), cons)
    try:
        prob.solve(solver=solver, **options)
        status = prob.status
    except cp.error.SolverError as e:
        status = f"solver_error: {e}"
    stats = prob.solver_stats
    out = {"status": status, "iterations": getattr(stats, "num_iters", None) if stats is not None else None, "z": None}
    if status in ("optimal", "optimal_inaccurate") and z.value is not None:
        out["z"] = np.maximum(np.asarray(z.value, dtype=np.float64), 0.0)
    return out


def _recover_multipliers(core: _Core, z: np.ndarray, tol_b: np.ndarray) -> np.ndarray:
    """Least-squares multipliers for a solution from another solver: for entries strictly inside their
    box, ln z_e = -(G^T y)_e / c_e. Bands at a bound get a multiplier, others 0."""
    m, K = core.m, core.K
    c = core.w * np.abs(core.a)
    inside = (z > core.zlo * (1 + 1e-9) + 1e-300) & (z < core.zhi * (1 - 1e-9))
    bs = (core.G @ z)[m:]
    at = (np.abs(bs - core.band_hi) <= tol_b) | (np.abs(bs - core.band_lo) <= tol_b)
    cols = np.concatenate([np.arange(m), m + np.flatnonzero(at)])
    Gs = core.G[cols][:, np.flatnonzero(inside)]
    Gs = Gs @ sp.diags(1.0 / c[inside])
    rhs = -np.log(z[inside])
    N = (Gs @ Gs.T).tocsc()
    diag = N.diagonal()
    N = N + sp.diags(1e-12 * diag + 1e-12 * float(np.max(diag, initial=1.0)))
    y = np.zeros(m + K)
    if len(cols):
        y[cols] = splu(N, permc_spec="COLAMD").solve(Gs @ rhs)
    return y


# ---------------------------------------------------------------------------------------------
# certificate
# ---------------------------------------------------------------------------------------------


def kkt_certificate(core: _Core, z: np.ndarray, y: np.ndarray, *, override: bool = False) -> dict[str, Any]:
    """Proof of optimality of z for the (widened) problem, whatever produced it: primal feasibility,
    stationarity of every entry not at a bound, the sign condition at bounds, complementary band
    multipliers with the right sign, and the duality gap (<= CERT_GAP). Any failure fails the run. A
    material entry (|prior| >= MATERIAL_CHANGE) below BOUNDARY_Z of its prior is refused too: the
    constraints force it to zero, where no dual optimum exists, and the SAM would need a new structural
    zero (an ever smaller z can still show a small gap, so this is tested explicitly: S-4). Immaterial
    ones are counted (and listed by the caller), not refused."""
    m = core.m
    loose = 1e3 if override else 1.0
    kt = spec.KKT_TOL_OVERRIDE if override else spec.KKT_TOL
    c = core.w * np.abs(core.a)
    gz = core.G @ z
    keep = np.flatnonzero(core.eq_of >= 0)
    res = gz[:m] + core.b[keep]
    tb, tk = _tolerances(core, z)
    tb, tk = tb * loose, tk * loose
    bs = gz[m:]
    over = np.maximum(bs - core.band_hi, core.band_lo - bs)
    # a band multiplier counts only with the band sum at the matching bound (complementarity); any other
    # multiplier is set to zero here, and the stationarity test below then shows whether it mattered
    nu = y[m:].copy()
    comp_ok = ((nu > 0) & (np.abs(bs - core.band_hi) <= tk)) | ((nu < 0) & (np.abs(bs - core.band_lo) <= tk))
    dropped = (nu != 0) & ~comp_ok
    nu[dropped] = 0.0
    y_eff = np.concatenate([y[:m], nu])
    t = core.GT @ y_eff
    with np.errstate(divide="ignore"):
        lnz = np.log(z)
    r = lnz + t / c  # d/dz of the Lagrangian, divided by c: 0 inside the box
    rel = 1e-9 if not override else 1e-6
    at_hi = np.isfinite(core.zhi) & (z >= core.zhi * (1 - rel))
    at_lo = (core.zlo > 0) & (z <= core.zlo * (1 + rel))
    inside = ~at_hi & ~at_lo
    stat = float(np.max(np.abs(r[inside]), initial=0.0))
    sign_hi = float(np.max(r[at_hi], initial=0.0))  # at the upper bound the derivative must be <= 0
    sign_lo = float(np.max(-r[at_lo], initial=0.0))  # at the lower bound >= 0
    wrong_sign = dropped & (np.abs(y[m:]) > kt * float(np.min(core.w, initial=1.0)))
    box = float(np.max(np.maximum(core.zlo - z, z - core.zhi) * np.abs(core.a), initial=0.0))
    f = float(np.sum(c * np.where(z > 0, z * lnz, 0.0) - c * z + c))
    gap = f - _evaluate(core, y)["q"] if not override else float("nan")
    out = {
        "stationarity": stat,
        "sign_at_upper_bounds": sign_hi,
        "sign_at_lower_bounds": sign_lo,
        "max_balance_residual": float(np.max(np.abs(res), initial=0.0)),
        "max_band_violation": float(max(0.0, np.max(over, initial=0.0))),
        "max_box_violation": box,
        "non_complementary_bands": int(np.sum(wrong_sign)),
        "entries_at_bounds": int(np.sum(at_hi | at_lo)),
        "entries_forced_to_zero": int(np.sum((z < BOUNDARY_Z) & (np.abs(core.a) >= spec.MATERIAL_CHANGE))),
        "immaterial_entries_forced_to_zero": int(np.sum((z < BOUNDARY_Z) & (np.abs(core.a) < spec.MATERIAL_CHANGE))),
        "duality_gap_rel": float(abs(gap) / max(1.0, abs(f))) if not override else None,
        "tolerance": kt,
    }
    ok = (
        stat <= kt
        and sign_hi <= kt
        and sign_lo <= kt
        and bool(np.all(np.abs(res) <= tb))
        and bool(np.all(over <= tk))
        and box <= float(np.max(tb, initial=spec.NEWTON_TOL_ABS))
        and out["non_complementary_bands"] == 0
        and out["entries_forced_to_zero"] == 0
        and (override or out["duality_gap_rel"] <= CERT_GAP)
    )
    out["ok"] = bool(ok)
    return out


def _fixed_only_violations(p: Problem) -> dict[str, tuple[float, float, int]]:
    """Constraints none of whose entries can move (fixed, zero or no entries at all) and whose sum lies outside
    the band: constraint id -> (signed violation, sum, number of entries), Rs crore. Known exactly, without a
    solve (Wave B review S-6); phase 1 cannot see them (it has no variable to put slack on)."""
    var = p.variable()
    out: dict[str, tuple[float, float, int]] = {}
    for c in p.constraints:
        if np.any(var[c.members]):
            continue
        s = float(np.sum(p.prior[c.members]))
        v = s - c.hi if s > c.hi else (s - c.lo if s < c.lo else 0.0)
        if abs(v) > spec.NEWTON_TOL_ABS:
            out[c.constraint_id] = (v, s, len(c.members))
    return out


def _entry_names(core: _Core, z: np.ndarray, idx: np.ndarray, limit: int = 10) -> str:
    p = core.p

    def name(i: int) -> str:
        e = int(core.var[i])
        return f"entry {e} ({p.name(int(p.row[e]))} <- {p.name(int(p.col[e]))}, prior {core.a[i]:,.6g}) z={z[i]:.3g}"

    more = f" and {len(idx) - limit} more" if len(idx) > limit else ""
    return ", ".join(name(int(i)) for i in idx[:limit]) + more


def _smallest_z_note(core: _Core, z: np.ndarray, k: int = 5) -> str:
    """For a failed run: the entries forced to (almost) zero, or else those with the smallest z, named, and
    what that means (Wave B review S-4)."""
    order = np.argsort(z, kind="stable")
    forced = order[z[order] < BOUNDARY_Z]
    if len(forced):
        return (
            f"entries balanced to below {BOUNDARY_Z:g} of their prior: {_entry_names(core, z, forced)}. The "
            "constraints force them to zero (a boundary optimum: balance or a band leaves them no room, e.g. an "
            "account whose fixed receipts and payments already match, or a max-0 band on a positive entry). No "
            "dual optimum exists there (a sign lock at the boundary), and an entry with a prior of Rs "
            f"{spec.MATERIAL_CHANGE:g} crore or more is refused. Make the cell a structural zero (drop the entry) "
            "or correct the data or constraint that forces it"
        )
    return (
        f"smallest z: {_entry_names(core, z, order[:k])}; no entry is near zero: a degenerate, heavily "
        "constrained problem (FRAMEWORK_REQUESTS.md, WA-1: merge redundant or nested constraints in the "
        "owning block)"
    )


def _immaterial_zero_note(core: _Core, z: np.ndarray) -> str | None:
    """For a certified run: the immaterial entries (prior below MATERIAL_CHANGE) the constraints forced to
    (almost) zero. Accepted, but a finding: the constraint that forces them is worth a look (S-4)."""
    order = np.argsort(z, kind="stable")
    idx = order[(z[order] < BOUNDARY_Z) & (np.abs(core.a[order]) < spec.MATERIAL_CHANGE)]
    if not len(idx):
        return None
    return (
        f"entries with a prior below Rs {spec.MATERIAL_CHANGE:g} crore balanced to below {BOUNDARY_Z:g} of their "
        f"prior (the constraints force them to zero; immaterial, so accepted): {_entry_names(core, z, idx)}"
    )


# ---------------------------------------------------------------------------------------------
# cross-entropy: the whole procedure
# ---------------------------------------------------------------------------------------------


def cross_entropy(
    problem: Problem, *, solver: str = spec.DEFAULT_SOLVER, scale: float = spec.SCALE, options: dict | None = None
) -> Solution:
    """Balance (module doc steps 0-4). Never raises on infeasibility: it reports, and `ok` is False. BLAS is
    pinned to one thread throughout (single_threaded_blas)."""
    with single_threaded_blas():
        return _cross_entropy(problem, solver=solver, scale=scale, options=options)


def _cross_entropy(problem: Problem, *, solver: str, scale: float, options: dict | None) -> Solution:
    p = problem
    msgs: list[str] = []
    x = p.prior.astype(np.float64).copy()
    core = _core(p)
    fixed_res = {
        p.name(int(np.flatnonzero(core.sink & (core.labels == k))[0])): float(core.comp_b[k])
        for k in range(len(core.comp_b))
        if spec.NEWTON_TOL_ABS < abs(core.comp_b[k]) <= spec.BALANCE_TOL
    }
    for k, v in sorted(fixed_res.items()):
        msgs.append(f"account {k}: its component's fixed entries leave {v:+.6f} crore (within the balance tolerance)")

    def fail(status: str, slack: dict[str, float], extra: list[str], ph1: dict | None = None) -> Solution:
        return Solution(
            x=x, status=status, solver=solver, objective=None, iterations=0, balance_slack=slack,
            band_violation=band_violations(p, x), anchor_violation=anchor_violations(p, x), polish={"applied": False},
            max_imbalance=float(np.max(np.abs(p.residual(x)), initial=0.0)), messages=msgs + extra,
            certificate={"ok": False}, phase1=ph1 or {}, fixed_residuals=fixed_res,
        )  # fmt: skip

    # step 0: components whose fixed parts do not close
    bad = [k for k in range(len(core.comp_b)) if abs(core.comp_b[k]) > spec.BALANCE_TOL]
    if bad:
        slack: dict[str, float] = {}
        extra = []
        for k in bad:
            names = _component_names(core, k)
            snk = p.name(int(np.flatnonzero(core.sink & (core.labels == k))[0]))
            slack[snk] = float(core.comp_b[k])
            extra.append(
                f"accounts {', '.join(names)} are linked to the rest of the SAM only through fixed entries (or not "
                f"at all), and their fixed entries leave row - col = {core.comp_b[k]:+,.4f} crore in total: exact "
                f"balance is impossible (reported at {snk})"
            )
        return fail("infeasible", slack, extra)

    # step 0, constraints: a constraint over entries that cannot move is violated or not, exactly (S-6)
    fixed_only = _fixed_only_violations(p)
    for cid, (v, s_, ne) in sorted(fixed_only.items()):
        msgs.append(
            f"constraint {cid}: none of its {ne} entries can move (fixed, zero or none) and their sum "
            f"{s_:,.6f} crore is {'above' if v > 0 else 'below'} its band by {abs(v):,.6f} crore: a conflict "
            "between fixed data and the constraint, known without a solve (reported as slack)"
        )

    if len(core.var) == 0:
        msgs.append("no variable entries: nothing to solve")
        return Solution(
            x=x, status="optimal", solver=solver, objective=0.0, iterations=0, balance_slack={},
            band_violation=band_violations(p, x), anchor_violation=anchor_violations(p, x), polish={"applied": False},
            max_imbalance=float(np.max(np.abs(p.residual(x)), initial=0.0)), messages=msgs,
            certificate={"ok": True, "note": "nothing to solve"}, fixed_residuals=fixed_res,
        )  # fmt: skip

    # phase 1: minimum slack
    ph1 = _phase1(core)
    if not ph1.get("feasible"):
        slack, extra = _diagnose_balance(core)
        if not slack:
            extra.append(f"phase-1 LP: {ph1.get('message')}")
            slack = {"(unlocated)": float("nan")}
        return fail("infeasible", slack, extra, {"status": ph1.get("status"), "message": ph1.get("message")})
    _widen(core, ph1)
    phase1 = {
        "total_slack": ph1["total_slack"] + sum(abs(v[0]) for v in fixed_only.values()),
        "widened_anchored": len(ph1["anchored"]),
        "widened_bands": len(ph1["bands"]),
        "fixed_only_bands": {cid: v[0] for cid, v in sorted(fixed_only.items())},
    }
    if ph1["anchored"] or ph1["bands"]:
        msgs.append(
            f"phase 1: the constraints cannot all hold; minimum total slack {ph1['total_slack']:,.6f} crore on "
            f"{len(ph1['bands'])} constraint band(s) and {len(ph1['anchored'])} anchored bound(s); those bounds were "
            "widened by their slack + WIDEN_MARGIN"
            + (
                " (findings below)"
                if ph1["total_slack"] > spec.LP_ZERO
                else " (at the level of solver rounding, <= LP_ZERO: not a finding)"
            )
        )

    # phase 2
    used_options: dict[str, Any] = {}
    iterations: int | None
    if solver.upper() == "NEWTON":
        d = _dual_newton_path(core)
        z, y, iterations = d.z, d.y, d.iterations
        status = "optimal" if d.converged else "not_converged"
        if d.converged and d.message != "converged":
            msgs.append(f"dual Newton: {d.message}")
        if not d.converged:
            msgs.append(f"dual Newton: {d.message}; {_smallest_z_note(core, z)}")
        used_options = {
            "max_iter": spec.NEWTON_MAX_ITER,
            "tol_abs": spec.NEWTON_TOL_ABS,
            "tol_rel": spec.NEWTON_TOL_REL,
            "path": d.path,
        }
        override = False
    else:
        opts = dict(spec.SOLVER_OPTIONS.get(solver, {}) if options is None else options)
        r = _cvxpy_solve(core, solver, scale, opts)
        used_options = opts
        if (r["status"] == "optimal_inaccurate" or str(r["status"]).startswith("solver_error")) and opts:
            msgs.append(f"{solver} returned {r['status']} at {opts}; solved again at the solver's defaults")
            r = _cvxpy_solve(core, solver, scale, {})
            used_options = {}
        status = r["status"] if r["z"] is not None or r["status"] != "optimal" else "solver_error: no solution"
        iterations = r["iterations"]
        if status != "optimal":
            msgs.append(f"solver {solver} returned status {status!r}: the run fails (no silent solver switch)")
            return fail(status, {}, [], phase1)
        z = r["z"]
        tb, tk = _tolerances(core, z)
        y = _recover_multipliers(core, z, tk * 1e3)
        override = True
    cert = kkt_certificate(core, z, y, override=override)
    if not cert["ok"] and status == "optimal":
        msgs.append(f"KKT certificate FAILED ({solver}): {cert}; the run fails; {_smallest_z_note(core, z)}")
    elif cert["ok"] and (note := _immaterial_zero_note(core, z)):
        msgs.append(note)
    c = core.w * np.abs(core.a)
    with np.errstate(divide="ignore", invalid="ignore"):
        objective = float(np.sum(c * np.where(z > 0, z * np.log(z), 0.0) - c * z + c))
    x[core.var] = core.a * z

    # polish
    target = np.zeros(p.n_accounts)
    for k in range(len(core.comp_b)):
        target[np.flatnonzero(core.sink & (core.labels == k))] = core.comp_b[k]
    pol: dict[str, Any] = {"applied": False}
    delta = np.zeros(len(x))
    if status == "optimal":
        x, pol, delta = polish(p, x, target=target)
        if pol.get("failed"):
            msgs.append(f"polish: {pol['failed']}; the run fails")
        moved = {k: v for k, v in pol.get("band_moves", {}).items() if abs(v) > spec.SLACK_REPORT_TOL}
        if moved:
            msgs.append(
                "polish: exact balance moved these constraint sums (Rs crore; a band it pushed outside its "
                "interval is reported with the slack findings): "
                + ", ".join(f"{k} {v:+,.4f}" for k, v in moved.items())
            )
    res = p.residual(x)
    max_imb = float(np.max(np.abs(res))) if len(res) else 0.0
    mult = {p.constraints[k].constraint_id: float(y[core.m + j]) for j, ks in enumerate(core.band_ids) for k in ks
            if y[core.m + j] != 0}  # fmt: skip
    return Solution(
        x=x, status=status, solver=solver, objective=objective, iterations=iterations, balance_slack={},
        band_violation=band_violations(p, x), anchor_violation=anchor_violations(p, x), polish=pol,
        max_imbalance=max_imb, messages=msgs, certificate=cert, phase1=phase1, solver_options=used_options,
        polish_delta=delta, fixed_residuals=fixed_res, band_multipliers=mult,
    )  # fmt: skip


def band_violations(p: Problem, x: np.ndarray, tol: float = spec.SLACK_REPORT_TOL) -> dict[str, float]:
    out: dict[str, float] = {}
    for c in p.constraints:
        s = float(np.sum(x[c.members]))
        if s > c.hi + tol:
            out[c.constraint_id] = s - c.hi
        elif s < c.lo - tol:
            out[c.constraint_id] = s - c.lo
    return out


def anchor_violations(p: Problem, x: np.ndarray, tol: float = spec.SLACK_REPORT_TOL) -> dict[int, float]:
    out: dict[int, float] = {}
    for e in np.flatnonzero((p.role == "anchored") & (p.prior != 0)):
        a, t = p.prior[e], p.tol_rel[e]
        lo, hi = sorted((a * (1 - t), a * (1 + t)))
        if a > 0:
            lo = max(lo, 0.0)
        else:
            hi = min(hi, 0.0)
        if x[e] > hi + tol:
            out[int(e)] = float(x[e] - hi)
        elif x[e] < lo - tol:
            out[int(e)] = float(x[e] - lo)
    return out


def binding(p: Problem, x: np.ndarray) -> list[str]:
    """Constraints whose sum sits on (or outside) a bound after balancing: within
    min(BINDING_ABS, BINDING_REL * band width) of it, plus the Newton tolerance."""
    return [p.constraints[k].constraint_id for k in _binding_indices(p, x, range(len(p.constraints)))]


def _binding_indices(p: Problem, x: np.ndarray, ks: Any) -> list[int]:
    out = []
    for k in ks:
        c = p.constraints[k]
        if not len(c.members):
            continue
        s = float(np.sum(x[c.members]))
        gross = float(np.sum(np.abs(x[c.members])))
        width = c.hi - c.lo if math.isfinite(c.hi) and math.isfinite(c.lo) else math.inf
        eps = min(spec.BINDING_ABS, spec.BINDING_REL * width) + spec.NEWTON_TOL_ABS + spec.NEWTON_TOL_REL * gross
        if s >= c.hi - eps or s <= c.lo + eps:  # an infinite side never binds
            out.append(k)
    return out


def _band_tolerance(c: BandConstraint, x: np.ndarray) -> float:
    """The Newton tolerance of a band at x (Rs crore)."""
    return spec.NEWTON_TOL_ABS + spec.NEWTON_TOL_REL * float(np.sum(np.abs(x[c.members])))


def polish(
    p: Problem, x: np.ndarray, *, passes: int = 3, target: np.ndarray | None = None
) -> tuple[np.ndarray, dict[str, Any], np.ndarray]:
    """Exact removal of the solver's residual imbalances using FREE entries only (module doc, step 4): the
    minimum weighted-least-squares change (weight w_e / |x_e|) that closes every account while holding the
    sum of every constraint band that sits at (or outside) a bound, and of any other band the change would
    push out of its interval (active set; Wave B review S-5: an unconstrained step moved binding bands out
    by up to its own size, and band_violations then reported that as slack). Balance comes first: a held
    band that exact balance needs to move moves as little as possible, and every band sum the polish moves
    is recorded (info['band_moves']). `target`: the residual each account may keep (a component sink's
    within-tolerance fixed residual). Returns (x, info, delta). info['failed'] is set when the pre-polish
    imbalance exceeds POLISH_MAX or the polish would flip a sign (then x is returned unpolished)."""
    x0 = x.copy()
    x = x.copy()
    tgt = np.zeros(p.n_accounts) if target is None else target
    before = float(np.max(np.abs(p.residual(x) - tgt))) if p.n_accounts else 0.0
    info: dict[str, Any] = {"applied": False, "max_imbalance_before": before, "entries_adjusted": 0,
                            "max_adjustment": 0.0, "unreachable_accounts": [], "sign_flips": 0,
                            "bands_held": [], "band_moves": {}}  # fmt: skip
    total = np.zeros(len(x))
    if before <= spec.POLISH_TRIGGER:
        info["max_imbalance_after"] = before
        return x, info, total
    if before > spec.POLISH_MAX:
        info["failed"] = (
            f"imbalance {before:,.6f} crore after the solve exceeds POLISH_MAX {spec.POLISH_MAX} crore: the solve "
            "itself is wrong"
        )
        info["max_imbalance_after"] = before
        return x, info, total
    free = np.flatnonzero((p.role == "free") & (x != 0) & (p.row != p.col))
    nf = len(free)
    fpos = -np.ones(len(x), dtype=np.int64)
    fpos[free] = np.arange(nf)
    bands: dict[int, np.ndarray] = {}  # constraint index -> positions (in `free`) of its free members
    for k, c in enumerate(p.constraints):
        mv = fpos[c.members]
        mv = np.sort(mv[mv >= 0])
        if len(mv):
            bands[k] = mv
    held = set(_binding_indices(p, x, sorted(bands)))  # at (or outside) a bound before the polish: held
    for _ in range(passes):
        r = p.residual(x) - tgt
        if np.max(np.abs(r)) <= 1e-9 or nf == 0:
            break
        w = np.abs(x[free]) / p.weight[free]
        i, j = p.row[free], p.col[free]
        n = p.n_accounts
        L = sp.coo_matrix(
            (np.concatenate([w, w, -w, -w]), (np.concatenate([i, j, i, j]), np.concatenate([i, j, j, i]))),
            shape=(n, n),
        ).tocsr()
        adj = sp.coo_matrix((np.ones(nf), (i, j)), shape=(n, n)).tocsr()
        ncomp, labels = connected_components(adj, directed=False)
        comps = []  # the grounded Laplacian of each component of the free-entry graph (its first account dropped)
        for comp in range(ncomp):
            nodes = np.flatnonzero(labels == comp)
            if len(nodes) < 2:
                continue
            rest = nodes[1:]
            comps.append((rest, splu(L[rest][:, rest].tocsc(), permc_spec="COLAMD")))

        def linv(rhs: np.ndarray, comps: list = comps) -> np.ndarray:
            out = np.zeros_like(rhs)
            for rest, lu in comps:
                out[rest] = lu.solve(rhs[rest])
            return out

        mu0 = linv(-r)
        sums = {k: float(np.sum(x[p.constraints[k].members])) for k in bands}
        while True:
            hk = sorted(held)
            if not hk:
                delta = w * (mu0[i] - mu0[j])
            else:
                # held bands: B delta = 0 as extra rows. With E = A W B^T (accounts x held) and F = B W B^T, the
                # grounded system [L E; E^T F] [mu; nu] = [-r; 0] by its Schur complement on the held bands
                E = np.zeros((n, len(hk)))
                Bt = np.zeros((nf, len(hk)))
                for col, k in enumerate(hk):
                    mv = bands[k]
                    Bt[mv, col] = 1.0
                    np.add.at(E[:, col], i[mv], w[mv])
                    np.add.at(E[:, col], j[mv], -w[mv])
                LE = linv(E)
                S = Bt.T @ (w[:, None] * Bt) - E.T @ LE
                rhs = -(E.T @ mu0)
                dS = np.abs(np.diag(S))  # ~0 for a held band that balance alone determines: floored
                sc = 1.0 / np.sqrt(np.maximum(dS, max(1e-14 * float(np.max(dS, initial=0.0)), 1e-300)))
                nu = sc * np.linalg.lstsq(S * sc[:, None] * sc[None, :], rhs * sc, rcond=1e-12)[0]
                mu = mu0 - LE @ nu
                delta = w * (mu[i] - mu[j]) + w * (Bt @ nu)
            pushed = []
            for k, mv in bands.items():
                if k in held:
                    continue
                c = p.constraints[k]
                new = sums[k] + float(np.sum(delta[mv]))
                tol = _band_tolerance(c, x)
                if (new > c.hi + tol and new > sums[k]) or (new < c.lo - tol and new < sums[k]):
                    pushed.append(k)
            if not pushed:
                break
            held.update(pushed)
        x[free] += delta
        total[free] += delta
    after = p.residual(x) - tgt
    flips = int(np.sum(np.sign(x) != np.sign(p.prior)))
    moves = {p.constraints[k].constraint_id: float(np.sum(total[p.constraints[k].members])) for k in bands}
    info.update(
        applied=True,
        entries_adjusted=int(np.sum(np.abs(total) > 0)),
        max_adjustment=float(np.max(np.abs(total))) if len(total) else 0.0,
        max_imbalance_after=float(np.max(np.abs(after))),
        unreachable_accounts=[p.name(k) for k in np.flatnonzero(np.abs(after) > spec.BALANCE_TOL)],
        sign_flips=flips,
        bands_held=sorted(p.constraints[k].constraint_id for k in held),
        band_moves={cid: v for cid, v in sorted(moves.items()) if abs(v) > spec.NEWTON_TOL_ABS},
    )
    if flips:
        info["failed"] = f"the polish would flip the sign of {flips} entr(y/ies): refused"
        return x0, info, np.zeros(len(x))
    return x, info, total


# ---------------------------------------------------------------------------------------------
# GRAS
# ---------------------------------------------------------------------------------------------


@dataclass
class GrasResult:
    x: np.ndarray
    iterations: int
    converged: bool
    max_gap: float
    messages: list[str]


def _multiplier(pp: np.ndarray, nn: np.ndarray, t: np.ndarray, flag: list[str], what: str) -> np.ndarray:
    """Solve pp*m - nn/m = t for m > 0 per element (Temurshoev et al. 2013, eqs. for r and s)."""
    m = np.ones(len(t))
    pos = pp > 0
    m[pos] = (t[pos] + np.sqrt(t[pos] ** 2 + 4.0 * pp[pos] * nn[pos])) / (2.0 * pp[pos])
    only_neg = (~pos) & (nn > 0)
    ok = only_neg & (t < 0)
    m[ok] = -nn[ok] / t[ok]
    bad = np.flatnonzero((only_neg & ~ok) | (pos & (m <= 0)) | ((~pos) & (nn == 0) & (np.abs(t) > 1e-9)))
    if len(bad):
        flag.append(f"{what}: no feasible multiplier for index {bad.tolist()[:10]}")
    return np.maximum(m, 1e-12)


def gras(
    row: np.ndarray,
    col: np.ndarray,
    a: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    *,
    max_iter: int = spec.GRAS_MAX_ITER,
    tol: float = spec.GRAS_TOL,
) -> GrasResult:
    """Generalised RAS: x_e = r_i a_e s_j for a_e > 0 and a_e / (r_i s_j) for a_e < 0, so that row sums
    equal u and column sums equal v. `row` indexes u, `col` indexes v (they may be different index
    spaces: a rectangular matrix, or the rows and columns of a SAM)."""
    P = np.where(a > 0, a, 0.0)
    N = np.where(a < 0, -a, 0.0)
    nr, nc = len(u), len(v)
    r = np.ones(nr)
    s = np.ones(nc)
    msgs: list[str] = []
    x = a.copy()
    gap = float("inf")
    it = 0
    flags: list[str] = []
    for it in range(1, max_iter + 1):
        flags = []
        pj = np.bincount(col, weights=P * r[row], minlength=nc)
        nj = np.bincount(col, weights=N / r[row], minlength=nc)
        s = _multiplier(pj, nj, v, flags, "column")
        pi = np.bincount(row, weights=P * s[col], minlength=nr)
        ni = np.bincount(row, weights=N / s[col], minlength=nr)
        r = _multiplier(pi, ni, u, flags, "row")
        x = P * r[row] * s[col] - N / (r[row] * s[col])
        gap = max(
            float(np.max(np.abs(np.bincount(row, weights=x, minlength=nr) - u), initial=0.0)),
            float(np.max(np.abs(np.bincount(col, weights=x, minlength=nc) - v), initial=0.0)),
        )
        if gap <= tol:
            break
        if flags and it == 1:
            msgs.extend(f"iteration 1: {f}" for f in flags)
    converged = gap <= tol
    if not converged:
        msgs.extend(f"last iteration: {f}" for f in flags)
        msgs.append(f"GRAS did not converge in {it} iterations (max gap {gap:,.6f})")
    return GrasResult(x, it, converged, gap, msgs)


def gras_sam(p: Problem, **kw: Any) -> GrasResult:
    """GRAS cross-check on a SAM prior (DESIGN_BRIEF s.5.2): fixed entries held; each account's row and
    column target = mean of its prior row and column sums."""
    rs, cs = p.sums(p.prior)
    target = (rs + cs) / 2.0
    var = p.variable()
    fixed_x = np.where(var, 0.0, p.prior)
    fr, fc = p.sums(fixed_x)
    idx = np.flatnonzero(var)
    res = gras(p.row[idx], p.col[idx], p.prior[idx], target - fr, target - fc, **kw)
    x = p.prior.copy()
    x[idx] = res.x
    return GrasResult(x, res.iterations, res.converged, res.max_gap, res.messages)
