import { describe, expect, it } from "vitest";
import { layoutSankey } from "@/lib/sankey/layout";
import {
  balanceViolations,
  classViolations,
  laneNestingViolations,
  nanViolations,
  returnCrossings,
  throughNodeViolations,
  returnCrossingFloor,
} from "@/lib/sankey/invariants";
import { PX_PER_PCT_GDP } from "@/lib/sankey/style";
import type { LayoutOptions } from "@/lib/sankey/types";
import { makeSynthetic, synthLinks, synthNodes } from "./synthetic";

const S = makeSynthetic();
const opts = (returnFlows: "arcs" | "stubs"): LayoutOptions => ({ gdp: S.gdp, pxPerPct: PX_PER_PCT_GDP, returnFlows });

const STATES: Array<{ name: string; expanded: string[] }> = [
  { name: "level 0", expanded: [] },
  { name: "households and taxes expanded", expanded: ["H", "G"] },
  { name: "everything expanded", expanded: ["P", "A", "R", "F", "H", "C", "G", "S", "D"] },
];

function build(expanded: string[], rf: "arcs" | "stubs") {
  const { nodes, map } = synthNodes(expanded);
  return layoutSankey(nodes, synthLinks(S, map), opts(rf));
}

describe("unrolled Sankey layout: invariants on a synthetic balanced SAM", () => {
  for (const st of STATES) {
    for (const rf of ["arcs", "stubs"] as const) {
      describe(`${st.name}, return flows as ${rf}`, () => {
        const L = build(st.expanded, rf);
        it("has links of every class", () => {
          const classes = new Set(L.links.map((l) => l.cls));
          expect(classes.has("forward")).toBe(true);
          expect(classes.has("return")).toBe(true);
        });
        it("balances every node: drawn inflow = drawn outflow = height; ports fill the node", () => {
          expect(balanceViolations(L)).toEqual([]);
        });
        it("classes every link by the column rule", () => {
          expect(classViolations(L)).toEqual([]);
        });
        it("has no NaN coordinates", () => {
          expect(nanViolations(L)).toEqual([]);
        });
        it("routes no ribbon through a node that is not its endpoint", () => {
          expect(throughNodeViolations(L)).toEqual([]);
        });
        it("nests return lanes by span", () => {
          expect(laneNestingViolations(L)).toEqual([]);
        });
      });
    }
  }

  it("draws reversed links for negative parts and keeps balance", () => {
    const L = build([], "arcs");
    const neg = L.links.filter((l) => l.id.endsWith("~neg"));
    expect(neg.length).toBeGreaterThan(0);
    for (const l of neg) expect(l.reversed).toBe(true);
    expect(balanceViolations(L)).toEqual([]);
  });

  it("keeps a node's height when any other node is expanded", () => {
    const base = build([], "arcs");
    const h0 = new Map(base.nodes.map((n) => [n.key, n.h]));
    for (const g of ["P", "A", "F", "H", "C", "G", "S"]) {
      const L = build([g], "arcs");
      for (const n of L.nodes) {
        if (h0.has(n.key)) expect(Math.abs(n.h - h0.get(n.key)!)).toBeLessThan(0.01);
      }
    }
  });

  it("draws the split node twice with equal heights", () => {
    const L = build([], "arcs");
    const out = L.nodes.find((n) => n.key === "P@out")!;
    const inn = L.nodes.find((n) => n.key === "P@in")!;
    expect(out.col).toBe(0);
    expect(inn.col).toBe(6);
    expect(Math.abs(out.h - inn.h)).toBeLessThan(0.01);
  });

  it("has no return-lane crossings beyond the unavoidable ones (partially overlapping spans)", () => {
    for (const st of STATES) {
      const L = build(st.expanded, "arcs");
      expect(returnCrossings(L)).toBeLessThanOrEqual(returnCrossingFloor(L));
    }
  });

  it("is deterministic", () => {
    const a = build(["H"], "arcs");
    const b = build(["H"], "arcs");
    expect(JSON.stringify(a)).toBe(JSON.stringify(b));
  });

  it("does not draw links under the threshold but keeps their port space and counts them", () => {
    const { nodes, map } = synthNodes([]);
    const links = synthLinks(S, map);
    links.push({ id: "tiny-a", source: "F", target: "G", value: 0.01 });
    links.push({ id: "tiny-b", source: "F", target: "G", value: 0.02, reversed: true });
    const L = layoutSankey(nodes, links, opts("arcs"));
    const tiny = L.links.find((l) => l.id === "tiny-a")!;
    expect(tiny.drawn).toBe(false);
    expect(tiny.d).toBe("");
    expect(L.nodes.find((n) => n.key === "F")!.small.count).toBeGreaterThanOrEqual(2);
  });

  it("nests a laminar set of return arcs without any crossing", () => {
    const nodes = [0, 1, 2, 3, 4, 5].map((c) => ({ id: `n${c}`, col: c, order: c, kind: "k" }));
    const fwd = (a: number, b: number, v: number) => ({ id: `n${a}--n${b}`, source: `n${a}`, target: `n${b}`, value: v });
    // returns 5→0 (outer), 4→1, 3→2 (inner), each balanced by a forward chain
    const links = [
      fwd(0, 1, 300), fwd(1, 2, 300), fwd(2, 3, 300), fwd(3, 4, 300), fwd(4, 5, 100),
      fwd(5, 0, 100), fwd(4, 1, 100), fwd(3, 2, 100),
    ];
    const L = layoutSankey(nodes, links, { gdp: 1000, pxPerPct: 1, returnFlows: "arcs" });
    expect(L.links.filter((l) => l.cls === "return").length).toBe(3);
    expect(returnCrossings(L)).toBe(0);
    expect(throughNodeViolations(L)).toEqual([]);
  });
});

