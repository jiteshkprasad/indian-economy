/**
 * The top-flows board (PLAN §2.1, §4.6): the same renderer as the SAM map, fed by the time series.
 *
 * - Nodes are `ts_nodes` with fixed slots (`slot_share`, the maximum over all years), so nothing
 *   moves while scrubbing; gutters and ports are reserved with each ribbon's maximum width.
 * - Ribbon width = the flow's share of GDP on the same base, with the SAM view's px-per-%-of-GDP.
 * - A flow with no value in a year is not drawn and is listed; nothing is interpolated or carried.
 * - A reversible flow with a negative year keeps its place and is marked "reversed this year".
 */
import type { Hierarchy, Series, SeriesFlow, TsView } from "@/data/types";
import { layoutSankey } from "@/lib/sankey/layout";
import { PX_PER_PCT_GDP } from "@/lib/sankey/style";
import type { Layout } from "@/lib/sankey/types";
import { tsMapNodes, type MapNode } from "@/lib/sankey/visible";

export type BoardRibbon = {
  flow: string;
  from: string;
  to: string;
  /** signed main value × display_sign, ₹ crore (null = no data this year) */
  value: number | null;
  /** share of GDP on the same base, × display_sign (null = no data) */
  share: number | null;
  reversed: boolean;
  reversedTextKey: string | null;
  status: "official" | "derived" | null;
  base: string | null;
  stage: string | null;
};

export type BoardYearFlow = {
  flow: string;
  value: number | null;
  share: number | null;
  status: "official" | "derived" | null;
  base: string | null;
  drawn: boolean;
  internalTo: string | null;
};

export type Board = {
  year: string;
  yearIndex: number;
  nodes: MapNode[];
  layout: Layout;
  ribbons: BoardRibbon[];
  /** flows with a main value this year */
  coverage: number;
  totalFlows: number;
  /** every flow this year, for the list view */
  flows: BoardYearFlow[];
  /** ribbons with no value this year */
  noData: string[];
};

export function flowById(series: Series): Map<string, SeriesFlow> {
  return new Map(series.flows.map((f) => [f.id, f]));
}

export function buildBoard(h: Hierarchy, view: TsView, series: Series, year: string): Board {
  const t = series.periods.indexOf(year);
  if (t < 0) throw new Error(`top flows: unknown year ${year}`);
  const byFlow = flowById(series);
  const nodes = tsMapNodes(h);
  const ribbons: BoardRibbon[] = view.ribbons.map((r) => {
    const f = byFlow.get(r.flow);
    if (!f) throw new Error(`top flows: ribbon ${r.flow} is not in series.json`);
    const share = f.main.share[t];
    const v = f.main.v[t];
    const value = v === null ? null : v * f.display_sign;
    const reversed = share !== null && share < 0;
    if (reversed && !r.reversible) throw new Error(`top flows: ${r.flow} is negative in ${year} but not reversible`);
    return {
      flow: r.flow,
      from: r.from,
      to: r.to,
      value,
      share,
      reversed,
      reversedTextKey: reversed ? r.reversed_text_key : null,
      status: f.main.status[t],
      base: f.main.base[t],
      stage: f.main.stage[t],
    };
  });
  const maxShare = new Map<string, number>();
  for (const r of view.ribbons) {
    const f = byFlow.get(r.flow)!;
    let m = 0;
    for (const s of f.main.share) if (s !== null) m = Math.max(m, Math.abs(s));
    maxShare.set(r.flow, m);
  }
  const fixedHeights: Record<string, number> = {};
  for (const n of nodes) fixedHeights[n.id] = (view.slot_share[n.id] ?? 0) * 100 * PX_PER_PCT_GDP;
  const layout = layoutSankey(
    nodes,
    ribbons.map((r) => ({
      id: r.flow,
      source: r.from,
      target: r.to,
      value: r.share === null ? 0 : Math.abs(r.share),
      reserve: maxShare.get(r.flow) ?? 0,
      reversed: r.reversed,
    })),
    { gdp: 1, pxPerPct: PX_PER_PCT_GDP, returnFlows: "stubs", fixedHeights, reservePorts: true },
  );
  const drawnSet = new Set(view.ribbons.map((r) => r.flow));
  const internalOf = new Map<string, string>();
  for (const [node, flows] of Object.entries(view.internal)) for (const f of flows) internalOf.set(f, node);
  const flows: BoardYearFlow[] = series.flows.map((f) => ({
    flow: f.id,
    value: f.main.v[t] === null ? null : f.main.v[t]! * f.display_sign,
    share: f.main.share[t],
    status: f.main.status[t],
    base: f.main.base[t],
    drawn: drawnSet.has(f.id) && f.main.share[t] !== null,
    internalTo: internalOf.get(f.id) ?? null,
  }));
  return {
    year,
    yearIndex: t,
    nodes,
    layout,
    ribbons,
    coverage: view.coverage[t],
    totalFlows: series.flows.length,
    flows,
    noData: ribbons.filter((r) => r.share === null).map((r) => r.flow),
  };
}
