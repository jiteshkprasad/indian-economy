import { describe, expect, it } from "vitest";
import {
  balanceViolations,
  classViolations,
  laneNestingViolations,
  nanViolations,
  returnCrossingFloor,
  returnCrossings,
  throughNodeViolations,
} from "@/lib/sankey/invariants";
import { buildSamModel } from "@/lib/sankey/model";
import { fixtureData, realData, type MapTestData } from "./data";

/** Level-0 split nodes: their two copies are equal (children of PRDS differ by the margins inside it). */
const SPLIT_L0 = new Set(["PRDS", "PRODUCERS"]);

type State = { name: string; preset: "simple" | "full"; expanded: string[]; rf: "stubs" | "arcs" };

const STATES: State[] = [
  { name: "simple, stubs (the default)", preset: "simple", expanded: [], rf: "stubs" },
  { name: "simple, arcs", preset: "simple", expanded: [], rf: "arcs" },
  { name: "full, level 0", preset: "full", expanded: [], rf: "arcs" },
  { name: "full, households and taxes", preset: "full", expanded: ["HH", "TAX"], rf: "arcs" },
  { name: "full, mixed zoom to accounts", preset: "full", expanded: ["HH", "HH.RUR", "PRDS", "PRDS.MANU", "FINM"], rf: "arcs" },
  { name: "full, every group at level 1", preset: "full", expanded: ["PRDS", "PROD", "FACT", "HH", "TAX", "SI", "FINM"], rf: "arcs" },
];

function model(d: MapTestData, s: State) {
  return buildSamModel(
    { hierarchy: d.hierarchy, cells: d.cells, pinned: d.pinned, gdp: d.summary.gdp.value },
    s.preset,
    s.expanded,
    s.rf,
  );
}

function invariants(d: MapTestData) {
  describe(`SAM map invariants: ${d.label}`, () => {
    for (const st of STATES) {
      describe(st.name, () => {
        const m = model(d, st);
        const L = m.layout;
        it("balances every node (Σ drawn in = Σ drawn out = height), ports fill the node, split copies equal", () => {
          expect(balanceViolations(L, false, SPLIT_L0)).toEqual([]);
        });
        it("classes every link forward / same-column / return by the column rule", () => {
          expect(classViolations(L)).toEqual([]);
        });
        it("has no NaN coordinates", () => {
          expect(nanViolations(L)).toEqual([]);
        });
        it("routes no ribbon through a node that is not its endpoint", () => {
          expect(throughNodeViolations(L)).toEqual([]);
        });
        it("nests return lanes by span, with no crossings beyond the unavoidable floor", () => {
          expect(laneNestingViolations(L)).toEqual([]);
          expect(returnCrossings(L)).toBeLessThanOrEqual(returnCrossingFloor(L));
        });
        it("draws negative parts reversed", () => {
          for (const l of L.links) expect(l.reversed).toBe(l.id.endsWith("~neg"));
        });
      });
    }

    it("keeps a node's height when another node is expanded", () => {
      const base = model(d, STATES[2]);
      const h0 = new Map(base.layout.nodes.map((n) => [n.key, n.h]));
      for (const g of ["PRDS", "PROD", "FACT", "HH", "TAX", "SI", "FINM"]) {
        const m = model(d, { name: g, preset: "full", expanded: [g], rf: "arcs" });
        for (const n of m.layout.nodes) if (h0.has(n.key)) expect(Math.abs(n.h - h0.get(n.key)!), `${n.key} with ${g} open`).toBeLessThan(0.01);
      }
    });

    it("draws the split node twice with equal heights in both presets", () => {
      for (const st of [STATES[0], STATES[2]]) {
        const L = model(d, st).layout;
        const out = L.nodes.filter((n) => n.copy === "out");
        expect(out.length).toBe(1);
        const inn = L.nodes.find((n) => n.key === `${out[0].id}@in`)!;
        expect(Math.abs(out[0].h - inn.h)).toBeLessThan(0.01);
        expect(inn.col).toBeGreaterThan(out[0].col);
      }
    });

    it("uses one width scale (share of GDP) in every zoom state", () => {
      const units = STATES.map((s) => model(d, s).layout.unit);
      for (const u of units) expect(u).toBe(units[0]);
    });
  });
}

const fx = fixtureData();
invariants(fx);
const real = realData();
if (real) invariants(real);
else it.skip("REAL-DATA INVARIANTS NOT RUN", () => {});

describe("SAM map on the fixture: coordinate snapshots", () => {
  for (const st of STATES) {
    it(st.name, () => {
      const L = model(fx, st).layout;
      const r = (n: number) => Math.round(n * 100) / 100;
      const nodes = L.nodes.map((n) => [n.key, r(n.x), r(n.y), r(n.h)]);
      const links = L.links.map((l) => [l.id, l.cls, l.drawn, l.stub, r(l.width), r(l.sPort.y0), r(l.tPort.y0), l.lane]);
      expect({ size: [r(L.width), r(L.height)], nodes, links }).toMatchSnapshot();
      // identical across runs
      expect(JSON.stringify(model(fx, st).layout)).toBe(JSON.stringify(L));
    });
  }
});

describe("real-data figures the map must reproduce (PLAN §3.2)", () => {
  if (!real) {
    it.skip("REAL-DATA INVARIANTS NOT RUN", () => {});
    return;
  }
  const lakh = 1e5;
  it("full preset: node heights in ₹ lakh crore", () => {
    const m = model(real, STATES[2]);
    const h = new Map<string, number>();
    for (const n of m.layout.nodes) h.set(n.id, Math.max(h.get(n.id) ?? 0, n.h / m.layout.unit / lakh));
    const want: Record<string, number> = { PRDS: 677.82, PROD: 578.51, FACT: 265.25, SI: 249.97, HH: 245.74, FINM: 145.39, ROW: 80.15, NFC: 64.27, TAX: 60.7, CEN: 43.8, FC: 41.78, STA: 38.79, DISC: 5.71 };
    for (const [id, v] of Object.entries(want)) expect(Math.abs(h.get(id)! - v), id).toBeLessThan(0.01);
  });
  it("link counts: full 70 (61 + 9 negative), simple 61", () => {
    const full = model(real, STATES[2]);
    expect(full.links.length).toBe(70);
    expect(full.links.filter((l) => l.part === "neg").length).toBe(9);
    expect(model(real, STATES[0]).links.length).toBe(61);
  });
  it("simple preset: PRODUCERS is 369.09 lakh crore on both copies", () => {
    const L = model(real, STATES[0]).layout;
    for (const n of L.nodes.filter((x) => x.id === "PRODUCERS")) expect(Math.abs(n.h / L.unit / lakh - 369.09)).toBeLessThan(0.01);
  });
});
