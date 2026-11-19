"""``python -m pipeline``: re-executes itself with the pinned environment, then runs the CLI."""

from __future__ import annotations

import os
import subprocess
import sys

from pipeline.core.env import REEXEC_VAR, env_mismatches, pinned_environ


def main() -> int:
    bad = env_mismatches()
    if bad:
        if os.environ.get(REEXEC_VAR) == "1":
            print(f"pipeline: pinned environment could not be applied: {bad}", file=sys.stderr)
            return 2
        env = pinned_environ({REEXEC_VAR: "1"})
        return subprocess.call([sys.executable, "-m", "pipeline", *sys.argv[1:]], env=env)
    os.environ.pop(REEXEC_VAR, None)  # verified; do not leak the marker into child processes
    from pipeline.cli import main as cli_main

    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
