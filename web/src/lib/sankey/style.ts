/**
 * Drawing constants of the Map (PLAN §4.5, §4.11). `tests/unit/platform/contrast.test.ts` (U2)
 * imports the opacity constants and composites each kind hue at each opacity over the page
 * background, so what is tested is what is drawn.
 */

/** Opacity of a forward ribbon's fill. */
export const FORWARD_OPACITY = 0.55;
/** Opacity of a return arc or a same-column side arc (drawn lighter so forward bands read first). */
export const RETURN_OPACITY = 0.35;
/** Opacity of a ribbon that is not highlighted while something else is. */
export const DIMMED_OPACITY = 0.12;
/** Opacity of a return-flow stub. */
export const STUB_OPACITY = 0.55;
/** Opacity of a node rectangle. */
export const NODE_OPACITY = 1;

/**
 * Every ribbon, arc and stub carries a 1-unit edge stroke in its kind's `-edge` colour, so a fill
 * below 3:1 against the background is always outlined by a ≥ 3:1 edge (PLAN §4.11).
 */
export const EDGE_STROKE_WIDTH = 1;
/** Label halo width (paint-order: stroke) in the page background colour. */
export const LABEL_HALO_WIDTH = 3;

/** Width scale: drawing units per 1% of GDP, shared by the SAM view and the top-flows board. */
export const PX_PER_PCT_GDP = 3;
/** Links narrower than this (drawing units) are not drawn; their port space is kept (§4.5.8). */
export const MIN_DRAW_PX = 0.5;
/** Ribbons narrower than this cannot show a hatch; their label carries the status (§4.5.11). */
export const MIN_PATTERN_PX = 6;

export const GEOMETRY = {
  nodeWidth: 16,
  /** Minimum horizontal room between two columns (for the forward ribbons' curves). */
  minColGap: 132,
  marginX: 24,
  marginTop: 8,
  /** Room above each node for its label. */
  labelSpace: 22,
  /** Space between two bands sharing a gutter, a lane, or a vertical channel. */
  bandPad: 2,
  /** Distance between a column's edge and its first vertical channel. */
  channelInset: 6,
  /** Space under the lowest node before the first return lane. */
  laneTop: 28,
  bottomPad: 16,
  stubLength: 22,
  /** Minimum drawn node height so a node with tiny flows stays visible. */
  minNodeH: 2,
} as const;

/** Visible-link guard (PLAN §4.5.9): above this the UI asks the user to collapse or use the matrix. */
export const MAX_LINKS_DESKTOP = 400;
export const MAX_LINKS_PHONE = 60;
/** Below this viewport width the phone view replaces the Sankey. */
export const PHONE_BREAKPOINT = 640;
