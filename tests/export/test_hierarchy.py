"""The zoom hierarchy (PLAN s.3.2): structure rules and the prototype figures on the real SAM."""

from __future__ import annotations

from collections import defaultdict

import polars as pl
import pytest
from _export_helpers import SAM

from pipeline.export.hierarchy import load_hierarchy, visible_nodes
from pipeline.sam.accounts import Accounts

pytestmark = pytest.mark.export


def test_every_account_once_and_ids() -> None:
    h = load_hierarchy()
    leaves = [n.id for n in h.nodes.values() if n.level == 2]
    assert sorted(leaves) == sorted(Accounts.load().codes)
    assert len(leaves) == len(set(leaves)) == 128
    assert sum(n.level == 0 for n in h.nodes.values()) == 13
    assert sum(n.level == 1 for n in h.nodes.values()) == 27
    assert len(h.nodes) == 168
    for n in h.nodes.values():
        if n.level == 0:
            assert n.id.isupper() and "." not in n.id
        elif n.level == 1:
            assert n.id.split(".")[0] == n.parent and len(n.children) >= 2


def test_parent_child_consistency_and_order() -> None:
    h = load_hierarchy()
    orders = [n.order for n in h.nodes.values()]
    assert len(set(orders)) == len(orders)
    for n in h.nodes.values():
        for c in n.children:
            assert h.nodes[c].parent == n.id
            assert h.nodes[c].col == n.col
            assert h.nodes[c].order > n.order
        if n.parent:
            assert n.id in h.nodes[n.parent].children
        acc = sorted(a for c in n.children for a in h.nodes[c].accounts) if n.children else [n.id]
        assert sorted(n.accounts) == acc
    j = h.to_json()
    assert all(isinstance(n["col"], int) for n in j["nodes"] if n["level"] == 0)
    assert [n["id"] for n in j["nodes"] if n["level"] == 0 and not n["expandable"]] == ["ROW", "CEN", "STA", "DISC"]


@pytest.mark.parametrize("preset", ["simple", "full"])
def test_presets_cover_every_account_once(preset: str) -> None:
    h = load_hierarchy()
    m = h.preset_map(preset)
    assert sorted(m) == sorted(h.codes)
    cols = h.presets[preset]["columns"]
    flat = [x for c in cols for x in c]
    assert set(flat) == set(visible_nodes(h, preset))
    assert len(visible_nodes(h, preset)) == {"simple": 11, "full": 13}[preset]


def test_ts_nodes_cover_every_account_once() -> None:
    h = load_hierarchy()
    j = h.to_json()
    accts = [a for t in j["ts_nodes"] for a in t["accounts"]]
    assert sorted(accts) == sorted(h.codes) and len(accts) == 128
    assert [t["id"] for t in j["ts_nodes"]] == ["PRODUCERS", "ROW", "FACT", "HH", "NFC", "FC", "GOV", "SI", "DISC"]


def _level0(preset: str) -> tuple[dict, dict, dict]:
    h = load_hierarchy()
    m = h.preset_map(preset)
    sam = pl.read_parquet(SAM / "sam_balanced.parquet").with_columns(pl.col("value").round(2))
    pos: dict = defaultdict(float)
    neg: dict = defaultdict(float)
    internal: dict = defaultdict(float)
    for r, c, v in sam.filter(pl.col("value") != 0).iter_rows():
        p, q = m[c], m[r]
        if p == q:
            internal[p] += v
        elif v > 0:
            pos[(p, q)] += v
        else:
            neg[(p, q)] += v
    return pos, neg, internal


def test_prototype_full() -> None:
    pos, neg, internal = _level0("full")
    assert len(set(pos) | set(neg)) + len(internal) == 66
    assert len(internal) == 4
    assert len(pos) + len(neg) == 70 and len(neg) == 9
    inflow: dict = defaultdict(float)
    outflow: dict = defaultdict(float)
    for (p, q), v in pos.items():
        outflow[p] += v
        inflow[q] += v
    for (p, q), v in neg.items():
        outflow[q] -= v
        inflow[p] -= v
    want = {
        "PRDS": 677.82, "PROD": 578.51, "FACT": 265.25, "SI": 249.97, "HH": 245.74, "FINM": 145.39,
        "ROW": 80.15, "NFC": 64.27, "TAX": 60.70, "CEN": 43.80, "FC": 41.78, "STA": 38.79, "DISC": 5.71,
    }  # fmt: skip
    for k, v in want.items():
        assert round(inflow[k] / 1e5, 2) == pytest.approx(v, abs=0.01), k
        assert abs(inflow[k] - outflow[k]) < 1.0, k  # cells rounded to 2 dp
    assert round(internal["PRDS"] / 1e5, 2) == 79.20


def test_prototype_simple() -> None:
    pos, neg, internal = _level0("simple")
    assert len(pos) + len(neg) == 61
    assert round(internal["PRODUCERS"] / 1e5, 2) == 966.43
    inflow: dict = defaultdict(float)
    for (_, q), v in pos.items():
        inflow[q] += v
    for (p, _), v in neg.items():
        inflow[p] -= v
    assert round(inflow["PRODUCERS"] / 1e5, 2) == 369.09


def test_exported_hierarchy_equals_yaml(ex) -> None:
    assert ex.get("hierarchy.json") == load_hierarchy().to_json()
