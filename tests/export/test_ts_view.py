"""The top-flows board: the five ribbon rules of PLAN s.3.7.3, checked mechanically."""

from __future__ import annotations

import polars as pl
import pytest
import yaml
from _export_helpers import REPO

pytestmark = pytest.mark.export


def test_ribbon_rules(real) -> None:
    v = real.get("ts/view.json")
    s = real.get("ts/series.json")
    cover = real.get("ts/cover.json")
    h = real.get("hierarchy.json")
    codes = [a["code"] for a in h["accounts"]]
    ts_of = {a: t["id"] for t in h["ts_nodes"] for a in t["accounts"]}
    flows = {f["id"]: f for f in s["flows"]}
    seen_cells: dict = {}
    for rb in v["ribbons"]:
        fid = rb["flow"]
        assert fid not in ("F11", "M09", "M11")
        cells = cover[fid]["cells"]
        assert cells, fid
        pairs = {(ts_of[codes[c]], ts_of[codes[r]]) for r, c, _ in cells}
        assert pairs == {(rb["from"], rb["to"])}, fid  # rule 1
        for r, c, _ in cells:  # rule 2 (at cell level: stricter than entries)
            assert (r, c) not in seen_cells or seen_cells[(r, c)] == fid, (fid, seen_cells.get((r, c)))
            seen_cells[(r, c)] = fid
        f = flows[fid]
        assert sum(x is not None for x in f["main"]["v"]) >= 10  # rule 3
        neg = any(x is not None and x * f["display_sign"] < 0 for x in f["main"]["v"])
        if neg:  # rule 4
            assert rb["reversible"] and rb["reversed_text_key"], fid
        assert f["check"]["verdict"] in ("pass", "explained")  # rule 5


def test_every_flow_is_placed_once() -> None:
    cfg = yaml.safe_load((REPO / "pipeline/export/ts_view.yaml").read_text())
    ids = [r["flow"] for r in cfg["ribbons"]] + [f for fl in cfg["internal"].values() for f in fl]
    ids += [r["flow"] for r in cfg["rejected"]]
    d = pl.read_parquet(REPO / "data/timeseries/top_flows_definitions.parquet")
    assert sorted(ids) == sorted(d["flow_id"].to_list())


def test_coverage_and_slots(real) -> None:
    v = real.get("ts/view.json")
    s = real.get("ts/series.json")
    assert v["coverage"] == [sum(f["main"]["v"][i] is not None for f in s["flows"]) for i in range(len(s["periods"]))]
    i = s["periods"].index("1950-51")
    assert v["coverage"][i] == 12
    assert v["coverage"][s["periods"].index("2022-23")] == 69
    ends = {n for rb in v["ribbons"] for n in (rb["from"], rb["to"])}
    assert all(v["slot_share"][n] > 0 for n in ends)
    assert all(x >= 0 for x in v["slot_share"].values())
