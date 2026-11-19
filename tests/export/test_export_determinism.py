"""The export is byte-identical under PYTHONHASHSEED 0 and 1 (PLAN s.3.1, s.5.1 item 8)."""

from __future__ import annotations

import subprocess
import sys

import pytest
from _export_helpers import REPO

from pipeline.core.env import ALLOW_HASHSEED_VAR, REEXEC_VAR, pinned_environ

pytestmark = pytest.mark.export


@pytest.mark.parametrize("fixture", [False, True])
def test_hash_seed_independent(tmp_path, fixture: bool) -> None:
    outs = []
    for seed in ("0", "1"):
        out = tmp_path / f"seed{seed}"
        env = pinned_environ({"PYTHONHASHSEED": seed, ALLOW_HASHSEED_VAR: "1", REEXEC_VAR: "1"})
        args = [sys.executable, "-m", "pipeline", "export", "--out", str(out), *(["--fixture"] if fixture else [])]
        p = subprocess.run(args, cwd=REPO, env=env, capture_output=True, text=True)
        assert p.returncode == 0, p.stdout + p.stderr
        outs.append({q.relative_to(out).as_posix(): q.read_bytes() for q in out.rglob("*") if q.is_file()})
    assert outs[0].keys() == outs[1].keys()
    diff = [k for k in outs[0] if outs[0][k] != outs[1][k]]
    assert not diff, diff
