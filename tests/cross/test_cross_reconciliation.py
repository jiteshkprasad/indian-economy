"""Cross-source reconciliation tests (Phase 1). Read-only over data/clean; no unit code involved.

One test per check in recon_lib.CHECKS (FY 2023-24, plus 2022-23 where the sources have it):

- verdict ``agree`` / ``explained``: must hold within the stated tolerance (after the sourced bridge);
- verdict ``UNEXPLAINED``: asserts the tolerance we would expect and is marked xfail (non-strict,
  raises=AssertionError), so the disagreement is listed in every run and an XPASS shows when a fix
  lands. A renamed series (LookupError) still fails loudly, even for an xfail check;
- a missing clean dataset (unit not built) skips the check with "MISSING DATA".

The same checks produce the tables in docs/phase1/RECONCILIATION.md
(`uv run python tests/cross/recon_lib.py --detail`).
"""

from __future__ import annotations

import pytest
import recon_lib as R

pytestmark = pytest.mark.quality


def _param(c: R.Check):
    marks = []
    if c.verdict == R.UNEXPLAINED:
        marks.append(pytest.mark.xfail(reason=f"UNEXPLAINED {c.id}: {c.note}", strict=False, raises=AssertionError))
    return pytest.param(c, id=c.id, marks=marks)


@pytest.mark.parametrize("check", [_param(c) for c in R.CHECKS])
def test_reconciliation(check: R.Check):
    try:
        r = check.evaluate()
    except R.MissingData as e:
        pytest.skip(f"MISSING DATA for {check.id}: {e}")
    if check.ratio_range:
        lo, hi = check.ratio_range
        assert r["ok"], (
            f"{check.id}: ratio A/B = {r['ratio']:.4f} outside [{lo}, {hi}] (A={r['a']:,.0f}, B={r['b']:,.0f})"
        )
        return
    assert r["ok"], (
        f"{check.id} ({check.verdict}): A={r['a']:,.0f} B={r['b']:,.0f} A-B={r['diff']:,.0f} ({r['pct']:+.3f}%), "
        f"bridge={r['bridge']:,.0f}, residual={r['resid']:,.0f} exceeds tolerance {r['tol']:,.0f} "
        f"({check.tol_pct}% of |B|, floor {check.tol_abs:g}). {check.note}"
    )


def test_checks_are_well_formed():
    for c in R.CHECKS:
        assert c.verdict in (R.AGREE, R.EXPLAINED, R.UNEXPLAINED), c.id
        assert c.a and c.b, c.id
        if c.verdict == R.AGREE:
            assert not c.bridge, f"{c.id}: an 'agree' check must not need a bridge"
        else:
            assert c.note, f"{c.id}: a non-agree verdict needs a stated reason"


def test_report_lists_every_check():
    """docs/phase1/RECONCILIATION.md must carry every check id (it is generated from recon_lib)."""
    doc = (R.REPO / "docs" / "phase1" / "RECONCILIATION.md").read_text(encoding="utf-8")
    missing = [c.id for c in R.CHECKS if f"| {c.id} |" not in doc]
    assert not missing, f"checks missing from RECONCILIATION.md (regenerate the tables): {missing}"
