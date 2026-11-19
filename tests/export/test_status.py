"""Labels, flags and pinned totals (PLAN s.3.4, s.5.1 item 4).

The entry-label rule and the pin check are re-implemented here from the parquet files, independently of
pipeline/export/status.py and pinned.py, and compared with the export."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import polars as pl
import pytest
import yaml
from _export_helpers import REPO, SAM, TS

from pipeline.export.hierarchy import load_hierarchy
from pipeline.export.status import FLAG_BITS, LABEL_CODE, entry_label, split_of
from pipeline.sam.report import current_items, load_explanations, verdict

pytestmark = pytest.mark.export

SECTION_6B = {
    "government:gov.cofog.current_transfers",
    "government:gov.cofog.capital_transfers",
    "government:gov.r9d.railways",
    "government:gov.r9d.posts",
    "government:gov.r2.css_outside_treasury",
    "government:gov.r18.psu_revenue_grants",
    "taxes:t1.cgst",
    "taxes:t1.gces",
    "taxes:t1.uexc",
    "factors:f4b.centre",
    "taxes:t4a.nfpu",
}
GOLDEN = REPO / "pipeline" / "export" / "golden" / "status_cases.json"


def _entries_all(ex) -> list[dict]:
    out = []
    for node in load_hierarchy().level0:
        out.extend(ex.get(f"sam/entries/{node}.json")["entries"])
    return out


def _log() -> pl.DataFrame:
    e = pl.read_parquet(SAM / "sam_entries_balanced.parquet")
    log = pl.read_parquet(SAM / "balancing_log.parquet")
    return e.with_columns(log["explanation_required"], log["binding"])


def _items() -> dict:
    log = pl.read_parquet(SAM / "balancing_log.parquet")
    return {k: verdict(it["why"]) for k, it in current_items(log, load_explanations())}


def test_judgement_bands_are_section_6b_and_bind() -> None:
    ids = yaml.safe_load((REPO / "pipeline/export/judgement_bands.yaml").read_text())["judgement_bands"]
    assert set(ids) == SECTION_6B and len(ids) == 11
    b = pl.read_parquet(SAM / "balancing_constraints.parquet")
    binding = dict(zip(b["constraint_id"].to_list(), b["binding"].to_list(), strict=True))
    assert all(binding[i] for i in ids)


def test_entry_labels_independent(real) -> None:
    """s.3.4.1 re-implemented with polars expressions; counts 1,127 / 114 / 2,180 / 472."""
    e = _log()
    items = _items()
    has_item = [
        (r, c, f, k) in items or (r, c, "*", "*") in items
        for r, c, f, k in e.select("row", "col", "ref", "component").iter_rows()
    ]
    jb = SECTION_6B
    in_band = [any(x in jb for x in (b or "").split(",")) for b in e["binding"].to_list()]
    e = e.with_columns(pl.Series("has_item", has_item), pl.Series("in_band", in_band))
    lab = e.select(
        pl.when(
            (pl.col("role") == "free")
            & (pl.col("status") == "balanced")
            & (pl.col("explanation_required") | pl.col("has_item") | pl.col("in_band"))
        )
        .then(pl.lit("balancing_set"))
        .otherwise(pl.col("prior_status"))
        .alias("label")
    )["label"].to_list()
    assert set(lab) <= {"official", "derived", "estimated", "balancing_set"}  # the else branch is never reached
    counts = {k: lab.count(k) for k in ("official", "derived", "estimated", "balancing_set")}
    assert counts == {"official": 1127, "derived": 114, "estimated": 2180, "balancing_set": 472}
    exported = {(x["row"], x["col"], x["ref"], x["component"]): x["label"] for x in _entries_all(real)}
    keys = e.select("row", "col", "ref", "component").iter_rows()
    assert [exported[k] for k in keys] == lab
    s = real.get("summary.json")["sam"]["labels"]
    assert {k: v["entries"] for k, v in s.items()} == counts


def test_flags_match_definitions(real) -> None:
    items = _items()
    obs = {
        x["prov_id"]
        for x in yaml.safe_load((REPO / "pipeline/export/old_base_scope.yaml").read_text())["old_base_scope"]
    }
    for x in _entries_all(real):
        k = (x["row"], x["col"], x["ref"], x["component"])
        verdicts = {items.get(k), items.get((x["row"], x["col"], "*", "*"))}
        assert ("unexplained" in x["flags"]) == ("unexplained" in verdicts), k
        assert ("level_unexplained" in x["flags"]) == ("level unexplained" in verdicts), k
        assert ("old_base_structure" in x["flags"]) == (x["prov"] in obs), k
        assert ("discrepancy" in x["flags"]) == ("X_DISC" in (x["row"], x["col"])), k
        if x["v"] != 0:  # an entry that rounds to zero keeps the sign of its unrounded value
            assert ("has_negative" in x["flags"]) == (x["v"] < 0), k
        assert ("judgement_band" in x["flags"]) == any(b in SECTION_6B for b in x["binding"]), k


def test_old_base_scope_ids_exist() -> None:
    ids = [
        x["prov_id"]
        for x in yaml.safe_load((REPO / "pipeline/export/old_base_scope.yaml").read_text())["old_base_scope"]
    ]
    sp = set(pl.read_parquet(SAM / "_provenance.parquet")["prov_id"].to_list())
    assert all(i in sp for i in ids)
    assert len(ids) == len(set(ids))


def test_composition_sums_to_one(ex) -> None:
    s = ex.get("summary.json")
    assert sum(s["sam"]["composition"].values()) == pytest.approx(1, abs=1e-4)
    for slug in ("gst-rupee", "remittance-dubai", "deficit-funding"):
        for f in ex.get(f"stories/{slug}.json")["figures"].values():
            assert sum(f["composition"].values()) == pytest.approx(1, abs=1e-3)


def test_golden_status_cases() -> None:
    g = json.loads(GOLDEN.read_text())
    for c in g["entry_cases"]:
        try:
            got = entry_label({**c, "key": c["name"]})
        except ValueError:
            got = "error"
        assert got == c["label"], c["name"]
    for c in g["split_cases"]:
        a = c["abs"]
        comp, lab = split_of(a["o"], a["d"], a["e"], a["b"])
        assert lab == c["split"], c["name"]
        assert {k: round(v, 4) for k, v in comp.items()} == c["composition"], c["name"]
    assert g["flag_bits"] == FLAG_BITS
    assert {c["link"] for c in g["aggregate_cases"]} >= {"HH--PRDS", "ROW--HH", "HH--SI", "NFC--SI"}


def test_golden_aggregate_cases_match_export(real) -> None:
    g = json.loads(GOLDEN.read_text())
    pinned = real.get("sam/pinned.json")
    for c in g["aggregate_cases"]:
        assert pinned.get(c["link"], {}).get("total") == c["total"], c["name"]
        a = c["abs"]
        assert split_of(a["o"], a["d"], a["e"], a["b"])[1] == c["split"]
    assert LABEL_CODE["balancing_set"] == 3


# ---------------------------------------------------------------------------------- pinned totals


def _pins() -> tuple[dict[str, tuple[str, frozenset[int]]], list[tuple[str, str, str, str]]]:
    """Independent pins: narrow official/derived equal/band constraints inside their band, plus time-series
    flows whose 2023-24 check passes (members by the pipeline's entry selector for constraints, by the export's
    cover for series). Entries keyed by row index in the parquet; zero entries dropped."""
    from pipeline.export.inputs import constraint_members

    e = pl.read_parquet(SAM / "sam_entries_balanced.parquet")
    keys = list(e.select("row", "col", "ref", "component").iter_rows())
    bal = e["balanced"].to_list()
    c = pl.read_parquet(SAM / "constraints.parquet").join(
        pl.read_parquet(SAM / "balancing_constraints.parquet").select("constraint_id", "lo", "hi", "balanced_sum"),
        on="constraint_id",
    )
    members = constraint_members(e, c, load_hierarchy().codes)
    prov = {}
    for f in [SAM / "_provenance.parquet", TS / "_provenance.parquet"]:
        prov |= dict(pl.read_parquet(f).select("prov_id", "status").iter_rows())
    pins: dict[str, tuple[str, frozenset[int]]] = {}
    for r in c.iter_rows(named=True):
        if r["kind"] not in ("equal", "band"):
            continue
        tol = max(r["tol_abs"] or 0, (r["tol_rel"] or 0) * abs(r["target"]))
        if tol > max(1.0, 0.001 * abs(r["target"])) or prov[r["prov_id"]] not in ("official", "derived"):
            continue
        if not (r["lo"] - 0.01 <= r["balanced_sum"] <= r["hi"] + 0.01):
            continue
        s = frozenset(int(i) for i in members[r["constraint_id"]] if abs(bal[int(i)]) >= 0.005)
        if s:
            pins[r["constraint_id"]] = (prov[r["prov_id"]], s)
    return pins, keys


def _cover(target: frozenset[int], pins: dict[str, tuple[str, frozenset[int]]]) -> bool:
    cands = [s for _, s in pins.values() if s <= target]
    if not cands or frozenset().union(*cands) != target:
        return False

    def go(rem: frozenset[int]) -> bool:
        if not rem:
            return True
        x = min(rem)
        return any(go(rem - s) for s in cands if x in s and s <= rem)

    return go(target)


def test_level0_pinned_pairs(real) -> None:
    """The 16 level-0 pairs whose whole entry set is pinned (s.3.4.2), and every listed pin set is an exact
    disjoint cover of its link's entries."""
    pinned = real.get("sam/pinned.json")
    l0 = set(load_hierarchy().level0)
    whole = set()
    for k in pinned:
        base, _, suf = k.partition("~")
        a, b = base.split("--")
        if (
            a in l0
            and b in l0
            and (suf == "pair" or (suf == "" and f"{base}~neg" not in pinned and f"{base}~pair" not in pinned))
        ):
            whole.add(base)
    # pairs with both parts present and only the positive part pinned are not "whole"
    cells = real.get("sam/cells.json")
    h = real.get("hierarchy.json")
    codes = [x["code"] for x in h["accounts"]]
    l0_of = {x["code"]: x["l0"] for x in h["accounts"]}
    has_neg = {
        f"{l0_of[codes[c]]}--{l0_of[codes[r]]}"
        for r, c, v in zip(cells["row"], cells["col"], cells["v"], strict=True)
        if v < 0
    }
    whole = {w for w in whole if not (w in has_neg and f"{w}~pair" not in pinned)}
    assert len(whole) == 16, sorted(whole)
    for must in (
        "HH--PRDS",
        "ROW--HH",
        "HH--SI",
        "FACT--HH",
        "PROD--FACT",
        "FC--SI",
        "PRDS--ROW",
        "ROW--PRDS",
        "HH--DISC",
        "DISC--ROW",
    ):
        assert must in whole
    assert "NFC--SI" not in pinned


def test_pinned_constraint_covers_are_exact(real) -> None:
    """For every pinned link whose pins are all constraints, recompute the link's entries and check the
    pins are an exact disjoint cover (independent of pinned.py). 200 links max, in sorted order."""
    pins, keys = _pins()
    pinned = real.get("sam/pinned.json")
    h = load_hierarchy()
    uni = {n: set(x.accounts) for n, x in h.nodes.items()}
    uni["PRODUCERS"] = uni["PRDS"] | uni["PROD"]
    bal = pl.read_parquet(SAM / "sam_entries_balanced.parquet")["balanced"].to_list()
    cellv: dict = defaultdict(float)
    for i, (r, c, _, _) in enumerate(keys):
        cellv[(r, c)] += bal[i]
    checked = 0
    for k in sorted(pinned):
        v = pinned[k]
        if any(p.startswith("ts:") for p in v["pins"]):
            continue
        base, _, suf = k.partition("~")
        a, b = base.split("--")
        part = {"": 1, "neg": -1, "pair": 0}[suf]
        ents = frozenset(
            i for i, (r, c, _, _) in enumerate(keys)
            if c in uni[a] and r in uni[b] and abs(bal[i]) >= 0.005
            and (part == 0 or round(cellv[(r, c)], 2) * part > 0)
        )  # fmt: skip
        chosen = [pins[p][1] for p in v["pins"]]
        assert sum(len(s) for s in chosen) == len(frozenset().union(*chosen)), k  # disjoint
        assert frozenset().union(*chosen) == ents, k
        assert _cover(ents, pins), k
        checked += 1
        if checked >= 200:
            break
    assert checked >= 50


def test_no_nan_in_cells(ex) -> None:
    c = ex.get("sam/cells.json")
    assert all(math.isfinite(x) for x in c["v"])
    assert all(0 <= f < 128 for f in c["flags"])
    _ = Path  # keep import for type checkers
