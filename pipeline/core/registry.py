"""Read-only access to the source registry.

The registry is data/registry.yaml (Phase 0, owned by the orchestrator) plus per-unit addition
files data/registry_additions/<unit>.yaml, which is how an ingest agent registers a source it
needs without editing the shared file (the orchestrator later merges them into registry.yaml).
Every `source_id` used anywhere in the pipeline must exist in one of them; an unknown id is a
hard error.

Addition files are validated one at a time. A malformed file, or two files adding the same id,
breaks only the units that own those files (and any unit that uses an id they declare); the
rest of the registry keeps working. The file name must be an existing unit.

An addition file looks like:

    unit: rbi_bop
    sources:
    - id: rbi_bop_quarterly_press_release
      name: ...
      publisher: ...
      family: rbi_core
      urls: {landing: https://..., data: [https://...]}
      access: {method: ..., requires: none}
      license: {name: ..., url: https://...}
      verification: {status: unverified, notes: why it was added and what was checked}
"""

from __future__ import annotations

import functools
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from pipeline.core.paths import Layout

try:  # the C loader is ~10x faster on the 8,000-line registry
    _Loader = yaml.CSafeLoader
except AttributeError:  # pragma: no cover
    _Loader = yaml.SafeLoader

ADDITION_REQUIRED = ("id", "name", "publisher", "family", "urls", "access", "license", "verification")


class UnknownSourceError(KeyError):
    """A source_id that is not in the registry."""

    def __str__(self) -> str:  # KeyError quotes its message; keep it readable
        return str(self.args[0]) if self.args else "unknown source"


class RegistryError(ValueError):
    """A malformed registry or registry-addition file."""


def _read(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return yaml.load(f, Loader=_Loader)


@dataclass(frozen=True)
class _Registry:
    entries: dict[str, dict[str, Any]]  # usable entries by id
    problems: dict[str, tuple[str, ...]]  # addition-file unit -> problems in its file
    broken: dict[str, str]  # id -> why it is unusable (declared in a broken or colliding addition)


def _unit_exists(layout_root: Path, unit: str) -> bool:
    ingest = layout_root / "pipeline" / "ingest"
    return (ingest / f"{unit}.py").exists() or (ingest / unit / "__init__.py").exists()


@functools.cache
def _load(path: Path, additions_dir: Path, root: Path, _stamp: tuple[tuple[str, float], ...]) -> _Registry:
    out: dict[str, dict[str, Any]] = {}
    for entry in (_read(path) or {}).get("sources", []):
        sid = entry.get("id")
        if not sid:
            raise RegistryError(f"{path}: registry entry without an id: {entry.get('name')!r}")
        if sid in out:
            raise RegistryError(f"{path}: duplicate source id {sid!r}")
        out[sid] = entry

    # Addition files are validated one by one. A broken file only breaks its own unit (and any
    # unit that uses an id it declares); every other unit keeps working.
    problems: dict[str, list[str]] = {}
    broken: dict[str, str] = {}
    candidates: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for add in sorted(additions_dir.glob("*.yaml")) if additions_dir.exists() else []:
        unit = add.stem
        errs = problems.setdefault(unit, [])
        where = f"data/registry_additions/{add.name}"
        try:
            doc = _read(add) or {}
        except yaml.YAMLError as e:
            errs.append(f"{where}: not valid YAML: {e}")
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get("sources") or [], list):
            errs.append(f"{where}: must be a mapping with 'unit' and a 'sources' list")
            continue
        if doc.get("unit") != unit:
            errs.append(f"{where}: 'unit' must be {unit!r} (the file name)")
        if not _unit_exists(root, unit):
            errs.append(f"{where}: there is no ingest unit {unit!r} in pipeline/ingest (the file name must be a unit)")
        file_ok = not errs
        for i, entry in enumerate(doc.get("sources") or []):
            if not isinstance(entry, dict):
                errs.append(f"{where}: sources[{i}] is not a mapping")
                continue
            sid = entry.get("id")
            bad = []
            missing = [k for k in ADDITION_REQUIRED if k not in entry]
            if missing:
                bad.append(f"entry {sid!r} lacks {missing}")
            if (entry.get("verification") or {}).get("status") != "unverified":
                bad.append(f"{sid}: added sources must have verification.status 'unverified'")
            if sid in out:
                bad.append(f"source id {sid!r} already exists in data/registry.yaml")
            if bad:
                errs.extend(f"{where}: {b}" for b in bad)
                if isinstance(sid, str) and sid not in out:
                    broken[sid] = f"{where} declares {sid!r} but the entry is invalid: {'; '.join(bad)}"
                continue
            if file_ok:
                candidates.setdefault(sid, []).append((unit, entry))
            elif isinstance(sid, str):
                broken[sid] = f"{where} declares {sid!r} but the file is invalid: {'; '.join(errs)}"
    for sid, owners in candidates.items():
        if sid in broken:
            continue
        if len(owners) > 1:
            units = [u for u, _ in owners]
            msg = f"source id {sid!r} is added by several addition files ({', '.join(units)}); keep it in one"
            broken[sid] = msg
            for u in units:
                problems[u].append(f"data/registry_additions/{u}.yaml: {msg}")
            continue
        unit, entry = owners[0]
        out[sid] = entry | {"_added_by": unit}
    return _Registry(out, {u: tuple(e) for u, e in problems.items() if e}, broken)


def _registry(layout: Layout | None) -> _Registry:
    layout = layout or Layout.default()
    adds = layout.registry_additions
    files = [layout.registry, *(sorted(adds.glob("*.yaml")) if adds.exists() else [])]
    stamp = tuple((p.as_posix(), p.stat().st_mtime) for p in files)
    return _load(layout.registry.resolve(), adds.resolve(), layout.root.resolve(), stamp)


def load_registry(layout: Layout | None = None) -> dict[str, dict[str, Any]]:
    """All usable registry entries (registry.yaml + valid additions) keyed by source id. Cached per file state."""
    return _registry(layout).entries


def registry_problems(layout: Layout | None = None) -> dict[str, tuple[str, ...]]:
    """{unit: problems} for addition files that are invalid. Each problem belongs to that unit only."""
    return _registry(layout).problems


def source_ids(layout: Layout | None = None) -> frozenset[str]:
    return frozenset(load_registry(layout))


def get_source(source_id: str, layout: Layout | None = None) -> dict[str, Any]:
    """The registry entry for `source_id`; raises UnknownSourceError if it does not exist and
    RegistryError if it is declared only in an invalid addition file."""
    reg = _registry(layout)
    if source_id in reg.entries:
        return reg.entries[source_id]
    if source_id in reg.broken:
        raise RegistryError(reg.broken[source_id])
    raise UnknownSourceError(
        f"source_id {source_id!r} is not in data/registry.yaml or data/registry_additions/. Use an existing "
        "id, or add one as described in docs/phase1/PIPELINE_GUIDE.md (section 'New sources')."
    )


def require_sources(ids: Iterable[str], layout: Layout | None = None, unit: str | None = None) -> None:
    """Raise unless every id in `ids` is usable, and (if `unit` is given) the unit's own addition
    file is valid. UnknownSourceError for unregistered ids, RegistryError for invalid additions."""
    reg = _registry(layout)
    ids = sorted(set(ids))
    broken = [reg.broken[i] for i in ids if i not in reg.entries and i in reg.broken]
    own = list(reg.problems.get(unit, ())) if unit else []
    if broken or own:
        raise RegistryError("; ".join(dict.fromkeys([*own, *broken])))
    missing = [i for i in ids if i not in reg.entries]
    if missing:
        raise UnknownSourceError(f"source_id(s) not in the registry: {', '.join(missing)}")
