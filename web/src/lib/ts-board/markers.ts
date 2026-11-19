/**
 * Markers on the slider and on every trend chart (PLAN §2.1 item 7), generated from the data, never
 * hand-placed: every `base_change`, `concept_break` and `segment_join` flag and every segment
 * boundary (exported per flow as `markers`), plus non-final estimate stages.
 */
import type { Series, SeriesFlow, SeriesMarker } from "@/data/types";

export type MarkerKind = SeriesMarker["kind"];

export type PeriodMarker = {
  period: string;
  index: number;
  kinds: MarkerKind[];
  /** distinct notes, in flow order */
  notes: string[];
  flows: string[];
};

const KIND_ORDER: MarkerKind[] = ["base_change", "concept_break", "break", "segment_join", "segment"];

/** All markers of the series, grouped by period, in period order. */
export function sliderMarkers(series: Series): PeriodMarker[] {
  const byPeriod = new Map<string, PeriodMarker>();
  for (const f of series.flows) {
    for (const m of f.markers) {
      const index = series.periods.indexOf(m.period);
      if (index < 0) throw new Error(`marker on unknown period ${m.period} (${f.id})`);
      let pm = byPeriod.get(m.period);
      if (!pm) {
        pm = { period: m.period, index, kinds: [], notes: [], flows: [] };
        byPeriod.set(m.period, pm);
      }
      if (!pm.kinds.includes(m.kind)) pm.kinds.push(m.kind);
      if (!pm.notes.includes(m.note)) pm.notes.push(m.note);
      if (!pm.flows.includes(f.id)) pm.flows.push(f.id);
    }
  }
  const out = [...byPeriod.values()].sort((a, b) => a.index - b.index);
  for (const pm of out) pm.kinds.sort((a, b) => KIND_ORDER.indexOf(a) - KIND_ORDER.indexOf(b));
  return out;
}

/** Markers of one flow, in period order (the trend chart). */
export function flowMarkers(series: Series, flow: SeriesFlow): Array<SeriesMarker & { index: number }> {
  return flow.markers
    .map((m) => ({ ...m, index: series.periods.indexOf(m.period) }))
    .filter((m) => m.index >= 0)
    .sort((a, b) => a.index - b.index || KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind));
}

/**
 * Estimate stages that are not final, as published: PE, "Provisional" and "Preliminary" (the
 * latest year) and the NAS revision stages FRE, SRE and TRE. Final, Actuals, Audited, Revised and
 * n.a. are not marked.
 */
export const NON_FINAL_STAGES = ["PE", "Provisional", "Preliminary", "FRE", "SRE", "TRE"] as const;
export const PROVISIONAL_STAGES = ["PE", "Provisional", "Preliminary"] as const;

export function stageMarkers(series: Series): Array<{ period: string; index: number; stages: string[] }> {
  const out: Array<{ period: string; index: number; stages: string[] }> = [];
  series.periods.forEach((p, i) => {
    const stages = new Set<string>();
    for (const f of series.flows) {
      const s = f.main.stage[i];
      if (s && (NON_FINAL_STAGES as readonly string[]).includes(s)) stages.add(s);
    }
    if (stages.size) out.push({ period: p, index: i, stages: [...stages].sort() });
  });
  return out;
}
