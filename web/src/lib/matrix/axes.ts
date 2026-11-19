// Matrix axes and block zoom (PLAN §4.8).
//
// The matrix shows rows = receivers and columns = payers (money flows from the column account to
// the row account). Each axis is described independently by a parent node (null = the whole
// economy) and a grain: "children" shows the parent's immediate children (level-0 groups at the
// root), "accounts" shows every account under the parent. The default above 640 px is the
// 128 × 128 account grid with level-0 block lines; below 640 px it is the 13 × 13 block grid.

import type { MatrixHierarchy, MatrixHierNode } from "./types";

export type Grain = "children" | "accounts";

export interface AxisState {
  parent: string | null;
  grain: Grain;
}

export interface ZoomState {
  rows: AxisState;
  cols: AxisState;
}

export interface AxisItem {
  /** Hierarchy node id (an account code for leaves). */
  id: string;
  /** Account indices (into hierarchy.accounts) that this item sums over. */
  accounts: number[];
  /** True when the item can be zoomed into (it has children). */
  expandable: boolean;
  /** Block key: the node that a zoom on this item goes to; block lines are drawn where it changes. */
  block: string;
  /** Level-0 ancestor id. */
  l0: string;
}

export const ROOT_ACCOUNTS: ZoomState = {
  rows: { parent: null, grain: "accounts" },
  cols: { parent: null, grain: "accounts" },
};

export const ROOT_BLOCKS: ZoomState = {
  rows: { parent: null, grain: "children" },
  cols: { parent: null, grain: "children" },
};

/** Index of the hierarchy for fast lookups; build once per hierarchy object. */
export interface HierIndex {
  byId: Map<string, MatrixHierNode>;
  roots: MatrixHierNode[];
  accountIdx: Map<string, number>;
  /** Account codes in matrix order (depth-first by `order`). */
  matrixOrder: string[];
  l0Of: Map<string, string>;
}

const byOrder = (a: MatrixHierNode, b: MatrixHierNode) => a.order - b.order;

export function indexHierarchy(h: MatrixHierarchy): HierIndex {
  const byId = new Map<string, MatrixHierNode>();
  for (const n of h.nodes) {
    if (byId.has(n.id)) throw new Error(`hierarchy: duplicate node id ${n.id}`);
    byId.set(n.id, n);
  }
  const accountIdx = new Map<string, number>();
  for (const a of h.accounts) accountIdx.set(a.code, a.idx);
  const roots = h.nodes.filter((n) => n.level === 0).sort(byOrder);
  const matrixOrder: string[] = [];
  const l0Of = new Map<string, string>();
  const walk = (n: MatrixHierNode, l0: string) => {
    l0Of.set(n.id, l0);
    if (n.children.length === 0) {
      if (!accountIdx.has(n.id)) throw new Error(`hierarchy: leaf ${n.id} is not an account`);
      matrixOrder.push(n.id);
      return;
    }
    const kids = n.children.map((c) => {
      const k = byId.get(c);
      if (!k) throw new Error(`hierarchy: ${n.id} lists unknown child ${c}`);
      return k;
    });
    for (const k of kids.sort(byOrder)) walk(k, l0);
  };
  for (const r of roots) walk(r, r.id);
  if (matrixOrder.length !== h.accounts.length) {
    throw new Error(
      `hierarchy: ${matrixOrder.length} leaves reached from level 0, but ${h.accounts.length} accounts`,
    );
  }
  return { byId, roots, accountIdx, matrixOrder, l0Of };
}

function leafCodes(ix: HierIndex, node: MatrixHierNode): string[] {
  if (node.children.length === 0) return [node.id];
  const kids = node.children.map((c) => ix.byId.get(c)!).sort(byOrder);
  return kids.flatMap((k) => leafCodes(ix, k));
}

function itemFor(ix: HierIndex, node: MatrixHierNode, block: string): AxisItem {
  return {
    id: node.id,
    accounts: leafCodes(ix, node).map((c) => ix.accountIdx.get(c)!),
    expandable: node.children.length > 0,
    block,
    l0: ix.l0Of.get(node.id)!,
  };
}

/** The items along one axis for a given axis state, in matrix order. */
export function axisItems(ix: HierIndex, s: AxisState): AxisItem[] {
  const parent = s.parent === null ? null : ix.byId.get(s.parent);
  if (s.parent !== null && !parent) throw new Error(`matrix: unknown node ${s.parent}`);
  const top: MatrixHierNode[] = parent
    ? parent.children.length === 0
      ? [parent]
      : parent.children.map((c) => ix.byId.get(c)!).sort(byOrder)
    : ix.roots;
  if (s.grain === "children") return top.map((n) => itemFor(ix, n, n.id));
  // accounts grain: every leaf under each top node, block = that top node
  return top.flatMap((n) =>
    leafCodes(ix, n).map((code) => itemFor(ix, ix.byId.get(code)!, n.id)),
  );
}

/** Axis items for an explicit list of node ids (e.g. the map's visible nodes), in the given order. */
export function itemsFromIds(ix: HierIndex, ids: readonly string[]): AxisItem[] {
  return ids.map((id) => {
    const n = ix.byId.get(id);
    if (!n) throw new Error(`matrix: unknown node ${id}`);
    return itemFor(ix, n, id);
  });
}

/** Indices i (0 < i < n) where a block line is drawn before item i. */
export function blockBoundaries(items: AxisItem[]): number[] {
  const out: number[] = [];
  for (let i = 1; i < items.length; i++) if (items[i].block !== items[i - 1].block) out.push(i);
  return out;
}

/** Zoom one axis into the block of an item. Returns null when there is nothing deeper to show. */
export function zoomAxis(ix: HierIndex, s: AxisState, item: AxisItem): AxisState | null {
  const target = ix.byId.get(item.block);
  // A single account has nothing deeper to show.
  if (!target || target.children.length === 0) return null;
  if (s.parent === target.id && s.grain === "children") return null;
  return { parent: target.id, grain: "children" };
}

/** Zoom both axes into the block that contains cell (rowItem, colItem). Null if nothing changes. */
export function zoomInto(
  ix: HierIndex,
  z: ZoomState,
  rowItem: AxisItem,
  colItem: AxisItem,
): ZoomState | null {
  const r = zoomAxis(ix, z.rows, rowItem);
  const c = zoomAxis(ix, z.cols, colItem);
  if (!r && !c) return null;
  return { rows: r ?? z.rows, cols: c ?? z.cols };
}

/** Breadcrumb trail for an axis: node ids from level 0 down to the parent (empty at the root). */
export function axisTrail(ix: HierIndex, s: AxisState): string[] {
  const out: string[] = [];
  let id = s.parent;
  while (id !== null) {
    out.unshift(id);
    id = ix.byId.get(id)?.parent ?? null;
  }
  return out;
}

export function sameZoom(a: ZoomState, b: ZoomState): boolean {
  return (
    a.rows.parent === b.rows.parent &&
    a.rows.grain === b.rows.grain &&
    a.cols.parent === b.cols.parent &&
    a.cols.grain === b.cols.grain
  );
}
