import { describe, expect, it } from "vitest";
import { collapseState, expandState, fyRange, keepYear } from "@/components/map/state";
import fs from "node:fs";
import path from "node:path";
import { composeText, discKeyOf, samPointOf } from "@/components/map/panel-text";
import { formatPct } from "@/lib/format";
import type { Entry } from "@/data/types";
import { buildSamModel } from "@/lib/sankey/model";
import { resolveLink, resolveNode } from "@/lib/sankey/select";
import { classify, matchSeries } from "@/lib/ts-board/match";
import { DEFAULT_STATE } from "@/lib/url-state";
import { fixtureData, realData } from "./data";

describe("trend matching (PLAN §3.7.4)", () => {
  it("classifies by the inside / covers table, including the 50–95% overlap tier", () => {
    expect(classify(1, 1)).toBe("trend");
    expect(classify(0.95, 0.995)).toBe("trend");
    expect(classify(0.96, 0.9)).toBe("related");
    expect(classify(0.949, 1)).toBe("overlap");
    expect(classify(0.5, 0.2)).toBe("overlap");
    expect(classify(0.499, 1)).toBeNull();
  });

  it("computes inside and covers from absolute covered cells", () => {
    const cells = { n: 3, row: [0, 1, 2], col: [5, 5, 5], v: [60, -20, 20] } as never;
    const cover = {
      A: { cells: [[0, 5, 60], [1, 5, -20]] as Array<[number, number, number]>, abs_total: 80 }, // all inside, covers 80/100
      B: { cells: [[0, 5, 60], [9, 9, 40]] as Array<[number, number, number]>, abs_total: 100 }, // 60% inside
      C: { cells: [[9, 9, 10]] as Array<[number, number, number]>, abs_total: 10 }, // outside
    };
    const m = matchSeries(cells, [0, 1, 2], cover);
    expect(m.map((x) => [x.flow, x.kind])).toEqual([
      ["A", "related"],
      ["B", "overlap"],
    ]);
    expect(m[0].inside).toBe(1);
    expect(m[0].covers).toBeCloseTo(0.8, 12);
    expect(m[1].inside).toBeCloseTo(0.6, 12);
    expect(m[1].rest).toEqual([[9, 9, 40]]);
  });

  const real = realData();
  it.runIf(!!real)("real data: household consumption is the F01 trend; Centre→States grants overlap F24", () => {
    const d = real!;
    const hh = resolveLink(d.hierarchy, d.cells, d.pinned, "HH--PRDS")!;
    expect(matchSeries(d.cells, hh.link.cells, d.cover)[0]).toMatchObject({ flow: "F01", kind: "trend" });
    const grants = resolveLink(d.hierarchy, d.cells, d.pinned, "CEN--STA")!;
    const f24 = matchSeries(d.cells, grants.link.cells, d.cover).find((x) => x.flow === "F24");
    expect(f24?.kind).toBe("overlap");
  });
});

describe("selection (any zoom) matches the map's aggregation", () => {
  const d = fixtureData();
  it("resolves level-0, mixed-zoom and preset ids, and rejects unknown ones", () => {
    expect(resolveLink(d.hierarchy, d.cells, d.pinned, "HH--PRDS")?.link.value).toBeGreaterThan(0);
    expect(resolveLink(d.hierarchy, d.cells, d.pinned, "HH--PRODUCERS")?.link.value).toBeGreaterThan(0);
    expect(resolveLink(d.hierarchy, d.cells, d.pinned, "H_R1--PRDS")?.link.value).toBeGreaterThan(0);
    expect(resolveLink(d.hierarchy, d.cells, d.pinned, "NOPE--PRDS")).toBeNull();
    expect(resolveLink(d.hierarchy, d.cells, d.pinned, "HH--HH.RUR")).toBeNull();
  });
  it("lists a node's partners by group: siblings, ancestors' siblings, then level-0 groups", () => {
    const n = resolveNode(d.hierarchy, d.cells, d.pinned, "HH.RUR")!;
    const partners = new Set([...n.moneyIn.map((l) => l.payer), ...n.moneyOut.map((l) => l.receiver)]);
    expect(partners.size).toBeGreaterThan(2);
    // never its own ancestor (a group that contains it) and never an unnamed remainder
    expect(partners.has("HH")).toBe(false);
    expect([...partners].some((p) => p.startsWith("__"))).toBe(false);
  });
  it("a node's drawn height = positive receipts + |negative payments|", () => {
    const n = resolveNode(d.hierarchy, d.cells, d.pinned, "CEN")!;
    const pos = n.moneyIn.filter((l) => l.part === "pos").reduce((a, l) => a + l.value, 0);
    const neg = n.moneyOut.filter((l) => l.part === "neg").reduce((a, l) => a + Math.abs(l.value), 0);
    expect(n.through).toBeCloseTo(pos + neg, 6);
  });
});

describe("a node's panel shows the node as drawn in the active preset (V1-05)", () => {
  for (const d of [fixtureData(), realData()]) {
    if (!d) continue;
    it(`${d.label}: every level-0 node's panel value equals its drawn height, in both presets`, () => {
      for (const preset of ["simple", "full"] as const) {
        const m = buildSamModel({ hierarchy: d.hierarchy, cells: d.cells, pinned: d.pinned, gdp: d.summary.gdp.value }, preset, [], "arcs");
        // drawn height in ₹ crore (the larger copy of the split node), as MapView's nodeValues
        const drawn = new Map<string, number>();
        for (const b of m.layout.nodes) drawn.set(b.id, Math.max(drawn.get(b.id) ?? 0, b.h / m.layout.unit));
        for (const n of m.nodes) {
          const sel = resolveNode(d.hierarchy, d.cells, d.pinned, n.id, preset);
          expect(sel, `${preset} ${n.id}`).not.toBeNull();
          expect(sel!.through, `${preset} ${n.id}`).toBeCloseTo(drawn.get(n.id)!, 0);
        }
      }
    });
    it(`${d.label}: the simple preset's SI is SI + FINM; FINM is never one of its partners`, () => {
      const simple = resolveNode(d.hierarchy, d.cells, d.pinned, "SI", "simple")!;
      const full = resolveNode(d.hierarchy, d.cells, d.pinned, "SI", "full")!;
      const finm = d.hierarchy.nodes.find((x) => x.id === "FINM")!.accounts;
      expect(finm.every((a) => simple.accounts.includes(a))).toBe(true);
      expect(finm.some((a) => full.accounts.includes(a))).toBe(false);
      const partners = (n: typeof simple) => new Set([...n.moneyIn.map((l) => l.payer), ...n.moneyOut.map((l) => l.receiver)]);
      expect(partners(simple).has("FINM")).toBe(false);
      expect(partners(simple).has("PRDS")).toBe(false);
      expect(partners(full).has("PRODUCERS")).toBe(false);
      // links keep their meaning: the same id resolves to the cells drawn in that preset
      for (const id of ["HH--SI", "SI--PRODUCERS"]) {
        const a = resolveLink(d.hierarchy, d.cells, d.pinned, id, "simple");
        if (!a) continue;
        const ms = buildSamModel({ hierarchy: d.hierarchy, cells: d.cells, pinned: d.pinned, gdp: d.summary.gdp.value }, "simple", [], "arcs");
        expect(a.link.value).toBeCloseTo(ms.links.find((l) => l.id === id)!.value, 2);
      }
    });
  }
});

describe("panel text", () => {
  const L = { text: { refs: { R1: { label: "Wages" }, R2: { label: "Rent" } } } } as never;
  const t = (k: string, v?: Record<string, string>) => (k === "composed" ? `Mostly ${v!.items}.` : `${v!.label} (${v!.share})`);
  const e = (ref: string, v: number) => ({ ref, v }) as Entry;
  it("composes 'Mostly …' from the entries' absolute values by ref, largest first", () => {
    expect(composeText([e("R1", 30), e("R2", -10), e("R1", 40)], L, t)).toBe("Mostly Wages (87.5%), Rent (12.5%).");
    expect(composeText([], L, t)).toBeNull();
  });
  it("names each X_DISC item by ref (and component for D3), never as one residual", () => {
    const x = (ref: string, component: string) => ({ row: "X_DISC", col: "H_R1", ref, component });
    expect(discKeyOf(x("D1", "total"))).toBe("D1");
    expect(discKeyOf({ row: "R_ROW", col: "X_DISC", ref: "D2", component: "total" })).toBe("D2");
    expect(discKeyOf(x("D3", "unsectored_valuables"))).toBe("D3_valuables");
    expect(discKeyOf(x("D3", "si_errors"))).toBe("D3_si_errors");
    expect(discKeyOf({ row: "H_R1", col: "C_CROP", ref: "D1", component: "total" })).toBeNull();
  });
});

describe("map state", () => {
  const d = fixtureData();
  const ctx = { hierarchy: d.hierarchy, years: d.series.periods };
  it("expanding in the simple preset switches to the full map first", () => {
    expect(expandState(d.hierarchy, DEFAULT_STATE, "HH")).toMatchObject({ preset: "full", expanded: ["HH"] });
    expect(expandState(d.hierarchy, DEFAULT_STATE, "PRODUCERS")).toMatchObject({ preset: "full", expanded: [] });
    expect(expandState(d.hierarchy, DEFAULT_STATE, "ROW")).toBe(DEFAULT_STATE);
  });
  it("collapsing a child folds its parent and everything under it", () => {
    const st = { ...DEFAULT_STATE, preset: "full" as const, expanded: ["HH", "HH.RUR", "TAX"] };
    expect(collapseState(d.hierarchy, st, "H_R1").expanded).toEqual(["HH", "TAX"]);
    expect(collapseState(d.hierarchy, st, "HH.RUR").expanded).toEqual(["TAX"]);
  });
  it("Back restores selection and zoom but keeps the year on screen", () => {
    const entry = { ...DEFAULT_STATE, selected: "HH--PRDS", preset: "full" as const };
    const cur = { ...DEFAULT_STATE, year: "1990-91", view: "ts" as const };
    expect(keepYear(entry, cur, ctx)).toMatchObject({ selected: "HH--PRDS", preset: "full", year: "1990-91", view: "ts" });
  });
  it("lists every FY from first to last", () => {
    const r = fyRange("1950-51", "2025-26");
    expect(r.length).toBe(76);
    expect(r[0]).toBe("1950-51");
    expect(r[49]).toBe("1999-00");
    expect(r[75]).toBe("2025-26");
  });
});

describe("trend chart SAM point (V1-02) and balancing moves (V5-01) on the real export", () => {
  const d = realData();
  it.runIf(!!d)("the SAM 2023-24 point is display-signed like the line: F13 and F30 are positive", () => {
    const gdp = d!.summary.gdp.value;
    const i = d!.series.periods.indexOf("2023-24");
    for (const f of d!.series.flows) {
      const sam = samPointOf(f, gdp);
      const share = f.main.share[i];
      if (!sam || share === null || f.check.verdict !== "pass") continue;
      // a passing check: the point sits on the line (same sign; apart by the check's own rel_diff)
      expect(Math.sign(sam.share), f.id).toBe(Math.sign(share));
      const rel = Math.abs(f.check.rel_diff ?? 0);
      expect(Math.abs(sam.share - share), f.id).toBeLessThanOrEqual(rel * Math.abs(share) * 1.02 + 2e-5);
    }
    for (const id of ["F13", "F30"]) {
      const f = d!.series.flows.find((x) => x.id === id)!;
      expect(f.display_sign).toBe(-1);
      expect(samPointOf(f, gdp)!.share, id).toBeGreaterThan(0);
      expect(samPointOf(f, gdp)!.value, id).toBeGreaterThan(0);
    }
  });
  it.runIf(!!d)("pct_change is a fraction of the prior, so the panel's pct format shows K4a H_U5 as 7.3%", () => {
    const root = path.resolve(__dirname, "../../../public/data");
    const ver = JSON.parse(fs.readFileSync(path.join(root, "index.json"), "utf8")).data_version as string;
    const entries = JSON.parse(fs.readFileSync(path.join(root, ver, "sam/entries/SI.json"), "utf8")).entries as Entry[];
    const e = entries.find((x) => x.ref === "K4a" && x.row === "K_HH" && x.col === "H_U5")!;
    expect(e).toBeDefined();
    expect(e.pct_change!).toBeCloseTo((e.v - e.prior) / Math.abs(e.prior), 4);
    expect(formatPct(e.pct_change!)).toBe("7.3%");
    // every entry: a fraction (a percent would be 100 times too large), up to the rounding of v and prior
    for (const x of entries) {
      if (x.pct_change === null || x.prior === 0) continue;
      const want = (x.v - x.prior) / Math.abs(x.prior);
      expect(Math.abs(x.pct_change - want), `${x.ref} ${x.row}<-${x.col}`).toBeLessThanOrEqual(0.01 * Math.max(1, Math.abs(want)));
    }
  });
});
