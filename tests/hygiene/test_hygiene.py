"""Repository hygiene: LF line endings, order-controlled polars calls, pinned environment."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from pipeline.core.env import PINNED_ENV
from pipeline.core.paths import REPO_ROOT
from pipeline.core.unit import unit_names

pytestmark = pytest.mark.hygiene

BINARY_SUFFIXES = {".parquet", ".xlsx", ".xlsm", ".xlsb", ".xls", ".ods", ".pdf", ".zip", ".gz", ".png", ".jpg"}


def _repo_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout
    return [REPO_ROOT / p for p in out.decode("utf-8").split("\0") if p]


UNITS = sorted(unit_names(), key=len, reverse=True)


def _owner(rel: str) -> str:
    """The ingest unit a repo file belongs to (by path component or file-name prefix), or 'shared'.
    Used for test ids, so `test -k <unit>` runs the hygiene checks on that unit's files only."""
    parts = rel.split("/")
    for u in UNITS:
        for part in parts:
            stem = part.split(".", 1)[0]
            if stem == u or stem.startswith((u + "_", f"test_{u}", f"_{u}_")) or part == u:
                return u
    return "shared"


def _by_owner(files: list[Path]) -> dict[str, list[Path]]:
    out: dict[str, list[Path]] = {}
    for p in files:
        out.setdefault(_owner(p.relative_to(REPO_ROOT).as_posix()), []).append(p)
    return dict(sorted(out.items()))


TEXT_FILES = _by_owner([p for p in _repo_files() if p.suffix.lower() not in BINARY_SUFFIXES])
PY_FILES = _by_owner(sorted((REPO_ROOT / "pipeline").rglob("*.py")))


@pytest.mark.parametrize("owner", list(TEXT_FILES), ids=[f"crlf-{o}" for o in TEXT_FILES])
def test_no_crlf_in_text_files(owner):
    bad = []
    for p in TEXT_FILES[owner]:
        if not p.is_file():
            continue
        data = p.read_bytes()
        if b"\0" in data[:8192]:
            continue
        if b"\r\n" in data:
            bad.append(p.relative_to(REPO_ROOT).as_posix())
    assert not bad, f"CRLF line endings (hashes differ across OSes): {bad}"


def _calls(src: str, name: str):
    """Yield the full text of each `.name(...)` call (balanced parentheses) and what follows it."""
    for m in re.finditer(rf"\.{name}\(", src):
        depth, i = 1, m.end()
        while depth and i < len(src):
            depth += {"(": 1, ")": -1}.get(src[i], 0)
            i += 1
        yield src[m.start() : i], src[i : i + 40]


@pytest.mark.parametrize("owner", list(PY_FILES), ids=[f"order-{o}" for o in PY_FILES])
def test_group_by_and_unique_control_order(owner):
    """polars group_by/unique return groups in arbitrary order unless maintain_order=True or an
    explicit sort follows (STACK_AND_REPO s1.5 rule 3)."""
    bad = []
    for p in PY_FILES[owner]:
        src = p.read_text(encoding="utf-8")
        for name in ("group_by", "unique"):
            for call, after in _calls(src, name):
                if "maintain_order" in call or after.lstrip().startswith(".sort("):
                    continue
                if name == "unique" and ".to_list()" in after[:12]:
                    continue  # set-like use (membership), order irrelevant
                line = src[: src.index(call)].count("\n") + 1
                bad.append(f"{p.relative_to(REPO_ROOT).as_posix()}:{line}: {call[:60]}")
    assert not bad, "order-uncontrolled polars calls:\n" + "\n".join(bad)


def test_pinned_environment_when_run_through_the_runner():
    missing = {k: (os.environ.get(k), v) for k, v in PINNED_ENV.items() if os.environ.get(k) != v}
    assert not missing, (
        f"pinned environment missing {missing}: run tests with `uv run python -m pipeline test` (or `just test`)"
    )


def test_cli_reexecs_with_pinned_env():
    env = {k: v for k, v in os.environ.items() if k not in PINNED_ENV}
    r = subprocess.run([sys.executable, "-m", "pipeline", "list"], cwd=REPO_ROOT, env=env, capture_output=True)
    assert r.returncode == 0, r.stderr.decode(errors="replace")
