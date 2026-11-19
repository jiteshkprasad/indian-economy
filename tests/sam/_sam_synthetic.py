"""A small synthetic two-block SAM written straight into a scratch layout, for end-to-end tests of
assembly, balancing, outputs and the report (run as a script by the determinism test)."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import polars as pl

from pipeline.core import io
from pipeline.core.paths import Layout
from pipeline.sam import spec
from pipeline.sam.framework import SamPaths

PID = "sam_b1:000000000000"


def _e(row, col, ref, v, role, conf=None, tol=None):
    return dict(row=row, col=col, ref=ref, component="total", value=float(v),
                status="estimated" if role == "free" else "official", role=role, tol_rel=tol, confidence=conf,
                bop_function=None, prov_id=PID, note=None)  # fmt: skip


BLOCKS = {
    "b1": [
        _e("A_CROP", "C_CROP", "P1", 100_000, "anchored", tol=0.01),
        _e("C_CROP", "A_CROP", "P2", 30_000, "fixed"),
        _e("F_MIXD", "A_CROP", "V2a", 65_000, "free", "medium"),
        _e("T_PROD", "A_CROP", "P10", -2_000, "fixed"),
    ],
    "b2": [
        _e("C_CROP", "H_R1", "C1a", 60_000, "free", "low"),
        _e("C_CROP", "H_U1", "C1a", 25_000, "free", "medium"),
        _e("H_R1", "F_MIXD", "F3", 45_000, "free", "high"),
        _e("H_U1", "F_MIXD", "F3", 25_000, "free", "high"),
        _e("G_STA", "T_PROD", "P10a", -2_000, "fixed"),
        _e("C_CROP", "G_STA", "C2a", -1_000, "free", "medium"),
    ],
}
CONSTRAINTS = {
    "b1": [dict(constraint_id="pfce", ref="C1", rows="C_CROP", cols="H_R1,H_U1", refs=None, components=None,
                target=73_000.0, tol_abs=10.0, tol_rel=0.0, kind="equal", prov_id=PID,
                description="synthetic PFCE total")],
    "b2": [dict(constraint_id="pfce_dup", ref="C1", rows="C_CROP", cols="H_R1,H_U1", refs=None, components=None,
                target=73_000.0, tol_abs=20.0, tol_rel=0.0, kind="equal", prov_id=PID,
                description="same selection, same target")],
}  # fmt: skip


def write_blocks(layout: Layout) -> SamPaths:
    paths = SamPaths(layout)
    paths.blocks.mkdir(parents=True, exist_ok=True)
    for b, rows in BLOCKS.items():
        df = pl.DataFrame(rows, schema=spec.ENTRY_DTYPES, orient="row").with_columns(pl.lit(b).alias("block"))
        io.write_parquet(df, paths.entries(b), sort_by=spec.ENTRY_KEY)
        c = pl.DataFrame(CONSTRAINTS[b], schema=spec.CONSTRAINT_DTYPES, orient="row").with_columns(
            pl.lit(b).alias("block")
        )
        io.write_parquet(c, paths.constraints(b), sort_by=("constraint_id",))
    return paths


def run(base: Path) -> dict:
    from pipeline.sam import run as samrun

    layout = Layout.scratch(base)
    write_blocks(layout)
    samrun.EXPECTED_BLOCKS = tuple(BLOCKS)
    return samrun.run_balance(layout)


def digest(base: Path) -> str:
    h = hashlib.sha256()
    files = sorted(
        p for p in base.rglob("*") if p.is_file() and not any(x.startswith(".") for x in p.relative_to(base).parts)
    )  # dotfiles (the repo lock's holder file carries a pid) are not outputs
    for p in files:
        h.update(p.relative_to(base).as_posix().encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


if __name__ == "__main__":
    out = Path(sys.argv[1])
    run(out)
    print(digest(out))
