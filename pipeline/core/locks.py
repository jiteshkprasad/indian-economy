"""Inter-process locks that the operating system releases when the holder dies.

Used for the repo write lock (data/.pipeline.lock) and the per-host fetch locks. The lock is an
OS byte-range lock (Windows `msvcrt.locking`) or `flock` (POSIX) on a lock file that is never
deleted. If a process is killed while holding it (a tool timeout, TerminateProcess, kill -9),
the OS drops the lock with the process, so no stale lock can block other agents. The holder's
pid, host and start time are written next to the lock (`<lock>.holder`) only for error messages.

Only the standard library is used.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class LockTimeout(TimeoutError):
    """Another live process held the lock for longer than the caller was willing to wait."""


def _try_lock(fd: int) -> bool:
    if sys.platform == "win32":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(fd: int) -> None:
    if sys.platform == "win32":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


def _holder_path(path: Path) -> Path:
    return path.with_name(path.name + ".holder")


def holder(path: Path) -> str:
    """Who holds (or last held) the lock, for messages."""
    try:
        d = json.loads(_holder_path(path).read_text(encoding="utf-8"))
        return f"pid {d.get('pid')} on {d.get('host')} since {d.get('since')}"
    except OSError, ValueError:
        return "unknown process"


@contextmanager
def file_lock(path: Path, *, timeout_s: float, what: str, poll_s: float = 0.1) -> Iterator[None]:
    """Hold an exclusive lock on `path` for the duration of the block.

    Waits up to `timeout_s` while another live process holds it, then raises LockTimeout. A lock
    held by a dead process is released by the OS, so it never needs breaking. Not re-entrant: do
    not nest two `file_lock`s on the same path in one process.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        deadline = time.monotonic() + timeout_s
        while not _try_lock(fd):
            if time.monotonic() > deadline:
                raise LockTimeout(
                    f"timed out after {timeout_s:.0f} s waiting for {what} ({path}), held by {holder(path)}. "
                    "That process is still alive; wait for it or stop it."
                )
            time.sleep(poll_s)
        try:
            try:
                info = {
                    "pid": os.getpid(),
                    "host": socket.gethostname(),
                    "since": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                _holder_path(path).write_text(json.dumps(info), encoding="utf-8")
            except OSError:
                pass  # informational only
            yield
        finally:
            _unlock(fd)
    finally:
        os.close(fd)
