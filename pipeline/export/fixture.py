"""The generated fixture (docs/phase3/PLAN.md s.3.10): `python -m pipeline export --fixture`.

A synthetic, balanced SAM on the REAL 128 accounts, hierarchy and cell pattern, with synthetic entries,
constraints, explanation items, provenance, time series and satellites, run through the same writer as the
real export (pipeline/export/build.py). Written to web/fixtures/data/ with `fixture: true` and data version
2023-24.fixture0000, so a build on it can never be mistaken for the real data.

Every number is synthetic: SAM cells start as |real cell| x U(0.5, 1.5) (seeded, numpy default_rng(20261002))
with the real sign pattern and are balanced with the pipeline's sign-preserving GRAS to account totals of
1.07 x the real ones; series values are |real| x U(0.7, 1.3)
with the real signs, gaps and markers. Structure (account codes, refs, components, flow definitions, story
specs) is real so the fixture exercises every code path.

Deviations from the PLAN text, on purpose (logged in docs/phase3/issues/U1.md): the fixture keeps the real
sign pattern (66 negative cells, not exactly 2) and all real entry keys per cell (not 1-3), because the stories
and the top-flows board reference real negative links and real entry selectors; a fixture without them would
fail the same validation the real export passes.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
import polars as pl

from pipeline.core import io
from pipeline.core.paths import Layout
from pipeline.export.hierarchy import HIERARCHY_FILE, load_hierarchy
from pipeline.export.inputs import (
    YEAR,
    ExportError,
    ExportInputs,
    constraint_members,
    load_config,
    load_stories,
)

SEED = 20261002
LANDING = "https://example.invalid/"
SOURCE = "fixture"


def _fid(kind: str, key: str) -> str:
    return f"fixture_{kind}:" + hashlib.sha256(key.encode()).hexdigest()[:12]


def fixture_inputs(layout: Layout | None = None) -> ExportInputs:
    from pipeline.sam.accounts import gap_map as read_gap_map
    from pipeline.sam.balance import gras
    from pipeline.timeseries.build import load_definitions

    layout = layout or Layout.default()
    rng = np.random.default_rng(SEED)
    hier = load_hierarchy()
    codes = hier.codes
    idx = hier.idx
    sam_dir = layout.sam / YEAR
    real_sam = pl.read_parquet(sam_dir / "sam_balanced.parquet").sort("row", "col")
    real_ent = pl.read_parquet(sam_dir / "sam_entries_balanced.parquet")
    # zero cells (the D4 GDP expenditure discrepancy) stay exactly zero, as in the real SAM

    # ---- 1. synthetic balanced SAM on the real pattern and signs --------------------------------------
    rows = real_sam["row"].to_list()
    cols = real_sam["col"].to_list()
    rv = real_sam["value"].to_numpy()
    rv = np.where(np.abs(rv) < 0.005, 0.0, rv)
    a = np.sign(rv) * np.abs(rv) * rng.uniform(0.5, 1.5, size=len(rv))
    ri = np.array([idx[r] for r in rows])
    ci = np.array([idx[c] for c in cols])
    n = len(codes)
    # Targets: the real account totals x 1.07. The real SAM (x 1.07) is a feasible point with the same pattern
    # and signs, so the sign-preserving GRAS converges; the cells themselves are random.
    target = np.bincount(ri, weights=rv, minlength=n) * 1.07
    res = gras(ri, ci, a, target, target, max_iter=20000, tol=1e-6)
    if not res.converged:
        raise ExportError("fixture: GRAS did not balance the synthetic SAM: " + "; ".join(res.messages))
    x = res.x
    if np.any(np.sign(x) != np.sign(a)):
        raise ExportError("fixture: GRAS changed a sign")
    sam = pl.DataFrame({"row": rows, "col": cols, "value": x})

    # ---- 2. synthetic entries: the real entry keys of each cell, the cell value split by random weights ----
    keys_by_cell: dict[tuple[str, str], list[tuple[str, str, str | None]]] = {}
    for r, c, ref, comp, bop in real_ent.select("row", "col", "ref", "component", "bop_function").iter_rows():
        keys_by_cell.setdefault((r, c), []).append((ref, comp, bop))
    prov_ids = {
        "clean": [_fid("clean", f"leaf{i}") for i in range(12)],
        "sam": [_fid("sam", f"rec{i}") for i in range(24)],
    }
    assumption_id = _fid("sam", "assumption")
    dependent_id = _fid("sam", "uses-assumption")
    cfg = load_config()
    old_base = [str(x["prov_id"]) for x in cfg["old_base_scope"]["old_base_scope"]]
    recs: list[dict[str, Any]] = []
    ent_rows: list[dict[str, Any]] = []
    statuses = ("official", "derived", "estimated")
    for k, (r, c) in enumerate(zip(rows, cols, strict=True)):
        keys = keys_by_cell.get((r, c))
        if not keys:
            raise ExportError(f"fixture: no real entry key for cell {r} <- {c}")
        w = rng.uniform(0.2, 1.0, size=len(keys))
        parts = x[k] * w / w.sum() if x[k] != 0 else np.zeros(len(keys))
        for (ref, comp, bop), v in zip(keys, parts, strict=True):
            j = len(ent_rows)
            ps = statuses[int(rng.integers(0, 3))]
            role = ("fixed", "anchored", "free", "free")[int(rng.integers(0, 4))]
            prior = float(v) * float(rng.uniform(0.85, 1.15))
            moved = abs(v - prior) >= 1.0 and role != "fixed"
            p0 = prior if role != "fixed" else float(v)  # a fixed entry does not move: prior = balanced
            status = "balanced" if moved else ps
            if j % 97 == 5:
                pid = old_base[j % len(old_base)]
            elif j % 89 == 7:
                pid = dependent_id
            else:
                pid = prov_ids["sam"][j % len(prov_ids["sam"])]
            from pipeline.sam.spec import needs_explanation

            ent_rows.append(
                {
                    "row": r,
                    "col": c,
                    "ref": ref,
                    "component": comp,
                    "value": float(v),
                    "status": status if role != "fixed" else ps,
                    "role": role,
                    "tol_rel": 0.05 if role == "anchored" else None,
                    "confidence": ("high", "medium", "low")[j % 3],
                    "bop_function": bop,
                    "prov_id": pid,
                    "note": None,
                    "block": "fixture",
                    "prior": p0,
                    "balanced": float(v),
                    "change": float(v) - p0,
                    "prior_status": ps,
                    "explanation_required": bool(role != "fixed" and needs_explanation(prior, float(v))),
                    # percent, as pipeline/sam/run.py writes the balancing log (100 x change / |prior|)
                    "pct_change": 100.0 * (float(v) - p0) / abs(p0) if p0 else None,
                    "cell_explanation_required": False,
                }
            )
    entries = pl.DataFrame(ent_rows, infer_schema_length=None).with_columns(
        pl.col("tol_rel").cast(pl.Float64),
        pl.col("bop_function").cast(pl.String),
        pl.col("pct_change").cast(pl.Float64),
    )

    # ---- 3. constraints: the 11 judgement bands (binding), pins, and some others ---------------------------
    jb = [str(x) for x in cfg["judgement_bands"]["judgement_bands"]]
    cells = list(zip(rows, cols, strict=True))
    cons_rows: list[dict[str, Any]] = []
    official_rec = _fid("sam", "official-constraint")
    estimated_rec = _fid("sam", "estimated-constraint")

    def add_con(cid: str, rset: list[str], cset: list[str], kind: str, prov: str, binding: bool, tol: float) -> None:
        sel = entries.filter(pl.col("row").is_in(rset) & pl.col("col").is_in(cset))
        tot = float(sel["balanced"].sum())
        cons_rows.append(
            {
                "constraint_id": cid,
                "declared_by": "fixture",
                "ref": str(sel["ref"][0]) if sel.height else "",
                "rows": ",".join(rset),
                "cols": ",".join(cset),
                "refs": "",
                "components": "",
                "target": tot,
                "tol_abs": tol,
                "tol_rel": 0.0,
                "kind": kind,
                "prov_id": prov,
                "description": f"Fixture constraint {cid} (synthetic)",
                "lo": tot - tol if kind != "max" else float("-inf"),
                "hi": tot + tol if kind != "min" else float("inf"),
                "balanced_sum": tot,
                "binding": binding,
            }
        )

    eligible = [cl for cl in cells if "X_DISC" not in cl]
    for t, cid in enumerate(jb):
        r, c = eligible[(t * 131 + 17) % len(eligible)]
        add_con(
            cid,
            [r],
            [c],
            "band",
            estimated_rec,
            True,
            0.05 * abs(sam.filter((pl.col("row") == r) & (pl.col("col") == c))["value"][0]),
        )
    hh = hier.node_accounts("HH")
    com = [c for c in codes if c.startswith("C_")]
    add_con("fixture:hh.consumption", com, hh, "equal", official_rec, True, 1.0)
    add_con("fixture:row.remittances", hh, ["R_ROW"], "equal", official_rec, False, 1.0)
    add_con("fixture:hh.saving", ["K_HH"], hh, "equal", official_rec, True, 1.0)
    for t in range(40):
        r, c = eligible[(t * 53 + 3) % len(eligible)]
        add_con(
            f"fixture:cell.{t:02d}", [r], [c], ("equal", "band", "max", "min")[t % 4], official_rec, t % 3 == 0, 1.0
        )
    constraints = pl.DataFrame(cons_rows, infer_schema_length=None)
    members = constraint_members(entries, constraints, codes)
    constraints = constraints.with_columns(
        pl.Series("n_members", [len(members[c]) for c in constraints["constraint_id"].to_list()], dtype=pl.Int64)
    )
    binding_of: dict[int, list[str]] = {}
    for cid, b in zip(constraints["constraint_id"].to_list(), constraints["binding"].to_list(), strict=True):
        if b:
            for i in members[cid]:
                binding_of.setdefault(int(i), []).append(cid)
    entries = entries.with_columns(
        pl.Series(
            "binding", [",".join(sorted(binding_of.get(i, []))) or None for i in range(entries.height)], dtype=pl.String
        )
    )

    # ---- 4. explanation items (every verdict, one cell-level item) ------------------------------------------
    items: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    verdicts = ("explained", "level unexplained", "unexplained")
    req = entries.with_row_index("i").filter(pl.col("explanation_required"))
    for t, r in enumerate(req.iter_rows(named=True)):
        if t % 2:
            continue
        v = verdicts[t // 2 % 3]
        items[(r["row"], r["col"], r["ref"], r["component"])] = {
            "verdict": v,
            "why": f"{v.capitalize()}: synthetic fixture explanation for this entry (not real data).",
        }
    multi = [k for k, ks in keys_by_cell.items() if len(ks) > 1 and k in set(cells)]
    if multi:
        r, c = multi[0]
        items[(r, c, "*", "*")] = {"verdict": "unexplained", "why": "Unexplained: synthetic fixture cell-level item."}

    # ---- 5. provenance --------------------------------------------------------------------------------------
    for i, pid in enumerate(prov_ids["clean"]):
        recs.append(
            _rec(pid, "fixture_clean", url=f"{LANDING}table/{i}", status="official", table=f"Fixture table {i}")
        )
    recs.append(
        _rec(_fid("clean", "no-url"), "fixture_clean", url=None, status="official", table="Fixture table without URL")
    )
    for i, pid in enumerate(prov_ids["sam"]):
        ins = [prov_ids["clean"][i % 12], prov_ids["clean"][(i * 5 + 1) % 12]]
        if i == 3:
            ins.append(_fid("clean", "no-url"))
        recs.append(_rec(pid, "fixture_sam", inputs=ins, status=statuses[i % 3], method="Synthetic fixture record."))
    for pid in old_base:
        recs.append(_rec(pid, "fixture_sam", inputs=[prov_ids["clean"][0]], status="estimated",
                         method="Synthetic fixture record standing in for an old-base-structure record."))  # fmt: skip
    recs.append(
        _rec(assumption_id, "fixture_sam", inputs=[], status="estimated", method="Assumption parameter (synthetic).")
    )
    recs.append(_rec(dependent_id, "fixture_sam", inputs=[assumption_id, prov_ids["clean"][1]], status="estimated",
                     method="Synthetic record that uses the assumption parameter."))  # fmt: skip
    recs.append(
        _rec(
            official_rec,
            "fixture_sam",
            inputs=[prov_ids["clean"][2]],
            status="official",
            method="Synthetic official total.",
        )
    )
    recs.append(
        _rec(estimated_rec, "fixture_sam", inputs=[prov_ids["clean"][3]], status="estimated", method="Synthetic band.")
    )

    # ---- 6. time series: real structure, synthetic values ----------------------------------------------------
    ts_dir = layout.clean.parent / "timeseries"
    real_ts = pl.read_parquet(ts_dir / "top_flows.parquet")
    ts_defs = pl.read_parquet(ts_dir / "top_flows_definitions.parquet")
    real_check = pl.read_parquet(ts_dir / "top_flows_sam_check.parquet")
    factor = rng.uniform(0.7, 1.3, size=real_ts.height)
    ts_prov: dict[str, str] = {}
    for p in real_ts["prov_id"].unique().sort().to_list():
        ts_prov[p] = _fid("ts", p)
        recs.append(_rec(ts_prov[p], "fixture_ts", inputs=[prov_ids["clean"][hash_index(p, 12)]], status="official",
                         method="Synthetic fixture series record."))  # fmt: skip
    ts = real_ts.with_columns(
        (pl.col("value") * pl.Series(factor)).alias("value"),
        pl.col("prov_id").replace_strict(ts_prov, default=None).alias("prov_id"),
        pl.lit(None, dtype=pl.String).alias("note"),
    )
    # GDP keeps a single scale per base so shares stay sensible: M01 = real M01 x 1 (structure), others scaled
    m01 = real_ts.filter(pl.col("flow_id") == "M01")
    ts = ts.filter(pl.col("flow_id") != "M01").vstack(
        m01.with_columns(
            pl.col("prov_id").replace_strict(ts_prov, default=None), pl.lit(None, dtype=pl.String).alias("note")
        )
    )
    defs = load_definitions(layout=layout)
    flows = {f.flow_id: f for f in defs.flows}

    # synthetic check: verdicts as in the real run, values from the fixture
    from pipeline.timeseries.build import eval_sam

    ent_eval = entries.select("row", "col", "ref", "component", pl.col("balanced").alias("value"), "role", "tol_rel",
                              "bop_function", "prior")  # fmt: skip
    chk = []
    for r in real_check.iter_rows(named=True):
        fid = r["flow_id"]
        tv = ts.filter((pl.col("flow_id") == fid) & (pl.col("period") == YEAR) & (pl.col("variant") == "published"))
        tsv = float(tv.sort("base_year", descending=True, nulls_last=True)["value"][0]) if tv.height else None
        sv = eval_sam(flows[fid], ent_eval).value if flows[fid].sam_terms else None
        rel = (sv - tsv) / tsv if tsv and sv is not None else None
        expl = None if r["verdict"] == "pass" else "Synthetic fixture explanation."
        chk.append({**r, "ts_value": tsv, "sam_balanced": sv, "rel_diff": rel, "explanation": expl})
    ts_check = pl.DataFrame(chk, schema=real_check.schema)

    # ---- 7. satellites the stories and the methodology page read ---------------------------------------------
    sats: dict[str, pl.DataFrame] = {}
    tables = {"households/hh_keys"}
    for spec in load_stories().values():
        for f in (spec.get("figures") or {}).values():
            if isinstance(f, dict) and "table" in f:
                tables.add(str(f["table"]))
    sat_rec = _fid("sam", "satellite")
    recs.append(
        _rec(sat_rec, "fixture_sam", inputs=[prov_ids["clean"][4]], status="estimated", method="Synthetic satellite.")
    )
    for t in sorted(tables):
        block, _, name = t.partition("/")
        df = pl.read_parquet(sam_dir / "blocks" / f"{block}_satellites" / f"{name}.parquet")
        f2 = rng.uniform(0.7, 1.3, size=df.height)
        df = df.with_columns((pl.col("value") * pl.Series(f2)).alias("value"))
        if "prov_id" in df.columns:
            df = df.with_columns(pl.lit(sat_rec).alias("prov_id"))
        sats[t] = df

    prov = {r["prov_id"]: r for r in recs}
    registry = {
        SOURCE: {
            "id": SOURCE,
            "name": "Synthetic fixture data (not real)",
            "publisher": "India SAM project (generated)",
            "urls": {"landing": LANDING, "data": [LANDING]},
            "license": {"name": "Synthetic test data", "attribution": "Synthetic fixture: not for citation."},
            "verification": {"status": "fixture"},
        }
    }
    hashes = {
        "pipeline/export/hierarchy.yaml": io.sha256_file(HIERARCHY_FILE),
        "pipeline/sam/accounts.yaml": io.sha256_file(layout.root / "pipeline" / "sam" / "accounts.yaml"),
    }
    return ExportInputs(
        hierarchy=hier,
        sam=sam,
        entries=entries,
        items=items,
        constraints=constraints,
        members=members,
        prov=prov,
        registry=registry,
        gap_map={k: dict(v) for k, v in read_gap_map(str(layout.gap_map)).items()},
        run={"status": "optimal", "iterations": int(res.iterations), "max_imbalance": float(res.max_gap)},
        ts=ts,
        ts_defs=ts_defs,
        ts_check=ts_check,
        ts_flows=flows,
        config=cfg,
        stories=load_stories(),
        satellites=sats,
        input_hashes=hashes,
        fixture=True,
        layout=None,
        gdp_sam_check=None,
    )


def hash_index(s: str, n: int) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16) % n


def _rec(
    pid: str,
    unit: str,
    *,
    url: str | None = None,
    inputs: list[str] | None = None,
    status: str = "official",
    table: str = "",
    method: str = "",
) -> dict[str, Any]:
    return {
        "prov_id": pid,
        "ingest_unit": unit,
        "source_id": SOURCE,
        "url": url,
        "retrieved_at": "2026-10-02" if url else None,
        "table_id": table or pid,
        "locator": None,
        "unit_as_published": "Rs crore",
        "conversion": None,
        "price_basis": "current",
        "base_year": "2022-23",
        "vintage": "fixture",
        "status": status,
        "method": method or "Synthetic fixture leaf.",
        "inputs": ",".join(inputs or []) or None,
    }
