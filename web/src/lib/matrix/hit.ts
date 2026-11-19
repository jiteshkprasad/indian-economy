// Canvas geometry and hit-testing for the heat-map (PLAN §4.8).
//
// Cells are square and snapped to whole device pixels, so lines stay crisp at any
// devicePixelRatio. All pointer maths is done in CSS pixels relative to the canvas box;
// drawing uses device pixels. hitTest(layout, x, y) is the exact inverse of cellRectDev.

export interface GridLayout {
  dpr: number;
  nR: number;
  nC: number;
  /** Left and top gutters (row and column labels), CSS px. Snapped to whole device px. */
  left: number;
  top: number;
  /** Cell size in device px (integer ≥ 1) and in CSS px. */
  cellDev: number;
  cellCss: number;
  /** Canvas size in CSS px and device px. */
  width: number;
  height: number;
  devWidth: number;
  devHeight: number;
}

export interface LayoutInput {
  /** Available width in CSS px. */
  cssWidth: number;
  nR: number;
  nC: number;
  dpr: number;
  left: number;
  top: number;
  /** Largest cell size in CSS px (small matrices must not become enormous). */
  maxCell?: number;
  /** Smallest cell size in CSS px; the canvas becomes wider than cssWidth (scrolls) below it. */
  minCell?: number;
}

export function layoutGrid(inp: LayoutInput): GridLayout {
  const dpr = inp.dpr > 0 && Number.isFinite(inp.dpr) ? inp.dpr : 1;
  if (inp.nR < 1 || inp.nC < 1) throw new Error("matrix layout: empty grid");
  const leftDev = Math.round(inp.left * dpr);
  const topDev = Math.round(inp.top * dpr);
  const availDev = Math.floor(inp.cssWidth * dpr) - leftDev;
  let cellDev = Math.floor(availDev / inp.nC);
  if (inp.maxCell !== undefined) cellDev = Math.min(cellDev, Math.floor(inp.maxCell * dpr));
  if (inp.minCell !== undefined) cellDev = Math.max(cellDev, Math.ceil(inp.minCell * dpr));
  cellDev = Math.max(1, cellDev);
  const devWidth = leftDev + cellDev * inp.nC;
  const devHeight = topDev + cellDev * inp.nR;
  return {
    dpr,
    nR: inp.nR,
    nC: inp.nC,
    left: leftDev / dpr,
    top: topDev / dpr,
    cellDev,
    cellCss: cellDev / dpr,
    width: devWidth / dpr,
    height: devHeight / dpr,
    devWidth,
    devHeight,
  };
}

/** Device-pixel rectangle [x, y, w, h] of cell (i, j). */
export function cellRectDev(l: GridLayout, i: number, j: number): [number, number, number, number] {
  const leftDev = Math.round(l.left * l.dpr);
  const topDev = Math.round(l.top * l.dpr);
  return [leftDev + j * l.cellDev, topDev + i * l.cellDev, l.cellDev, l.cellDev];
}

/** CSS-pixel rectangle of cell (i, j), for the SVG overlay. */
export function cellRectCss(l: GridLayout, i: number, j: number): [number, number, number, number] {
  const [x, y, w, h] = cellRectDev(l, i, j);
  return [x / l.dpr, y / l.dpr, w / l.dpr, h / l.dpr];
}

// Device-pixel offset of a CSS coordinate from a gutter edge. CSS → device → CSS round trips are
// not exact in floating point (x / 2.625 * 2.625 ≠ x), so snap to 1e-6 device px first.
function devOffset(css: number, dpr: number, gutter: number): number {
  return Math.round((css * dpr - Math.round(gutter * dpr)) * 1e6) / 1e6 + 0; // + 0 turns -0 into 0
}

/**
 * The cell under a point given in CSS px relative to the canvas's top-left corner,
 * or null when the point is in a gutter or outside the grid.
 */
export function hitTest(l: GridLayout, x: number, y: number): { i: number; j: number } | null {
  const xd = devOffset(x, l.dpr, l.left);
  const yd = devOffset(y, l.dpr, l.top);
  if (xd < 0 || yd < 0) return null;
  const j = Math.floor(xd / l.cellDev);
  const i = Math.floor(yd / l.cellDev);
  if (i >= l.nR || j >= l.nC) return null;
  return { i, j };
}

/** Row header under a point in the left gutter (or null). */
export function hitRowHeader(l: GridLayout, x: number, y: number): number | null {
  if (x < 0 || x >= l.left) return null;
  const yd = devOffset(y, l.dpr, l.top);
  if (yd < 0) return null;
  const i = Math.floor(yd / l.cellDev);
  return i < l.nR ? i : null;
}

/** Column header under a point in the top gutter (or null). */
export function hitColHeader(l: GridLayout, x: number, y: number): number | null {
  if (y < 0 || y >= l.top) return null;
  const xd = devOffset(x, l.dpr, l.left);
  if (xd < 0) return null;
  const j = Math.floor(xd / l.cellDev);
  return j < l.nC ? j : null;
}
