"""Entry labels, split labels and flags (docs/phase3/PLAN.md s.3.4, proposed D3-3). Owner: U1.

Mirrored in the browser by web/src/lib/status.ts (U2) for the parts the browser computes (the split label
and composition of an aggregate from the exported per-label absolute values). Both must reproduce
`pipeline/export/golden/status_cases.json`.
"""

from __future__ import annotations

from typing import Any

LABELS = ("official", "derived", "estimated", "balancing_set")  # least certain last
LABEL_CODE = {lab: i for i, lab in enumerate(LABELS)}  # cells.json `split`: 0 o, 1 d, 2 e, 3 b
COMPOSITION_KEYS = ("o", "d", "e", "b")
SPLIT_SHARE = 0.10  # the headline split label carries >= 10% of the aggregate's absolute value

FLAG_BITS = {
    "judgement_band": 1,
    "unexplained": 2,
    "level_unexplained": 4,
    "old_base_structure": 8,
    "discrepancy": 16,
    "has_negative": 32,
    "depends_on_assumption": 64,
}
VERDICT_FLAG = {"unexplained": "unexplained", "level unexplained": "level_unexplained"}


class LabelError(ValueError):
    """An entry matched no label branch (the export fails, naming it)."""


def entry_label(e: dict[str, Any]) -> str:
    """The four-branch rule of s.3.4.1, applied in order.

    `e` needs: role, status, prior_status, explanation_required (bool), has_item (the entry or its cell has a
    current explanation item, any verdict), in_judgement_band (member of a binding judgement band), and
    `key` (for the error message).
    """
    if (
        e["role"] == "free"
        and e["status"] == "balanced"
        and (bool(e["explanation_required"]) or bool(e["has_item"]) or bool(e["in_judgement_band"]))
    ):
        return "balancing_set"
    ps = e["prior_status"]
    if ps == "official":
        return "official"
    if ps == "derived":
        return "derived"
    if ps == "estimated":
        return "estimated"
    raise LabelError(
        f"entry {e.get('key', '?')} matches no label branch (role={e['role']!r}, status={e['status']!r}, "
        f"prior_status={ps!r})"
    )


def split_of(abs_o: float, abs_d: float, abs_e: float, abs_b: float) -> tuple[dict[str, float], str]:
    """(composition, headline split label) of an aggregate from its absolute values by entry label.

    total = abs_o + abs_d + abs_e + abs_b (in that order, float64). The headline label is the least certain
    label L with abs_L >= 0.1 * total. Composition shares are abs_L / total (not rounded here).
    """
    vals = (abs_o, abs_d, abs_e, abs_b)
    total = abs_o + abs_d + abs_e + abs_b
    if not total > 0:
        raise LabelError("an aggregate with zero absolute value has no split label")
    comp = {k: v / total for k, v in zip(COMPOSITION_KEYS, vals, strict=True)}
    label = None
    for lab, v in zip(LABELS, vals, strict=True):
        if v >= SPLIT_SHARE * total:
            label = lab  # later (less certain) labels overwrite earlier ones
    assert label is not None  # the largest part always carries >= 25%
    return comp, label


def least_certain(labels: list[str]) -> str:
    return max(labels, key=lambda lab: LABEL_CODE[lab])


def least_certain_total(totals: list[str | None]) -> str | None:
    """Total label of a combination: None if any part has none, else the least certain."""
    if any(t is None for t in totals) or not totals:
        return None
    return "derived" if "derived" in totals else "official"


def flags_mask(names: list[str] | set[str]) -> int:
    m = 0
    for n in names:
        m |= FLAG_BITS[n]
    return m


def flag_names(mask: int) -> list[str]:
    return [n for n, b in FLAG_BITS.items() if mask & b]
