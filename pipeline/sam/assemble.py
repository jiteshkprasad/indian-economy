"""Block entries -> the unbalanced (prior) SAM, the merged constraint set, and pre-balancing diagnostics.

- Entries of all blocks are stacked; the key (row, col, ref, component) must stay unique across blocks.
- Constraints are merged by their selection (rows, cols, refs, components) and kind. Declarations of
  the same kind on one selection must have the same target (DESIGN_BRIEF s.4: duplicates fine,
  conflicts an error); the tighter tolerance is kept and every declaration is named. Across kinds
  (equal, band, min, max) on one selection, the intervals they allow must intersect, else the assembly
  stops. Global ids are '<block>:<constraint_id>'.
- Every anchored entry must carry tol_rel > 0 as written (Wave A review F4).
- Diagnostics (s.5.4): each account's prior row total, column total, imbalance (row - column) in Rs
  crore and as % of the larger total, sorted by absolute imbalance. Large imbalances are findings
  to trace to a source disagreement, not things to balance away.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import polars as pl

from pipeline.sam import spec
from pipeline.sam.accounts import Accounts
from pipeline.sam.framework import SamError, SamPaths

CONSTRAINT_OUT_DTYPES: dict[str, pl.DataType] = {
    "constraint_id": pl.String(),  # '<block>:<id>' of the kept declaration
    "declared_by": pl.String(),  # comma-joined '<block>:<id>' of every declaration with this selection
    **{k: v for k, v in spec.CONSTRAINT_DTYPES.items() if k != "constraint_id"},
}


@dataclass
class Assembly:
    entries: pl.DataFrame  # spec.ENTRY_DTYPES + block
    constraints: pl.DataFrame  # CONSTRAINT_OUT_DTYPES
    cells: pl.DataFrame  # row, col, value, n_entries
    diagnostics: pl.DataFrame  # account, group, row_total, col_total, imbalance, imbalance_pct, rank


def read_entries(paths: SamPaths, blocks: Sequence[str]) -> pl.DataFrame:
    frames = [pl.read_parquet(paths.entries(b)) for b in blocks if paths.entries(b).exists()]
    if not frames:
        return pl.DataFrame(schema={**spec.ENTRY_DTYPES, "block": pl.String()})
    df = pl.concat(frames, how="vertical")
    bad = df.filter((pl.col("role") == "anchored") & ~(pl.col("tol_rel") > 0).fill_null(False))
    if bad.height:
        raise SamError(
            f"{bad.height} anchored entries without tol_rel > 0 as written (rebuild their blocks):\n"
            f"{bad.select('block', 'row', 'col', 'ref', 'component', 'value', 'tol_rel').head(20)}"
        )
    dup = df.group_by(list(spec.ENTRY_KEY), maintain_order=True).agg(pl.col("block").sort().str.join(","))
    dup = dup.filter(pl.col("block").str.contains(","))
    if dup.height:
        raise SamError(f"entry keys written by more than one block:\n{dup.head(20)}")
    return df.sort(list(spec.ENTRY_KEY))


def merge_constraints(paths: SamPaths, blocks: Sequence[str]) -> pl.DataFrame:
    frames = [pl.read_parquet(paths.constraints(b)) for b in blocks if paths.constraints(b).exists()]
    frames = [f for f in frames if f.height]
    if not frames:
        return pl.DataFrame(schema=CONSTRAINT_OUT_DTYPES)
    df = pl.concat(frames, how="vertical").with_columns(
        (pl.col("block") + ":" + pl.col("constraint_id")).alias("gid"),
        pl.max_horizontal(pl.col("tol_abs"), pl.col("tol_rel") * pl.col("target").abs()).alias("_tol"),
    )
    out: list[dict] = []
    problems: list[str] = []
    for key, g in df.sort("gid").group_by(["rows", "cols", "refs", "components", "kind"], maintain_order=True):
        g = g.sort(["_tol", "gid"])
        t0 = g["target"][0]
        spread = g["target"].max() - g["target"].min()
        if spread > max(spec.BALANCE_TOL, float(g["_tol"].min())):
            problems.append(
                f"conflicting {key[4]} constraints on rows={key[0]} cols={key[1]} refs={key[2]} components={key[3]}: "
                + ", ".join(f"{i}={t:,.2f}" for i, t in zip(g["gid"], g["target"]))
            )
            continue
        first = g.row(0, named=True)
        out.append(
            {
                "constraint_id": first["gid"],
                "declared_by": ",".join(sorted(g["gid"].to_list())),
                **{k: first[k] for k in spec.CONSTRAINT_DTYPES if k != "constraint_id"},
                "target": t0,
            }
        )
    # across kinds on one selection: the allowed intervals must intersect
    sel = ["rows", "cols", "refs", "components"]
    for key, g in df.sort("gid").group_by(sel, maintain_order=True):
        lo, hi, who = -math.inf, math.inf, []
        for r in g.iter_rows(named=True):
            rlo = -math.inf if r["kind"] == "max" else r["target"] - r["_tol"]
            rhi = math.inf if r["kind"] == "min" else r["target"] + r["_tol"]
            lo, hi = max(lo, rlo), min(hi, rhi)
            who.append(f"{r['gid']} ({r['kind']} {r['target']:,.2f} +- {r['_tol']:,.2f})")
        if lo > hi + spec.BALANCE_TOL:
            problems.append(
                f"constraints on rows={key[0]} cols={key[1]} refs={key[2]} components={key[3]} allow no common value "
                f"(needed >= {lo:,.2f} and <= {hi:,.2f}): " + ", ".join(who)
            )
    if problems:
        raise SamError("constraints disagree across blocks:\n  " + "\n  ".join(problems))
    return pl.DataFrame(out, schema=CONSTRAINT_OUT_DTYPES, orient="row").sort("constraint_id")


def cells_of(entries: pl.DataFrame, value: str = "value") -> pl.DataFrame:
    return (
        entries.group_by(["row", "col"], maintain_order=True)
        .agg(pl.col(value).sum().alias("value"), pl.len().cast(pl.Int64).alias("n_entries"))
        .sort(["row", "col"])
    )


def diagnostics(entries: pl.DataFrame, accounts: Accounts, value: str = "value") -> pl.DataFrame:
    """Per account: row total (receipts), column total (payments), imbalance = row - column."""
    # exact sums (math.fsum): a polars group_by sum depends on the thread count in its last bits (repro)
    def fsum(side: str, name: str) -> pl.DataFrame:
        vals: dict[str, list[float]] = {}
        for k, v in zip(entries[side].to_list(), entries[value].to_list(), strict=True):
            vals.setdefault(k, []).append(v)
        keys = list(vals)
        return pl.DataFrame({side: keys, name: [math.fsum(vals[k]) for k in keys]},
                            schema={side: pl.String(), name: pl.Float64()})  # fmt: skip

    rt, ct = fsum("row", "row_total"), fsum("col", "col_total")
    base = pl.DataFrame(
        {"account": accounts.codes, "group": [accounts.group(c) for c in accounts.codes]},
        schema={"account": pl.String(), "group": pl.String()},
    )
    df = (
        base.join(rt.rename({"row": "account"}), on="account", how="left", maintain_order="left")
        .join(ct.rename({"col": "account"}), on="account", how="left", maintain_order="left")
        .with_columns(pl.col("row_total", "col_total").fill_null(0.0))
        .with_columns((pl.col("row_total") - pl.col("col_total")).alias("imbalance"))
        .with_columns(
            pl.when(pl.max_horizontal(pl.col("row_total").abs(), pl.col("col_total").abs()) > 0)
            .then(100.0 * pl.col("imbalance") / pl.max_horizontal(pl.col("row_total").abs(), pl.col("col_total").abs()))
            .otherwise(None)
            .alias("imbalance_pct")
        )
    )
    order = {c: i for i, c in enumerate(accounts.codes)}
    df = df.with_columns(pl.col("account").replace_strict(order, return_dtype=pl.Int64).alias("_o"))
    # rank on |imbalance| rounded to 1e-4 crore (below the 0.01 balance tolerance): the sums carry ~1e-9
    # float noise that depends on the hash seed and thread count, and near-zero accounts would otherwise
    # swap ranks between builds (repro)
    df = df.sort([pl.col("imbalance").abs().round(4), pl.col("_o")], descending=[True, False]).drop("_o")
    return df.with_row_index("rank", offset=1).with_columns(pl.col("rank").cast(pl.Int64))


def assemble(paths: SamPaths, blocks: Sequence[str], accounts: Accounts) -> Assembly:
    entries = read_entries(paths, blocks)
    cons = merge_constraints(paths, blocks)
    return Assembly(entries, cons, cells_of(entries), diagnostics(entries, accounts))
