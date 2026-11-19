import { describe, expect, it } from "vitest";
import {
  ROOT_ACCOUNTS,
  ROOT_BLOCKS,
  axisItems,
  axisTrail,
  blockBoundaries,
  indexHierarchy,
  zoomAxis,
  zoomInto,
} from "../../../src/lib/matrix/axes";
import { absDomain, at, buildGrid, colTotals, rowTotals } from "../../../src/lib/matrix/grid";
import { composition, headlineSplit } from "../../../src/lib/status";
import { totalFor } from "../../../src/lib/matrix/links";
import { tinyCells, tinyHierarchy } from "./tiny";

const ix = indexHierarchy(tinyHierarchy);
const N = tinyHierarchy.accounts.length;

describe("matrix order and axes", () => {
  it("orders accounts depth-first by hierarchy order", () => {
    expect(ix.matrixOrder).toEqual(["p1", "p2", "p3", "q1", "r1", "r2"]);
  });

  it("root blocks are the level-0 nodes; root accounts are all leaves with level-0 blocks", () => {
    expect(axisItems(ix, ROOT_BLOCKS.rows).map((x) => x.id)).toEqual(["P", "Q", "R"]);
    const acc = axisItems(ix, ROOT_ACCOUNTS.rows);
    expect(acc.map((x) => x.id)).toEqual(["p1", "p2", "p3", "q1", "r1", "r2"]);
    expect(acc.map((x) => x.block)).toEqual(["P", "P", "P", "Q", "R", "R"]);
    expect(blockBoundaries(acc)).toEqual([3, 4]);
  });

  it("an item sums exactly its accounts; every account is on the root axis once", () => {
    const blocks = axisItems(ix, ROOT_BLOCKS.rows);
    const all = blocks.flatMap((b) => b.accounts).sort();
    expect(all).toEqual([0, 1, 2, 3, 4, 5]);
    expect(blocks[0].accounts.sort()).toEqual([1, 2, 3]);
  });

  it("zooms a block into its children and stops at single accounts", () => {
    const [P, Q] = axisItems(ix, ROOT_BLOCKS.rows);
    const zp = zoomAxis(ix, ROOT_BLOCKS.rows, P)!;
    expect(zp).toEqual({ parent: "P", grain: "children" });
    const kids = axisItems(ix, zp);
    expect(kids.map((x) => x.id)).toEqual(["P.X", "p3"]);
    expect(kids.map((x) => x.expandable)).toEqual([true, false]);
    // Q has one child (q1): zooming shows it; zooming q1 itself gives nothing deeper
    const zq = zoomAxis(ix, ROOT_BLOCKS.rows, Q)!;
    expect(axisItems(ix, zq).map((x) => x.id)).toEqual(["q1"]);
    expect(zoomAxis(ix, zq, axisItems(ix, zq)[0])).toBeNull();
    expect(zoomAxis(ix, zp, kids[1])).toBeNull();
    expect(axisTrail(ix, zoomAxis(ix, zp, kids[0])!)).toEqual(["P", "P.X"]);
  });

  it("from the account grid, a cell zooms into the level-0 blocks that contain it", () => {
    const rows = axisItems(ix, ROOT_ACCOUNTS.rows);
    const cols = axisItems(ix, ROOT_ACCOUNTS.cols);
    const z = zoomInto(ix, ROOT_ACCOUNTS, rows[1], cols[4])!; // p2 row, r1 col
    expect(z.rows).toEqual({ parent: "P", grain: "children" });
    expect(z.cols).toEqual({ parent: "R", grain: "children" });
  });

  it("rejects unknown nodes loudly", () => {
    expect(() => axisItems(ix, { parent: "NOPE", grain: "children" })).toThrow(/unknown node/);
  });
});

describe("grid aggregation", () => {
  it("conserves every cell: grid total equals the sum of all cells at every zoom", () => {
    const total = tinyCells.v.reduce((a, b) => a + b, 0);
    for (const z of [ROOT_BLOCKS, ROOT_ACCOUNTS]) {
      const g = buildGrid(tinyCells, axisItems(ix, z.rows), axisItems(ix, z.cols), N);
      expect(g.v.reduce((a, b) => a + b, 0)).toBeCloseTo(total, 9);
      expect(g.nCells.reduce((a, b) => a + b, 0)).toBe(tinyCells.n);
    }
  });

  it("keeps positive and negative parts, OR'd flags and abs by label", () => {
    const rows = axisItems(ix, ROOT_BLOCKS.rows);
    const cols = axisItems(ix, ROOT_BLOCKS.cols);
    const g = buildGrid(tinyCells, rows, cols, N);
    // P receives from Q: 100 + 50 - 20
    const p = at(g, 0, 1);
    expect(g.v[p]).toBe(130);
    expect(g.pos[p]).toBe(150);
    expect(g.neg[p]).toBe(-20);
    expect(g.flags[p]).toBe(1 | 32);
    expect(g.absO[p]).toBe(100);
    expect(g.absE[p]).toBe(70);
    const c = composition(g.absO[p], g.absD[p], g.absE[p], g.absB[p])!;
    expect(c.o + c.d + c.e + c.b).toBeCloseTo(1, 12);
    expect(c.e).toBeCloseTo(70 / 170, 12);
    expect(headlineSplit(c)).toBe("estimated");
    // internal flow P -> P stays on the diagonal
    expect(g.v[at(g, 0, 0)]).toBe(10);
    // R receives from P: 30 - 5 + 7
    expect(g.v[at(g, 2, 0)]).toBe(32);
    const q = at(g, 1, 1);
    expect(g.nCells[q]).toBe(0);
    expect(composition(g.absO[q], g.absD[q], g.absE[q], g.absB[q])).toBeNull();
  });

  it("row and column totals match the cells' receipts and payments", () => {
    const rows = axisItems(ix, ROOT_BLOCKS.rows);
    const cols = axisItems(ix, ROOT_BLOCKS.cols);
    const g = buildGrid(tinyCells, rows, cols, N);
    const rt = rowTotals(g);
    const ct = colTotals(g);
    const recv = (accs: number[]) =>
      tinyCells.v.reduce((s, v, k) => (accs.includes(tinyCells.row[k]) ? s + v : s), 0);
    const pay = (accs: number[]) =>
      tinyCells.v.reduce((s, v, k) => (accs.includes(tinyCells.col[k]) ? s + v : s), 0);
    rows.forEach((r, i) => expect(rt[i]).toBeCloseTo(recv(r.accounts), 9));
    cols.forEach((c, j) => expect(ct[j]).toBeCloseTo(pay(c.accounts), 9));
  });

  it("a mixed zoom only contains the cells on its axes, with members when asked", () => {
    const rows = axisItems(ix, { parent: "P", grain: "children" }); // P.X, p3
    const cols = axisItems(ix, ROOT_BLOCKS.cols);
    const g = buildGrid(tinyCells, rows, cols, N, true);
    expect(g.nR).toBe(2);
    expect(g.v[at(g, 0, 1)]).toBe(150); // P.X receives from Q
    expect(g.v[at(g, 1, 1)]).toBe(-20); // p3 receives from Q (negative)
    expect(g.members![at(g, 0, 1)].sort()).toEqual([0, 1]);
    expect(absDomain(g)).toEqual([0.5, 150]);
  });

  it("refuses an axis that lists an account twice", () => {
    const rows = axisItems(ix, ROOT_BLOCKS.rows);
    expect(() => buildGrid(tinyCells, [...rows, rows[0]], rows, N)).toThrow(/twice/);
  });
});

describe("total labels from pinned.json", () => {
  const pinned = {
    "Q--P~pair": { total: "official" as const, pins: ["c1"] },
    "P--R": { total: "derived" as const, pins: ["ts:F01"] },
    "Q--R~neg": { total: "official" as const, pins: ["c2"] },
  };
  it("uses the pair label for a cell with both parts", () => {
    expect(totalFor(pinned, "Q", "P", 150, -20)).toEqual({ total: "official", pins: ["c1"], part: "pair" });
  });
  it("uses the positive or negative part when the cell has one sign", () => {
    expect(totalFor(pinned, "P", "R", 37, 0).total).toBe("derived");
    expect(totalFor(pinned, "Q", "R", 0, -3).part).toBe("neg");
  });
  it("a cell with both parts is not labelled by one part's pin", () => {
    expect(totalFor(pinned, "P", "R", 37, -5).total).toBeNull();
  });
  it("an unlisted pair has no total", () => {
    expect(totalFor(pinned, "R", "P", 1, 0)).toEqual({ total: null, pins: [], part: null });
  });
});
