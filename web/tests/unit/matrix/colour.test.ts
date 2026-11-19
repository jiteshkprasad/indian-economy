import { describe, expect, it } from "vitest";
import {
  RAMPS,
  cellFill,
  contrast,
  logScale,
  parseCssColour,
  rampAt,
  scalePos,
  themeFromBackground,
  type Rgb,
} from "../../../src/lib/matrix/colour";

describe("log colour scale", () => {
  const s = logScale([1, 1e6]);

  it("is linear in log10(|v|)", () => {
    expect(scalePos(s, 1)).toBe(0);
    expect(scalePos(s, 1e6)).toBe(1);
    expect(scalePos(s, 1e3)).toBeCloseTo(0.5, 12);
    expect(scalePos(s, 1e2)).toBeCloseTo(1 / 3, 12);
  });

  it("uses |v|, so a negative cell sits at the same position as its absolute value", () => {
    expect(scalePos(s, -1e3)).toBe(scalePos(s, 1e3));
  });

  it("clamps outside the domain and handles a one-value domain", () => {
    expect(scalePos(s, 1e9)).toBe(1);
    expect(scalePos(s, 0.01)).toBe(0);
    expect(scalePos(logScale([5, 5]), 5)).toBe(1);
  });

  it("rejects a bad domain", () => {
    expect(() => logScale([0, 10])).toThrow();
    expect(() => logScale([10, 1])).toThrow();
    expect(() => logScale([1, Infinity])).toThrow();
  });

  it("is monotone: larger flows get darker fills in light mode and brighter in dark mode", () => {
    const lum = (c: Rgb) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
    let prevL = Infinity;
    let prevD = -Infinity;
    for (let e = 0; e <= 6; e++) {
      const l = lum(cellFill(RAMPS.light, s, 10 ** e, 1)!);
      const d = lum(cellFill(RAMPS.dark, s, 10 ** e, 1)!);
      expect(l).toBeLessThan(prevL);
      expect(d).toBeGreaterThan(prevD);
      prevL = l;
      prevD = d;
    }
  });
});

describe("negative hue", () => {
  const s = logScale([1, 1e6]);
  for (const theme of ["light", "dark"] as const) {
    it(`negative cells use a different hue from positive cells (${theme})`, () => {
      for (const v of [1, 1e3, 1e6]) {
        const p = cellFill(RAMPS[theme], s, v, 1)!;
        const n = cellFill(RAMPS[theme], s, -v, 1)!;
        expect(n).not.toEqual(p);
        // positive ramp is green-blue (green or blue beats red); negative is orange-red (red leads)
        expect(Math.max(p[1], p[2])).toBeGreaterThan(p[0]);
        expect(n[0]).toBeGreaterThan(n[2]);
        expect(n[0]).toBeGreaterThanOrEqual(n[1]);
      }
    });
  }

  it("empty blocks draw nothing; blocks whose cells cancel draw the zero-net grey", () => {
    expect(cellFill(RAMPS.light, s, 0, 0)).toBeNull();
    expect(cellFill(RAMPS.light, s, 0, 3)).toEqual(RAMPS.light.zeroNet);
  });
});

describe("ramp helpers", () => {
  it("interpolates between stops and hits the ends exactly", () => {
    const stops: Rgb[] = [
      [0, 0, 0],
      [100, 200, 50],
    ];
    expect(rampAt(stops, 0)).toEqual([0, 0, 0]);
    expect(rampAt(stops, 1)).toEqual([100, 200, 50]);
    expect(rampAt(stops, 0.5)).toEqual([50, 100, 25]);
    expect(rampAt(stops, Number.NaN)).toEqual([0, 0, 0]);
  });

  it("the smallest non-zero fill stays visible against the page background", () => {
    expect(contrast(RAMPS.light.pos[0], [255, 255, 255])).toBeGreaterThan(1.15);
    expect(contrast(RAMPS.dark.pos[0], [17, 17, 17])).toBeGreaterThan(1.3);
  });

  it("parses computed colours and picks the theme from the background", () => {
    expect(parseCssColour("rgb(17, 18, 19)")).toEqual([17, 18, 19]);
    expect(parseCssColour("rgba(1, 2, 3, 0.5)")).toEqual([1, 2, 3]);
    expect(parseCssColour("#ffffff")).toEqual([255, 255, 255]);
    expect(parseCssColour("#fff")).toEqual([255, 255, 255]);
    expect(parseCssColour("transparent")).toBeNull();
    expect(themeFromBackground([255, 255, 255])).toBe("light");
    expect(themeFromBackground([18, 18, 18])).toBe("dark");
    expect(themeFromBackground(null)).toBe("light");
  });
});
