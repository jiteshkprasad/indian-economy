"""Bytes of the exported JSON (PLAN s.3.3, s.4.13, s.5.1 item 7)."""

from __future__ import annotations

import gzip
import hashlib
import json
import re

import pytest

pytestmark = pytest.mark.export

KB = 1024
FIRST_VIEW = ("summary.json", "hierarchy.json", "sam/cells.json", "sam/pinned.json", "ts/view.json")


def _bytes(ex, rel: str) -> bytes:
    return (ex.vdir / rel).read_bytes()


def test_no_nan_no_negative_zero_utf8_lf(ex) -> None:
    for rel in [*ex.files()]:
        b = _bytes(ex, rel)
        t = b.decode("utf-8")
        assert "\r" not in t and t.endswith("\n") and t.count("\n") == 1, rel
        assert not re.search(r"\bNaN\b|\bInfinity\b", t), rel
        assert not re.search(r"[:\[,]-0(\.0+)?[,\]}]", t), rel

        def bad(c: str, rel: str = rel) -> None:
            pytest.fail(f"{rel}: {c}")

        json.loads(t, parse_constant=bad)


def test_index_hashes(ex) -> None:
    for rel, meta in ex.index["files"].items():
        b = _bytes(ex, rel)
        assert hashlib.sha256(b).hexdigest() == meta["sha256"] and len(b) == meta["bytes"], rel
    on_disk = sorted(p.relative_to(ex.vdir).as_posix() for p in ex.vdir.rglob("*") if p.is_file())
    assert on_disk == sorted(ex.index["files"])


def test_size_budgets(real) -> None:
    gz = {rel: len(gzip.compress(_bytes(real, rel), 9)) for rel in real.files()}
    # first view without map-text.json (U6's file; U2's first-load check covers the whole page)
    assert sum(gz[r] for r in FIRST_VIEW) <= 120 * KB
    assert gz["ts/series.json"] <= 60 * KB
    for rel, n in gz.items():
        if rel not in FIRST_VIEW:
            assert n <= 120 * KB, (rel, n)
