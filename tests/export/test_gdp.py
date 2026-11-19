"""GDP and shares (PLAN s.3.3, s.3.7.2, s.5.1 item 2)."""

from __future__ import annotations

import polars as pl
import pytest
from _export_helpers import REPO, SAM, TS

pytestmark = pytest.mark.export


def test_gdp_value(real) -> None:
    g = real.get("summary.json")["gdp"]
    ts = pl.read_parquet(TS / "top_flows.parquet")
    row = ts.filter(
        (pl.col("flow_id") == "M01") & (pl.col("period") == "2023-24") & (pl.col("variant") == "published")
        & (pl.col("base_year") == "2022-23")
    )  # fmt: skip
    assert row.height == 1
    assert g["value"] == pytest.approx(row["value"][0], abs=0.005)
    assert g["prov"] == row["prov_id"][0] and g["label"] == "official"
    nas = pl.read_parquet(REPO / "data/clean/mospi_nas_2026/mospi_nas_2026_s1_1.parquet")
    v = nas.filter((pl.col("series_id") == "s1_1.gdp.current") & (pl.col("period") == "2023-24"))["value"]
    assert v.len() == 1 and g["value"] == pytest.approx(v[0], abs=1.0)
    sam = pl.read_parquet(SAM / "sam_balanced.parquet")
    act = sam.filter(pl.col("col").str.starts_with("A_"))
    va = act.filter(pl.col("row").str.starts_with("F_") | (pl.col("row") == "T_PROD"))["value"].sum()
    pt = sam.filter(pl.col("col").str.starts_with("C_") & pl.col("row").str.starts_with("T_"))["value"].sum()
    assert va + pt == pytest.approx(g["value"], abs=1.0)


def test_every_share_recomputed(ex) -> None:
    s = ex.get("ts/series.json")
    periods = s["periods"]
    ts = pl.read_parquet(TS / "top_flows.parquet") if ex.index["fixture"] is False else None
    m01 = {}
    src = ex.get("ts/series.json")
    gdp_new = {
        p: v for p, v, b in zip(periods, src["gdp"]["main"], src["gdp"]["main_base"], strict=True) if b == "2022-23"
    }
    if ts is not None:
        for r in ts.filter((pl.col("flow_id") == "M01") & (pl.col("variant") == "published")).iter_rows(named=True):
            m01[(r["period"], r["base_year"])] = r["value"]
    n = 0
    for f in s["flows"]:
        a = f["main"]
        for i, p in enumerate(periods):
            if a["v"][i] is None:
                assert a["share"][i] is None
                continue
            base = a["base"][i] or ("2022-23" if int(p[:4]) >= 2022 else "2011-12")
            den = m01.get((p, base)) if ts is not None else (gdp_new.get(p) if base == "2022-23" else None)
            if den is None:
                continue
            assert a["share"][i] == pytest.approx(a["v"][i] * f["display_sign"] / den, abs=1e-6), (f["id"], p)
            n += 1
    assert n > 100


def test_headline_parts_sum_to_total(ex) -> None:
    h = ex.get("summary.json")["headline"]["hh_outlays"]
    assert sum(p["value"] for p in h["parts"]) == pytest.approx(h["total"], abs=0.05)
    assert sum(p["per100"] for p in h["parts"]) == pytest.approx(100, abs=1e-4)
    keys = [p["key"] for p in h["parts"]]
    assert "unallocated_residual" in keys and len(keys) == len(set(keys))
