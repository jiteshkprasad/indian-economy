"""V1 data fidelity: independent re-derivation of every number the Phase 3 site shows (PLAN s.7, row V1).

Report: docs/phase3/verify/V1_data_fidelity.md. Written by a verifier who built nothing in Phase 3. Nothing here
imports `pipeline` code: the balanced SAM, the entries, the balancing log, the constraints, the time series and the
provenance are read with DuckDB straight from Parquet; the curated YAML files (hierarchy, explanation items,
judgement bands, old-base scope, link policy, story specs, the time-series account sets) are read as data. The
account hierarchy is re-typed from the PLAN s.3.2 table, not read from pipeline/export/hierarchy.yaml.

The display formatter (`fmt`) is written here from PLAN s.3.3 (half away from zero on the exact binary value), so
the built pages are compared with an independent formatter.

Confirmed defects are strict xfails: they turn into failures (XPASS) once fixed, so the xfail must then go.
Tests that read the built site (web/out/) skip when it is absent: build with `npm --prefix web run build`.

`uv run python tests/verify/test_phase3_data_fidelity.py` regenerates web/tests/verify/panel_states.json and
web/tests/verify/story_expect.json, the expectations the Playwright spec web/tests/verify/v1_fidelity.spec.ts
checks against the rendered site.
"""

from __future__ import annotations

import glob
import html
import json
import random
import re
from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal
from functools import cache
from pathlib import Path
from urllib.parse import urlparse

import duckdb
import pytest
import yaml

pytestmark = [pytest.mark.export]

ROOT = Path(__file__).resolve().parents[2]
SAM = ROOT / "data" / "sam" / "2023-24"
TSD = ROOT / "data" / "timeseries"
TF = TSD / "top_flows.parquet"
WEB = ROOT / "web"
OUT = WEB / "out" / "en"
SEED = 20261002

CON = duckdb.connect()


def q(sql: str) -> list[tuple]:
    return CON.sql(sql).fetchall()


@cache
def vdir() -> Path:
    idx = json.loads((WEB / "public" / "data" / "index.json").read_text())
    assert idx["fixture"] is False, "V1 runs on the real export only"
    return WEB / "public" / "data" / idx["data_version"]


def jload(rel: str):
    return json.loads((vdir() / rel).read_text())


# ---------------------------------------------------------------------------------------------------------------
# The hierarchy, re-typed from PLAN s.3.2
# ---------------------------------------------------------------------------------------------------------------
SUF = {
    "AGRI": ["CROP", "LVST", "FOFI"],
    "MINE": ["COAL", "OILG", "OMIN"],
    "MANU": ["FOOD", "BVTB", "TXAP", "WOOD", "GJOM", "RPET", "CHEM", "PHRM", "NMMN", "MTLS", "MACH", "ELEQ", "TREQ"],
    "CNUT": ["CNST", "UTIL"],
    "TTC": ["TRAD", "HOTL", "TRNS", "COMM"],
    "FIRE": ["FINS", "INSR", "DWEL", "BSRE", "ITSV"],
    "PSOC": ["EDUC", "HLTH", "OSRV", "PADM"],
}
L1: dict[str, list[str]] = {}
for _g, _s in SUF.items():
    L1[f"PRDS.{_g}"] = [f"C_{x}" for x in _s]
    L1[f"PROD.{_g}"] = [f"A_{x}" for x in _s]
L1.update(
    {
        "FACT.LAB": ["F_LREG", "F_LCAS"],
        "HH.RUR": [f"H_R{i}" for i in range(1, 6)],
        "HH.URB": [f"H_U{i}" for i in range(1, 6)],
        "TAX.GST": ["T_CGST", "T_SGST", "T_GCES"],
        "TAX.OIND": ["T_CUST", "T_UEXC", "T_SVAT", "T_SEXC", "T_OPRT"],
        "TAX.DIR": ["T_PIT", "T_CIT"],
        "SI.CORP": ["K_NFPU", "K_NFPR"],
        "SI.FIN": ["K_RBI", "K_BANK", "K_NBFC", "K_INSP", "K_MUTF"],
        "SI.GOV": ["K_GCEN", "K_GSTA"],
        "FINM.MONEY": ["I_CURR", "I_DEPO"],
        "FINM.GOVD": ["I_GSEC", "I_SSAV"],
        "FINM.SEC": ["I_CBND", "I_EQTY", "I_MFUN"],
        "FINM.OTH": ["I_RESV", "I_OTHR"],
    }
)
L0: dict[str, list[str]] = {
    "PRDS": [a for k, v in L1.items() if k.startswith("PRDS.") for a in v] + ["M_TTM"],
    "PROD": [a for k, v in L1.items() if k.startswith("PROD.") for a in v],
    "ROW": ["R_ROW"],
    "FACT": ["F_LREG", "F_LCAS", "F_MIXD", "F_GOSC"],
    "HH": L1["HH.RUR"] + L1["HH.URB"],
    "NFC": ["E_NFPU", "E_NFPR"],
    "FC": ["E_RBI", "E_BANK", "E_NBFC", "E_INSP"],
    "TAX": L1["TAX.GST"] + L1["TAX.OIND"] + L1["TAX.DIR"] + ["T_PSUB", "T_PROD"],
    "CEN": ["G_CEN"],
    "STA": ["G_STA"],
    "SI": L1["SI.CORP"] + L1["SI.FIN"] + L1["SI.GOV"] + ["K_HH", "K_ROW", "K_DSTK"],
    "DISC": ["X_DISC"],
    "FINM": L1["FINM.MONEY"] + L1["FINM.GOVD"] + L1["FINM.SEC"] + L1["FINM.OTH"] + ["I_LOAN", "I_INPE"],
}
SIMPLE = {"PRODUCERS": L0["PRDS"] + L0["PROD"], "SI": L0["SI"] + L0["FINM"]}
SIMPLE.update({k: L0[k] for k in ["ROW", "FACT", "HH", "NFC", "FC", "TAX", "CEN", "STA", "DISC"]})
TSN = {k: v for k, v in SIMPLE.items() if k not in ("TAX", "CEN", "STA")}
TSN["GOV"] = L0["TAX"] + L0["CEN"] + L0["STA"]
CHILDREN = {
    g: [k for k in L1 if k.startswith(g + ".")] + [a for a in accs if not any(a in v for v in L1.values())]
    for g, accs in L0.items()
}
CHILDREN.update({k: list(v) for k, v in L1.items()})
NODE_ACC: dict[str, list[str]] = {**L0, **L1, "PRODUCERS": SIMPLE["PRODUCERS"], "GOV": TSN["GOV"]}
ORDER = [g for g in L0]


def to_map(groups: dict[str, list[str]]) -> dict[str, str]:
    m: dict[str, str] = {}
    for g, accs in groups.items():
        for a in accs:
            assert a not in m, a
            m[a] = g
    return m


def visible(preset: str, expanded: list[str]) -> dict[str, str]:
    """account -> visible node, for a preset and a list of expanded node ids (PLAN s.3.2, s.4.3)."""
    if not expanded and preset == "simple":
        return to_map(SIMPLE)
    groups = {g: list(a) for g, a in L0.items()}
    for x in expanded:  # parents before children, as the URL keeps them in hierarchy order
        if x not in groups:
            continue
        del groups[x]
        for c in CHILDREN[x]:
            groups[c] = list(NODE_ACC.get(c, [c]))
    return to_map(groups)


@cache
def accounts_yaml() -> list[dict]:
    return yaml.safe_load((ROOT / "pipeline" / "sam" / "accounts.yaml").read_text())["accounts"]


@cache
def groups_yaml() -> dict[str, list[str]]:
    g: dict[str, list[str]] = defaultdict(list)
    for a in accounts_yaml():
        g[a["group"]].append(a["code"])
    return dict(g)


# ---------------------------------------------------------------------------------------------------------------
# SAM, entries, labels, flags, pins
# ---------------------------------------------------------------------------------------------------------------
@cache
def cells() -> list[tuple[str, str, float]]:
    """Non-zero account cells after rounding to 2 dp (row receives, col pays)."""
    return [
        (r, c, round(v, 2))
        for r, c, v in q(f"select row, col, value from '{SAM}/sam_balanced.parquet'")
        if round(v, 2) != 0
    ]


def aggregate(m: dict[str, str], prds_internal: bool = True) -> tuple[dict[str, float], dict[str, list[float]]]:
    """Links {payer--receiver[~neg]: value} and internal {node: [pos, neg]}; the account cell is the atom.
    Cells inside PRDS stay internal at every zoom (PLAN s.4.4) unless prds_internal is False."""
    links: dict[str, float] = defaultdict(float)
    internal: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for r, c, v in cells():
        p, rc = m[c], m[r]
        # flows inside product markets stay internal
        if p == rc or (prds_internal and r in L0["PRDS"] and c in L0["PRDS"]):
            internal[p if p == rc else "PRDS"][0 if v > 0 else 1] += v
            continue
        links[f"{p}--{rc}" + ("" if v > 0 else "~neg")] += v
    return dict(links), dict(internal)


def heights(links: dict[str, float]) -> tuple[dict[str, float], dict[str, float]]:
    inn: dict[str, float] = defaultdict(float)
    out: dict[str, float] = defaultdict(float)
    for k, v in links.items():
        p, r = k.split("~")[0].split("--")
        if v > 0:
            out[p] += v
            inn[r] += v
        else:  # drawn reversed: receiver -> payer
            out[r] -= v
            inn[p] -= v
    return dict(inn), dict(out)


KEY = ("row", "col", "ref", "component")


@cache
def entries() -> list[dict]:
    rows = q(f"""select e.row, e.col, e.ref, e.component, e.value, e.status, e.prior_status, e.role, e.prov_id,
                 e.prior, e.balanced, e.change, e.bop_function, l.explanation_required, l.binding, l.pct_change
                 from '{SAM}/sam_entries_balanced.parquet' e
                 join '{SAM}/balancing_log.parquet' l using (row, col, ref, component)""")
    cols = [
        "row",
        "col",
        "ref",
        "component",
        "value",
        "status",
        "prior_status",
        "role",
        "prov",
        "prior",
        "balanced",
        "change",
        "bop",
        "req",
        "binding",
        "pct",
    ]
    return [dict(zip(cols, r)) for r in rows]


def ekey(e: dict) -> tuple[str, str, str, str]:
    return (e["row"], e["col"], e["ref"], e["component"])


def _verdict(why: str) -> str:
    w = " ".join(why.split()).lower()
    if w.startswith("explained in direction") or "level unexplained" in w[:90]:
        return "level unexplained"
    if w.startswith("unexplained"):
        return "unexplained"
    if w.startswith("explained"):
        return "explained"
    return "no verdict word"


def _needs(p: float, b: float) -> bool:  # SPEC s.5.3 threshold, as stated in PLAN s.3.4.1
    d = abs(b - p)
    return d >= 5000 or (d >= 500 and (p == 0 or d / abs(p) >= 0.10))


def _drift() -> tuple[float, float]:
    """EXPLAIN_DRIFT_REL / _ABS, read as text (not imported) from pipeline/sam/spec.py."""
    t = (ROOT / "pipeline" / "sam" / "spec.py").read_text()
    rel = float(re.search(r"^EXPLAIN_DRIFT_REL\s*=\s*([0-9.]+)", t, re.M).group(1))
    ab = float(re.search(r"^EXPLAIN_DRIFT_ABS\s*=\s*([0-9.]+)", t, re.M).group(1))
    return rel, ab


@cache
def verdicts() -> tuple[dict, dict]:
    items = {}
    files = sorted(glob.glob(str(ROOT / "pipeline" / "sam" / "explanations" / "*.yaml")))
    shared = ROOT / "pipeline" / "sam" / "explanations.yaml"
    if shared.exists():
        files.append(str(shared))
    for f in files:
        for it in (yaml.safe_load(Path(f).read_text()) or {}).get("explanations") or []:
            items[(it["row"], it["col"], str(it["ref"]), str(it["component"]))] = it
    rel, ab = _drift()

    def fits(it, ch):
        ex = float(it["balanced"]) - float(it["prior"])
        return abs(ch - ex) <= max(rel * abs(ex), ab)

    ev = {}
    for e in entries():
        it = items.get(ekey(e))
        if e["req"] and it is not None and fits(it, e["change"]):
            ev[ekey(e)] = _verdict(it["why"])
    agg: dict = defaultdict(lambda: [0.0, 0.0, 0])
    for e in entries():
        a = agg[(e["row"], e["col"])]
        a[0] += e["prior"]
        a[1] += e["balanced"]
        a[2] += 1
    cv = {}
    for (r, c), (p, b, n) in agg.items():
        it = items.get((r, c, "*", "*"))
        if n > 1 and _needs(p, b) and it is not None and fits(it, b - p):
            cv[(r, c)] = _verdict(it["why"])
    return ev, cv


@cache
def constraints() -> dict[str, tuple]:
    rows = q(f"""select c.constraint_id, c.kind, c.rows, c.cols, c.refs, c.components, c.target, c.tol_abs,
                 c.tol_rel, c.prov_id, b.binding from '{SAM}/constraints.parquet' c
                 join '{SAM}/balancing_constraints.parquet' b using (constraint_id)""")
    return {r[0]: r for r in rows}


def select(rows, cols, refs=None, comps=None, bops=None, excl=None) -> frozenset:
    return frozenset(
        ekey(e)
        for e in entries()
        if e["row"] in rows
        and e["col"] in cols
        and (refs is None or e["ref"] in refs)
        and (comps is None or e["component"] in comps)
        and (bops is None or e["bop"] in bops)
        and not (excl and e["component"] in excl)
    )


def members(cid: str) -> frozenset:
    _, _, rows, cols, refs, comps, *_ = constraints()[cid]
    return select(
        set(rows.split(",")),
        set(cols.split(",")),
        set(refs.split(",")) if refs else None,
        set(comps.split(",")) if comps else None,
    )


@cache
def judgement_members() -> frozenset:
    ids = yaml.safe_load((ROOT / "pipeline" / "export" / "judgement_bands.yaml").read_text())["judgement_bands"]
    out: set = set()
    for c in ids:
        out |= members(c)
    return frozenset(out)


@cache
def labels() -> dict[tuple, str]:
    """PLAN s.3.4.1, re-implemented."""
    ev, cv = verdicts()
    jm = judgement_members()
    out = {}
    for e in entries():
        k = ekey(e)
        if (
            e["role"] == "free"
            and e["status"] == "balanced"
            and (e["req"] or k in ev or (e["row"], e["col"]) in cv or k in jm)
        ):
            out[k] = "balancing_set"
        else:
            out[k] = {"official": "official", "derived": "derived", "estimated": "estimated"}[e["prior_status"]]
    return out


@cache
def prov_graph() -> dict[str, dict]:
    g: dict[str, dict] = {}
    for f, kind in [
        (SAM / "_provenance.parquet", "sam"),
        (TSD / "_provenance.parquet", "ts"),
        (ROOT / "data" / "clean" / "*" / "_provenance.parquet", "clean"),
    ]:
        for pid, src, url, ret, tab, inp, st in q(
            f"select prov_id, source_id, url, retrieved_at, table_id, inputs, status from '{f}'"
        ):
            assert pid not in g, f"duplicate prov id {pid}"
            g[pid] = dict(
                kind=kind, src=src, url=url, ret=ret, tab=tab, st=st, inp=[x for x in (inp or "").split(",") if x]
            )
    return g


@cache
def reach(pid: str) -> frozenset:
    g = prov_graph()
    seen: set = set()
    stack = [pid]
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        assert p in g, f"unresolved prov id {p}"
        seen.add(p)
        stack.extend(g[p]["inp"])
    return frozenset(seen)


@cache
def leaves(pid: str) -> tuple[str, ...]:
    g = prov_graph()
    return tuple(sorted(x for x in reach(pid) if g[x]["kind"] == "clean" and g[x]["url"]))


def is_assumption(pid: str) -> bool:
    return prov_graph()[pid]["kind"] != "clean" and not leaves(pid)


def depends_on_assumption(pid: str) -> bool:
    return any(is_assumption(x) for x in reach(pid))


@cache
def old_base_ids() -> frozenset:
    y = yaml.safe_load((ROOT / "pipeline" / "export" / "old_base_scope.yaml").read_text())["old_base_scope"]
    return frozenset(r["prov_id"] for r in y)


def entry_flags(e: dict) -> set[str]:
    ev, cv = verdicts()
    k = ekey(e)
    vs = {ev.get(k), cv.get((e["row"], e["col"]))}
    fl = set()
    if k in judgement_members():
        fl.add("judgement_band")
    if "unexplained" in vs:
        fl.add("unexplained")
    if "level unexplained" in vs:
        fl.add("level_unexplained")
    if e["prov"] in old_base_ids():
        fl.add("old_base_structure")
    if "X_DISC" in (e["row"], e["col"]):
        fl.add("discrepancy")
    if e["value"] < 0:
        fl.add("has_negative")
    if depends_on_assumption(e["prov"]):
        fl.add("depends_on_assumption")
    return fl


@cache
def account_sets() -> dict[str, list[str]]:
    return yaml.safe_load((ROOT / "pipeline" / "timeseries" / "flows.yaml").read_text())["account_sets"]


def expand(xs) -> set[str]:
    out: set[str] = set()
    for x in xs:
        if x.startswith("@"):
            out |= set(groups_yaml()[x[1:]])
        elif x.startswith("$"):
            out |= set(account_sets()[x[1:]])
        else:
            out.add(x)
    return out


@cache
def ts_entries() -> dict[str, tuple[frozenset, frozenset]]:
    """The SAM entries each series measures (eval_sam re-implemented): {flow: (entries, coefs)}."""
    out = {}
    for fid, terms in q(f"select flow_id, sam_terms from '{TSD}/top_flows_definitions.parquet'"):
        if not terms:
            continue
        m: set = set()
        coefs = set()
        for t in json.loads(terms):
            m |= select(
                expand(t["rows"]),
                expand(t["cols"]),
                set(t["refs"]),
                set(t["components"]) if t.get("components") else None,
                set(t["bop_functions"]) if t.get("bop_functions") else None,
                set(t.get("exclude_components") or []),
            )
            coefs.add(t.get("coef", 1))
        out[fid] = (frozenset(m), frozenset(coefs))
    return out


def ts_row(fid: str, period: str, variant: str = "published"):
    """The main-series row (PLAN s.3.7.1): base 2022-23, else 2011-12, else null base."""
    r = q(f"""select value, base_year, status, estimate_stage, flags, segment, prov_id from '{TF}'
              where flow_id = '{fid}' and period = '{period}' and variant = '{variant}'
              order by case base_year when '2022-23' then 1 when '2011-12' then 2 else 3 end""")
    return r[0] if r else None


@cache
def pins() -> dict[str, tuple[frozenset, str]]:
    """PLAN s.3.4.2 pins: tight equal/band constraints with official/derived prov, and passing series."""
    pst = {}
    for f in (SAM / "_provenance.parquet", TSD / "_provenance.parquet"):
        pst.update(dict(q(f"select prov_id, status from '{f}'")))
    sums = defaultdict(float)
    vals = {ekey(e): e["value"] for e in entries()}
    out = {}
    for cid, kind, _r, _c, _rf, _cp, tgt, ta, tr, prov, _ in constraints().values():
        if kind not in ("equal", "band"):
            continue
        tol = max(ta, tr * abs(tgt))
        if tol > max(1.0, 0.001 * abs(tgt)) or pst.get(prov) not in ("official", "derived"):
            continue
        m = members(cid)
        s = sum(vals[k] for k in m)
        if m and abs(s - tgt) <= tol + 1e-4:  # the solver's band edge carries ~1e-6 of float noise
            out[cid] = (m, pst[prov])
        sums[cid] = s
    verdict = dict(q(f"select flow_id, verdict from '{TSD}/top_flows_sam_check.parquet'"))
    for fid, (m, coefs) in ts_entries().items():
        if verdict.get(fid) == "pass" and coefs == {1} and m:
            out["ts:" + fid] = (m, ts_row(fid, "2023-24")[2])
    return out


@cache
def _pins_by_entry() -> dict:
    d = defaultdict(list)
    for pid, (m, _) in pins().items():
        for k in m:
            d[k].append(pid)
    return d


def cover(keys) -> tuple[str, list[str]] | None:
    """Total label: the entry set is exactly a disjoint union of pins; the most certain such cover wins."""
    s = frozenset(keys)
    if not s:
        return None
    by = _pins_by_entry()
    cand = [p for p in {p for k in s for p in by.get(k, [])} if pins()[p][0] <= s]
    cmap = defaultdict(list)
    for p in cand:
        for k in pins()[p][0]:
            cmap[k].append(p)
    sols: list[list[str]] = []

    def rec(rem, chosen):
        if len(sols) > 200:
            return
        if not rem:
            sols.append(list(chosen))
            return
        k = min(rem, key=lambda k: len(cmap.get(k, [])))
        for p in sorted(cmap.get(k, [])):
            if pins()[p][0] <= rem:
                rec(rem - pins()[p][0], chosen + [p])

    rec(s, [])
    if not sols:
        return None
    for so in sols:
        if all(pins()[p][1] == "official" for p in so):
            return "official", sorted(so)
    return "derived", sorted(sols[0])


ORD = ["official", "derived", "estimated", "balancing_set"]


def composition(keys) -> tuple[dict[str, float], str]:
    ab: dict[str, float] = defaultdict(float)
    lb = labels()
    vals = {ekey(e): e["value"] for e in entries()}
    for k in keys:
        ab[lb[k]] += abs(vals[k])
    tot = sum(ab.values())
    head = ORD[max((ORD.index(x) for x in ab if ab[x] >= 0.1 * tot - 1e-9), default=0)]
    return {x: ab[x] / tot for x in ORD} if tot else {}, head


def link_entries(lid: str, payer_acc, rec_acc) -> frozenset:
    """Entries of a link's positive part, negative part (~neg) or whole pair (~pair); sign by account cell."""
    part = lid.split("~")[1] if "~" in lid else "pos"
    cv = {(r, c): v for r, c, v in cells()}
    out = set()
    for e in entries():
        if e["col"] in payer_acc and e["row"] in rec_acc:
            if e["row"] in L0["PRDS"] and e["col"] in L0["PRDS"]:
                continue
            v = cv.get((e["row"], e["col"]), 0)
            if part == "pair" or (part == "pos" and v > 0) or (part == "neg" and v < 0):
                out.add(ekey(e))
    return frozenset(out)


# ---------------------------------------------------------------------------------------------------------------
# Formatter, PLAN s.3.3 (written here, not ported from format.ts)
# ---------------------------------------------------------------------------------------------------------------
MINUS = "−"


def _fixed(x: float, d: int) -> str:
    return str(Decimal(abs(x)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


def _group(s: str) -> str:
    ip, _, fr = s.partition(".")
    if len(ip) > 3:
        head, last = ip[:-3], ip[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        ip = ",".join(parts + [last])
    return ip + ("." + fr if fr else "")


def _signed(v: float, mag: str, body: str) -> str:
    return MINUS + body if v < 0 and re.search(r"[1-9]", mag) else body


def fmt(v: float, kind: str) -> str:
    if kind == "inr":
        if float(_fixed(v, 0)) >= 1e5:
            m = _fixed(v / 1e5, 2)
            return _signed(v, m, f"₹{_group(m)} lakh crore")
        r1 = _fixed(v, 1)
        if float(r1) >= 10:
            r0 = _fixed(v, 0)
            return _signed(v, r0, f"₹{_group(r0)} crore")
        return _signed(v, r1, f"₹{r1} crore")
    if kind == "pct_gdp":
        p1 = _fixed(100 * v, 1)
        if float(p1) >= 1:
            return _signed(v, p1, f"{_group(p1)}% of GDP")
        p2 = _fixed(100 * v, 2)
        if float(p2) >= 0.01:
            return _signed(v, p2, f"{p2}% of GDP")
        return "0% of GDP" if v == 0 else (MINUS if v < 0 else "") + "<0.01% of GDP"
    if kind == "per100":
        m = _fixed(v, 1)
        return _signed(v, m, f"₹{_group(m)}")
    if kind == "pct":
        m = _fixed(100 * v, 1)
        return _signed(v, m, f"{_group(m)}%")
    if kind == "count":
        m = _fixed(v, 0)
        return _signed(v, m, _group(m))
    raise ValueError(kind)


def test_formatter_golden():
    g = json.loads((ROOT / "pipeline" / "export" / "golden" / "format_cases.json").read_text())
    bad = [(c, fmt(c["value"], c["kind"])) for c in g["cases"] if fmt(c["value"], c["kind"]) != c["out"]]
    assert not bad, bad


# ---------------------------------------------------------------------------------------------------------------
# 1. Hierarchy and cells
# ---------------------------------------------------------------------------------------------------------------
def test_hierarchy_matches_plan_table():
    h = jload("hierarchy.json")
    hn = {n["id"]: n for n in h["nodes"]}
    for g, accs in {**L0, **L1}.items():
        assert sorted(hn[g]["accounts"]) == sorted(accs), g
    assert sum(1 for n in h["nodes"] if n["level"] == 1) == 27
    assert len(h["nodes"]) == 168
    assert sorted(a["code"] for a in h["accounts"]) == sorted(a["code"] for a in accounts_yaml())
    for n in h["ts_nodes"]:
        assert sorted(n["accounts"]) == sorted(TSN[n["id"]]), n["id"]
    assert h["presets"]["simple"]["merges"] == {"PRODUCERS": ["PRDS", "PROD"], "SI": ["SI", "FINM"]}


def test_cells_equal_parquet():
    h = jload("hierarchy.json")
    acc = [a["code"] for a in h["accounts"]]
    c = jload("sam/cells.json")
    ex = {(acc[r], acc[k]): v for r, k, v in zip(c["row"], c["col"], c["v"])}
    mine = {(r, k): v for r, k, v in cells()}
    assert set(ex) == set(mine)
    bad = [(k, ex[k], mine[k]) for k in ex if abs(ex[k] - mine[k]) > 0.0051]
    assert not bad, bad[:5]
    assert sum(1 for v in ex.values() if v < 0) == 66
    rs, cs = defaultdict(float), defaultdict(float)
    for (r, k), v in ex.items():
        rs[r] += v
        cs[k] += v
    assert max(abs(rs[a] - cs[a]) for a in acc) <= 0.005 * len(ex)


def test_level0_prototype_figures():
    links, internal = aggregate(to_map(L0))
    assert len(links) == 70 and sum(k.endswith("~neg") for k in links) == 9
    assert len({k.split("~")[0] for k in links}) == 62
    neg = {k: round(v / 1e5, 2) for k, v in links.items() if k.endswith("~neg")}
    assert neg == {
        "PRDS--TAX~neg": -5.76,
        "TAX--CEN~neg": -2.71,
        "TAX--STA~neg": -3.63,
        "PROD--TAX~neg": -2.86,
        "CEN--SI~neg": -4.27,
        "SI--FINM~neg": -8.55,
        "FINM--SI~neg": -1.45,
        "SI--PRDS~neg": -0.26,
        "PROD--PRDS~neg": -0.0,
    }
    assert {k: round(v[0] / 1e5, 2) for k, v in internal.items()} == {
        "PRDS": 79.20,
        "NFC": 2.56,
        "FC": 4.29,
        "SI": 7.28,
    }
    inn, out = heights(links)
    want = {
        "PRDS": 677.82,
        "PROD": 578.51,
        "FACT": 265.25,
        "SI": 249.97,
        "HH": 245.74,
        "FINM": 145.39,
        "ROW": 80.15,
        "NFC": 64.27,
        "TAX": 60.70,
        "CEN": 43.80,
        "FC": 41.78,
        "STA": 38.79,
        "DISC": 5.71,
    }
    for n, w in want.items():
        assert round(inn[n] / 1e5, 2) == w and abs(inn[n] - out[n]) < 0.5, n


def test_simple_and_level1_figures():
    links, internal = aggregate(to_map(SIMPLE))
    assert len(links) == 61
    inn, out = heights(links)
    assert round(inn["PRODUCERS"] / 1e5, 2) == 369.09 and round(inn["SI"] / 1e5, 2) == 104.58
    for n in inn:
        assert abs(inn[n] - out[n]) < 0.5, n
    assert round(internal["PRODUCERS"][0] / 1e5, 2) == 966.43
    assert (round(internal["SI"][0] / 1e5, 2), round(internal["SI"][1] / 1e5, 2)) == (288.06, -10.00)
    l1, i1 = aggregate(visible("full", list(L0)), prds_internal=False)
    pairs = {k.split("~")[0] for k in l1}
    assert len(pairs) + len(i1) == 364  # PLAN s.3.2: 364 non-zero directed pairs, 6 internal


# ---------------------------------------------------------------------------------------------------------------
# 2. GDP, summary, headline
# ---------------------------------------------------------------------------------------------------------------
def test_gdp_and_summary():
    s = jload("summary.json")
    m01 = q(
        f"select value, prov_id from '{TF}' where flow_id='M01' and period='2023-24' "
        f"and variant='published' and base_year='2022-23'"
    )
    assert len(m01) == 1
    assert abs(s["gdp"]["value"] - round(m01[0][0], 2)) < 0.006 and s["gdp"]["prov"] == m01[0][1]
    links, _ = aggregate(to_map(L0))
    gdp_sam = sum(v for k, v in links.items() if k.split("~")[0] in ("PROD--FACT", "PROD--TAX", "PRDS--TAX"))
    assert abs(gdp_sam - s["gdp"]["value"]) <= 1.0
    lb = labels()
    cnt = Counter(lb.values())
    ab = defaultdict(float)
    for e in entries():
        ab[lb[ekey(e)]] += abs(e["value"])
    for k, v in s["sam"]["labels"].items():
        assert v["entries"] == cnt[k] and abs(v["abs"] - ab[k]) < 1, k
    assert cnt == {"official": 1127, "derived": 114, "estimated": 2180, "balancing_set": 472}
    tot = sum(ab.values())
    for k, short in (("official", "o"), ("derived", "d"), ("estimated", "e"), ("balancing_set", "b")):
        assert abs(s["sam"]["composition"][short] - ab[k] / tot) < 1e-4
    assert s["sam"]["cells_nonzero"] == len(cells()) and s["sam"]["entries"] == len(entries())
    moved = sum(abs(e["balanced"] - e["prior"]) for e in entries())
    assert abs(s["sam"]["balancing"]["moved_abs"] - moved) < 1


def test_headline_household_outlays():
    hh = set(L0["HH"])
    m = to_map(L0)
    by = defaultdict(float)
    for r, c, v in cells():
        if c in hh:
            by[m[r]] += v
    want = {
        "consumption": by["PRDS"],
        "saving": by["SI"],
        "taxes": by["TAX"],
        "financial_services_and_interest": by["FC"],
        "transfers_abroad": by["ROW"],
        "to_government": by["CEN"] + by["STA"],
        "unallocated_residual": by["DISC"],
    }
    assert set(by) == {"PRDS", "SI", "TAX", "FC", "ROW", "CEN", "STA", "DISC"}
    h = jload("summary.json")["headline"]["hh_outlays"]
    tot = sum(by.values())
    assert abs(h["total"] - tot) < 0.1
    for p in h["parts"]:
        assert abs(p["value"] - want[p["key"]]) < 0.1, p["key"]
        assert abs(p["per100"] - 100 * want[p["key"]] / tot) < 1e-5, p["key"]


# ---------------------------------------------------------------------------------------------------------------
# 3. Time series
# ---------------------------------------------------------------------------------------------------------------
def test_series_main_selection_and_shares():
    s = jload("ts/series.json")
    per = s["periods"]
    assert per[0] == "1950-51" and per[-1] == "2025-26" and len(per) == 76
    rows = q(f"""with p as (select *, case when base_year='2022-23' then 1 when base_year='2011-12' then 2
                 when base_year is null then 3 end pr from '{TF}' where variant='published'),
                 b as (select flow_id, period, min(pr) m from p group by all)
                 select p.flow_id, p.period, p.value, p.base_year, p.status, p.estimate_stage, p.flags, p.segment,
                 p.prov_id, count(*) over (partition by p.flow_id, p.period) n
                 from p join b on p.flow_id=b.flow_id and p.period=b.period and p.pr=b.m""")
    assert all(r[-1] == 1 for r in rows), "two candidate rows for one main value"
    main = {(r[0], r[1]): r for r in rows}
    gdp = {
        (p, b): v
        for p, b, v in q(f"select period, base_year, value from '{TF}' where flow_id='M01' and variant='published'")
    }
    gdpl = dict(q(f"select period, value from '{TF}' where flow_id='M01' and variant='linked_2022_23'"))
    defs = {r[0]: r for r in q(f"select flow_id, display_sign, link_policy from '{TSD}/top_flows_definitions.parquet'")}
    bad = []
    n = 0
    for f in s["flows"]:
        fid = f["id"]
        ds = defs[fid][1]
        assert f["display_sign"] == ds
        for i, p in enumerate(per):
            r = main.get((fid, p))
            a = f["main"]
            if r is None:
                assert a["v"][i] is None, (fid, p)
                continue
            n += 1
            if abs(a["v"][i] - round(r[2], 2)) > 0.0051:
                bad.append(("v", fid, p))
            if (a["base"][i], a["status"][i], a["flags"][i], a["segment"][i], a["prov"][i]) != (
                r[3],
                r[4],
                r[6],
                r[7],
                r[8],
            ):
                bad.append(("meta", fid, p))
            if a["stage"][i] != (None if r[5] == "n.a." else r[5]):
                bad.append(("stage", fid, p))
            b = r[3] or ("2022-23" if p >= "2022-23" else "2011-12")
            if abs(a["share"][i] - r[2] * ds / gdp[(p, b)]) > 1.5e-6:
                bad.append(("share", fid, p))
        if f["linked"] is not None:
            assert defs[fid][2] == "linked"
            lr = dict(q(f"select period, value from '{TF}' where flow_id='{fid}' and variant='linked_2022_23'"))
            for i, p in enumerate(per):
                e = lr.get(p) if p < "2022-23" else (main.get((fid, p)) or (None, None, None))[2]
                v = f["linked"]["v"][i]
                if (v is None) != (e is None) or (v is not None and abs(v - round(e, 2)) > 0.0051):
                    bad.append(("linked", fid, p))
                if v is not None:
                    g = gdpl[p] if p < "2022-23" else gdp[(p, "2022-23")]
                    if abs(f["linked"]["share"][i] - e * ds / g) > 1.5e-6:
                        bad.append(("linkedshare", fid, p))
        else:
            assert defs[fid][2] != "linked", fid
        for alt in f["alts"]:
            rr = dict(q(f"select period, value from '{TF}' where flow_id='{fid}' and variant='{alt['variant']}'"))
            for i, p in enumerate(per):
                v = alt["arrays"]["v"][i]
                if (v is None) != (p not in rr) or (v is not None and abs(v - round(rr[p], 2)) > 0.0051):
                    bad.append(("alt", fid, p))
    assert not bad, bad[:20]
    assert n == len(main) == 1937
    assert sum(1 for f in s["flows"] if f["linked"] is not None) == 10
    mk = {(f["id"], m["period"], m["kind"]) for f in s["flows"] for m in f["markers"]}
    flags = q(
        f"select flow_id, period, flags from '{TF}' where flags in ('base_change','concept_break','segment_join')"
    )
    assert flags and all(r in mk for r in flags)
    for i, p in enumerate(per):
        r = main.get(("M01", p))
        assert (s["gdp"]["main"][i] is None) == (r is None)
        if r:
            assert abs(s["gdp"]["main"][i] - round(r[2], 2)) < 0.006 and s["gdp"]["main_base"][i] == r[3]


def test_series_sam_check_copied():
    s = {f["id"]: f["check"] for f in jload("ts/series.json")["flows"]}
    for fid, tv, sb, vd, ex in q(
        f"select flow_id, ts_value, sam_balanced, verdict, explanation from '{TSD}/top_flows_sam_check.parquet'"
    ):
        c = s[fid]
        assert c["verdict"] == vd and c["explanation"] == ex, fid
        for a, b in ((c["ts_value"], tv), (c["sam_value"], sb)):
            assert (a is None) == (b is None) and (a is None or abs(a - round(b, 2)) < 0.006), fid


# ---------------------------------------------------------------------------------------------------------------
# 4. Labels, flags, cells, pins
# ---------------------------------------------------------------------------------------------------------------
@cache
def exported_entries() -> dict[tuple, tuple[str, dict]]:
    out = {}
    for f in glob.glob(str(vdir() / "sam" / "entries" / "*.json")):
        d = json.loads(Path(f).read_text())
        for x in d["entries"]:
            out[(x["row"], x["col"], x["ref"], x["component"])] = (d["node"], x)
    return out


def test_entry_labels_verdicts_flags():
    ev, cv = verdicts()
    assert Counter(ev.values()) == {"explained": 151, "level unexplained": 64, "unexplained": 8}
    assert Counter(cv.values()) == {"explained": 73, "level unexplained": 26, "unexplained": 4}
    assert len(judgement_members()) == 97
    X = exported_entries()
    assert len(X) == len(entries()) == 3893
    m0 = to_map(L0)
    bad = Counter()
    for e in entries():
        node, x = X[ekey(e)]
        k = ekey(e)
        bad["node"] += node != m0[e["row"]]
        bad["label"] += x["label"] != labels()[k]
        bad["value"] += abs(x["v"] - round(e["value"], 2)) > 0.0051 or abs(x["prior"] - round(e["prior"], 2)) > 0.0051
        bad["meta"] += (x["status"], x["prior_status"], x["role"], x["prov"]) != (
            e["status"],
            e["prior_status"],
            e["role"],
            e["prov"],
        )
        bad["verdict"] += x["verdict"] != (ev.get(k) or cv.get((e["row"], e["col"])))
        bad["flags"] += set(x["flags"]) != entry_flags(e)
        bad["binding"] += sorted(x["binding"]) != (sorted(e["binding"].split(",")) if e["binding"] else [])
    assert not +bad, bad


def test_entry_pct_change_is_a_fraction():
    """V1-01 (fixed in round 2): pct_change is a fraction of the prior, (value - prior) / |prior|, on the real export,
    checked against the unrounded parquet values (the exported v and prior are rounded to 2 dp, which moves the
    ratio for small entries). 1e-4 is a hundredth of a percentage point, below the display's 0.1%."""
    X = exported_entries()
    bad, n = [], 0
    for e in entries():
        x = X[ekey(e)][1]
        if x["pct_change"] is None:
            if e["prior"] and e["value"] != e["prior"]:
                bad.append(("null", ekey(e)))
            continue
        n += 1
        if not e["prior"]:
            bad.append(("zero prior", ekey(e), x["pct_change"]))
            continue
        want = (e["value"] - e["prior"]) / abs(e["prior"])
        if abs(x["pct_change"] - want) > 1e-4:
            bad.append((ekey(e), x["pct_change"], want))
    assert n > 3800 and not bad, (n, len(bad), bad[:5])


BIT = {
    "judgement_band": 1,
    "unexplained": 2,
    "level_unexplained": 4,
    "old_base_structure": 8,
    "discrepancy": 16,
    "has_negative": 32,
    "depends_on_assumption": 64,
}


def test_cells_composition_split_flags():
    h = jload("hierarchy.json")
    acc = [a["code"] for a in h["accounts"]]
    c = jload("sam/cells.json")
    by = defaultdict(list)
    for e in entries():
        by[(e["row"], e["col"])].append(e)
    bad = Counter()
    for i in range(c["n"]):
        es = by[(acc[c["row"][i]], acc[c["col"][i]])]
        comp, head = composition([ekey(e) for e in es])
        tot = sum(abs(e["value"]) for e in es)
        for lab, key in (
            ("official", "abs_o"),
            ("derived", "abs_d"),
            ("estimated", "abs_e"),
            ("balancing_set", "abs_b"),
        ):
            bad[key] += abs(c[key][i] - comp.get(lab, 0) * tot) > 0.011
        bad["split"] += ORD[c["split"][i]] != head
        fl = 0
        for e in es:
            for f in entry_flags(e):
                fl |= BIT[f]
        bad["flags"] += c["flags"][i] != fl
        bad["n"] += c["n_entries"][i] != len(es)
        ra = defaultdict(float)
        for e in es:
            ra[e["ref"]] += abs(e["value"])
        bad["refs"] += c["refs"][i] != sorted(ra, key=lambda k: (-ra[k], k))
    assert not +bad, bad


def _all_link_ids() -> set[str]:
    ids = set()
    for m in (to_map(L0), to_map(SIMPLE), visible("full", list(L0))):
        links, _ = aggregate(m)
        ids |= set(links)
        for k in links:
            b = k.split("~")[0]
            if b in links and b + "~neg" in links:
                ids.add(b + "~pair")
    return ids


def test_pinned_totals():
    pj = jload("sam/pinned.json")
    bad = []
    for lid, v in sorted(pj.items()):
        p, r = lid.split("~")[0].split("--")
        c = cover(link_entries(lid, set(NODE_ACC.get(p, [p])), set(NODE_ACC.get(r, [r]))))
        if c is None or c[0] != v["total"]:
            bad.append((lid, v, c))
    assert not bad, bad[:10]
    extra = []
    for lid in sorted(_all_link_ids() - set(pj)):
        p, r = lid.split("~")[0].split("--")
        s = link_entries(lid, set(NODE_ACC.get(p, [p])), set(NODE_ACC.get(r, [r])))
        if s and cover(s) is not None:
            extra.append(lid)
    assert not extra, extra[:10]
    l0 = {k.split("~")[0] for k in aggregate(to_map(L0))[0]}
    whole = [
        p
        for p in l0
        if p + "~pair" in pj or (p in pj and (p + "~neg" in pj or p + "~neg" not in aggregate(to_map(L0))[0]))
    ]
    assert len(whole) == 16, sorted(whole)
    for must in ("HH--PRDS", "ROW--HH", "HH--SI"):
        assert pj[must]["total"] == "official"
    assert "NFC--SI" not in pj


# ---------------------------------------------------------------------------------------------------------------
# 5. Provenance
# ---------------------------------------------------------------------------------------------------------------
@cache
def registry() -> dict[str, dict]:
    return {s["id"]: s for s in yaml.safe_load((ROOT / "data" / "registry.yaml").read_text())["sources"]}


def test_provenance_walk():
    pj = jload("provenance.json")
    pol = yaml.safe_load((ROOT / "pipeline" / "export" / "link_policy.yaml").read_text())["hosts"]
    g = prov_graph()
    bad = Counter()
    for pid, r in pj["records"].items():
        lv = leaves(pid)
        mine = defaultdict(set)
        for x in lv:
            mine[g[x]["src"]].add(g[x]["url"])
        cites = {c["source"]: c for c in r["cites"]}
        bad["sources"] += set(mine) != set(cites)
        for src, c in cites.items():
            hosts = {urlparse(u).hostname for u in mine.get(src, ())}
            wh = any(pol.get(h) == "withheld" for h in hosts)
            bad["withheld"] += wh != c["withheld"]
            bad["url_leak"] += wh and any(c["urls"])
            bad["url_unknown"] += any(u and u not in mine.get(src, ()) for u in c["urls"])
        bad["dep"] += depends_on_assumption(pid) != r["depends_on_assumption"]
        bad["assumption"] += is_assumption(pid) != r["assumption"]
        bad["status"] += r["status"] != g[pid]["st"]
    assert not +bad, bad
    for f in glob.glob(str(vdir() / "**" / "*.json"), recursive=True):
        assert not re.search(r"https?://[a-z0-9.]*rbi\.org\.in", Path(f).read_text()), f
    for sid, s in pj["sources"].items():
        if sid in registry():
            assert s["attribution"] == registry()[sid]["license"]["attribution"], sid


def test_every_cited_source_in_registry():
    """V1-07 (closed in round 2: the IFPRI paper was merged into registry.yaml, DECISIONS D3-3). Every cited source is
    in data/registry.yaml itself (not only in an additions file), and its exported registry_status is the
    registry's verification status."""
    pj = jload("provenance.json")
    missing = sorted({c["source"] for r in pj["records"].values() for c in r["cites"]} - set(registry()))
    assert not missing, missing
    bad = [
        (sid, s.get("registry_status"), (registry()[sid].get("verification") or {}).get("status"))
        for sid, s in pj["sources"].items()
        if s.get("registry_status") != (registry()[sid].get("verification") or {}).get("status")
    ]
    assert not bad, bad


def test_cite_sample_50():
    """50 cites (seeded) checked against the clean records: url, table, retrieval dates, registry entry."""
    pj = jload("provenance.json")
    g = prov_graph()
    allc = [(pid, c) for pid, r in sorted(pj["records"].items()) for c in r["cites"]]
    rng = random.Random(SEED)
    bad = []
    for pid, c in rng.sample(allc, 50):
        lv = [g[x] for x in leaves(pid) if g[x]["src"] == c["source"]]
        ok_url = all(any(x["url"] == u for x in lv) for u in c["urls"] if u)
        ok_tab = set(c["tables"]) <= {x["tab"] for x in lv}
        dates = sorted(x["ret"][:10] for x in lv if x["ret"])
        ok_date = not dates or c["retrieved"] == [dates[0], dates[-1]]
        if not (lv and ok_url and ok_tab and ok_date):
            bad.append((pid, c["source"], ok_url, ok_tab, ok_date))
    assert not bad, bad


# ---------------------------------------------------------------------------------------------------------------
# 6. Top-flows board: ribbons, double counting, signs
# ---------------------------------------------------------------------------------------------------------------
def test_ts_view_ribbons():
    tv = jload("ts/view.json")
    s = jload("ts/series.json")
    per = s["periods"]
    F = {f["id"]: f for f in s["flows"]}
    mt = to_map(TSN)
    seen: dict = {}
    for r in tv["ribbons"]:
        fid = r["flow"]
        ents, _ = ts_entries()[fid]
        assert {(mt[k[1]], mt[k[0]]) for k in ents} == {(r["from"], r["to"])}, fid  # rule 1
        for k in ents:  # rule 2: no double counting between ribbons
            assert k not in seen, (fid, seen.get(k), k)
            seen[k] = fid
        assert sum(v is not None for v in F[fid]["main"]["v"]) >= 10, fid  # rule 3
        neg = [per[i] for i, v in enumerate(F[fid]["main"]["v"]) if v is not None and v * F[fid]["display_sign"] < 0]
        assert not neg or (r["reversible"] and r["reversed_text_key"]), (fid, neg)  # rule 4
        assert F[fid]["check"]["verdict"] in ("pass", "explained"), fid  # rule 5
    assert tv["coverage"] == [sum(f["main"]["v"][i] is not None for f in s["flows"]) for i in range(len(per))]
    inn = defaultdict(lambda: [0.0] * len(per))
    out = defaultdict(lambda: [0.0] * len(per))
    for r in tv["ribbons"]:
        for i, sh in enumerate(F[r["flow"]]["main"]["share"]):
            if sh is not None:
                a, b = (r["from"], r["to"]) if sh >= 0 else (r["to"], r["from"])
                out[a][i] += abs(sh)
                inn[b][i] += abs(sh)
    for n, v in tv["slot_share"].items():
        mine = max((max(inn[n][i], out[n][i]) for i in range(len(per))), default=0.0)
        assert abs(mine - v) < 2e-6, n


@pytest.mark.xfail(
    strict=True,
    reason="V1-09: F24 (grants to States) is listed as internal to GOV, but its R2k "
    "capital-grant term (K_GSTA <- K_GCEN) lies inside SI (PLAN s.3.7.3 rule 1)",
)
def test_ts_internal_lists_one_node():
    mt = to_map(TSN)
    bad = []
    for node, fl in jload("ts/view.json")["internal"].items():
        for fid in fl:
            pairs = {(mt[k[1]], mt[k[0]]) for k in ts_entries()[fid][0]}
            if pairs != {(node, node)}:
                bad.append((node, fid, sorted(pairs)))
    assert not bad, bad


# ---------------------------------------------------------------------------------------------------------------
# 7. Story figures (PLAN s.3.8), evaluated independently
# ---------------------------------------------------------------------------------------------------------------
def _sel_accounts(sel, cur=None) -> set[str]:
    if sel is None:
        return set()
    if isinstance(sel, str):
        sel = [sel]
    out: set[str] = set()
    hj = {n["id"]: n["accounts"] for n in jload("hierarchy.json")["nodes"]}
    for x in sel:
        if x == "@ALL":
            out |= {a["code"] for a in accounts_yaml()}
        elif x.startswith("@"):
            out |= set(groups_yaml()[x[1:]])
        elif x.startswith("node:"):
            out |= set(hj[x[5:]])
        elif x == "$":
            out.add(cur)
        else:
            out.add(x)
    return out


def _lesser(a: str, b: str) -> str:
    return ORD[max(ORD.index(a), ORD.index(b))]


def _ent_fig(keys: set, coefs: dict) -> dict:
    vals = {ekey(e): e["value"] for e in entries()}
    comp, head = composition(keys)
    fl: set = set()
    for e in entries():
        if ekey(e) in keys:
            fl |= entry_flags(e)
    c = cover(keys)
    return dict(value=sum(coefs[k] * vals[k] for k in keys), split=head, total=c[0] if c else None, flags=fl, comp=comp)


def _story_eval(spec: dict, figs: dict) -> dict:
    k = spec.get("kind")
    if "ref" in spec and not k:
        return figs[spec["ref"]]
    if "gdp" in spec:
        v = ts_row("M01", spec["gdp"])[0]
        return dict(value=v, split="official", total="official", flags=set(), comp=None)
    if k in ("sam_sum", "entries_sum"):
        keys: set = set()
        coefs: dict = {}
        for t in spec["terms"]:
            R = _sel_accounts(t["rows"]) - _sel_accounts(t.get("not_rows"))
            C = _sel_accounts(t["cols"]) - _sel_accounts(t.get("not_cols"))
            for e in entries():
                if e["row"] not in R or e["col"] not in C:
                    continue
                if k == "entries_sum" and (
                    ("refs" in t and e["ref"] not in t["refs"])
                    or ("not_refs" in t and e["ref"] in t["not_refs"])
                    or ("components" in t and e["component"] not in t["components"])
                    or ("not_components" in t and e["component"] in t["not_components"])
                ):
                    continue
                keys.add(ekey(e))
                coefs[ekey(e)] = t.get("coef", 1)
        assert keys, spec
        return _ent_fig(keys, coefs)
    if k in ("satellite_sum", "satellite_share"):
        b, n = spec["table"].split("/")
        path = SAM / "blocks" / f"{b}_satellites" / f"{n}.parquet"

        def ssum(w):
            cond = " and ".join(f"{c} = '{v}'" for c, v in w.items())
            return q(f"select sum(value) from '{path}' where {cond}")[0][0]

        if k == "satellite_sum":
            return dict(value=ssum(spec["where"]), split="estimated", total=None, flags=set(), comp=None)
        t = _story_eval(spec["total"], figs)
        return dict(
            value=t["value"] * ssum(spec["share_of"]) / ssum(spec["within"]),
            split="estimated",
            total=None,
            flags=set(t["flags"]),
            comp=None,
        )
    if k == "ts_value":
        v, b, st, *_ = ts_row(spec["flow"], spec["period"])
        if spec["measure"] == "share":
            ds = q(f"select display_sign from '{TSD}/top_flows_definitions.parquet' where flow_id='{spec['flow']}'")[0][
                0
            ]
            b = b or ("2022-23" if spec["period"] >= "2022-23" else "2011-12")
            g = q(
                f"select value from '{TF}' where flow_id='M01' and period='{spec['period']}' "
                f"and variant='published' and base_year='{b}'"
            )[0][0]
            v = v * ds / g
        return dict(value=v, split=st, total=st, flags=set(), comp=None)
    if k == "prorata_sum":
        cv = defaultdict(float)
        for e in entries():
            cv[(e["row"], e["col"])] += e["value"]
        tot = 0.0
        for a in _sel_accounts(spec["over"]):

            def cs(sel, a=a):
                R = _sel_accounts(sel.get("rows", ["@ALL"]), a)
                C = _sel_accounts(sel.get("cols", ["@ALL"]), a)
                return sum(v for (r, c), v in cv.items() if r in R and c in C)

            d = cs(spec["den"])
            if d:
                tot += cs(spec["base"]) * cs(spec["num"]) / d
        return dict(value=tot, split="estimated", total=None, flags=set(), comp=None)
    if k == "sum":
        parts = [_story_eval(t, figs) for t in spec["terms"]]
        v = sum(t.get("coef", 1) * p["value"] for t, p in zip(spec["terms"], parts))
    elif k == "difference":
        parts = [_story_eval(spec["a"], figs), _story_eval(spec["b"], figs)]
        v = parts[0]["value"] - parts[1]["value"]
    elif k == "ratio":
        parts = [_story_eval(spec["num"], figs), _story_eval(spec["den"], figs)]
        v = parts[0]["value"] / parts[1]["value"]
    elif k == "per100":
        # round-2 rule (V1-06, adopted by the integrator in pipeline/export/stories.py and the module docstring):
        # a share is labelled by its part alone (split, total, flags, composition); the whole's label is in the
        # method text. This is the rule summary.json's headline parts follow, so the two places agree.
        p, w = _story_eval(spec["part"], figs), _story_eval(spec["whole"], figs)
        return dict(
            value=100 * p["value"] / w["value"],
            split=p["split"],
            total=p["total"],
            flags=set(p["flags"]),
            comp=p["comp"],
            whole=w,
        )
    else:
        raise ValueError(k)
    sp = parts[0]["split"]
    for p in parts[1:]:
        sp = _lesser(sp, p["split"])
    tl = None
    if all(p["total"] for p in parts):
        tl = "official" if all(p["total"] == "official" for p in parts) else "derived"
    return dict(value=v, split=sp, total=tl, flags=set().union(*[p["flags"] for p in parts]), comp=None)


def _deps(spec) -> list[str]:
    out: list[str] = []

    def walk(s):
        if isinstance(s, dict):
            if "ref" in s and len(s) == 1:
                out.append(s["ref"])
            for v in s.values():
                walk(v)
        elif isinstance(s, list):
            for v in s:
                walk(v)

    walk({k: v for k, v in spec.items() if k != "check_equals"})
    return out


@cache
def story_values() -> dict[str, dict[str, dict]]:
    out = {}
    for f in sorted(glob.glob(str(ROOT / "pipeline" / "export" / "stories" / "*.yaml"))):
        y = yaml.safe_load(Path(f).read_text())
        figs: dict = {}
        pending = dict(y["figures"])
        while pending:
            for fid, spec in list(pending.items()):
                if all(d in figs for d in _deps(spec)):
                    figs[fid] = _story_eval(spec, figs)
                    figs[fid]["unit"] = spec["unit"]
                    del pending[fid]
        out[y["slug"]] = figs
    return out


@pytest.mark.parametrize("slug", ["gst-rupee", "remittance-dubai", "deficit-funding"])
def test_story_figures(slug):
    figs = story_values()[slug]
    y = yaml.safe_load((ROOT / "pipeline" / "export" / "stories" / f"{slug}.yaml").read_text())
    j = jload(f"stories/{slug}.json")
    assert set(j["figures"]) == set(figs)
    bad = []
    for fid, m in figs.items():
        x = j["figures"][fid]
        tol = 0.011 if m["unit"] == "inr" else 1.5e-6 if m["unit"] in ("pct_gdp", "pct") else 1e-5
        if abs(x["value"] - m["value"]) > tol:
            bad.append(("value", fid, x["value"], m["value"]))
        if (x["split"], x["total"]) != (m["split"], m["total"]):
            bad.append(("label", fid, x["split"], x["total"], m["split"], m["total"]))
        if set(x["flags"]) != m["flags"]:
            bad.append(("flags", fid))
        if m["comp"] and any(
            abs(x["composition"][c[0] if c != "balancing_set" else "b"] - m["comp"][c]) > 2e-4 for c in ORD
        ):
            bad.append(("composition", fid))
        ce = y["figures"][fid].get("check_equals")
        if ce:
            assert abs(m["value"] - figs[ce["ref"]]["value"]) <= ce["tol"], fid
    assert not bad, bad[:10]


def test_story_identities():
    d = story_values()["deficit-funding"]
    g = story_values()["gst-rupee"]
    r = story_values()["remittance-dubai"]
    # net borrowing = liabilities - assets = -(net lending) (PLAN s.4.9; V1-04 fixed: the story now shows nb_*)
    assert abs(d["nb_cen"]["value"] - (d["liab_cen"]["value"] - d["assets_cen"]["value"])) < 0.01
    assert abs(d["nb_sta"]["value"] - (d["liab_sta"]["value"] - d["assets_sta"]["value"])) < 0.01
    assert abs(d["nb_gg"]["value"] - d["nb_cen"]["value"] - d["nb_sta"]["value"]) < 0.01
    # satellite_share parts add up to the balanced totals of each tax account
    for t in ("cgst", "sgst", "cess"):
        parts = sum(g[f"till_{u}_{t}"]["value"] for u in ("pfce", "ic", "gfcf", "gfce", "valu"))
        assert abs(parts - g[f"{t}_total"]["value"]) < 0.01, t
    assert abs(g["gst_total"]["value"] - g["gst_commodity_side"]["value"]) < 0.01
    # the seven household outlays exhaust the column; GG outlay shares exhaust the 100
    assert abs(r["hh_outlays"]["value"] - r["hh_outlays_all"]["value"]) < 0.01
    assert (
        abs(
            sum(
                g[f"gg_{k}_per100"]["value"]
                for k in ("goods_services", "interest", "pensions", "cash_transfers", "corp_transfers", "capital")
            )
            - 100
        )
        < 1e-6
    )
    # orientation figures quoted in PLAN s.4.9
    assert round(g["cgst_total"]["value"] / 1e5, 2) == 8.62 and round(g["sgst_total"]["value"] / 1e5, 2) == 8.29
    assert round(g["cess_total"]["value"] / 1e5, 2) == 1.49 and round(g["utgst"]["value"]) == 5772
    assert round(g["comp_grants"]["value"]) == 44946 and round(g["cess_loan_transfer"]["value"]) == 78104
    assert round(g["gg_current"]["value"] / 1e5, 2) == 57.26 and round(g["gg_capital"]["value"] / 1e5, 2) == 14.14
    assert round(g["gg_fin_assets"]["value"] / 1e5, 2) == 5.91
    assert round(r["remit_total"]["value"] / 1e5, 2) == 9.83 and round(r["uae_remit"]["value"]) == 189139
    assert round(d["nb_cen"]["value"] / 1e5, 2) == 11.47 and round(d["nb_sta"]["value"] / 1e5, 2) == 5.84
    assert round(d["nb_gg"]["value"] / 1e5, 2) == 17.31
    assert round(d["liab_cen_gsec"]["value"] / 1e5, 2) == 11.71 and round(d["liab_sta_gsec"]["value"] / 1e5, 2) == 6.65


# ---------------------------------------------------------------------------------------------------------------
# 8. The built site (web/out/), static HTML
# ---------------------------------------------------------------------------------------------------------------
NUM = re.compile(r'data-num-value="([^"]+)" data-num-fmt="([^"]+)">([^<]*)<')


def _built(rel: str) -> str:
    p = OUT / rel
    if not p.exists():
        pytest.skip(f"web/out not built ({rel})")
    return p.read_text()


def _text(h: str) -> str:
    h = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)))


def test_methodology_figures():
    """summary.methodology and the counts the methodology page binds, recomputed here."""
    s = jload("summary.json")
    m = s["methodology"]
    ents = entries()
    jm = judgement_members()
    assert m["judgement_band_entries"]["value"] == len(jm) == 97
    assert abs(m["judgement_band_abs"]["value"] - sum(abs(e["value"]) for e in ents if ekey(e) in jm)) < 0.01
    ob = [e for e in ents if e["prov"] in old_base_ids()]
    assert m["old_base_entries"]["value"] == len(ob)
    assert abs(m["old_base_abs"]["value"] - sum(abs(e["value"]) for e in ob)) < 0.01
    sam_ids = [p for p, v in prov_graph().items() if v["kind"] == "sam" and not is_assumption(p)]
    assert m["assumption_records"]["value"] == sum(depends_on_assumption(p) for p in sam_ids)
    assert m["constraints"]["value"] == len(constraints())
    assert m["constraints_binding"]["value"] == sum(1 for c in constraints().values() if c[-1])
    ev, cv = verdicts()
    assert m["explain_entries"]["value"] == len(ev) and m["explain_cells"]["value"] == len(cv)
    links, _ = aggregate(to_map(L0))
    assert abs(m["hh_factor_income"]["value"] - links["FACT--HH"]) < 0.01
    disc = {r: v for r, c, v in cells() if c == "X_DISC"}
    assert abs(m["disc_d2"]["value"] - disc["R_ROW"]) < 0.01
    assert abs(m["disc_d1"]["value"] - links["HH--DISC"]) < 0.01
    assert abs(s["sam"]["grand_total"] - sum(v for _, _, v in cells())) < 0.1
    # round 2 (V2-02, V5-03): economic methodology values now carry labels; recomputed with this file's composition
    # and exact-cover pin search, and the whole of D3 equals the NAS derived S-I errors and omissions for 2023-24
    sets = {
        "hh_factor_income": [ekey(e) for e in ents if e["col"] in L0["FACT"] and e["row"] in L0["HH"]],
        "disc_d1": [ekey(e) for e in ents if e["ref"] == "D1"],
        "disc_d2": [ekey(e) for e in ents if e["ref"] == "D2"],
        "disc_d3": [ekey(e) for e in ents if e["ref"] == "D3"],
        "disc_d3_valuables": [ekey(e) for e in ents if e["ref"] == "D3" and e["component"] == "unsectored_valuables"],
        "disc_d3_si_errors": [ekey(e) for e in ents if e["ref"] == "D3" and e["component"] == "si_errors"],
        "judgement_band_abs": [ekey(e) for e in ents if ekey(e) in jm],
        "old_base_abs": [ekey(e) for e in ents if e["prov"] in old_base_ids()],
    }
    val = {ekey(e): e["value"] for e in ents}
    for key, ks in sets.items():
        c = cover(frozenset(ks))
        _, split = composition(ks)
        x = m[key]
        assert (x["split_label"], x["total_label"], sorted(x["pins"])) == (
            split,
            c[0] if c else None,
            sorted(c[1]) if c else [],
        ), key
        want = sum(abs(val[k]) for k in ks) if key.endswith("_abs") else sum(val[k] for k in ks)
        assert abs(x["value"] - want) < 0.01, key
    nas = q(
        f"select value from '{ROOT}/data/clean/mospi_nas_2026/mospi_nas_2026_derived_residuals.parquet' "
        "where series_id = 'derived.si_errors_omissions.current' and period = '2023-24'"
    )[0][0]
    assert abs(m["disc_d3"]["value"] - nas) < 0.01
    fl = dict(
        q(
            f"select flags, count(*) from '{TF}' where flags in ('base_change','concept_break','segment_join') "
            f"group by all"
        )
    )
    assert (m["ts_base_changes"]["value"], m["ts_segment_joins"]["value"], m["ts_concept_breaks"]["value"]) == (
        fl["base_change"],
        fl["segment_join"],
        fl["concept_break"],
    )


def test_flow_pages_values_and_format():
    if not (OUT / "flow").exists():
        pytest.skip("web/out not built")
    full, _ = aggregate(to_map(L0))
    simple, _ = aggregate(to_map(SIMPLE))
    gdp = jload("summary.json")["gdp"]["value"]
    pages = sorted(p.name for p in (OUT / "flow").iterdir())
    assert len(pages) == 80
    bad = []
    for fid in pages:
        h = (OUT / "flow" / fid / "index.html").read_text()
        nums = NUM.findall(h)
        v = float(nums[0][0])
        want = full.get(fid, simple.get(fid))
        clash = fid in full and fid in simple and abs(full[fid] - simple[fid]) > 0.01
        if want is None or abs(v - want) > 0.011 or clash:
            bad.append(("value", fid, v, want))
        share = [float(n[0]) for n in nums if n[1] == "pct_gdp"][0]
        if abs(share - v / gdp) > 1e-6:
            bad.append(("share", fid))
        for val, kind, text in nums:
            if html.unescape(text).strip() != fmt(float(val), kind):
                bad.append(("format", fid, val, kind, text))
    assert not bad, bad[:10]


def test_methodology_pages_bound_figures():
    """Round 2: every <DataFig> on the methodology pages shows its summary.json value with this file's formatter, and
    a labelled methodology item (V2-02, V5-03) is followed by a badge with the item's own split and total labels."""
    pages = glob.glob(str(OUT / "methodology" / "**" / "index.html"), recursive=True)
    if not pages:
        pytest.skip("web/out not built")
    summ = jload("summary.json")
    bad, n = [], 0
    for f in pages:
        h = re.sub(r"<script.*?</script>", "", Path(f).read_text(), flags=re.S)
        for mm in re.finditer(r'data-fig-path="([^"]+)" data-num-value="([^"]+)" data-num-fmt="([^"]+)">([^<]*)<', h):
            path, val, kind, text = mm.groups()
            n += 1
            x = summ
            for part in path.split("."):
                x = x[part]
            want = x["value"] if isinstance(x, dict) else x
            if abs(float(val) - want) > 1e-9 * max(1, abs(want)) or html.unescape(text).strip() != fmt(want, kind):
                bad.append((path, val, text))
            if isinstance(x, dict) and x.get("split_label"):
                rest = h[mm.end() :]
                # the first badge after the figure, unless another figure comes first
                nxt = re.search(r'data-status-split="[^"]*"|data-fig-path', rest)
                head = rest[: nxt.end()] if nxt and nxt.group(0) != "data-fig-path" else ""
                tag = head[head.rfind("<") :]
                sp = re.search(r'data-status-split="([^"]*)"', tag)
                tt = re.search(r'data-status-total="([^"]*)"', tag)
                got = (sp.group(1) if sp else None, (tt.group(1) or None) if tt else None)
                if got != (x["split_label"], x["total_label"]):
                    bad.append((path, "badge", got, x["split_label"], x["total_label"]))
    assert n > 50 and not bad, (n, bad)


def test_flow_pages_entry_moves():
    """V1-01 on the static flow pages: every "before → after (x%)" percentage is the move, as a fraction of the
    prior, of one of that link's own entries (from the parquet), so a 100x unit slip cannot pass."""
    if not (OUT / "flow").exists():
        pytest.skip("web/out not built")
    ev = {ekey(e): e for e in entries()}
    full, _ = aggregate(to_map(L0))
    bad, n = [], 0
    for page in sorted(p.name for p in (OUT / "flow").iterdir()):
        m = to_map(L0) if page in full else to_map(SIMPLE)
        p_, r_ = page.split("~")[0].split("--")
        keys = link_entries(page, {a for a, x in m.items() if x == p_}, {a for a, x in m.items() if x == r_})
        moves = [(ev[k]["value"] - ev[k]["prior"]) / abs(ev[k]["prior"]) for k in keys if ev[k]["prior"]]
        h = (OUT / "flow" / page / "index.html").read_text()
        for val, kind, _ in NUM.findall(h):
            if kind == "pct":
                n += 1
                if not any(abs(float(val) - w) <= 1e-4 for w in moves):
                    bad.append((page, val))
    assert n > 300 and not bad, (n, bad[:10])


def test_story_pages_static():
    for slug, figs in story_values().items():
        h = _built(f"story/{slug}/index.html")
        found = re.findall(r'data-fig-id="([^"]+)"[^>]*>(.*?)</span>', h)
        assert found, slug
        for fid, inner in found:
            text = html.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
            assert text == fmt(figs[fid]["value"], figs[fid]["unit"]), (slug, fid, text)


def test_series_pages_values_and_format():
    """Every number on the 69 series pages is a main/linked/alt value x display_sign (or the SAM check value), or
    its share of GDP; every text equals this file's formatter."""
    if not (OUT / "series").exists():
        pytest.skip("web/out not built")
    s = jload("ts/series.json")
    gdp = jload("summary.json")["gdp"]["value"]
    bad = []
    for f in s["flows"]:
        h = (OUT / "series" / f["id"] / "index.html").read_text()
        ds = f["display_sign"]
        arrays = [f["main"]] + ([f["linked"]] if f["linked"] else []) + [a["arrays"] for a in f["alts"]]
        inr = {round(v * ds, 2) for a in arrays for v in a["v"] if v is not None}
        shares = {round(v, 6) for a in arrays for v in a["share"] if v is not None}
        if f["check"]["sam_value"] is not None:  # the SAM point is drawn with the line's sign (V1-02)
            inr.add(round(f["check"]["sam_value"] * ds, 2))
            shares.add(round(f["check"]["sam_value"] * ds / gdp, 6))
        for val, kind, text in NUM.findall(h):
            v = float(val)
            if html.unescape(text).strip() != fmt(v, kind):
                bad.append(("format", f["id"], val, kind, text))
            if kind == "inr" and not any(abs(v - x) < 0.011 for x in inr):
                bad.append(("inr", f["id"], v))
            if kind == "pct_gdp" and not any(abs(v - x) < 2e-6 for x in shares):
                bad.append(("share", f["id"], v))
    assert not bad, bad[:10]


def test_playwright_observed_numbers():
    """Every [data-num-value] the V1 Playwright run saw in a panel or story reads this file's fmt(value)."""
    files = glob.glob(str(WEB / "test-results-v1" / "v1_observed*.json"))
    if not files:
        pytest.skip("run: npx playwright test -c tests/verify/playwright.v1.config.ts (in web/)")
    bad = []
    n = 0
    for f in files:
        for name, d in json.loads(Path(f).read_text()).items():
            nums = (
                d["got"]["nums"]
                if isinstance(d, dict)
                else [dict(value=x["value"], fmt=None, text=x["text"]) for x in d]
            )
            for x in nums:
                kind = (
                    x["fmt"]
                    or story_expect()[name.split(" ", 1)[1]][
                        next(y["id"] for y in d if y["text"] == x["text"] and y["value"] == x["value"])
                    ]["unit"]
                )
                n += 1
                if x["text"] != fmt(x["value"], kind):
                    bad.append((name, x))
    assert n > 300 and not bad, (n, bad[:10])


def test_trend_sam_point_uses_display_sign():
    """V1-02 (fixed in round 2): on every series page with a SAM check and a chart, the SAM 2023-24 point is drawn
    and captioned with the line's sign (sam_value x display_sign); short runs shown as values have no point."""
    s = jload("ts/series.json")
    gdp = jload("summary.json")["gdp"]["value"]
    bad, n = [], 0
    for f in s["flows"]:
        t = _text(_built(f"series/{f['id']}/index.html"))
        full = re.findall(r"SAM 2023-24 ?: (\S+% of GDP)", t)
        short = re.findall(r"SAM 2023-24 ?: (\S+)%(?! of)", t)
        c = f["check"]["sam_value"]
        if c is None:
            if full or short:
                bad.append((f["id"], "point without a check"))
            continue
        sv = c * f["display_sign"]
        if sum(v is not None for v in f["main"]["v"]) < 3:  # fewer than 3 points: listed as values, no chart
            if full or short:
                bad.append((f["id"], "point on a values list"))
            continue
        n += 1
        if set(full) != {fmt(sv / gdp, "pct_gdp")}:
            bad.append((f["id"], full, fmt(sv / gdp, "pct_gdp")))
        bad += [(f["id"], "sign", x) for x in short if x.startswith(MINUS) != (sv < 0)]
    assert n >= 60 and not bad, (n, bad)
    for fid in ("F13", "F30"):  # the two subsidy series the finding named
        t = _text(_built(f"series/{fid}/index.html"))
        assert not re.search(r"SAM 2023-24 ?: " + MINUS, t), fid


FIRST_CARD = ("Each ₹100 of household income", "Follow the money")


def test_first_screen_total_labels():
    """V1-03 (fixed in round 2): each household part on the first screen carries the total label of its own entry set
    (this file's exact-cover pin search), and the split label of its composition."""
    t = _text(_built("index.html"))
    i = t.find(FIRST_CARD[0])
    assert i >= 0, "first-screen household card title not found"
    head = t[i : t.find(FIRST_CARD[1], i)]
    hh = set(L0["HH"])
    m = to_map(L0)
    keymap = {"PRDS": "consumption", "SI": "saving", "TAX": "taxes", "FC": "financial_services_and_interest",
              "ROW": "transfers_abroad", "CEN": "to_government", "STA": "to_government",
              "DISC": "unallocated_residual"}  # fmt: skip
    keys = defaultdict(set)
    for e in entries():
        if e["col"] in hh:
            keys[keymap[m[e["row"]]]].add(ekey(e))
    words = {
        "official": "Official",
        "derived": "Derived",
        "estimated": "Estimated",
        "balancing_set": "Set by balancing",
    }
    parts = {p["key"]: p for p in jload("summary.json")["headline"]["hh_outlays"]["parts"]}
    bad = []
    for k, ks in keys.items():
        c = cover(ks)
        _, split = composition(ks)
        p = parts[k]
        if (p["total_label"], sorted(p["pins"]), p["split_label"]) != ((c[0], sorted(c[1])) if c else (None, [])) + (
            split,
        ):
            bad.append(("summary", k, p["total_label"], p["pins"], p["split_label"], c, split))
        txt = fmt(p["per100"], "per100")
        badge = (
            f"{words[c[0]]} total · split {words[split].lower()}"
            if c and c[0] != split
            else f"{words[c[0]]} total"
            if c
            else words[split]
        )
        if f"{txt} {badge}" not in head:
            bad.append(("page", k, f"{txt} {badge}"))
    assert keys["consumption"] and parts["saving"]["total_label"] == "official", parts["saving"]
    assert not bad, (bad, head)


def test_share_labels_agree_between_first_screen_and_story():
    """V1-06 (fixed in round 2): a per-100 share is labelled by its part, so the remittance story's household shares
    carry the same labels as the first-screen card, and the deficit story's household G-sec share is official."""
    parts = {p["key"]: p for p in jload("summary.json")["headline"]["hh_outlays"]["parts"]}
    r = jload("stories/remittance-dubai.json")["figures"]
    pairs = {"consumption": "hh_consumption_per100", "saving": "hh_saving_per100", "taxes": "hh_taxes_per100",
             "financial_services_and_interest": "hh_finance_per100", "transfers_abroad": "hh_abroad_per100",
             "to_government": "hh_to_gov_per100", "unallocated_residual": "hh_residual_per100"}  # fmt: skip
    bad = []
    for k, fid in pairs.items():
        x = r[fid]
        if abs(x["value"] - parts[k]["per100"]) > 1e-5 or (x["split"], x["total"]) != (
            parts[k]["split_label"],
            parts[k]["total_label"],
        ):
            bad.append((k, x["value"], x["split"], x["total"], parts[k]))
        if "whole is" not in x["method"]:
            bad.append((k, "method does not state the whole's label"))
    d = jload("stories/deficit-funding.json")["figures"]
    assert (d["gsec_hh_per100"]["split"], d["gsec_hh"]["split"]) == ("official", "official")
    assert not bad, bad


def test_published_single_figures_not_called_unpinned():
    """V1-08 (fixed in round 2): no single published figure (GDP card, series page header) carries the
    'not held to a single published figure' line; the line remains only on sums of entries without a pin."""
    noto = "not held to a single published figure"
    t = _text(_built("index.html"))
    gdp = t[t.find("India's GDP in 2023-24") : t.find(FIRST_CARD[0])]
    assert "Official total" in gdp and noto not in gdp, gdp
    for f in jload("ts/series.json")["flows"]:
        s = _text(_built(f"series/{f['id']}/index.html"))
        assert noto not in s, f["id"]


def test_deficit_story_net_borrowing_sign():
    """V1-04 (fixed in round 2): the story shows net borrowing as positive amounts for both governments."""
    t = _text(_built("story/deficit-funding/index.html"))
    assert "Net borrowing by the Centre was −" not in t and "Net borrowing by the Centre came to −" not in t
    d = story_values()["deficit-funding"]
    row = (
        f"Net borrowing (national accounts), 2023-24 Item Value and label The Centre {fmt(d['nb_cen']['value'], 'inr')}"
    )
    assert d["nb_cen"]["value"] > 0 and d["nb_sta"]["value"] > 0 and row in t, t[t.find("Net borrowing (") :][:300]
    assert f"Net borrowing by the Centre came to {fmt(d['nb_cen_gdp']['value'], 'pct_gdp')}" in t


# ---------------------------------------------------------------------------------------------------------------
# 9. Expectations for the Playwright spec (web/tests/verify/v1_fidelity.spec.ts)
# ---------------------------------------------------------------------------------------------------------------
def panel_states() -> list[dict]:
    """30 flow-panel states chosen with seed 20261002, with values, shares, labels and display text expected
    from this file's own aggregation and formatter."""
    rng = random.Random(SEED)
    gdp = jload("summary.json")["gdp"]["value"]
    states: list[dict] = []

    def add(lid, preset, x, m):
        links, _ = aggregate(m)
        v = links[lid]
        p, r = lid.split("~")[0].split("--")
        pa = {a for a, n in m.items() if n == p}
        ra = {a for a, n in m.items() if n == r}
        keys = link_entries(lid, pa, ra)
        comp, head = composition(keys)
        c = cover(keys)
        ev = {ekey(e): e for e in entries()}
        moves = sorted(
            round((ev[k]["value"] - ev[k]["prior"]) / abs(ev[k]["prior"]), 6)
            for k in keys
            if ev[k]["prior"] and ev[k]["value"] != ev[k]["prior"]
        )
        states.append(
            dict(
                kind="link",
                id=lid,
                preset=preset,
                x=x,
                value=round(v, 2),
                share=v / gdp,
                value_text=fmt(v, "inr"),
                share_text=fmt(v / gdp, "pct_gdp"),
                split=head,
                total=c[0] if c else "",
                pins=c[1] if c else [],
                moves=moves,  # each entry's (value - prior) / |prior| (V1-01: the panel's "before → after" list)
            )
        )

    full, _ = aggregate(to_map(L0))
    for lid in rng.sample(sorted(full), 8):
        add(lid, "full", [], to_map(L0))
    simple, _ = aggregate(to_map(SIMPLE))
    for lid in rng.sample(sorted(simple), 6):
        add(lid, "simple", [], to_map(SIMPLE))
    exp_all = [g for g in L0 if len(CHILDREN[g]) > 1]
    for _ in range(8):
        xs = sorted(rng.sample(exp_all, 2), key=ORDER.index)
        m = visible("full", xs)
        links, _ = aggregate(m)
        kids = {c for g in xs for c in CHILDREN[g]}
        cand = sorted(k for k in links if set(k.split("~")[0].split("--")) & kids)
        add(rng.choice(cand), "full", xs, m)
    for _ in range(5):
        g1, g2 = rng.sample(["HH", "FACT", "TAX", "SI", "FINM", "FC", "NFC"], 2)
        xs = [g1, g2]
        for g in (g1, g2):
            subs = [c for c in CHILDREN[g] if c in L1]
            if subs:
                xs.append(rng.choice(subs))
        xs = sorted(xs, key=lambda n: (ORDER.index(n.split(".")[0]), n.count(".")))
        m = visible("full", xs)
        links, _ = aggregate(m)
        cand = sorted(k for k in links if all("_" in end for end in k.split("~")[0].split("--")))
        if cand:
            add(rng.choice(cand), "full", xs, m)
    for nid, preset, x in (("HH", "simple", []), ("SI", "simple", []), ("SI", "full", []), ("HH.RUR", "full", ["HH"])):
        m = visible(preset, x)
        inn, _ = heights(aggregate(m)[0])
        states.append(
            dict(
                kind="node",
                id=nid,
                preset=preset,
                x=x,
                value=round(inn[nid], 2),
                share=inn[nid] / gdp,
                value_text=fmt(inn[nid], "inr"),
                share_text=fmt(inn[nid] / gdp, "pct_gdp"),
            )
        )
    return states[:30] if len(states) >= 30 else states


def node_states() -> list[dict]:
    """Every top-level node in both presets (V1-05 regression guard): the panel's value is the drawn node's height."""
    gdp = jload("summary.json")["gdp"]["value"]
    out = []
    for preset in ("simple", "full"):
        m = visible(preset, [])
        inn, _ = heights(aggregate(m)[0])
        for nid in sorted(set(m.values())):
            v = inn[nid]
            out.append(dict(kind="node", id=nid, preset=preset, x=[], value=round(v, 2), share=v / gdp,
                            value_text=fmt(v, "inr"), share_text=fmt(v / gdp, "pct_gdp")))  # fmt: skip
    return out


def story_expect() -> dict:
    out = {}
    for slug, figs in story_values().items():
        out[slug] = {
            fid: dict(
                value=f["value"],
                unit=f["unit"],
                text=fmt(f["value"], f["unit"]),
                split=f["split"],
                total=f["total"] or "",
            )
            for fid, f in figs.items()
        }
    return out


def _write_expectations():
    d = WEB / "tests" / "verify"
    d.mkdir(parents=True, exist_ok=True)
    st = panel_states()
    (d / "panel_states.json").write_text(
        json.dumps({"seed": SEED, "states": st, "nodes": node_states()}, indent=1, ensure_ascii=False) + "\n"
    )
    (d / "story_expect.json").write_text(json.dumps(story_expect(), indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {len(st)} panel states and story expectations to {d}")


def test_expectation_files_current():
    d = WEB / "tests" / "verify"
    if not (d / "panel_states.json").exists():
        pytest.skip("run this file as a script to write the Playwright expectations")

    def same(a, b):
        if isinstance(a, float) or isinstance(b, float):
            return abs(a - b) <= 1e-9 * max(1.0, abs(a))
        if isinstance(a, dict):
            return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
        if isinstance(a, list):
            return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
        return a == b

    ps = json.loads((d / "panel_states.json").read_text())
    assert same(ps["states"], json.loads(json.dumps(panel_states(), ensure_ascii=False)))
    assert same(ps["nodes"], json.loads(json.dumps(node_states(), ensure_ascii=False)))
    assert same(
        json.loads((d / "story_expect.json").read_text()), json.loads(json.dumps(story_expect(), ensure_ascii=False))
    )


if __name__ == "__main__":
    _write_expectations()
