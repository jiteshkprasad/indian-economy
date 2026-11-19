"""The ingest-unit contract: what a unit module defines and the context objects it receives.

A unit is a module `pipeline/ingest/<unit>.py` (or a package `pipeline/ingest/<unit>/`) defining:

    UNIT = "<unit>"                  # must equal the module name
    SOURCES = ["<source_id>", ...]   # registry ids this unit reads
    DEPENDS = ["<other unit>", ...]  # optional: units whose clean output build() reads
    def fetch(ctx: FetchContext) -> None: ...
    def build(ctx: BuildContext) -> list[Dataset]: ...

Units are discovered automatically; there is no central list. See docs/phase1/PIPELINE_GUIDE.md.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any

import polars as pl

from pipeline.core import io
from pipeline.core.fetch import ChallengeServed, PinStore, RawFile, fetch_file, pinned_raw
from pipeline.core.paths import Layout
from pipeline.core.policy import source_refusal
from pipeline.core.registry import RegistryError, get_source, require_sources
from pipeline.core.schema import ESTIMATE_STAGES, PRICE_BASIS_RE, PROV_DTYPES, STATUSES

UNIT_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
INGEST_PACKAGE = "pipeline.ingest"


class UnitError(RuntimeError):
    """A unit module breaks the contract (missing attributes, wrong names, unknown sources...)."""


@dataclass(frozen=True)
class Dataset:
    """One clean table produced by a unit.

    name: 'snake_case', must start with '<UNIT>_' or equal UNIT; becomes data/clean/<unit>/<name>.parquet.
    df: rows in the clean schema (see pipeline/core/schema.py). `dataset` and the optional dims may
        be omitted; the runner adds them.
    description: one line, shown by `python -m pipeline list`.
    ratio_sig_digits: opt-in. Rows whose unit is `percent` or `ratio` are rounded to this many
        significant digits (never to fewer than the default 6 decimals, never beyond 15) instead of
        6 decimals, so small shares keep their relative precision (units.round_sig_expr). Other rows
        are unaffected. Recorded in _datasets.json.
    """

    name: str
    df: pl.DataFrame
    description: str = ""
    ratio_sig_digits: int | None = None


@dataclass
class _BaseContext:
    unit: str
    sources: tuple[str, ...]
    layout: Layout
    log_lines: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        print(f"[{self.unit}] {msg}")
        self.log_lines.append(msg)

    def warn(self, msg: str) -> None:
        """Something a human must look at (it is printed in the run summary). Warnings do not fail
        the build; if the problem affects data, also write it in docs/phase1/issues/<unit>.md."""
        print(f"[{self.unit}] WARNING: {msg}")
        self.warnings.append(msg)

    def _check_source(self, source_id: str) -> None:
        if source_id not in self.sources:
            raise UnitError(f"{self.unit}: source_id {source_id!r} is not in this unit's SOURCES {self.sources}")


@dataclass
class FetchContext(_BaseContext):
    """Given to `fetch(ctx)`. Use `ctx.fetch(...)` for every download."""

    offline: bool = False
    refresh: bool = False
    store: PinStore | None = None
    fetched: list[RawFile] = field(default_factory=list)
    requested: set[str] = field(default_factory=set)  # pin keys asked for in this run
    challenged_hosts: dict[str, str] = field(default_factory=dict)  # host -> first challenge (this run)

    def fetch(
        self,
        source_id: str,
        url: str,
        name: str | None = None,
        *,
        method: str = "GET",
        json_body: Any = None,
        headers: Mapping[str, str] | None = None,
        referer: str | None = None,
        expect: str | None = None,
        form_body: Mapping[str, str] | None = None,
    ) -> RawFile:
        """Download (or reuse the pinned copy of) one public file and pin it.

        name: the file name under data/raw/<source_id>/<date>/<unit>/ (default: last URL path segment).
              It is also the pin key '<source_id>/<name>' that build() uses with ctx.raw().
        method/json_body: POST JSON for public JSON APIs a web page itself calls (e.g. MoSPI listings).
        form_body: with method="POST", submit a public keyless HTML form (e.g. an ASP.NET archive
              page's __VIEWSTATE postback; DECISIONS D1-7). Credential, session and CSRF-token
              fields are refused.
        referer: the public page that links to the file, if the host expects one.
        expect: file kind to verify ('xlsx', 'xls', 'pdf', 'csv', 'json', 'html', 'zip', 'any');
                default from the name's extension. An HTML/challenge page instead raises AccessBlocked.

        A bot challenge (ChallengeServed, a subclass of AccessBlocked) stops the host for the rest of
        this run: every later ctx.fetch to it raises ChallengeServed without contacting it (D1-1b,
        D1-4). Per-host minimum gaps (e.g. 10 s for rbidocs.rbi.org.in) are enforced by the framework.
        """
        self._check_source(source_id)
        if name is None:
            name = url.rstrip("/").rsplit("/", 1)[-1].split("?", 1)[0]
        assert self.store is not None
        self.requested.add(f"{source_id}/{name}")
        try:
            raw = self._fetch(source_id, url, name, method, json_body, headers, referer, expect, form_body)
        except ChallengeServed as e:
            if e.host not in self.challenged_hosts:
                self.challenged_hosts[e.host] = str(e).split(". Nothing was saved", 1)[0][:300]
                self.warn(f"{e.host} served a bot challenge; no further request to it in this run (D1-1b/D1-4)")
            raise
        self.store.save()  # save after every file so a later failure keeps earlier pins
        self.fetched.append(raw)
        return raw

    def _fetch(
        self,
        source_id: str,
        url: str,
        name: str,
        method: str,
        json_body: Any,
        headers: Mapping[str, str] | None,
        referer: str | None,
        expect: str | None,
        form_body: Mapping[str, str] | None,
    ) -> RawFile:
        assert self.store is not None
        return fetch_file(
            self.layout,
            self.store,
            source_id=source_id,
            url=url,
            name=name,
            method=method,
            json_body=json_body,
            headers=headers,
            referer=referer,
            expect=expect,
            offline=self.offline,
            refresh=self.refresh,
            log=self.log,
            warn=self.warn,
            form_body=form_body,
            stop_hosts=self.challenged_hosts,
        )

    def is_pinned(self, source_id: str, name: str, url: str | None = None) -> bool:
        """True if a plain ctx.fetch of (source_id, name) would reuse the local pinned copy without
        any network request: a pin exists, its file is on disk, this is not a --refresh run, and
        (if `url` is given) the pin is for that URL. Use it to skip politeness waits or to report
        what an offline run can still provide; it does not hash-verify the file."""
        self._check_source(source_id)
        assert self.store is not None
        pin = self.store.pins.get(f"{source_id}/{name}")
        if pin is None or self.refresh or (url is not None and pin.get("url") != url):
            return False
        return self.layout.raw_abs(pin["path"]).exists()

    def raw(self, source_id: str, name: str) -> RawFile:
        """A file pinned by an earlier call (e.g. to read a listing and decide what to fetch next)."""
        self._check_source(source_id)
        return pinned_raw(self.layout, self.unit, source_id, name)


@dataclass
class BuildContext(_BaseContext):
    """Given to `build(ctx)`. Builds are offline: read pinned files with `ctx.raw(...)`."""

    provenance: dict[str, dict[str, Any]] = field(default_factory=dict)
    depends: tuple[str, ...] = ()

    def raw(self, source_id: str, name: str) -> RawFile:
        """The pinned raw file (hash-verified). Fails loudly if it was never fetched or is missing."""
        self._check_source(source_id)
        return pinned_raw(self.layout, self.unit, source_id, name)

    def clean(self, unit: str, dataset: str) -> pl.DataFrame:
        """Another unit's clean dataset (e.g. an exchange-rate series). `unit` must be in DEPENDS;
        the runner builds dependencies first. Cite the rows' prov_ids in your records' `inputs`."""
        if unit not in self.depends:
            raise UnitError(f"{self.unit}: reading {unit!r} requires DEPENDS = [..., {unit!r}]")
        p = self.layout.clean / unit / f"{dataset}.parquet"
        if not p.exists():
            raise UnitError(f"{p} does not exist: build {unit} first")
        return pl.read_parquet(p)

    def prov(
        self,
        *,
        raw: RawFile | None,
        table_id: str,
        locator: str,
        unit_as_published: str,
        price_basis: str,
        vintage: str,
        release: str,
        base_year: str | None = None,
        conversion: str = "none",
        status: str = "official",
        method: str | None = None,
        inputs: Sequence[str] = (),
        notes: str | None = None,
        source_id: str | None = None,
    ) -> str:
        """Register one provenance record and return its prov_id ('<unit>:<12 hex>').

        The id is a hash of the record, so calling prov() again with the same arguments returns the
        same id. Use one record per block of cells that share all these fields (e.g. one sheet's
        current-price block); put the sheet and cell range in `locator`.

        raw: the pinned file the numbers come from (None only for derived/estimated records, which
             must then say what they are computed from: see below).
        locator: where in the file, precise enough for a verifier: "sheet '1.1', rows 6-40, cols C:F
                 (years 2022-23..2025-26)" or "page 12, table 3".
        unit_as_published: e.g. 'Rs crore', 'Rs lakh', 'US$ million'. conversion: e.g. 'none',
                 'INR_lakh -> INR_crore: x 0.01' (see units.conversion_note).
        status: 'official' (as published, after unit conversion), 'derived' (arithmetic on official
                numbers by us), 'estimated' (modelled/imputed). derived/estimated need `method`.
                A derived record needs `inputs` (the prov_ids it is computed from) or `raw`.
                An estimated record needs `inputs`, `raw`, or `notes` citing the document behind it.
        """
        if status not in STATUSES:
            raise UnitError(f"status must be one of {STATUSES}, got {status!r}")
        if not re.match(PRICE_BASIS_RE, price_basis):
            raise UnitError(f"bad price_basis {price_basis!r}")
        if raw is None and status == "official":
            raise UnitError("an official provenance record needs the raw file it was read from")
        if status != "official" and not (method and method.strip()):
            raise UnitError(f"a {status} provenance record needs a method")
        if status == "derived" and raw is None and not inputs:
            raise UnitError(
                "a derived provenance record needs `inputs` (the prov_ids it is computed from) or the `raw` file it "
                "is computed from; otherwise its numbers cannot be traced (SPEC rule 1)"
            )
        if status == "estimated" and raw is None and not inputs and not (notes and notes.strip()):
            raise UnitError(
                "an estimated provenance record needs `inputs`, a `raw` file, or `notes` citing the document or "
                "assumption it rests on; otherwise its numbers cannot be traced (SPEC rule 1)"
            )
        sid = source_id or (raw.source_id if raw else None)
        if sid is None:
            raise UnitError("source_id is required when raw is None")
        self._check_source(sid)
        rec: dict[str, Any] = {
            "ingest_unit": self.unit,
            "source_id": sid,
            "url": raw.url if raw else None,
            "raw_path": raw.rel_path if raw else None,
            "raw_sha256": raw.sha256 if raw else None,
            "retrieved_at": raw.retrieved_at if raw else None,
            "table_id": table_id,
            "locator": locator,
            "unit_as_published": unit_as_published,
            "conversion": conversion,
            "price_basis": price_basis,
            "base_year": base_year,
            "vintage": vintage,
            "release": release,
            "status": status,
            "method": method,
            "inputs": ",".join(sorted(set(inputs))) or None,
            "notes": notes,
        }
        pid = f"{self.unit}:{io.sha256_bytes(io.dumps_json(rec, indent=None).encode())[:12]}"
        self.provenance[pid] = {"prov_id": pid, **rec}
        return pid

    def provenance_frame(self) -> pl.DataFrame:
        rows = [self.provenance[k] for k in sorted(self.provenance)]
        return pl.DataFrame(rows, schema=PROV_DTYPES, orient="row") if rows else pl.DataFrame(schema=PROV_DTYPES)


# ---------------------------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------------------------


def unit_names(layout: Layout | None = None) -> list[str]:
    """Names of all unit modules/packages in pipeline/ingest (without importing them)."""
    layout = layout or Layout.default()
    names = [m.name for m in pkgutil.iter_modules([str(layout.ingest_dir)]) if not m.name.startswith("_")]
    return sorted(names)


def load_unit(name: str, layout: Layout | None = None) -> ModuleType:
    """Import one unit and check its contract. Importing one unit never imports the others."""
    layout = layout or Layout.default()
    if not UNIT_ID_RE.match(name):
        raise UnitError(f"bad unit name {name!r}")
    if name not in unit_names(layout):
        raise UnitError(f"no unit {name!r} in pipeline/ingest (known: {', '.join(unit_names(layout)) or 'none'})")
    mod = importlib.import_module(f"{INGEST_PACKAGE}.{name}")
    check_contract(mod, name, layout)
    return mod


def check_contract(mod: ModuleType, name: str | None = None, layout: Layout | None = None) -> None:
    """UNIT, SOURCES, fetch and build exist and are well-formed; every source is registered, its
    registry addition (if any) is valid, and the access policy allows it (pipeline/core/policy.py)."""
    name = name or getattr(mod, "UNIT", None)
    if not isinstance(name, str) or not UNIT_ID_RE.match(name):
        raise UnitError(f"bad unit id {name!r}")
    problems = []
    if getattr(mod, "UNIT", None) != name:
        problems.append(f"UNIT must be {name!r} (the module name), got {getattr(mod, 'UNIT', None)!r}")
    sources = getattr(mod, "SOURCES", None)
    if not isinstance(sources, (list, tuple)) or not sources or not all(isinstance(s, str) for s in sources):
        problems.append("SOURCES must be a non-empty list of registry source ids")
    deps = getattr(mod, "DEPENDS", [])
    if not isinstance(deps, (list, tuple)) or not all(isinstance(d, str) and UNIT_ID_RE.match(d) for d in deps):
        problems.append("DEPENDS, if present, must be a list of unit ids")
    elif name in deps:
        problems.append("a unit cannot depend on itself")
    for fn in ("fetch", "build"):
        if not callable(getattr(mod, fn, None)):
            problems.append(f"missing function {fn}(ctx)")
    if problems:
        raise UnitError(f"unit {name}: " + "; ".join(problems))
    try:
        require_sources(sources, layout, unit=name)
    except RegistryError as e:
        raise UnitError(f"unit {name}: registry additions: {e}") from None
    refused = [r for s in sources if (r := source_refusal(s, get_source(s, layout)))]
    if refused:
        raise UnitError(f"unit {name}: access policy (DECISIONS.md D1-1/D1-2): " + "; ".join(refused))


__all__ = [
    "ESTIMATE_STAGES",
    "BuildContext",
    "Dataset",
    "FetchContext",
    "RawFile",
    "UnitError",
    "check_contract",
    "load_unit",
    "unit_names",
]
