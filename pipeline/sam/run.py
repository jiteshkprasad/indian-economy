"""The `sam` and `sam-report` commands (called from pipeline/cli.py).

sam [BLOCK ...] [--with-deps] [--no-balance] [--solver NAME] [--out DIR]
  1. Build the listed blocks (default: every block in pipeline/sam/blocks) in dependency order.
     Blocks in DEPENDS that are not listed are read as already built; --with-deps rebuilds them.
  2. If no block was listed, every block of DESIGN_BRIEF s.4 is built, all builds succeeded and
     --no-balance is not given: assemble the prior, write the diagnostics, balance (cross-entropy,
     polish, GRAS cross-check), write the outputs of DESIGN_BRIEF s.6 and BALANCING.md.
     Otherwise say clearly that balancing was skipped and why (with a partial set of blocks the prior
     imbalances are printed, not written).
  3. Regenerate data/manifest.json (it hashes data/sam too).
sam-report
  Regenerate BALANCING.md from the balancing outputs (no re-balancing).
"""

from __future__ import annotations

import math
import traceback
from collections.abc import Sequence
from types import ModuleType
from typing import Any

import numpy as np
import polars as pl

from pipeline.core import io
from pipeline.core.manifest import repo_lock, write_manifest
from pipeline.core.paths import Layout
from pipeline.sam import spec
from pipeline.sam.accounts import EXPECTED_BLOCKS, Accounts, check_ownership
from pipeline.sam.assemble import assemble, diagnostics
from pipeline.sam.balance import binding, cross_entropy, gras_sam, problem_from_frames
from pipeline.sam.framework import (
    BlockRun,
    SamError,
    SamPaths,
    block_names,
    block_order,
    build_block_module,
    load_block,
    stale_dependents,
)
from pipeline.sam.report import cell_changes, load_explanations, unexplained, write_report

# entry tables (prior, balanced) keep tol_rel unrounded like the block outputs; other floats at io.DEFAULT_DECIMALS
ENTRY_DECIMALS: dict[str, int | None] = {"tol_rel": None}


def _print_run(r: BlockRun) -> None:
    print(f"   {'OK' if r.ok else 'FAILED'}: {r.message}")
    for k, v in r.counts.items():
        print(f"   {k}: {v}")


def _load(name: str) -> tuple[ModuleType | None, str]:
    """Import and contract-check one block; a broken module becomes a message, never an exception, so one
    builder's half-written block cannot stop another block's build (Wave A review, integration F1)."""
    try:
        return load_block(name), ""
    except SamError as e:
        return None, f"SamError: {e}"
    except Exception as e:  # noqa: BLE001 - a syntax or import error in a block module is that block's failure
        return None, f"{type(e).__name__} while importing the module: {e}\n{traceback.format_exc()}"


def build_blocks(layout: Layout, requested: Sequence[str], *, with_deps: bool) -> tuple[list[BlockRun], list[str]]:
    """Build `requested` (+ their DEPENDS closure if with_deps) in dependency order. Only those modules
    are imported; a module that fails to import or breaks the contract fails its own build (and its
    dependents are skipped), not the others."""
    names = block_names()
    unknown = [b for b in requested if b not in names]
    if unknown:
        raise SamError(f"unknown block(s) {unknown}; known: {names}")
    mods: dict[str, ModuleType] = {}
    load_errors: dict[str, str] = {}
    todo: set[str] = set()
    stack = list(requested)
    while stack:
        n = stack.pop()
        if n in todo:
            continue
        todo.add(n)
        mod, err = _load(n)
        if mod is None:
            load_errors[n] = err
            continue
        mods[n] = mod
        if with_deps:
            for d in getattr(mod, "DEPENDS", ()):
                if d not in names:
                    load_errors.setdefault(n, f"dependency {d!r} has no module in pipeline/sam/blocks")
                elif d not in todo:
                    stack.append(d)
    # two loaded modules claiming one ref (impossible when both pass the contract, kept as a guard)
    seen: dict[str, str] = {}
    for n in sorted(mods):
        for r in getattr(mods[n], "REFS", []):
            if r in seen:
                load_errors[n] = f"ref {r} is claimed by both {seen[r]} and {n}"
            seen.setdefault(r, n)
    deps = {n: tuple(getattr(mods[n], "DEPENDS", ())) if n in mods else () for n in todo}
    order = block_order(sorted(todo), {n: [d for d in deps[n] if d in todo] for n in todo})
    runs: list[BlockRun] = []
    failed: set[str] = set()
    for n in order:
        print(f"== sam {n}")
        bad = [d for d in deps[n] if d in failed]
        if n in load_errors:
            r = BlockRun(n, False, load_errors[n])
        elif bad:
            r = BlockRun(n, False, "not built: dependency failed: " + ", ".join(bad))
        else:
            r, _ = build_block_module(mods[n], layout)
        _print_run(r)
        if not r.ok:
            failed.add(n)
        runs.append(r)
    return runs, order


def run_balance(layout: Layout, *, solver: str = spec.DEFAULT_SOLVER) -> dict[str, Any]:
    """Assemble all blocks, diagnose, balance, write every output of DESIGN_BRIEF s.6 and BALANCING.md."""
    acc = Accounts.load()
    paths = SamPaths(layout)
    asm = assemble(paths, EXPECTED_BLOCKS, acc)
    ent = asm.entries
    prob = problem_from_frames(ent, asm.constraints, acc.codes)
    sol = cross_entropy(prob, solver=solver)
    gr = gras_sam(prob)
    x = sol.x
    prior = prob.prior
    change = x - prior
    ex = load_explanations()
    bind = set(binding(prob, x))
    member_of: dict[int, list[str]] = {}
    for c in prob.constraints:
        if c.constraint_id in bind:
            for e in c.members.tolist():
                member_of.setdefault(e, []).append(c.constraint_id)
    need = np.array([spec.needs_explanation(float(a), float(b)) for a, b in zip(prior, x)], dtype=bool)
    gdiff = gr.x - x
    # a GRAS that did not converge is not a cross-check: no findings are computed from it (review F11)
    gfind = (
        np.array([spec.needs_explanation(float(a), float(b)) for a, b in zip(x, gr.x)], dtype=bool)
        if gr.converged
        else np.zeros(len(x), dtype=bool)
    )
    keys = list(zip(*(ent[k].to_list() for k in ("row", "col", "ref", "component"))))
    polish_delta = sol.polish_delta if sol.polish_delta is not None else np.zeros(len(x))
    with np.errstate(divide="ignore", invalid="ignore"):
        pct = np.where(prior != 0, 100.0 * change / np.abs(prior), np.nan)
    log = ent.select("row", "col", "ref", "component", "block", "role", "confidence", "status", "prov_id").with_columns(
        pl.Series("weight", prob.weight, dtype=pl.Float64),
        pl.Series("prior", prior, dtype=pl.Float64),
        pl.Series("balanced", x, dtype=pl.Float64),
        pl.Series("change", change, dtype=pl.Float64),
        pl.Series("pct_change", [None if math.isnan(v) else float(v) for v in pct], dtype=pl.Float64),
        pl.Series("polish_change", polish_delta, dtype=pl.Float64),
        pl.Series("gras", gr.x, dtype=pl.Float64),
        pl.Series("gras_diff", gdiff, dtype=pl.Float64),
        pl.Series("gras_finding", gfind, dtype=pl.Boolean),
        pl.Series("explanation_required", need, dtype=pl.Boolean),
        pl.Series("binding", [",".join(sorted(member_of.get(i, []))) or None for i in range(len(x))], dtype=pl.String),
    )
    missing = unexplained(log, ex)
    missing_keys = {tuple(r[k] for k in ("row", "col", "ref", "component")) for r in missing.iter_rows(named=True)}
    cells = cell_changes(log)
    cell_need = {(r["row"], r["col"]) for r in cells.filter(pl.col("explanation_required")).iter_rows(named=True)}
    log = log.with_columns(
        pl.Series(
            "explained", [bool(need[i]) and keys[i] not in missing_keys for i in range(len(x))], dtype=pl.Boolean
        ),
        pl.Series("cell_explanation_required", [(k[0], k[1]) in cell_need for k in keys], dtype=pl.Boolean),
    )
    cstat = pl.DataFrame(
        {
            "constraint_id": [c.constraint_id for c in prob.constraints],
            "lo": [c.lo if math.isfinite(c.lo) else None for c in prob.constraints],  # null = no lower bound (max)
            "hi": [c.hi if math.isfinite(c.hi) else None for c in prob.constraints],  # null = no upper bound (min)
            "prior_sum": [float(np.sum(prior[c.members])) for c in prob.constraints],
            "balanced_sum": [float(np.sum(x[c.members])) for c in prob.constraints],
            "n_members": [len(c.members) for c in prob.constraints],
            "binding": [c.constraint_id in bind for c in prob.constraints],
        },
        schema={
            "constraint_id": pl.String(),
            "lo": pl.Float64(),
            "hi": pl.Float64(),
            "prior_sum": pl.Float64(),
            "balanced_sum": pl.Float64(),
            "n_members": pl.Int64(),
            "binding": pl.Boolean(),
        },  # fmt: skip
    ).join(asm.constraints.select("constraint_id", "declared_by", "ref", "target"), on="constraint_id", how="left")
    roles = ent["role"].to_list()
    variable = prob.variable()
    run: dict[str, Any] = {
        "year": paths.year,
        # the block outputs this run balanced (the audit test fails if a block was rebuilt since)
        "block_inputs": {
            b: {"entries": io.sha256_file(paths.entries(b)), "constraints": io.sha256_file(paths.constraints(b))}
            for b in EXPECTED_BLOCKS
        },
        "method": (
            "cross-entropy (GRAS / minimum-information-loss form, signed priors): phase-1 minimum-slack LP (HiGHS), "
            "then "
            + (
                "the dual Newton method"
                + {
                    "interior-point fallback": " (after its interior-point fallback, DECISIONS D2-23)",
                    "proximal fallback": " (after its proximal fallback)",
                }.get(sol.solver_options.get("path", ""), "")
                if sol.solver.upper() == "NEWTON"
                else f"cvxpy + {sol.solver}"
            )  # fmt: skip
            + ", KKT certificate, polish on free entries"
        ),
        "solver": sol.solver,
        "solver_options": sol.solver_options,  # the options of the accepted solve (review F3)
        "status": sol.status,
        "certificate": sol.certificate,
        "phase1": sol.phase1,
        "fixed_residuals": sol.fixed_residuals,
        "ok": sol.ok,
        "objective": sol.objective,
        "iterations": sol.iterations,
        "max_imbalance": sol.max_imbalance,
        "polish": sol.polish,
        "balance_slack": sol.balance_slack,
        "band_violation": sol.band_violation,
        "anchor_violation": {
            f"{ent['row'][e]} <- {ent['col'][e]} [{ent['ref'][e]}/{ent['component'][e]}]": v
            for e, v in sol.anchor_violation.items()
        },
        "messages": sol.messages,
        "gras": {
            "converged": gr.converged,
            "iterations": gr.iterations,
            "max_gap": gr.max_gap,
            "messages": gr.messages,
        },  # fmt: skip
        "tolerances": {
            "balance_tol": spec.BALANCE_TOL,
            "explain_abs": spec.EXPLAIN_ABS,
            "explain_min_abs": spec.EXPLAIN_MIN_ABS,
            "explain_rel": spec.EXPLAIN_REL,
            "material_change": spec.MATERIAL_CHANGE,
            "slack_report_tol": spec.SLACK_REPORT_TOL,
            "lp_zero": spec.LP_ZERO,
            "widen_margin": spec.WIDEN_MARGIN,
            "newton_tol_abs": spec.NEWTON_TOL_ABS,
            "newton_tol_rel": spec.NEWTON_TOL_REL,
            "kkt_tol": spec.KKT_TOL,
            "polish_trigger": spec.POLISH_TRIGGER,
            "polish_max": spec.POLISH_MAX,
            "explain_drift_rel": spec.EXPLAIN_DRIFT_REL,
            "explain_drift_abs": spec.EXPLAIN_DRIFT_ABS,
            "gras_tol": spec.GRAS_TOL,
        },
        "counts": {
            "entries": ent.height,
            "variable": int(variable.sum()),
            "fixed": roles.count("fixed"),
            "anchored": int(((prob.role == "anchored") & variable).sum()),
            "free": int(((prob.role == "free") & variable).sum()),
            "constraints": len(prob.constraints),
            "moved": int(np.sum(np.abs(change) >= spec.MATERIAL_CHANGE)),
            "explanation_required": int(need.sum()),
            "cells_explanation_required": int(
                cells.filter(pl.col("explanation_required") & (pl.col("n_entries") > 1)).height
            ),
            "unexplained": missing.height,
            "gras_findings": int(gfind.sum()),
        },
    }
    bal = ent.with_columns(
        pl.col("value").alias("prior"),
        pl.Series("balanced", x, dtype=pl.Float64),
        pl.Series("change", change, dtype=pl.Float64),
        pl.col("status").alias("prior_status"),
    ).with_columns(
        pl.when(pl.col("change").abs() >= spec.MATERIAL_CHANGE)
        .then(pl.lit(spec.BALANCED_STATUS))
        .otherwise(pl.col("status"))
        .alias("status"),
        pl.col("balanced").alias("value"),
    )
    with repo_lock(layout):
        paths.root.mkdir(parents=True, exist_ok=True)
        # tol_rel unrounded, as in the block outputs (Wave A F4; Wave C: at 6 decimals the assembled prior showed 5
        # anchored entries with tol_rel 0, so the problem could not be rebuilt from it)
        io.write_parquet(ent, paths.prior_entries, sort_by=spec.ENTRY_KEY, decimals=ENTRY_DECIMALS)
        io.write_parquet(asm.cells, paths.prior_cells, sort_by=("row", "col"))
        io.write_parquet(asm.diagnostics, paths.diagnostics, sort_by=("rank",))
        io.write_parquet(asm.constraints, paths.constraints_all, sort_by=("constraint_id",))
        io.write_parquet(log, paths.log, sort_by=spec.ENTRY_KEY)
        io.write_parquet(cstat, paths.constraint_status, sort_by=("constraint_id",))
        io.write_json(paths.run_json, run_record_floats(run), decimals=None)
        if sol.ok:
            io.write_parquet(bal, paths.balanced_entries, sort_by=spec.ENTRY_KEY, decimals=ENTRY_DECIMALS)
            cells = bal.group_by(["row", "col"], maintain_order=True).agg(pl.col("value").sum()).sort(["row", "col"])
            io.write_parquet(cells, paths.balanced_cells, sort_by=("row", "col"))
            io.write_text(paths.matrix_csv, matrix_csv(cells, acc))
        else:
            for p in (paths.balanced_entries, paths.balanced_cells, paths.matrix_csv):
                if p.exists():
                    p.unlink()  # never leave a balanced SAM from an earlier run next to a failed one
        write_report(layout)
    return run


# Fields of balancing_run.json written with significant digits rather than 6 decimals (close-out re-verification,
# 2026-10-01: at 6 decimals the certificate tolerance 1e-8, the solver tolerances and the measured duality gap all
# printed as 0.0). Tolerances are spec constants (12 significant digits); the certificate's measured quantities get
# 3, enough to read their order of magnitude. Every other float keeps 6 decimals, as before.
RUN_SIG_DIGITS_CONSTANT = 12
RUN_SIG_DIGITS_MEASURED = 3
CERTIFICATE_CONSTANTS = ("tolerance",)


def _sig(x: float, digits: int) -> float:
    if not math.isfinite(x):
        raise SamError(f"non-finite float {x!r} in the run record")
    y = float(f"{x:.{digits}g}")
    return 0.0 if y == 0 else y


def run_record_floats(run: dict[str, Any]) -> dict[str, Any]:
    """The run record with its floats rounded for writing (deterministic; see RUN_SIG_DIGITS_*)."""

    def dec(obj: Any) -> Any:
        if isinstance(obj, bool) or not isinstance(obj, float):
            if isinstance(obj, dict):
                return {k: dec(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [dec(v) for v in obj]
            return obj
        return io.canonical_float(obj, 6)

    def sig(obj: Any, digits: int) -> Any:
        if isinstance(obj, float):
            return _sig(obj, digits)
        if isinstance(obj, dict):
            return {k: sig(v, digits) for k, v in obj.items()}
        return dec(obj)

    out: dict[str, Any] = {}
    for k, v in run.items():
        if k == "tolerances":
            out[k] = sig(v, RUN_SIG_DIGITS_CONSTANT)
        elif k == "solver_options" and isinstance(v, dict):
            out[k] = {o: sig(w, RUN_SIG_DIGITS_CONSTANT) if o.startswith("tol") else dec(w) for o, w in v.items()}
        elif k == "certificate" and isinstance(v, dict):
            out[k] = {
                c: sig(w, RUN_SIG_DIGITS_CONSTANT if c in CERTIFICATE_CONSTANTS else RUN_SIG_DIGITS_MEASURED)
                for c, w in v.items()
            }
        else:
            out[k] = dec(v)
    return out


def matrix_csv(cells: pl.DataFrame, acc: Accounts) -> str:
    """128 x 128, account order from accounts.yaml; empty = no entry, values in Rs crore to 6 decimals (audit BS-2:
    at 2 decimals a reader summing a row saw accounts off by up to 0.04 against the 0.01 balance tolerance)."""
    vals = {(r, c): v for r, c, v in cells.select("row", "col", "value").iter_rows()}
    lines = ["row/col," + ",".join(acc.codes)]
    for r in acc.codes:
        cells_txt = []
        for c in acc.codes:
            v = vals.get((r, c))
            cells_txt.append("" if v is None else f"{round(v, 6) + 0.0:.6f}")
        lines.append(r + "," + ",".join(cells_txt))
    return "\n".join(lines) + "\n"


def print_partial_diagnostics(layout: Layout, built: Sequence[str], top: int = 15) -> None:
    """With a partial set of blocks: show the largest prior imbalances of what exists (not written)."""
    from pipeline.sam.assemble import read_entries

    acc = Accounts.load()
    ent = read_entries(SamPaths(layout), [b for b in EXPECTED_BLOCKS if b in built])
    if ent.height == 0:
        return
    d = diagnostics(ent, acc).head(top)
    print(f"prior imbalances of the blocks built so far ({', '.join(built)}), largest {top} (not written):")
    for r in d.iter_rows(named=True):
        print(
            f"   {r['account']:<8} row {r['row_total']:>16,.2f}  col {r['col_total']:>16,.2f}  "
            f"imbalance {r['imbalance']:>+16,.2f}"
        )


def cmd_sam(
    layout: Layout,
    blocks: Sequence[str],
    *,
    with_deps: bool = False,
    balance: bool = True,
    solver: str = spec.DEFAULT_SOLVER,
) -> int:
    problems = check_ownership(layout.gap_map)
    if problems:
        print("ownership table inconsistent with data/gap_map.csv:\n  " + "\n  ".join(problems))
        return 1
    subset = bool(blocks)
    try:
        runs, order = build_blocks(layout, list(blocks) or block_names(), with_deps=with_deps or not subset)
    except SamError as e:
        print(f"sam: {e}")
        return 1
    failed = [r for r in runs if not r.ok]
    paths = SamPaths(layout)
    known = set(block_names())
    catalogs = sorted(paths.blocks.glob("*_block.json")) if paths.blocks.exists() else []
    orphans = [n for n in (p.name.removesuffix("_block.json") for p in catalogs) if n not in known]
    for o in orphans:
        print(f"WARNING: outputs of block {o!r} exist but pipeline/sam/blocks has no such module (stale; delete them)")
    built = [b for b in EXPECTED_BLOCKS if paths.built(b)]
    missing = [b for b in EXPECTED_BLOCKS if b not in built]
    rc = 1 if failed else 0
    if subset:
        print(f"\nbalancing skipped: only a subset of blocks was built ({', '.join(order)}); run `sam` with no "
              "block names to build everything and balance")  # fmt: skip
    elif failed:
        print("\nbalancing skipped: block(s) failed: " + ", ".join(r.block for r in failed))
    elif not balance:
        print("\nbalancing skipped: --no-balance")
    elif missing:
        print(f"\nbalancing skipped: block(s) not written yet: {', '.join(missing)} (DESIGN_BRIEF s.4)")
        print_partial_diagnostics(layout, built)
    else:
        print("\n== balancing")
        run = run_balance(layout, solver=solver)
        print(
            f"   status {run['status']}, max imbalance {run['max_imbalance']:.6f} crore, "
            f"{run['counts']['explanation_required']} adjustment(s) need an explanation; report: "
            f"{layout.balancing_report}"
        )
        for m in run["messages"]:
            print(f"   {m}")
        if not run["ok"]:
            print("   BALANCING FAILED: no balanced SAM written (see BALANCING.md)")
            rc = 1
    for r in runs:
        for w in r.warnings:
            print(f"  WARNING {r.block}: {w}")
    for w in stale_dependents(paths):
        print(f"  WARNING stale block: {w}: rebuild it (`sam <block>`, or `sam` to rebuild everything)")
    with repo_lock(layout):
        write_manifest(layout)
    print(f"manifest written: {layout.manifest}")
    print(f"\n{len(runs) - len(failed)} block(s) ok, {len(failed)} failed")
    for r in failed:
        print(f"  FAILED {r.block}: {r.message.splitlines()[0] if r.message else ''}")
    return rc


def cmd_sam_report(layout: Layout) -> int:
    try:
        p = write_report(layout)
    except SamError as e:
        print(f"sam-report: {e}")
        return 1
    with repo_lock(layout):
        write_manifest(layout)
    print(f"wrote {p}")
    return 0
