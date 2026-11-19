"""End to end on a synthetic SAM: assembly, constraint merging, balancing, outputs, explanation check,
report and manifest; byte-identical across hash seeds and thread counts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import polars as pl
import pytest
from _sam_synthetic import BLOCKS, digest, run

from pipeline.core.env import ALLOW_HASHSEED_VAR, ALLOW_THREADS_VAR, REEXEC_VAR, THREAD_VARS, pinned_environ
from pipeline.core.manifest import build_manifest
from pipeline.core.paths import REPO_ROOT, Layout
from pipeline.sam import spec
from pipeline.sam.framework import SamPaths
from pipeline.sam.report import render, stale_explanations, unexplained

pytestmark = pytest.mark.sam


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    from pipeline.sam import run as samrun

    monkeypatch.setattr(samrun, "EXPECTED_BLOCKS", tuple(BLOCKS))
    result = run(tmp_path)
    return tmp_path, result


def test_balancing_run_writes_every_output(synthetic):
    base, result = synthetic
    paths = SamPaths(Layout.scratch(base))
    assert result["ok"] and result["status"] == "optimal"
    for p in (paths.prior_entries, paths.prior_cells, paths.diagnostics, paths.constraints_all, paths.balanced_entries,
              paths.balanced_cells, paths.matrix_csv, paths.log, paths.constraint_status, paths.run_json):  # fmt: skip
        assert p.exists(), p
    bal = pl.read_parquet(paths.balanced_cells)
    rows = bal.group_by("row", maintain_order=True).agg(pl.col("value").sum()).rename({"row": "a", "value": "r"})
    cols = bal.group_by("col", maintain_order=True).agg(pl.col("value").sum()).rename({"col": "a", "value": "c"})
    j = rows.join(cols, on="a", how="full", coalesce=True).fill_null(0.0)
    assert (j["r"] - j["c"]).abs().max() <= spec.BALANCE_TOL
    ent = pl.read_parquet(paths.balanced_entries)
    fixed = ent.filter(pl.col("role") == "fixed")
    assert (fixed["value"] == fixed["prior"]).all()  # fixed entries never move
    assert set(ent.filter(pl.col("change").abs() >= spec.MATERIAL_CHANGE)["status"]) == {"balanced"}


def test_duplicate_constraints_merge_and_the_band_holds(synthetic):
    base, result = synthetic
    paths = SamPaths(Layout.scratch(base))
    cons = pl.read_parquet(paths.constraints_all)
    assert cons["constraint_id"].to_list() == ["b1:pfce"]
    assert cons["declared_by"].to_list() == ["b1:pfce,b2:pfce_dup"]
    st = pl.read_parquet(paths.constraint_status)
    assert 73_000 - 10 - 1e-6 <= st["balanced_sum"][0] <= 73_000 + 10 + 1e-6
    assert result["band_violation"] == {}


def test_over_threshold_adjustments_need_explanations(synthetic):
    base, _ = synthetic
    log = pl.read_parquet(SamPaths(Layout.scratch(base)).log)
    need = log.filter(pl.col("explanation_required"))
    assert set(zip(need["row"], need["col"])) >= {("F_MIXD", "A_CROP"), ("C_CROP", "G_STA")}
    assert unexplained(log, {}).height == need.height
    key = ("F_MIXD", "A_CROP", "V2a", "total")
    r = log.filter((pl.col("row") == "F_MIXD") & (pl.col("col") == "A_CROP")).row(0, named=True)
    item = {"why": "x" * 50, "prior": r["prior"], "balanced": r["balanced"]}
    assert unexplained(log, {key: item}).height == need.height - 1
    # an explanation of a different change is stale and does not count (review F9)
    stale = {**item, "balanced": r["prior"] + 10 * (r["balanced"] - r["prior"])}
    assert unexplained(log, {key: stale}).height == need.height
    assert stale_explanations(log, {key: stale}) and not stale_explanations(log, {key: item})
    assert stale_explanations(log, {("X", "Y", "P1", "total"): item}) == ["('X', 'Y', 'P1', 'total'): no such entry"]


def _write_explanations(path: Path, items: list[dict]) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"explanations": items}, sort_keys=True), encoding="utf-8", newline="\n")


def _item(row: str, col: str, ref: str = "P1", component: str = "total") -> dict:
    return {"row": row, "col": col, "ref": ref, "component": component, "prior": 1.0, "balanced": 2.0,
            "why": "synthetic explanation long enough to pass the length rule", "sources": []}  # fmt: skip


def test_per_block_explanation_files_are_read_with_the_shared_file(tmp_path):
    """DECISIONS D2-22: pipeline/sam/explanations/<block>.yaml files are read with the shared file (same item
    format); a key explained in two files, or twice in one, is an error naming the files; a file not named after
    a DESIGN_BRIEF block is an error (its items would otherwise be ignored); each item knows its file."""
    from pipeline.sam.framework import SamError
    from pipeline.sam.report import load_explanations

    shared, d = tmp_path / "explanations.yaml", tmp_path / "explanations"
    _write_explanations(shared, [_item("A", "B")])
    _write_explanations(d / "production.yaml", [_item("C", "D"), _item("C", "D", "*", "*")])
    _write_explanations(d / "factors.yaml", [_item("E", "F")])
    ex = load_explanations(shared, d)
    assert sorted(ex) == [("A", "B", "P1", "total"), ("C", "D", "*", "*"), ("C", "D", "P1", "total"),
                          ("E", "F", "P1", "total")]  # fmt: skip
    assert ex[("E", "F", "P1", "total")]["_file"] == "explanations/factors.yaml"
    assert ex[("A", "B", "P1", "total")]["_file"] == "explanations.yaml"
    assert load_explanations(tmp_path / "none.yaml", tmp_path / "no_dir") == {}
    _write_explanations(d / "taxes.yaml", [_item("C", "D")])
    with pytest.raises(SamError, match=r"explained twice \(also in explanations/production.yaml\)"):
        load_explanations(shared, d)
    _write_explanations(d / "taxes.yaml", [_item("G", "H"), _item("G", "H")])
    with pytest.raises(SamError, match="explained twice in this file"):
        load_explanations(shared, d)
    (d / "taxes.yaml").unlink()
    _write_explanations(d / "taxs.yaml", [_item("G", "H")])
    with pytest.raises(SamError, match="not <block>.yaml files"):
        load_explanations(shared, d)


def test_an_entry_item_in_another_blocks_file_is_stale(synthetic):
    """An entry-level item in explanations/<block>.yaml must explain an entry of that block (the shared file may
    explain any); otherwise it is listed as stale, so the audit test names it."""
    base, _ = synthetic
    log = pl.read_parquet(SamPaths(Layout.scratch(base)).log)
    r = log.filter((pl.col("row") == "F_MIXD") & (pl.col("col") == "A_CROP")).row(0, named=True)
    key = (r["row"], r["col"], r["ref"], r["component"])
    item = {"why": "x" * 50, "prior": r["prior"], "balanced": r["balanced"]}
    assert not stale_explanations(log, {key: {**item, "_file": f"explanations/{r['block']}.yaml"}})
    assert not stale_explanations(log, {key: {**item, "_file": "explanations.yaml"}})
    other = "explanations/production.yaml" if r["block"] != "production" else "explanations/taxes.yaml"
    out = stale_explanations(log, {key: {**item, "_file": other}})
    assert len(out) == 1 and f"belongs to block {r['block']}" in out[0]


def test_report_shows_closures_gap_tables_before_balancing(synthetic):
    """FR-closure-1: with closure's satellites present, BALANCING.md shows Z, delivered/required/gap by institution
    and by flow class, and the constraints the prior violates; without them it says they are missing."""
    import polars as pl_

    base, _ = synthetic
    paths = SamPaths(Layout.scratch(base))
    text = render(paths)
    assert "## Before balancing: where the gaps come from" in text and "closure's satellite(s)" in text
    sat = paths.satellites("closure")
    sat.mkdir(parents=True, exist_ok=True)
    common = {"unit": "INR_crore", "status": "estimated", "prov_id": "sam_closure:000000000000"}
    pl_.DataFrame([{"series_id": "all.z", "household_group": "ALL", "measure": "z", "value": -1144073.44, **common},
                   {"series_id": "all.k4a_sum", "household_group": "ALL", "measure": "k4a_sum", "value": 4746257.0,
                    **common},
                   {"series_id": "all.k4_nas", "household_group": "ALL", "measure": "k4_nas", "value": 5890330.44,
                    **common}]).write_parquet(sat / "hh_saving.parquet")  # fmt: skip
    ig = []
    for inst, d, q in (("HH", 2486901.85, 3630974.76), ("GG", 203751.13, -183400.52)):
        ig += [
            {"series_id": f"{inst}.{m}", "institution": inst, "members": "", "measure": m, "value": v, **common}
            for m, v in (("delivered_net", d), ("required_net", q), ("gap", d - q), ("property_income.net", 5.0))
        ]
    pl_.DataFrame(ig).write_parquet(sat / "institution_gaps.parquet")
    cg = [{"series_id": f"c.{m}", "constraint_id": "closure:k4.hh_saving_total", "block": "closure", "ref": "K4a",
           "kind": "equal", "outside_band": "yes", "measure": m, "value": v, **common}
          for m, v in (("target", 5890330.44), ("lo", 5890329.94), ("hi", 5890330.94), ("prior_sum", 4746257.0),
                       ("gap", -1144073.44))]  # fmt: skip
    cg.append({**cg[0], "series_id": "d.gap", "constraint_id": "x:inside", "outside_band": "no", "value": 0.0})
    pl_.DataFrame(cg).write_parquet(sat / "constraint_gaps.parquet")
    text = render(paths)
    sec = text[text.index("## Before balancing") : text.index("## Adjustments that need")]
    assert "Z (household saving gap, `hh_saving` all.z): -11,44,073.44 crore" in sec
    assert "| HH | 24,86,901.85 | 36,30,974.76 | -11,44,072.91 |" in sec and "| GG |" in sec
    assert "| property_income | 5 | 5 |" in sec
    assert "closure:k4.hh_saving_total" in sec and "x:inside" not in sec


def test_report_is_regenerated_identically_and_manifested(synthetic):
    base, _ = synthetic
    layout = Layout.scratch(base)
    text = layout.balancing_report.read_text(encoding="utf-8")
    assert "Result: BALANCED" in text and "**MISSING**" in text
    assert render(SamPaths(layout)) == text
    m = build_manifest(layout)
    assert "BALANCING.md" in m["files"]
    assert "data/sam/2023-24/sam_balanced.parquet" in m["files"]
    run_json = json.loads(SamPaths(layout).run_json.read_text(encoding="utf-8"))
    assert run_json["tolerances"]["balance_tol"] == spec.BALANCE_TOL
    # close-out re-verification (2026-10-01): tolerances below 1e-6 keep their significant digits in the run record
    assert run_json["tolerances"]["kkt_tol"] == spec.KKT_TOL
    assert run_json["tolerances"]["newton_tol_rel"] == spec.NEWTON_TOL_REL
    assert run_json["certificate"]["tolerance"] > 0


def test_run_record_keeps_small_tolerances_and_rounds_the_rest():
    from pipeline.sam.run import run_record_floats

    rec = run_record_floats({
        "objective": 113697.9000894321,
        "tolerances": {"kkt_tol": 1e-8, "balance_tol": 0.01},
        "solver_options": {"tol_rel": 1e-12, "max_iter": 500, "path": "direct"},
        "certificate": {"tolerance": 1e-8, "duality_gap_rel": 5.71234e-12, "ok": True, "entries_at_bounds": 8},
        "nested": {"x": [0.1234567891, 2]},
    })  # fmt: skip
    assert rec["objective"] == 113697.900089
    assert rec["tolerances"] == {"kkt_tol": 1e-8, "balance_tol": 0.01}
    assert rec["solver_options"] == {"tol_rel": 1e-12, "max_iter": 500, "path": "direct"}
    assert rec["certificate"] == {"tolerance": 1e-8, "duality_gap_rel": 5.71e-12, "ok": True, "entries_at_bounds": 8}
    assert rec["nested"] == {"x": [0.123457, 2]}


def test_failed_balance_leaves_no_balanced_sam(tmp_path, monkeypatch):
    from _sam_synthetic import write_blocks

    from pipeline.sam import run as samrun

    layout = Layout.scratch(tmp_path)
    paths = write_blocks(layout)
    # make b1's fixed IC entry impossible to absorb: an extra fixed payment with no counterpart
    df = pl.read_parquet(paths.entries("b1"))
    extra = df.head(1).with_columns(
        pl.lit("R_ROW").alias("row"), pl.lit("C_CROP").alias("col"), pl.lit("P6").alias("ref"),
        pl.lit(5_000.0).alias("value"), pl.lit("fixed").alias("role"), pl.lit(None, pl.Float64).alias("tol_rel"),
    )  # fmt: skip
    from pipeline.core import io

    io.write_parquet(pl.concat([df, extra]), paths.entries("b1"), sort_by=spec.ENTRY_KEY)
    monkeypatch.setattr(samrun, "EXPECTED_BLOCKS", tuple(BLOCKS))
    res = samrun.run_balance(layout)
    assert not res["ok"] and "R_ROW" in res["balance_slack"]
    assert not paths.balanced_entries.exists() and not paths.matrix_csv.exists()
    assert "NOT BALANCED" in layout.balancing_report.read_text(encoding="utf-8")


def test_outputs_are_identical_across_hash_seeds_and_thread_counts(tmp_path):
    script = Path(__file__).with_name("_sam_synthetic.py")
    outs = []
    for i, (seed, threads) in enumerate((("0", "1"), ("1", "1"), ("0", "4"))):
        extra = {"PYTHONHASHSEED": seed, ALLOW_HASHSEED_VAR: "1", REEXEC_VAR: "1"}
        if threads != "1":
            extra |= {v: threads for v in THREAD_VARS} | {ALLOW_THREADS_VAR: "1"}
        env = pinned_environ(extra)
        env["PYTHONPATH"] = str(REPO_ROOT)
        r = subprocess.run([sys.executable, str(script), str(tmp_path / f"run{i}")], cwd=REPO_ROOT, env=env,
                           capture_output=True, text=True)  # fmt: skip
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout.strip().splitlines()[-1])
    assert len(set(outs)) == 1, outs
    assert digest(tmp_path / "run0") == outs[0]


def _with_b2_constraint(layout, **change):
    from _sam_synthetic import CONSTRAINTS, write_blocks

    from pipeline.core import io

    paths = write_blocks(layout)
    row = {**CONSTRAINTS["b2"][0], **change}
    df = pl.DataFrame([row], schema=spec.CONSTRAINT_DTYPES, orient="row").with_columns(pl.lit("b2").alias("block"))
    io.write_parquet(df, paths.constraints("b2"), sort_by=("constraint_id",))
    return paths


def test_constraints_of_different_kinds_on_one_selection_must_intersect(tmp_path):
    """Review integration F6: b1 says 73,000 +- 10; b2 a band at 80,000 +- 20 on the same selection: no
    common value, the assembly stops. A compatible floor (min 72,000) is kept alongside."""
    from pipeline.sam.assemble import merge_constraints
    from pipeline.sam.framework import SamError

    layout = Layout.scratch(tmp_path / "a")
    paths = _with_b2_constraint(layout, kind="band", target=80_000.0)
    with pytest.raises(SamError, match="allow no common value"):
        merge_constraints(paths, ["b1", "b2"])
    paths = _with_b2_constraint(Layout.scratch(tmp_path / "b"), kind="min", target=72_000.0)
    merged = merge_constraints(paths, ["b1", "b2"])
    assert sorted(merged["kind"].to_list()) == ["equal", "min"]


def test_a_gras_that_does_not_converge_yields_no_findings(tmp_path, monkeypatch):
    """Review F11: GRAS findings are computed only from a converged GRAS; the report says why not."""
    from _sam_synthetic import write_blocks

    from pipeline.sam import run as samrun
    from pipeline.sam.balance import GrasResult

    layout = Layout.scratch(tmp_path)
    write_blocks(layout)
    monkeypatch.setattr(samrun, "EXPECTED_BLOCKS", tuple(BLOCKS))
    monkeypatch.setattr(
        samrun, "gras_sam", lambda p: GrasResult(p.prior * 3.0, 7, False, 1e3, ["GRAS did not converge (synthetic)"])
    )
    res = samrun.run_balance(layout)
    assert res["ok"] and res["counts"]["gras_findings"] == 0
    assert not pl.read_parquet(SamPaths(layout).log)["gras_finding"].any()
    assert "did NOT converge" in layout.balancing_report.read_text(encoding="utf-8")


def test_the_run_records_the_certificate_phase1_and_the_polish_per_entry(synthetic):
    base, result = synthetic
    assert result["certificate"]["ok"] and result["phase1"]["total_slack"] == 0
    assert result["solver"] == "NEWTON" and result["solver_options"]["path"] == "direct"
    log = pl.read_parquet(SamPaths(Layout.scratch(base)).log)
    assert {"polish_change", "cell_explanation_required", "explained"} <= set(log.columns)
