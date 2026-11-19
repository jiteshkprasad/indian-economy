// The "all non-zero cells" list (PLAN §4.8): every account cell, sortable and filterable by payer
// and receiver. Pure: returns the indices into cells.json arrays in display order.

import type { HierIndex } from "./axes";
import type { MatrixCells, MatrixHierarchy } from "./types";

export type SortKey = "abs" | "value" | "payer" | "receiver";
export type SortDir = "asc" | "desc";

export interface ListFilter {
  /** Hierarchy node id (any level) whose accounts the payer must be in; null = any. */
  payer: string | null;
  receiver: string | null;
  /** Case-insensitive text matched against payer and receiver labels and codes. */
  text: string;
}

export const NO_FILTER: ListFilter = { payer: null, receiver: null, text: "" };

function accountSet(ix: HierIndex, id: string | null): Set<number> | null {
  if (id === null) return null;
  const n = ix.byId.get(id);
  if (!n) throw new Error(`cells list: unknown node ${id}`);
  const out = new Set<number>();
  const walk = (nid: string) => {
    const node = ix.byId.get(nid)!;
    if (node.children.length === 0) out.add(ix.accountIdx.get(nid)!);
    else node.children.forEach(walk);
  };
  walk(n.id);
  return out;
}

export function listCells(
  cells: MatrixCells,
  h: MatrixHierarchy,
  ix: HierIndex,
  filter: ListFilter,
  sort: SortKey,
  dir: SortDir,
  label: (code: string) => string,
): number[] {
  const payers = accountSet(ix, filter.payer);
  const receivers = accountSet(ix, filter.receiver);
  const code = (idx: number) => h.accounts[idx].code;
  const q = filter.text.trim().toLowerCase();
  const out: number[] = [];
  for (let k = 0; k < cells.n; k++) {
    if (payers && !payers.has(cells.col[k])) continue;
    if (receivers && !receivers.has(cells.row[k])) continue;
    if (q) {
      const p = code(cells.col[k]);
      const r = code(cells.row[k]);
      const hay = `${p} ${label(p)} ${r} ${label(r)}`.toLowerCase();
      if (!hay.includes(q)) continue;
    }
    out.push(k);
  }
  const sign = dir === "asc" ? 1 : -1;
  // matrix position (row-major) is the final tie-break, so the order is total and deterministic
  const pos = new Map<number, number>();
  ix.matrixOrder.forEach((c, i) => pos.set(ix.accountIdx.get(c)!, i));
  const tie = (a: number, b: number) =>
    pos.get(cells.row[a])! - pos.get(cells.row[b])! || pos.get(cells.col[a])! - pos.get(cells.col[b])!;
  const cmpText = (x: string, y: string) => (x < y ? -1 : x > y ? 1 : 0);
  out.sort((a, b) => {
    let d = 0;
    if (sort === "abs") d = Math.abs(cells.v[a]) - Math.abs(cells.v[b]);
    else if (sort === "value") d = cells.v[a] - cells.v[b];
    else if (sort === "payer") d = cmpText(label(code(cells.col[a])), label(code(cells.col[b])));
    else d = cmpText(label(code(cells.row[a])), label(code(cells.row[b])));
    return d !== 0 ? sign * d : tie(a, b);
  });
  return out;
}
