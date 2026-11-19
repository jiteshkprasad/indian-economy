"""V1-06 (integrator decision, requests/U5.md): a `per100` story figure is labelled by its part alone (split,
total, composition and flags), the same rule summary.json's headline parts follow; the whole's label is
stated in the figure's method text."""

from __future__ import annotations

import pytest

from pipeline.export.inputs import load_stories

pytestmark = pytest.mark.export


def test_per100_takes_its_parts_label(ex) -> None:
    n = 0
    for slug, spec in sorted(load_stories().items()):
        figs = ex.get(f"stories/{slug}.json")["figures"]
        for fid, s in spec["figures"].items():
            if s.get("kind") != "per100":
                continue
            f, part = figs[fid], figs[str(s["part"]["ref"])]
            assert (f["split"], f["total"], f["flags"]) == (part["split"], part["total"], part["flags"]), (slug, fid)
            assert f["composition"] == part["composition"], (slug, fid)
            assert "labelled by its part (the whole is " in f["method"], (slug, fid)
            n += 1
    assert n > 0


def test_household_shares_agree_with_the_first_screen(real) -> None:
    """The same share reads the same on /en/ and in the remittance story (the V1-06 example)."""
    figs = real.get("stories/remittance-dubai.json")["figures"]
    parts = {p["key"]: p for p in real.get("summary.json")["headline"]["hh_outlays"]["parts"]}
    f = figs["hh_consumption_per100"]
    assert (f["split"], f["total"]) == (parts["consumption"]["split_label"], parts["consumption"]["total_label"])
