/**
 * Pure state helpers of the interactive Map (PLAN §2.1, §3.2, §4.3): no React, no Next.
 */
import type { Hierarchy } from "@/data/types";
import { normaliseState, type MapUrlState } from "@/lib/url-state";

/** FY labels from first to last: "1950-51" … "2025-26". */
export function fyRange(first: string, last: string): string[] {
  const a = Number(first.slice(0, 4));
  const b = Number(last.slice(0, 4));
  const out: string[] = [];
  for (let y = a; y <= b; y++) out.push(`${y}-${String((y + 1) % 100).padStart(2, "0")}`);
  return out;
}

/** The state after Back/Forward: the entry's selection and zoom, with the year (and view) on screen. */
export function keepYear(entry: MapUrlState, current: MapUrlState, ctx: Parameters<typeof normaliseState>[1]): MapUrlState {
  return normaliseState({ ...entry, year: current.year, view: current.view }, ctx);
}

/** Expanding a node (PLAN §3.2): in the simple preset the map first switches to `full`. */
export function expandState(h: Hierarchy, st: MapUrlState, id: string): MapUrlState {
  const node = h.nodes.find((n) => n.id === id);
  // a preset merge that is not a hierarchy node (PRODUCERS) opens into its members (PRDS, PROD)
  if (!node && h.presets.simple.merges[id]) return { ...st, preset: "full", expanded: [] };
  if (!node || !node.expandable || node.children.length === 0) return st;
  return { ...st, preset: "full", expanded: [...st.expanded.filter((x) => x !== id), id] };
}

/** Collapsing a node folds its parent (and everything under the parent) back. */
export function collapseState(h: Hierarchy, st: MapUrlState, id: string): MapUrlState {
  const node = h.nodes.find((n) => n.id === id);
  if (!node?.parent) return st;
  const parent = node.parent;
  const under = (x: string): boolean => {
    let n = h.nodes.find((m) => m.id === x);
    while (n) {
      if (n.id === parent) return true;
      n = n.parent ? h.nodes.find((m) => m.id === n!.parent) : undefined;
    }
    return false;
  };
  return { ...st, expanded: st.expanded.filter((x) => !under(x)) };
}

