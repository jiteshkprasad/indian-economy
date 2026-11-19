"""Runs units: fetch (network, pins raw files) and build (offline, validates, writes clean Parquet).

Build of one unit, in order:
 1. import the unit (only that unit) and check its contract and SOURCES against the registry;
 2. call build(ctx) and collect the returned Datasets and the provenance records;
 3. per dataset: conform columns, validate the schema, check source ids, prov ids and that every
    row agrees with its provenance record (source, status, price basis, vintage);
 4. validate the provenance table (only records that rows or `inputs` reference are kept) and
    check each row's unit against its record's unit_as_published / conversion / inputs;
 5. write everything to a temp folder, then swap it in as data/clean/<unit>/ (a full rebuild:
    datasets the unit no longer returns disappear). The swap is two renames: the old folder is
    renamed aside first, and if that fails (a file in it is open elsewhere, on Windows) nothing
    changes; the aside folder is deleted afterwards, best effort, and swept by later builds;
 6. regenerate data/manifest.json from what is on disk.
Nothing is written for a unit whose build, validation or swap fails.

`build UNIT` builds only the named units. Units in their DEPENDS are read as already built (and
must exist); `--with-deps` rebuilds them too. `build` with no units builds everything in order.
"""

from __future__ import annotations

import os
import re
import shutil
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

import polars as pl

from pipeline.core import io
from pipeline.core.fetch import FetchError, PinStore
from pipeline.core.manifest import repo_lock, write_manifest
from pipeline.core.paths import Layout
from pipeline.core.registry import source_ids
from pipeline.core.schema import (
    CLEAN_KEY,
    PROV_DTYPES,
    PROV_KEY,
    CleanDataError,
    conform_clean,
    validate_clean,
    validate_provenance,
)
from pipeline.core.unit import (
    BuildContext,
    Dataset,
    FetchContext,
    UnitError,
    check_contract,
    load_unit,
    unit_names,
)
from pipeline.core.units import SIG_DIGIT_UNITS, conversion_note, inr_unit_from_label, round_sig_expr
from pipeline.core.units import UnitError as MeasureUnitError

DATASET_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PROVENANCE_FILE = "_provenance.parquet"
DATASETS_FILE = "_datasets.json"


@dataclass
class UnitResult:
    unit: str
    ok: bool
    message: str = ""
    datasets: dict[str, int] = field(default_factory=dict)  # name -> rows
    warnings: list[str] = field(default_factory=list)


def _crash(name: str, e: BaseException) -> UnitResult:
    """An unexpected exception inside a unit: report it with its traceback, keep other units going."""
    return UnitResult(name, False, f"{type(e).__name__}: {e}" + chr(10) + traceback.format_exc())


# ---------------------------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------------------------


def fetch_unit(
    name: str, layout: Layout, *, offline: bool = False, refresh: bool = False, prune: bool = False
) -> UnitResult:
    try:
        mod = load_unit(name, layout)
    except (UnitError, KeyError) as e:
        return UnitResult(name, False, f"{type(e).__name__}: {e}")
    except Exception as e:  # noqa: BLE001 - e.g. a syntax error in the unit module
        return _crash(name, e)
    return fetch_module(mod, layout, offline=offline, refresh=refresh, prune=prune)


def _unused_pins(ctx: FetchContext, store: PinStore, prune: bool) -> str:
    """Pins this run's fetch() never asked for. Reported always; removed only with --prune, and
    only after a clean run (no warnings: a skipped or blocked file must not lose its pin). The raw
    files stay on disk; only the pin entries go (they remain in git history)."""
    unused = sorted(set(store.pins) - ctx.requested)
    if not unused:
        return ""
    if not prune:
        ctx.log(
            f"{len(unused)} pin(s) not requested by this run: {', '.join(unused)}. If fetch() no longer needs "
            "them, run `fetch <unit> --prune` (after a clean run) to drop them."
        )
        return ""
    if ctx.warnings:
        ctx.warn(
            f"--prune skipped: this run had warnings, so unrequested pins may still be needed: {', '.join(unused)}"
        )
        return ""
    for k in unused:
        del store.pins[k]
    store.changed = True
    ctx.log(f"pruned {len(unused)} unrequested pin(s): {', '.join(unused)} (raw files kept on disk)")
    return f"; pruned {len(unused)} pin(s)"


def fetch_module(
    mod: ModuleType, layout: Layout, *, offline: bool = False, refresh: bool = False, prune: bool = False
) -> UnitResult:
    name = getattr(mod, "UNIT", "?")
    try:
        check_contract(mod, None, layout)
        store = PinStore.load(layout, name)
        ctx = FetchContext(
            unit=name, sources=tuple(mod.SOURCES), layout=layout, offline=offline, refresh=refresh, store=store
        )
        mod.fetch(ctx)
        pruned = _unused_pins(ctx, store, prune)
        store.save()
        return UnitResult(name, True, f"{len(ctx.fetched)} raw file(s) ready{pruned}", warnings=ctx.warnings)
    except (FetchError, UnitError, KeyError) as e:
        return UnitResult(name, False, f"{type(e).__name__}: {e}")
    except Exception as e:  # noqa: BLE001 - report any unit crash, keep other units going
        return _crash(name, e)


# ---------------------------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------------------------


def _check_dataset(
    unit: str, sources: tuple[str, ...], ds: Dataset, prov: pl.DataFrame, layout: Layout
) -> pl.DataFrame:
    if not isinstance(ds, Dataset):
        raise UnitError(f"build() must return a list of Dataset objects, got {type(ds).__name__}")
    if not DATASET_RE.match(ds.name) or not (ds.name == unit or ds.name.startswith(unit + "_")):
        raise UnitError(f"dataset name {ds.name!r} must be snake_case and equal {unit!r} or start with '{unit}_'")
    if not isinstance(ds.df, pl.DataFrame):
        raise UnitError(f"{ds.name}: df must be a polars DataFrame")
    if not ds.description.strip():
        raise UnitError(f"{ds.name}: Dataset.description is required (one line: what the table holds)")
    if ds.df.height == 0:
        raise CleanDataError(f"{ds.name}: empty dataset (no silent empties; drop it or log why)")
    df = conform_clean(ds.df, ds.name)
    validate_clean(df, ds.name)

    bad_src = sorted(set(df["source_id"].unique().to_list()) - set(sources))
    if bad_src:
        raise CleanDataError(f"{ds.name}: source_id(s) {bad_src} not in the unit's SOURCES")
    unknown = sorted(set(df["source_id"].unique().to_list()) - source_ids(layout))
    if unknown:
        raise CleanDataError(f"{ds.name}: source_id(s) {unknown} not in data/registry.yaml")

    joined = df.join(
        prov.select(
            "prov_id",
            pl.col("source_id").alias("_p_source"),
            pl.col("status").alias("_p_status"),
            pl.col("price_basis").alias("_p_price"),
            pl.col("vintage").alias("_p_vintage"),
        ),
        on="prov_id",
        how="left",
        maintain_order="left",
    )
    missing = joined.filter(pl.col("_p_source").is_null())
    if missing.height:
        raise CleanDataError(
            f"{ds.name}: prov_id(s) not registered with ctx.prov(): {missing['prov_id'].unique().to_list()[:10]}"
        )
    for col, pcol in (
        ("source_id", "_p_source"),
        ("status", "_p_status"),
        ("price_basis", "_p_price"),
        ("vintage", "_p_vintage"),
    ):
        bad = joined.filter(pl.col(col) != pl.col(pcol))
        if bad.height:
            raise CleanDataError(
                f"{ds.name}: {col} of {bad.height} row(s) differs from their provenance record, e.g. series "
                f"{bad['series_id'][0]!r}: row {bad[col][0]!r} vs provenance {bad[pcol][0]!r}"
            )
    return df


def _referenced_provenance(
    prov: pl.DataFrame, used: set[str], unit: str, depends: tuple[str, ...], layout: Layout
) -> pl.DataFrame:
    """Own records that rows use, plus everything reachable through `inputs`. Inputs from another
    unit (e.g. an exchange-rate series) must come from a unit in DEPENDS and exist in its built
    _provenance.parquet; they are checked, not copied."""
    by_id = {r["prov_id"]: r for r in prov.iter_rows(named=True)}
    foreign: dict[str, set[str]] = {}
    keep: set[str] = set()
    stack = list(used)
    while stack:
        pid = stack.pop()
        owner = pid.split(":", 1)[0]
        if owner != unit:
            if owner not in depends:
                raise CleanDataError(f"provenance input {pid!r} belongs to unit {owner!r}, which is not in DEPENDS")
            foreign.setdefault(owner, set()).add(pid)
            continue
        if pid in keep:
            continue
        if pid not in by_id:
            raise CleanDataError(f"provenance input {pid!r} is not a registered prov_id of this unit")
        keep.add(pid)
        if by_id[pid]["inputs"]:
            stack.extend(by_id[pid]["inputs"].split(","))
    for owner, ids in sorted(foreign.items()):
        f = layout.clean / owner / PROVENANCE_FILE
        if not f.exists():
            raise CleanDataError(f"provenance inputs from {owner!r} but {f} does not exist (build {owner} first)")
        have = set(pl.read_parquet(f, columns=["prov_id"])["prov_id"].to_list())
        if ids - have:
            raise CleanDataError(f"provenance inputs not found in {owner}/_provenance.parquet: {sorted(ids - have)}")
    return prov.filter(pl.col("prov_id").is_in(sorted(keep)))


_DOLLAR = re.compile(r"us\s*\$|\busd\b|dollar", re.I)
_EURO = re.compile(r"\beur\b|euro|\u20ac", re.I)


def _unit_inputs(frames: dict[str, pl.DataFrame], layout: Layout, foreign_units: set[str]) -> dict[str, set[str]]:
    """{prov_id: units of measure of the rows that use it}, over this build and the DEPENDS units read."""
    out: dict[str, set[str]] = {}
    tables = list(frames.values())
    for owner in sorted(foreign_units):
        for f in sorted((layout.clean / owner).glob("*.parquet")):
            if f.name != PROVENANCE_FILE:
                tables.append(pl.read_parquet(f, columns=["prov_id", "unit"]))
    for t in tables:
        for pid, unit in t.select("prov_id", "unit").unique(maintain_order=True).iter_rows():
            out.setdefault(pid, set()).add(unit)
    return out


def check_units_against_provenance(
    frames: dict[str, pl.DataFrame], prov: pl.DataFrame, layout: Layout, unit: str
) -> None:
    """A row's unit must agree with its provenance record (a hidden 100x or exchange-rate error
    otherwise). Rules, by the row's `unit`:
    - INR_crore rows: an official record's unit_as_published must be a rupee caption
      (units.inr_unit_from_label), and whenever it is one, `conversion` must start with
      units.conversion_note(<that key>) ('none' for crore).
    - INR_crore / INR rows whose record says US$: status 'derived', with an INR_per_USD series
      among the record's `inputs`.
    - USD_million / USD / EUR_million rows whose record is a rupee caption: an error.
    - INR_crore / INR rows whose record says euro: an error (there is no INR_per_EUR series yet).
    """
    by_id = {r["prov_id"]: r for r in prov.iter_rows(named=True)}
    combos: set[tuple[str, str]] = set()
    for df in frames.values():
        combos.update(df.select("prov_id", "unit").unique(maintain_order=True).iter_rows())
    foreign = {
        i.split(":", 1)[0]
        for r in by_id.values()
        if r["inputs"]
        for i in r["inputs"].split(",")
        if not i.startswith(unit + ":")
    }
    input_units: dict[str, set[str]] | None = None
    problems: list[str] = []
    for pid, row_unit in sorted(combos):
        rec = by_id[pid]
        uap, conv, status = rec["unit_as_published"], rec["conversion"], rec["status"]
        where = f"prov_id {pid} (unit_as_published {uap!r}, conversion {conv!r}, status {status}) on {row_unit} rows"
        dollars = bool(_DOLLAR.search(uap))
        euros = bool(_EURO.search(uap))
        try:
            key = None if dollars or euros else inr_unit_from_label(uap)
        except MeasureUnitError:
            key = None
        if row_unit in ("INR_crore", "INR") and euros:
            problems.append(
                f"{where}: euro figures cannot be shown in rupees (no INR_per_EUR series); keep EUR_million"
            )
        elif row_unit in ("INR_crore", "INR") and dollars:
            if input_units is None:
                input_units = _unit_inputs(frames, layout, foreign)
            ins = (rec["inputs"] or "").split(",") if rec["inputs"] else []
            has_rate = any("INR_per_USD" in input_units.get(i, set()) for i in ins)
            if status != "derived" or not has_rate:
                problems.append(
                    f"{where}: dollar figures shown in rupees must be status 'derived' with an INR_per_USD rate "
                    "series among `inputs` (units.usd_million_to_inr_crore); never a hard-coded rate"
                )
        elif row_unit == "INR_crore":
            if key is None and status == "official":
                problems.append(
                    f"{where}: official INR_crore rows need a rupee unit_as_published such as 'Rs crore', 'Rs lakh' "
                    'or "Rs \'000 crore" (units.inr_unit_from_label), describing this block only'
                )
            elif key is not None and not conv.startswith(conversion_note(key)):
                problems.append(
                    f"{where}: published in {key}, so conversion must be {conversion_note(key)!r} "
                    "(units.conversion_note) and the values converted with units.to_inr_crore"
                )
        elif row_unit in ("USD_million", "USD", "EUR_million") and key is not None:
            problems.append(f"{where}: a rupee unit_as_published on dollar rows")
    if problems:
        raise CleanDataError(f"{unit}: row units disagree with provenance:\n  " + "\n  ".join(problems))


def _round_ratios(df: pl.DataFrame, sig_digits: int) -> pl.DataFrame:
    """Dataset.ratio_sig_digits: percent/ratio rows to significant digits (units.round_sig_expr),
    all other rows to the default 6 decimals, exactly as the writer would round them."""
    if not isinstance(sig_digits, int) or isinstance(sig_digits, bool):
        raise UnitError(f"ratio_sig_digits must be an int, got {sig_digits!r}")
    v = pl.col("value")
    rounded = pl.when(pl.col("unit").is_in(list(SIG_DIGIT_UNITS))).then(round_sig_expr(v, sig_digits))
    return df.with_columns(rounded.otherwise(v.round(io.DEFAULT_DECIMALS)).alias("value"))


def sweep_leftovers(clean: Path) -> None:
    """Delete .<unit>.tmp-* / .<unit>.old-* folders left by crashed or blocked builds. Call only
    while holding the repo lock (then no other build is writing)."""
    if not clean.exists():
        return
    for p in sorted([*clean.glob(".*.tmp-*"), *clean.glob(".*.old-*")]):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)


def _swap_in(tmp: Path, final: Path) -> None:
    """Replace `final` by `tmp` with renames only. On failure `final` is unchanged and `tmp` removed."""
    old = final.with_name(f".{final.name}.old-{os.getpid()}")
    if old.exists():
        shutil.rmtree(old, ignore_errors=True)
    moved = False
    try:
        if final.exists():
            os.replace(final, old)
            moved = True
        os.replace(tmp, final)
    except OSError as e:
        if moved and not final.exists():
            try:
                os.replace(old, final)
            except OSError as e2:
                raise UnitError(
                    f"could not swap in the new output ({e}) nor put the old one back ({e2}): the previous output is "
                    f"in {old}. Close whatever has files open there and rebuild."
                ) from None
        shutil.rmtree(tmp, ignore_errors=True)
        raise UnitError(
            f"could not swap in the new output for {final.name}: {e}. A file in {final} is probably open in "
            "another process (Windows does not allow renaming it). The previous output is unchanged; close it "
            "and rebuild."
        ) from None
    shutil.rmtree(old, ignore_errors=True)  # best effort: an open reader keeps it until the next sweep


def build_unit(name: str, layout: Layout, *, update_manifest: bool = True) -> UnitResult:
    try:
        mod = load_unit(name, layout)
    except (UnitError, KeyError) as e:
        return UnitResult(name, False, f"{type(e).__name__}: {e}")
    except Exception as e:  # noqa: BLE001 - e.g. a syntax error in the unit module
        return _crash(name, e)
    return build_module(mod, layout, update_manifest=update_manifest)


def build_module(mod: ModuleType, layout: Layout, *, update_manifest: bool = True) -> UnitResult:
    """Build an already-imported unit module (tests pass in-memory modules here)."""
    name = getattr(mod, "UNIT", "?")
    try:
        check_contract(mod, None, layout)
        depends = tuple(getattr(mod, "DEPENDS", ()))
        ctx = BuildContext(unit=name, sources=tuple(mod.SOURCES), layout=layout, depends=depends)
        datasets = mod.build(ctx)
        if not isinstance(datasets, (list, tuple)) or not datasets:
            raise UnitError("build() must return a non-empty list of Dataset objects")
        prov = ctx.provenance_frame()
        seen: set[str] = set()
        frames: dict[str, pl.DataFrame] = {}
        for ds in datasets:
            if ds.name in seen:
                raise UnitError(f"dataset {ds.name!r} returned twice")
            seen.add(ds.name)
            frames[ds.name] = _check_dataset(name, tuple(mod.SOURCES), ds, prov, layout)
        used = set().union(*(set(f["prov_id"].unique().to_list()) for f in frames.values()))
        prov = _referenced_provenance(prov, used, name, depends, layout).select(list(PROV_DTYPES))
        validate_provenance(prov, f"{name}/_provenance")
        bad_src = sorted(set(prov["source_id"].to_list()) - source_ids(layout))
        if bad_src:
            raise CleanDataError(f"{name}: provenance source_id(s) {bad_src} not in the registry")
        check_units_against_provenance(frames, prov, layout, name)

        catalog = {
            d.name: {
                "description": d.description,
                "rows": frames[d.name].height,
                "source_ids": sorted(set(frames[d.name]["source_id"].to_list())),
            }
            | ({"ratio_sig_digits": d.ratio_sig_digits} if d.ratio_sig_digits is not None else {})
            for d in datasets
        }
        with repo_lock(layout):
            sweep_leftovers(layout.clean)
            tmp = layout.clean / f".{name}.tmp-{os.getpid()}"
            try:
                sig = {d.name: d.ratio_sig_digits for d in datasets}
                for dname, df in frames.items():
                    if sig[dname] is None:
                        io.write_parquet(df, tmp / f"{dname}.parquet", sort_by=CLEAN_KEY)
                    else:  # Dataset.ratio_sig_digits: rounded here, so the writer must not round again
                        out = _round_ratios(df, sig[dname])
                        io.write_parquet(out, tmp / f"{dname}.parquet", sort_by=CLEAN_KEY, decimals={"value": None})
                io.write_parquet(prov, tmp / PROVENANCE_FILE, sort_by=PROV_KEY)
                io.write_json(tmp / DATASETS_FILE, catalog)
            except BaseException:
                shutil.rmtree(tmp, ignore_errors=True)
                raise
            _swap_in(tmp, layout.clean / name)
            if update_manifest:
                write_manifest(layout)
        return UnitResult(name, True, "ok", {k: v.height for k, v in frames.items()}, ctx.warnings)
    except (CleanDataError, UnitError, FetchError, KeyError) as e:
        return UnitResult(name, False, f"{type(e).__name__}: {e}")
    except Exception as e:  # noqa: BLE001
        return _crash(name, e)


def build_order(
    names: list[str], layout: Layout, *, with_deps: bool = True
) -> tuple[list[str], dict[str, str], dict[str, tuple[str, ...]]]:
    """Units to build, dependencies first: `names` plus (with_deps) their DEPENDS closure.
    Returns (order, {unit: load error}, {unit: DEPENDS})."""
    deps: dict[str, tuple[str, ...]] = {}
    errors: dict[str, str] = {}
    todo = list(names)
    while todo:
        n = todo.pop(0)
        if n in deps or n in errors:
            continue
        try:
            d = tuple(getattr(load_unit(n, layout), "DEPENDS", ()))
        except Exception as e:  # noqa: BLE001 - reported per unit
            errors[n] = f"{type(e).__name__}: {e}"
            continue
        deps[n] = d
        if with_deps:
            todo.extend(d)
    order: list[str] = []
    state: dict[str, int] = {}

    def visit(n: str, path: tuple[str, ...]) -> None:
        if state.get(n) == 2 or n in errors or n not in deps:
            return  # not in deps: a dependency read as already built (with_deps=False)
        if state.get(n) == 1:
            raise UnitError("DEPENDS cycle: " + " -> ".join((*path, n)))
        state[n] = 1
        for d in sorted(deps.get(n, ())):
            visit(d, (*path, n))
        state[n] = 2
        order.append(n)

    for n in sorted(deps):
        visit(n, ())
    return order, errors, deps


def run(command: str, units: list[str] | None, layout: Layout, **kw: bool) -> list[UnitResult]:
    """fetch or build `units` (None = all units). For build, `with_deps=True` also rebuilds the
    DEPENDS closure; otherwise dependencies outside `units` must already be built."""
    names = units or unit_names(layout)
    if not names:
        print("no units found in pipeline/ingest")
        return []
    results: list[UnitResult] = []
    deps_of: dict[str, tuple[str, ...]] = {}
    if command == "build":
        with_deps = bool(kw.get("with_deps", False)) or not units
        order, load_errors, deps_of = build_order(list(names), layout, with_deps=with_deps)
        extra = [n for n in order if n not in names]
        if extra:
            print("(also building dependencies: " + ", ".join(extra) + ")")
        for n, m in load_errors.items():
            print(f"== build {n}\n   FAILED: {m}")
            results.append(UnitResult(n, False, m))
        names = order
    failed: set[str] = {r.unit for r in results}
    for n in names:
        print(f"== {command} {n}")
        if command == "fetch":
            r = fetch_unit(
                n,
                layout,
                offline=kw.get("offline", False),
                refresh=kw.get("refresh", False),
                prune=kw.get("prune", False),
            )
        else:
            bad_deps = [d for d in deps_of.get(n, ()) if d in failed]
            unbuilt = [
                d for d in deps_of.get(n, ()) if d not in names and not (layout.clean / d / PROVENANCE_FILE).exists()
            ]
            if bad_deps:
                r = UnitResult(n, False, "not built: dependency failed: " + ", ".join(bad_deps))
            elif unbuilt:
                r = UnitResult(
                    n,
                    False,
                    f"not built: dependency {', '.join(unbuilt)} has no clean output in {layout.clean}. Build it "
                    "first (its owner's job), or pass --with-deps to rebuild it here.",
                )
            else:
                r = build_unit(n, layout, update_manifest=False)
        print(f"   {'OK' if r.ok else 'FAILED'}: {r.message}")
        for d, rows in sorted(r.datasets.items()):
            print(f"   {d}: {rows} rows")
        if not r.ok:
            failed.add(n)
        results.append(r)
    if command == "build":
        with repo_lock(layout):
            write_manifest(layout)
        print(f"manifest written: {layout.manifest}")
    return results


def summarize(results: list[UnitResult]) -> int:
    failed = [r for r in results if not r.ok]
    warned = [r for r in results if r.warnings]
    if warned:
        print("\nWARNINGS")
        for r in warned:
            for w in r.warnings:
                print(f"  {r.unit}: {w}")
    print(f"\n{len(results) - len(failed)} ok, {len(failed)} failed")
    for r in failed:
        print(f"  FAILED {r.unit}: {r.message.splitlines()[0] if r.message else ''}")
    return 1 if failed else 0


def clean_files(layout: Layout) -> list[Path]:
    if not layout.clean.exists():
        return []
    return sorted(
        p for p in layout.clean.glob("*/*.parquet") if not p.parent.name.startswith(".") and p.name != PROVENANCE_FILE
    )
