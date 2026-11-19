"""The committed export equals a fresh export (`python -m pipeline export --check`), real and fixture."""

from __future__ import annotations

import subprocess
import sys

import pytest
from _export_helpers import REPO, ROOTS

pytestmark = pytest.mark.export


@pytest.mark.parametrize("kind", ["real", "fixture"])
def test_export_check(kind: str) -> None:
    if not (ROOTS[kind] / "index.json").exists():
        pytest.skip(f"no {kind} export on disk")
    args = [sys.executable, "-m", "pipeline", "export", "--check", *(["--fixture"] if kind == "fixture" else [])]
    p = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
