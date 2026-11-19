// Structural subsets of the export contract (PLAN §3.6) that the matrix library needs.
// They are deliberately narrow so the pure library can be tested on small in-test data;
// the generated contract types (src/data/contract.gen.ts) are assignable to them.

export interface MatrixHierNode {
  id: string;
  level: number;
  parent: string | null;
  children: string[];
  accounts: string[];
  order: number;
}

export interface MatrixHierAccount {
  code: string;
  idx: number;
  l0: string;
}

export interface MatrixHierarchy {
  nodes: MatrixHierNode[];
  accounts: MatrixHierAccount[];
}

export interface MatrixCells {
  n: number;
  row: number[];
  col: number[];
  v: number[];
  abs_o: number[];
  abs_d: number[];
  abs_e: number[];
  abs_b: number[];
  split: number[];
  flags: number[];
  n_entries: number[];
  refs: string[][];
}

export type MatrixPinned = Record<string, { total: "official" | "derived"; pins: string[] }>;
