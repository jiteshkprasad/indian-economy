"""Provenance resolution and the link policy (docs/phase3/PLAN.md s.3.5, proposed D3-7).

For every provenance id the export uses, walk `inputs` transitively (cycle-safe) through the SAM, time-series
and clean provenance records. Leaves are records with a URL, and terminal clean records without one (cited by
name and table, "no public URL recorded"). Leaves are grouped by `source_id` into `cites`, in the order they are
first reached (direct-input order). RBI hosts are withheld (no URL exported) until RBI grants permission.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from pipeline.export.inputs import ExportError, ExportInputs

DERIVED_PREFIXES = ("sam_", "timeseries", "fixture_sam", "fixture_ts")


def _inputs(rec: dict[str, Any]) -> list[str]:
    return [x.strip() for x in str(rec.get("inputs") or "").split(",") if x.strip()]


def is_derived_record(rec: dict[str, Any]) -> bool:
    """A SAM or time-series record (built by Phase 2 from other records), as opposed to a clean record."""
    unit = str(rec.get("ingest_unit") or "")
    return unit.startswith(DERIVED_PREFIXES)


class Walker:
    def __init__(self, inp: ExportInputs) -> None:
        self.inp = inp
        self.prov = inp.prov
        self._leaves: dict[str, list[str]] = {}
        policy = inp.config["link_policy"]
        self.default_mode = str(policy.get("default") or "")
        if self.default_mode not in ("deep", "landing", "withheld"):
            raise ExportError("link_policy.yaml: default must be deep, landing or withheld")
        self.hosts = {str(k).lower(): str(v) for k, v in (policy.get("hosts") or {}).items()}

    def record(self, pid: str) -> dict[str, Any]:
        r = self.prov.get(pid)
        if r is None:
            raise ExportError(f"provenance id {pid!r} does not resolve")
        return r

    def leaves(self, pid: str) -> list[str]:
        """Leaf prov ids reached from `pid`, in first-reached (depth-first, input) order."""
        if pid in self._leaves:
            return self._leaves[pid]
        out: list[str] = []
        seen: set[str] = set()
        stack = [pid]
        order: list[str] = []
        # iterative depth-first walk that keeps input order
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            order.append(cur)
            rec = self.record(cur)
            if rec.get("url"):
                continue  # a leaf: stop here
            kids = _inputs(rec)
            for k in reversed(kids):
                if k not in seen:
                    stack.append(k)
        for cur in order:
            rec = self.prov[cur]
            if rec.get("url") or (not _inputs(rec) and not is_derived_record(rec)):
                out.append(cur)
        self._leaves[pid] = out
        return out

    def reach(self, pid: str) -> list[str]:
        seen: list[str] = []
        stack = [pid]
        done: set[str] = set()
        while stack:
            cur = stack.pop()
            if cur in done:
                continue
            done.add(cur)
            seen.append(cur)
            rec = self.record(cur)
            if rec.get("url"):
                continue
            stack.extend(reversed(_inputs(rec)))
        return seen

    def is_assumption(self, pid: str) -> bool:
        """A derived (SAM or time-series) record whose walk reaches no leaf: a stated assumption."""
        rec = self.record(pid)
        return is_derived_record(rec) and not rec.get("url") and not self.leaves(pid)

    def depends_on_assumption(self, pid: str) -> bool:
        return any(self.is_assumption(x) for x in self.reach(pid))

    def mode(self, url: str) -> str:
        host = (urlparse(url).hostname or "").lower()
        if not host:
            raise ExportError(f"URL without a host in provenance: {url!r}")
        return self.hosts.get(host, self.default_mode)

    def source_entry(self, sid: str) -> dict[str, Any]:
        reg = self.inp.registry.get(sid)
        if reg is None:
            raise ExportError(
                f"source id {sid!r} is not in data/registry.yaml or a valid data/registry_additions/ file "
                "(sources from additions are exported with registry_status 'unverified')"
            )
        return reg


def _date(x: Any) -> str | None:
    if x is None:
        return None
    s = str(x)
    return s[:10] if s else None


def provenance_json(inp: ExportInputs, used: list[str]) -> tuple[dict[str, Any], dict[str, dict[str, bool]]]:
    """(provenance.json, {prov id: {assumption, depends_on_assumption}}) for the given used prov ids."""
    w = Walker(inp)
    records: dict[str, Any] = {}
    flags: dict[str, dict[str, bool]] = {}
    sources: set[str] = set()
    for pid in sorted(set(used)):
        rec = w.record(pid)
        leaves = w.leaves(pid)
        assumption = w.is_assumption(pid)
        if not leaves and not assumption:
            raise ExportError(f"provenance id {pid} reaches no citable source and is not an assumption")
        cites: dict[str, dict[str, Any]] = {}
        for lid in leaves:
            lr = w.prov[lid]
            sid = str(lr.get("source_id") or "")
            w.source_entry(sid)
            sources.add(sid)
            c = cites.setdefault(sid, {"source": sid, "tables": [], "urls": [], "withheld": False, "_dates": []})
            table = str(lr.get("table_id") or lr.get("locator") or lid)
            url = lr.get("url")
            out_url = None
            if url:
                m = w.mode(str(url))
                if m == "withheld":
                    c["withheld"] = True
                elif m == "landing":
                    out_url = (w.source_entry(sid).get("urls") or {}).get("landing")
                else:
                    out_url = str(url)
            if table not in c["tables"]:
                c["tables"].append(table)
                c["urls"].append(out_url)
            d = _date(lr.get("retrieved_at"))
            if d:
                c["_dates"].append(d)
        cite_list = []
        for c in cites.values():
            dates = sorted(c.pop("_dates"))
            c["retrieved"] = [dates[0], dates[-1]] if dates else [None, None]
            cite_list.append(c)
        sid = str(rec.get("source_id") or "")
        if sid:
            w.source_entry(sid)
            sources.add(sid)
        dep = w.depends_on_assumption(pid)
        flags[pid] = {"assumption": assumption, "depends_on_assumption": dep}
        records[pid] = {
            "source": sid,
            "status": rec.get("status"),
            "table": str(rec.get("table_id") or ""),
            "locator": rec.get("locator"),
            "method": " ".join(str(rec.get("method") or "").split()),
            "vintage": None if rec.get("vintage") is None else str(rec.get("vintage")),
            "base_year": rec.get("base_year"),
            "price_basis": str(rec.get("price_basis") or ""),
            "unit": str(rec.get("unit_as_published") or ""),
            "conversion": rec.get("conversion"),
            "assumption": assumption,
            "depends_on_assumption": dep,
            "cites": cite_list,
        }
        if records[pid]["status"] not in ("official", "derived", "estimated"):
            raise ExportError(f"provenance {pid}: status {rec.get('status')!r} is not official/derived/estimated")
    src_out: dict[str, Any] = {}
    for sid in sorted(sources):
        reg = w.source_entry(sid)
        urls = reg.get("urls") or {}
        landing = urls.get("landing")
        lic = reg.get("license") or {}
        modes = set()
        for u in [landing, *(urls.get("data") or [])]:
            if u:
                modes.add(w.mode(str(u)))
        link_mode = "withheld" if "withheld" in modes else ("landing" if modes == {"landing"} else "deep")
        src_out[sid] = {
            "name": str(reg.get("name") or sid),
            "publisher": str(reg.get("publisher") or ""),
            "landing": None if link_mode == "withheld" or not landing else str(landing),
            "link_mode": link_mode,
            "licence": str(lic.get("name") or ""),
            "attribution": " ".join(str(lic.get("attribution") or "").split()),
            "registry_status": str((reg.get("verification") or {}).get("status") or "unknown"),
        }
    return {"records": records, "sources": src_out}, flags


def withheld_url_count(inp: ExportInputs) -> int:
    """Provenance records whose URL is on a withheld host (summary.methodology `withheld_urls`)."""
    w = Walker(inp)
    return sum(1 for r in inp.prov.values() if r.get("url") and w.mode(str(r["url"])) == "withheld")


def assumption_dependents(inp: ExportInputs, direct: bool = False) -> int:
    """SAM provenance records that depend on a stated assumption, not counting the assumption records:
    transitively (any record whose walk reaches one), or with direct=True only those taking one as an input."""
    w = Walker(inp)
    n = 0
    for pid, rec in inp.prov.items():
        if not str(rec.get("ingest_unit") or "").startswith(("sam_", "fixture_sam")) or w.is_assumption(pid):
            continue
        if direct:
            n += int(any(k in inp.prov and w.is_assumption(k) for k in _inputs(rec)))
        else:
            n += int(w.depends_on_assumption(pid))
    return n
