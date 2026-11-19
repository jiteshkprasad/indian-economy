// Colour scale for the SAM heat-map (PLAN §4.8): a sequential scale on log10(|v|), with a
// separate hue for negative cells, in a light and a dark variant. Pure functions; the component
// picks the theme from the resolved page background.

export type Rgb = readonly [number, number, number];
export type Theme = "light" | "dark";

export interface Ramp {
  pos: readonly Rgb[];
  neg: readonly Rgb[];
  /** Fill for a block whose cells net to exactly zero (it has flows, but they cancel). */
  zeroNet: Rgb;
}

const hex = (h: string): Rgb => {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};

// Light: small flows are pale, large flows dark. Positive = green-blue, negative = orange-red.
// Dark: small flows are dim, large flows bright. The low ends stay visibly different from the
// page background so that a tiny non-zero cell is never mistaken for an empty one.
export const RAMPS: Record<Theme, Ramp> = {
  light: {
    pos: ["#c7e9b4", "#7fcdbb", "#41b6c4", "#2c7fb8", "#253494", "#081d58"].map(hex),
    neg: ["#fdd0a2", "#fdae6b", "#f16913", "#d94801", "#a63603", "#6b1d02"].map(hex),
    zeroNet: hex("#9e9e9e"),
  },
  dark: {
    pos: ["#16384a", "#1d5c7a", "#2a86a6", "#41b6c4", "#8fd8c4", "#e8f7b0"].map(hex),
    neg: ["#4a1a08", "#7a2a0e", "#b5461a", "#e0692b", "#f59a5c", "#ffd2a8"].map(hex),
    zeroNet: hex("#7a7a7a"),
  },
};

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

/** Colour at position t ∈ [0, 1] along a ramp (piecewise linear in sRGB). */
export function rampAt(stops: readonly Rgb[], t: number): Rgb {
  if (!(t >= 0)) t = 0;
  if (t > 1) t = 1;
  const x = t * (stops.length - 1);
  const k = Math.min(Math.floor(x), stops.length - 2);
  const f = x - k;
  const a = stops[k];
  const b = stops[k + 1];
  return [
    Math.round(lerp(a[0], b[0], f)),
    Math.round(lerp(a[1], b[1], f)),
    Math.round(lerp(a[2], b[2], f)),
  ];
}

export interface LogScale {
  lo: number; // log10 of the smallest |v|
  hi: number; // log10 of the largest |v|
}

/** Build the log scale from the [min, max] of non-zero |v| in the current view. */
export function logScale(domain: [number, number]): LogScale {
  const [a, b] = domain;
  if (!(a > 0) || !(b >= a) || !Number.isFinite(b)) {
    throw new Error(`matrix colour: bad domain [${a}, ${b}]`);
  }
  return { lo: Math.log10(a), hi: Math.log10(b) };
}

/** Position of |v| on the scale, in [0, 1]. A single-value domain maps to the top. */
export function scalePos(s: LogScale, v: number): number {
  const a = Math.abs(v);
  if (!(a > 0)) return 0;
  if (s.hi === s.lo) return 1;
  const t = (Math.log10(a) - s.lo) / (s.hi - s.lo);
  return t < 0 ? 0 : t > 1 ? 1 : t;
}

/**
 * Fill for a block cell: null when it has no account cells (draw nothing), the zero-net grey when
 * its cells cancel exactly, otherwise the positive or negative ramp at the cell's log position.
 */
export function cellFill(ramp: Ramp, s: LogScale, v: number, nCells: number): Rgb | null {
  if (nCells === 0) return null;
  if (v === 0) return ramp.zeroNet;
  return rampAt(v > 0 ? ramp.pos : ramp.neg, scalePos(s, v));
}

export const rgbCss = (c: Rgb) => `rgb(${c[0]}, ${c[1]}, ${c[2]})`;

/** WCAG relative luminance of an sRGB colour. */
export function luminance(c: Rgb): number {
  const ch = (x: number) => {
    const s = x / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2]);
}

export function contrast(a: Rgb, b: Rgb): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/** Parse a computed CSS colour ("rgb(r, g, b)", "rgba(...)", "#rrggbb" or "#rgb"); null if unknown. */
export function parseCssColour(s: string): Rgb | null {
  const t = s.trim();
  const m = /^rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)/i.exec(t);
  if (m) return [Math.round(+m[1]), Math.round(+m[2]), Math.round(+m[3])];
  if (/^#[0-9a-f]{6}$/i.test(t)) return hex(t);
  if (/^#[0-9a-f]{3}$/i.test(t)) return hex(`#${t[1]}${t[1]}${t[2]}${t[2]}${t[3]}${t[3]}`);
  return null;
}

/** Light or dark ramp from the page background colour. */
export function themeFromBackground(bg: Rgb | null): Theme {
  return bg !== null && luminance(bg) < 0.2 ? "dark" : "light";
}

/** Text colour (black or white) with the better contrast on a fill, for in-cell labels. */
export function inkOn(fill: Rgb): Rgb {
  return contrast(fill, [0, 0, 0]) >= contrast(fill, [255, 255, 255]) ? [0, 0, 0] : [255, 255, 255];
}
