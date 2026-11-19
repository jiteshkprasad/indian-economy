/**
 * The flows a story step highlights, with their values (PLAN §4.9: on phones the
 * compact map is followed by an inline list of the highlighted flows). Values come
 * from the shared aggregation of account cells (src/data/aggregate.ts), so they are
 * the same numbers the Map shows for those links.
 */
import { aggregate, visibleNodes, type AggLink } from "@/data/aggregate";
import type { Cells, Hierarchy, Pinned, StoryView } from "@/data/types";

export type HighlightResult = { links: AggLink[]; missing: string[] };

/** Highlighted link ids of a step, in the step's order. Node ids are skipped; unknown link ids are reported. */
export function highlightedLinks(cells: Cells, h: Hierarchy, pinned: Pinned, view: StoryView): HighlightResult {
  const visible = visibleNodes(h, view.preset, view.expanded);
  const { links } = aggregate(cells, h, visible, pinned);
  const byId = new Map(links.map((l) => [l.id, l]));
  const nodes = new Set(visible.ids);
  const out: AggLink[] = [];
  const missing: string[] = [];
  for (const id of view.highlight) {
    const link = byId.get(id);
    if (link) out.push(link);
    else if (!nodes.has(id)) missing.push(id);
  }
  return { links: out, missing };
}
