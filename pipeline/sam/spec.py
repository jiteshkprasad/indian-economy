"""Vocabularies, column schemas, thresholds and tolerances of the SAM (DESIGN_BRIEF s.3 and s.5).

Every number here is a stated rule, not data. Changing one changes the balanced SAM: record why in
docs/phase2/FRAMEWORK_REQUESTS.md (and DECISIONS.md if it is a policy change).
"""

from __future__ import annotations

import re

import polars as pl

from pipeline.core.paths import REFERENCE_YEAR

YEAR = REFERENCE_YEAR  # "2023-24" (DECISIONS D0-3)
BASE_YEAR = "2022-23"  # NAS base of every current-price number in the SAM (DECISIONS D0-2)

# --- entries --------------------------------------------------------------------------------
STATUSES = ("official", "derived", "estimated")  # as in the Phase 1 clean schema
BALANCED_STATUS = "balanced"  # status of an entry that balancing moved materially (output only)
ROLES = ("fixed", "anchored", "free")
CONFIDENCE_WEIGHTS = {"high": 4.0, "medium": 1.0, "low": 0.25}  # s.5.1: moving a high entry costs more
ANCHORED_WEIGHT = 16.0  # s.5.1
# Tags on RoW-instrument entries (DESIGN_BRIEF s.3; ACCOUNT_STRUCTURE s.7 also names FDI_debt and
# short_term_credit, so both are accepted; the BoP financial-account lines external_assistance, banking_capital,
# errors_omissions and portfolio_abroad were added in Wave C for rest_of_world's K8b lines, FR-row-1: see
# FRAMEWORK_REQUESTS.md).
BOP_FUNCTIONS = (
    "FDI_equity",
    "FDI_debt",
    "FDI_reinvested_earnings",
    "FPI_equity",
    "FPI_debt",
    "ECB",
    "NRI_deposits",
    "trade_credit",
    "short_term_credit",
    "ODI",
    "reserves",
    "external_assistance",
    "banking_capital",
    "errors_omissions",
    "portfolio_abroad",
    "other",
)
BOP_ACCOUNTS = ("K_ROW", "R_ROW")  # a bop_function tag needs one of these as row or column ...
BOP_MIRROR_REFS = ("K7b",)  # ... or one of these refs: the domestic mirror of a RoW line (FR-cf-6, Wave C)
# A zero-valued entry is allowed only where the gap map says the cell exists but is zero this year.
ZERO_ENTRY_REFS = ("D4",)

COMPONENT_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")
CONSTRAINT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.\-]*$")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
BLOCK_RE = re.compile(r"^[a-z][a-z0-9_]*$")

ENTRY_DTYPES: dict[str, pl.DataType] = {
    "row": pl.String(),
    "col": pl.String(),
    "ref": pl.String(),
    "component": pl.String(),
    "value": pl.Float64(),
    "status": pl.String(),
    "role": pl.String(),
    "tol_rel": pl.Float64(),
    "confidence": pl.String(),
    "bop_function": pl.String(),
    "prov_id": pl.String(),
    "note": pl.String(),
}
ENTRY_KEY = ("row", "col", "ref", "component")
ENTRY_REQUIRED = ("row", "col", "ref", "value", "status", "role", "prov_id")

# A constraint: sum of entries with row in `rows`, col in `cols` (and ref in `refs`, component in
# `components` if given) lies in
# target +- max(tol_abs, tol_rel*|target|). Lists are stored as comma-joined, sorted strings.
CONSTRAINT_DTYPES: dict[str, pl.DataType] = {
    "constraint_id": pl.String(),
    "ref": pl.String(),
    "rows": pl.String(),
    "cols": pl.String(),
    "refs": pl.String(),
    "components": pl.String(),
    "target": pl.Float64(),
    "tol_abs": pl.Float64(),
    "tol_rel": pl.Float64(),
    "kind": pl.String(),
    "prov_id": pl.String(),
    "description": pl.String(),
}
# equal: an official total (tolerance = rounding); band: a range around a target; min: sum >= target - tol;
# max: sum <= target + tol (one-sided; a min and a max on the same selection make an asymmetric range)
CONSTRAINT_KINDS = ("equal", "band", "min", "max")

# Control-total checks a block reports (not enforced by balancing; listed in its outputs and tests).
CHECK_DTYPES: dict[str, pl.DataType] = {
    "check_id": pl.String(),
    "description": pl.String(),
    "sam_value": pl.Float64(),
    "target": pl.Float64(),
    "diff": pl.Float64(),
    "tol_abs": pl.Float64(),
    "ok": pl.Boolean(),
    "target_prov_id": pl.String(),
}

# --- balancing (s.5) ---------------------------------------------------------------------------
BALANCE_TOL = 0.01  # |row - col| <= Rs 0.01 crore per account (s.5.3)
EXPLAIN_ABS = 5000.0  # |x - a| >= Rs 5,000 crore needs an explanation ...
EXPLAIN_MIN_ABS = 500.0  # ... or |x - a| >= Rs 500 crore
EXPLAIN_REL = 0.10  # ... and |x - a| / |a| >= 10%
MATERIAL_CHANGE = 1.0  # Rs crore: a balanced entry that moved at least this much gets status 'balanced'
SLACK_REPORT_TOL = 0.01  # Rs crore: a slack above this is a finding (BALANCING.md and ISSUES.md)
# Solver (balance.py). NEWTON is the framework's own dual Newton method for the cross-entropy problem (Wave A
# review F1: a general-purpose conic interior-point solver cannot resolve objective weights that span 11 orders of
# magnitude), with its own interior-point method (log-barrier path following on the same dual) as the fallback
# (DECISIONS D2-23, Wave C). Any
# cvxpy solver name (e.g. CLARABEL) is the documented `--solver` override, for diagnosis; the KKT certificate gates
# every answer.
DEFAULT_SOLVER = "NEWTON"
# Phase 1: minimum-slack LP (HiGHS dual simplex, Rs crore). Every positive slack widens its bound by the slack +
# WIDEN_MARGIN (rounded up to 1e-6 crore) before the entropy solve; a total at or below LP_ZERO is labelled solver
# rounding, not a finding (Wave B S-3).
LP_ZERO = 1e-6
WIDEN_MARGIN = 1e-3
# Phase 2 (NEWTON): stop when every account balance and every constraint band holds within
# NEWTON_TOL_ABS + NEWTON_TOL_REL * (gross flow through it), Rs crore.
NEWTON_MAX_ITER = 500
NEWTON_TOL_ABS = 1e-6
NEWTON_TOL_REL = 1e-12
# KKT certificate after any solve: stationarity |ln z + s(dlambda + sum mu)/w| (dimensionless) within KKT_TOL
# (NEWTON) or KKT_TOL_OVERRIDE (a cvxpy solver, multipliers recovered by least squares); primal feasibility
# within the Newton tolerances (cvxpy: x1000); complementary constraint multipliers. A failed certificate fails the run.
KKT_TOL = 1e-8
KKT_TOL_OVERRIDE = 1e-5
# cvxpy override only: working unit Rs lakh crore; Clarabel tolerances tighter than its defaults, one retry at
# its defaults on optimal_inaccurate or solver_error (the options actually used are recorded).
SCALE = 1e-5
SOLVER_OPTIONS = {"CLARABEL": {"tol_gap_abs": 1e-10, "tol_gap_rel": 1e-10, "tol_feas": 1e-10}}
# Polish (free entries only): applied only when an account is off by more than POLISH_TRIGGER after the solve;
# a pre-polish imbalance above POLISH_MAX means the solve itself is wrong, and a sign flip is never accepted:
# either fails the run.
POLISH_TRIGGER = 1e-4
POLISH_MAX = 1.0
# A constraint is 'at a bound' when its sum is within min(BINDING_ABS, BINDING_REL * band width) of it
# (plus the Newton tolerance).
BINDING_ABS = 1e-3
BINDING_REL = 1e-3
GRAS_TOL = 1e-6  # Rs crore: GRAS stops when every row and column is within this of its target
GRAS_MAX_ITER = 20000
# Explanations (explanations.yaml) record the prior and balanced value they explain; a later run whose change
# differs by more than max(EXPLAIN_DRIFT_REL * |explained change|, EXPLAIN_DRIFT_ABS) makes the explanation stale.
EXPLAIN_DRIFT_REL = 0.20
EXPLAIN_DRIFT_ABS = 500.0


def needs_explanation(prior: float, balanced: float) -> bool:
    """s.5.3: an entry (or a cell: SPEC s.6) needs an explanation if it moved >= 5,000 crore, or >= 500 crore
    and >= 10%."""
    d = abs(balanced - prior)
    if d >= EXPLAIN_ABS:
        return True
    return d >= EXPLAIN_MIN_ABS and (prior == 0 or d / abs(prior) >= EXPLAIN_REL)


def entry_weight(role: str, confidence: str | None) -> float:
    """Balancing weight of an entry (s.5.1). Fixed entries do not move, so they have no weight."""
    if role == "anchored":
        return ANCHORED_WEIGHT
    if role == "free":
        return CONFIDENCE_WEIGHTS[confidence or ""]
    return 0.0
