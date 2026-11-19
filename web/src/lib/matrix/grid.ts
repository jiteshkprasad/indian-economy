// Sum account cells (the atoms, PLAN §4.4) into the current zoom matrix.
//
// Every block cell keeps its net value and, separately, its positive and negative parts, the
// absolute value by entry label (for the split label and composition bar), the OR of the cell
// flags and the number of account cells it sums. Nothing is dropped: a cell that maps outside the
// current axes is simply not in this view.

import type { AxisItem } from "./axes";
import type { MatrixCells } from "./types";

export interface Grid {
  nR: number;
  nC: number;
  rows: AxisItem[];
  cols: AxisItem[];
  /** Row-major arrays of length nR * nC. */
  v: Float64Array;
  pos: Float64Array;
  neg: Float64Array;
  absO: Float64Array;
  absD: Float64Array;
  absE: Float64Array;
  absB: Float64Array;
  flags: Int32Array;
  nCells: Int32Array;
  /** Indices into cells.json arrays, per block cell (only built when asked for). */
  members: number[][] | null;
}

function axisMap(items: AxisItem[], nAccounts: number): Int32Array {
  const m = new Int32Array(nAccounts).fill(-1);
  items.forEach((it, i) => {
    for (const a of it.accounts) {
      if (m[a] !== -1) throw new Error(`matrix: account ${a} appears twice on one axis`);
      m[a] = i;
    }
  });
  return m;
}

export function buildGrid(
  cells: MatrixCells,
  rows: AxisItem[],
  cols: AxisItem[],
  nAccounts: number,
  withMembers = false,
): Grid {
  const nR = rows.length;
  const nC = cols.length;
  const size = nR * nC;
  const g: Grid = {
    nR,
    nC,
    rows,
    cols,
    v: new Float64Array(size),
    pos: new Float64Array(size),
    neg: new Float64Array(size),
    absO: new Float64Array(size),
    absD: new Float64Array(size),
    absE: new Float64Array(size),
    absB: new Float64Array(size),
    flags: new Int32Array(size),
    nCells: new Int32Array(size),
    members: withMembers ? Array.from({ length: size }, () => [] as number[]) : null,
  };
  const rm = axisMap(rows, nAccounts);
  const cm = axisMap(cols, nAccounts);
  for (let k = 0; k < cells.n; k++) {
    const i = rm[cells.row[k]];
    const j = cm[cells.col[k]];
    if (i < 0 || j < 0) continue;
    const p = i * nC + j;
    const v = cells.v[k];
    g.v[p] += v;
    if (v > 0) g.pos[p] += v;
    else g.neg[p] += v;
    g.absO[p] += cells.abs_o[k];
    g.absD[p] += cells.abs_d[k];
    g.absE[p] += cells.abs_e[k];
    g.absB[p] += cells.abs_b[k];
    g.flags[p] |= cells.flags[k];
    g.nCells[p] += 1;
    g.members?.[p].push(k);
  }
  return g;
}

/** Index of block cell (i, j). */
export const at = (g: Grid, i: number, j: number) => i * g.nC + j;

/** Row total (receipts) and column total (payments) of the current view, net values. */
export function rowTotals(g: Grid): Float64Array {
  const out = new Float64Array(g.nR);
  for (let i = 0; i < g.nR; i++) for (let j = 0; j < g.nC; j++) out[i] += g.v[i * g.nC + j];
  return out;
}

export function colTotals(g: Grid): Float64Array {
  const out = new Float64Array(g.nC);
  for (let i = 0; i < g.nR; i++) for (let j = 0; j < g.nC; j++) out[j] += g.v[i * g.nC + j];
  return out;
}

/** Smallest and largest non-zero |net value| in the grid (for the colour scale); null if all zero. */
export function absDomain(g: Grid): [number, number] | null {
  let lo = Infinity;
  let hi = 0;
  for (let p = 0; p < g.v.length; p++) {
    if (g.nCells[p] === 0) continue;
    const a = Math.abs(g.v[p]);
    if (a === 0) continue;
    if (a < lo) lo = a;
    if (a > hi) hi = a;
  }
  return hi > 0 ? [lo, hi] : null;
}
