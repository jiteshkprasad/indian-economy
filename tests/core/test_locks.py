"""OS-released locks: a killed holder never blocks anyone (repo write lock and host fetch locks)."""

import subprocess
import sys
import time

import pytest

from pipeline.core.locks import LockTimeout, file_lock
from pipeline.core.manifest import repo_lock
from pipeline.core.paths import REPO_ROOT

pytestmark = pytest.mark.unit

HOLDER = """
import sys, time
from pathlib import Path
from pipeline.core.locks import file_lock
with file_lock(Path(sys.argv[1]), timeout_s=5, what="test lock"):
    print("held", flush=True)
    time.sleep(120)
"""


def _hold(path):
    p = subprocess.Popen([sys.executable, "-c", HOLDER, str(path)], cwd=REPO_ROOT, stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "held"
    return p


def test_live_holder_blocks_and_killed_holder_releases(tmp_path):
    lock = tmp_path / "x.lock"
    p = _hold(lock)
    try:
        with pytest.raises(LockTimeout, match="held by pid"):
            with file_lock(lock, timeout_s=0.5, what="test lock"):
                pass
    finally:
        p.kill()  # TerminateProcess on Windows, SIGKILL on POSIX: no `finally` runs in the holder
        p.wait()
    t0 = time.monotonic()
    with file_lock(lock, timeout_s=10, what="test lock"):
        pass
    assert time.monotonic() - t0 < 5  # released with the process, not after a staleness timeout


def test_leftover_lock_file_from_old_code_does_not_block(tmp_layout):
    tmp_layout.lock.parent.mkdir(parents=True, exist_ok=True)
    tmp_layout.lock.write_text("99999", encoding="utf-8")  # the old O_EXCL lock of a dead pid
    t0 = time.monotonic()
    with repo_lock(tmp_layout, timeout_s=5):
        pass
    assert time.monotonic() - t0 < 2


def test_lock_is_exclusive_within_one_process(tmp_path):
    lock = tmp_path / "y.lock"
    with file_lock(lock, timeout_s=1, what="outer"):
        with pytest.raises(LockTimeout):
            with file_lock(lock, timeout_s=0.3, what="inner"):
                pass
    with file_lock(lock, timeout_s=1, what="again"):
        pass
