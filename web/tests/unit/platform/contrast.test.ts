import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import * as style from "@/lib/sankey/style";

// PLAN §4.11: contrast is tested on what is drawn. Each kind hue is composited at
// each drawing opacity (imported from U3's lib/sankey/style.ts) over --bg and
// --surface, in both themes.
const css = fs.readFileSync(path.resolve(__dirname, "../../../src/styles/tokens.css"), "utf8");

function block(re: RegExp): Record<string, string> {
  const m = re.exec(css);
  if (!m) throw new Error(`token block not found: ${re}`);
  const out: Record<string, string> = {};
  for (const d of m[1].matchAll(/(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;/g)) out[d[1]] = d[2];
  return out;
}

const light = block(/^:root\s*\{([\s\S]*?)\n\}/m);
const darkMedia = block(/:root:not\(\[data-theme="light"\]\)\s*\{([\s\S]*?)\n {2}\}/);
const darkAttr = block(/:root\[data-theme="dark"\]\s*\{([\s\S]*?)\n\}/);
const themes = { light, dark: darkAttr } as const;

type RGB = [number, number, number];
const hex = (h: string): RGB => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)) as RGB;
const lin = (c: number) => {
  const s = c / 255;
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
};
const lum = ([r, g, b]: RGB) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
export function contrast(a: RGB, b: RGB): number {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}
const over = (fg: RGB, bg: RGB, alpha: number): RGB => fg.map((c, i) => Math.round(c * alpha + bg[i] * (1 - alpha))) as RGB;

const KINDS = ["production", "factors", "households", "corporations", "government", "row", "capital", "discrepancy"];
const STATUS = ["official", "derived", "estimated", "balancing"];

describe("tokens", () => {
  it("dark values are identical under the media query and under [data-theme=dark]", () => {
    expect(darkMedia).toEqual(darkAttr);
  });
  it("both themes define the same tokens", () => {
    const lightKeys = Object.keys(light).sort();
    for (const k of Object.keys(darkAttr)) expect(lightKeys).toContain(k);
    for (const k of [...KINDS.flatMap((k) => [`--k-${k}`, `--k-${k}-edge`, `--k-${k}-text`]), ...STATUS.map((s) => `--st-${s}`), "--pattern-line"])
      expect(light[k], k).toBeDefined();
  });
});

for (const [name, t] of Object.entries(themes)) {
  const bgs = { "--bg": hex(t["--bg"]), "--surface": hex(t["--surface"]) };
  describe(`${name} theme`, () => {
    it("text >= 4.5:1 on bg, surface and surface-2", () => {
      for (const fg of ["--text", "--text-muted", "--accent"]) {
        for (const bg of ["--bg", "--surface", "--surface-2"]) {
          expect(contrast(hex(t[fg]), hex(t[bg])), `${fg} on ${bg}`).toBeGreaterThanOrEqual(4.5);
        }
      }
      expect(contrast(hex(t["--accent-text"]), hex(t["--accent"])), "--accent-text on --accent").toBeGreaterThanOrEqual(4.5);
      expect(contrast(hex(t["--danger"]), hex(t["--surface"])), "--danger").toBeGreaterThanOrEqual(4.5);
    });
    it("focus ring and control borders >= 3:1", () => {
      for (const bg of Object.values(bgs)) {
        expect(contrast(hex(t["--focus"]), bg)).toBeGreaterThanOrEqual(3);
        expect(contrast(hex(t["--border-strong"]), bg)).toBeGreaterThanOrEqual(3);
      }
    });
    it("status colours >= 4.5:1 as text on bg, surface and their own badge background", () => {
      for (const s of STATUS) {
        for (const bg of [t["--bg"], t["--surface"], t[`--st-${s}-bg`]]) {
          expect(contrast(hex(t[`--st-${s}`]), hex(bg)), `--st-${s} on ${bg}`).toBeGreaterThanOrEqual(4.5);
        }
      }
    });
    it("kind -edge >= 3:1 and -text >= 4.5:1 against bg and surface", () => {
      for (const k of KINDS) {
        for (const [bn, bg] of Object.entries(bgs)) {
          expect(contrast(hex(t[`--k-${k}-edge`]), bg), `--k-${k}-edge on ${bn}`).toBeGreaterThanOrEqual(3);
          expect(contrast(hex(t[`--k-${k}-text`]), bg), `--k-${k}-text on ${bn}`).toBeGreaterThanOrEqual(4.5);
        }
      }
    });
    it("every drawn fill is >= 3:1 or carries a >= 3:1 edge stroke", () => {
      const opacities = {
        FORWARD_OPACITY: style.FORWARD_OPACITY,
        RETURN_OPACITY: style.RETURN_OPACITY,
        STUB_OPACITY: style.STUB_OPACITY,
        NODE_OPACITY: style.NODE_OPACITY,
      };
      expect(style.EDGE_STROKE_WIDTH).toBeGreaterThanOrEqual(1);
      for (const k of KINDS) {
        for (const [on, a] of Object.entries(opacities)) {
          for (const [bn, bg] of Object.entries(bgs)) {
            const fill = over(hex(t[`--k-${k}`]), bg, a);
            const ok = contrast(fill, bg) >= 3 || contrast(hex(t[`--k-${k}-edge`]), bg) >= 3;
            expect(ok, `${k} at ${on} on ${bn}`).toBe(true);
          }
        }
      }
    });
    it("label text >= 4.5:1 against its halo (--bg)", () => {
      for (const k of KINDS) expect(contrast(hex(t[`--k-${k}-text`]), hex(t["--bg"]))).toBeGreaterThanOrEqual(4.5);
      expect(contrast(hex(t["--text"]), hex(t["--bg"]))).toBeGreaterThanOrEqual(4.5);
    });
    it("the hatch line (--pattern-line) is >= 3:1 against every ribbon fill it is drawn on", () => {
      const line = hex(t["--pattern-line"]);
      for (const k of KINDS) {
        for (const a of [style.FORWARD_OPACITY, style.RETURN_OPACITY, style.STUB_OPACITY]) {
          for (const [bn, bg] of Object.entries(bgs)) {
            const fill = over(hex(t[`--k-${k}`]), bg, a);
            expect(contrast(line, fill), `hatch on ${k}@${a} over ${bn}`).toBeGreaterThanOrEqual(3);
          }
        }
      }
    });
  });
}
