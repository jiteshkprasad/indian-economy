"""V4 build / tests / performance: checks behind docs/phase3/verify/V4_build_perf.md (PLAN s.7, row V4).

Written by the V4 verifier, who built nothing in Phase 3. Nothing here imports `pipeline` code: the certified
balancing record, vercel.json, package.json, the web sources and the built static site (web/out) are read as
data. The browser-side checks (hydration under compressed delivery, story-page layout shift, RSC prefetch, the
served cache headers) are in web/tests/verify/v4_build_perf.spec.ts.

Each test names the finding it guards. A fixed finding's test passes normally. A finding that is still open is
a strict xfail: it turns into a failure (XPASS) once fixed, so the mark must then go and the report be updated.
Tests that read the built site skip when web/out/ is absent: build with `npm --prefix web run build`.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.export]

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
OUT = WEB / "out"
IMMUTABLE = "public, max-age=31536000, immutable"


def _vercel_headers(path: str) -> dict[str, str]:
    """vercel.json headers for a path: every matching rule applies, the last one wins per key."""
    v = json.loads((WEB / "vercel.json").read_text())
    h: dict[str, str] = {}
    for rule in v["headers"]:
        if re.fullmatch(rule["source"].replace("(.*)", "(.*)"), path):
            for kv in rule["headers"]:
                h[kv["key"].lower()] = kv["value"]
    return h


# ---------------------------------------------------------------- V4-01 (high): `just test` had a non-raw failure


def test_v4_01_production_smoke_test_is_run_unmarked():
    """The Phase 2 smoke test V4-01 found failing must run as a normal test (no skip / xfail), so `just test`
    being green means it passed."""
    src = (ROOT / "tests" / "sam" / "test_sam_production.py").read_text()
    fn = next(
        n
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.FunctionDef) and n.name == "test_production_prior_closed_with_pseudo_entries_balances"
    )
    marks = [ast.unparse(d) for d in fn.decorator_list]
    assert not any(re.search(r"skip|xfail", m) for m in marks), marks
    body = ast.unparse(fn)
    assert "pytest.skip" not in body and "pytest.xfail" not in body
    # every non-gap certificate criterion is still required (the fix moved only the gap to its exact form)
    for crit in ("stationarity", "sign_at_upper_bounds", "sign_at_lower_bounds", "non_complementary_bands",
                 "entries_forced_to_zero", "max_box_violation", "CERT_GAP"):  # fmt: skip
        assert crit in body, crit


def test_v4_01_certified_run_is_far_above_the_gap_noise_floor():
    """The certified SAM is not affected by the cancellation behind V4-01: its own certificate passed with the
    unchanged gap formula, on an objective many orders above the floor where the formula measures rounding."""
    run = json.loads((ROOT / "data" / "sam" / "2023-24" / "balancing_run.json").read_text())
    cert = run["certificate"]
    assert run["ok"] is True and run["status"] == "optimal" and cert["ok"] is True
    assert cert["duality_gap_rel"] <= cert["tolerance"]
    assert run["objective"] > 1e3  # vs about 2e-5 on the synthetic smoke-test prior


def test_v4_01_framework_weakness_stays_logged():
    """The latent weakness (the certificate's gap is a difference of large sums) is logged, not silently
    worked around: ISSUES.md carries P3-O1 (resolved in the test) and P3-O2."""
    issues = (ROOT / "ISSUES.md").read_text()
    assert re.search(r"^\| P3-O1 \|.*RESOLVED", issues, re.M)
    assert re.search(r"^\| P3-O2 \|.*kkt_certificate", issues, re.M)


# ---------------------------------------------------------------- V4-05 (medium): hashed chunks not cached


@pytest.mark.skipif(not (OUT / "_next" / "static").is_dir(), reason="web/out not built")
def test_v4_05_every_next_static_file_is_immutable_and_html_is_not():
    files = ["/" + p.relative_to(OUT).as_posix() for p in (OUT / "_next" / "static").rglob("*") if p.is_file()]
    assert len(files) > 10
    assert [f for f in files if _vercel_headers(f).get("cache-control") != IMMUTABLE] == []
    for page in ("/en/", "/en/index.html", "/en/flow/CEN--HH/", "/404.html"):
        assert "immutable" not in _vercel_headers(page).get("cache-control", ""), page
    assert _vercel_headers("/data/index.json")["cache-control"] == "public, max-age=0, must-revalidate"
    v = json.loads((WEB / "vercel.json").read_text())
    assert v["trailingSlash"] is True and v["framework"] is None


@pytest.mark.skipif(not (OUT / "_next" / "static").is_dir(), reason="web/out not built")
def test_v4_05_fixed_name_build_files_sit_under_a_per_build_folder():
    """Immutable caching of /_next/static is safe only while the non-hashed files (_buildManifest.js etc.) live
    under a folder that changes every build. A constant `generateBuildId` (one way to "fix" V4-12) would freeze
    them in every browser cache for a year."""
    static = OUT / "_next" / "static"
    loose = [p.name for p in static.iterdir() if p.is_file()]
    assert loose == []
    build_dirs = [p for p in static.iterdir() if p.is_dir() and p.name not in ("chunks", "media", "css")]
    assert len(build_dirs) == 1, build_dirs
    assert re.fullmatch(r"[A-Za-z0-9_-]{16,}", build_dirs[0].name), build_dirs[0].name
    cfg = (WEB / "next.config.ts").read_text()
    assert "generateBuildId" not in cfg or "hash" in cfg.lower()


# ---------------------------------------------------------------- V4-07 (low): unused dependencies

# Packages used without an import in our code: React DOM (Next renders with it), the MDX loader and the optional
# React peer of @next/mdx, and remark-gfm (named as a string in next.config.ts).
_USED_WITHOUT_IMPORT = {"react-dom", "@mdx-js/loader", "@mdx-js/react"}


def test_v4_07_every_runtime_dependency_is_used():
    pkg = json.loads((WEB / "package.json").read_text())
    deps = set(pkg["dependencies"])
    text = (
        "\n".join(
            p.read_text(errors="ignore")
            for d in ("src", "scripts", "content")
            for p in (WEB / d).rglob("*")
            if p.is_file() and p.suffix in {".ts", ".tsx", ".mjs", ".js", ".mdx", ".md"}
        )
        + (WEB / "next.config.ts").read_text()
    )
    unused = sorted(
        d
        for d in deps - _USED_WITHOUT_IMPORT
        if not re.search(r"""['"]""" + re.escape(d) + r"""(/[^'"]*)?['"]""", text)
    )
    assert unused == []
    assert not [
        d for d in {**pkg["dependencies"], **pkg.get("devDependencies", {})} if d.startswith(("d3", "@types/d3"))
    ]


# ---------------------------------------------------------------- V4-13 (low, new in round 2): stray result folders


@pytest.mark.xfail(strict=True, reason="V4-13 open: web/.gitignore ignores test-results/ but not test-results-<run>/")
def test_v4_13_playwright_output_folders_are_gitignored():
    """Verifier and fixer runs write Playwright output to web/test-results-<name>/ (the v1/v3 configs set it);
    those folders show up as untracked files and are one `git add -A` away from being committed."""
    r = subprocess.run(
        ["git", "check-ignore", "-q", "web/test-results-v4/x.json"], cwd=ROOT, capture_output=True, check=False
    )
    assert r.returncode == 0
