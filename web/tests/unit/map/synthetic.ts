/**
 * A small synthetic balanced SAM for the layout tests, built in the test (no fixture needed).
 * Balance holds by construction: values are added around closed cycles of accounts, so every
 * account's receipts equal its payments. Some cycles are negative, which yields negative cells.
 */
import type { LayoutLinkInput, LayoutNodeInput } from "@/lib/sankey/types";
import { drawnLinks, type PairPart } from "@/lib/sankey/links";

export function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Level-0 groups: id, payer column, receiver column (split node), kind, level-1 groups of accounts. */
export const GROUPS: Array<{ id: string; col: number; inCol?: number; kind: string; subs: string[][] }> = [
  { id: "P", col: 0, inCol: 6, kind: "production", subs: [["p1", "p2"], ["p3"]] },
  { id: "A", col: 1, kind: "production", subs: [["a1", "a2"], ["a3"]] },
  { id: "R", col: 1, kind: "row", subs: [["r1"]] },
  { id: "F", col: 2, kind: "factors", subs: [["f1"], ["f2"]] },
  { id: "H", col: 3, kind: "households", subs: [["h1", "h2"], ["h3", "h4"]] },
  { id: "C", col: 3, kind: "corporations", subs: [["c1"], ["c2"]] },
  { id: "G", col: 4, kind: "government", subs: [["g1"], ["g2"]] },
  { id: "S", col: 5, kind: "capital", subs: [["s1", "s2"], ["s3"]] },
  { id: "D", col: 5, kind: "discrepancy", subs: [["d1"]] },
];

export type Synthetic = {
  accounts: string[];
  /** cells.get(`${row}|${col}`) = signed value; row receives, col pays. */
  cells: Map<string, number>;
  gdp: number;
};

export function makeSynthetic(seed = 20261002, nCycles = 60): Synthetic {
  const r = rng(seed);
  const accounts = GROUPS.flatMap((g) => g.subs.flat());
  const cells = new Map<string, number>();
  const add = (payer: string, receiver: string, v: number) => {
    if (payer === receiver) return;
    const k = `${receiver}|${payer}`;
    cells.set(k, (cells.get(k) ?? 0) + v);
  };
  // a backbone circular flow through every column, then random cycles
  const backbone = ["p1", "a1", "f1", "h1", "g1", "s1", "p2"];
  for (let i = 0; i < backbone.length; i++) add(backbone[i], backbone[(i + 1) % backbone.length], 5000);
  for (let k = 0; k < nCycles; k++) {
    const len = 2 + Math.floor(r() * 4);
    const cyc: string[] = [];
    while (cyc.length < len) {
      const a = accounts[Math.floor(r() * accounts.length)];
      if (!cyc.includes(a)) cyc.push(a);
    }
    const negative = k % 9 === 4;
    const v = (negative ? -1 : 1) * (negative ? 50 + r() * 300 : 20 + r() * 2000);
    for (let i = 0; i < cyc.length; i++) add(cyc[i], cyc[(i + 1) % cyc.length], v);
  }
  // round to 2 dp like the export
  for (const [k, v] of cells) {
    const rv = Math.round(v * 100) / 100;
    if (rv === 0) cells.delete(k);
    else cells.set(k, rv);
  }
  return { accounts, cells, gdp: 20000 };
}

/** Visible nodes: level-0 groups, with `expanded` level-0 ids replaced by their level-1 groups. */
export function synthNodes(expanded: string[] = []): { nodes: LayoutNodeInput[]; map: Map<string, string> } {
  const nodes: LayoutNodeInput[] = [];
  const map = new Map<string, string>();
  let order = 0;
  for (const g of GROUPS) {
    if (expanded.includes(g.id)) {
      g.subs.forEach((s, i) => {
        const id = `${g.id}.${i}`;
        nodes.push({ id, col: g.col, inCol: g.inCol, order: order++, kind: g.kind });
        s.forEach((a) => map.set(a, id));
      });
    } else {
      nodes.push({ id: g.id, col: g.col, inCol: g.inCol, order: order++, kind: g.kind });
      g.subs.flat().forEach((a) => map.set(a, g.id));
    }
  }
  return { nodes, map };
}

/** Test-only aggregation: account cells → positive and negative parts per visible pair. */
export function synthLinks(s: Synthetic, map: Map<string, string>): LayoutLinkInput[] {
  const parts = new Map<string, PairPart>();
  const keys = [...s.cells.keys()].sort();
  for (const k of keys) {
    const v = s.cells.get(k)!;
    const [row, col] = k.split("|");
    const payer = map.get(col)!;
    const receiver = map.get(row)!;
    if (payer === receiver) continue;
    const pk = `${payer}--${receiver}`;
    const p = parts.get(pk) ?? { payer, receiver, pos: 0, neg: 0 };
    if (v > 0) p.pos += v;
    else p.neg += v;
    parts.set(pk, p);
  }
  return drawnLinks([...parts.values()]);
}
