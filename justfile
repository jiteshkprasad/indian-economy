# One-command runner (STACK_AND_REPO s1.8). Every recipe is a single call into the Python CLI, so
# `uv run python -m pipeline <cmd>` does exactly the same thing without `just`.
# Install just (user level, no admin): uv tool install rust-just
#
# Recipes run as Python (`uv run python -c`) with positional arguments, the same on Windows,
# macOS and Linux. Arguments reach the CLI as a list, so quoting survives:
#   just test -k "s8_17_1 and not live"
# sys.argv inside a recipe is ['-c', <recipe name>, <args...>].

set positional-arguments
set shell := ["uv", "run", "--locked", "python", "-c"]
set windows-shell := ["uv", "run", "--locked", "python", "-c"]

# list recipes
default:
    @import subprocess, sys; sys.exit(subprocess.call(["just", "--list"]))

# install Python 3.14 and the locked packages
setup:
    @import subprocess, sys; sys.exit(subprocess.call(["uv", "sync", "--locked"]))

# download and pin raw files: just fetch [UNIT ...] [--offline] [--refresh] [--prune]
fetch *args:
    @import subprocess, sys; sys.exit(subprocess.call([sys.executable, "-m", "pipeline", *sys.argv[1:]]))

# offline build from pinned raw files: just build [UNIT ...] [--with-deps]
build *args:
    @import subprocess, sys; sys.exit(subprocess.call([sys.executable, "-m", "pipeline", *sys.argv[1:]]))

# offline tests (live tests excluded): just test [PYTEST ARGS ...]
test *args:
    @import subprocess, sys; sys.exit(subprocess.call([sys.executable, "-m", "pipeline", *sys.argv[1:]]))

# network canaries only
test-live *args:
    @import subprocess, sys; sys.exit(subprocess.call([sys.executable, "-m", "pipeline", "test", "-m", "live", *sys.argv[2:]]))

# With UNITs, only those units' code + pipeline/core + uv.lock must stay unedited during the builds.
# build three times (two hash seeds, two thread counts) and compare hashes: just repro [UNIT ...]
repro *args:
    @import subprocess, sys; sys.exit(subprocess.call([sys.executable, "-m", "pipeline", *sys.argv[1:]]))

# regenerate data/manifest.json (add --check to only verify)
manifest *args:
    @import subprocess, sys; sys.exit(subprocess.call([sys.executable, "-m", "pipeline", *sys.argv[1:]]))

# gap-map coverage report: just coverage [UNIT ...]
coverage *args:
    @import subprocess, sys; sys.exit(subprocess.call([sys.executable, "-m", "pipeline", *sys.argv[1:]]))

# units, sources, pins and datasets
list:
    @import subprocess, sys; sys.exit(subprocess.call([sys.executable, "-m", "pipeline", *sys.argv[1:]]))

# every pinned raw file exists and matches its sha256
verify-raw *args:
    @import subprocess, sys; sys.exit(subprocess.call([sys.executable, "-m", "pipeline", *sys.argv[1:]]))

# Phase 2: build SAM blocks and (with no BLOCK, once all are built) balance: just sam [BLOCK ...] [--with-deps] [--no-balance]
sam *args:
    @import subprocess, sys; sys.exit(subprocess.call([sys.executable, "-m", "pipeline", *sys.argv[1:]]))

# regenerate BALANCING.md from the balancing outputs
sam-report *args:
    @import subprocess, sys; sys.exit(subprocess.call([sys.executable, "-m", "pipeline", *sys.argv[1:]]))

# Phase 2 post-SAM step: the top-flows time series (data/timeseries/): just timeseries
timeseries *args:
    @import subprocess, sys; sys.exit(subprocess.call([sys.executable, "-m", "pipeline", *sys.argv[1:]]))

# Phase 3: export web JSON (web/public/data/): just export [--check | --fixture]
export *args:
    @import subprocess, sys; sys.exit(subprocess.call([sys.executable, "-m", "pipeline", *sys.argv[1:]]))

# Phase 3: local website (needs Node 24: export PATH=/opt/homebrew/opt/node@24/bin:$PATH; npm ci in web/)
web *args:
    @import shutil, subprocess, sys; npm = shutil.which("npm") or sys.exit("npm not found on PATH"); sys.exit(subprocess.call([npm, "--prefix", "web", "run", "dev", "--", *sys.argv[2:]]))

# Phase 3: build + first-load budget + Playwright e2e and axe; args go to Playwright only
test-web *args:
    @import shutil, subprocess, sys; npm = shutil.which("npm") or sys.exit("npm not found on PATH"); sys.exit(subprocess.call([npm, "--prefix", "web", "run", "test:web", "--", *sys.argv[2:]]))
