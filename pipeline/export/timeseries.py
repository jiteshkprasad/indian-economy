"""Time series in the export: ts/series.json, ts/view.json, ts/cover.json (docs/phase3/PLAN.md s.3.7)."""

from __future__ import annotations

import json
from typing import Any

import polars as pl

from pipeline.core.io import canonical_float
from pipeline.export.inputs import ExportError, ExportInputs
from pipeline.export.sam_export import SamView, r2

SHARE = 6
NEW_BASE = "2022-23"
OLD_BASE = "2011-12"
MAIN = "published"
LINKED = "linked_2022_23"
ALT_VARIANTS = ("fc16_definition", "proxy_total_portfolio")
NEVER_RIBBONS = ("F11", "M09", "M11")  # nets of mixed-sign content by definition (s.3.7.3 rule 4)
MIN_PERIODS = 10
MARKER_FLAGS = ("base_change", "concept_break", "segment_join")


def fy_periods(first: str, last: str) -> list[str]:
    a, b = int(first[:4]), int(last[:4])
    return [f"{y}-{(y + 1) % 100:02d}" for y in range(a, b + 1)]


def _stage(x: Any) -> str | None:
    if x is None or str(x) in ("", "n.a."):
        return None
    return str(x)


class TsData:
    """Main / linked / alt rows per flow and period, selected by the s.3.7.1 rule with no silent choice."""

    def __init__(self, inp: ExportInputs) -> None:
        self.inp = inp
        ts = inp.ts
        if ts.filter(pl.col("value").is_null() | ~pl.col("value").is_finite()).height:
            raise ExportError("top_flows.parquet has a null or non-finite value")
        periods = sorted(set(ts["period"].to_list()), key=lambda p: int(p[:4]))
        self.periods = fy_periods(periods[0], periods[-1])
        if set(periods) - set(self.periods):
            raise ExportError("top_flows.parquet has periods that are not financial years")
        self.defs = {r["flow_id"]: r for r in inp.ts_defs.iter_rows(named=True)}
        self.flow_ids = sorted(self.defs)
        self.rows: dict[tuple[str, str, str, str | None], dict[str, Any]] = {}
        for r in ts.iter_rows(named=True):
            k = (r["flow_id"], r["variant"], r["period"], r["base_year"])
            if k in self.rows:
                raise ExportError(f"top_flows.parquet: two rows for {k}")
            self.rows[k] = r
        self.main: dict[str, dict[str, dict[str, Any]]] = {f: {} for f in self.flow_ids}
        self.linked: dict[str, dict[str, dict[str, Any]]] = {f: {} for f in self.flow_ids}
        self.alts: dict[str, dict[str, dict[str, dict[str, Any]]]] = {f: {} for f in self.flow_ids}
        by: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for (fid, var, per, _), r in self.rows.items():
            if fid not in self.defs:
                raise ExportError(f"top_flows.parquet: flow {fid} has no definition")
            by.setdefault((fid, var, per), []).append(r)
        for (fid, var, per), rs in sorted(by.items()):
            if var == MAIN:
                self.main[fid][per] = self._pick(fid, per, rs)
            elif var == LINKED:
                if len(rs) != 1:
                    raise ExportError(f"{fid} {per}: {len(rs)} linked rows")
                self.linked[fid][per] = rs[0]
            elif var in ALT_VARIANTS:
                if len(rs) != 1:
                    raise ExportError(f"{fid} {per}: {len(rs)} rows of variant {var}")
                self.alts[fid].setdefault(var, {})[per] = rs[0]
            else:
                raise ExportError(f"top_flows.parquet: unknown variant {var!r}")

    @staticmethod
    def _pick(fid: str, per: str, rs: list[dict[str, Any]]) -> dict[str, Any]:
        for base in (NEW_BASE, OLD_BASE, None):
            cand = [r for r in rs if r["base_year"] == base]
            if len(cand) > 1:
                raise ExportError(f"{fid} {per}: {len(cand)} candidate main rows at base {base}")
            if cand:
                return cand[0]
        raise ExportError(f"{fid} {per}: published rows with an unknown base year {[r['base_year'] for r in rs]}")

    def linked_series(self, fid: str) -> dict[str, dict[str, Any]] | None:
        if self.defs[fid]["link_policy"] != "linked":
            if self.linked[fid]:
                raise ExportError(f"{fid}: linked rows exist but link_policy is {self.defs[fid]['link_policy']}")
            return None
        out = {p: r for p, r in self.linked[fid].items() if int(p[:4]) < int(NEW_BASE[:4])}
        for p, r in self.main[fid].items():
            if int(p[:4]) >= int(NEW_BASE[:4]):
                if r["base_year"] != NEW_BASE and r["base_year"] is not None:
                    raise ExportError(f"{fid} {p}: linked series needs a new-base main row")
                out[p] = r
        return out

    def gdp(self, period: str, base: str | None, linked: bool = False) -> float:
        if linked and int(period[:4]) < int(NEW_BASE[:4]):
            r = self.linked["M01"].get(period)
        else:
            b = base if base is not None else (NEW_BASE if int(period[:4]) >= int(NEW_BASE[:4]) else OLD_BASE)
            r = self.rows.get(("M01", MAIN, period, b))
        if r is None or not r["value"]:
            raise ExportError(f"no GDP (M01) denominator for {period} base {base} (linked={linked})")
        return float(r["value"])

    def share(self, fid: str, r: dict[str, Any], linked: bool = False) -> float:
        sign = int(self.defs[fid]["display_sign"])
        return canonical_float(float(r["value"]) * sign / self.gdp(r["period"], r["base_year"], linked), SHARE)

    def status_2023(self) -> dict[str, str]:
        return {f: str(m["2023-24"]["status"]) for f, m in self.main.items() if "2023-24" in m}


def _arrays(td: TsData, fid: str, rows: dict[str, dict[str, Any]], linked: bool = False) -> dict[str, Any]:
    out: dict[str, list[Any]] = {k: [] for k in ("v", "share", "base", "status", "stage", "flags", "segment", "prov")}
    for p in td.periods:
        r = rows.get(p)
        if r is None:
            for k in out:
                out[k].append(None)
            continue
        if not r.get("prov_id"):
            raise ExportError(f"{fid} {p}: a value without a provenance id")
        if r["status"] not in ("official", "derived"):
            raise ExportError(f"{fid} {p}: status {r['status']!r}")
        out["v"].append(r2(r["value"]))
        out["share"].append(td.share(fid, r, linked))
        out["base"].append(r["base_year"])
        out["status"].append(r["status"])
        out["stage"].append(_stage(r["estimate_stage"]))
        out["flags"].append(r["flags"])
        out["segment"].append(r["segment"])
        out["prov"].append(r["prov_id"])
    return out


def _segments(d: dict[str, Any]) -> list[dict[str, Any]]:
    return json.loads(d["segments"]) if d.get("segments") else []


def _breaks(d: dict[str, Any]) -> list[dict[str, Any]]:
    return json.loads(d["breaks"]) if d.get("breaks") else []


def markers(td: TsData, fid: str) -> list[dict[str, Any]]:
    d = td.defs[fid]
    segs = {s["code"]: s for s in _segments(d)}
    brk = {b["period"]: b["note"] for b in _breaks(d)}
    out: dict[tuple[str, str], str] = {}

    def seg_name(code: str | None) -> str:
        if code is None:
            return "unknown source"
        s = segs.get(code.removeprefix("LINK:"))
        return f"{s['dataset']} ({code})" if s else str(code)

    # every flag row of the flow (any variant)
    for (f, var, per, _), r in sorted(td.rows.items(), key=lambda kv: (kv[0][2], kv[0][1], str(kv[0][3]))):
        if f != fid or r["flags"] not in MARKER_FLAGS:
            continue
        kind = r["flags"]
        seg = segs.get(str(r["segment"]).removeprefix("LINK:")) if r["segment"] else None
        if kind == "concept_break":
            note = brk.get(per) or (seg or {}).get("note") or "Concept break: the definition changes here."
        elif kind == "base_change":
            note = (seg or {}).get("note") or (
                f"Base change: from {per} the series is on the {r['base_year']} base; levels before and after are "
                "not directly comparable."
            )
        else:
            note = r["note"] or f"Sources are joined here: the series continues as {seg_name(r['segment'])}."
            if var == LINKED:
                note = f"Linked (derived) series: {note}"
        key = (per, kind)
        if key not in out:
            out[key] = " ".join(str(note).split())
    # segment boundaries of the main series
    prev = None
    for p in td.periods:
        r = td.main[fid].get(p)
        if r is None:
            continue
        if prev is not None and r["segment"] != prev["segment"]:
            note = f"Source changes from {seg_name(prev['segment'])} to {seg_name(r['segment'])}."
            if r["base_year"] != prev["base_year"] and r["base_year"] == NEW_BASE:
                note += (
                    f" New GDP base ({NEW_BASE}). Earlier years are on the {prev['base_year'] or 'earlier'} base; "
                    "levels are not directly comparable, shares are closer."
                )
            s = segs.get(str(r["segment"]))
            if s and s.get("note"):
                note += " " + s["note"]
            out.setdefault((p, "segment"), " ".join(note.split()))
        prev = r
    for per, note in brk.items():
        if (per, "concept_break") not in out:
            out[(per, "break")] = " ".join(str(note).split())
    return [
        {"period": p, "kind": k, "note": n}
        for (p, k), n in sorted(out.items(), key=lambda kv: (int(kv[0][0][:4]), kv[0][1]))
    ]


def series_json(td: TsData) -> dict[str, Any]:
    check = {r["flow_id"]: r for r in td.inp.ts_check.iter_rows(named=True)}
    flows = []
    for fid in td.flow_ids:
        d = td.defs[fid]
        c = check.get(fid)
        if c is None:
            raise ExportError(f"{fid}: no row in top_flows_sam_check.parquet")
        if c["verdict"] not in ("pass", "explained", "no_check"):
            raise ExportError(f"{fid}: SAM check verdict {c['verdict']!r} cannot be published")
        if d["display_sign"] not in (1, -1):
            raise ExportError(f"{fid}: display_sign {d['display_sign']}")
        linked_rows = td.linked_series(fid)
        alts = [{"variant": var, "arrays": _arrays(td, fid, rows)} for var, rows in sorted(td.alts[fid].items())]
        flows.append(
            {
                "id": fid,
                "tier": d["tier"],
                "group": d["group"],
                "display_sign": int(d["display_sign"]),
                "name_tech": d["name"],
                "check": {
                    "class": c["check_class"],
                    "verdict": c["verdict"],
                    "ts_value": None if c["ts_value"] is None else r2(c["ts_value"]),
                    "sam_value": None if c["sam_balanced"] is None else r2(c["sam_balanced"]),
                    "rel_diff": None if c["rel_diff"] is None else canonical_float(c["rel_diff"], SHARE),
                    "explanation": None if not c["explanation"] else " ".join(c["explanation"].split()),
                },
                "link_policy": d["link_policy"],
                "link_reason": d["link_reason"],
                "markers": markers(td, fid),
                "main": _arrays(td, fid, td.main[fid]),
                "linked": None if linked_rows is None else _arrays(td, fid, linked_rows, linked=True),
                "alts": alts,
            }
        )
    gm = td.main["M01"]
    gl = td.linked_series("M01") or {}
    return {
        "periods": td.periods,
        "gdp": {
            "main": [None if p not in gm else r2(gm[p]["value"]) for p in td.periods],
            "main_base": [None if p not in gm else gm[p]["base_year"] for p in td.periods],
            "linked": [None if p not in gl else r2(gl[p]["value"]) for p in td.periods],
            "prov": [None if p not in gm else gm[p]["prov_id"] for p in td.periods],
        },
        "flows": flows,
    }


def flow_ts_pairs(view: SamView, fe: list[tuple[int, float]]) -> set[tuple[str, str]]:
    tsm = view.inp.hierarchy.ts_map()
    return {(tsm[view.col[i]], tsm[view.row[i]]) for i, _ in fe if abs(float(view.v[i])) > 0}


def view_json(
    view: SamView, td: TsData, flow_entries: dict[str, list[tuple[int, float]]]
) -> tuple[dict[str, Any], list[str]]:
    """ts/view.json, checked against the five ribbon rules of s.3.7.3. Returns (json, warnings)."""
    cfg = view.inp.config["ts_view"]
    ts_ids = [t["id"] for t in view.inp.hierarchy.ts_nodes]
    check = {r["flow_id"]: r["verdict"] for r in view.inp.ts_check.iter_rows(named=True)}
    ribbons = []
    used: dict[int, str] = {}
    for rb in cfg.get("ribbons") or []:
        fid = str(rb["flow"])
        if fid not in td.defs:
            raise ExportError(f"ts_view.yaml: ribbon {fid} is not a flow")
        frm, to = str(rb["from"]), str(rb["to"])
        if frm not in ts_ids or to not in ts_ids or frm == to:
            raise ExportError(f"ts_view.yaml: ribbon {fid} {frm}->{to} must join two different ts nodes")
        if fid in NEVER_RIBBONS:
            raise ExportError(f"ts_view.yaml: {fid} is a net of mixed-sign content and is never a ribbon")
        pairs = flow_ts_pairs(view, flow_entries.get(fid, []))
        if pairs != {(frm, to)}:
            raise ExportError(f"ts_view.yaml: ribbon {fid} declared {frm}->{to}, its SAM terms map to {sorted(pairs)}")
        for i, _ in flow_entries[fid]:
            if i in used:
                raise ExportError(f"ts_view.yaml: ribbons {used[i]} and {fid} share SAM entry {i}")
            used[i] = fid
        n = len(td.main[fid])
        if n < MIN_PERIODS:
            raise ExportError(f"ts_view.yaml: ribbon {fid} has {n} periods (< {MIN_PERIODS})")
        sign = int(td.defs[fid]["display_sign"])
        neg = [p for p, r in td.main[fid].items() if float(r["value"]) * sign < 0]
        rev = bool(rb.get("reversible", False))
        key = rb.get("reversed_text_key")
        if neg and not (rev and key):
            raise ExportError(
                f"ts_view.yaml: ribbon {fid} is negative in {len(neg)} years ({', '.join(neg[:5])}) and is not "
                "marked reversible with a reversed_text_key"
            )
        if check.get(fid) not in ("pass", "explained"):
            raise ExportError(f"ts_view.yaml: ribbon {fid} has 2023-24 SAM check {check.get(fid)!r}")
        ribbons.append(
            {"flow": fid, "from": frm, "to": to, "reversible": rev, "reversed_text_key": key if rev else None}
        )
    internal: dict[str, list[str]] = {t: [] for t in ts_ids}
    for node, flows in (cfg.get("internal") or {}).items():
        if node not in internal:
            raise ExportError(f"ts_view.yaml: internal node {node!r} is not a ts node")
        for fid in flows:
            pairs = flow_ts_pairs(view, flow_entries.get(fid, []))
            if pairs and (any(a != b for a, b in pairs) or (node, node) not in pairs):
                raise ExportError(f"ts_view.yaml: internal flow {fid} of {node} maps to {sorted(pairs)}")
            internal[node].append(str(fid))
    coverage = [sum(1 for f in td.flow_ids if p in td.main[f]) for p in td.periods]
    slot: dict[str, float] = dict.fromkeys(ts_ids, 0.0)
    for p in td.periods:
        inflow = dict.fromkeys(ts_ids, 0.0)
        outflow = dict.fromkeys(ts_ids, 0.0)
        for rb in ribbons:
            r = td.main[rb["flow"]].get(p)
            if r is None:
                continue
            s = td.share(rb["flow"], r)
            a, b = (rb["from"], rb["to"]) if s >= 0 else (rb["to"], rb["from"])
            outflow[a] += abs(s)
            inflow[b] += abs(s)
        for t in ts_ids:
            slot[t] = max(slot[t], inflow[t], outflow[t])
    warnings = []
    listed = {rb["flow"] for rb in ribbons} | {f for fl in internal.values() for f in fl}
    for rj in cfg.get("rejected") or []:
        listed.add(str(rj["flow"]))
    for f in td.flow_ids:
        if f not in listed:
            warnings.append(f"ts_view.yaml: flow {f} is neither a ribbon, internal, nor listed as rejected")
    return (
        {
            "coverage": coverage,
            "ribbons": ribbons,
            "internal": internal,
            "slot_share": {t: canonical_float(x, SHARE) for t, x in slot.items()},
        },
        warnings,
    )


def cover_json(view: SamView, flow_entries: dict[str, list[tuple[int, float]]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for fid in sorted(flow_entries):
        cells: dict[tuple[str, str], float] = {}
        for i, coef in flow_entries[fid]:
            k = (view.row[i], view.col[i])
            cells[k] = cells.get(k, 0.0) + coef * float(view.v[i])
        rows = [
            [view.idx[r], view.idx[c], r2(x)]
            for (r, c), x in sorted(cells.items(), key=lambda kv: (view.idx[kv[0][0]], view.idx[kv[0][1]]))
            if r2(x) != 0
        ]
        out[fid] = {"cells": rows, "abs_total": r2(sum(abs(x[2]) for x in rows))}
    return out
