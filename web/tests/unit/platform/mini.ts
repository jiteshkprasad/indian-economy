import type { Cells, Hierarchy, HierarchyNode } from "@/data/types";

/**
 * A tiny balanced SAM on a toy hierarchy shaped like the real one (PLAN §3.2):
 * PRDS (with a level-1 group and the margin account), PROD, FACT, HH (two
 * accounts), TAX, SI, FINM; presets simple (PRODUCERS = PRDS + PROD, SI absorbs FINM) and full.
 * Every account balances (row sum = column sum). One negative cell (a subsidy).
 */
export const ACCOUNTS = ["C_A", "C_B", "M_TTM", "A_A", "F_L", "H_R1", "H_U1", "T_1", "K_HH", "I_DEPO"] as const;
const L0: Record<string, string> = {
  C_A: "PRDS",
  C_B: "PRDS",
  M_TTM: "PRDS",
  A_A: "PROD",
  F_L: "FACT",
  H_R1: "HH",
  H_U1: "HH",
  T_1: "TAX",
  K_HH: "SI",
  I_DEPO: "FINM",
};

// [row (receives), col (pays), value]
export const CELLS: Array<[string, string, number]> = [
  ["M_TTM", "C_A", 5],
  ["C_B", "M_TTM", 5],
  ["A_A", "C_A", 62],
  ["A_A", "C_B", 38],
  ["C_A", "A_A", 30],
  ["F_L", "A_A", 70],
  ["H_R1", "F_L", 40],
  ["H_U1", "F_L", 30],
  ["C_A", "H_R1", 30],
  ["T_1", "H_R1", 5],
  ["K_HH", "H_R1", 5],
  ["C_B", "H_U1", 20],
  ["K_HH", "H_U1", 10],
  ["C_A", "T_1", 7],
  ["C_B", "T_1", -2],
  ["C_B", "K_HH", 10],
  ["I_DEPO", "K_HH", 5],
  ["C_B", "I_DEPO", 5],
];

function node(p: Partial<HierarchyNode> & { id: string }): HierarchyNode {
  return { level: 0, parent: null, children: [], accounts: [], order: 0, col: 0, kind: "production", expandable: false, ...p };
}

export function miniHierarchy(): Hierarchy {
  const nodes: HierarchyNode[] = [
    node({ id: "PRDS", children: ["PRDS.X", "M_TTM"], accounts: ["C_A", "C_B", "M_TTM"], order: 0, col: 0, expandable: true }),
    node({ id: "PRDS.X", level: 1, parent: "PRDS", children: ["C_A", "C_B"], accounts: ["C_A", "C_B"], order: 1, expandable: true }),
    node({ id: "C_A", level: 2, parent: "PRDS.X", accounts: ["C_A"], order: 2 }),
    node({ id: "C_B", level: 2, parent: "PRDS.X", accounts: ["C_B"], order: 3 }),
    node({ id: "M_TTM", level: 2, parent: "PRDS", accounts: ["M_TTM"], order: 4 }),
    node({ id: "PROD", accounts: ["A_A"], order: 5, col: 1 }),
    node({ id: "FACT", accounts: ["F_L"], order: 6, col: 2, kind: "factors" }),
    node({ id: "HH", children: ["H_R1", "H_U1"], accounts: ["H_R1", "H_U1"], order: 7, col: 3, kind: "households", expandable: true }),
    node({ id: "H_R1", level: 2, parent: "HH", accounts: ["H_R1"], order: 8, col: 3, kind: "households" }),
    node({ id: "H_U1", level: 2, parent: "HH", accounts: ["H_U1"], order: 9, col: 3, kind: "households" }),
    node({ id: "TAX", accounts: ["T_1"], order: 10, col: 4, kind: "government" }),
    node({ id: "SI", accounts: ["K_HH"], order: 11, col: 6, kind: "capital" }),
    node({ id: "FINM", accounts: ["I_DEPO"], order: 12, col: 7, kind: "capital" }),
  ];
  return {
    nodes,
    accounts: ACCOUNTS.map((code, idx) => ({ code, idx, group: code.split("_")[0], l0: L0[code], l1: code === "C_A" || code === "C_B" ? "PRDS.X" : null, name_tech: code })),
    columns: [["PRDS"], ["PROD"], ["FACT"], ["HH"], ["TAX"], [], ["SI"], ["FINM"], ["PRDS"]],
    split_node: "PRDS",
    presets: {
      simple: {
        merges: { PRODUCERS: ["PRDS", "PROD"], SI: ["SI", "FINM"] },
        columns: [["PRODUCERS"], [], ["FACT"], ["HH"], ["TAX"], [], ["SI"], ["PRODUCERS"]],
        split_node: "PRODUCERS",
        return_flows: "stubs",
      },
      full: { merges: {}, columns: [["PRDS"], ["PROD"], ["FACT"], ["HH"], ["TAX"], [], ["SI"], ["FINM"], ["PRDS"]], split_node: "PRDS", return_flows: "arcs" },
    },
    ts_nodes: [],
  };
}

export function miniCells(): Cells {
  const idx = new Map(ACCOUNTS.map((a, i) => [a as string, i]));
  const c: Cells = { n: CELLS.length, row: [], col: [], v: [], abs_o: [], abs_d: [], abs_e: [], abs_b: [], split: [], flags: [], n_entries: [], refs: [] };
  CELLS.forEach(([r, k, v], i) => {
    c.row.push(idx.get(r)!);
    c.col.push(idx.get(k)!);
    c.v.push(v);
    const a = Math.abs(v);
    // households' spending is estimated, the rest official; one cell set by balancing
    const est = k === "H_R1" || k === "H_U1";
    const bal = r === "K_HH" && k === "H_U1";
    c.abs_o.push(est || bal ? 0 : a);
    c.abs_d.push(0);
    c.abs_e.push(est && !bal ? a : 0);
    c.abs_b.push(bal ? a : 0);
    c.split.push(bal ? 3 : est ? 2 : 0);
    c.flags.push(v < 0 ? 32 : bal ? 2 : 0);
    c.n_entries.push(1 + (i % 2));
    c.refs.push(v < 0 ? ["P2"] : [`R${i % 3}`]);
  });
  return c;
}
