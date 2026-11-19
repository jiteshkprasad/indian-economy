/**
 * Columns and order of the visible nodes (PLAN §3.2, §4.5.1–2). Which nodes are visible comes from
 * the platform's `visibleNodes` (`@/data/aggregate`); this adds where each one is drawn.
 */
import type { Visible } from "@/data/aggregate";
import type { Hierarchy, HierarchyNode } from "./contract";
import type { LayoutNodeInput } from "./types";

export type MapNode = LayoutNodeInput & {
  accounts: string[];
  /** hierarchy level; a preset merge (PRODUCERS) counts as level 0 */
  level: number;
  /** "+" is available: a hierarchy node with children, or a preset merge (expands to the full map) */
  expandable: boolean;
  /** level-0 node (or preset merge) this node belongs to */
  l0: string;
};

function colsIn(columns: string[][], id: string): number[] {
  const out: number[] = [];
  columns.forEach((ids, c) => {
    if (ids.includes(id)) out.push(c);
  });
  return out;
}

export function mapNodes(h: Hierarchy, vis: Visible): MapNode[] {
  const idx = new Map<string, HierarchyNode>(h.nodes.map((n) => [n.id, n]));
  const P = h.presets[vis.preset];
  return vis.ids.map((id) => {
    const n = idx.get(id);
    const members = P.merges[id];
    // the column: this node, or its nearest ancestor, as listed in the preset's columns
    let cur: HierarchyNode | undefined = n;
    let cols = colsIn(P.columns, id);
    let l0 = id;
    while (!cols.length && cur) {
      cur = cur.parent ? idx.get(cur.parent) : undefined;
      if (cur) {
        cols = colsIn(P.columns, cur.id);
        l0 = cur.id;
      }
    }
    if (!cols.length) {
      // a node absorbed by a merge is never visible on its own; anything else is a data error
      throw new Error(`map: node ${id} has no column in preset ${vis.preset}`);
    }
    const first = n ?? (members ? idx.get(members[0]) : undefined);
    if (!first) throw new Error(`map: node ${id} is not in the hierarchy or a preset merge`);
    return {
      id,
      col: cols[0],
      inCol: cols.length > 1 ? cols[cols.length - 1] : undefined,
      order: first.order,
      kind: first.kind,
      accounts: vis.members[id] ?? [],
      level: n ? n.level : 0,
      expandable: n ? n.expandable && n.children.length > 0 : true,
      l0,
    };
  });
}

/** Nodes of the top-flows board (`ts_nodes`); PRODUCERS is split like in the simple preset. */
export function tsMapNodes(h: Hierarchy): MapNode[] {
  const simple = h.presets.simple;
  const lastCol = simple.columns.length - 1;
  return h.ts_nodes.map((n) => ({
    id: n.id,
    col: n.col,
    inCol: n.id === simple.split_node ? lastCol : undefined,
    order: n.order,
    kind: n.kind,
    accounts: n.accounts,
    level: 0,
    expandable: false,
    l0: n.id,
  }));
}
