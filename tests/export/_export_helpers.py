"""Helpers shared by tests/export (imported as `_export_helpers`; pytest puts this folder on sys.path)."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
ROOTS = {"real": REPO / "web" / "public" / "data", "fixture": REPO / "web" / "fixtures" / "data"}
SAM = REPO / "data" / "sam" / "2023-24"
TS = REPO / "data" / "timeseries"


class Export:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.index = json.loads((root / "index.json").read_text(encoding="utf-8"))
        self.version = self.index["data_version"]
        self.vdir = root / self.version

    @cache  # noqa: B019 (a handful of instances per session)
    def get(self, rel: str) -> Any:
        return json.loads((self.vdir / rel).read_text(encoding="utf-8"))

    def files(self) -> list[str]:
        return sorted(self.index["files"])


@cache
def exported(kind: str) -> Export:
    root = ROOTS[kind]
    if not (root / "index.json").exists():
        flag = " --fixture" if kind == "fixture" else ""
        pytest.skip(f"{kind} export not found at {root} (run `uv run python -m pipeline export{flag}`)")
    return Export(root)
