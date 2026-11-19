"""accounts.yaml, structure.yaml and the ref-ownership table (ACCOUNT_STRUCTURE s.10-11, DESIGN_BRIEF s.4)."""

from __future__ import annotations

import pytest

from pipeline.core.paths import REPO_ROOT, Layout
from pipeline.sam.accounts import BLOCK_DEPENDS, EXPECTED_BLOCKS, OWNERSHIP, Accounts, check_ownership, gap_map
from pipeline.sam.framework import block_names, block_order, load_block

pytestmark = pytest.mark.sam

# ACCOUNT_STRUCTURE s.10 group counts (Corporations = NFC + FC in the s.11 diagram)
S10_COUNTS = {"ACT": 34, "COM": 34, "MRG": 1, "FAC": 4, "HH": 10, "CORP": 6, "GOV": 2, "TAX": 12, "ROW": 1,
              "CAP": 11, "DSTK": 1, "INST": 11, "DISC": 1}  # fmt: skip


def test_128_unique_accounts_with_the_s10_group_counts():
    acc = Accounts.load()
    assert len(acc.codes) == 128 == len(set(acc.codes))
    counts: dict[str, int] = {}
    for c in acc.codes:
        g = acc.group(c)
        g = "CORP" if g in ("NFC", "FC") else g
        counts[g] = counts.get(g, 0) + 1
    assert counts == S10_COUNTS
    assert acc.in_group("NFC") == ["E_NFPU", "E_NFPR"]
    assert acc.in_group("FC") == ["E_RBI", "E_BANK", "E_NBFC", "E_INSP"]
    assert acc.codes[0] == "A_CROP" and acc.codes[34] == "C_CROP" and acc.codes[-1] == "X_DISC"
    assert acc.group("K_ROW") == "CAP" and acc.group("K_DSTK") == "DSTK" and acc.group("R_ROW") == "ROW"


def test_activity_and_commodity_order_follow_the_sector_concordance():
    import csv

    with open(REPO_ROOT / "data" / "concordance" / "io_tables_sam34_sectors.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    acc = Accounts.load()
    assert acc.in_group("ACT") == [r["activity"] for r in rows]
    assert acc.in_group("COM") == [r["commodity"] for r in rows]


@pytest.mark.parametrize(
    "row,col",
    [
        ("COM", "DISC"), ("DISC", "HH"), ("CAP", "DISC"), ("ROW", "DISC"), ("TAX", "NFC"), ("TAX", "FC"),
        ("GOV", "GOV"), ("CAP", "CAP"), ("INST", "CAP"), ("CAP", "INST"), ("DSTK", "CAP"), ("COM", "DSTK"),
        ("ACT", "COM"), ("COM", "ACT"), ("MRG", "COM"), ("COM", "MRG"), ("FAC", "ACT"), ("TAX", "ACT"),
        ("TAX", "COM"), ("ROW", "COM"), ("COM", "ROW"), ("FAC", "ROW"), ("ROW", "FAC"), ("GOV", "TAX"),
        ("CAP", "ROW"), ("HH", "HH"),
    ],
)  # fmt: skip
def test_s11_blocks_are_allowed(row, col):
    assert (row, col) in Accounts.load().allowed


@pytest.mark.parametrize(
    "row,col",
    [("ACT", "ACT"), ("COM", "COM"), ("HH", "DISC"), ("TAX", "GOV"), ("TAX", "ROW"), ("INST", "INST"),
     ("DISC", "DISC"), ("FAC", "FAC"), ("ACT", "HH"), ("DSTK", "COM"), ("MRG", "MRG"), ("TAX", "TAX")],
)  # fmt: skip
def test_structural_zero_blocks_are_not_allowed(row, col):
    assert (row, col) not in Accounts.load().allowed


def test_every_gap_map_ref_is_owned_exactly_once():
    assert check_ownership(Layout.default().gap_map) == []
    gm = gap_map(str(Layout.default().gap_map))
    owned = [r for refs in OWNERSHIP.values() for r in refs]
    assert sorted(owned) == sorted(gm)


def test_block_dependencies_are_acyclic_and_closure_is_last():
    order = block_order(list(BLOCK_DEPENDS), BLOCK_DEPENDS)
    assert order[0] == "production" and order[-1] == "closure"
    assert set(order) == set(EXPECTED_BLOCKS)


def test_discovered_blocks_honour_the_ownership_table():
    for name in block_names():
        mod = load_block(name)  # raises on any contract breach
        assert set(mod.REFS) <= set(OWNERSHIP[name])
        assert set(mod.DEPENDS) <= set(BLOCK_DEPENDS[name])
