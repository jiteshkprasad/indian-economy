/**
 * Map state in the URL, PLAN §4.3:
 *   /en/?view=sam|ts&p=simple|full&y=2023-24&x=HH,TAX&s=HH--PRDS&t=table
 *
 * Parsing validates against the hierarchy and the list of years. An invalid value
 * is dropped and reported as a notice (a message key in the `common` namespace
 * with its params) for the UI to show; it is never silently ignored.
 * The server-rendered page never reads the URL; a client child applies it after mount.
 * Slider moves use replaceState; selection, zoom and preset changes use pushState.
 */
import type { Hierarchy, PresetId } from "@/data/types";
import { isLinkId, isSeriesId, parseLinkId, SAM_YEAR } from "./ids";

export type MapUrlState = {
  view: "sam" | "ts";
  preset: PresetId;
  year: string;
  expanded: string[];
  selected: string | null;
  table: boolean;
};

export type UrlNotice = { key: string; values: Record<string, string> };

export const DEFAULT_STATE: MapUrlState = {
  view: "sam",
  preset: "simple",
  year: SAM_YEAR,
  expanded: [],
  selected: null,
  table: false,
};

export type ParseContext = {
  hierarchy: Pick<Hierarchy, "nodes" | "presets" | "ts_nodes">;
  /** valid year labels (series periods); when omitted only the SAM year is valid */
  years?: readonly string[];
  /** extra valid node ids (preset ids such as PRODUCERS and GOV come from the hierarchy presets) */
  extraNodeIds?: readonly string[];
};

function knownNodeIds(ctx: ParseContext): Set<string> {
  const s = new Set<string>(ctx.hierarchy.nodes.map((n) => n.id));
  for (const p of Object.values(ctx.hierarchy.presets)) for (const m of Object.keys(p.merges)) s.add(m);
  for (const n of ctx.hierarchy.ts_nodes) s.add(n.id);
  for (const x of ctx.extraNodeIds ?? []) s.add(x);
  return s;
}

/** Normalises a state: x implies full; view forced to ts off the SAM year; x in hierarchy order with ancestors. */
export function normaliseState(s: MapUrlState, ctx: ParseContext): MapUrlState {
  const byId = new Map(ctx.hierarchy.nodes.map((n) => [n.id, n]));
  const set = new Set<string>();
  for (const id of s.expanded) {
    let n = byId.get(id);
    while (n) {
      if (n.expandable) set.add(n.id);
      n = n.parent ? byId.get(n.parent) : undefined;
    }
  }
  const expanded = ctx.hierarchy.nodes
    .filter((n) => set.has(n.id))
    .sort((a, b) => a.order - b.order)
    .map((n) => n.id);
  return {
    ...s,
    expanded,
    preset: expanded.length ? "full" : s.preset,
    view: s.year !== SAM_YEAR ? "ts" : s.view,
  };
}

export function parseUrlState(search: string, ctx: ParseContext): { state: MapUrlState; notices: UrlNotice[] } {
  const q = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const notices: UrlNotice[] = [];
  const st: MapUrlState = { ...DEFAULT_STATE, expanded: [] };
  const nodes = knownNodeIds(ctx);
  const byId = new Map(ctx.hierarchy.nodes.map((n) => [n.id, n]));
  const years = ctx.years ?? [SAM_YEAR];

  const view = q.get("view");
  if (view !== null) {
    if (view === "sam" || view === "ts") st.view = view;
    else notices.push({ key: "url.invalidView", values: { value: view } });
  }
  const p = q.get("p");
  if (p !== null) {
    if (p === "simple" || p === "full") st.preset = p;
    else notices.push({ key: "url.invalidPreset", values: { value: p } });
  }
  const y = q.get("y");
  if (y !== null) {
    if (years.includes(y)) st.year = y;
    else notices.push({ key: "url.invalidYear", values: { value: y } });
  }
  const x = q.get("x");
  if (x !== null && x !== "") {
    for (const id of x.split(",")) {
      const n = byId.get(id);
      if (!n) notices.push({ key: "url.nodeNotFound", values: { value: id } });
      else if (!n.expandable) notices.push({ key: "url.notExpandable", values: { value: id } });
      else st.expanded.push(id);
    }
  }
  const s = q.get("s");
  if (s !== null && s !== "") {
    const link = parseLinkId(s);
    if (link && link.part !== "pair" && nodes.has(link.payer) && nodes.has(link.receiver)) st.selected = s;
    else if (!isLinkId(s) && (nodes.has(s) || isSeriesId(s))) st.selected = s;
    else notices.push({ key: isLinkId(s) ? "url.linkNotFound" : "url.selectionNotFound", values: { value: s } });
  }
  const t = q.get("t");
  if (t !== null) {
    if (t === "table") st.table = true;
    else notices.push({ key: "url.invalidTable", values: { value: t } });
  }
  return { state: normaliseState(st, ctx), notices };
}

/** Query string for a state, omitting defaults; "" for the default state. */
export function serialiseUrlState(s: MapUrlState): string {
  const q: string[] = [];
  if (s.view !== DEFAULT_STATE.view && !(s.view === "ts" && s.year !== SAM_YEAR)) q.push(`view=${s.view}`);
  if (s.preset !== DEFAULT_STATE.preset && s.expanded.length === 0) q.push(`p=${s.preset}`);
  if (s.year !== DEFAULT_STATE.year) q.push(`y=${encodeURIComponent(s.year)}`);
  if (s.expanded.length) q.push(`x=${s.expanded.map(encodeURIComponent).join(",")}`);
  if (s.selected) q.push(`s=${encodeURIComponent(s.selected)}`);
  if (s.table) q.push("t=table");
  return q.length ? `?${q.join("&")}` : "";
}

/** Writes the state to the address bar. "replace" for slider moves; "push" for selection, zoom and preset. */
export function writeUrlState(s: MapUrlState, mode: "push" | "replace", win: Window = window): void {
  const url = `${win.location.pathname}${serialiseUrlState(s)}${win.location.hash}`;
  if (mode === "push") win.history.pushState(null, "", url);
  else win.history.replaceState(null, "", url);
}

/** Which mode a state change needs: replace when only the year (and the view it forces) changed. */
export function historyModeFor(prev: MapUrlState, next: MapUrlState): "push" | "replace" {
  const same =
    prev.preset === next.preset &&
    prev.selected === next.selected &&
    prev.table === next.table &&
    prev.expanded.join(",") === next.expanded.join(",");
  return same ? "replace" : "push";
}
