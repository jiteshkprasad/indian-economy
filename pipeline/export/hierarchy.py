"""The account hierarchy for the Map's semantic zoom (docs/phase3/PLAN.md s.3.2).

`load_hierarchy()` reads pipeline/export/hierarchy.yaml, validates it against the 128 accounts of
pipeline/sam/accounts.yaml and returns a `Hierarchy`. `Hierarchy.to_json()` is the exported
hierarchy.json (s.3.6). Nothing here falls back silently: a malformed file raises `HierarchyError`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from pipeline.core import io
from pipeline.sam.accounts import Accounts

EXPORT_DIR = Path(__file__).resolve().parent
HIERARCHY_FILE = EXPORT_DIR / "hierarchy.yaml"

L0_RE = re.compile(r"^[A-Z]+$")
L1_RE = re.compile(r"^([A-Z]+)\.([A-Z]+)$")
KINDS = ("production", "factors", "households", "corporations", "government", "row", "capital", "discrepancy")
PRESETS = ("simple", "full")


class HierarchyError(ValueError):
    """hierarchy.yaml is inconsistent with the accounts or with its own rules."""


@dataclass
class Node:
    id: str
    level: int
    parent: str | None
    children: list[str]
    accounts: list[str]
    order: int
    col: int
    kind: str
    name_tech: str

    @property
    def expandable(self) -> bool:
        # a node with one account (ROW, CEN, STA, DISC and every leaf) has nothing to split into
        return len(self.children) > 1


@dataclass
class Hierarchy:
    nodes: dict[str, Node]  # in global order
    accounts: Accounts
    kinds: dict[str, str]
    split_node: str
    split_col: int
    presets: dict[str, dict[str, Any]]
    ts_nodes: list[dict[str, Any]]
    _l0_of: dict[str, str] = field(default_factory=dict)
    _l1_of: dict[str, str | None] = field(default_factory=dict)

    # ---- lookups ---------------------------------------------------------------------------
    @cached_property
    def codes(self) -> list[str]:
        return self.accounts.codes

    @cached_property
    def idx(self) -> dict[str, int]:
        return self.accounts.index

    @cached_property
    def level0(self) -> list[str]:
        return [n.id for n in self.nodes.values() if n.level == 0]

    def l0(self, code: str) -> str:
        return self._l0_of[code]

    def l1(self, code: str) -> str | None:
        return self._l1_of[code]

    def preset_map(self, preset: str) -> dict[str, str]:
        """account code -> node id of the preset's level-0 view (merges applied)."""
        if preset not in self.presets:
            raise HierarchyError(f"unknown preset {preset!r}")
        merged: dict[str, str] = {}
        for new_id, members in self.presets[preset]["merges"].items():
            for m in members:
                merged[m] = new_id
        return {c: merged.get(self.l0(c), self.l0(c)) for c in self.codes}

    def ts_map(self) -> dict[str, str]:
        """account code -> ts node id (s.2.1 item 6)."""
        member_of = {m: t["id"] for t in self.ts_nodes for m in t["members"]}
        return {c: member_of[self.l0(c)] for c in self.codes}

    def node_accounts(self, node_id: str) -> list[str]:
        """Accounts under a hierarchy node, else a preset merge id, else a ts node id. A hierarchy id wins: the
        simple preset's SI (SI + FINM) and the ts node SI are not returned for "SI"."""
        if node_id in self.nodes:
            return list(self.nodes[node_id].accounts)
        for p in self.presets.values():
            if node_id in p["merges"]:
                return [a for m in p["merges"][node_id] for a in self.nodes[m].accounts]
        for t in self.ts_nodes:
            if t["id"] == node_id:
                return [a for m in t["members"] for a in self.nodes[m].accounts]
        raise HierarchyError(f"unknown node id {node_id!r}")

    # ---- export ------------------------------------------------------------------------------
    def to_json(self) -> dict[str, Any]:
        full_cols = self.presets["full"]["columns"]
        nodes = [
            {
                "id": n.id,
                "level": n.level,
                "parent": n.parent,
                "children": list(n.children),
                "accounts": list(n.accounts),
                "order": n.order,
                "col": n.col,
                "kind": n.kind,
                "expandable": n.expandable,
            }
            for n in self.nodes.values()
        ]
        accounts = [
            {
                "code": c,
                "idx": i,
                "group": self.accounts.group(c),
                "l0": self.l0(c),
                "l1": self.l1(c),
                "name_tech": self.accounts.name(c),
            }
            for i, c in enumerate(self.codes)
        ]
        presets = {
            name: {
                "merges": {k: list(v) for k, v in p["merges"].items()},
                "columns": [list(col) for col in p["columns"]],
                "split_node": p["split_node"],
                "return_flows": p["return_flows"],
            }
            for name, p in self.presets.items()
        }
        ts_nodes = []
        for i, t in enumerate(self.ts_nodes):
            ts_nodes.append(
                {
                    "id": t["id"],
                    "accounts": [a for m in t["members"] for a in self.nodes[m].accounts],
                    "order": i,
                    "col": t["col"],
                    "kind": t["kind"],
                }
            )
        return {
            "nodes": nodes,
            "accounts": accounts,
            "columns": [list(col) for col in full_cols],
            "split_node": self.split_node,
            "presets": presets,
            "ts_nodes": ts_nodes,
        }


def load_hierarchy(path: Path = HIERARCHY_FILE, accounts: Accounts | None = None) -> Hierarchy:
    accts = accounts or Accounts.load()
    doc = io.read_yaml(path) or {}
    kinds = doc.get("kinds") or {}
    if sorted(kinds) != sorted(KINDS):
        raise HierarchyError(f"hierarchy.yaml kinds must be exactly {KINDS}, got {sorted(kinds)}")
    nodes: dict[str, Node] = {}
    l0_of: dict[str, str] = {}
    l1_of: dict[str, str | None] = {}
    counter = [0]

    def next_order() -> int:
        counter[0] += 1
        return counter[0] - 1

    def add(node: Node) -> None:
        if node.id in nodes:
            raise HierarchyError(f"hierarchy.yaml: node id {node.id!r} appears twice")
        nodes[node.id] = node

    def leaf(code: str, tid: str, gid: str | None) -> None:
        if not accts.exists(code):
            raise HierarchyError(f"hierarchy.yaml names {code!r}, which is not an account in accounts.yaml")
        if code in l0_of:
            raise HierarchyError(f"account {code} appears twice in hierarchy.yaml")
        top = nodes[tid]
        add(Node(code, 2, gid or tid, [], [code], next_order(), top.col, top.kind, accts.name(code)))
        l0_of[code] = tid
        l1_of[code] = gid

    for top in doc.get("nodes") or []:
        tid = str(top["id"])
        if not L0_RE.match(tid):
            raise HierarchyError(f"level-0 id {tid!r} must be an UPPER word")
        kind = top.get("kind")
        if kind not in KINDS:
            raise HierarchyError(f"{tid}: unknown kind {kind!r}")
        col = top.get("col")
        if not isinstance(col, int) or isinstance(col, bool):
            raise HierarchyError(f"{tid}: level-0 node needs an integer col")
        l0 = Node(tid, 0, None, [], [], next_order(), col, kind, str(top.get("name_tech") or tid))
        add(l0)
        for ch in top.get("children") or []:
            if "account" in ch:
                if set(ch) != {"account"}:
                    raise HierarchyError(f"{tid}: a leaf child takes only `account`: {ch!r}")
                code = str(ch["account"])
                leaf(code, tid, None)
                l0.children.append(code)
                l0.accounts.append(code)
                continue
            gid = str(ch["id"])
            m = L1_RE.match(gid)
            if not m or m.group(1) != tid:
                raise HierarchyError(f"level-1 id {gid!r} must be {tid}.<WORD>")
            members = [str(a) for a in ch.get("accounts") or []]
            if len(members) < 2:
                raise HierarchyError(f"{gid}: a group with fewer than two accounts is not created; use a leaf")
            g = Node(gid, 1, tid, [], [], next_order(), col, kind, str(ch.get("name_tech") or gid))
            add(g)
            l0.children.append(gid)
            for code in members:
                leaf(code, tid, gid)
                g.children.append(code)
                g.accounts.append(code)
                l0.accounts.append(code)

    missing = [c for c in accts.codes if c not in l0_of]
    if missing:
        raise HierarchyError(f"accounts missing from hierarchy.yaml: {missing}")
    level0 = [n.id for n in nodes.values() if n.level == 0]

    split_node = str(doc.get("split_node"))
    if split_node not in level0:
        raise HierarchyError(f"split_node {split_node!r} is not a level-0 node")
    split_col = doc.get("split_col")
    if not isinstance(split_col, int):
        raise HierarchyError("split_col must be an integer")

    presets: dict[str, dict[str, Any]] = {}
    for name in PRESETS:
        p = (doc.get("presets") or {}).get(name)
        if p is None:
            raise HierarchyError(f"preset {name!r} missing")
        merges = {str(k): [str(m) for m in v] for k, v in (p.get("merges") or {}).items()}
        seen: set[str] = set()
        for k, members in merges.items():
            for m in members:
                if m not in level0:
                    raise HierarchyError(f"preset {name}: merge {k} names {m!r}, not a level-0 node")
                if m in seen:
                    raise HierarchyError(f"preset {name}: {m} merged twice")
                seen.add(m)
            if k in level0 and k not in members:
                raise HierarchyError(f"preset {name}: merge id {k} clashes with a level-0 node it does not contain")
        visible = _visible(level0, merges)
        cols = [[str(x) for x in c] for c in p.get("columns") or []]
        flat = [x for c in cols for x in c]
        sn = str(p.get("split_node"))
        if sorted(set(flat)) != sorted(visible):
            raise HierarchyError(f"preset {name}: columns {sorted(set(flat))} != visible nodes {sorted(visible)}")
        if [x for x in flat if x != sn] != [x for x in dict.fromkeys(flat) if x != sn] or flat.count(sn) != 2:
            raise HierarchyError(f"preset {name}: each node once per column list, the split node {sn} exactly twice")
        if cols[0] != [sn] or cols[-1] != [sn]:
            raise HierarchyError(f"preset {name}: the split node must be alone in the first and last column")
        if p.get("return_flows") not in ("arcs", "stubs"):
            raise HierarchyError(f"preset {name}: return_flows must be arcs or stubs")
        presets[name] = {"merges": merges, "columns": cols, "split_node": sn, "return_flows": p["return_flows"]}

    full_cols = presets["full"]["columns"]
    for n in level0:
        where = [i for i, c in enumerate(full_cols) if n in c]
        want = [nodes[n].col] + ([split_col] if n == split_node else [])
        if where != want:
            raise HierarchyError(f"{n}: col {want} disagrees with the full preset columns {where}")
    if presets["full"]["split_node"] != split_node:
        raise HierarchyError("the full preset's split node must be the hierarchy split node")

    ts_nodes = []
    seen_ts: set[str] = set()
    for t in doc.get("ts_nodes") or []:
        members = [str(m) for m in t["members"]]
        for m in members:
            if m not in level0 or m in seen_ts:
                raise HierarchyError(f"ts_nodes: {m!r} unknown or listed twice")
            seen_ts.add(m)
        if t.get("kind") not in KINDS:
            raise HierarchyError(f"ts_nodes {t['id']}: unknown kind")
        ts_nodes.append({"id": str(t["id"]), "members": members, "col": int(t["col"]), "kind": t["kind"]})
    if seen_ts != set(level0):
        raise HierarchyError(f"ts_nodes do not cover every level-0 node: {sorted(set(level0) - seen_ts)}")

    return Hierarchy(
        nodes=nodes,
        accounts=accts,
        kinds={str(k): str(v) for k, v in kinds.items()},
        split_node=split_node,
        split_col=split_col,
        presets=presets,
        ts_nodes=ts_nodes,
        _l0_of=l0_of,
        _l1_of=l1_of,
    )


def _visible(level0: list[str], merges: dict[str, list[str]]) -> list[str]:
    """Visible node ids of a preset, in level-0 order (a merge takes its first member's place)."""
    member_of = {m: k for k, ms in merges.items() for m in ms}
    out: list[str] = []
    for n in level0:
        v = member_of.get(n, n)
        if v not in out:
            out.append(v)
    return out


def visible_nodes(h: Hierarchy, preset: str) -> list[str]:
    return _visible(h.level0, h.presets[preset]["merges"])
