"""Provenance and the link policy (PLAN s.3.5, s.5.1 item 3), with an independent walk of `inputs`."""

from __future__ import annotations

import glob
from urllib.parse import urlparse

import polars as pl
import pytest
import yaml
from _export_helpers import REPO, SAM, TS

from pipeline.core.registry import load_registry

pytestmark = pytest.mark.export


def _all_prov() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in [
        SAM / "_provenance.parquet",
        TS / "_provenance.parquet",
        *sorted(glob.glob(str(REPO / "data/clean/*/_provenance.parquet"))),
    ]:
        for r in pl.read_parquet(f).iter_rows(named=True):
            out[r["prov_id"]] = r
    return out


def _ins(r: dict) -> list[str]:
    return [x for x in (r.get("inputs") or "").split(",") if x]


def _walk(pid: str, prov: dict[str, dict]) -> list[str]:
    """Recursive depth-first walk in input order (first visit wins), stopping at records with a URL."""
    seen: list[str] = []

    def go(p: str) -> None:
        if p in seen:
            return
        seen.append(p)
        if prov[p].get("url"):
            return
        for k in _ins(prov[p]):
            go(k)

    go(pid)
    return seen


def _referenced(ex) -> set[str]:
    out = set()
    for f in ex.files():
        if f.startswith("sam/entries/"):
            out |= {e["prov"] for e in ex.get(f)["entries"]}
        if f.startswith("stories/"):
            for x in ex.get(f)["figures"].values():
                out |= set(x["prov"])
    out |= {c["prov"] for c in ex.get("sam/constraints.json").values()}
    for fl in ex.get("ts/series.json")["flows"]:
        out |= {p for p in fl["main"]["prov"] if p}
    s = ex.get("summary.json")
    out.add(s["gdp"]["prov"])
    for m in s["methodology"].values():
        out |= set(m["prov"])
    return out


def test_every_referenced_prov_is_exported(ex) -> None:
    recs = ex.get("provenance.json")["records"]
    missing = _referenced(ex) - set(recs)
    assert not missing, sorted(missing)[:10]
    for pid, r in recs.items():
        assert r["cites"] or (r["assumption"] and r["method"]), pid


def test_cites_follow_independent_walk(real) -> None:
    prov = _all_prov()
    recs = real.get("provenance.json")["records"]
    for pid, r in sorted(recs.items())[:400]:
        order = _walk(pid, prov)
        leaves = [
            p
            for p in order
            if prov[p].get("url")
            or (not _ins(prov[p]) and not str(prov[p]["ingest_unit"]).startswith(("sam_", "timeseries")))
        ]
        want_sources = list(dict.fromkeys(prov[p]["source_id"] for p in leaves))
        assert [c["source"] for c in r["cites"]] == want_sources, pid
        reaches_assumption = any(
            str(prov[p]["ingest_unit"]).startswith(("sam_", "timeseries"))
            and not prov[p].get("url")
            and not _ins(prov[p])
            for p in order
        )
        assert r["depends_on_assumption"] == reaches_assumption, pid


def test_link_policy_and_dates(ex) -> None:
    pol = yaml.safe_load((REPO / "pipeline/export/link_policy.yaml").read_text())
    withheld = {h for h, m in pol["hosts"].items() if m == "withheld"}
    p = ex.get("provenance.json")
    for pid, r in p["records"].items():
        for c in r["cites"]:
            assert len(c["urls"]) == len(c["tables"])
            for u in c["urls"]:
                if u is None:
                    continue
                host = urlparse(u).hostname
                assert host and host not in withheld, (pid, u)
                assert c["retrieved"][0] is not None, (pid, c["source"])
    for s in p["sources"].values():
        if s["link_mode"] == "withheld":
            assert s["landing"] is None
            assert not any(h in (s["landing"] or "") for h in withheld)


def test_sources_in_registry_with_attribution(real) -> None:
    reg = load_registry()
    p = real.get("provenance.json")
    assert set(p["sources"]) <= set(reg)
    for sid, s in p["sources"].items():
        lic = reg[sid].get("license") or {}
        assert s["attribution"] == " ".join(str(lic.get("attribution") or "").split())
    rbi = [s for s in p["sources"] if s.startswith("rbi_")]
    assert rbi and all(p["sources"][s]["link_mode"] == "withheld" for s in rbi)
