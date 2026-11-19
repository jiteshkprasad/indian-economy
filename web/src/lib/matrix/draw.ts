// Draws the heat-map grid onto a canvas (PLAN §4.8). Labels, the cursor and the highlighted row
// and column are an SVG overlay drawn by the component; this draws only cells and lines, so it
// stays fast for 128 × 128. The context is a narrow interface so the drawing can be tested with a
// recording mock.

import { blockBoundaries } from "./axes";
import { cellFill, rgbCss, type LogScale, type Ramp } from "./colour";
import type { Grid } from "./grid";
import { cellRectDev, type GridLayout } from "./hit";

export interface Ctx2D {
  fillStyle: string | CanvasGradient | CanvasPattern;
  setTransform(a: number, b: number, c: number, d: number, e: number, f: number): void;
  clearRect(x: number, y: number, w: number, h: number): void;
  fillRect(x: number, y: number, w: number, h: number): void;
}

export interface DrawColours {
  /** Lines between level-0 (or current) blocks. */
  block: string;
  /** Faint lines between cells (drawn only when cells are large enough). */
  grid: string;
}

/** Cells at least this many CSS px wide get faint separating lines. */
export const GRID_LINE_MIN_CELL = 10;

export function drawGrid(
  ctx: Ctx2D,
  l: GridLayout,
  g: Grid,
  ramp: Ramp,
  scale: LogScale | null,
  colours: DrawColours,
): number {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, l.devWidth, l.devHeight);
  let drawn = 0;
  for (let i = 0; i < g.nR; i++) {
    for (let j = 0; j < g.nC; j++) {
      const p = i * g.nC + j;
      if (g.nCells[p] === 0 || scale === null) continue;
      const fill = cellFill(ramp, scale, g.v[p], g.nCells[p]);
      if (!fill) continue;
      const [x, y, w, h] = cellRectDev(l, i, j);
      ctx.fillStyle = rgbCss(fill);
      ctx.fillRect(x, y, w, h);
      drawn++;
    }
  }
  const [x0, y0] = cellRectDev(l, 0, 0);
  const W = l.cellDev * g.nC;
  const H = l.cellDev * g.nR;
  const line = Math.max(1, Math.round(l.dpr));
  if (l.cellCss >= GRID_LINE_MIN_CELL) {
    ctx.fillStyle = colours.grid;
    for (let i = 1; i < g.nR; i++) ctx.fillRect(x0, y0 + i * l.cellDev, W, 1);
    for (let j = 1; j < g.nC; j++) ctx.fillRect(x0 + j * l.cellDev, y0, 1, H);
  }
  ctx.fillStyle = colours.block;
  for (const i of blockBoundaries(g.rows)) ctx.fillRect(x0, y0 + i * l.cellDev - (line >> 1), W, line);
  for (const j of blockBoundaries(g.cols)) ctx.fillRect(x0 + j * l.cellDev - (line >> 1), y0, line, H);
  // frame
  ctx.fillRect(x0, y0, W, line);
  ctx.fillRect(x0, y0 + H - line, W, line);
  ctx.fillRect(x0, y0, line, H);
  ctx.fillRect(x0 + W - line, y0, line, H);
  return drawn;
}
