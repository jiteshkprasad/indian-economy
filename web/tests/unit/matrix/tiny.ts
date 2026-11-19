// A tiny in-test hierarchy and cell set for the matrix library tests (no fixture needed).
//
//   P (level 0)            Q (level 0)       R (level 0)
//   ├─ P.X: p1, p2         └─ q1 (leaf)      └─ R.Y: r1, r2
//   └─ p3 (leaf)
//
// Accounts in hierarchy.accounts order (idx): q1 0, p1 1, p2 2, p3 3, r1 4, r2 5 — deliberately
// not matrix order, which is P, Q, R depth-first: p1 p2 p3 q1 r1 r2.

import type { MatrixCells, MatrixHierarchy } from "../../../src/lib/matrix/types";

export const tinyHierarchy: MatrixHierarchy = {
  nodes: [
    { id: "R", level: 0, parent: null, children: ["R.Y"], accounts: ["r1", "r2"], order: 8 },
    { id: "R.Y", level: 1, parent: "R", children: ["r1", "r2"], accounts: ["r1", "r2"], order: 9 },
    { id: "r1", level: 2, parent: "R.Y", children: [], accounts: ["r1"], order: 10 },
    { id: "r2", level: 2, parent: "R.Y", children: [], accounts: ["r2"], order: 11 },
    { id: "P", level: 0, parent: null, children: ["P.X", "p3"], accounts: ["p1", "p2", "p3"], order: 1 },
    { id: "P.X", level: 1, parent: "P", children: ["p1", "p2"], accounts: ["p1", "p2"], order: 2 },
    { id: "p1", level: 2, parent: "P.X", children: [], accounts: ["p1"], order: 3 },
    { id: "p2", level: 2, parent: "P.X", children: [], accounts: ["p2"], order: 4 },
    { id: "p3", level: 1, parent: "P", children: [], accounts: ["p3"], order: 5 },
    { id: "Q", level: 0, parent: null, children: ["q1"], accounts: ["q1"], order: 6 },
    { id: "q1", level: 1, parent: "Q", children: [], accounts: ["q1"], order: 7 },
  ],
  accounts: [
    { code: "q1", idx: 0, l0: "Q" },
    { code: "p1", idx: 1, l0: "P" },
    { code: "p2", idx: 2, l0: "P" },
    { code: "p3", idx: 3, l0: "P" },
    { code: "r1", idx: 4, l0: "R" },
    { code: "r2", idx: 5, l0: "R" },
  ],
};

type Cell = { row: number; col: number; v: number; label: 0 | 1 | 2 | 3; flags?: number };

// row receives, col pays
const raw: Cell[] = [
  { row: 1, col: 0, v: 100, label: 0 }, // q1 pays p1
  { row: 2, col: 0, v: 50, label: 2, flags: 1 }, // q1 pays p2
  { row: 3, col: 0, v: -20, label: 2, flags: 32 }, // q1 pays p3 (negative)
  { row: 0, col: 1, v: 90, label: 1 }, // p1 pays q1
  { row: 0, col: 3, v: 60, label: 3, flags: 2 }, // p3 pays q1
  { row: 2, col: 1, v: 10, label: 2 }, // p1 pays p2 (inside P)
  { row: 4, col: 2, v: 30, label: 0 }, // p2 pays r1
  { row: 5, col: 2, v: -5, label: 2, flags: 32 }, // p2 pays r2 (negative)
  { row: 4, col: 3, v: 7, label: 1 }, // p3 pays r1
  { row: 1, col: 4, v: 0.5, label: 2 }, // r1 pays p1
  { row: 0, col: 5, v: 12, label: 0 }, // r2 pays q1
  { row: 5, col: 4, v: 3, label: 2, flags: 8 }, // r1 pays r2 (inside R)
];

export const tinyCells: MatrixCells = {
  n: raw.length,
  row: raw.map((c) => c.row),
  col: raw.map((c) => c.col),
  v: raw.map((c) => c.v),
  abs_o: raw.map((c) => (c.label === 0 ? Math.abs(c.v) : 0)),
  abs_d: raw.map((c) => (c.label === 1 ? Math.abs(c.v) : 0)),
  abs_e: raw.map((c) => (c.label === 2 ? Math.abs(c.v) : 0)),
  abs_b: raw.map((c) => (c.label === 3 ? Math.abs(c.v) : 0)),
  split: raw.map((c) => c.label),
  flags: raw.map((c) => c.flags ?? 0),
  n_entries: raw.map(() => 1),
  refs: raw.map(() => ["X1"]),
};
