import { describe, expect, it } from "vitest";
import { balanceViolations, nanViolations, throughNodeViolations } from "@/lib/sankey/invariants";
import { buildSamModel } from "@/lib/sankey/model";
import { buildBoard } from "@/lib/ts-board/board";
import { sliderMarkers, stageMarkers } from "@/lib/ts-board/markers";
import { fixtureData, realData, type MapTestData } from "./data";

function boardTests(d: MapTestData) {
  describe(`top-flows board: ${d.label}`, () => {
    const boards = d.series.periods.map((y) => buildBoard(d.hierarchy, d.tsView, d.series, y));

    it("keeps every node in the same place in every year (slots are the maximum over years)", () => {
      const ref = boards[0].layout.nodes.map((n) => [n.key, n.x, n.y, n.h]);
      for (const b of boards) expect(b.layout.nodes.map((n) => [n.key, n.x, n.y, n.h]), b.year).toEqual(ref);
    });

    it("keeps every ribbon's ports and gutter slots in place while scrubbing", () => {
      const pos = new Map<string, number[]>();
      for (const b of boards) {
        for (const l of b.layout.links) {
          const p = [l.sPort.y0, l.tPort.y0, l.reserve];
          if (!pos.has(l.id)) pos.set(l.id, p);
          else expect(p, `${l.id} in ${b.year}`).toEqual(pos.get(l.id));
        }
      }
    });

    it("never lets a year's flows overflow their slot, and draws no NaN or ribbon through a node", () => {
      for (const b of boards) {
        expect(balanceViolations(b.layout, true), b.year).toEqual([]);
        expect(nanViolations(b.layout), b.year).toEqual([]);
        expect(throughNodeViolations(b.layout), b.year).toEqual([]);
      }
    });

    it("does not draw a flow with no value that year, and lists it; nothing is interpolated", () => {
      for (const b of boards) {
        for (const r of b.ribbons) {
          const laid = b.layout.links.find((l) => l.id === r.flow)!;
          if (r.share === null) {
            expect(laid.drawn, `${r.flow} ${b.year}`).toBe(false);
            expect(b.noData).toContain(r.flow);
            expect(r.value).toBeNull();
          } else {
            expect(b.noData).not.toContain(r.flow);
          }
        }
      }
    });

    it("draws a reversible flow reversed in its negative years, with its own text", () => {
      let seen = 0;
      for (const b of boards) {
        for (const r of b.ribbons) {
          const spec = d.tsView.ribbons.find((x) => x.flow === r.flow)!;
          expect(r.reversed).toBe(r.share !== null && r.share < 0);
          if (r.reversed) {
            seen++;
            expect(spec.reversible).toBe(true);
            expect(r.reversedTextKey).toBe(spec.reversed_text_key);
            expect(b.layout.links.find((l) => l.id === r.flow)!.reversed).toBe(true);
          }
        }
      }
      expect(seen).toBeGreaterThan(0);
    });

    it("sizes ribbons with the SAM view's width scale (share of GDP)", () => {
      const sam = buildSamModel(
        { hierarchy: d.hierarchy, cells: d.cells, pinned: d.pinned, gdp: d.summary.gdp.value },
        "simple",
        [],
        "stubs",
      );
      const b = boards[boards.length - 3];
      const r = b.ribbons.find((x) => x.share !== null)!;
      const l = b.layout.links.find((x) => x.id === r.flow)!;
      // width per % of GDP is the same constant in both views
      expect(l.width / (Math.abs(r.share!) * 100)).toBeCloseTo((sam.layout.unit * d.summary.gdp.value) / 100, 6);
    });

    it("counts coverage per year from the export", () => {
      for (const b of boards) expect(b.coverage).toBe(d.tsView.coverage[b.yearIndex]);
    });
  });

  describe(`slider markers: ${d.label}`, () => {
    const pm = sliderMarkers(d.series);
    it("shows every base_change, concept_break and segment_join flag of the series as a marker", () => {
      for (const f of d.series.flows) {
        f.main.flags.forEach((fl, i) => {
          if (!fl) return;
          for (const kind of fl.split(",").map((x) => x.trim())) {
            if (!["base_change", "concept_break", "segment_join"].includes(kind)) continue;
            const m = pm.find((x) => x.index === i);
            expect(m, `${f.id} ${d.series.periods[i]} ${kind}`).toBeDefined();
            expect(m!.kinds).toContain(kind);
            expect(m!.flows).toContain(f.id);
          }
        });
      }
    });
    it("keeps every exported marker (incl. segment boundaries), in period order", () => {
      const n = d.series.flows.reduce((a, f) => a + f.markers.length, 0);
      expect(n).toBeGreaterThan(0);
      for (const f of d.series.flows) for (const m of f.markers) expect(pm.find((x) => x.period === m.period)!.notes).toContain(m.note);
      for (let i = 1; i < pm.length; i++) expect(pm[i].index).toBeGreaterThan(pm[i - 1].index);
    });
    it("marks non-final estimate stages only", () => {
      for (const s of stageMarkers(d.series)) for (const st of s.stages) expect(["PE", "Provisional", "Preliminary", "FRE", "SRE", "TRE"]).toContain(st);
    });
  });
}

boardTests(fixtureData());
const real = realData();
if (real) boardTests(real);
else it.skip("REAL-DATA INVARIANTS NOT RUN", () => {});
