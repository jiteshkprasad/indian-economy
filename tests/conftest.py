"""Shared pytest setup.

Run tests through `uv run python -m pipeline test` (or `just test`): that pins threads and the hash
seed. If pytest is started directly, the thread variables are still pinned here before numpy or
polars load; PYTHONHASHSEED cannot be changed in-process, so hash-seed tests use subprocesses.
"""

from __future__ import annotations

import os

from pipeline.core.env import PINNED_ENV

for _k, _v in PINNED_ENV.items():
    if _k != "PYTHONHASHSEED":
        os.environ.setdefault(_k, _v)

import pytest  # noqa: E402

from pipeline.core.paths import Layout  # noqa: E402


@pytest.fixture
def repo_layout() -> Layout:
    return Layout.default()


@pytest.fixture
def tmp_layout(tmp_path) -> Layout:
    """Outputs, raw cache and pins under tmp_path; registry and gap map from the repo."""
    return Layout.scratch(tmp_path)
