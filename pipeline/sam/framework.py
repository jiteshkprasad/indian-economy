"""The block framework: what a SAM block is, what it may read, what it returns, and how it is checked.

A block is a module `pipeline/sam/blocks/<block>.py` (or a package `pipeline/sam/blocks/<block>/`):

    BLOCK = "<block>"                 # == module name, one of accounts.OWNERSHIP
    REFS = ["P1", ...]                # gap-map refs it implements; a subset of OWNERSHIP[BLOCK]
    DEPENDS = ["production", ...]     # blocks whose outputs build() reads; a subset of BLOCK_DEPENDS[BLOCK]
    def build(ctx: BlockContext) -> BlockResult: ...

build(ctx) reads clean data (ctx.value / ctx.rows / ctx.frame), committed concordances
(ctx.concordance) and the outputs of its DEPENDS (ctx.block_entries / ctx.satellite), registers a
provenance record for every number it writes (ctx.prov) and returns entries, constraints,
satellites and control-total checks. The framework validates everything (validate_result) and writes
data/sam/<year>/blocks/<block>_*.parquet deterministically through pipeline/core/io.

The how-to with examples is docs/phase2/SAM_GUIDE.md; the working template is blocks/production.py.
"""

from __future__ import annotations

import importlib
import json
import math
import pkgutil
import shutil
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import pandera.errors as pa_errors
import polars as pl

from pipeline.core import io
from pipeline.core.manifest import repo_lock
from pipeline.core.paths import Layout
from pipeline.core.registry import source_ids
from pipeline.core.schema import PROV_DTYPES, PROV_ID_RE, PROV_SCHEMA
from pipeline.core.units import UNITS, vintage_end, vintage_problem
from pipeline.sam import spec
from pipeline.sam.accounts import BLOCK_DEPENDS, OWNERSHIP, SAM_DIR, Accounts, gap_map

BLOCKS_PACKAGE = "pipeline.sam.blocks"
BLOCKS_DIR = SAM_DIR / "blocks"


class SamError(RuntimeError):
    """A block or a SAM output breaks the contract. The message lists every problem found."""


# ---------------------------------------------------------------------------------------------
# where things live
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SamPaths:
    """Every SAM output path (DESIGN_BRIEF s.6)."""

    layout: Layout
    year: str = spec.YEAR

    @property
    def root(self) -> Path:
        return self.layout.sam / self.year

    @property
    def blocks(self) -> Path:
        return self.root / "blocks"

    def entries(self, block: str) -> Path:
        return self.blocks / f"{block}_entries.parquet"

    def constraints(self, block: str) -> Path:
        return self.blocks / f"{block}_constraints.parquet"

    def checks(self, block: str) -> Path:
        return self.blocks / f"{block}_checks.parquet"

    def provenance(self, block: str) -> Path:
        return self.blocks / f"{block}_provenance.parquet"

    def catalog(self, block: str) -> Path:
        return self.blocks / f"{block}_block.json"

    def satellites(self, block: str) -> Path:
        return self.blocks / f"{block}_satellites"

    def built(self, block: str) -> bool:
        return self.catalog(block).exists() and self.entries(block).exists()

    @property
    def provenance_all(self) -> Path:
        return self.root / "_provenance.parquet"

    # assembly and balancing
    prior_entries = property(lambda self: self.root / "sam_entries_prior.parquet")
    prior_cells = property(lambda self: self.root / "sam_prior.parquet")
    diagnostics = property(lambda self: self.root / "prior_diagnostics.parquet")
    constraints_all = property(lambda self: self.root / "constraints.parquet")
    balanced_entries = property(lambda self: self.root / "sam_entries_balanced.parquet")
    balanced_cells = property(lambda self: self.root / "sam_balanced.parquet")
    matrix_csv = property(lambda self: self.root / "sam_balanced_matrix.csv")
    log = property(lambda self: self.root / "balancing_log.parquet")
    constraint_status = property(lambda self: self.root / "balancing_constraints.parquet")
    run_json = property(lambda self: self.root / "balancing_run.json")


# ---------------------------------------------------------------------------------------------
# what a block returns
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Satellite:
    """A memo table outside the SAM (DESIGN_BRIEF s.3): series_id (unique), any String dims, value,
    unit (pipeline.core.units.UNITS), status, prov_id. `ref` is the gap-map ref it implements.
    `decimals` (6..12) is the rounding of `value` on write: raise it for small shares (a 0.05% share keeps
    only 3 significant digits at 6 decimals)."""

    ref: str
    df: pl.DataFrame
    description: str
    decimals: int = 6


@dataclass
class BlockResult:
    """What build(ctx) returns. entries/constraints: a list of dicts (use `entry()` / `constraint()`)
    or a polars DataFrame with the spec columns. Control-total checks are recorded with ctx.check()."""

    entries: list[dict[str, Any]] | pl.DataFrame = field(default_factory=list)
    constraints: list[dict[str, Any]] | pl.DataFrame = field(default_factory=list)
    satellites: dict[str, Satellite] = field(default_factory=dict)


def entry(
    row: str,
    col: str,
    ref: str,
    value: float,
    *,
    prov_id: str,
    status: str,
    role: str,
    component: str = "total",
    tol_rel: float | None = None,
    confidence: str | None = None,
    bop_function: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """One SAM sub-cell: `row` receives from `col` (DESIGN_BRIEF s.3). Validated when the block returns."""
    return {
        "row": row,
        "col": col,
        "ref": ref,
        "component": component,
        "value": float(value),
        "status": status,
        "role": role,
        "tol_rel": None if tol_rel is None else float(tol_rel),
        "confidence": confidence,
        "bop_function": bop_function,
        "prov_id": prov_id,
        "note": note,
    }


def constraint(
    constraint_id: str,
    ref: str,
    rows: Sequence[str],
    cols: Sequence[str],
    target: float,
    *,
    prov_id: str,
    description: str,
    tol_abs: float = 0.0,
    tol_rel: float = 0.0,
    kind: str = "equal",
    refs: Sequence[str] | None = None,
    components: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Sum of entries with row in `rows` and col in `cols` (and ref in `refs`, component in `components`,
    if given) must lie in target +- max(tol_abs, tol_rel*|target|). Balancing enforces it (a conflict
    shows as minimum slack from phase 1)."""
    return {
        "constraint_id": constraint_id,
        "ref": ref,
        "rows": list(rows),
        "cols": list(cols),
        "refs": None if refs is None else list(refs),
        "components": None if components is None else list(components),
        "target": float(target),
        "tol_abs": float(tol_abs),
        "tol_rel": float(tol_rel),
        "kind": kind,
        "prov_id": prov_id,
        "description": description,
    }


# ---------------------------------------------------------------------------------------------
# reading clean data
# ---------------------------------------------------------------------------------------------


class CleanIndex:
    """Which unit owns which clean dataset, and the clean provenance records (read lazily)."""

    def __init__(self, layout: Layout) -> None:
        self.layout = layout
        self._datasets: dict[str, str] | None = None
        self._prov: dict[str, dict[str, Any]] | None = None

    @property
    def datasets(self) -> dict[str, str]:
        if self._datasets is None:
            out: dict[str, str] = {}
            if self.layout.clean.exists():
                for cat in sorted(self.layout.clean.glob("*/_datasets.json")):
                    if cat.parent.name.startswith("."):
                        continue
                    for name in sorted(json.loads(cat.read_text(encoding="utf-8"))):
                        out[name] = cat.parent.name
            self._datasets = out
        return self._datasets

    def path(self, dataset: str) -> Path:
        unit = self.datasets.get(dataset)
        if unit is None:
            raise SamError(f"clean dataset {dataset!r} not found under {self.layout.clean} (is its unit built?)")
        return self.layout.clean / unit / f"{dataset}.parquet"

    def prov(self, prov_id: str) -> dict[str, Any] | None:
        if self._prov is None:
            recs: dict[str, dict[str, Any]] = {}
            for f in sorted(self.layout.clean.glob("*/_provenance.parquet")) if self.layout.clean.exists() else []:
                if f.parent.name.startswith("."):
                    continue
                for r in pl.read_parquet(f, columns=["prov_id", "status", "vintage", "source_id"]).iter_rows(
                    named=True
                ):
                    recs[r["prov_id"]] = r
            self._prov = recs
        return self._prov.get(prov_id)


def select_vintage(df: pl.DataFrame, vintage: str | None, what: str) -> pl.DataFrame:
    """vintage=None: the rows must carry a single vintage; a date string: exactly that vintage;
    'latest': the latest vintage of each (series, period) (an explicit choice the caller makes and states;
    per period, so a series whose older periods come only from older releases keeps them)."""
    if df.height == 0:
        return df
    if vintage is None:
        vs = sorted(set(df["vintage"].to_list()))
        if len(vs) > 1:
            raise SamError(f"{what}: several vintages {vs}; pass vintage=<date> or vintage='latest'")
        return df
    if vintage == "latest":
        keys = [k for k in ("series_id", "period") if k in df.columns]
        # order vintages as ctx.prov does: by the latest date they can mean ('2026' is 2026-12-31), then by text
        order = sorted(set(df["vintage"].to_list()), key=lambda v: (vintage_end(v), v))
        rank = {v: i for i, v in enumerate(order)}
        ranked = df.with_columns(pl.col("vintage").replace_strict(rank, return_dtype=pl.Int64).alias("_r"))
        latest = ranked.group_by(keys, maintain_order=True).agg(pl.col("_r").max().alias("_m"))
        return (
            ranked.join(latest, on=keys, how="inner", maintain_order="left")
            .filter(pl.col("_r") == pl.col("_m"))
            .drop("_r", "_m")
        )
    return df.filter(pl.col("vintage") == vintage)


# ---------------------------------------------------------------------------------------------
# the context a block receives
# ---------------------------------------------------------------------------------------------


@dataclass
class BlockContext:
    """Given to build(ctx). Everything a block reads and every provenance record goes through here."""

    block: str
    refs: tuple[str, ...]
    depends: tuple[str, ...]
    layout: Layout
    year: str = spec.YEAR
    accounts: Accounts = field(default_factory=Accounts.load)
    provenance: dict[str, dict[str, Any]] = field(default_factory=dict)
    checks: list[dict[str, Any]] = field(default_factory=list)
    log_lines: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    datasets_read: set[str] = field(default_factory=set)
    concordances_read: dict[str, str] = field(default_factory=dict)
    prov_ref: dict[str, str] = field(default_factory=dict)  # own prov_id -> the gap-map ref it was registered for
    _clean: CleanIndex | None = None
    _frames: dict[str, pl.DataFrame] = field(default_factory=dict)
    _dep_prov: dict[str, dict[str, Any]] | None = None
    _read_units: dict[str, set[tuple[str, str]]] = field(default_factory=dict)  # clean prov_id -> (unit, basis) read

    # --- logging ------------------------------------------------------------------------------
    def log(self, msg: str) -> None:
        print(f"[sam_{self.block}] {msg}")
        self.log_lines.append(msg)

    def warn(self, msg: str) -> None:
        """Something a human must look at. Also write it in docs/phase2/issues/<block>.md (no silent fallbacks)."""
        print(f"[sam_{self.block}] WARNING: {msg}")
        self.warnings.append(msg)

    @property
    def paths(self) -> SamPaths:
        return SamPaths(self.layout, self.year)

    @property
    def clean_index(self) -> CleanIndex:
        if self._clean is None:
            self._clean = CleanIndex(self.layout)
        return self._clean

    # --- clean data ---------------------------------------------------------------------------
    def frame(self, dataset: str) -> pl.DataFrame:
        """A whole clean table (all periods and vintages). Prefer ctx.rows() / ctx.value()."""
        if dataset not in self._frames:
            self._frames[dataset] = pl.read_parquet(self.clean_index.path(dataset))
            self.datasets_read.add(dataset)
        return self._frames[dataset]

    def rows(
        self,
        dataset: str,
        *,
        series_id: str | Sequence[str] | None = None,
        period: str | None = spec.YEAR,
        vintage: str | None = None,
        unit: str | None = "INR_crore",
        price_basis: str | None = "current",
        allow_empty: bool = False,
        **dims: str | Sequence[str],
    ) -> pl.DataFrame:
        """Rows of a clean dataset for `period` (None = all periods), filtered by series_id and by any
        clean column (item_code='ce', industry=[...], ...). Vintage: see select_vintage().

        Fails loudly (no silent empties): a series_id, dimension value, period or explicit vintage that the
        dataset does not have, or an empty result (unless allow_empty=True). Units: every row returned must
        be `unit` (default INR_crore) at `price_basis` (default current prices); to read US$, percent or
        constant-price rows name them (unit='USD_million', price_basis='constant_2022_23'), or pass None to
        accept any, and convert explicitly."""
        full = self.frame(dataset)
        df = full
        what = f"{dataset} {series_id or dims or ''} {period}"
        if period is not None:
            df = df.filter(pl.col("period") == period)
            if df.height == 0 and not allow_empty:
                ps = sorted(set(full["period"].to_list()))
                raise SamError(f"{dataset}: no rows for period {period!r} (periods {ps[:3]} ... {ps[-3:]})")
        if series_id is not None:
            ids = [series_id] if isinstance(series_id, str) else list(series_id)
            missing = sorted(set(ids) - set(full["series_id"].unique().to_list()))
            if missing:
                raise SamError(f"{dataset}: series_id(s) not in the dataset: {missing[:10]}")
            df = df.filter(pl.col("series_id").is_in(ids))
        for col, val in dims.items():
            if col not in df.columns:
                raise SamError(f"{dataset}: no column {col!r}")
            vals = [val] if isinstance(val, str) else list(val)
            missing = sorted(set(vals) - set(full[col].drop_nulls().unique().to_list()))
            if missing:
                raise SamError(f"{dataset}: {col} value(s) not in the dataset: {missing[:10]}")
            df = df.filter(pl.col(col).is_in(vals))
        if vintage not in (None, "latest") and df.height and vintage not in set(df["vintage"].to_list()):
            raise SamError(f"{what}: vintage {vintage!r} not found (vintages: {sorted(set(df['vintage']))})")
        df = select_vintage(df, vintage, what)
        if df.height == 0 and not allow_empty:
            raise SamError(f"{what}: no rows match (pass allow_empty=True if an empty result is expected)")
        for col, want in (("unit", unit), ("price_basis", price_basis)):
            if want is not None and df.height:
                bad = sorted(set(df[col].to_list()) - {want})
                if bad:
                    raise SamError(
                        f"{what}: rows in {col} {bad} (expected {want!r}); filter them out, or pass {col}=<that "
                        f"{col}> (or None) and convert explicitly (cite the rate's prov_id)"
                    )
        if df.height:
            for pid, u, pb in df.select("prov_id", "unit", "price_basis").unique(maintain_order=True).iter_rows():
                self._read_units.setdefault(pid, set()).add((u, pb))
        return df

    def value(
        self,
        dataset: str,
        series_id: str,
        period: str = spec.YEAR,
        vintage: str | None = None,
        *,
        unit: str | None = "INR_crore",
        price_basis: str | None = "current",
    ) -> tuple[float, str]:
        """One number and its clean prov_id. Fails unless exactly one row matches (name the vintage
        if the series has several: a date or 'latest'), and unless it is `unit` at `price_basis`
        (defaults: INR_crore, current prices; see rows())."""
        df = self.rows(dataset, series_id=series_id, period=period, vintage=vintage, unit=unit,
                       price_basis=price_basis, allow_empty=True)  # fmt: skip
        if df.height != 1:
            raise SamError(
                f"{dataset}/{series_id} {period} (vintage {vintage}): {df.height} rows match, need exactly 1"
            )
        return float(df["value"][0]), str(df["prov_id"][0])

    def concordance(self, name: str) -> pl.DataFrame:
        """A committed concordance, data/concordance/<name>.csv (all columns as strings). Its sha256 is
        recorded in the block catalog; cite it in the method text of records that use it."""
        p = self.layout.concordance / f"{name}.csv"
        if not p.exists():
            raise SamError(f"concordance {p} does not exist")
        self.concordances_read[name] = io.sha256_file(p)
        return pl.read_csv(p, infer_schema=False)

    # --- other blocks -------------------------------------------------------------------------
    def _need(self, block: str) -> None:
        if block not in self.depends:
            raise SamError(f"{self.block}: reading block {block!r} requires DEPENDS = [..., {block!r}]")
        if not self.paths.built(block):
            raise SamError(f"{self.block}: block {block!r} is not built (run `sam {block}` first)")

    def block_entries(self, block: str) -> pl.DataFrame:
        """The validated entries a dependency block wrote (columns of spec.ENTRY_DTYPES + block)."""
        self._need(block)
        return pl.read_parquet(self.paths.entries(block))

    def block_constraints(self, block: str) -> pl.DataFrame:
        self._need(block)
        return pl.read_parquet(self.paths.constraints(block))

    def satellite(self, block: str, name: str) -> pl.DataFrame:
        """A dependency block's satellite table (e.g. households' `hh_keys`)."""
        self._need(block)
        p = self.paths.satellites(block) / f"{name}.parquet"
        if not p.exists():
            raise SamError(f"{block} has no satellite {name!r}")
        return pl.read_parquet(p)

    # --- provenance ---------------------------------------------------------------------------
    def _dependency_prov(self) -> dict[str, dict[str, Any]]:
        if self._dep_prov is None:
            recs: dict[str, dict[str, Any]] = {}
            for b in self.depends:
                p = self.paths.provenance(b)
                if p.exists():
                    for r in pl.read_parquet(p).iter_rows(named=True):
                        recs[r["prov_id"]] = r
            self._dep_prov = recs
        return self._dep_prov

    def lookup_prov(self, prov_id: str) -> dict[str, Any] | None:
        """A provenance record this block may cite: its own, a DEPENDS block's, or any clean record."""
        return self.provenance.get(prov_id) or self._dependency_prov().get(prov_id) or self.clean_index.prov(prov_id)

    def prov(
        self,
        *,
        ref: str,
        method: str,
        status: str,
        inputs: Iterable[str] = (),
        notes: str | None = None,
        source_id: str | None = None,
        table_id: str | None = None,
        locator: str | None = None,
        vintage: str | None = None,
        release: str | None = None,
        unit_as_published: str = "Rs crore",
        conversion: str = "none",
        price_basis: str = "current",
        base_year: str | None = spec.BASE_YEAR,
    ) -> str:
        """Register one SAM provenance record and return its prov_id ('sam_<block>:<12 hex>').

        ref: the gap-map ref the numbers implement. method: plain words, precise enough to reproduce
        (cite the gap-map ref, the concordance and any assumption). status: 'official' (pure
        aggregation of official numbers: every input must be official), 'derived' (arithmetic on
        official numbers) or 'estimated' (modelled; needs inputs or notes naming the assumption).
        inputs: the clean / SAM prov_ids the numbers are computed from. source_id defaults to the
        source of the inputs when they all share one (inputs from several sources: pass the one the numbers
        mainly rest on, which must be among them unless `notes` say why); with no inputs, to the gap map's
        primary source of `ref`. vintage defaults to the latest vintage among the inputs. `ref` is any
        gap-map ref, but an entry or satellite may only cite a record made for its own ref (a record for
        another block's ref can back a constraint or a check). An 'official' record over clean inputs
        read in another unit or at constant prices needs `conversion` stated.
        The id is a hash of the record, so the same call returns the same id.
        """
        problems: list[str] = []
        gm = gap_map(str(self.layout.gap_map))
        if ref not in gm:
            problems.append(f"ref {ref!r} is not in data/gap_map.csv")
        if status not in spec.STATUSES:
            problems.append(f"status must be one of {spec.STATUSES}, got {status!r}")
        if not (method and method.strip()):
            problems.append("every SAM provenance record needs a method (plain words)")
        ins = sorted(set(inputs))
        recs = []
        for i in ins:
            r = self.lookup_prov(i)
            if r is None:
                problems.append(f"input {i!r} does not resolve (not a clean, own or DEPENDS-block prov_id)")
            else:
                recs.append(r)
        if status == "official" and any(r["status"] != "official" for r in recs):
            bad = [r["prov_id"] for r in recs if r["status"] != "official"]
            problems.append(f"an 'official' record may only aggregate official inputs; not official: {bad[:5]}")
        if status == "official" and not ins:
            problems.append("an 'official' SAM record needs the official inputs it aggregates")
        if status == "derived" and not ins:
            problems.append("a 'derived' record needs inputs (the prov_ids it is computed from)")
        if status == "estimated" and not ins and not (notes and notes.strip()):
            problems.append("an 'estimated' record needs inputs or notes naming the assumption it rests on")
        if vintage is None:
            vs = [r["vintage"] for r in recs if r.get("vintage")]
            if not vs:
                problems.append("no inputs to take a vintage from: pass vintage='YYYY-MM-DD'")
            else:
                vintage = max(vs, key=lambda v: (vintage_end(v), v))
        elif why := vintage_problem(vintage):
            problems.append(f"vintage {vintage!r}: {why}")
        in_sources = sorted({str(r.get("source_id")) for r in recs if r.get("source_id")})
        if source_id is None:
            if len(in_sources) == 1:
                source_id = in_sources[0]
            elif len(in_sources) > 1:
                problems.append(
                    f"inputs come from several sources {in_sources}: pass source_id= (the one the numbers mainly "
                    "rest on)"
                )
            elif ref in gm:
                source_id = gm[ref]["primary_source_id"]
        elif in_sources and source_id not in in_sources and not (notes and notes.strip()):
            problems.append(
                f"source_id {source_id!r} is not the source of any input ({in_sources}); use one of them or say "
                "why in notes"
            )
        if source_id is not None and source_id not in source_ids(self.layout):
            problems.append(f"source_id {source_id!r} is not in the registry")
        if status == "official" and conversion == "none":
            odd = sorted(i for i in ins if any(u != ("INR_crore", "current") for u in self._read_units.get(i, set())))
            if odd:
                problems.append(
                    f"inputs {odd[:5]} were read in another unit or at constant prices: state the conversion "
                    "(conversion=...)"
                )
        if problems:
            raise SamError(f"sam_{self.block}: prov(ref={ref}) rejected:\n  " + "\n  ".join(problems))
        rec: dict[str, Any] = {
            "ingest_unit": f"sam_{self.block}",
            "source_id": source_id,
            "url": None,
            "raw_path": None,
            "raw_sha256": None,
            "retrieved_at": None,
            "table_id": table_id or f"SAM {self.year} gap-map {ref}",
            "locator": locator or f"data/sam/{self.year}/blocks/{self.block}_*.parquet, ref {ref}",
            "unit_as_published": unit_as_published,
            "conversion": conversion,
            "price_basis": price_basis,
            "base_year": base_year,
            "vintage": vintage,
            "release": release or f"India SAM {self.year}, block {self.block}",
            "status": status,
            "method": method.strip(),
            "inputs": ",".join(ins) or None,
            "notes": notes,
        }
        pid = f"sam_{self.block}:{io.sha256_bytes(io.dumps_json(rec, indent=None).encode())[:12]}"
        if self.prov_ref.get(pid, ref) != ref:
            raise SamError(
                f"sam_{self.block}: the same record was registered for refs {self.prov_ref[pid]} and {ref}: give each "
                "ref its own method text"
            )
        self.provenance[pid] = {"prov_id": pid, **rec}
        self.prov_ref[pid] = ref
        return pid

    # --- control totals -----------------------------------------------------------------------
    def check(
        self,
        check_id: str,
        description: str,
        sam_value: float,
        target: float,
        *,
        target_prov_id: str,
        tol_abs: float,
    ) -> bool:
        """Record a control-total comparison (a SAM total vs an official figure read from clean data).
        A failed check is a warning here and must be logged in docs/phase2/issues/<block>.md; block tests
        assert that the checks they care about pass."""
        diff = float(sam_value) - float(target)
        ok = abs(diff) <= tol_abs
        self.checks.append(
            {
                "check_id": check_id,
                "description": description,
                "sam_value": float(sam_value),
                "target": float(target),
                "diff": diff,
                "tol_abs": float(tol_abs),
                "ok": ok,
                "target_prov_id": target_prov_id,
            }
        )
        msg = f"check {check_id}: SAM {sam_value:,.2f} vs {target:,.2f} (diff {diff:+,.2f}, tol {tol_abs:,.2f})"
        self.log(msg) if ok else self.warn(msg + " FAILED")
        return ok


# ---------------------------------------------------------------------------------------------
# discovery and contract
# ---------------------------------------------------------------------------------------------


def block_names() -> list[str]:
    """Block modules/packages in pipeline/sam/blocks (without importing them)."""
    return sorted(m.name for m in pkgutil.iter_modules([str(BLOCKS_DIR)]) if not m.name.startswith("_"))


def load_block(name: str) -> ModuleType:
    if not spec.BLOCK_RE.match(name):
        raise SamError(f"bad block name {name!r}")
    if name not in block_names():
        raise SamError(f"no block {name!r} in pipeline/sam/blocks (known: {', '.join(block_names()) or 'none'})")
    mod = importlib.import_module(f"{BLOCKS_PACKAGE}.{name}")
    check_contract(mod, name)
    return mod


def check_contract(mod: ModuleType, name: str | None = None, layout: Layout | None = None) -> None:
    """BLOCK, REFS, DEPENDS and build() exist and agree with the ownership table (DESIGN_BRIEF s.4)."""
    layout = layout or Layout.default()
    name = name or getattr(mod, "BLOCK", None)
    problems: list[str] = []
    if getattr(mod, "BLOCK", None) != name:
        problems.append(f"BLOCK must be {name!r} (the module name), got {getattr(mod, 'BLOCK', None)!r}")
    if name not in OWNERSHIP:
        problems.append(
            f"{name!r} is not a block of DESIGN_BRIEF s.4 ({', '.join(OWNERSHIP)}); a new block needs a "
            "FRAMEWORK_REQUESTS.md entry"
        )
    refs = getattr(mod, "REFS", None)
    gm = gap_map(str(layout.gap_map))
    if not isinstance(refs, (list, tuple)) or not refs or not all(isinstance(r, str) for r in refs):
        problems.append("REFS must be a non-empty list of gap-map refs")
    else:
        if len(set(refs)) != len(refs):
            problems.append("REFS lists a ref twice")
        for r in refs:
            if r not in gm:
                problems.append(f"ref {r!r} is not in data/gap_map.csv")
            elif name in OWNERSHIP and r not in OWNERSHIP[name]:
                owner = next((b for b, rs in OWNERSHIP.items() if r in rs), None)
                problems.append(f"ref {r} is owned by block {owner!r}, not {name!r} (DESIGN_BRIEF s.4)")
    deps = getattr(mod, "DEPENDS", [])
    if not isinstance(deps, (list, tuple)) or not all(isinstance(d, str) for d in deps):
        problems.append("DEPENDS must be a list of block names")
    elif name in OWNERSHIP:
        extra = [d for d in deps if d not in BLOCK_DEPENDS[name]]
        if extra:
            problems.append(
                f"DEPENDS {extra} not allowed for {name} by DESIGN_BRIEF s.4 (allowed: {list(BLOCK_DEPENDS[name])}); "
                "file a FRAMEWORK_REQUESTS.md entry"
            )
    if not callable(getattr(mod, "build", None)):
        problems.append("missing function build(ctx)")
    if problems:
        raise SamError(f"block {name}: " + "; ".join(problems))


def check_ref_ownership(modules: dict[str, ModuleType]) -> None:
    """Across the discovered blocks: no ref may be claimed twice."""
    seen: dict[str, str] = {}
    problems = []
    for name, mod in sorted(modules.items()):
        for r in getattr(mod, "REFS", []):
            if r in seen:
                problems.append(f"ref {r} is claimed by both {seen[r]} and {name}")
            seen[r] = name
    if problems:
        raise SamError("; ".join(problems))


def block_order(names: Sequence[str], deps: dict[str, Sequence[str]]) -> list[str]:
    """Dependencies first; ties alphabetical. Raises on a cycle."""
    order: list[str] = []
    state: dict[str, int] = {}

    def visit(n: str, path: tuple[str, ...]) -> None:
        if state.get(n) == 2 or n not in deps:
            return
        if state.get(n) == 1:
            raise SamError("DEPENDS cycle: " + " -> ".join((*path, n)))
        state[n] = 1
        for d in sorted(deps[n]):
            visit(d, (*path, n))
        state[n] = 2
        order.append(n)

    for n in sorted(names):
        visit(n, ())
    return order


# ---------------------------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------------------------


def _frame(data: list[dict[str, Any]] | pl.DataFrame, dtypes: dict[str, pl.DataType], what: str) -> pl.DataFrame:
    if isinstance(data, pl.DataFrame):
        df = data
    else:
        if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
            raise SamError(f"{what}: must be a list of dicts or a polars DataFrame")
        extra = sorted({k for r in data for k in r} - set(dtypes))
        if extra:
            raise SamError(f"{what}: unknown columns {extra}")
        df = (
            pl.DataFrame([{c: r.get(c) for c in dtypes} for r in data], schema=dtypes, orient="row")
            if data
            else pl.DataFrame(schema=dtypes)
        )
    extra = [c for c in df.columns if c not in dtypes]
    if extra:
        raise SamError(f"{what}: unknown columns {extra}")
    for c, t in dtypes.items():
        if c not in df.columns:
            df = df.with_columns(pl.lit(None, dtype=t).alias(c))
    try:
        return df.select([pl.col(c).cast(t, strict=True) for c, t in dtypes.items()])
    except pl.exceptions.PolarsError as e:
        raise SamError(f"{what}: cannot cast to the spec dtypes: {e}") from None


def _as_list(v: Any) -> list[str] | None:
    if v is None:
        return None
    if isinstance(v, str):
        return [s for s in v.split(",") if s]
    return [str(s) for s in v]


def validate_entries(ctx: BlockContext, data: list[dict[str, Any]] | pl.DataFrame) -> pl.DataFrame:
    acc = ctx.accounts
    df = _frame(data, spec.ENTRY_DTYPES, f"{ctx.block} entries")
    df = df.with_columns(pl.col("component").fill_null("total"))
    # tol_rel is written unrounded (Wave A review F4: at 6 decimals a Rs 1 crore allowance on a Rs 69 lakh
    # crore cell became 0); 12 significant digits make it deterministic
    df = df.with_columns(
        pl.Series(
            "tol_rel", [None if v is None else float(f"{v:.12g}") for v in df["tol_rel"].to_list()], dtype=pl.Float64
        )  # fmt: skip
    )
    problems: list[str] = []
    for c in spec.ENTRY_REQUIRED:
        n = df[c].null_count()
        if n:
            problems.append(f"{n} entries have no {c}")
    if problems:
        raise SamError(f"{ctx.block} entries:\n  " + "\n  ".join(problems))
    prov = ctx.provenance
    for r in df.iter_rows(named=True):
        key = f"{r['row']} <- {r['col']} [{r['ref']}/{r['component']}]"
        bad: list[str] = []
        if not acc.exists(r["row"]):
            bad.append(f"unknown account {r['row']!r}")
        if not acc.exists(r["col"]):
            bad.append(f"unknown account {r['col']!r}")
        if not bad and not acc.allowed_cell(r["row"], r["col"]):
            bad.append(f"block {acc.group(r['row'])} <- {acc.group(r['col'])} is structurally zero (structure.yaml)")
        if r["ref"] not in ctx.refs:
            bad.append(f"ref {r['ref']} is not in this block's REFS")
        if not spec.COMPONENT_RE.match(r["component"]):
            bad.append(f"component {r['component']!r} must be a lower-case slug")
        v = r["value"]
        if not math.isfinite(v):
            bad.append(f"value {v!r} is not finite")
        elif v == 0 and r["ref"] not in spec.ZERO_ENTRY_REFS:
            bad.append(f"zero value: a structural zero is simply absent (zero entries only for {spec.ZERO_ENTRY_REFS})")
        if r["status"] not in spec.STATUSES:
            bad.append(f"status {r['status']!r} not in {spec.STATUSES}")
        role, tol, conf = r["role"], r["tol_rel"], r["confidence"]
        if role not in spec.ROLES:
            bad.append(f"role {role!r} not in {spec.ROLES}")
        elif role == "fixed" and (tol is not None or conf is not None):
            bad.append("a fixed entry has no tol_rel and no confidence")
        elif role == "anchored" and (tol is None or not math.isfinite(tol) or tol <= 0 or conf is not None):
            bad.append("an anchored entry needs tol_rel > 0 and no confidence")
        elif role == "free" and (conf not in spec.CONFIDENCE_WEIGHTS or tol is not None):
            bad.append(f"a free entry needs confidence in {list(spec.CONFIDENCE_WEIGHTS)} and no tol_rel")
        bop = r["bop_function"]
        if bop is not None:
            if bop not in spec.BOP_FUNCTIONS:
                bad.append(f"bop_function {bop!r} not in {spec.BOP_FUNCTIONS}")
            if (r["row"] not in spec.BOP_ACCOUNTS and r["col"] not in spec.BOP_ACCOUNTS
                    and r["ref"] not in spec.BOP_MIRROR_REFS):  # fmt: skip
                bad.append(
                    f"bop_function needs {spec.BOP_ACCOUNTS} as row or column (or a ref in {spec.BOP_MIRROR_REFS}: the "
                    "domestic mirror of a RoW line)"
                )
        p = prov.get(r["prov_id"])
        if p is None:
            bad.append(f"prov_id {r['prov_id']!r} was not registered with ctx.prov() in this block")
        else:
            if p["status"] != r["status"]:
                bad.append(f"status {r['status']!r} differs from its provenance record's {p['status']!r}")
            if ctx.prov_ref.get(r["prov_id"]) != r["ref"]:
                bad.append(f"cites a record made for ref {ctx.prov_ref.get(r['prov_id'])}, not {r['ref']}")
        if bad:
            problems.append(f"{key}: " + "; ".join(bad))
    dup = df.group_by(list(spec.ENTRY_KEY), maintain_order=True).len().filter(pl.col("len") > 1)
    for r in dup.iter_rows(named=True):
        problems.append(f"duplicate key {r['row']} <- {r['col']} [{r['ref']}/{r['component']}] ({r['len']} entries)")
    if problems:
        head = problems[:40] + ([f"... and {len(problems) - 40} more"] if len(problems) > 40 else [])
        raise SamError(f"{ctx.block} entries: {len(problems)} problem(s)\n  " + "\n  ".join(head))
    return df


SATELLITE_SIG_DIGITS = 12


def _sig(v: float, decimals: int) -> float:
    """A satellite value rounded to `decimals` but to at most SATELLITE_SIG_DIGITS significant digits. At 9 decimals
    a value of Rs 10 lakh crore carries 16 significant digits, more than a double holds, so the last bit (which
    depends on the thread count of a polars sum) survived the rounding and repro was not byte-identical."""
    if v == 0.0 or not math.isfinite(v):
        return v
    d = min(decimals, SATELLITE_SIG_DIGITS - 1 - math.floor(math.log10(abs(v))))
    return round(v, d)


def validate_constraints(ctx: BlockContext, data: list[dict[str, Any]] | pl.DataFrame) -> pl.DataFrame:
    acc = ctx.accounts
    gm = gap_map(str(ctx.layout.gap_map))
    rows_in: list[dict[str, Any]] = []
    problems: list[str] = []
    records = data.to_dicts() if isinstance(data, pl.DataFrame) else data
    ids: set[str] = set()
    for r in records:
        cid = r.get("constraint_id")
        bad: list[str] = []
        if not isinstance(cid, str) or not spec.CONSTRAINT_ID_RE.match(cid):
            bad.append("constraint_id must match [a-z0-9][a-z0-9_.-]*")
        elif cid in ids:
            bad.append("constraint_id used twice")
        ids.add(str(cid))
        if r.get("ref") not in gm:
            bad.append(f"ref {r.get('ref')!r} is not a gap-map ref")
        rows, cols, refs = _as_list(r.get("rows")), _as_list(r.get("cols")), _as_list(r.get("refs"))
        for what, lst in (("rows", rows), ("cols", cols)):
            if not lst:
                bad.append(f"{what} must be a non-empty list of accounts")
            else:
                unknown = [a for a in lst if not acc.exists(a)]
                if unknown:
                    bad.append(f"{what}: unknown accounts {unknown}")
        if refs is not None and (not refs or any(x not in gm for x in refs)):
            bad.append(f"refs filter {refs} must be a non-empty list of gap-map refs")
        comps = _as_list(r.get("components"))
        if comps is not None and (not comps or any(not spec.COMPONENT_RE.match(x) for x in comps)):
            bad.append(f"components filter {comps} must be a non-empty list of component slugs")
        t, ta, tr = r.get("target"), r.get("tol_abs", 0.0), r.get("tol_rel", 0.0)
        if not isinstance(t, (int, float)) or not math.isfinite(t):
            bad.append("target must be a finite number")
        for nm, x in (("tol_abs", ta), ("tol_rel", tr)):
            if not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0:
                bad.append(f"{nm} must be a finite number >= 0")
        if r.get("kind", "equal") not in spec.CONSTRAINT_KINDS:
            bad.append(f"kind must be one of {spec.CONSTRAINT_KINDS}")
        if r.get("prov_id") not in ctx.provenance:
            bad.append(f"prov_id {r.get('prov_id')!r} was not registered with ctx.prov() in this block")
        elif ctx.prov_ref.get(r["prov_id"]) != r.get("ref"):
            bad.append(f"cites a record made for ref {ctx.prov_ref.get(r['prov_id'])}, not {r.get('ref')}")
        if not (r.get("description") or "").strip():
            bad.append("description is required")
        if not bad and rows and cols:
            possible = any(acc.allowed_cell(a, b) for a in rows for b in cols)
            tol_c = max(float(ta), float(tr) * abs(float(t)))
            kind = r.get("kind", "equal")
            lo = -math.inf if kind == "max" else float(t) - tol_c
            hi = math.inf if kind == "min" else float(t) + tol_c
            if not possible and not (lo <= 0.0 <= hi):
                bad.append(
                    "no (row, col) pair in rows x cols is allowed by structure.yaml, so the sum is always 0, "
                    f"outside [{lo:,.2f}, {hi:,.2f}]"
                )
        if bad:
            problems.append(f"constraint {cid}: " + "; ".join(bad))
            continue
        order = acc.index
        rows_in.append(
            {
                "constraint_id": cid,
                "ref": r["ref"],
                "rows": ",".join(sorted(set(rows or []), key=order.__getitem__)),
                "cols": ",".join(sorted(set(cols or []), key=order.__getitem__)),
                "refs": None if refs is None else ",".join(sorted(set(refs))),
                "components": None if comps is None else ",".join(sorted(set(comps))),
                "target": float(t),
                "tol_abs": float(ta),
                "tol_rel": float(tr),
                "kind": r.get("kind", "equal"),
                "prov_id": r["prov_id"],
                "description": r["description"],
            }
        )
    if problems:
        raise SamError(f"{ctx.block} constraints: {len(problems)} problem(s)\n  " + "\n  ".join(problems[:40]))
    return (
        pl.DataFrame(rows_in, schema=spec.CONSTRAINT_DTYPES, orient="row")
        if rows_in
        else pl.DataFrame(schema=spec.CONSTRAINT_DTYPES)
    )


def validate_satellite(ctx: BlockContext, name: str, sat: Satellite) -> pl.DataFrame:
    problems: list[str] = []
    if not spec.NAME_RE.match(name):
        problems.append("name must be snake_case")
    if not isinstance(sat, Satellite):
        raise SamError(f"{ctx.block} satellite {name}: must be a Satellite(ref, df, description)")
    if sat.ref not in ctx.refs:
        problems.append(f"ref {sat.ref} is not in this block's REFS")
    if not sat.description.strip():
        problems.append("description is required")
    if not (isinstance(sat.decimals, int) and 6 <= sat.decimals <= 12):
        problems.append("decimals must be an int from 6 to 12")
    df = sat.df
    if not isinstance(df, pl.DataFrame) or df.height == 0:
        raise SamError(f"{ctx.block} satellite {name}: df must be a non-empty polars DataFrame")
    need = {"series_id": pl.String, "value": pl.Float64, "unit": pl.String, "status": pl.String, "prov_id": pl.String}
    for c, t in need.items():
        if c not in df.columns:
            problems.append(f"missing column {c}")
        elif df[c].dtype != t:
            problems.append(f"column {c} must be {t}")
    for c, t in df.schema.items():
        if c not in need and t != pl.String:
            problems.append(f"dimension column {c} must be String (got {t})")
    if not problems:
        if df.select(pl.sum_horizontal(pl.col("series_id", "unit", "status", "prov_id").null_count())).item():
            problems.append("series_id/unit/status/prov_id may not be null")
        v = pl.col("value")
        if df.select((v.is_null() | v.is_nan() | v.is_infinite()).any()).item():
            problems.append("value must be finite, never null")
        if df["series_id"].n_unique() != df.height:
            problems.append("series_id must be unique")
        bad_units = sorted(set(df["unit"].to_list()) - set(UNITS))
        if bad_units:
            problems.append(f"units {bad_units} not in pipeline.core.units.UNITS")
        for pid, st in df.select("prov_id", "status").unique(maintain_order=True).iter_rows():
            p = ctx.provenance.get(pid)
            if p is None:
                problems.append(f"prov_id {pid} was not registered in this block")
            elif p["status"] != st:
                problems.append(f"status {st!r} differs from its provenance record's {p['status']!r}")
            elif ctx.prov_ref.get(pid) != sat.ref:
                problems.append(f"prov_id {pid} is a record made for ref {ctx.prov_ref.get(pid)}, not {sat.ref}")
    if problems:
        raise SamError(f"{ctx.block} satellite {name}: " + "; ".join(problems[:20]))
    return df


def referenced_provenance(ctx: BlockContext, used: set[str]) -> pl.DataFrame:
    """Own records that outputs use, plus own records reachable through `inputs`. Foreign inputs were
    resolved in ctx.prov(). Validated against the Phase 1 provenance schema."""
    keep: set[str] = set()
    stack = sorted(used)
    while stack:
        pid = stack.pop()
        if pid in keep or pid not in ctx.provenance:
            continue
        keep.add(pid)
        ins = ctx.provenance[pid]["inputs"]
        if ins:
            stack.extend(i for i in ins.split(",") if i.startswith(f"sam_{ctx.block}:"))
    rows = [ctx.provenance[k] for k in sorted(keep)]
    df = pl.DataFrame(rows, schema=PROV_DTYPES, orient="row") if rows else pl.DataFrame(schema=PROV_DTYPES)
    df = df.select(list(PROV_DTYPES))
    try:
        PROV_SCHEMA.validate(df, lazy=True)
    except pa_errors.SchemaErrors as e:
        raise SamError(f"{ctx.block} provenance: schema violations\n{e.failure_cases.head(20)}") from None
    bad = df.filter(pl.col("method").is_null() | ~pl.col("prov_id").str.contains(PROV_ID_RE))
    if bad.height:
        raise SamError(f"{ctx.block} provenance: records without method or with bad ids: {bad['prov_id'].to_list()}")
    return df


@dataclass
class ValidResult:
    entries: pl.DataFrame
    constraints: pl.DataFrame
    satellites: dict[str, tuple[Satellite, pl.DataFrame]]
    checks: pl.DataFrame
    provenance: pl.DataFrame


def validate_result(ctx: BlockContext, result: BlockResult) -> ValidResult:
    """Everything DESIGN_BRIEF s.3 requires of a block's output. Raises SamError listing every problem."""
    if not isinstance(result, BlockResult):
        raise SamError(f"{ctx.block}: build() must return a BlockResult, got {type(result).__name__}")
    entries = validate_entries(ctx, result.entries)
    constraints = validate_constraints(ctx, result.constraints)
    if entries.height == 0 and constraints.height == 0 and not result.satellites:
        raise SamError(f"{ctx.block}: build() returned nothing (no silent empties)")
    sats = {n: (s, validate_satellite(ctx, n, s)) for n, s in sorted(result.satellites.items())}
    checks = (
        pl.DataFrame(ctx.checks, schema=spec.CHECK_DTYPES, orient="row")
        if ctx.checks
        else pl.DataFrame(schema=spec.CHECK_DTYPES)
    )
    if checks["check_id"].n_unique() != checks.height:
        raise SamError(f"{ctx.block}: check ids must be unique")
    for pid in checks["target_prov_id"].to_list():
        rec = ctx.lookup_prov(pid)
        if rec is None:
            raise SamError(f"{ctx.block}: check target_prov_id {pid!r} does not resolve")
        if pid.startswith("sam_") and not (rec.get("status") in ("official", "derived") and rec.get("inputs")):
            raise SamError(
                f"{ctx.block}: check target_prov_id {pid!r} must be a clean record, or a SAM record that is "
                "official/derived with inputs (a check compares with a figure read from data, never typed in)"
            )
    used = set(entries["prov_id"].to_list()) | set(constraints["prov_id"].to_list())
    for _, df in sats.values():
        used |= set(df["prov_id"].to_list())
    used |= {p for p in checks["target_prov_id"].to_list() if p.startswith(f"sam_{ctx.block}:")}
    prov = referenced_provenance(ctx, used)
    return ValidResult(entries, constraints, sats, checks, prov)


# ---------------------------------------------------------------------------------------------
# writing a block's outputs
# ---------------------------------------------------------------------------------------------


def write_block(ctx: BlockContext, valid: ValidResult, refs_not_implemented: Sequence[str]) -> None:
    """Write the block's files under data/sam/<year>/blocks/ (deterministic; stale satellites removed)."""
    paths = ctx.paths
    b = ctx.block
    with repo_lock(ctx.layout):
        paths.blocks.mkdir(parents=True, exist_ok=True)
        ent = valid.entries.with_columns(pl.lit(b).alias("block"))
        io.write_parquet(ent, paths.entries(b), sort_by=spec.ENTRY_KEY, decimals={"value": 6, "tol_rel": None})
        con = valid.constraints.with_columns(pl.lit(b).alias("block"))
        io.write_parquet(con, paths.constraints(b), sort_by=("constraint_id",))
        io.write_parquet(valid.checks, paths.checks(b), sort_by=("check_id",))
        io.write_parquet(valid.provenance, paths.provenance(b), sort_by=("prov_id",))
        sdir = paths.satellites(b)
        keep = {f"{n}.parquet" for n in valid.satellites}
        if sdir.exists():
            for p in sorted(sdir.glob("*.parquet")):
                if p.name not in keep:
                    p.unlink()
        for n, (s, df) in valid.satellites.items():
            df = df.with_columns(pl.Series("value", [_sig(v, s.decimals) for v in df["value"].to_list()],
                                           dtype=pl.Float64))  # fmt: skip
            io.write_parquet(df, sdir / f"{n}.parquet", sort_by=("series_id",), decimals={"value": s.decimals})
        if sdir.exists() and not any(sdir.iterdir()):
            shutil.rmtree(sdir)
        catalog = {
            "block": b,
            "year": ctx.year,
            "refs": list(ctx.refs),
            "refs_not_implemented": sorted(refs_not_implemented),
            "depends": list(ctx.depends),
            "entries": valid.entries.height,
            "constraints": valid.constraints.height,
            "satellites": {
                n: {"ref": s.ref, "description": s.description, "rows": df.height, "decimals": s.decimals}
                for n, (s, df) in valid.satellites.items()
            },
            "checks": {"n": valid.checks.height, "failed": sorted(valid.checks.filter(~pl.col("ok"))["check_id"])},
            "datasets_read": sorted(ctx.datasets_read),
            "concordances_read": dict(sorted(ctx.concordances_read.items())),
            # what this build read from its DEPENDS (a rebuilt dependency makes this block stale: run.py warns)
            "dependency_hashes": dependency_hashes(paths, ctx.depends),
            "warnings": len(ctx.warnings),
        }
        io.write_json(paths.catalog(b), catalog)
        write_combined_provenance(paths)


def dependency_hashes(paths: SamPaths, depends: Sequence[str]) -> dict[str, dict[str, str]]:
    """sha256 of the entries, constraints and provenance files of each dependency, as built now."""
    out: dict[str, dict[str, str]] = {}
    for d in sorted(depends):
        out[d] = {
            k: io.sha256_file(f)
            for k, f in (
                ("entries", paths.entries(d)),
                ("constraints", paths.constraints(d)),
                ("provenance", paths.provenance(d)),
            )  # fmt: skip
            if f.exists()
        }
    return out


def stale_dependents(paths: SamPaths) -> list[str]:
    """Built blocks whose recorded dependency hashes no longer match their dependencies' files."""
    out = []
    for cat in sorted(paths.blocks.glob("*_block.json")) if paths.blocks.exists() else []:
        doc = json.loads(cat.read_text(encoding="utf-8"))
        rec = doc.get("dependency_hashes") or {}
        now = dependency_hashes(paths, sorted(rec))
        changed = sorted(d for d in rec if rec[d] != now.get(d))
        if changed:
            out.append(f"{doc.get('block')} (read {', '.join(changed)} before it was rebuilt)")
    return out


def write_combined_provenance(paths: SamPaths) -> None:
    """data/sam/<year>/_provenance.parquet: every block's provenance records (caller holds the lock)."""
    frames = [pl.read_parquet(p) for p in sorted(paths.blocks.glob("*_provenance.parquet"))]
    if not frames:
        return
    df = pl.concat(frames, how="vertical").unique(subset=["prov_id"], keep="first", maintain_order=True)
    io.write_parquet(df, paths.provenance_all, sort_by=("prov_id",))


def remove_block_outputs(paths: SamPaths, block: str) -> None:
    for p in (paths.entries(block), paths.constraints(block), paths.checks(block), paths.provenance(block),
              paths.catalog(block)):  # fmt: skip
        if p.exists():
            p.unlink()
    if paths.satellites(block).exists():
        shutil.rmtree(paths.satellites(block))


@dataclass
class BlockRun:
    block: str
    ok: bool
    message: str = ""
    counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def build_block_module(mod: ModuleType, layout: Layout, *, write: bool = True) -> tuple[BlockRun, ValidResult | None]:
    """Build one (already imported) block: contract, build(ctx), validation, outputs. Tests pass
    in-memory modules here (with a scratch layout)."""
    import traceback

    name = getattr(mod, "BLOCK", "?")
    try:
        check_contract(mod, None, layout)
        depends = tuple(getattr(mod, "DEPENDS", ()))
        paths = SamPaths(layout)
        missing = [d for d in depends if not paths.built(d)]
        if missing:
            msg = f"not built: dependency {', '.join(missing)} has no output (build it first)"
            return BlockRun(name, False, msg), None
        ctx = BlockContext(block=name, refs=tuple(mod.REFS), depends=depends, layout=layout)
        result = mod.build(ctx)
        valid = validate_result(ctx, result)
        not_impl = [r for r in OWNERSHIP[name] if r not in mod.REFS]
        if write:
            write_block(ctx, valid, not_impl)
        counts = {"entries": valid.entries.height, "constraints": valid.constraints.height,
                  "satellites": len(valid.satellites), "checks": valid.checks.height,
                  "provenance": valid.provenance.height}  # fmt: skip
        return BlockRun(name, True, "ok", counts, ctx.warnings), valid
    except SamError as e:
        return BlockRun(name, False, f"SamError: {e}"), None
    except Exception as e:  # noqa: BLE001 - report any block crash with its traceback
        return BlockRun(name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}"), None
