"""ts/series.json against top_flows.parquet (PLAN s.3.7.1, s.2.1 item 7, s.5.1 item 6)."""

from __future__ import annotations

import json

import polars as pl
import pytest
from _export_helpers import TS

pytestmark = pytest.mark.export


def _main_rows() -> dict[tuple[str, str], dict]:
    ts = pl.read_parquet(TS / "top_flows.parquet").filter(pl.col("variant") == "published")
    out: dict[tuple[str, str], dict] = {}
    for base in (None, "2011-12", "2022-23"):  # later wins: 2022-23 > 2011-12 > null
        sel = ts.filter(pl.col("base_year").is_null() if base is None else pl.col("base_year") == base)
        for r in sel.iter_rows(named=True):
            out[(r["flow_id"], r["period"])] = r
    return out


def test_main_values_equal_parquet(real) -> None:
    s = real.get("ts/series.json")
    rows = _main_rows()
    assert len(s["periods"]) == 76 and s["periods"][0] == "1950-51" and s["periods"][-1] == "2025-26"
    assert len(s["flows"]) == 69
    n = 0
    for f in s["flows"]:
        for i, p in enumerate(s["periods"]):
            r = rows.get((f["id"], p))
            v = f["main"]["v"][i]
            if r is None:
                assert v is None, (f["id"], p)  # no interpolation, no carry-forward
                continue
            assert v == pytest.approx(r["value"], abs=0.0051), (f["id"], p)
            assert f["main"]["prov"][i] == r["prov_id"] and f["main"]["status"][i] in ("official", "derived")
            assert f["main"]["base"][i] == r["base_year"]
            n += 1
    assert n == len(rows)


def test_linked_only_for_linked_flows(real) -> None:
    s = real.get("ts/series.json")
    d = pl.read_parquet(TS / "top_flows_definitions.parquet")
    linked = set(d.filter(pl.col("link_policy") == "linked")["flow_id"].to_list())
    assert len(linked) == 10
    for f in s["flows"]:
        assert (f["linked"] is not None) == (f["id"] in linked), f["id"]
        assert (f["link_policy"] == "linked") == (f["id"] in linked)


def test_every_flag_and_segment_boundary_is_a_marker(real) -> None:
    s = real.get("ts/series.json")
    by = {f["id"]: {(m["period"], m["kind"]) for m in f["markers"]} for f in s["flows"]}
    ts = pl.read_parquet(TS / "top_flows.parquet")
    for r in ts.filter(pl.col("flags").is_in(["base_change", "concept_break", "segment_join"])).iter_rows(named=True):
        assert (r["period"], r["flags"]) in by[r["flow_id"]], (r["flow_id"], r["period"], r["flags"])
    rows = _main_rows()
    for f in s["flows"]:
        prev = None
        for p in s["periods"]:
            r = rows.get((f["id"], p))
            if r is None:
                continue
            if prev is not None and r["segment"] != prev["segment"]:
                assert (p, "segment") in by[f["id"]], (f["id"], p)
            prev = r
        for m in f["markers"]:
            assert m["note"].strip(), (f["id"], m)
    d = pl.read_parquet(TS / "top_flows_definitions.parquet")
    for fid, b in d.select("flow_id", "breaks").iter_rows():
        for x in json.loads(b) if b else []:
            assert (x["period"], "concept_break") in by[fid] or (x["period"], "break") in by[fid]


def test_check_block(real) -> None:
    s = real.get("ts/series.json")
    c = {r["flow_id"]: r for r in pl.read_parquet(TS / "top_flows_sam_check.parquet").iter_rows(named=True)}
    verdicts = [f["check"]["verdict"] for f in s["flows"]]
    assert verdicts.count("pass") == 57 and verdicts.count("explained") == 11 and verdicts.count("no_check") == 1
    for f in s["flows"]:
        assert f["check"]["verdict"] == c[f["id"]]["verdict"]
        if f["check"]["verdict"] == "explained":
            assert f["check"]["explanation"]
