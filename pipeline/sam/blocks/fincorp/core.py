"""fincorp helpers: tracked numbers (value + the prov_ids it rests on), clean readers, the entry and satellite
collectors that register one provenance record per (ref, method) with exactly the inputs used, and key helpers.

Nothing here reads another block: that is `deps.py` (the integration boundary)."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import polars as pl

from pipeline.sam.framework import BlockContext, SamError, Satellite, entry

HH = ["H_R1", "H_R2", "H_R3", "H_R4", "H_R5", "H_U1", "H_U2", "H_U3", "H_U4", "H_U5"]
FC = ["E_RBI", "E_BANK", "E_NBFC", "E_INSP"]
NFC = ["E_NFPU", "E_NFPR"]
GOV = ["G_CEN", "G_STA"]
KFC = {"E_RBI": "K_RBI", "E_BANK": "K_BANK", "E_NBFC": "K_NBFC", "E_INSP": "K_INSP"}


# ---------------------------------------------------------------------------------------------
# tracked numbers
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Q:
    """A number and the provenance ids it was computed from. Arithmetic unions the ids, so the inputs of a
    record are exactly what its numbers used (no hand-kept input lists)."""

    v: float
    p: frozenset[str] = frozenset()

    @staticmethod
    def of(x: Q | float | int) -> Q:
        return x if isinstance(x, Q) else Q(float(x))

    def __add__(self, o: Q | float) -> Q:
        o = Q.of(o)
        return Q(self.v + o.v, self.p | o.p)

    __radd__ = __add__

    def __sub__(self, o: Q | float) -> Q:
        o = Q.of(o)
        return Q(self.v - o.v, self.p | o.p)

    def __rsub__(self, o: Q | float) -> Q:
        return Q.of(o) - self

    def __mul__(self, o: Q | float) -> Q:
        o = Q.of(o)
        return Q(self.v * o.v, self.p | o.p)

    __rmul__ = __mul__

    def __truediv__(self, o: Q | float) -> Q:
        o = Q.of(o)
        if o.v == 0:
            raise SamError(f"fincorp: division by zero (inputs {sorted(o.p)[:3]})")
        return Q(self.v / o.v, self.p | o.p)

    def __rtruediv__(self, o: Q | float) -> Q:
        return Q.of(o) / self

    def __neg__(self) -> Q:
        return Q(-self.v, self.p)

    def __float__(self) -> float:
        return self.v

    def __repr__(self) -> str:
        return f"Q({self.v:,.4f}, {len(self.p)} inputs)"


def qsum(xs: Iterable[Q | float]) -> Q:
    out = Q(0.0)
    for x in xs:
        out = out + x
    return out


def shares(levels: Mapping[str, Q]) -> dict[str, Q]:
    """Normalise non-negative levels to shares (each share carries the inputs of every level)."""
    tot = qsum(levels.values())
    if tot.v <= 0:
        raise SamError(f"fincorp: cannot normalise levels with total {tot.v} ({list(levels)})")
    bad = [k for k, x in levels.items() if x.v < 0]
    if bad:
        raise SamError(f"fincorp: negative levels in a key: {bad}")
    return {k: Q(x.v / tot.v, x.p | tot.p) for k, x in levels.items()}


def split(total: Q, key: Mapping[str, Q]) -> dict[str, Q]:
    return {k: total * s for k, s in shares(key).items()}


# ---------------------------------------------------------------------------------------------
# clean readers
# ---------------------------------------------------------------------------------------------


@dataclass
class Reader:
    """ctx.value / ctx.rows returning Q. Every multi-vintage dataset is read with a named vintage."""

    ctx: BlockContext

    def v(
        self,
        dataset: str,
        series_id: str,
        *,
        vintage: str = "latest",
        period: str | None = None,
        unit: str | None = "INR_crore",
    ) -> Q:
        basis = "current" if unit == "INR_crore" else None  # percent / ratio rows carry price_basis 'n/a'
        val, pid = self.ctx.value(
            dataset, series_id, period=period or self.ctx.year, vintage=vintage, unit=unit, price_basis=basis
        )
        return Q(val, frozenset({pid}))

    def pct(self, dataset: str, series_id: str, *, vintage: str = "latest", period: str | None = None) -> Q:
        """A percent series as a fraction (x / 100)."""
        q = self.v(dataset, series_id, vintage=vintage, period=period, unit="percent")
        return Q(q.v / 100.0, q.p)

    def avg(
        self,
        dataset: str,
        series_id: str,
        periods: Sequence[str],
        *,
        vintage: str = "latest",
        unit: str | None = "INR_crore",
    ) -> Q:
        """Average of a stock over several dates (e.g. end-March 2023 and 2024)."""
        vals = [self.v(dataset, series_id, vintage=vintage, period=p, unit=unit) for p in periods]
        return qsum(vals) / float(len(vals))

    def sum(self, dataset: str, series_ids: Sequence[str], *, vintage: str = "latest") -> Q:
        return qsum(self.v(dataset, s, vintage=vintage) for s in series_ids)


# ---------------------------------------------------------------------------------------------
# collectors: entries and satellites, one provenance record per (ref, method key)
# ---------------------------------------------------------------------------------------------


@dataclass
class Method:
    ref: str
    status: str
    text: str
    source_id: str | None = None
    notes: str | None = None


@dataclass
class Out:
    """Collects entries (with tracked values) and registers their provenance records at the end.

    `method(key, ref, status, text)` declares a record; `add(..., key=)` files an entry under it. The record's
    inputs are the union of the prov_ids of every value filed under it."""

    ctx: BlockContext
    methods: dict[str, Method] = field(default_factory=dict)
    items: list[dict[str, Any]] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)

    def method(
        self, key: str, ref: str, status: str, text: str, *, source_id: str | None = None, notes: str | None = None
    ) -> None:
        if key in self.methods:
            raise SamError(f"fincorp: method key {key!r} declared twice")
        self.methods[key] = Method(ref, status, text, source_id, notes)

    def add(
        self,
        row: str,
        col: str,
        comp: str,
        q: Q,
        *,
        key: str,
        role: str,
        confidence: str | None = None,
        tol_rel: float | None = None,
        note: str | None = None,
        sign: int = 1,
    ) -> None:
        """File one entry. `sign` is the sign the flow must have (+1: a payment; -1: e.g. a negative net
        flow). A zero value is dropped (a structural zero is absent) and listed; a value of the wrong sign fails."""
        if key not in self.methods:
            raise SamError(f"fincorp: entry filed under undeclared method {key!r}")
        if not math.isfinite(q.v):
            raise SamError(f"fincorp: non-finite value for {row}<-{col} {comp}")
        if abs(q.v) < 1e-9:
            self.dropped.append(f"{self.methods[key].ref} {row}<-{col} [{comp}] = 0")
            return
        if q.v * sign < 0:
            raise SamError(f"fincorp: {self.methods[key].ref} {row}<-{col} [{comp}] has the wrong sign: {q.v:,.4f}")
        self.items.append(
            dict(
                row=row, col=col, comp=comp, q=q, key=key, role=role, confidence=confidence, tol_rel=tol_rel, note=note
            )
        )

    def total(
        self,
        *,
        ref: str | None = None,
        rows: Iterable[str] | None = None,
        cols: Iterable[str] | None = None,
        comps: Iterable[str] | None = None,
    ) -> Q:
        rs, cs, ks = (set(x) if x is not None else None for x in (rows, cols, comps))
        return qsum(
            i["q"]
            for i in self.items
            if (ref is None or self.methods[i["key"]].ref == ref)
            and (rs is None or i["row"] in rs)
            and (cs is None or i["col"] in cs)
            and (ks is None or i["comp"] in ks)
        )

    def records(self) -> dict[str, str]:
        """Register one record per used method key; returns key -> prov_id (unused keys are not registered)."""
        used: dict[str, set[str]] = {}
        for i in self.items:
            used.setdefault(i["key"], set()).update(i["q"].p)
        return {k: register(self.ctx, self.methods[k], used[k]) for k in sorted(used)}

    def entries(self) -> list[dict[str, Any]]:
        pids = self.records()
        out = []
        for i in self.items:
            m = self.methods[i["key"]]
            out.append(
                entry(
                    i["row"],
                    i["col"],
                    m.ref,
                    i["q"].v,
                    prov_id=pids[i["key"]],
                    status=m.status,
                    role=i["role"],
                    component=i["comp"],
                    tol_rel=i["tol_rel"],
                    confidence=i["confidence"],
                    note=i["note"],
                )
            )
        return out


def register(ctx: BlockContext, m: Method, inputs: Iterable[str]) -> str:
    ins = sorted(set(inputs))
    source_id = m.source_id
    if source_id is None:
        srcs = sorted({str(r.get("source_id")) for r in (ctx.lookup_prov(i) for i in ins) if r and r.get("source_id")})
        if len(srcs) > 1:
            source_id = _main_source(ctx, ins)
    return ctx.prov(ref=m.ref, status=m.status, method=m.text, inputs=ins, source_id=source_id, notes=m.notes)


def _main_source(ctx: BlockContext, inputs: Sequence[str]) -> str:
    """With inputs from several sources, the record's source is the most frequent clean source among them
    (ties: alphabetical); SAM inputs count by their own source_id."""
    counts: dict[str, int] = {}
    for i in inputs:
        r = ctx.lookup_prov(i)
        if r and r.get("source_id"):
            counts[str(r["source_id"])] = counts.get(str(r["source_id"]), 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


@dataclass
class SatOut:
    """A satellite built row by row with tracked values; one record per method key."""

    ctx: BlockContext
    ref: str
    dims: list[str]
    methods: dict[str, Method] = field(default_factory=dict)
    rows: list[dict[str, Any]] = field(default_factory=list)

    def method(self, key: str, status: str, text: str, *, source_id: str | None = None) -> None:
        self.methods[key] = Method(self.ref, status, text, source_id)

    def add(self, series_id: str, q: Q, *, key: str, unit: str = "INR_crore", **dims: str | None) -> None:
        if not math.isfinite(q.v):
            raise SamError(f"fincorp satellite {series_id}: non-finite value")
        self.rows.append(dict(series_id=series_id, q=q, key=key, unit=unit, dims=dims))

    def build(self, description: str, decimals: int = 9) -> Satellite:
        used: dict[str, set[str]] = {}
        for r in self.rows:
            used.setdefault(r["key"], set()).update(r["q"].p)
        pids = {k: register(self.ctx, self.methods[k], used[k]) for k in sorted(used)}
        recs = [
            {
                "series_id": r["series_id"],
                **{d: r["dims"].get(d) for d in self.dims},
                "value": float(r["q"].v),
                "unit": r["unit"],
                "status": self.methods[r["key"]].status,
                "prov_id": pids[r["key"]],
            }
            for r in self.rows
        ]
        schema = {
            "series_id": pl.String(),
            **{d: pl.String() for d in self.dims},
            "value": pl.Float64(),
            "unit": pl.String(),
            "status": pl.String(),
            "prov_id": pl.String(),
        }
        df = pl.DataFrame(recs, schema=schema, orient="row").sort("series_id")
        return Satellite(self.ref, df, description, decimals=decimals)
