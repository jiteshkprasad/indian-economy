// What one matrix cell says: value, share of GDP, total and split labels, flags (PLAN §3.4, §4.8).
// Pure; the heat-map info box, the table, the list and the live-region text all read this.

import type { Composition, Label, TotalLabel } from "@/data/types";
import { SPLIT_CODE_LABEL, composition, flagNames, headlineSplit, type FlagName } from "../status";
import { at, type Grid } from "./grid";
import { totalFor } from "./links";
import type { MatrixCells, MatrixPinned } from "./types";

export interface CellFacts {
  /** Column item (pays) and row item (receives) ids. */
  payer: string;
  receiver: string;
  /** Both ends are the same node: money moving inside it. */
  internal: boolean;
  empty: boolean;
  v: number;
  pos: number;
  neg: number;
  /** v / GDP. */
  share: number;
  total: TotalLabel | null;
  pins: string[];
  split: Label | null;
  composition: Composition | null;
  flags: FlagName[];
  nCells: number;
}

export function cellFacts(
  g: Grid,
  i: number,
  j: number,
  pinned: MatrixPinned,
  gdp: number,
): CellFacts {
  if (!(gdp > 0)) throw new Error(`matrix: GDP must be positive, got ${gdp}`);
  const p = at(g, i, j);
  const payer = g.cols[j].id;
  const receiver = g.rows[i].id;
  const comp = composition(g.absO[p], g.absD[p], g.absE[p], g.absB[p]);
  const tot = totalFor(pinned, payer, receiver, g.pos[p], g.neg[p]);
  return {
    payer,
    receiver,
    internal: payer === receiver,
    empty: g.nCells[p] === 0,
    v: g.v[p],
    pos: g.pos[p],
    neg: g.neg[p],
    share: g.v[p] / gdp,
    total: tot.total,
    pins: tot.pins,
    split: comp ? headlineSplit(comp) : null,
    composition: comp,
    flags: flagNames(g.flags[p]),
    nCells: g.nCells[p],
  };
}

/** Facts for one account cell from cells.json (the all-cells list). */
export function accountCellFacts(
  cells: MatrixCells,
  k: number,
  codeOf: (idx: number) => string,
  pinned: MatrixPinned,
  gdp: number,
): CellFacts {
  if (!(gdp > 0)) throw new Error(`matrix: GDP must be positive, got ${gdp}`);
  const v = cells.v[k];
  const payer = codeOf(cells.col[k]);
  const receiver = codeOf(cells.row[k]);
  const comp = composition(cells.abs_o[k], cells.abs_d[k], cells.abs_e[k], cells.abs_b[k]);
  const pos = v > 0 ? v : 0;
  const neg = v < 0 ? v : 0;
  const tot = totalFor(pinned, payer, receiver, pos, neg);
  return {
    payer,
    receiver,
    internal: payer === receiver,
    empty: false,
    v,
    pos,
    neg,
    share: v / gdp,
    total: tot.total,
    pins: tot.pins,
    // the exporter's own headline split label for this account cell
    split: SPLIT_CODE_LABEL[cells.split[k] as 0 | 1 | 2 | 3],
    composition: comp,
    flags: flagNames(cells.flags[k]),
    nCells: 1,
  };
}
