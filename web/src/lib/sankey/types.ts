/**
 * Types of the unrolled circular Sankey layout (PLAN §4.5). The layout is a pure function of its
 * inputs: no DOM, no randomness, no dependence on iteration order of hash maps.
 */

export type Pt = { x: number; y: number };

/** A node to lay out. A split node is drawn twice: its payer copy in `col`, its receiver copy in `inCol`. */
export type LayoutNodeInput = {
  id: string;
  col: number;
  /** Receiver column for the split node only (PLAN §4.5.1). */
  inCol?: number;
  /** Global vertical order (hierarchy `order`); fixed for every zoom state and year. */
  order: number;
  kind: string;
};

/**
 * A drawn link. `source` → `target` is the DRAWN direction: for a positive part it is payer →
 * receiver; for a negative part (`~neg`) it is receiver → payer (reversed, PLAN §4.5.4).
 */
export type LayoutLinkInput = {
  id: string;
  source: string;
  target: string;
  /** Absolute value in ₹ crore; sets the drawn width. */
  value: number;
  /**
   * Absolute value in ₹ crore used to reserve space in gutters, ports and lanes (top-flows board:
   * the maximum over all years, so nothing moves while scrubbing). Defaults to `value`.
   */
  reserve?: number;
  reversed?: boolean;
};

export type LayoutOptions = {
  /** GDP in ₹ crore: widths are a share of GDP (PLAN §4.5.3). */
  gdp: number;
  /** Drawing units per 1% of GDP: one constant for every view and zoom state. */
  pxPerPct: number;
  returnFlows: "stubs" | "arcs";
  /**
   * Fixed node heights in drawing units (top-flows board slots, PLAN §4.6). When given, ports are
   * stacked from the top of the slot and the node height is the slot, not the flow sum.
   */
  fixedHeights?: Record<string, number>;
  /** Ports and gutter slots are reserved with `reserve` widths (top-flows board). */
  reservePorts?: boolean;
};

export type LinkClass = "forward" | "same" | "return";

export type NodeBox = {
  /** `id` for ordinary nodes; `id@out` / `id@in` for the two copies of the split node. */
  key: string;
  id: string;
  copy: "only" | "out" | "in";
  col: number;
  order: number;
  kind: string;
  x: number;
  y: number;
  w: number;
  /** Height in drawing units = Σ drawn inflow widths = Σ drawn outflow widths (SAM view). */
  h: number;
  /** Σ widths of links entering on the left side (includes links too small to draw). */
  inSum: number;
  /** Σ widths of links leaving on the right side. */
  outSum: number;
  /** Links into or out of this node narrower than the drawing threshold (PLAN §4.5.8). */
  small: { count: number; value: number };
};

export type Port = { y0: number; y1: number };

export type Station = { x0: number; x1: number; y: number; col: number; gap: number };

export type LaidLink = {
  id: string;
  source: string;
  target: string;
  sourceKey: string;
  targetKey: string;
  cls: LinkClass;
  reversed: boolean;
  value: number;
  /** Drawn width in drawing units. */
  width: number;
  /** Reserved width (≥ width). */
  reserve: number;
  /** False when narrower than the threshold: the port is reserved but nothing is drawn. */
  drawn: boolean;
  /** Return or same-column link drawn as two labelled stubs (simple preset). */
  stub: boolean;
  sPort: Port;
  tPort: Port;
  /** Forward links: where the band passes intermediate columns (gutters). */
  stations: Station[];
  /** Return and same-column links: the centreline (orthogonal polyline). */
  route: Pt[];
  /** Return links in arc mode: lane index (0 = innermost). */
  lane: number | null;
  /** SVG path data of the filled shape (ribbon, arc outline or the two stubs). */
  d: string;
};

export type Layout = {
  nodes: NodeBox[];
  links: LaidLink[];
  width: number;
  height: number;
  /** Bottom of the node area; return lanes run below it. */
  diagramBottom: number;
  /** Node keys per column, top to bottom. */
  columns: string[][];
  colX: number[];
  /** Drawing units per ₹ crore. */
  unit: number;
  options: LayoutOptions;
};
