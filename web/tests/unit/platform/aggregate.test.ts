import { describe, expect, it } from "vitest";
import { aggregate, nodeFlows, normaliseExpanded, visibleNodes } from "@/data/aggregate";
import { ACCOUNTS, CELLS, miniCells, miniHierarchy } from "./mini";

const h = miniHierarchy();
const cells = miniCells();
const pinned = {
  "HH--PRODUCERS": { total: "official" as const, pins: ["ts:F01"] },
  "TAX--PRODUCERS~pair": { total: "official" as const, pins: ["m07"] },
};

function byId(links: ReturnType<typeof aggregate>["links"]) {
  return Object.fromEntries(links.map((l) => [l.id, l]));
}

describe("visibleNodes", () => {
  it("simple preset merges PRDS+PROD into PRODUCERS and FINM into SI", () => {
    const v = visibleNodes(h, "simple");
    expect(v.preset).toBe("simple");
    expect(v.ids).toEqual(["PRODUCERS", "FACT", "HH", "TAX", "SI"]);
    expect(v.members.PRODUCERS.sort()).toEqual(["A_A", "C_A", "C_B", "M_TTM"]);
    expect(v.members.SI.sort()).toEqual(["I_DEPO", "K_HH"]);
  });
  it("full preset is level 0", () => {
    expect(visibleNodes(h, "full").ids).toEqual(["PRDS", "PROD", "FACT", "HH", "TAX", "SI", "FINM"]);
  });
  it("expanding switches to full and replaces the node by its children in place", () => {
    const v = visibleNodes(h, "simple", ["HH"]);
    expect(v.preset).toBe("full");
    expect(v.ids).toEqual(["PRDS", "PROD", "FACT", "H_R1", "H_U1", "TAX", "SI", "FINM"]);
  });
  it("expanding a level-1 node implies its parent", () => {
    expect(normaliseExpanded(h, ["PRDS.X"])).toEqual(["PRDS", "PRDS.X"]);
    expect(visibleNodes(h, "full", ["PRDS.X"]).ids.slice(0, 3)).toEqual(["C_A", "C_B", "M_TTM"]);
  });
  it("every account maps to exactly one visible node", () => {
    for (const ex of [[], ["HH"], ["PRDS", "PRDS.X", "HH"]]) {
      const v = visibleNodes(h, "full", ex);
      expect(v.accountToNode).toHaveLength(ACCOUNTS.length);
      expect(v.accountToNode.every((x) => typeof x === "string")).toBe(true);
    }
  });
});

describe("aggregate", () => {
  it("simple preset: positive and negative parts, pins and pair pins", () => {
    const a = aggregate(cells, h, visibleNodes(h, "simple"), pinned);
    const L = byId(a.links);
    expect(Object.keys(L).sort()).toEqual(
      ["FACT--HH", "HH--PRODUCERS", "HH--SI", "HH--TAX", "PRODUCERS--FACT", "SI--PRODUCERS", "TAX--PRODUCERS", "TAX--PRODUCERS~neg"].sort(),
    );
    expect(L["HH--PRODUCERS"].value).toBe(50);
    expect(L["HH--PRODUCERS"].total).toBe("official");
    expect(L["HH--PRODUCERS"].pins).toEqual(["ts:F01"]);
    expect(L["TAX--PRODUCERS"].value).toBe(7);
    expect(L["TAX--PRODUCERS~neg"].value).toBe(-2);
    expect(L["TAX--PRODUCERS~neg"].part).toBe("neg");
    expect(L["TAX--PRODUCERS~neg"].total).toBeNull();
    expect(L["TAX--PRODUCERS~neg"].pair?.pins).toEqual(["m07"]);
    expect(L["SI--PRODUCERS"].value).toBe(15);
    expect(L["HH--SI"].value).toBe(15);
  });
  it("flags are OR'd and the split label follows the composition", () => {
    const L = byId(aggregate(cells, h, visibleNodes(h, "simple")).links);
    expect(L["TAX--PRODUCERS~neg"].flags & 32).toBe(32);
    expect(L["HH--SI"].flags & 2).toBe(2);
    // HH--SI: 5 estimated + 10 set by balancing -> balancing carries >= 10%
    expect(L["HH--SI"].split).toBe("balancing_set");
    expect(L["HH--PRODUCERS"].split).toBe("estimated");
    expect(L["FACT--HH"].split).toBe("official");
    expect(L["HH--SI"].composition!.b).toBeCloseTo(10 / 15, 12);
  });
  it("internal flows: the whole producer loop in simple, margins inside PRDS at every zoom", () => {
    const simple = aggregate(cells, h, visibleNodes(h, "simple"));
    expect(simple.internal.PRODUCERS.pos).toBe(5 + 5 + 62 + 38 + 30);
    expect(simple.internal.SI.pos).toBe(5);
    const full = aggregate(cells, h, visibleNodes(h, "full"));
    expect(full.internal.PRDS.pos).toBe(10);
    const deep = aggregate(cells, h, visibleNodes(h, "full", ["PRDS.X"]));
    expect(deep.internal.PRDS.pos).toBe(10);
    expect(deep.links.some((l) => l.payer === "M_TTM" || l.receiver === "M_TTM")).toBe(false);
  });
  it("conserves value: links + internal = all cells, at every zoom", () => {
    const total = CELLS.reduce((s, [, , v]) => s + v, 0);
    for (const [p, ex] of [
      ["simple", []],
      ["full", []],
      ["full", ["HH"]],
      ["full", ["PRDS.X", "HH"]],
    ] as const) {
      const a = aggregate(cells, h, visibleNodes(h, p, ex));
      const sum = a.links.reduce((s, l) => s + l.value, 0) + Object.values(a.internal).reduce((s, i) => s + i.pos + i.neg, 0);
      expect(sum).toBeCloseTo(total, 9);
      expect(a.links.reduce((s, l) => s + l.n_cells, 0) + Object.values(a.internal).reduce((s, i) => s + i.cells.length, 0)).toBe(CELLS.length);
    }
  });
  it("drawn inflow equals drawn outflow for every node (balanced SAM), independent of other nodes' zoom", () => {
    const heights = (ex: string[]) => {
      const f = nodeFlows(aggregate(cells, h, visibleNodes(h, "full", ex)).links);
      for (const [id, x] of Object.entries(f)) expect(x.inflow, id).toBeCloseTo(x.outflow, 9);
      return f;
    };
    const base = heights([]);
    const zoomed = heights(["HH"]);
    for (const id of ["PROD", "FACT", "TAX", "SI", "FINM"]) expect(zoomed[id].inflow).toBeCloseTo(base[id].inflow, 9);
    const simple = nodeFlows(aggregate(cells, h, visibleNodes(h, "simple")).links);
    expect(simple.PRODUCERS.inflow).toBe(72);
    expect(simple.PRODUCERS.outflow).toBe(72);
    expect(simple.TAX.inflow).toBe(7);
  });
  it("is deterministic and ordered by payer, receiver, then pos before neg", () => {
    const a = aggregate(cells, h, visibleNodes(h, "simple"));
    const b = aggregate(cells, h, visibleNodes(h, "simple"));
    expect(a).toEqual(b);
    const ids = a.links.map((l) => l.id);
    expect(ids.indexOf("TAX--PRODUCERS")).toBe(ids.indexOf("TAX--PRODUCERS~neg") - 1);
    expect(ids[0]).toBe("PRODUCERS--FACT");
  });
});
