// The matrix table must show the same numbers as the map: summing account cells into a block
// grid has to agree with src/data/aggregate.ts (PLAN §5.2, U4 "table aggregation equals
// aggregate()"). Checked on a tiny in-test SAM, on the generated fixture, and on the real export
// when it exists.
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { aggregate, visibleNodes } from "../../../src/data/aggregate";
import type { Cells, Hierarchy, Pinned } from "../../../src/data/types";
import { indexHierarchy, itemsFromIds } from "../../../src/lib/matrix/axes";
import { at, buildGrid } from "../../../src/lib/matrix/grid";
import { tinyCells, tinyHierarchy } from "./tiny";

const TOL = 1e-6;

function compare(cells: Cells, h: Hierarchy, preset: "simple" | "full", expanded: string[], pinned: Pinned = {}) {
  const vis = visibleNodes(h, preset, expanded);
  const agg = aggregate(cells, h, vis, pinned);
  // merged preset nodes (PRODUCERS, SI+FINM) are not hierarchy nodes; the matrix only shows
  // hierarchy nodes, so compare the full preset (any expansion) where every visible id is a node
  const ix = indexHierarchy(h);
  const items = itemsFromIds(ix, vis.ids);
  const g = buildGrid(cells, items, items, h.accounts.length);
  const pos = new Map(vis.ids.map((id, k) => [id, k]));
  const isPrds = h.accounts.map((a) => a.l0 === "PRDS");
  let checked = 0;
  // every aggregate link equals the matching part of the matrix cell
  const seen = new Set<string>();
  for (const l of agg.links) {
    const p = at(g, pos.get(l.receiver)!, pos.get(l.payer)!);
    const want = l.part === "pos" ? g.pos[p] : g.neg[p];
    expect(Math.abs(l.value - want)).toBeLessThan(TOL);
    seen.add(`${l.payer}|${l.receiver}|${l.part}`);
    checked++;
  }
  // every non-empty off-diagonal matrix part is an aggregate link, unless both ends are in PRDS
  // (those stay internal to PRDS at every zoom in the map; the matrix still shows them)
  let prdsInside = 0;
  for (let i = 0; i < g.nR; i++) {
    for (let j = 0; j < g.nC; j++) {
      const p = at(g, i, j);
      if (i === j || g.nCells[p] === 0) continue;
      const bothPrds = g.rows[i].accounts.every((a) => isPrds[a]) && g.cols[j].accounts.every((a) => isPrds[a]);
      if (bothPrds) {
        prdsInside += g.v[p];
        continue;
      }
      if (g.pos[p] > 0) expect(seen.has(`${g.cols[j].id}|${g.rows[i].id}|pos`)).toBe(true);
      if (g.neg[p] < 0) expect(seen.has(`${g.cols[j].id}|${g.rows[i].id}|neg`)).toBe(true);
    }
  }
  // the diagonal equals the aggregate's internal flows (PRDS also holds its children's cross flows)
  for (const id of vis.ids) {
    const k = pos.get(id)!;
    const p = at(g, k, k);
    const it = agg.internal[id];
    if (g.nCells[p] === 0 && !it) continue;
    expect(Math.abs((it ? it.pos + it.neg : 0) - g.v[p])).toBeLessThan(TOL);
    checked++;
  }
  // with PRDS expanded, flows between its children are the aggregate's PRDS internal flows
  if (!pos.has("PRDS")) {
    const it = agg.internal.PRDS;
    expect(Math.abs((it ? it.pos + it.neg : 0) - prdsInside)).toBeLessThan(TOL);
  }
  return checked;
}

function tinyAsHierarchy(): { h: Hierarchy; cells: Cells } {
  const h = {
    nodes: tinyHierarchy.nodes.map((n) => ({ ...n, col: 0, kind: "production", expandable: n.children.length > 0 })),
    accounts: tinyHierarchy.accounts.map((a) => ({ ...a, group: a.l0, l1: null, name_tech: a.code })),
    columns: [],
    split_node: "P",
    presets: {
      simple: { merges: {}, columns: [], split_node: "P", return_flows: "stubs" },
      full: { merges: {}, columns: [], split_node: "P", return_flows: "arcs" },
    },
    ts_nodes: [],
  } as unknown as Hierarchy;
  return { h, cells: tinyCells as Cells };
}

describe("matrix grid equals aggregate() (tiny SAM)", () => {
  const { h, cells } = tinyAsHierarchy();
  for (const expanded of [[], ["P"], ["P", "P.X"], ["R", "Q"], ["P.X", "R.Y"]]) {
    it(`expanded = [${expanded.join(", ")}]`, () => {
      expect(compare(cells, h, "full", expanded)).toBeGreaterThan(0);
    });
  }
});

function loadRoot(dir: string) {
  const idxPath = path.join(dir, "index.json");
  if (!fs.existsSync(idxPath)) return null;
  const idx = JSON.parse(fs.readFileSync(idxPath, "utf8"));
  const read = (f: string) => JSON.parse(fs.readFileSync(path.join(dir, idx.data_version, f), "utf8"));
  return {
    fixture: idx.fixture as boolean,
    h: read("hierarchy.json") as Hierarchy,
    cells: read("sam/cells.json") as Cells,
    pinned: read("sam/pinned.json") as Pinned,
  };
}

const WEB = path.resolve(__dirname, "../../..");
const roots: Array<[string, string]> = [
  ["fixture", path.join(WEB, "fixtures", "data")],
  ["real export", path.join(WEB, "public", "data")],
];

for (const [name, dir] of roots) {
  const data = loadRoot(dir);
  describe(`matrix grid equals aggregate() (${name})`, () => {
    if (!data || (name === "real export" && data.fixture)) {
      it.skip(`${name.toUpperCase()} NOT PRESENT: parity on ${name} not run`, () => {});
      return;
    }
    const zooms: string[][] = [[], ["HH"], ["PRDS"], ["PRDS", "PRDS.MANU", "TAX"], ["FINM", "SI", "FC", "HH.URB"]];
    for (const expanded of zooms) {
      it(`expanded = [${expanded.join(", ")}]`, () => {
        expect(compare(data.cells, data.h, "full", expanded, data.pinned)).toBeGreaterThan(0);
      });
    }
  });
}
