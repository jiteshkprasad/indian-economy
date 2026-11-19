/**
 * Completeness of web/content/en/map-text.json and map-desc.json (PLAN §3.9, §5.2 U6):
 * all 168 hierarchy nodes plus PRODUCERS and GOV; every level-0 link id of the full
 * and simple presets (positive and ~neg); every ref; every series. On the generated
 * fixture only the parts that do not depend on real values are checked, and the
 * rest prints "REAL-DATA ... NOT RUN" (never a silent pass).
 */
import { describe, expect, it } from "vitest";
import type { Hierarchy, Refs, Series } from "../../../src/data/types";
import { dataRoot, levelZeroLinkIds, loadMapDesc, loadMapText } from "./helpers";

const text = loadMapText();
const desc = loadMapDesc();
const data = dataRoot();
const hierarchy = data.read<Hierarchy>("hierarchy.json");

const SECTIONS = ["nodes", "links", "refs", "series"] as const;

function sorted(s: Iterable<string>): string[] {
  return [...s].sort();
}

describe("map-text.json and map-desc.json: shape", () => {
  it("every node has a non-empty label and short text", () => {
    for (const [id, v] of Object.entries(text.nodes)) {
      expect(typeof v.label, id).toBe("string");
      expect(v.label.trim().length, `${id} label`).toBeGreaterThan(0);
      expect(typeof v.short, id).toBe("string");
      expect(v.short.trim().length, `${id} short`).toBeGreaterThan(0);
    }
  });

  it("every link, ref and series has a non-empty label", () => {
    for (const sec of ["links", "refs", "series"] as const) {
      for (const [id, v] of Object.entries(text[sec])) {
        expect(typeof v.label, `${sec}.${id}`).toBe("string");
        expect(v.label.trim().length, `${sec}.${id}`).toBeGreaterThan(0);
      }
    }
  });

  it("every description is a non-empty string", () => {
    for (const sec of SECTIONS) {
      for (const [id, v] of Object.entries(desc[sec])) {
        expect(typeof v, `${sec}.${id}`).toBe("string");
        expect(v.trim().length, `${sec}.${id}`).toBeGreaterThan(0);
      }
    }
  });

  it("map-text and map-desc cover the same ids", () => {
    for (const sec of SECTIONS) {
      expect(sorted(Object.keys(desc[sec])), sec).toEqual(sorted(Object.keys(text[sec])));
    }
  });

  it("labels are unique within nodes of the same level (no two accounts read alike)", () => {
    const byLevel = new Map<number, Map<string, string>>();
    for (const n of hierarchy.nodes) {
      const label = text.nodes[n.id]?.label;
      if (!label) continue;
      const m = byLevel.get(n.level) ?? new Map<string, string>();
      // a single-account group repeats its account's label on purpose (e.g. CEN and G_CEN differ in level)
      expect(m.get(label), `level ${n.level}: "${label}" used by ${m.get(label)} and ${n.id}`).toBeUndefined();
      m.set(label, n.id);
      byLevel.set(n.level, m);
    }
  });
});

describe("map-text.json: coverage of nodes", () => {
  it("covers exactly the hierarchy nodes plus the preset and top-flows ids", () => {
    const expected = new Set<string>(hierarchy.nodes.map((n) => n.id));
    for (const p of Object.values(hierarchy.presets)) for (const id of Object.keys(p.merges)) expected.add(id);
    for (const n of hierarchy.ts_nodes) expected.add(n.id);
    expect(expected.has("PRODUCERS")).toBe(true);
    expect(expected.has("GOV")).toBe(true);
    expect(sorted(Object.keys(text.nodes))).toEqual(sorted(expected));
  });

  it("the hierarchy has the 168 nodes PLAN §3.2 promises", () => {
    expect(hierarchy.nodes.length).toBe(168);
  });
});

describe("map-text.json: coverage of level-0 links, refs and series", () => {
  if (!data.real) {
    it("REAL-DATA LINK, REF AND SERIES COVERAGE NOT RUN (fixture data)", () => {
      console.warn(
        `REAL-DATA LINK, REF AND SERIES COVERAGE NOT RUN: data root ${data.dir} is the fixture (${data.index.data_version}).`,
      );
      // On the fixture, still check that every link key is a well-formed id between preset nodes.
      const nodeIds = new Set<string>(hierarchy.nodes.filter((n) => n.level === 0).map((n) => n.id));
      for (const p of Object.values(hierarchy.presets)) for (const id of Object.keys(p.merges)) nodeIds.add(id);
      for (const id of Object.keys(text.links)) {
        const m = /^([A-Z]+)--([A-Z]+)(~neg)?$/.exec(id);
        expect(m, id).not.toBeNull();
        expect(nodeIds.has(m![1]), `${id}: payer`).toBe(true);
        expect(nodeIds.has(m![2]), `${id}: receiver`).toBe(true);
      }
    });
    return;
  }

  const cells = data.read<{ n: number; row: number[]; col: number[]; v: number[] }>("sam/cells.json");

  it("covers exactly the level-0 link ids of the full and simple presets", () => {
    const full = levelZeroLinkIds(hierarchy, cells, "full");
    const simple = levelZeroLinkIds(hierarchy, cells, "simple");
    const expected = new Set([...full, ...simple]);
    expect(sorted(Object.keys(text.links))).toEqual(sorted(expected));
  });

  it("covers exactly the refs in sam/refs.json", () => {
    const refs = data.read<Refs>("sam/refs.json");
    expect(sorted(Object.keys(text.refs))).toEqual(sorted(Object.keys(refs)));
  });

  it("covers exactly the series in ts/series.json", () => {
    const series = data.read<Series>("ts/series.json");
    expect(sorted(Object.keys(text.series))).toEqual(sorted(series.flows.map((f) => f.id)));
  });
});
