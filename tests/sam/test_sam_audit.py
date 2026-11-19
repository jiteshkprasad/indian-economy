"""Balancing audit and SAM identities on the real outputs (DESIGN_BRIEF s.5.3, s.7). They run once every
block is built and `sam` has balanced; until then they skip and say why."""

from __future__ import annotations

import json

import polars as pl
import pytest

from pipeline.core.paths import Layout
from pipeline.sam import spec
from pipeline.sam.accounts import EXPECTED_BLOCKS
from pipeline.sam.framework import SamPaths
from pipeline.sam.report import stale_explanations, unexplained

pytestmark = pytest.mark.sam

LAYOUT = Layout.default()
PATHS = SamPaths(LAYOUT)


@pytest.fixture(scope="module")
def run():
    if not PATHS.run_json.exists():
        missing = [b for b in EXPECTED_BLOCKS if not PATHS.built(b)]
        pytest.skip(f"no balancing run yet (blocks not built: {', '.join(missing) or 'none'}; run `sam`)")
    return json.loads(PATHS.run_json.read_text(encoding="utf-8"))


def test_balancing_succeeded(run):
    assert run["ok"], run["messages"]


def test_balancing_is_current(run):
    """Every block's outputs are the ones this balancing run used (else: run `sam` again)."""
    from pipeline.core.io import sha256_file

    stale = [
        b
        for b, h in run["block_inputs"].items()
        if sha256_file(PATHS.entries(b)) != h["entries"] or sha256_file(PATHS.constraints(b)) != h["constraints"]
    ]
    assert stale == [], f"blocks rebuilt after the last balancing run: {stale}"


def test_every_account_balances(run):
    cells = pl.read_parquet(PATHS.balanced_cells)
    r = cells.group_by("row", maintain_order=True).agg(pl.col("value").sum().alias("r")).rename({"row": "a"})
    c = cells.group_by("col", maintain_order=True).agg(pl.col("value").sum().alias("c")).rename({"col": "a"})
    j = r.join(c, on="a", how="full", coalesce=True).fill_null(0.0)
    assert (j["r"] - j["c"]).abs().max() <= spec.BALANCE_TOL


def test_fixed_and_discrepancy_cells_unchanged(run):
    ent = pl.read_parquet(PATHS.balanced_entries)
    moved = ent.filter(((pl.col("role") == "fixed") | (pl.col("row") == "X_DISC") | (pl.col("col") == "X_DISC"))
                       & (pl.col("value") != pl.col("prior")))  # fmt: skip
    assert moved.height == 0, moved


def test_no_over_threshold_adjustment_without_an_explanation(run):
    """Entries and cells (SPEC s.6); an explanation of a different change does not count (review F9). Read from
    pipeline/sam/explanations.yaml and every pipeline/sam/explanations/<block>.yaml (DECISIONS D2-22): a key
    explained twice fails the load, and an entry item in another block's file is stale."""
    log = pl.read_parquet(PATHS.log)
    missing = unexplained(log)
    assert missing.height == 0, missing
    assert stale_explanations(log) == []


def test_no_slack_without_an_issues_entry(run):
    issues = (LAYOUT.root / "ISSUES.md").read_text(encoding="utf-8")
    ids = [*run["balance_slack"], *run["band_violation"], *run["anchor_violation"]]
    assert [i for i in ids if i not in issues] == []


def test_every_sam_provenance_input_resolves():
    """Review integration F8: after `sam <block>` a dependent built earlier may cite records that no longer
    exist. Runs whenever SAM provenance exists (no balancing run needed)."""
    if not PATHS.provenance_all.exists():
        pytest.skip("no SAM block built yet")
    prov = pl.read_parquet(PATHS.provenance_all)
    ids = set(prov["prov_id"].to_list())
    dangling = sorted(
        {i for ins in prov["inputs"].drop_nulls().to_list() for i in ins.split(",") if i.startswith("sam_")} - ids
    )
    assert dangling == [], f"SAM records cite records that no longer exist (rebuild the dependents): {dangling[:10]}"
