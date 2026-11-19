/**
 * From exported data to a drawn map: visible nodes → aggregated links (the platform's `aggregate`,
 * account cells as atoms) → layout. Pure; the same call on the server and the client gives the
 * same geometry, so the build-time HTML and the hydrated map agree.
 */
import { aggregate, visibleNodes, type AggLink, type Aggregate, type Visible } from "@/data/aggregate";
import type { Cells, Hierarchy, Pinned, PresetId } from "./contract";
import { layoutSankey } from "./layout";
import { PX_PER_PCT_GDP } from "./style";
import type { Layout, LayoutLinkInput } from "./types";
import { mapNodes, type MapNode } from "./visible";

export type SamInputs = { hierarchy: Hierarchy; cells: Cells; pinned: Pinned; gdp: number };

export type SamModel = {
  visible: Visible;
  agg: Aggregate;
  nodes: MapNode[];
  nodeById: Map<string, MapNode>;
  links: AggLink[];
  linkById: Map<string, AggLink>;
  layout: Layout;
  gdp: number;
};

/** Drawn links: a positive part is drawn payer → receiver; a negative part reversed (§4.5.4). */
export function toLayoutLinks(links: readonly AggLink[]): LayoutLinkInput[] {
  return links.map((l) =>
    l.part === "pos"
      ? { id: l.id, source: l.payer, target: l.receiver, value: Math.abs(l.value) }
      : { id: l.id, source: l.receiver, target: l.payer, value: Math.abs(l.value), reversed: true },
  );
}

export function buildSamModel(
  d: SamInputs,
  preset: PresetId,
  expanded: readonly string[],
  returnFlows: "stubs" | "arcs",
): SamModel {
  const visible = visibleNodes(d.hierarchy, preset, expanded);
  const agg = aggregate(d.cells, d.hierarchy, visible, d.pinned);
  const nodes = mapNodes(d.hierarchy, visible);
  const layout = layoutSankey(nodes, toLayoutLinks(agg.links), {
    gdp: d.gdp,
    pxPerPct: PX_PER_PCT_GDP,
    returnFlows,
  });
  return {
    visible,
    agg,
    nodes,
    nodeById: new Map(nodes.map((n) => [n.id, n])),
    links: agg.links,
    linkById: new Map(agg.links.map((l) => [l.id, l])),
    layout,
    gdp: d.gdp,
  };
}

/** Links touching a node: outgoing first (as drawn), then incoming; each list by size. */
export function linksOfNode(m: SamModel, nodeId: string): { out: AggLink[]; in: AggLink[] } {
  const drawnSource = (l: AggLink) => (l.part === "pos" ? l.payer : l.receiver);
  const drawnTarget = (l: AggLink) => (l.part === "pos" ? l.receiver : l.payer);
  const bySize = (a: AggLink, b: AggLink) => Math.abs(b.value) - Math.abs(a.value) || (a.id < b.id ? -1 : 1);
  return {
    out: m.links.filter((l) => drawnSource(l) === nodeId).sort(bySize),
    in: m.links.filter((l) => drawnTarget(l) === nodeId).sort(bySize),
  };
}

/** Money in and money out of a node in SAM terms (receipts and payments, both parts). */
export function moneyInOut(m: SamModel, nodeId: string): { in: AggLink[]; out: AggLink[] } {
  const bySize = (a: AggLink, b: AggLink) => Math.abs(b.value) - Math.abs(a.value) || (a.id < b.id ? -1 : 1);
  return {
    in: m.links.filter((l) => l.receiver === nodeId).sort(bySize),
    out: m.links.filter((l) => l.payer === nodeId).sort(bySize),
  };
}
