"""Build the top-flows time series (DESIGN_BRIEF s.8, DECISIONS D2-18; plan docs/phase2/plans/timeseries.md).

A post-SAM step with its own context and provenance (no gap-map ref). It reads:
- clean data (data/clean/<unit>/<dataset>.parquet and the clean provenance records), never data/raw;
- pipeline/timeseries/flows.yaml (the flow definitions) and explanations.yaml (registered 2023-24 bridges);
- the SAM for the 2023-24 check only: data/sam/2023-24/sam_entries_balanced.parquet when it exists, and for
  the prior sam_entries_prior.parquet (or, before a full `sam` run, the built blocks' entries).

It writes data/timeseries/ (deterministic, through pipeline/core/io):
- top_flows.parquet            one row per (flow_id, period, base_year, variant): the value, its segment,
                               datasets, series, estimate stage, vintage, status, flags and prov_id
- top_flows_definitions.parquet one row per flow: SAM terms (JSON), segments (JSON), check class, link policy
                               and the two overlap ratios computed from the rows
- top_flows_coverage.parquet   flow x FY of the main (published) variant: bases, segments, statuses
- top_flows_sam_check.parquet  2023-24: time-series value vs the SAM definition (prior and balanced), with
                               the verdict and the guards (refs found in the flow's cell blocks but not listed,
                               selectors that match nothing, entries matched twice)
- _provenance.parquet          one record per (flow, segment) and per linked flow, Phase 1 provenance schema,
                               ingest_unit 'timeseries'; inputs are the clean prov_ids used

Rules (plan s.2.0): FY periods only; budget RE/BE rows never used; the latest vintage per (series, period);
nothing after the cutoff FY; old (2011-12) and new (2022-23) NAS bases kept as separate rows (the break at
2022-23 stays visible); a splice exists only as the labelled `linked_2022_23` variant (status derived, the
ratio computed from the rows, rules of plan s.2.5 evaluated in code for every flow); nothing is estimated. A
segment must be complete: a missing value inside its declared period range is an error (no silent gaps). A
segment's base_year must equal the base_year of every clean record it reads (RBI HBS Table 12 before 2011-12
splices earlier bases and carries none); a switch of base without an overlap year is flagged `base_change`.
Every name in flows.yaml must be a YAML string (an unquoted NO is read as the boolean False and rejected).
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandera.errors as pa_errors
import polars as pl

from pipeline.core import io
from pipeline.core.manifest import repo_lock, write_manifest
from pipeline.core.paths import Layout
from pipeline.core.registry import source_ids
from pipeline.core.schema import PROV_DTYPES, PROV_ID_RE, PROV_SCHEMA
from pipeline.core.units import vintage_end
from pipeline.sam import spec as sam_spec
from pipeline.sam.accounts import Accounts, gap_map
from pipeline.sam.framework import CleanIndex, SamPaths, select_vintage

TS_CODE_DIR = Path(__file__).resolve().parent
FLOWS_YAML = TS_CODE_DIR / "flows.yaml"
EXPLANATIONS_YAML = TS_CODE_DIR / "explanations.yaml"
INGEST_UNIT = "timeseries"
YEAR = sam_spec.YEAR  # "2023-24": the SAM reference year the check compares
OLD_BASE, NEW_BASE = "2011-12", "2022-23"
BASE_YEARS = (OLD_BASE, NEW_BASE, None)
MAIN_VARIANT = "published"
LINK_VARIANT = "linked_2022_23"
VARIANTS = (MAIN_VARIANT, LINK_VARIANT, "proxy_total_portfolio", "fc16_definition")
TIERS = ("core", "memo")
CHECK_CLASSES = ("A", "B", "C", "D", "none")
# NAS API old-base revision rounds, latest first (mospi_nas_2026-34, checked against NAS 2025 1.1 levels):
# the 'additional revision' of 2011-12..2013-14 is later than every other round of those years.
ROUNDS_LATEST = (
    "additional_revision",
    "final_estimates",
    "third_revised_estimates",
    "second_revised_estimates",
    "first_revised_estimates",
    "provisional_estimates",
    "second_advance_estimates",
    "first_advance_estimates",
)
# Estimate stages, most mature first; a row built from several clean rows carries the least mature one.
STAGE_ORDER = (
    "Audited",
    "Final",
    "Actuals",
    "Revised",
    "TRE",
    "SRE",
    "FRE",
    "Partially Revised",
    "PE",
    "Provisional",
    "Preliminary",
    "Unaudited",
    "SAE",
    "FAE",
    "AE",
    "QE",
    "n.a.",
)
# Class thresholds (plan s.7 T3). A: max(TOL_A, summed anchored allowances); B: max(TOL_A, tol_rel |TS|);
# C: max(TOL_C_ABS, TOL_C_REL |TS|); D: TOL_D. An explanation stays valid while the residual is within
# max(EXPLAIN_DRIFT_REL |explained|, EXPLAIN_DRIFT_ABS) of the one it explains (SAM_GUIDE s.12 rule).
TOL_A = 5.0
TOL_C_ABS = 500.0
TOL_C_REL = 0.01
TOL_D = 5.0
EXPLAIN_DRIFT_REL = sam_spec.EXPLAIN_DRIFT_REL
EXPLAIN_DRIFT_ABS = sam_spec.EXPLAIN_DRIFT_ABS

OUT_FILES = (
    "top_flows.parquet",
    "top_flows_definitions.parquet",
    "top_flows_coverage.parquet",
    "top_flows_sam_check.parquet",
    "_provenance.parquet",
)

ROW_DTYPES: dict[str, pl.DataType] = {
    "flow_id": pl.String(),
    "period": pl.String(),
    "period_type": pl.String(),
    "value": pl.Float64(),
    "unit": pl.String(),
    "price_basis": pl.String(),
    "base_year": pl.String(),
    "variant": pl.String(),
    "segment": pl.String(),
    "datasets": pl.String(),
    "series_ids": pl.String(),
    "estimate_stage": pl.String(),
    "vintage": pl.String(),
    "status": pl.String(),
    "flags": pl.String(),
    "prov_id": pl.String(),
    "note": pl.String(),
}
ROW_KEY = ("flow_id", "variant", "base_year", "period")
FLAGS = ("base_overlap", "segment_join", "base_change", "concept_break")
SEGMENT_CODE_RE = re.compile(r"^[A-Z][A-Z0-9]{1,3}$")  # NB, NO, NN, T12, ... (plan s.2.1)

DEF_DTYPES: dict[str, pl.DataType] = {
    "flow_id": pl.String(),
    "name": pl.String(),
    "group": pl.String(),
    "tier": pl.String(),
    "display_sign": pl.Int64(),
    "check_class": pl.String(),
    "tol_abs": pl.Float64(),
    "tol_rel": pl.Float64(),
    "sam_terms": pl.String(),
    "excluded_refs": pl.String(),
    "sam_note": pl.String(),
    "segments": pl.String(),
    "link_policy": pl.String(),
    "link_reason": pl.String(),
    "link_rules": pl.String(),
    "link_ratio_2022_23": pl.Float64(),
    "link_ratio_2023_24": pl.Float64(),
    "n_rows": pl.Int64(),
    "first_period": pl.String(),
    "last_period": pl.String(),
    "explanation": pl.String(),
    "breaks": pl.String(),
}

COVERAGE_DTYPES: dict[str, pl.DataType] = {
    "flow_id": pl.String(),
    "tier": pl.String(),
    "period": pl.String(),
    "n_rows": pl.Int64(),
    "base_years": pl.String(),
    "segments": pl.String(),
    "statuses": pl.String(),
}

CHECK_DTYPES: dict[str, pl.DataType] = {
    "flow_id": pl.String(),
    "check_class": pl.String(),
    "ts_value": pl.Float64(),
    "ts_segment": pl.String(),
    "ts_base_year": pl.String(),
    "ts_prov_id": pl.String(),
    "sam_prior": pl.Float64(),
    "sam_prior_source": pl.String(),
    "sam_balanced": pl.Float64(),
    "n_entries": pl.Int64(),
    "anchored_allowance": pl.Float64(),
    "diff": pl.Float64(),
    "rel_diff": pl.Float64(),
    "bridge": pl.Float64(),
    "residual": pl.Float64(),
    "tolerance": pl.Float64(),
    "explained_residual": pl.Float64(),
    "verdict": pl.String(),
    "unlisted_refs": pl.String(),
    "missing_selectors": pl.String(),
    "overlapping_entries": pl.Int64(),
    "explanation": pl.String(),
}
VERDICTS = ("pass", "explained", "fail", "unexplained", "pending_balancing", "no_check")


class TsError(RuntimeError):
    """The definitions or the data break the time-series contract. The message lists every problem."""


def ts_dir(layout: Layout) -> Path:
    """data/timeseries: next to data/clean and data/sam, so scratch and repro layouts move it with them."""
    return layout.clean.parent / "timeseries"


# ---------------------------------------------------------------------------------------------
# periods
# ---------------------------------------------------------------------------------------------


def fy(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def fy_start(period: str) -> int:
    if len(period) != 7 or period[4] != "-" or not (period[:4] + period[5:]).isdigit():
        raise TsError(f"not a fiscal year 'YYYY-YY': {period!r}")
    y = int(period[:4])
    if (y + 1) % 100 != int(period[5:]):
        raise TsError(f"not a fiscal year (years not consecutive): {period!r}")
    return y


def fy_range(a: str, b: str) -> list[str]:
    return [fy(y) for y in range(fy_start(a), fy_start(b) + 1)]


# ---------------------------------------------------------------------------------------------
# definitions
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Term:
    series: tuple[str, ...]  # one id, or the revision rounds of a template in precedence order
    coef: float
    lo: str | None  # the term applies only inside [lo, hi] (None = the segment's range)
    hi: str | None
    label: str  # the id, or the template
    template: str | None = None  # '...{round}...' for a NAS API revision-round term


@dataclass(frozen=True)
class Segment:
    code: str
    dataset: str
    base_year: str | None
    lo: str
    hi: str
    variant: str
    terms: tuple[Term, ...]
    status_override: str | None
    note: str | None


@dataclass(frozen=True)
class SamTerm:
    rows: tuple[str, ...]
    cols: tuple[str, ...]
    refs: tuple[str, ...]
    optional_refs: tuple[str, ...]  # refs of the definition that may have no entry (constraint-only refs, guards)
    components: tuple[str, ...] | None
    bop_functions: tuple[str, ...] | None
    coef: float
    spec: dict[str, Any]  # as written (tokens), for the definitions table
    exclude_components: tuple[str, ...] = ()  # components of the listed refs that are not part of the flow


@dataclass(frozen=True)
class Flow:
    flow_id: str
    name: str
    group: str
    tier: str
    display_sign: int
    check_class: str
    tol_abs: float | None
    tol_rel: float | None
    link_allowed: bool
    link_refused_reason: str | None
    sam_terms: tuple[SamTerm, ...]
    excluded_refs: tuple[str, ...]
    sam_note: str | None
    segments: tuple[Segment, ...]
    breaks: tuple[tuple[str, str], ...]  # (period, note): documented concept breaks inside a segment


@dataclass(frozen=True)
class Definitions:
    flows: tuple[Flow, ...]
    first_period: str
    last_period: str
    excluded_stages: tuple[str, ...]
    max_ratio_gap: float
    overlap: tuple[str, str]
    last_linked: str
    account_sets: dict[str, tuple[str, ...]]


def _as_list(x: Any) -> list[Any]:
    return [] if x is None else list(x)


def load_definitions(path: Path = FLOWS_YAML, layout: Layout | None = None) -> Definitions:
    """Read and validate flows.yaml: every account token, ref, component and bop tag is checked here."""
    layout = layout or Layout.default()
    doc = io.read_yaml(path) or {}
    acc = Accounts.load()
    gm = gap_map(str(layout.gap_map))
    problems: list[str] = []
    cut = doc.get("cutoff") or {}
    rules = doc.get("link_rules") or {}

    def need_str(where: str, x: Any, what: str) -> str:
        """YAML 1.1 reads unquoted NO/YES/ON/OFF as booleans and bare numbers as numbers: every name must be a
        string, or it would be written as 'False' (verification TSV-1)."""
        if not isinstance(x, str):
            problems.append(
                f"{where}: {what} {x!r} is not a string (quote it; YAML 1.1 reads NO/YES/ON/OFF as booleans)"
            )
            return str(x)
        return x

    def strs(where: str, xs: Any, what: str) -> list[str]:
        return [need_str(where, x, what) for x in _as_list(xs)]

    sets: dict[str, tuple[str, ...]] = {}
    for name, codes in sorted((doc.get("account_sets") or {}).items()):
        bad = [c for c in codes if not acc.exists(c)]
        if bad:
            problems.append(f"account set {name}: unknown accounts {bad}")
        if len(set(codes)) != len(codes):
            problems.append(f"account set {name}: an account is listed twice")
        sets[name] = tuple(codes)
    groups = sorted({acc.group(c) for c in acc.codes})

    def tokens(where: str, toks: Sequence[str]) -> tuple[str, ...]:
        out: list[str] = []
        for t in toks:
            if not isinstance(t, str):
                problems.append(f"{where}: account token {t!r} is not a string")
            elif t.startswith("@"):
                if t[1:] not in groups:
                    problems.append(f"{where}: unknown account group {t!r} (groups: {groups})")
                else:
                    out.extend(acc.in_group(t[1:]))
            elif t.startswith("$"):
                if t[1:] not in sets:
                    problems.append(f"{where}: unknown account set {t!r}")
                else:
                    out.extend(sets[t[1:]])
            elif not acc.exists(t):
                problems.append(f"{where}: unknown account {t!r}")
            else:
                out.append(t)
        if len(set(out)) != len(out):
            problems.append(f"{where}: an account appears twice after expanding {list(toks)}")
        if not out and toks:
            problems.append(f"{where}: no accounts")
        return tuple(out)

    def refs_ok(where: str, refs: Sequence[str]) -> tuple[str, ...]:
        for r in refs:
            if r not in gm:
                problems.append(f"{where}: ref {r!r} is not in data/gap_map.csv")
        return tuple(refs)

    first = need_str("cutoff", cut.get("first_period", ""), "first_period")
    last = need_str("cutoff", cut.get("last_period", ""), "last_period")
    for p in (first, last):
        try:
            fy_start(p)
        except TsError as e:
            problems.append(f"cutoff: {e}")
    flows: list[Flow] = []
    seen: set[str] = set()
    for f in doc.get("flows") or []:
        fid = need_str("flows", f.get("id", ""), "flow id")
        w = f"flow {fid or '?'}"
        need_str(w, f.get("name"), "name")
        need_str(w, f.get("group"), "group")
        if not fid or fid in seen or not (len(fid) == 3 and fid[0] in "FMX" and fid[1:].isdigit()):
            problems.append(f"{w}: id must be unique and look like F01 / M01 / X01")
        seen.add(fid)
        tier = f.get("tier")
        if tier not in TIERS:
            problems.append(f"{w}: tier must be one of {TIERS}")
        cls = str(f.get("check_class"))
        if cls not in CHECK_CLASSES:
            problems.append(f"{w}: check_class must be one of {CHECK_CLASSES}")
        if cls == "B" and not f.get("tol_rel"):
            problems.append(f"{w}: class B needs tol_rel (the owning band)")
        ds = int(f.get("display_sign", 1))
        if ds not in (1, -1):
            problems.append(f"{w}: display_sign must be 1 or -1")
        link = f.get("link")
        if link == "allowed":
            allowed, reason = True, None
        elif isinstance(link, dict) and isinstance(link.get("refused"), str) and link["refused"].strip():
            allowed, reason = False, link["refused"].strip()
        else:
            allowed, reason = False, None
            problems.append(f"{w}: link must be 'allowed' or {{refused: <reason>}}")
        sam = f.get("sam") or {}
        sterms: list[SamTerm] = []
        for i, t in enumerate(sam.get("terms") or []):
            tw = f"{w} sam term {i + 1}"
            known_keys = {"rows", "cols", "refs", "optional_refs", "components", "exclude_components",
                          "bop_functions", "coef"}  # fmt: skip
            if set(t) - known_keys:
                problems.append(f"{tw}: unknown keys {sorted(set(t) - known_keys)}")
            comps = None if t.get("components") is None else strs(tw, t.get("components"), "component")
            excl_comps = strs(tw, t.get("exclude_components"), "excluded component")
            bops = None if t.get("bop_functions") is None else strs(tw, t.get("bop_functions"), "bop_function")
            for c in [*_as_list(comps), *excl_comps]:
                if not sam_spec.COMPONENT_RE.match(c):
                    problems.append(f"{tw}: bad component slug {c!r}")
            if set(_as_list(comps)) & set(excl_comps):
                problems.append(
                    f"{tw}: components both selected and excluded: {sorted(set(comps or []) & set(excl_comps))}"
                )
            for b in _as_list(bops):
                if b not in sam_spec.BOP_FUNCTIONS:
                    problems.append(f"{tw}: bop_function {b!r} not in the framework vocabulary")
            refs = strs(tw, t.get("refs"), "ref")
            if not refs:
                problems.append(f"{tw}: refs must be listed explicitly (plan s.2.0)")
            coef = float(t.get("coef", 1))
            if coef == 0 or not math.isfinite(coef):
                problems.append(f"{tw}: coef must be finite and non-zero")
            optional = strs(tw, t.get("optional_refs"), "optional ref")
            if not set(optional) <= set(refs):
                problems.append(f"{tw}: optional_refs {sorted(set(optional) - set(refs))} are not in refs")
            sterms.append(
                SamTerm(
                    rows=tokens(f"{tw} rows", _as_list(t.get("rows"))),
                    cols=tokens(f"{tw} cols", _as_list(t.get("cols"))),
                    refs=refs_ok(tw, refs),
                    optional_refs=tuple(optional),
                    components=None if comps is None else tuple(comps),
                    bop_functions=None if bops is None else tuple(bops),
                    coef=coef,
                    spec={k: t[k] for k in sorted(t)},
                    exclude_components=tuple(excl_comps),
                )
            )
        if cls != "none" and not sterms:
            problems.append(f"{w}: a SAM definition (sam.terms) is required unless check_class is 'none'")
        excluded = refs_ok(f"{w} excluded_refs", strs(w, sam.get("excluded_refs"), "excluded ref"))
        named = {r for t in sterms for r in t.refs}
        if named & set(excluded):
            problems.append(f"{w}: refs both in the definition and excluded: {sorted(named & set(excluded))}")
        segs: list[Segment] = []
        for s in f.get("segments") or []:
            code = need_str(w, s.get("code"), "segment code")
            sw = f"{w} segment {code}"
            if isinstance(s.get("code"), str) and not SEGMENT_CODE_RE.match(code):
                problems.append(f"{sw}: a segment code is 2-4 capitals or digits starting with a capital (plan s.2.1)")
            dataset = need_str(sw, s.get("dataset"), "dataset")
            base = s.get("base_year")
            if base not in BASE_YEARS:
                problems.append(f"{sw}: base_year must be one of {BASE_YEARS}")
            variant = need_str(sw, s.get("variant", MAIN_VARIANT), "variant")
            if variant not in VARIANTS or variant == LINK_VARIANT:
                problems.append(f"{sw}: variant {variant!r} not allowed (the linked variant is built, not declared)")
            lo, hi = need_str(sw, s.get("from", ""), "from"), need_str(sw, s.get("to", ""), "to")
            try:
                if fy_start(lo) > fy_start(hi):
                    problems.append(f"{sw}: from {lo} is after to {hi}")
                if first and last and (fy_start(lo) < fy_start(first) or fy_start(hi) > fy_start(last)):
                    problems.append(f"{sw}: {lo}..{hi} outside the cutoff {first}..{last}")
            except TsError as e:
                problems.append(f"{sw}: {e}")
            st = s.get("status")
            if st not in (None, "derived"):
                problems.append(f"{sw}: status may only be overridden to 'derived'")
            terms: list[Term] = []
            for t in s.get("terms") or []:
                coef = float(t.get("coef", 1))
                if coef == 0 or not math.isfinite(coef):
                    problems.append(f"{sw}: coef must be finite and non-zero")
                template: str | None = None
                if "id" in t and "template" not in t:
                    label = need_str(sw, t["id"], "series id")
                    series: tuple[str, ...] = (label,)
                elif (
                    "template" in t
                    and t.get("rounds") == "latest"
                    and isinstance(t["template"], str)
                    and t["template"].count("{round}") == 1
                ):
                    template = label = t["template"]
                    series = tuple(template.format(round=r) for r in ROUNDS_LATEST)
                else:
                    problems.append(
                        f"{sw}: a term is {{id: <series>}} or {{template: '...{{round}}...', rounds: latest}}"
                    )
                    continue
                tlo, thi = t.get("from"), t.get("to")
                tlo = None if tlo is None else need_str(sw, tlo, "term from")
                thi = None if thi is None else need_str(sw, thi, "term to")
                terms.append(Term(series, coef, tlo, thi, label, template))
            if not terms:
                problems.append(f"{sw}: no terms")
            segs.append(
                Segment(
                    code=code,
                    dataset=dataset,
                    base_year=base,
                    lo=lo,
                    hi=hi,
                    variant=variant,
                    terms=tuple(terms),
                    status_override=st,
                    note=None if s.get("note") is None else need_str(sw, s.get("note"), "note"),
                )
            )
        if not segs:
            problems.append(f"{w}: no segments")
        codes = [(s.code, s.variant) for s in segs]
        if len(set(codes)) != len(codes):
            problems.append(f"{w}: segment codes must be unique within a variant")
        # segments of one (base_year, variant) must not overlap and must be contiguous (no silent gaps)
        by: dict[tuple[str | None, str], list[Segment]] = {}
        for s in segs:
            by.setdefault((s.base_year, s.variant), []).append(s)
        for (b, v), ss in sorted(by.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
            try:
                ss = sorted(ss, key=lambda s: fy_start(s.lo))
                for a, c in zip(ss, ss[1:]):
                    if fy_start(c.lo) <= fy_start(a.hi):
                        problems.append(f"{w}: segments {a.code} and {c.code} overlap (base {b}, variant {v})")
                    elif fy_start(c.lo) != fy_start(a.hi) + 1:
                        problems.append(f"{w}: gap between segments {a.code} and {c.code} (base {b}, variant {v})")
            except TsError:
                pass
        brk = tuple(
            (need_str(w, b.get("period"), "break period"), need_str(w, b.get("note") or "", "break note"))
            for b in f.get("breaks") or []
        )
        for bp, bn in brk:
            try:
                in_seg = any(fy_start(s.lo) <= fy_start(bp) <= fy_start(s.hi) for s in segs)
            except TsError as e:
                problems.append(f"{w} break: {e}")
                continue
            if not in_seg or not bn.strip():
                problems.append(f"{w}: break {bp} must fall inside a segment and carry a note")
        flows.append(
            Flow(
                flow_id=fid,
                name=str(f.get("name", "")),
                group=str(f.get("group", "")),
                tier=str(tier),
                display_sign=ds,
                check_class=cls,
                tol_abs=None if f.get("tol_abs") is None else float(f["tol_abs"]),
                tol_rel=None if f.get("tol_rel") is None else float(f["tol_rel"]),
                link_allowed=allowed,
                link_refused_reason=reason,
                sam_terms=tuple(sterms),
                excluded_refs=excluded,
                sam_note=sam.get("note"),
                segments=tuple(segs),
                breaks=brk,
            )
        )
    if not flows:
        problems.append("no flows defined")
    excl = tuple(strs("cutoff", cut.get("excluded_stages"), "excluded stage"))
    overlap = tuple(strs("link_rules", rules.get("overlap_periods"), "overlap period"))
    if len(overlap) != 2:
        problems.append("link_rules.overlap_periods must name two FYs")
    need_str("link_rules", rules.get("last_linked_period"), "last_linked_period")
    if problems:
        raise TsError(f"{path.name}:\n  " + "\n  ".join(problems))
    return Definitions(
        flows=tuple(flows),
        first_period=first,
        last_period=last,
        excluded_stages=excl,
        max_ratio_gap=float(rules.get("max_ratio_gap", 0.02)),
        overlap=(str(overlap[0]), str(overlap[1])),
        last_linked=str(rules.get("last_linked_period")),
        account_sets=sets,
    )


def load_explanations(path: Path = EXPLANATIONS_YAML) -> dict[str, dict[str, Any]]:
    doc = io.read_yaml(path) or {}
    out: dict[str, dict[str, Any]] = {}
    for e in doc.get("explanations") or []:
        fid = e.get("flow_id")
        if not isinstance(fid, str):
            raise TsError(f"{path.name}: flow_id {fid!r} is not a string")
        if fid in out:
            raise TsError(f"{path.name}: flow {fid} explained twice")
        if not isinstance(e.get("why"), str) or not e["why"].strip():
            raise TsError(f"{path.name}: flow {fid} has no 'why'")
        for b in e.get("bridge_series") or []:
            if not (isinstance(b.get("dataset"), str) and isinstance(b.get("id"), str)):
                raise TsError(f"{path.name}: flow {fid}: bridge dataset and id must be strings: {b!r}")
        ex = e.get("explained_residual")
        if ex is not None and (isinstance(ex, bool) or not isinstance(ex, (int, float))):
            raise TsError(f"{path.name}: flow {fid}: explained_residual must be a number or null")
        out[fid] = e
    return out


# ---------------------------------------------------------------------------------------------
# provenance
# ---------------------------------------------------------------------------------------------


@dataclass
class ProvBook:
    """The time series' own provenance records (Phase 1 schema, ingest_unit 'timeseries')."""

    clean: CleanIndex
    layout: Layout
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    _sources: frozenset[str] | None = None

    def lookup(self, pid: str) -> dict[str, Any] | None:
        return self.records.get(pid) or self.clean.prov(pid)

    def add(
        self,
        *,
        status: str,
        method: str,
        inputs: Iterable[str],
        table_id: str,
        locator: str,
        base_year: str | None,
        conversion: str = "none",
        notes: str | None = None,
        source_id: str | None = None,
    ) -> str:
        ins = sorted(set(inputs))
        recs = []
        problems = []
        for i in ins:
            r = self.lookup(i)
            if r is None:
                problems.append(f"input {i!r} does not resolve (not a clean or time-series record)")
            else:
                recs.append(r)
        if not ins:
            problems.append("a time-series record needs inputs (nothing is estimated or typed in)")
        if status == "official" and any(r["status"] != "official" for r in recs):
            problems.append("an 'official' record may only aggregate official inputs")
        if status not in ("official", "derived"):
            problems.append(f"status {status!r}: the time series has only official and derived rows")
        in_sources = sorted({str(r["source_id"]) for r in recs if r.get("source_id")})
        if source_id is None:
            if len(in_sources) != 1:
                problems.append(f"inputs from several sources {in_sources}: name source_id")
            else:
                source_id = in_sources[0]
        elif source_id not in in_sources and not notes:
            problems.append(f"source_id {source_id!r} is not the source of any input: say why in notes")
        if self._sources is None:
            self._sources = source_ids(self.layout)
        if source_id is not None and source_id not in self._sources:
            problems.append(f"source_id {source_id!r} is not in the registry")
        vs = [str(r["vintage"]) for r in recs if r.get("vintage")]
        if problems:
            raise TsError(f"provenance ({table_id}):\n  " + "\n  ".join(problems))
        rec: dict[str, Any] = {
            "ingest_unit": INGEST_UNIT,
            "source_id": source_id,
            "url": None,
            "raw_path": None,
            "raw_sha256": None,
            "retrieved_at": None,
            "table_id": table_id,
            "locator": locator,
            "unit_as_published": "Rs crore",
            "conversion": conversion,
            "price_basis": "current",
            "base_year": base_year,
            "vintage": max(vs, key=lambda v: (vintage_end(v), v)),
            "release": "India SAM top-flows time series (post-SAM step, DECISIONS D2-18)",
            "status": status,
            "method": method.strip(),
            "inputs": ",".join(ins),
            "notes": notes,
        }
        pid = f"{INGEST_UNIT}:{io.sha256_bytes(io.dumps_json(rec, indent=None).encode())[:12]}"
        self.records[pid] = {"prov_id": pid, **rec}
        return pid

    def frame(self) -> pl.DataFrame:
        rows = [self.records[k] for k in sorted(self.records)]
        df = pl.DataFrame(rows, schema=PROV_DTYPES, orient="row") if rows else pl.DataFrame(schema=PROV_DTYPES)
        df = df.select(list(PROV_DTYPES))
        try:
            PROV_SCHEMA.validate(df, lazy=True)
        except pa_errors.SchemaErrors as e:
            raise TsError(f"time-series provenance: schema violations\n{e.failure_cases.head(20)}") from None
        bad = df.filter(pl.col("method").is_null() | ~pl.col("prov_id").str.contains(PROV_ID_RE))
        if bad.height:
            raise TsError(f"time-series provenance: records without method or with bad ids: {bad['prov_id'].to_list()}")
        return df


# ---------------------------------------------------------------------------------------------
# segments -> rows
# ---------------------------------------------------------------------------------------------


def _least_mature(stages: Iterable[str]) -> str:
    st = sorted(set(stages), key=lambda s: STAGE_ORDER.index(s) if s in STAGE_ORDER else len(STAGE_ORDER))
    return st[-1]


def _latest(vintages: Iterable[str]) -> str:
    return max(set(vintages), key=lambda v: (vintage_end(v), v))


@dataclass
class Reader:
    clean: CleanIndex
    frames: dict[str, pl.DataFrame] = field(default_factory=dict)

    def frame(self, dataset: str) -> pl.DataFrame:
        if dataset not in self.frames:
            try:
                p = self.clean.path(dataset)
            except Exception as e:  # noqa: BLE001 - CleanIndex raises SamError: say it in our terms
                raise TsError(str(e)) from None
            self.frames[dataset] = pl.read_parquet(p)
        return self.frames[dataset]


def read_term(reader: Reader, defs: Definitions, seg: Segment, term: Term, what: str) -> dict[str, dict[str, Any]]:
    """{period: {value, prov_id, stage, vintage, series_id, base_year}} for one term inside its range. Rules: FY
    only, INR crore at current prices, BE/RE excluded, the latest vintage per (series, period); for revision
    rounds, the first round in precedence order that has the period. A revision round of the template that is
    not in ROUNDS_LATEST is an error (it cannot be ordered, and skipping it would silently use an older round)."""
    df = reader.frame(seg.dataset)
    have = set(df["series_id"].unique().to_list())
    if term.template is not None:
        pre, post = term.template.split("{round}")
        found = {s[len(pre) : len(s) - len(post)] for s in have if s.startswith(pre) and s.endswith(post)}
        unknown = sorted(r for r in found if r not in ROUNDS_LATEST)
        if unknown:
            raise TsError(
                f"{what}: {seg.dataset} has revision rounds {unknown} of {term.template!r} that are not in "
                f"ROUNDS_LATEST {ROUNDS_LATEST}: place them in the precedence order (build.py) before building"
            )
    present = [s for s in term.series if s in have]
    if not present:
        raise TsError(f"{what}: series {term.label!r} not in {seg.dataset}")
    lo = term.lo or seg.lo
    hi = term.hi or seg.hi
    periods = set(fy_range(max(lo, seg.lo, key=fy_start), min(hi, seg.hi, key=fy_start)))
    rows = df.filter(pl.col("series_id").is_in(present) & pl.col("period").is_in(sorted(periods)))
    rows = rows.filter(~pl.col("estimate_stage").is_in(list(defs.excluded_stages)))
    bad = rows.filter(
        (pl.col("period_type") != "fy") | (pl.col("unit") != "INR_crore") | (pl.col("price_basis") != "current")
    )
    if bad.height:
        raise TsError(f"{what}: rows not FY / INR_crore / current prices:\n{bad.head(5)}")
    rows = select_vintage(rows, "latest", what)
    out: dict[str, dict[str, Any]] = {}
    for sid in present:  # precedence order
        for r in rows.filter(pl.col("series_id") == sid).sort("period").iter_rows(named=True):
            if r["period"] in out:
                continue
            out[r["period"]] = {
                "value": float(r["value"]),
                "prov_id": r["prov_id"],
                "stage": r["estimate_stage"],
                "vintage": r["vintage"],
                "series_id": sid,
                "base_year": r["base_year"],
            }
    return out


def build_segment_rows(
    reader: Reader, book: ProvBook, defs: Definitions, flow: Flow, seg: Segment, problems: list[str]
) -> list[dict[str, Any]]:
    what = f"{flow.flow_id} segment {seg.code}"
    terms = [(t, read_term(reader, defs, seg, t, f"{what} term {t.label}")) for t in seg.terms]
    per: list[tuple[str, float, list[dict[str, Any]]]] = []
    for p in fy_range(seg.lo, seg.hi):
        parts: list[dict[str, Any]] = []
        total = 0.0
        ok = True
        for t, vals in terms:
            if (t.lo and fy_start(p) < fy_start(t.lo)) or (t.hi and fy_start(p) > fy_start(t.hi)):
                continue
            v = vals.get(p)
            if v is None:
                problems.append(f"{what}: no value of {t.label} for {p} (segments must be complete)")
                ok = False
                continue
            total += t.coef * v["value"]
            parts.append(v)
        bases = {x["base_year"] for x in parts}
        if parts and bases != {seg.base_year}:
            problems.append(
                f"{what}: {p}: segment base_year {seg.base_year!r} but its clean inputs carry "
                f"{sorted(str(b) for b in bases)} (a row's base_year is its inputs' base)"
            )
            ok = False
        if ok:
            per.append((p, total, parts))
    if not per:
        return []
    ins = sorted({x["prov_id"] for _, _, parts in per for x in parts})
    stats = {str(r["status"]) for r in (book.lookup(i) for i in ins) if r is not None}
    one_dataset_sum = all(t.coef == 1 for t in seg.terms)
    status = "official" if (one_dataset_sum and stats == {"official"} and seg.status_override is None) else "derived"
    flips = [t.label for t in seg.terms if t.coef != 1]
    formula = " + ".join(
        (f"{t.coef:g} x " if t.coef != 1 else "")
        + t.label
        + (f" [{t.lo or seg.lo}..{t.hi or seg.hi}]" if t.lo or t.hi else "")
        for t in seg.terms
    )
    rounds = any(len(t.series) > 1 for t in seg.terms)
    method = (
        f"Top-flows time series, flow {flow.flow_id} ({flow.name}), segment {seg.code}"
        f"{'' if seg.variant == MAIN_VARIANT else f', variant {seg.variant}'}: for each FY {seg.lo}..{seg.hi}, "
        f"{formula} from clean dataset {seg.dataset}. Rules: FY rows in INR crore at current prices; budget "
        f"BE/RE rows excluded; the latest vintage per (series, period)"
        + ("; NAS API revision rounds taken latest first (" + " > ".join(ROUNDS_LATEST) + ")" if rounds else "")
        + (f"; {', '.join(flips)} enter with the coefficient shown (SAM sign convention)" if flips else "")
        + ("." if not seg.note else f". {seg.note}.")
        + (" Status derived by definition of the segment." if seg.status_override else "")
    )
    pid = book.add(
        status=status,
        method=method,
        inputs=ins,
        table_id=f"top flows {flow.flow_id} segment {seg.code}",
        locator=f"data/timeseries/top_flows.parquet flow_id={flow.flow_id} segment={seg.code} variant={seg.variant}",
        base_year=seg.base_year,
        conversion="none" if not flips else "coefficients as stated in the method (sign flips / differences)",
    )
    rows = []
    for p, total, parts in per:
        rows.append(
            {
                "flow_id": flow.flow_id,
                "period": p,
                "period_type": "fy",
                "value": total,
                "unit": "INR_crore",
                "price_basis": "current",
                "base_year": seg.base_year,
                "variant": seg.variant,
                "segment": seg.code,
                "datasets": seg.dataset,
                "series_ids": ",".join(x["series_id"] for x in parts),
                "estimate_stage": _least_mature(x["stage"] for x in parts),
                "vintage": _latest(x["vintage"] for x in parts),
                "status": status,
                "flags": None,
                "prov_id": pid,
                "note": None,
            }
        )
    return rows


@dataclass
class LinkResult:
    policy: str  # linked | refused
    reason: str | None
    rules_met: bool | None  # the plan s.2.5 data rules: True / False, None when there is nothing to link
    rules: str  # what the rules give in the data (definitions column link_rules)
    r22: float | None
    r23: float | None
    rows: list[dict[str, Any]]


def link_flow(book: ProvBook, defs: Definitions, flow: Flow, rows: list[dict[str, Any]]) -> LinkResult:
    """plan s.2.5: linked(t) = old(t) x new(2022-23) / old(2022-23) for t <= 2021-22, only if both overlap ratios
    exist, differ by at most max_ratio_gap, and the flow keeps one sign. The ratios are computed from the rows.
    The data rules are evaluated for every flow, also the refused ones, and stored (verification TSV-5)."""
    main = [r for r in rows if r["variant"] == MAIN_VARIANT]
    old = {r["period"]: r for r in main if r["base_year"] == OLD_BASE}
    new = {r["period"]: r for r in main if r["base_year"] == NEW_BASE}
    p22, p23 = defs.overlap

    def ratio(p: str) -> float | None:
        if p in old and p in new and old[p]["value"] != 0:
            return new[p]["value"] / old[p]["value"]
        return None

    r22, r23 = ratio(p22), ratio(p23)
    met: bool | None
    if not old or not new:
        met, rules = None, "not applicable: no old-base and new-base rows to link"
    else:
        why = []
        if r22 is None or r23 is None:
            why.append("an overlap ratio is missing")
        elif abs(r22 - r23) > defs.max_ratio_gap:
            why.append(f"|r({p22}) - r({p23})| = {abs(r22 - r23):.4f} > {defs.max_ratio_gap}")
        signs = {math.copysign(1, r["value"]) for r in [*old.values(), *new.values()] if r["value"] != 0}
        if len(signs) > 1:
            why.append("the flow changes sign")
        if why:
            met, rules = False, "not met: " + "; ".join(why)
        else:
            assert r22 is not None and r23 is not None
            met = True
            rules = f"met: |r({p22}) - r({p23})| = {abs(r22 - r23):.4f} <= {defs.max_ratio_gap}; one sign"
    if not flow.link_allowed:
        return LinkResult("refused", flow.link_refused_reason, met, rules, r22, r23, [])
    if not met:
        return LinkResult("refused", f"rules of plan s.2.5 {rules}", met, rules, r22, r23, [])
    assert r22 is not None and r23 is not None
    targets = [r for p, r in sorted(old.items()) if fy_start(p) <= fy_start(defs.last_linked)]
    ins = sorted({r["prov_id"] for r in targets} | {old[p22]["prov_id"], new[p22]["prov_id"]})
    new_src = book.lookup(new[p22]["prov_id"])
    pid = book.add(
        status="derived",
        method=(
            f"Top-flows time series, flow {flow.flow_id} ({flow.name}), variant {LINK_VARIANT}: for each old-base "
            f"(2011-12) FY up to {defs.last_linked}, linked(t) = old(t) x new({p22}) / old({p22}) = old(t) x "
            f"{r22:.9f} (new-base NAS 2026 over old-base value in {p22}); r({p23}) = {r23:.9f}, within "
            f"{defs.max_ratio_gap} of it; the flow keeps one sign. Ratio-linked at the 2022-23 overlap: not additive "
            "across flows; replace with MoSPI's new-base back series when published (ISSUES P1-6)."
        ),
        inputs=ins,
        table_id=f"top flows {flow.flow_id} linked_2022_23",
        locator=f"data/timeseries/top_flows.parquet flow_id={flow.flow_id} variant={LINK_VARIANT}",
        base_year=NEW_BASE,
        conversion=f"multiplied by the overlap ratio {r22:.9f}",
        source_id=None if new_src is None else str(new_src["source_id"]),
        notes=(
            "inputs are the old-base segment records and both 2022-23 records; source_id is the new-base level's source"
        ),
    )
    out = []
    for r in targets:
        out.append(
            {
                **r,
                "value": r["value"] * r22,
                "base_year": NEW_BASE,
                "variant": LINK_VARIANT,
                "segment": f"LINK:{r['segment']}",
                "vintage": _latest([r["vintage"], new[p22]["vintage"]]),
                "status": "derived",
                "prov_id": pid,
                "note": f"old-base value x {r22:.6f} (ratio-linked at {p22})",
            }
        )
    return LinkResult("linked", None, met, rules, r22, r23, out)


def add_flags(flow: Flow, rows: list[dict[str, Any]]) -> None:
    """base_overlap: the published variant has both NAS bases in this FY (the break stays visible);
    segment_join: the first FY of a segment that continues another in the same (base_year, variant);
    base_change: a published row whose base_year differs from every published row of the previous FY while no
    row of this FY keeps a previous base (a switch of base without an overlap year: the level break is not
    adjusted, e.g. RBI HBS Table 12 before 2011-12 to old-base NAS 5.3);
    concept_break: a documented definitional break (flows.yaml `breaks`)."""
    main_bases: dict[str, set[str | None]] = {}
    for r in rows:
        if r["variant"] == MAIN_VARIANT:
            main_bases.setdefault(r["period"], set()).add(r["base_year"])
    first_of: dict[tuple[str | None, str, str], str] = {}
    for r in rows:
        k = (r["base_year"], r["variant"], r["segment"])
        if k not in first_of or fy_start(r["period"]) < fy_start(first_of[k]):
            first_of[k] = r["period"]
    starts: dict[tuple[str | None, str], list[str]] = {}
    for (b, v, _s), p in first_of.items():
        starts.setdefault((b, v), []).append(p)
    breaks = {p for p, _ in flow.breaks}
    for r in rows:
        fl = []
        if r["variant"] == MAIN_VARIANT and {OLD_BASE, NEW_BASE} <= main_bases.get(r["period"], set()):
            fl.append("base_overlap")
        ss = sorted(starts[(r["base_year"], r["variant"])], key=fy_start)
        if r["period"] in ss[1:]:
            fl.append("segment_join")
        if r["variant"] == MAIN_VARIANT:
            prev = main_bases.get(fy(fy_start(r["period"]) - 1), set())
            if prev and r["base_year"] not in prev and not (main_bases[r["period"]] & prev):
                fl.append("base_change")
        if r["period"] in breaks:
            fl.append("concept_break")
        r["flags"] = ",".join(fl) or None


# ---------------------------------------------------------------------------------------------
# the 2023-24 SAM check
# ---------------------------------------------------------------------------------------------


@dataclass
class SamEval:
    value: float
    n_entries: int
    allowance: float
    unlisted: list[str]
    missing: list[str]
    overlapping: int


def eval_sam(flow: Flow, ent: pl.DataFrame) -> SamEval:
    """Sum of the entries matching each term (x coef); the anchored allowance of the matched entries
    (tol_rel x |prior|); refs found in the terms' cell blocks that are neither in the definition nor excluded;
    selectors (ref, component, bop tag) that match no entry; entries matched by more than one term."""
    named = {r for t in flow.sam_terms for r in t.refs}
    total = 0.0
    allowance = 0.0
    n = 0
    unlisted: set[str] = set()
    missing: list[str] = []
    seen: dict[tuple[str, str, str, str], int] = {}
    prior_col = "prior" if "prior" in ent.columns else "value"
    for i, t in enumerate(flow.sam_terms):
        block = ent.filter(pl.col("row").is_in(list(t.rows)) & pl.col("col").is_in(list(t.cols)))
        unlisted |= set(block["ref"].to_list()) - named - set(flow.excluded_refs)
        sel = block.filter(pl.col("ref").is_in(list(t.refs)))
        for r in t.refs:
            if r not in t.optional_refs and sel.filter(pl.col("ref") == r).height == 0:
                missing.append(f"term{i + 1}:ref={r}")
        if t.components is not None:
            for c in t.components:
                if sel.filter(pl.col("component") == c).height == 0:
                    missing.append(f"term{i + 1}:component={c}")
            sel = sel.filter(pl.col("component").is_in(list(t.components)))
        if t.bop_functions is not None:
            for b in t.bop_functions:
                if sel.filter(pl.col("bop_function") == b).height == 0:
                    missing.append(f"term{i + 1}:bop_function={b}")
            sel = sel.filter(pl.col("bop_function").is_in(list(t.bop_functions)))
        if t.exclude_components:
            sel = sel.filter(~pl.col("component").is_in(list(t.exclude_components)).fill_null(False))
        total += t.coef * float(sel["value"].sum())
        n += sel.height
        anc = sel.filter(pl.col("role") == "anchored")
        if anc.height:
            allowance += float((anc["tol_rel"] * anc[prior_col].abs()).sum())
        for k in sel.select("row", "col", "ref", "component").iter_rows():
            seen[k] = seen.get(k, 0) + 1
    return SamEval(
        value=total,
        n_entries=n,
        allowance=allowance,
        unlisted=sorted(unlisted),
        missing=missing,
        overlapping=sum(1 for v in seen.values() if v > 1),
    )


def read_sam(layout: Layout) -> tuple[pl.DataFrame | None, str | None, pl.DataFrame | None]:
    """(prior entries, where they came from, balanced entries). Before a full `sam` run the prior is the union
    of the built blocks' entries."""
    paths = SamPaths(layout)
    cols = ["row", "col", "ref", "component", "value", "role", "tol_rel", "bop_function"]
    bal = pl.read_parquet(paths.balanced_entries) if paths.balanced_entries.exists() else None
    if bal is not None:
        bal = bal.select([*cols, "prior"])
    if paths.prior_entries.exists():
        return pl.read_parquet(paths.prior_entries).select(cols), "sam_entries_prior", bal
    files = sorted(paths.blocks.glob("*_entries.parquet")) if paths.blocks.exists() else []
    if not files:
        return None, None, bal
    frames = [pl.read_parquet(f).select(cols) for f in files]
    return pl.concat(frames, how="vertical"), "block_entries", bal


def bridge_value(reader: Reader, defs: Definitions, expl: dict[str, Any] | None, what: str) -> tuple[float, list[str]]:
    total, pids = 0.0, []
    for b in (expl or {}).get("bridge_series") or []:
        seg = Segment("bridge", str(b["dataset"]), None, YEAR, YEAR, MAIN_VARIANT, (), None, None)
        t = Term((str(b["id"]),), float(b.get("coef", 1)), None, None, str(b["id"]))
        vals = read_term(reader, defs, seg, t, f"{what} bridge {b['id']}")
        if YEAR not in vals:
            raise TsError(f"{what}: bridge series {b['id']} has no {YEAR} value")
        total += t.coef * vals[YEAR]["value"]
        pids.append(vals[YEAR]["prov_id"])
    return total, pids


def sam_check(
    reader: Reader,
    defs: Definitions,
    rows: pl.DataFrame,
    explanations: dict[str, dict[str, Any]],
    prior: pl.DataFrame | None,
    prior_src: str | None,
    bal: pl.DataFrame | None,
) -> pl.DataFrame:
    out = []
    for f in defs.flows:
        ex = explanations.get(f.flow_id)
        rec: dict[str, Any] = {k: None for k in CHECK_DTYPES}
        rec |= {"flow_id": f.flow_id, "check_class": f.check_class, "overlapping_entries": 0,
                "explanation": None if ex is None else " ".join(str(ex["why"]).split())}  # fmt: skip
        ts = rows.filter(
            (pl.col("flow_id") == f.flow_id) & (pl.col("period") == YEAR) & (pl.col("variant") == MAIN_VARIANT)
        )
        ts = ts.filter(pl.col("base_year").is_null() | (pl.col("base_year") == NEW_BASE))
        if ts.height > 1:
            raise TsError(f"{f.flow_id}: several {YEAR} rows on the SAM's basis")
        if ts.height == 1:
            rec |= {"ts_value": ts["value"][0], "ts_segment": ts["segment"][0], "ts_base_year": ts["base_year"][0],
                    "ts_prov_id": ts["prov_id"][0]}  # fmt: skip
        if f.check_class == "none" or ts.height == 0:
            rec["verdict"] = "no_check"
            out.append(rec)
            continue
        tsv = float(rec["ts_value"])
        if prior is not None:
            ep = eval_sam(f, prior)
            rec |= {"sam_prior": ep.value, "sam_prior_source": prior_src}
        bridge, _ = bridge_value(reader, defs, ex, f.flow_id) if f.check_class in ("C", "D") else (0.0, [])
        if f.check_class in ("C", "D"):
            rec["bridge"] = bridge
        explained = None if ex is None or ex.get("explained_residual") is None else float(ex["explained_residual"])
        rec["explained_residual"] = explained
        if bal is None:
            rec["verdict"] = "pending_balancing"
            out.append(rec)
            continue
        eb = eval_sam(f, bal)
        diff = eb.value - tsv
        rec |= {
            "sam_balanced": eb.value,
            "n_entries": eb.n_entries,
            "anchored_allowance": eb.allowance,
            "diff": diff,
            "rel_diff": diff / abs(tsv) if tsv else None,
            "unlisted_refs": ",".join(eb.unlisted) or None,
            "missing_selectors": ",".join(eb.missing) or None,
            "overlapping_entries": eb.overlapping,
        }
        if f.check_class == "A":
            tol = max(f.tol_abs if f.tol_abs is not None else TOL_A, eb.allowance)
            resid = diff
        elif f.check_class == "B":
            tol = max(TOL_A, float(f.tol_rel or 0) * abs(tsv))
            resid = diff
        elif f.check_class == "C":
            tol = max(TOL_C_ABS, TOL_C_REL * abs(tsv))
            resid = diff - bridge
        else:
            tol = TOL_D
            resid = diff - bridge
        rec |= {"tolerance": tol, "residual": resid}
        if abs(resid) <= tol:
            verdict = "pass"
        elif explained is not None and abs(resid - explained) <= max(
            EXPLAIN_DRIFT_REL * abs(explained), EXPLAIN_DRIFT_ABS
        ):
            verdict = "explained"
        else:
            verdict = "fail" if f.check_class in ("A", "B") and ex is None else "unexplained"
        rec["verdict"] = verdict
        out.append(rec)
    return pl.DataFrame(out, schema=CHECK_DTYPES, orient="row")


# ---------------------------------------------------------------------------------------------
# the build
# ---------------------------------------------------------------------------------------------


@dataclass
class TsResult:
    rows: pl.DataFrame
    definitions: pl.DataFrame
    coverage: pl.DataFrame
    check: pl.DataFrame
    provenance: pl.DataFrame
    warnings: list[str]


def build(layout: Layout, *, flows_path: Path = FLOWS_YAML, explanations_path: Path = EXPLANATIONS_YAML) -> TsResult:
    defs = load_definitions(flows_path, layout)
    explanations = load_explanations(explanations_path)
    unknown = sorted(set(explanations) - {f.flow_id for f in defs.flows})
    if unknown:
        raise TsError(f"explanations.yaml names unknown flows {unknown}")
    clean = CleanIndex(layout)
    reader = Reader(clean)
    book = ProvBook(clean, layout)
    problems: list[str] = []
    warnings: list[str] = []
    all_rows: list[dict[str, Any]] = []
    def_rows: list[dict[str, Any]] = []
    for f in defs.flows:
        rows: list[dict[str, Any]] = []
        for seg in f.segments:
            try:
                rows += build_segment_rows(reader, book, defs, f, seg, problems)
            except TsError as e:
                problems.append(str(e))
        link = (
            link_flow(book, defs, f, rows)
            if rows
            else LinkResult("refused", "no rows", None, "not applicable: no rows", None, None, [])
        )
        if f.link_allowed and link.policy == "refused":
            warnings.append(f"{f.flow_id}: link allowed by flows.yaml but refused: {link.reason}")
        if not f.link_allowed and link.rules_met and "unstable" in (f.link_refused_reason or "").lower():
            problems.append(
                f"{f.flow_id}: the link refusal cites unstable overlap ratios but the plan s.2.5 rules hold in the "
                f"data ({link.rules}): state the real reason in flows.yaml"
            )
        rows += link.rows
        add_flags(f, rows)
        all_rows += rows
        periods = sorted({r["period"] for r in rows if r["variant"] == MAIN_VARIANT}, key=fy_start)
        ex = explanations.get(f.flow_id)
        def_rows.append(
            {
                "flow_id": f.flow_id,
                "name": f.name,
                "group": f.group,
                "tier": f.tier,
                "display_sign": f.display_sign,
                "check_class": f.check_class,
                "tol_abs": f.tol_abs,
                "tol_rel": f.tol_rel,
                "sam_terms": json.dumps([t.spec for t in f.sam_terms], sort_keys=True, ensure_ascii=False),
                "excluded_refs": ",".join(f.excluded_refs) or None,
                "sam_note": f.sam_note,
                "segments": json.dumps(
                    [
                        {
                            "code": s.code,
                            "dataset": s.dataset,
                            "base_year": s.base_year,
                            "variant": s.variant,
                            "from": s.lo,
                            "to": s.hi,
                            "terms": [{"series": t.label, "coef": t.coef, "from": t.lo, "to": t.hi} for t in s.terms],
                            "note": s.note,
                        }  # fmt: skip
                        for s in f.segments
                    ],
                    sort_keys=True,
                    ensure_ascii=False,
                ),
                "link_policy": link.policy,
                "link_reason": link.reason,
                "link_rules": link.rules,
                "link_ratio_2022_23": link.r22,
                "link_ratio_2023_24": link.r23,
                "n_rows": len(rows),
                "first_period": periods[0] if periods else None,
                "last_period": periods[-1] if periods else None,
                "explanation": None if ex is None else " ".join(str(ex["why"]).split()),
                "breaks": json.dumps([{"period": bp, "note": bn} for bp, bn in f.breaks]) if f.breaks else None,
            }
        )
    if problems:
        raise TsError("time series:\n  " + "\n  ".join(problems))
    df = pl.DataFrame(all_rows, schema=ROW_DTYPES, orient="row")
    dup = df.group_by(list(ROW_KEY), maintain_order=True).len().filter(pl.col("len") > 1)
    if dup.height:
        raise TsError(f"duplicate (flow_id, variant, base_year, period) rows:\n{dup.head(10)}")
    defs_df = pl.DataFrame(def_rows, schema=DEF_DTYPES, orient="row")
    tier = {f.flow_id: f.tier for f in defs.flows}
    cov = (
        df.filter(pl.col("variant") == MAIN_VARIANT)
        .sort(["flow_id", "period", "base_year"], nulls_last=True)
        .group_by(["flow_id", "period"], maintain_order=True)
        .agg(
            pl.len().cast(pl.Int64).alias("n_rows"),
            pl.col("base_year").fill_null("none").str.join(",").alias("base_years"),
            pl.col("segment").str.join(",").alias("segments"),
            pl.col("status").unique(maintain_order=True).sort().str.join(",").alias("statuses"),
        )
        .with_columns(pl.col("flow_id").replace_strict(tier, return_dtype=pl.String).alias("tier"))
        .select(list(COVERAGE_DTYPES))
    )
    prior, prior_src, bal = read_sam(layout)
    check = sam_check(reader, defs, df, explanations, prior, prior_src, bal)
    return TsResult(df, defs_df, cov, check, book.frame(), warnings)


def write(layout: Layout, res: TsResult) -> None:
    out = ts_dir(layout)
    with repo_lock(layout):
        out.mkdir(parents=True, exist_ok=True)
        for p in sorted(out.iterdir()):
            if p.is_file() and p.name not in OUT_FILES and not p.name.startswith("."):
                p.unlink()  # no orphaned outputs
        io.write_parquet(res.rows, out / "top_flows.parquet", sort_by=ROW_KEY)
        io.write_parquet(
            res.definitions,
            out / "top_flows_definitions.parquet",
            sort_by=("flow_id",),
            decimals={"link_ratio_2022_23": 12, "link_ratio_2023_24": 12, "tol_abs": 6, "tol_rel": 12},
        )
        io.write_parquet(res.coverage, out / "top_flows_coverage.parquet", sort_by=("flow_id", "period"))
        io.write_parquet(
            res.check, out / "top_flows_sam_check.parquet", sort_by=("flow_id",), decimals={"rel_diff": 12}
        )
        io.write_parquet(res.provenance, out / "_provenance.parquet", sort_by=("prov_id",))
        write_manifest(layout)


def cmd_timeseries(layout: Layout) -> int:
    try:
        res = build(layout)
    except TsError as e:
        print(f"timeseries FAILED (nothing written):\n{e}")
        return 1
    write(layout, res)
    r = res.rows
    main = r.filter(pl.col("variant") == MAIN_VARIANT)
    periods = sorted(set(main["period"].to_list()), key=fy_start)
    print(
        f"timeseries: {res.definitions.height} flows, {r.height} rows ({main.height} published, "
        f"{r.filter(pl.col('variant') == LINK_VARIANT).height} linked), {periods[0]}..{periods[-1]}, "
        f"{res.provenance.height} provenance records -> {ts_dir(layout)}"
    )
    linked = res.definitions.filter(pl.col("link_policy") == "linked")["flow_id"].to_list()
    print(f"   linked_2022_23 variant: {', '.join(linked) or 'none'}")
    policy = res.definitions.filter((pl.col("link_policy") == "refused") & pl.col("link_rules").str.starts_with("met"))
    if policy.height:
        print(f"   refused by flows.yaml although the plan s.2.5 data rules hold: {', '.join(policy['flow_id'])}")
    counts = res.check.group_by("verdict", maintain_order=True).len().sort("verdict")
    print("   2023-24 SAM check: " + ", ".join(f"{v} {n}" for v, n in counts.iter_rows()))
    for w in res.warnings:
        print(f"   WARNING: {w}")
    bad = res.check.filter(pl.col("verdict").is_in(["fail", "unexplained"]))
    for c in bad.iter_rows(named=True):
        print(
            f"   {c['verdict'].upper()} {c['flow_id']} ({c['check_class']}): TS {c['ts_value']:,.2f} SAM "
            f"{c['sam_balanced']:,.2f} residual {c['residual']:+,.2f} (tol {c['tolerance']:,.2f})"
        )
    print(f"manifest written: {layout.manifest}")
    return 0
