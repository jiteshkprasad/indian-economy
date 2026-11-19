import { describe, expect, it } from "vitest";
import {
  cellRectCss,
  cellRectDev,
  hitColHeader,
  hitRowHeader,
  hitTest,
  layoutGrid,
} from "../../../src/lib/matrix/hit";

const DPRS = [1, 1.25, 1.5, 2, 2.625, 3];

describe("canvas layout", () => {
  for (const dpr of DPRS) {
    it(`snaps cells to whole device pixels and fits the width (dpr ${dpr})`, () => {
      const l = layoutGrid({ cssWidth: 343, nR: 13, nC: 13, dpr, left: 92, top: 88 });
      expect(Number.isInteger(l.cellDev)).toBe(true);
      expect(l.cellDev).toBeGreaterThanOrEqual(1);
      expect(l.width).toBeLessThanOrEqual(343 + 1e-9);
      expect(l.devWidth).toBe(Math.round(l.left * dpr) + l.cellDev * 13);
      expect(l.height).toBeCloseTo(l.top + l.cellCss * 13, 9);
    });
  }

  it("respects maxCell and minCell", () => {
    expect(layoutGrid({ cssWidth: 1200, nR: 3, nC: 3, dpr: 2, left: 0, top: 0, maxCell: 40 }).cellCss).toBe(40);
    const wide = layoutGrid({ cssWidth: 343, nR: 128, nC: 128, dpr: 1, left: 0, top: 0, minCell: 4 });
    expect(wide.cellCss).toBe(4);
    expect(wide.width).toBe(512); // scrolls rather than shrinking below the minimum
  });

  it("refuses an empty grid", () => {
    expect(() => layoutGrid({ cssWidth: 100, nR: 0, nC: 3, dpr: 1, left: 0, top: 0 })).toThrow();
  });
});

describe("hit-testing (pixel → cell)", () => {
  for (const dpr of DPRS) {
    for (const [nR, nC, w] of [
      [13, 13, 343],
      [128, 128, 1100],
      [5, 9, 700],
    ] as const) {
      it(`is the inverse of the drawn rectangles (${nR}×${nC}, dpr ${dpr})`, () => {
        const l = layoutGrid({ cssWidth: w, nR, nC, dpr, left: 120.3, top: 77.7 });
        for (let i = 0; i < nR; i += Math.max(1, Math.floor(nR / 7))) {
          for (let j = 0; j < nC; j += Math.max(1, Math.floor(nC / 7))) {
            const [x, y, cw, ch] = cellRectDev(l, i, j);
            // centre, top-left corner and the last device pixel inside the cell, in CSS px
            const pts: Array<[number, number]> = [
              [(x + cw / 2) / dpr, (y + ch / 2) / dpr],
              [x / dpr, y / dpr],
              [(x + cw - 0.5) / dpr, (y + ch - 0.5) / dpr],
            ];
            for (const [px, py] of pts) expect(hitTest(l, px, py)).toEqual({ i, j });
          }
        }
        // the device pixel just past the last cell is outside
        const [x, y, cw, ch] = cellRectDev(l, nR - 1, nC - 1);
        expect(hitTest(l, (x + cw + 0.5) / dpr, (y + ch / 2) / dpr)).toBeNull();
        expect(hitTest(l, (x + cw / 2) / dpr, (y + ch + 0.5) / dpr)).toBeNull();
      });
    }
  }

  it("gutters are not cells but hit the row and column headers", () => {
    const l = layoutGrid({ cssWidth: 400, nR: 4, nC: 4, dpr: 2, left: 100, top: 50 });
    expect(hitTest(l, 50, 60)).toBeNull();
    expect(hitTest(l, 150, 10)).toBeNull();
    const [cx, cy, cw] = cellRectCss(l, 2, 3);
    expect(hitRowHeader(l, 10, cy + cw / 2)).toBe(2);
    expect(hitColHeader(l, cx + cw / 2, 10)).toBe(3);
    expect(hitRowHeader(l, 150, cy)).toBeNull();
    expect(hitColHeader(l, cx, 60)).toBeNull();
  });

  it("CSS rectangles tile the grid without gaps", () => {
    const l = layoutGrid({ cssWidth: 500, nR: 3, nC: 3, dpr: 1.5, left: 33, top: 21 });
    const a = cellRectCss(l, 0, 0);
    const b = cellRectCss(l, 0, 1);
    expect(b[0]).toBeCloseTo(a[0] + a[2], 9);
  });
});
