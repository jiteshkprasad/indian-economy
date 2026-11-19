import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

// PLAN §4.12 and §6.5: every page.tsx and layout.tsx under src/app/[locale] calls
// setRequestLocale (and so does every generateMetadata); dynamic segments set
// dynamicParams = false. Without it the route turns dynamic and `output: export` fails.
const root = path.resolve(__dirname, "../../../src/app/[locale]");

function walk(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    return e.isDirectory() ? walk(p) : [p];
  });
}

const files = walk(root).filter((f) => /\/(page|layout)\.(t|j)sx?$/.test(f));

describe("static rendering pattern under src/app/[locale]", () => {
  it("finds the locale layout", () => {
    expect(files.some((f) => f.endsWith(`${path.sep}layout.tsx`))).toBe(true);
  });
  for (const f of files) {
    const rel = path.relative(root, f);
    const src = fs.readFileSync(f, "utf8");
    it(`${rel} calls setRequestLocale`, () => {
      expect(src).toMatch(/setRequestLocale\(/);
    });
    if (/export\s+(async\s+)?function\s+generateMetadata/.test(src)) {
      it(`${rel} generateMetadata calls setRequestLocale`, () => {
        const body = src.slice(src.search(/export\s+(async\s+)?function\s+generateMetadata/));
        const end = body.indexOf("\n}");
        expect(body.slice(0, end)).toMatch(/setRequestLocale\(/);
      });
    }
    const segs = rel.split(path.sep).filter((s) => /^\[.+\]$/.test(s));
    if (segs.length > 0 && /page\.(t|j)sx?$/.test(f)) {
      it(`${rel} (dynamic segment) sets dynamicParams = false and generateStaticParams`, () => {
        // the [locale] segment itself is covered by the locale layout
        const own = rel.split(path.sep).slice(0, -1).some((s) => /^\[.+\]$/.test(s));
        if (!own) return;
        const layoutOrPage = [f, path.join(path.dirname(f), "layout.tsx")].filter((p) => fs.existsSync(p)).map((p) => fs.readFileSync(p, "utf8")).join("\n");
        expect(layoutOrPage).toMatch(/export\s+const\s+dynamicParams\s*=\s*false/);
        expect(layoutOrPage).toMatch(/generateStaticParams/);
      });
    }
  }
});
