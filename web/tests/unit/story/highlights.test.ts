import { describe, expect, it } from "vitest";
import type { StoryView } from "@/data/types";
import { highlightedLinks } from "@/lib/story/highlights";
import { miniCells, miniHierarchy } from "../platform/mini";

const view = (p: Partial<StoryView>): StoryView => ({
  view: "sam",
  preset: "simple",
  year: "2023-24",
  expanded: [],
  highlight: [],
  select: null,
  ...p,
});

describe("highlighted flows of a story step (PLAN §4.9)", () => {
  const cells = miniCells();
  const h = miniHierarchy();

  it("returns the highlighted links in the step's order with their aggregated values", () => {
    const r = highlightedLinks(cells, h, {}, view({ highlight: ["HH--PRODUCERS", "FACT--HH"] }));
    expect(r.missing).toEqual([]);
    expect(r.links.map((l) => l.id)).toEqual(["HH--PRODUCERS", "FACT--HH"]);
    // households buy 30 + 20 from producers; factors pay households 40 + 30 (mini data)
    expect(r.links[0].value).toBeCloseTo(50, 9);
    expect(r.links[1].value).toBeCloseTo(70, 9);
  });

  it("keeps a negative part separate (~neg) and signed", () => {
    const r = highlightedLinks(cells, h, {}, view({ preset: "full", highlight: ["TAX--PRDS~neg"] }));
    expect(r.missing).toEqual([]);
    expect(r.links).toHaveLength(1);
    expect(r.links[0].value).toBeLessThan(0);
  });

  it("follows the step's zoom: expanded nodes split into their children", () => {
    const r = highlightedLinks(cells, h, {}, view({ preset: "full", expanded: ["HH"], highlight: ["FACT--H_R1", "FACT--HH"] }));
    expect(r.links.map((l) => l.id)).toEqual(["FACT--H_R1"]);
    expect(r.links[0].value).toBeCloseTo(40, 9);
    expect(r.missing).toEqual(["FACT--HH"]); // reported, never silently dropped
  });

  it("skips node ids (they are highlighted on the map, not listed as flows)", () => {
    const r = highlightedLinks(cells, h, {}, view({ highlight: ["HH"] }));
    expect(r.links).toEqual([]);
    expect(r.missing).toEqual([]);
  });
});
