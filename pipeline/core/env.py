"""Pinned process environment for byte-reproducible builds (STACK_AND_REPO s1.5 rule 5).

Only the standard library may be imported here: this module is used before numpy/polars load.
"""

from __future__ import annotations

import os

PINNED_ENV: dict[str, str] = {
    "PYTHONHASHSEED": "0",
    "POLARS_MAX_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
}

# Set to "1" by the repro command so that a build can run under a different PYTHONHASHSEED
# (to prove hash-seed independence). Every other pinned variable must still match.
ALLOW_HASHSEED_VAR = "INDIA_SAM_ALLOW_ANY_HASHSEED"
# Set to "1" by the repro command so that a build can run with more threads (to prove that the
# outputs do not depend on the thread count, e.g. 28 local cores against a 4-vCPU CI runner).
ALLOW_THREADS_VAR = "INDIA_SAM_ALLOW_ANY_THREADS"
THREAD_VARS = ("POLARS_MAX_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
REEXEC_VAR = "INDIA_SAM_REEXEC"


def env_mismatches(environ: dict[str, str] | None = None) -> dict[str, tuple[str | None, str]]:
    """Return {name: (actual, expected)} for every pinned variable that is not set as required."""
    env = os.environ if environ is None else environ
    out: dict[str, tuple[str | None, str]] = {}
    for key, want in PINNED_ENV.items():
        have = env.get(key)
        if key == "PYTHONHASHSEED" and env.get(ALLOW_HASHSEED_VAR) == "1" and (have or "").isdigit():
            continue
        if key in THREAD_VARS and env.get(ALLOW_THREADS_VAR) == "1" and (have or "").isdigit():
            continue
        if have != want:
            out[key] = (have, want)
    return out


def pinned_environ(extra: dict[str, str] | None = None) -> dict[str, str]:
    """A copy of os.environ with the pinned variables applied (plus `extra`)."""
    env = dict(os.environ)
    env.update(PINNED_ENV)
    if extra:
        env.update(extra)
    return env
