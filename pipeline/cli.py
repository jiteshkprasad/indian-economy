"""Command line: `uv run python -m pipeline <command>` (the justfile recipes call exactly these).

  list                          units, their sources, pins and built datasets
  fetch   [UNIT ...] [--offline] [--refresh] [--prune]
                                download/pin raw files (network). --offline only verifies the cache.
                                --prune drops pins that fetch() no longer requests (clean runs only)
  build   [UNIT ...] [--with-deps] [--out DIR]
                                offline build: raw pins -> validated clean Parquet + manifest.
                                DEPENDS units are read as built; --with-deps rebuilds them too
  test    [PYTEST ARGS ...]     run pytest with the pinned environment (live tests excluded)
  repro   [UNIT ...]            build three times into data/runs/repro-<pid> (PYTHONHASHSEED 0 and 1 with
                                1 thread, then 4 threads) and compare hashes with each other and with
                                data/manifest.json (DEPENDS units are rebuilt too). With UNITs, only
                                those units' code hashes must stay fixed during the three builds
  manifest [--check]            regenerate data/manifest.json (--check: fail if it is out of date)
  coverage [UNIT ...] [--json PATH]
                                gap-map coverage report (only these units' entries if UNITs are given)
  verify-raw [UNIT ...]         every pinned raw file exists and matches its sha256
  sam     [BLOCK ...] [--with-deps] [--no-balance] [--solver NAME] [--out DIR]
                                Phase 2: build SAM blocks (default all, dependencies first). With no BLOCK,
                                once every DESIGN_BRIEF block is built: assemble, diagnose, balance and write
                                data/sam/<year>/ + BALANCING.md. With BLOCKs, balancing is skipped (said so)
  sam-report                    regenerate BALANCING.md from the balancing outputs
  export  [--out DIR] [--check] [--fixture]
                                Phase 3: the web data contract (web/public/data/, docs/phase3/PLAN.md s.3).
                                --check: compare a fresh export with what is on disk. --fixture: the generated
                                synthetic fixture (web/fixtures/data/)
  timeseries [--out DIR]        Phase 2 post-SAM step: the top-flows time series (data/timeseries/) from clean
                                data, with the 2023-24 check against the SAM definitions (DESIGN_BRIEF s.8)

UNIT may also be given as --unit UNIT (repeatable). No UNIT = all units.
A full `repro` (no UNIT) also runs `sam` and `timeseries` in each build and compares data/sam and
data/timeseries outputs and BALANCING.md.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from pipeline.core.env import ALLOW_HASHSEED_VAR, ALLOW_THREADS_VAR, REEXEC_VAR, THREAD_VARS, pinned_environ
from pipeline.core.paths import Layout


def _units(args: argparse.Namespace) -> list[str]:
    return list(dict.fromkeys([*(getattr(args, "units", None) or []), *(getattr(args, "unit", None) or [])]))


def cmd_list(layout: Layout) -> int:
    from pipeline.core.fetch import PinStore
    from pipeline.core.unit import load_unit, unit_names

    for n in unit_names(layout):
        try:
            mod = load_unit(n, layout)
            pins = PinStore.load(layout, n).pins
            built = sorted(p.stem for p in (layout.clean / n).glob("*.parquet") if not p.name.startswith("_"))
            print(
                f"{n}\n  sources: {', '.join(mod.SOURCES)}\n  pins: {len(pins)}\n  datasets: {', '.join(built) or '-'}"
            )
        except Exception as e:  # noqa: BLE001
            print(f"{n}\n  BROKEN: {type(e).__name__}: {e}")
    return 0


def cmd_fetch_build(command: str, args: argparse.Namespace, layout: Layout) -> int:
    from pipeline.core.runner import run, summarize

    if command == "build" and args.out:
        layout = layout.with_outputs(Path(args.out).resolve())
    results = run(
        command,
        _units(args),
        layout,
        offline=getattr(args, "offline", False),
        refresh=getattr(args, "refresh", False),
        with_deps=getattr(args, "with_deps", False),
        prune=getattr(args, "prune", False),
    )
    for r in results:
        if not r.ok and "\n" in r.message:
            print(f"\n--- {r.unit} traceback ---\n{r.message}")
    return summarize(results) if results else 1


NODE24_BIN = Path("/opt/homebrew/opt/node@24/bin")


def _vitest(layout: Layout) -> int:
    """Phase 3 web unit tests (vitest) on Node 24 (PLAN s.5, proposed D3-10). Fails loudly on the wrong Node or
    a missing web/node_modules."""
    env = dict(os.environ)
    if (NODE24_BIN / "node").exists():
        env["PATH"] = f"{NODE24_BIN}{os.pathsep}{env.get('PATH', '')}"
    node = shutil.which("node", path=env["PATH"])
    fix = "export PATH=/opt/homebrew/opt/node@24/bin:$PATH"
    if node is None:
        print(f"WEB UNIT TESTS FAILED: node not found. This project needs Node 24. Run: {fix}")
        return 1
    ver = subprocess.run([node, "-v"], capture_output=True, text=True, env=env).stdout.strip()
    if not ver.startswith("v24."):
        print(f"WEB UNIT TESTS FAILED: Node {ver} found at {node}; this project needs Node 24. Run: {fix}")
        return 1
    web = layout.root / "web"
    if not (web / "node_modules").exists():
        print("WEB UNIT TESTS FAILED: web/node_modules is missing (run `npm ci` in web/ with Node 24) or pass --no-web")
        return 1
    npm = shutil.which("npm", path=env["PATH"])
    if npm is None:
        print(f"WEB UNIT TESTS FAILED: npm not found next to Node 24. Run: {fix}")
        return 1
    print(f"== vitest (Node {ver})", flush=True)
    return subprocess.call([npm, "--prefix", str(web), "run", "test:unit"], cwd=layout.root, env=env)


def cmd_test(extra: list[str], layout: Layout) -> int:
    if extra and extra[0] == "--":
        extra = extra[1:]
    no_web = "--no-web" in extra
    extra = [a for a in extra if a != "--no-web"]
    rc = subprocess.call([sys.executable, "-m", "pytest", *extra], cwd=layout.root, env=pinned_environ())
    if no_web:
        print("WEB UNIT TESTS NOT RUN (--no-web)")
        return rc
    if extra:
        print("WEB UNIT TESTS NOT RUN (pytest arguments were given; run `test` with no arguments to include vitest)")
        return rc
    web_rc = _vitest(layout)
    return rc or web_rc


# Output trees a full repro rebuilds and compares (Phase 1 clean data, Phase 2 SAM, the post-SAM time series).
REPRO_OUTPUT_DIRS = ("data/clean/", "data/sam/", "data/timeseries/")


def cmd_repro(args: argparse.Namespace, layout: Layout) -> int:
    from pipeline.core.manifest import diff_manifests, frames_equal_within, read_manifest

    units = _units(args)
    base = layout.runs / f"repro-{os.getpid()}"  # per process: agents may run repro concurrently
    if base.exists():
        shutil.rmtree(base)
    # (PYTHONHASHSEED, threads): hash-seed independence, then thread-count independence.
    runs = (("0", "1"), ("1", "1"), ("0", "4"))
    manifests = []
    for i, (seed, threads) in enumerate(runs):
        out = base / f"run{i}"
        extra = {"PYTHONHASHSEED": seed, ALLOW_HASHSEED_VAR: "1", REEXEC_VAR: "1"}
        if threads != "1":
            extra |= {v: threads for v in THREAD_VARS} | {ALLOW_THREADS_VAR: "1"}
        env = pinned_environ(extra)
        print(f"== repro build {i + 1}/{len(runs)} (PYTHONHASHSEED={seed}, {threads} thread(s)) -> {out}", flush=True)
        rc = subprocess.call(
            [sys.executable, "-m", "pipeline", "build", *units, "--with-deps", "--out", str(out)],
            cwd=layout.root,
            env=env,
        )
        if rc != 0:
            print(f"repro: build {i + 1} failed (exit {rc})")
            return rc
        if not units:  # a full repro also rebuilds the SAM (Phase 2) from the freshly built clean data
            rc = subprocess.call([sys.executable, "-m", "pipeline", "sam", "--out", str(out)], cwd=layout.root, env=env)
            if rc != 0:
                print(f"repro: sam {i + 1} failed (exit {rc})")
                return rc
            rc = subprocess.call(
                [sys.executable, "-m", "pipeline", "timeseries", "--out", str(out)], cwd=layout.root, env=env
            )
            if rc != 0:
                print(f"repro: timeseries {i + 1} failed (exit {rc})")
                return rc
        manifests.append(read_manifest(out / "manifest.json"))
    m0 = manifests[0]
    failures = []
    for i in range(1, len(runs)):
        mi = manifests[i]
        d = diff_manifests(m0, mi)
        what = f"build 1 vs build {i + 1} (PYTHONHASHSEED={runs[i][0]}, {runs[i][1]} thread(s))"
        if d:
            failures.append(f"{what} differ:\n  " + "\n  ".join(d))
            for line in d:
                if line.startswith("differs: "):
                    rel = line.split(" ")[1]
                    if not rel.endswith(".parquet") or not rel.startswith(REPRO_OUTPUT_DIRS):
                        print(f"  {rel}: differs")
                        continue
                    kind, sub = rel[len("data/") :].split("/", 1)
                    same = frames_equal_within(base / "run0" / kind / sub, base / f"run{i}" / kind / sub)
                    verdict = "equal within 1e-9 (tolerance mode, NOT byte-identical)" if same else "values differ"
                    print(f"  {rel}: {verdict}")
        failures.extend(_code_hash_changes(m0, mi, scoped=bool(units)))
        print(f"{what}: {len(m0['files'])} files, {'identical' if not d else f'{len(d)} differences'}")

    if layout.manifest.exists():
        committed = read_manifest(layout.manifest)
        built = dict(m0["files"])
        stale = [
            f"{k}: {'not in data/manifest.json' if k not in committed['files'] else 'hash differs'}"
            for k, v in sorted(built.items())
            if committed["files"].get(k) != v
        ]
        if not units:  # a full repro rebuilds every output: a committed one it did not produce is an orphan
            stale += [
                f"{k}: in data/manifest.json but not produced by the rebuild (orphaned output: delete it and "
                "regenerate the manifest)"
                for k in sorted(committed["files"])
                if k.startswith(REPRO_OUTPUT_DIRS) and k not in built
            ]
        if stale:
            failures.append(
                "data/clean, data/sam or data/timeseries does not match what the current code builds (run "
                "`python -m pipeline build`, then `sam`, then `timeseries`):\n  " + "\n  ".join(stale)
            )
        else:
            print(f"matches data/manifest.json for all {len(built)} rebuilt files")
        if committed.get("code_hash") != m0["code_hash"] and not stale:
            print(
                "note: data/manifest.json code_hash is older than the current code (the outputs are identical; "
                "run `python -m pipeline manifest` to refresh it)"
            )
    else:
        failures.append("data/manifest.json does not exist yet (run `python -m pipeline build`)")
    if failures:
        print(f"\nREPRO FAILED (outputs kept in {base})\n" + "\n".join(failures))
        return 1
    shutil.rmtree(base, ignore_errors=True)
    print("\nREPRO OK: byte-identical outputs across hash seeds and thread counts")
    return 0


def _code_hash_changes(m0: dict, mi: dict, *, scoped: bool) -> list[str]:
    """Code edited while repro ran. A unit-scoped repro (`repro UNIT`) compares only the built units'
    code hashes (framework + the unit's own files + uv.lock; manifest.unit_code_hashes), so another
    unit's edit does not fail it. A full repro compares the whole code base (code_hash)."""
    h0, hi = m0.get("unit_code_hashes", {}), mi.get("unit_code_hashes", {})
    changed = sorted(u for u in set(h0) | set(hi) if h0.get(u) != hi.get(u))
    if changed:
        return [f"code of {', '.join(changed)} (or the shared framework) changed between builds (edited during repro?)"]
    if mi["code_hash"] != m0["code_hash"]:
        if scoped:
            print("note: code outside the rebuilt units changed during repro; ignored for a unit-scoped repro")
            return []
        return ["code_hash changed between builds (code edited during repro?)"]
    return []


def cmd_manifest(args: argparse.Namespace, layout: Layout) -> int:
    from pipeline.core.io import dumps_json
    from pipeline.core.manifest import build_manifest, repo_lock, write_manifest

    if args.check:
        want = dumps_json(build_manifest(layout))
        have = layout.manifest.read_text(encoding="utf-8") if layout.manifest.exists() else ""
        if want != have:
            print("data/manifest.json is out of date; run `uv run python -m pipeline manifest`")
            return 1
        print("data/manifest.json is up to date")
        return 0
    with repo_lock(layout):
        m = write_manifest(layout)
    print(f"wrote {layout.manifest} ({len(m['files'])} files, code_hash {m['code_hash'][:12]})")
    return 0


def cmd_verify_raw(args: argparse.Namespace, layout: Layout) -> int:
    from pipeline.core.fetch import FetchError, PinStore, _verify_pinned
    from pipeline.core.unit import unit_names

    bad = 0
    n = 0
    for u in _units(args) or unit_names(layout):
        store = PinStore.load(layout, u)
        for key, pin in sorted(store.pins.items()):
            n += 1
            try:
                _verify_pinned(layout, key, pin)
            except FetchError as e:
                bad += 1
                print(f"{u}: {e}")
    print(f"{n - bad}/{n} pinned raw files present and hash-verified")
    return 1 if bad else 0


def cmd_sam(args: argparse.Namespace, layout: Layout) -> int:
    from pipeline.sam.run import cmd_sam as run_sam

    if args.out:
        layout = layout.with_outputs(Path(args.out).resolve())
    blocks = list(dict.fromkeys([*(args.blocks or []), *(args.block or [])]))
    return run_sam(layout, blocks, with_deps=args.with_deps, balance=not args.no_balance, solver=args.solver)


def cmd_timeseries(args: argparse.Namespace, layout: Layout) -> int:
    from pipeline.timeseries.build import cmd_timeseries as run_timeseries

    if args.out:
        layout = layout.with_outputs(Path(args.out).resolve())
    return run_timeseries(layout)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="python -m pipeline", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="command", required=True)

    def with_units(sp: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sp.add_argument("units", nargs="*", metavar="UNIT")
        sp.add_argument("--unit", action="append", metavar="UNIT", help="unit id (repeatable)")
        return sp

    sub.add_parser("list")
    f = with_units(sub.add_parser("fetch"))
    f.add_argument("--offline", action="store_true", help="never download; verify pinned files only")
    f.add_argument("--refresh", action="store_true", help="re-download pinned files and detect upstream changes")
    f.add_argument(
        "--prune", action="store_true", help="drop pins this run did not request (only if the run had no warnings)"
    )
    b = with_units(sub.add_parser("build"))
    b.add_argument("--with-deps", action="store_true", help="also rebuild the units in DEPENDS (default: read them)")
    b.add_argument("--out", help="write clean files and manifest under this folder instead of data/")
    t = sub.add_parser("test")
    t.add_argument("pytest_args", nargs=argparse.REMAINDER)
    with_units(sub.add_parser("repro"))
    m = sub.add_parser("manifest")
    m.add_argument("--check", action="store_true")
    c = with_units(sub.add_parser("coverage"))
    c.add_argument("--json", help="also write the report as JSON to this path")
    with_units(sub.add_parser("verify-raw"))
    sm = sub.add_parser("sam", help="Phase 2: build SAM blocks and balance (docs/phase2/SAM_GUIDE.md)")
    sm.add_argument("blocks", nargs="*", metavar="BLOCK")
    sm.add_argument("--block", action="append", metavar="BLOCK", help="block name (repeatable)")
    sm.add_argument("--with-deps", action="store_true", help="also rebuild the blocks in DEPENDS")
    sm.add_argument("--no-balance", action="store_true", help="build blocks only; do not assemble or balance")
    sm.add_argument(
        "--solver",
        default="NEWTON",
        help="cross-entropy solver: NEWTON (default: the framework's dual Newton method) or a cvxpy solver name "
        "such as CLARABEL (the documented override; both are gated by the KKT certificate)",
    )
    sm.add_argument("--out", help="read clean data from and write SAM outputs under this folder (used by repro)")
    sub.add_parser("sam-report", help="regenerate BALANCING.md from the balancing outputs")
    ex = sub.add_parser("export", help="Phase 3: export the web data contract (docs/phase3/PLAN.md s.3)")
    ex.add_argument("--out", help="data root to write (default web/public/data; web/fixtures/data with --fixture)")
    ex.add_argument("--check", action="store_true", help="compare a fresh export with the files on disk")
    ex.add_argument("--fixture", action="store_true", help="write the generated synthetic fixture, not the real export")
    ts = sub.add_parser("timeseries", help="Phase 2 post-SAM step: the top-flows time series (DESIGN_BRIEF s.8)")
    ts.add_argument("--out", help="read clean data and the SAM from, and write data/timeseries under, this folder")

    layout = Layout.default()
    if argv[:1] == ["test"]:  # everything after `test` goes to pytest untouched
        return cmd_test(argv[1:], layout)
    args = p.parse_args(argv)
    if args.command == "list":
        return cmd_list(layout)
    if args.command in ("fetch", "build"):
        return cmd_fetch_build(args.command, args, layout)
    if args.command == "test":
        return cmd_test(args.pytest_args, layout)
    if args.command == "repro":
        return cmd_repro(args, layout)
    if args.command == "manifest":
        return cmd_manifest(args, layout)
    if args.command == "coverage":
        from pipeline.core.coverage import report

        return report(layout, Path(args.json) if args.json else None, units=_units(args) or None)
    if args.command == "verify-raw":
        return cmd_verify_raw(args, layout)
    if args.command == "sam":
        return cmd_sam(args, layout)
    if args.command == "sam-report":
        from pipeline.sam.run import cmd_sam_report

        return cmd_sam_report(layout)
    if args.command == "timeseries":
        return cmd_timeseries(args, layout)
    if args.command == "export":
        from pipeline.export.build import cmd_export

        return cmd_export(layout, args)
    p.error(f"unknown command {args.command}")
    return 2
