"""Where things live. Every path used by the framework comes from a `Layout`, so tests and the
repro command can redirect outputs to a scratch folder without touching the real data tree."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_YEAR = "2023-24"  # DECISIONS.md D0-3
HOST_LOCK_DIR_VAR = "INDIA_SAM_HOST_LOCK_DIR"


def host_lock_dir() -> Path:
    """One machine-wide (per user) folder for the per-host fetch locks and last-request stamps.

    It does not depend on the Layout or the checkout, so every process on this machine (scratch
    layouts, live tests, other worktrees) shares the same >= 2 s per-host spacing (DECISIONS D1-1a).
    Override with the environment variable INDIA_SAM_HOST_LOCK_DIR.
    """
    override = os.environ.get(HOST_LOCK_DIR_VAR)
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "india-sam" / "host-locks"


@dataclass(frozen=True)
class Layout:
    root: Path  # repo root: code, registry, gap map
    raw: Path  # data/raw: downloaded files (git-ignored except .meta.json sidecars)
    pins: Path  # data/raw_pins: one <unit>.yaml per ingest unit (committed)
    clean: Path  # data/clean: <unit>/<dataset>.parquet + <unit>/_provenance.parquet
    manifest: Path  # data/manifest.json
    runs: Path  # data/runs: volatile run logs and repro scratch (git-ignored)

    @classmethod
    def default(cls) -> Layout:
        d = REPO_ROOT / "data"
        return cls(
            root=REPO_ROOT,
            raw=d / "raw",
            pins=d / "raw_pins",
            clean=d / "clean",
            manifest=d / "manifest.json",
            runs=d / "runs",
        )

    @classmethod
    def scratch(cls, base: Path, *, raw: Path | None = None, pins: Path | None = None) -> Layout:
        """A layout whose outputs live under `base` (registry and gap map stay in the repo)."""
        base = Path(base)
        return cls(
            root=REPO_ROOT,
            raw=raw or base / "raw",
            pins=pins or base / "raw_pins",
            clean=base / "clean",
            manifest=base / "manifest.json",
            runs=base / "runs",
        )

    def with_outputs(self, base: Path) -> Layout:
        """Same raw files and pins, but clean outputs and manifest under `base` (used by repro)."""
        base = Path(base)
        return replace(self, clean=base / "clean", manifest=base / "manifest.json")

    @property
    def registry(self) -> Path:
        return self.root / "data" / "registry.yaml"

    @property
    def registry_additions(self) -> Path:
        return self.root / "data" / "registry_additions"

    @property
    def gap_map(self) -> Path:
        return self.root / "data" / "gap_map.csv"

    @property
    def ingest_dir(self) -> Path:
        return self.root / "pipeline" / "ingest"

    @property
    def lock(self) -> Path:
        return self.clean.parent / ".pipeline.lock"

    def raw_rel(self, path: Path) -> str:
        """Portable path of a raw file: 'data/raw/<source_id>/<date>/<name>' (independent of layout)."""
        return "data/raw/" + Path(path).resolve().relative_to(self.raw.resolve()).as_posix()

    def raw_abs(self, rel: str) -> Path:
        if not rel.startswith("data/raw/"):
            raise ValueError(f"not a raw path: {rel!r}")
        return self.raw / rel[len("data/raw/") :]

    def clean_rel(self, path: Path) -> str:
        return "data/clean/" + Path(path).resolve().relative_to(self.clean.resolve()).as_posix()

    # --- Phase 2 (SAM). Derived from `clean` so that scratch and repro layouts (with_outputs) move the
    # SAM outputs together with the clean outputs they are built from.
    @property
    def sam(self) -> Path:
        """data/sam: SAM outputs, one folder per reference year (data/sam/2023-24/)."""
        return self.clean.parent / "sam"

    @property
    def balancing_report(self) -> Path:
        """BALANCING.md: at the repo root for the real data tree, next to the outputs for scratch layouts."""
        if self.clean.resolve() == (self.root / "data" / "clean").resolve():
            return self.root / "BALANCING.md"
        return self.clean.parent / "BALANCING.md"

    @property
    def concordance(self) -> Path:
        """data/concordance: committed classification concordances (e.g. SUT -> 34 SAM sectors)."""
        return self.root / "data" / "concordance"

    def sam_rel(self, path: Path) -> str:
        return "data/sam/" + Path(path).resolve().relative_to(self.sam.resolve()).as_posix()
