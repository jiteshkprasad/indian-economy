import { describe, expect, it } from "vitest";
import { ROOT_ACCOUNTS, ROOT_BLOCKS, axisItems, indexHierarchy } from "../../../src/lib/matrix/axes";
import { RAMPS, cellFill, logScale, rgbCss } from "../../../src/lib/matrix/colour";
import { drawGrid, type Ctx2D } from "../../../src/lib/matrix/draw";
import { absDomain, at, buildGrid } from "../../../src/lib/matrix/grid";
import { cellRectDev, hitTest, layoutGrid } from "../../../src/lib/matrix/hit";
import { tinyCells, tinyHierarchy } from "./tiny";

type Call = { style: string; rect: [number, number, number, number] };

function recorder() {
  const calls: Call[] = [];
  const ctx: Ctx2D & { calls: Call[] } = {
    fillStyle: "",
    calls,
    setTransform() {},
    clearRect() {},
    fillRect(x, y, w, h) {
      calls.push({ style: String(this.fillStyle), rect: [x, y, w, h] });
    },
  };
  return ctx;
}

const ix = indexHierarchy(tinyHierarchy);
const colours = { block: "#000", grid: "#ccc" };

describe("canvas drawing", () => {
  for (const dpr of [1, 2, 3]) {
    it(`fills exactly the non-empty cells with their scale colour (dpr ${dpr})`, () => {
      const g = buildGrid(tinyCells, axisItems(ix, ROOT_ACCOUNTS.rows), axisItems(ix, ROOT_ACCOUNTS.cols), 6);
      const l = layoutGrid({ cssWidth: 300, nR: g.nR, nC: g.nC, dpr, left: 40, top: 30 });
      const scale = logScale(absDomain(g)!);
      const ctx = recorder();
      const drawn = drawGrid(ctx, l, g, RAMPS.light, scale, colours);
      expect(drawn).toBe(tinyCells.n);
      const fills = ctx.calls.filter((c) => c.style !== colours.block && c.style !== colours.grid);
      expect(fills.length).toBe(tinyCells.n);
      for (const f of fills) {
        // the centre of each painted rectangle hit-tests back to a cell with that colour
        const cx = (f.rect[0] + f.rect[2] / 2) / dpr;
        const cy = (f.rect[1] + f.rect[3] / 2) / dpr;
        const hit = hitTest(l, cx, cy)!;
        const p = at(g, hit.i, hit.j);
        expect(f.rect).toEqual(cellRectDev(l, hit.i, hit.j));
        expect(f.style).toBe(rgbCss(cellFill(RAMPS.light, scale, g.v[p], g.nCells[p])!));
      }
    });
  }

  it("draws block lines at level-0 boundaries and a negative cell in the negative hue", () => {
    const g = buildGrid(tinyCells, axisItems(ix, ROOT_ACCOUNTS.rows), axisItems(ix, ROOT_ACCOUNTS.cols), 6);
    const l = layoutGrid({ cssWidth: 300, nR: g.nR, nC: g.nC, dpr: 1, left: 0, top: 0 });
    const ctx = recorder();
    const scale = logScale(absDomain(g)!);
    drawGrid(ctx, l, g, RAMPS.light, scale, colours);
    const blocks = ctx.calls.filter((c) => c.style === colours.block);
    // 2 boundaries per axis (P|Q, Q|R) + 4 frame edges
    expect(blocks.length).toBe(8);
    // p3 receives -20 from q1: row p3 (2), col q1 (3)
    const neg = rgbCss(cellFill(RAMPS.light, scale, -20, 1)!);
    expect(neg).not.toBe(rgbCss(cellFill(RAMPS.light, scale, 20, 1)!));
    expect(ctx.calls.some((c) => c.style === neg)).toBe(true);
  });

  it("draws faint grid lines only when cells are large", () => {
    const g = buildGrid(tinyCells, axisItems(ix, ROOT_BLOCKS.rows), axisItems(ix, ROOT_BLOCKS.cols), 6);
    const big = layoutGrid({ cssWidth: 300, nR: 3, nC: 3, dpr: 1, left: 0, top: 0 });
    const small = layoutGrid({ cssWidth: 300, nR: 3, nC: 3, dpr: 1, left: 0, top: 0, maxCell: 6 });
    const a = recorder();
    const b = recorder();
    const scale = logScale(absDomain(g)!);
    drawGrid(a, big, g, RAMPS.dark, scale, colours);
    drawGrid(b, small, g, RAMPS.dark, scale, colours);
    expect(a.calls.filter((c) => c.style === colours.grid).length).toBe(4);
    expect(b.calls.filter((c) => c.style === colours.grid).length).toBe(0);
  });
});
