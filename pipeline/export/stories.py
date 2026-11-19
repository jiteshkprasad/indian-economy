"""The story figure evaluator (docs/phase3/PLAN.md s.3.8; grammar in docs/phase3/requests/U5.md). Owner: U1.

Each story YAML (pipeline/export/stories/<slug>.yaml, owner U5) names figures by kind. The evaluator resolves
each figure from the balanced SAM entries, satellites, the time series and other figures, and labels it with
the s.3.4 rules: `total` (official/derived only when the figure's entry set is pinned, or every part of a
combination has a total) and `split` (least certain label carrying >= 10% of the absolute value; for a
combination, the least certain split of its parts). A `per100` share is labelled by its part alone (split,
total, composition and flags of the part); the whole's label goes into its `method` text (V1-06, the rule
summary.json's headline parts already follow). Unknown kinds or keys, unknown ids and selectors that
match nothing fail the export, naming the story and figure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import polars as pl

from pipeline.core.io import canonical_float
from pipeline.export.inputs import YEAR, ExportError
from pipeline.export.pinned import Pin, Pinner, _mask, node_universe
from pipeline.export.sam_export import SamView, composition_json, r2
from pipeline.export.status import FLAG_BITS, LABELS, least_certain, least_certain_total, split_of
from pipeline.export.timeseries import TsData

UNITS = ("inr", "pct_gdp", "per100", "pct")
COMMON = {"kind", "unit", "note_key", "check_equals"}
KIND_KEYS = {
    "sam_sum": {"terms"},
    "entries_sum": {"terms"},
    "satellite_sum": {"table", "where"},
    "satellite_share": {"table", "share_of", "within", "total"},
    "ts_value": {"flow", "period", "measure"},
    "ratio": {"num", "den"},
    "per100": {"part", "whole"},
    "difference": {"a", "b"},
    "sum": {"terms"},
    "prorata_sum": {"over", "base", "num", "den"},
}
SAM_TERM_KEYS = {"rows", "cols", "not_rows", "not_cols", "coef"}
ENTRY_TERM_KEYS = SAM_TERM_KEYS | {"refs", "not_refs", "components", "not_components"}
STATUS_LABEL = {"official": "official", "derived": "derived", "estimated": "estimated", "balanced": "balancing_set"}
SHARE_DP = 6
LABEL_WORDS = {"official": "official", "derived": "derived", "estimated": "estimated", "balancing_set": "set by balancing"}


def _label_words(f: "Fig") -> str:
    """A figure's two-part label in words, for method text: "official total, split estimated" or "estimated"."""
    if f.total is None:
        return LABEL_WORDS[f.split]
    if f.total == f.split:
        return f"{LABEL_WORDS[f.total]}"
    return f"{LABEL_WORDS[f.total]} total, split {LABEL_WORDS[f.split]}"


@dataclass
class Fig:
    value: float
    total: str | None
    split: str
    comp: dict[str, float]  # o, d, e, b (unrounded)
    flags: list[str] = field(default_factory=list)
    prov: list[str] = field(default_factory=list)
    method: str = ""


def _one_hot(label: str) -> dict[str, float]:
    key = {"official": "o", "derived": "d", "estimated": "e", "balancing_set": "b"}[label]
    return {k: (1.0 if k == key else 0.0) for k in ("o", "d", "e", "b")}


class Evaluator:
    def __init__(
        self,
        slug: str,
        spec: dict[str, Any],
        view: SamView,
        td: TsData,
        pins: list[Pin],
        gdp: float,
        gdp_prov: str,
    ) -> None:
        self.slug = slug
        self.spec = spec
        self.view = view
        self.td = td
        self.pinner = Pinner(pins)
        self.gdp = gdp
        self.gdp_prov = gdp_prov
        self.h = view.inp.hierarchy
        self.figs: dict[str, Fig] = {}
        self.stack: list[str] = []
        self.universe = node_universe(view)

    def err(self, fid: str, msg: str) -> ExportError:
        return ExportError(f"story {self.slug}, figure {fid}: {msg}")

    # ---- selectors -------------------------------------------------------------------------------
    def accounts(self, fid: str, sel: Any, dollar: str | None = None) -> set[str]:
        items = [sel] if isinstance(sel, str) else list(sel or [])
        out: set[str] = set()
        for it in items:
            it = str(it)
            if it == "$":
                if dollar is None:
                    raise self.err(fid, "'$' is only allowed inside prorata_sum")
                out.add(dollar)
            elif it == "@ALL":
                out |= set(self.view.codes)
            elif it.startswith("@"):
                g = self.view.inp.hierarchy.accounts.in_group(it[1:])
                if not g:
                    raise self.err(fid, f"unknown account group {it!r}")
                out |= set(g)
            elif it.startswith("node:"):
                try:
                    out |= set(self.h.node_accounts(it[5:]))
                except Exception as e:  # noqa: BLE001
                    raise self.err(fid, f"unknown node {it!r}") from e
            elif it in self.view.idx:
                out.add(it)
            else:
                raise self.err(fid, f"unknown account {it!r}")
        if not out:
            raise self.err(fid, f"selector {sel!r} selects no account")
        return out

    def _term_accounts(self, fid: str, t: dict[str, Any], dollar: str | None = None) -> tuple[set[str], set[str]]:
        rows = self.accounts(fid, t.get("rows"), dollar)
        cols = self.accounts(fid, t.get("cols"), dollar)
        if t.get("not_rows"):
            rows -= self.accounts(fid, t["not_rows"], dollar)
        if t.get("not_cols"):
            cols -= self.accounts(fid, t["not_cols"], dollar)
        return rows, cols

    def term_entries(self, fid: str, t: dict[str, Any], entries_kind: bool, dollar: str | None = None) -> list[int]:
        allowed = ENTRY_TERM_KEYS if entries_kind else SAM_TERM_KEYS
        bad = set(t) - allowed
        if bad:
            raise self.err(fid, f"unknown term keys {sorted(bad)}")
        if "rows" not in t or "cols" not in t:
            raise self.err(fid, "a term needs rows and cols")
        rows, cols = self._term_accounts(fid, t, dollar)
        ents = self.view.entries_in(rows, cols)
        v = self.view
        if entries_kind:
            for key, attr, neg in (
                ("refs", v.ref, False),
                ("not_refs", v.ref, True),
                ("components", v.comp, False),
                ("not_components", v.comp, True),
            ):
                if key not in t:
                    continue
                vals = [t[key]] if isinstance(t[key], str) else [str(x) for x in t[key]]
                if not neg:
                    for val in vals:
                        if not any(attr[i] == val for i in ents):
                            raise self.err(fid, f"{key[:-1]} {val!r} matches no entry in its term")
                    ents = [i for i in ents if attr[i] in vals]
                else:
                    ents = [i for i in ents if attr[i] not in vals]
        return ents

    # ---- figures from entries --------------------------------------------------------------------
    def from_terms(self, fid: str, terms: list[dict[str, Any]], entries_kind: bool, what: str) -> Fig:
        if not terms:
            raise self.err(fid, "no terms")
        per_term: list[tuple[float, list[int]]] = []
        for t in terms:
            if not isinstance(t, dict):
                raise self.err(fid, f"a term must be a mapping: {t!r}")
            coef = float(t.get("coef", 1.0))
            ents = self.term_entries(fid, t, entries_kind)
            if not ents:
                raise self.err(fid, f"term {t!r} selects nothing")
            if all(abs(float(self.view.v[i])) == 0 for i in ents):
                raise self.err(fid, f"term {t!r} selects only zero entries")
            per_term.append((coef, ents))
        value = sum(c * float(self.view.v[i]) for c, es in per_term for i in es)
        all_e = [i for _, es in per_term for i in es]
        disjoint = len(all_e) == len(set(all_e))
        abs_lab = dict.fromkeys(LABELS, 0.0)
        for c, es in per_term:
            for i in es:
                abs_lab[self.view.label[i]] += abs(c) * abs(float(self.view.v[i]))
        a = {k: r2(x) for k, x in abs_lab.items()}
        comp, split = split_of(a["official"], a["derived"], a["estimated"], a["balancing_set"])
        total = None
        if disjoint and all(c == 1.0 for c, _ in per_term):
            got = self.pinner.label(_mask(self.view, sorted(set(all_e))))
            total = None if got is None else got["total"]
        if total is None and len(per_term) > 1:
            parts = []
            for _, es in per_term:
                got = self.pinner.label(_mask(self.view, sorted(set(es))))
                parts.append(None if got is None else got["total"])
            total = least_certain_total(parts)
        w: dict[str, float] = {}
        for i in all_e:
            w[self.view.prov[i]] = w.get(self.view.prov[i], 0.0) + abs(float(self.view.v[i]))
        prov = [p for p, _ in sorted(w.items(), key=lambda kv: (-kv[1], kv[0]))]
        flags = self.view.flag_set(sorted(set(all_e)))
        n = len(set(all_e))
        method = f"{what}: {n} balanced SAM entr{'y' if n == 1 else 'ies'}" + (
            "" if all(c == 1.0 for c, _ in per_term) else " with the signs given in the spec"
        )
        return Fig(value, total, split, comp, flags, prov, method)

    def satellite_rows(self, fid: str, table: str, where: dict[str, Any]) -> pl.DataFrame:
        df = self.view.inp.satellite(table)
        if not isinstance(where, dict) or not where:
            raise self.err(fid, "where/share_of/within must be a non-empty mapping")
        for col, val in where.items():
            if col not in df.columns:
                raise self.err(fid, f"satellite {table} has no column {col!r}")
            vals = val if isinstance(val, list) else [val]
            df = df.filter(pl.col(col).is_in(vals))
        if df.height == 0:
            raise self.err(fid, f"satellite {table} where {where} matches no row")
        if "value" not in df.columns:
            raise self.err(fid, f"satellite {table} has no value column")
        return df

    def _sat_prov(self, df: pl.DataFrame) -> list[str]:
        return sorted(set(df["prov_id"].drop_nulls().to_list())) if "prov_id" in df.columns else []

    # ---- evaluation --------------------------------------------------------------------------------
    def get(self, fid: str) -> Fig:
        if fid in self.figs:
            return self.figs[fid]
        figs = self.spec.get("figures") or {}
        if fid not in figs:
            raise ExportError(f"story {self.slug}: figure {fid!r} is referenced but not defined")
        if fid in self.stack:
            raise ExportError(f"story {self.slug}: figure references form a cycle: {' -> '.join([*self.stack, fid])}")
        self.stack.append(fid)
        try:
            f = self.evaluate(fid, figs[fid])
        finally:
            self.stack.pop()
        self.figs[fid] = f
        return f

    def operand(self, fid: str, o: Any) -> Fig:
        if not isinstance(o, dict) or len(o) != 1:
            raise self.err(fid, f"an operand is {{ref: id}} or {{gdp: '{YEAR}'}}: {o!r}")
        if "ref" in o:
            return self.get(str(o["ref"]))
        if "gdp" in o:
            if str(o["gdp"]) != YEAR:
                raise self.err(fid, f"GDP is available for {YEAR} only")
            return Fig(self.gdp, "official", "official", _one_hot("official"), [], [self.gdp_prov], f"GDP {YEAR}")
        raise self.err(fid, f"unknown operand {o!r}")

    def combine(self, parts: list[Fig], value: float, method: str, comp_from: list[Fig] | None = None) -> Fig:
        split = least_certain([p.split for p in parts])
        total = least_certain_total([p.total for p in parts])
        src = comp_from or parts
        wsum = sum(abs(p.value) for p in src) or 1.0
        comp = {k: sum(abs(p.value) * p.comp[k] for p in src) / wsum for k in ("o", "d", "e", "b")}
        flags_set = {x for p in parts for x in p.flags}
        prov: list[str] = []
        for p in parts:
            prov.extend(x for x in p.prov if x not in prov)
        return Fig(value, total, split, comp, [n for n in FLAG_BITS if n in flags_set], prov, method)

    def evaluate(self, fid: str, s: dict[str, Any]) -> Fig:
        if not isinstance(s, dict):
            raise self.err(fid, "a figure spec must be a mapping")
        kind = s.get("kind")
        if kind not in KIND_KEYS:
            raise self.err(fid, f"unknown kind {kind!r}")
        if s.get("unit") not in UNITS:
            raise self.err(fid, f"unit must be one of {UNITS}")
        extra = set(s) - COMMON - KIND_KEYS[kind]
        missing = KIND_KEYS[kind] - set(s)
        if extra or missing:
            raise self.err(fid, f"keys: unknown {sorted(extra)}, missing {sorted(missing)}")
        if kind == "sam_sum":
            f = self.from_terms(fid, list(s["terms"]), False, "Sum of SAM cells")
        elif kind == "entries_sum":
            f = self.from_terms(fid, list(s["terms"]), True, "Sum of selected SAM entries")
        elif kind == "satellite_sum":
            df = self.satellite_rows(fid, s["table"], s["where"])
            labels = [STATUS_LABEL.get(str(x), None) for x in df["status"].to_list()] if "status" in df.columns else []
            if not labels or any(x is None for x in labels):
                raise self.err(fid, f"satellite {s['table']} rows need a status (official/derived/estimated)")
            ab = dict.fromkeys(LABELS, 0.0)
            for lab, val in zip(labels, df["value"].to_list(), strict=True):
                ab[lab] += abs(float(val))
            a = {k: r2(x) for k, x in ab.items()}
            comp, split = split_of(a["official"], a["derived"], a["estimated"], a["balancing_set"])
            f = Fig(
                float(df["value"].sum()), None, split, comp, [], self._sat_prov(df),
                f"Sum of {df.height} row(s) of the {s['table']} satellite",
            )  # fmt: skip
        elif kind == "satellite_share":
            num = self.satellite_rows(fid, s["table"], s["share_of"])
            den = self.satellite_rows(fid, s["table"], s["within"])
            dv = float(den["value"].sum())
            if dv == 0:
                raise self.err(fid, "satellite_share: the `within` rows sum to zero")
            tspec = s["total"]
            if (
                not isinstance(tspec, dict)
                or tspec.get("kind") not in ("sam_sum", "entries_sum")
                or set(tspec) - {"kind", "terms"}
            ):
                raise self.err(fid, "satellite_share total must be an inline sam_sum or entries_sum {kind, terms}")
            tot = self.from_terms(fid, list(tspec["terms"]), tspec["kind"] == "entries_sum", "total")
            share = float(num["value"].sum()) / dv
            prov = [*tot.prov, *[p for p in self._sat_prov(num) + self._sat_prov(den) if p not in tot.prov]]
            f = Fig(
                share * tot.value, None, "estimated", _one_hot("estimated"), tot.flags, prov,
                f"Prior split, rescaled to the balanced total: the {s['table']} satellite's share "
                f"({share:.6f}, built on the prior SAM) applied to the balanced total",
            )  # fmt: skip
        elif kind == "ts_value":
            fl = str(s["flow"])
            per = str(s["period"])
            if fl not in self.td.main:
                raise self.err(fid, f"unknown flow {fl!r}")
            r = self.td.main[fl].get(per)
            if r is None:
                raise self.err(fid, f"flow {fl} has no main value for {per}")
            st = str(r["status"])
            if s["measure"] == "value":
                val = float(r["value"])
                prov = [r["prov_id"]]
                meth = f"Time series {fl}, {per}, main series"
            elif s["measure"] == "share":
                val = self.td.share(fl, r)
                g = self.td.main["M01"].get(per)
                prov = [r["prov_id"], *([g["prov_id"]] if g else [])]
                meth = f"Time series {fl}, {per}, share of GDP on the same base"
            else:
                raise self.err(fid, "measure must be value or share")
            f = Fig(
                val,
                st if st in ("official", "derived") else None,
                STATUS_LABEL[st],
                _one_hot(STATUS_LABEL[st]),
                [],
                prov,
                meth,
            )
        elif kind == "ratio":
            n, d = self.operand(fid, s["num"]), self.operand(fid, s["den"])
            if d.value == 0:
                raise self.err(fid, "ratio: zero denominator")
            f = self.combine([n, d], n.value / d.value, "Ratio of two figures", comp_from=[n])
        elif kind == "per100":
            p, w = self.operand(fid, s["part"]), self.operand(fid, s["whole"])
            if w.value == 0:
                raise self.err(fid, "per100: zero whole")
            # labelled by its part (V1-06): the share says how its own amount was made; the whole's label is
            # stated in the method, so the badge does not inherit the least certain part of the whole
            prov = list(p.prov)
            prov.extend(x for x in w.prov if x not in prov)
            f = Fig(
                100.0 * p.value / w.value,
                p.total,
                p.split,
                dict(p.comp),
                list(p.flags),
                prov,
                f"Rupees per 100 of the whole; labelled by its part (the whole is {_label_words(w)})",
            )
        elif kind == "difference":
            a, b = self.operand(fid, s["a"]), self.operand(fid, s["b"])
            f = self.combine([a, b], a.value - b.value, "Difference of two figures")
        elif kind == "sum":
            terms = s["terms"] or []
            parts, val = [], 0.0
            for t in terms:
                if not isinstance(t, dict) or set(t) - {"ref", "coef"} or "ref" not in t:
                    raise self.err(fid, f"sum terms are {{ref, coef?}}: {t!r}")
                p = self.get(str(t["ref"]))
                parts.append(p)
                val += float(t.get("coef", 1.0)) * p.value
            if not parts:
                raise self.err(fid, "sum without terms")
            f = self.combine(parts, val, f"Sum of {len(parts)} figures")
        else:  # prorata_sum
            over = sorted(self.accounts(fid, s["over"]), key=lambda c: self.view.idx[c])
            val = 0.0
            ents_all: list[int] = []
            for a in over:

                def tsum(t: dict[str, Any], a: str = a) -> tuple[float, list[int]]:
                    if not isinstance(t, dict) or set(t) - {"rows", "cols"}:
                        raise self.err(fid, f"prorata_sum parts are {{rows, cols}}: {t!r}")
                    tt = {"rows": t.get("rows", "@ALL"), "cols": t.get("cols", "@ALL")}
                    es = self.term_entries(fid, tt, False, dollar=a)
                    return float(sum(float(self.view.v[i]) for i in es)), es

                b, eb = tsum(s["base"])
                nmr, en = tsum(s["num"])
                dnm, _ = tsum(s["den"])
                if dnm == 0:
                    if b != 0:
                        raise self.err(fid, f"prorata_sum: den is zero for {a} while base is not")
                    continue
                val += b * nmr / dnm
                ents_all.extend(eb + en)
            w: dict[str, float] = {}
            for i in ents_all:
                w[self.view.prov[i]] = w.get(self.view.prov[i], 0.0) + abs(float(self.view.v[i]))
            prov = [p for p, _ in sorted(w.items(), key=lambda kv: (-kv[1], kv[0]))]
            f = Fig(
                val, None, "estimated", _one_hot("estimated"), self.view.flag_set(sorted(set(ents_all))), prov,
                "Proportionality assumption: for each account, base x num / den, summed",
            )  # fmt: skip
        ce = s.get("check_equals")
        if ce is not None:
            if not isinstance(ce, dict) or set(ce) - {"ref", "tol"} or "ref" not in ce:
                raise self.err(fid, "check_equals is {ref, tol}")
            other = self.get(str(ce["ref"]))
            tol = float(ce.get("tol", 0.01))
            if abs(f.value - other.value) > tol:
                raise self.err(fid, f"check_equals {ce['ref']}: {f.value:,.4f} vs {other.value:,.4f} (tol {tol})")
        return f

    def output(self, fid: str) -> dict[str, Any]:
        f = self.get(fid)
        s = self.spec["figures"][fid]
        unit = s["unit"]
        val = r2(f.value) if unit == "inr" else canonical_float(f.value, SHARE_DP)
        return {
            "value": val,
            "unit": unit,
            "total": f.total,
            "split": f.split,
            "composition": composition_json(f.comp),
            "flags": list(f.flags),
            "prov": list(f.prov),
            "method": f.method,
            "note_key": s.get("note_key"),
        }


def _check_view_ids(ev: Evaluator, step: dict[str, Any]) -> None:
    v = step.get("view") or {}
    sid = step.get("id")
    need = {"view", "preset", "year", "expanded", "highlight", "select"}
    if set(v) != need:
        raise ExportError(f"story {ev.slug}, step {sid}: view keys must be {sorted(need)}, got {sorted(v)}")
    if v["view"] not in ("sam", "ts") or v["preset"] not in ("simple", "full"):
        raise ExportError(f"story {ev.slug}, step {sid}: bad view/preset")
    if v["year"] not in ev.td.periods:
        raise ExportError(f"story {ev.slug}, step {sid}: year {v['year']!r} is not a period")
    uni = ev.universe
    ts_ids = {t["id"] for t in ev.h.ts_nodes}
    for n in v["expanded"] or []:
        if n not in ev.h.nodes or not ev.h.nodes[n].expandable:
            raise ExportError(f"story {ev.slug}, step {sid}: expanded {n!r} is not an expandable node")
    for x in [*(v["highlight"] or []), *([v["select"]] if v["select"] else [])]:
        if x in uni or x in ts_ids:
            continue
        base, _, suffix = x.partition("~")
        a, sep, b = base.partition("--")
        if not sep or a not in uni or b not in uni or suffix not in ("", "neg"):
            raise ExportError(f"story {ev.slug}, step {sid}: {x!r} is not a node or link id")
        ua, ub = uni[a], uni[b]
        if ua & ub:
            raise ExportError(f"story {ev.slug}, step {sid}: link {x!r} joins nested nodes")
        sign = -1 if suffix == "neg" else 1
        if not any(c in ua and r in ub and r2(val) * sign > 0 for (r, c), val in ev.view.cell_value.items()):
            raise ExportError(
                f"story {ev.slug}, step {sid}: link {x!r} has no {'negative' if sign < 0 else 'positive'} cells"
            )


def evaluate_story(
    slug: str,
    spec: dict[str, Any],
    view: SamView,
    td: TsData,
    pins: list[Pin],
    flow_entries: dict[str, Any],
    gdp: float,
    gdp_prov: str,
) -> dict[str, Any]:
    bad = set(spec) - {"slug", "figures", "steps"}
    if bad:
        raise ExportError(f"story {slug}: unknown top-level keys {sorted(bad)}")
    ev = Evaluator(slug, spec, view, td, pins, gdp, gdp_prov)
    figures = {fid: ev.output(fid) for fid in sorted(spec.get("figures") or {})}
    steps = []
    for st in spec.get("steps") or []:
        if set(st) - {"id", "view", "figures"}:
            raise ExportError(f"story {slug}: step keys are id, view, figures: {sorted(st)}")
        for f in st.get("figures") or []:
            if f not in figures:
                raise ExportError(f"story {slug}, step {st.get('id')}: figure {f!r} is not defined")
        _check_view_ids(ev, st)
        v = st["view"]
        steps.append(
            {
                "id": str(st["id"]),
                "view": {
                    "view": v["view"],
                    "preset": v["preset"],
                    "year": v["year"],
                    "expanded": list(v["expanded"] or []),
                    "highlight": list(v["highlight"] or []),
                    "select": v["select"],
                },
                "figures": list(st.get("figures") or []),
            }
        )
    ids = [s["id"] for s in steps]
    if len(ids) != len(set(ids)):
        raise ExportError(f"story {slug}: duplicate step ids")
    return {"slug": slug, "figures": figures, "steps": steps}
