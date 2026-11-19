"""The 2023-24 check of the top-flows time series against the SAM (plan s.7 T3/T4; DESIGN_BRIEF s.8): each
flow's 2023-24 value equals its definition as a sum of SAM cells within its class tolerance, or the difference
is a registered bridge (optional_refs: refs of a definition allowed to have no entry). The SAM sums are
recomputed here from the entry files with plain polars filters (not with pipeline.timeseries code); the
balanced-SAM tests skip until data/sam/2023-24/sam_entries_balanced.parquet exists (balancing runs after every
block is built)."""

from __future__ import annotations

import polars as pl
import pytest
from _ts_helpers import LAYOUT, output, value

from pipeline.core import io
from pipeline.sam.accounts import Accounts
from pipeline.sam.framework import SamPaths
from pipeline.timeseries import build as ts

pytestmark = pytest.mark.sam

PATHS = SamPaths(LAYOUT)
YEAR = "2023-24"
FLOWS = io.read_yaml(ts.FLOWS_YAML)
EXPL = {e["flow_id"]: e for e in io.read_yaml(ts.EXPLANATIONS_YAML)["explanations"]}
ACC = Accounts.load()


def _expand(tokens: list[str]) -> list[str]:
    out: list[str] = []
    for t in tokens:
        if t.startswith("@"):
            out += ACC.in_group(t[1:])
        elif t.startswith("$"):
            out += FLOWS["account_sets"][t[1:]]
        else:
            out.append(t)
    return out


def _sam_sum(flow: dict, ent: pl.DataFrame) -> tuple[float, float, int]:
    """(value, anchored allowance, matched entries) of a flow's SAM definition on an entry table."""
    total = allowance = 0.0
    n = 0
    prior = "prior" if "prior" in ent.columns else "value"
    for t in flow["sam"]["terms"]:
        m = ent.filter(
            pl.col("row").is_in(_expand(t["rows"]))
            & pl.col("col").is_in(_expand(t["cols"]))
            & pl.col("ref").is_in(t["refs"])
        )
        if t.get("components") is not None:
            m = m.filter(pl.col("component").is_in(t["components"]))
        if t.get("bop_functions") is not None:
            m = m.filter(pl.col("bop_function").is_in(t["bop_functions"]))
        if t.get("exclude_components"):
            m = m.filter(~pl.col("component").is_in(t["exclude_components"]).fill_null(False))
        total += float(t.get("coef", 1)) * float(m["value"].sum())
        a = m.filter(pl.col("role") == "anchored")
        allowance += float((a["tol_rel"] * a[prior].abs()).sum())
        n += m.height
    return total, allowance, n


def _ts_2023_24(rows: pl.DataFrame, fid: str) -> float | None:
    r = rows.filter(
        (pl.col("flow_id") == fid) & (pl.col("period") == YEAR) & (pl.col("variant") == "published")
        & (pl.col("base_year").is_null() | (pl.col("base_year") == "2022-23"))
    )  # fmt: skip
    assert r.height <= 1, fid
    return float(r["value"][0]) if r.height else None


def _bridge(fid: str) -> float:
    return sum(
        float(b.get("coef", 1)) * value(b["dataset"], b["id"], YEAR)
        for b in EXPL.get(fid, {}).get("bridge_series") or []
    )


@pytest.fixture(scope="module")
def check() -> pl.DataFrame:
    return output("top_flows_sam_check.parquet")


@pytest.fixture(scope="module")
def rows() -> pl.DataFrame:
    return output("top_flows.parquet")


def test_check_table_covers_every_flow(check, rows):
    ids = [f["id"] for f in FLOWS["flows"]]
    assert sorted(check["flow_id"]) == sorted(ids)
    assert set(check["verdict"]) <= set(ts.VERDICTS)
    for f in FLOWS["flows"]:
        c = check.filter(pl.col("flow_id") == f["id"]).row(0, named=True)
        tsv = _ts_2023_24(rows, f["id"])
        if f["check_class"] == "none":
            assert c["verdict"] == "no_check"
            continue
        assert tsv is not None and c["ts_value"] == tsv, f"{f['id']}: every checked flow has a 2023-24 value"
        if f["check_class"] in ("C", "D"):
            assert abs(c["bridge"] - _bridge(f["id"])) < 1e-6, f["id"]
    if not PATHS.balanced_entries.exists():
        assert set(check["verdict"]) == {"pending_balancing", "no_check"}
    else:
        assert "pending_balancing" not in set(check["verdict"]), "re-run `timeseries` after balancing"


def test_explanations_are_well_formed():
    ids = {f["id"]: f for f in FLOWS["flows"]}
    for fid, e in EXPL.items():
        assert fid in ids and ids[fid]["check_class"] in ("C", "D"), fid
        assert e["why"].strip()
        assert e.get("explained_residual") is None or isinstance(e["explained_residual"], (int, float))
        _bridge(fid)  # every bridge series exists in clean data with a 2023-24 value


def test_flows_from_production_equal_their_sam_definition_on_its_entries(rows):
    """Early check before balancing: flows whose cells production writes (as published SUT cells) equal the
    NAS 2026 series within max(Rs 5 crore, the entries' anchored allowance of Rs 1 crore per SUT cell)."""
    if not PATHS.built("production"):
        pytest.skip("production block not built")
    ent = pl.read_parquet(PATHS.entries("production"))
    by_id = {f["id"]: f for f in FLOWS["flows"]}
    for fid in ("F05", "F06", "F07", "F08", "F13", "M03", "M04", "M10"):
        sam, allowance, n = _sam_sum(by_id[fid], ent)
        tsv = _ts_2023_24(rows, fid)
        assert n > 0 and tsv is not None, fid
        assert abs(sam - tsv) <= max(5.0, allowance), (fid, sam, tsv, allowance)


def test_government_interest_and_pensions_bridge_onto_the_block_entries(rows):
    """Before balancing (verification TSV-3, TSV-4, TSV-7): F25-F28 are class C, and TS + the registered clean
    bridge equals their SAM definition on the built blocks' entries within the class tolerance, i.e. the
    bridges reproduce the owning controls (fincorp r3b.union/states_nas_concept, government gov.r9.centre/states).
    Balancing may then move them within those controls' bands."""
    if not all(PATHS.built(b) for b in ("fincorp", "government", "rest_of_world")):
        pytest.skip("fincorp, government or rest_of_world not built")
    cols = ["row", "col", "ref", "component", "value", "role", "tol_rel", "bop_function"]
    ent = pl.concat([pl.read_parquet(p).select(cols) for p in sorted(PATHS.blocks.glob("*_entries.parquet"))])
    by_id = {f["id"]: f for f in FLOWS["flows"]}
    for fid in ("F25", "F26", "F27", "F28"):
        assert by_id[fid]["check_class"] == "C" and EXPL[fid]["bridge_series"], fid
        sam, _, n = _sam_sum(by_id[fid], ent)
        tsv = _ts_2023_24(rows, fid)
        assert n > 0 and tsv is not None, fid
        resid = sam - tsv - _bridge(fid)
        assert abs(resid) <= max(500.0, 0.01 * abs(tsv)), (fid, sam, tsv, _bridge(fid), resid)


@pytest.fixture(scope="module")
def balanced() -> pl.DataFrame:
    if not PATHS.balanced_entries.exists():
        pytest.skip("no balanced SAM yet (data/sam/2023-24/sam_entries_balanced.parquet): balancing runs next")
    return pl.read_parquet(PATHS.balanced_entries)


def test_each_flow_equals_its_sam_definition_on_the_balanced_sam(balanced, rows, check):
    problems = []
    for f in FLOWS["flows"]:
        cls = f["check_class"]
        if cls == "none":
            continue
        fid = f["id"]
        tsv = _ts_2023_24(rows, fid)
        sam, allowance, n = _sam_sum(f, balanced)
        c = check.filter(pl.col("flow_id") == fid).row(0, named=True)
        assert abs(c["sam_balanced"] - sam) <= 1e-6 * max(1.0, abs(sam)), f"{fid}: check file vs recomputation"
        diff = sam - tsv
        if cls == "A":
            tol, resid = max(float(f.get("tol_abs") or 5.0), allowance), diff
        elif cls == "B":
            tol, resid = max(5.0, float(f["tol_rel"]) * abs(tsv)), diff
        elif cls == "C":
            tol, resid = max(500.0, 0.01 * abs(tsv)), diff - _bridge(fid)
        else:
            tol, resid = 5.0, diff - _bridge(fid)
        if abs(resid) <= tol:
            continue
        ex = EXPL.get(fid, {}).get("explained_residual")
        if ex is not None and abs(resid - ex) <= max(0.2 * abs(ex), 500.0):
            continue
        problems.append(f"{fid} ({cls}): TS {tsv:,.2f} SAM {sam:,.2f} residual {resid:+,.2f} > tol {tol:,.2f}")
    assert not problems, "flows whose 2023-24 value differs from the SAM without an explanation:\n" + "\n".join(
        problems
    )


def test_definitions_cover_their_cell_blocks(balanced, check):
    """T4: every ref, component and bop tag a definition names exists in the balanced entries, no other ref sits
    in a flow's cell blocks unless it is explicitly excluded, and no entry is counted twice."""
    problems = []
    for f in FLOWS["flows"]:
        if not f["sam"]["terms"]:
            continue
        named = {r for t in f["sam"]["terms"] for r in t["refs"]}
        excluded = set(f["sam"].get("excluded_refs") or [])
        keys: list[tuple] = []
        for t in f["sam"]["terms"]:
            blk = balanced.filter(pl.col("row").is_in(_expand(t["rows"])) & pl.col("col").is_in(_expand(t["cols"])))
            extra = set(blk["ref"]) - named - excluded
            if extra:
                problems.append(f"{f['id']}: refs {sorted(extra)} in its cells are neither listed nor excluded")
            sel = blk.filter(pl.col("ref").is_in(t["refs"]))
            for r in t["refs"]:
                if r not in (t.get("optional_refs") or []) and not sel.filter(pl.col("ref") == r).height:
                    problems.append(f"{f['id']}: ref {r} has no entry in rows {t['rows']} x cols {t['cols']}")
            for c in t.get("components") or []:
                if not sel.filter(pl.col("component") == c).height:
                    problems.append(f"{f['id']}: component {c} not found")
            if t.get("components") is not None:
                sel = sel.filter(pl.col("component").is_in(t["components"]))
            for b in t.get("bop_functions") or []:
                if not sel.filter(pl.col("bop_function") == b).height:
                    problems.append(f"{f['id']}: bop_function {b} not found")
            if t.get("bop_functions") is not None:
                sel = sel.filter(pl.col("bop_function").is_in(t["bop_functions"]))
            if t.get("exclude_components"):
                sel = sel.filter(~pl.col("component").is_in(t["exclude_components"]).fill_null(False))
            keys += list(sel.select("row", "col", "ref", "component").iter_rows())
        if len(keys) != len(set(keys)):
            problems.append(f"{f['id']}: an entry is matched by two terms")
    assert not problems, "\n".join(problems)
    # the build's own guard columns agree
    assert check.filter(pl.col("overlapping_entries") > 0).height == 0
    assert check["unlisted_refs"].null_count() == check.height
    assert check["missing_selectors"].null_count() == check.height


def test_check_machinery_on_a_partial_sam(rows):
    """The verdict logic and the T4 guards, exercised on production's entries standing in for a balanced SAM
    (every other block's cells are empty, so their flows must fail or be unexplained, not pass)."""
    if not PATHS.built("production"):
        pytest.skip("production block not built")
    ent = pl.read_parquet(PATHS.entries("production"))
    fake = ent.with_columns(pl.col("value").alias("prior")).select(
        "row", "col", "ref", "component", "value", "role", "tol_rel", "bop_function", "prior"
    )
    defs = ts.load_definitions()
    flows = {f.flow_id: f for f in defs.flows}
    ev = ts.eval_sam(flows["F05"], fake)
    assert ev.missing == [] and ev.unlisted == [] and ev.overlapping == 0 and ev.n_entries > 0
    assert "term1:ref=P7a" in ts.eval_sam(flows["F12"], fake).missing
    stray = fake.head(1).with_columns(pl.lit("C_FOOD").alias("row"), pl.lit("R_ROW").alias("col"),
                                      pl.lit("R13").alias("ref"))  # fmt: skip
    assert ts.eval_sam(flows["F05"], pl.concat([fake, stray])).unlisted == ["R13"]
    reader = ts.Reader(ts.CleanIndex(LAYOUT))
    expl = ts.load_explanations()
    chk = ts.sam_check(reader, defs, rows, expl, None, None, fake)
    verdict = dict(chk.select("flow_id", "verdict").iter_rows())
    assert verdict["F05"] == verdict["F07"] == verdict["M03"] == "pass"
    assert verdict["F01"] == "fail" and verdict["F14"] == "unexplained" and verdict["M15"] == "no_check"
    resid = chk.filter(pl.col("flow_id") == "F14")["residual"][0]
    expl2 = {**expl, "F14": {**expl["F14"], "explained_residual": resid * 1.1}}
    chk2 = ts.sam_check(reader, defs, rows, expl2, None, None, fake)
    assert chk2.filter(pl.col("flow_id") == "F14")["verdict"][0] == "explained"  # within the 20% drift rule
