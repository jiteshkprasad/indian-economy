"""The SAM's accounts (accounts.yaml), its allowed blocks (structure.yaml) and who owns which gap-map ref.

- `Accounts.load()`: the 128 accounts in matrix order, their groups, and the allowed (row group,
  column group) pairs. accounts.yaml is the only source of matrix order.
- `OWNERSHIP` / `BLOCK_DEPENDS`: the ref-ownership table of DESIGN_BRIEF s.4. Every gap-map ref is
  owned by exactly one block (checked against data/gap_map.csv by `check_ownership`).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import cache, cached_property
from pathlib import Path

from pipeline.core import io

SAM_DIR = Path(__file__).resolve().parent
ACCOUNTS_FILE = SAM_DIR / "accounts.yaml"
STRUCTURE_FILE = SAM_DIR / "structure.yaml"

GROUPS = ("ACT", "COM", "MRG", "FAC", "HH", "NFC", "FC", "GOV", "TAX", "ROW", "CAP", "DSTK", "INST", "DISC")

# DESIGN_BRIEF s.4. Satellite refs (P6a, P7b, S1-S9) are owned too; `hh_keys` is a satellite name, not a ref.
OWNERSHIP: dict[str, tuple[str, ...]] = {
    "production": (
        "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10",
        "V1", "V2", "C1", "C2", "I1", "I3", "D4", "P6a", "S6",
    ),
    "households": ("C1a", "C4a", "C4b", "C4c", "C4d", "S8"),
    "factors": ("V1a", "V2a", "V3", "V4", "F1", "F1a", "F2", "F3", "F3a", "F3b", "F3c", "F4", "F4b"),
    "taxes": ("P7a", "P7b", "P9a", "P10a", "T1", "T1a", "T2", "T2x", "T3", "T3a", "T4", "T4a", "S7"),
    "government": (
        "C2a", "R1", "R2", "R2k", "T2b", "R6", "R7", "R7x", "R9", "R9a", "R9b", "R9d", "R10",
        "R15", "R16", "R18", "K3", "K3a", "K6", "K8e",
    ),
    "fincorp": ("F4a", "R3", "R3a", "R3b", "R4", "R5", "R8", "R8a", "R9c", "R17", "K2", "K2a", "S9"),
    "rest_of_world": ("R11", "R11a", "R12", "R12a", "R13", "R14", "R14a", "K5", "K8b", "K8c", "D2", "S1", "S2", "S3"),
    "capital_financial": (
        "I1a", "I2", "I2a", "I3a", "K1", "K4", "K7", "K7a", "K7b", "K8", "K8a", "K8d", "K9", "K9b", "D3", "S4", "S5",
    ),
    "closure": ("K4a", "D1"),
}  # fmt: skip

# DESIGN_BRIEF s.4 "depends on", as amended by DECISIONS D2-10 (2026-09-30).
# A block's DEPENDS must be a subset (a new need goes to FRAMEWORK_REQUESTS.md).
BLOCK_DEPENDS: dict[str, tuple[str, ...]] = {
    "production": (),
    "households": ("production",),
    "factors": ("production", "households"),
    "taxes": ("production", "households", "factors"),
    "government": ("production", "households", "factors", "taxes"),
    "fincorp": ("production", "households", "factors", "government", "rest_of_world"),
    "rest_of_world": ("production", "households"),
    "capital_financial": ("production", "households", "rest_of_world", "government", "fincorp"),
    "closure": ("production", "households", "factors", "taxes", "government", "fincorp", "rest_of_world",
                "capital_financial"),
}  # fmt: skip

EXPECTED_BLOCKS = tuple(OWNERSHIP)  # balancing runs only when all of these are built


class SamStructureError(ValueError):
    """accounts.yaml / structure.yaml / the ownership table is inconsistent."""


@dataclass(frozen=True)
class Account:
    code: str
    group: str
    name: str


@dataclass(frozen=True)
class Accounts:
    accounts: tuple[Account, ...]
    allowed: frozenset[tuple[str, str]]  # (row group, col group)

    @cached_property
    def codes(self) -> list[str]:
        return [a.code for a in self.accounts]

    @cached_property
    def index(self) -> dict[str, int]:
        return {a.code: i for i, a in enumerate(self.accounts)}

    def group(self, code: str) -> str:
        return self._by_code[code].group

    def name(self, code: str) -> str:
        return self._by_code[code].name

    @cached_property
    def _by_code(self) -> dict[str, Account]:
        return {a.code: a for a in self.accounts}

    def exists(self, code: str) -> bool:
        return code in self._by_code

    def in_group(self, group: str) -> list[str]:
        return [a.code for a in self.accounts if a.group == group]

    def allowed_cell(self, row: str, col: str) -> bool:
        return (self.group(row), self.group(col)) in self.allowed

    @classmethod
    def load(cls, accounts_file: Path = ACCOUNTS_FILE, structure_file: Path = STRUCTURE_FILE) -> Accounts:
        return _load(str(accounts_file), str(structure_file))


@cache
def _load(accounts_file: str, structure_file: str) -> Accounts:
    doc = io.read_yaml(Path(accounts_file)) or {}
    rows = doc.get("accounts") or []
    accts: list[Account] = []
    for r in rows:
        if set(r) != {"code", "group", "name"}:
            raise SamStructureError(f"accounts.yaml: each account needs exactly code, group, name: {r!r}")
        if r["group"] not in GROUPS:
            raise SamStructureError(f"accounts.yaml: unknown group {r['group']!r} for {r['code']}")
        accts.append(Account(str(r["code"]), str(r["group"]), str(r["name"])))
    codes = [a.code for a in accts]
    if len(set(codes)) != len(codes):
        dup = sorted({c for c in codes if codes.count(c) > 1})
        raise SamStructureError(f"accounts.yaml: duplicate codes {dup}")
    sdoc = io.read_yaml(Path(structure_file)) or {}
    allowed: set[tuple[str, str]] = set()
    for item in sdoc.get("allowed") or []:
        if not (isinstance(item, list) and len(item) == 3 and item[0] in GROUPS and item[1] in GROUPS):
            raise SamStructureError(f"structure.yaml: bad item {item!r} (want [row group, col group, text])")
        if (item[0], item[1]) in allowed:
            raise SamStructureError(f"structure.yaml: block {item[0]} <- {item[1]} listed twice")
        allowed.add((item[0], item[1]))
    return Accounts(tuple(accts), frozenset(allowed))


# ---------------------------------------------------------------------------------------------
# gap map and ownership
# ---------------------------------------------------------------------------------------------


@cache
def gap_map(path: str) -> dict[str, dict[str, str]]:
    """{ref: row of data/gap_map.csv}."""
    with open(path, encoding="utf-8", newline="") as f:
        return {r["ref"]: r for r in csv.DictReader(f)}


def owner_of(ref: str) -> str | None:
    for block, refs in OWNERSHIP.items():
        if ref in refs:
            return block
    return None


def check_ownership(gap_map_path: Path) -> list[str]:
    """Problems with the ownership table: a ref owned twice, a ref not in the gap map, a gap-map ref
    owned by nobody, or a dependency on an unknown block. Empty list = consistent. (Cycles are caught by
    framework.block_order when blocks are built, and tested on BLOCK_DEPENDS in test_sam_structure.)"""
    gm = gap_map(str(gap_map_path))
    problems: list[str] = []
    seen: dict[str, str] = {}
    for block, refs in OWNERSHIP.items():
        for r in refs:
            if r in seen:
                problems.append(f"ref {r} is owned by both {seen[r]} and {block}")
            seen[r] = block
            if r not in gm:
                problems.append(f"ref {r} (block {block}) is not in data/gap_map.csv")
    for r in gm:
        if r not in seen:
            problems.append(f"gap-map ref {r} is owned by no block")
    for block, deps in BLOCK_DEPENDS.items():
        for d in deps:
            if d not in OWNERSHIP:
                problems.append(f"block {block} depends on unknown block {d}")
    if set(BLOCK_DEPENDS) != set(OWNERSHIP):
        problems.append("OWNERSHIP and BLOCK_DEPENDS list different blocks")
    return problems
