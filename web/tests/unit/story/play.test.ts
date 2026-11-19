/**
 * Home page play data (round 3, 19 Nov 2026): every rupee-tour stop and every guessing-game
 * question points at a story step and figures that exist in the exported story JSON, each
 * question's answer sits inside its slider, and every stop and question has its wording.
 * Reads the same data root as the build: the real export when present, else the fixture.
 */
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { resolveDataRoot } from "@/data/root.mjs";
import type { DataIndex, Story } from "@/data/types";
import { closeness, displayValue, GUESSES, storedValue, TOURS } from "@/data/play";
import map from "@messages/en/map.json";

const WEB = path.resolve(import.meta.dirname, "../../..");

function storyJson(slug: string): Story {
  const r = resolveDataRoot(WEB) as { dir: string };
  const idx = JSON.parse(fs.readFileSync(path.join(r.dir, "index.json"), "utf8")) as DataIndex;
  return JSON.parse(fs.readFileSync(path.join(r.dir, idx.data_version, `stories/${slug}.json`), "utf8")) as Story;
}

const tour = map.tour as unknown as Record<string, Record<string, { before?: string; after?: string; middle?: string }>>;
const guess = map.guess as unknown as { q: Record<string, string>; why: Record<string, string> };

describe("rupee tour", () => {
  for (const t of TOURS) {
    const story = storyJson(t.slug);
    it(`${t.slug}: stops point at real steps and figures, with wording`, () => {
      expect(t.stops.length).toBeGreaterThan(0);
      for (const st of t.stops) {
        expect(story.steps.map((x) => x.id), `${t.slug} step`).toContain(st.step);
        expect(story.figures[st.fig], `${t.slug}.${st.fig}`).toBeTruthy();
        if (st.fig2) expect(story.figures[st.fig2], `${t.slug}.${st.fig2}`).toBeTruthy();
        const w = tour[t.slug]?.[st.step];
        expect(w?.before, `wording ${t.slug}.${st.step}`).toBeTypeOf("string");
        expect(w?.after, `wording ${t.slug}.${st.step}`).toBeTypeOf("string");
        if (st.fig2) expect(w?.middle, `middle ${t.slug}.${st.step}`).toBeTypeOf("string");
      }
    });
  }
});

describe("guessing game", () => {
  it("has unique ids", () => {
    expect(new Set(GUESSES.map((q) => q.id)).size).toBe(GUESSES.length);
  });
  for (const q of GUESSES) {
    it(`${q.id}: answer exists, fits the slider, has wording`, () => {
      const story = storyJson(q.slug);
      expect(story.steps.map((x) => x.id)).toContain(q.step);
      const f = story.figures[q.fig];
      expect(f, `${q.slug}.${q.fig}`).toBeTruthy();
      expect(["per100", "pct", "pct_gdp"]).toContain(f.unit);
      const a = displayValue(f.value, f.unit);
      expect(a).toBeGreaterThanOrEqual(q.min);
      expect(a).toBeLessThanOrEqual(q.max);
      expect(storedValue(a, f.unit)).toBeCloseTo(f.value, 10);
      expect(guess.q[q.id]).toBeTypeOf("string");
      expect(guess.why[q.id]).toBeTypeOf("string");
    });
  }
  it("scores closeness against the slider range", () => {
    const q = { min: 0, max: 100 };
    expect(closeness(66, 66.1, q)).toBe("spot");
    expect(closeness(58, 66.1, q)).toBe("close");
    expect(closeness(40, 66.1, q)).toBe("far");
  });
});
