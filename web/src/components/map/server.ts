/**
 * Build-time helpers for the Map's static pages (PLAN §4.2, D3-12): the level-0 link ids of both
 * presets, and the SUBSET of the data one flow or series page needs, so each permalink renders
 * fully without JavaScript and without embedding the whole export in every page.
 * Server only; never import from `index.ts` (client code imports that).
 */
import "server-only";
import { aggregate, visibleNodes } from "@/data/aggregate";
import {
  loadCells,
  loadConstraints,
  loadCover,
  loadEntries,
  loadHierarchy,
  loadMapDesc,
  loadPinned,
  loadProvenance,
  loadSeries,
  loadSummary,
} from "@/data/server";
import type { Cells, Constraints, Cover, Entry, MapDesc, Pinned, Provenance, Series } from "@/data/types";
import { pairId, siblingId } from "@/lib/ids";
import { entryFilesFor, resolveLink } from "@/lib/sankey/select";
import { matchSeries } from "@/lib/ts-board/match";
import type { FlowPreload } from "./FlowDetailPanel";

export type PresetId = "simple" | "full";

/** Level-0 link ids (positive and `~neg` parts) of each preset, in aggregate order. */
let level0Cache: { key: unknown; links: Record<PresetId, string[]> } | null = null;

export function level0Links(): Record<PresetId, string[]> {
  const h = loadHierarchy();
  // the loaders return the same objects for one export, so the ids are computed once per build worker
  if (level0Cache && level0Cache.key === h) return level0Cache.links;
  const cells = loadCells();
  const pinned = loadPinned();
  const out = {} as Record<PresetId, string[]>;
  for (const p of ["simple", "full"] as const) {
    out[p] = aggregate(cells, h, visibleNodes(h, p, []), pinned).links.map((l) => l.id);
  }
  level0Cache = { key: h, links: out };
  return out;
}

/** Every level-0 link id of both presets, sorted (the `/flow/<id>/` routes). */
export function level0LinkIds(): string[] {
  const l = level0Links();
  return [...new Set([...l.simple, ...l.full])].sort();
}

/** The preset a level-0 link is drawn in (the simple map when it is in both). */
export function presetOf(id: string): PresetId {
  return level0Links().simple.includes(id) ? "simple" : "full";
}

/** Keep only the listed cell indices (every column array of `cells`). */
export function subsetCells(cells: Cells, idx: readonly number[]): Cells {
  const pick = <T,>(a: T[]) => idx.map((i) => a[i]);
  return {
    n: idx.length,
    row: pick(cells.row),
    col: pick(cells.col),
    v: pick(cells.v),
    abs_o: pick(cells.abs_o),
    abs_d: pick(cells.abs_d),
    abs_e: pick(cells.abs_e),
    abs_b: pick(cells.abs_b),
    split: pick(cells.split),
    flags: pick(cells.flags),
    n_entries: pick(cells.n_entries),
    refs: pick(cells.refs),
  };
}

function subsetProvenance(prov: Provenance, ids: Iterable<string>): Provenance {
  const records: Provenance["records"] = {};
  for (const id of ids) {
    const r = prov.records[id];
    if (!r) throw new Error(`provenance: record ${id} is not in provenance.json`);
    records[id] = r;
  }
  return { records, sources: prov.sources };
}

function emptyDesc(): MapDesc {
  return { nodes: {}, links: {}, refs: {}, series: {} };
}

/** Everything the flow panel needs for one link, computed at build time. Throws if the link has no cells. */
export function flowPreload(id: string, locale: string): FlowPreload {
  const summary = loadSummary();
  const hierarchy = loadHierarchy();
  const cells = loadCells();
  const pinned = loadPinned();
  const sel = resolveLink(hierarchy, cells, pinned, id, presetOf(id));
  if (!sel) throw new Error(`flow page: link ${id} has no cells`);
  const linkCells = sel.link.cells;
  const codes = hierarchy.accounts.map((a) => a.code);
  const keys = new Set(linkCells.map((i) => `${codes[cells.row[i]]}|${codes[cells.col[i]]}`));
  const entries: Entry[] = entryFilesFor(hierarchy, sel.receiverAccounts)
    .flatMap((l0) => loadEntries(l0).entries)
    .filter((e) => keys.has(`${e.row}|${e.col}`));
  const pins: Pinned = {};
  for (const k of [id, pairId(id), siblingId(id)]) if (k && pinned[k]) pins[k] = pinned[k];
  const coverAll = loadCover();
  const matched = matchSeries(cells, linkCells, coverAll).map((m) => m.flow);
  const cover: Cover = {};
  for (const f of matched) cover[f] = coverAll[f];
  const seriesAll = loadSeries();
  const series: Series = { ...seriesAll, flows: seriesAll.flows.filter((f) => matched.includes(f.id)) };
  const constraintsAll = loadConstraints();
  const constraints: Constraints = {};
  for (const e of entries) for (const c of e.binding) if (constraintsAll[c]) constraints[c] = constraintsAll[c];
  const descAll = loadMapDesc(locale);
  const desc = emptyDesc();
  if (descAll.links[id]) desc.links[id] = descAll.links[id];
  return {
    summary,
    hierarchy,
    cells: subsetCells(cells, linkCells),
    pinned: pins,
    entries,
    provenance: subsetProvenance(loadProvenance(), new Set(entries.map((e) => e.prov))),
    series,
    cover,
    constraints,
    desc,
  };
}

/** Every series id (the `/series/<id>/` routes). */
export function seriesIds(): string[] {
  return loadSeries().flows.map((f) => f.id);
}

/** Data for one series page: that flow only, its provenance records and its description. */
export function seriesPreload(id: string, locale: string): FlowPreload & { series: Series } {
  const seriesAll = loadSeries();
  const flow = seriesAll.flows.find((f) => f.id === id);
  if (!flow) throw new Error(`series page: ${id} is not in ts/series.json`);
  const provIds = new Set<string>();
  for (const a of [flow.main, flow.linked, ...flow.alts.map((x) => x.arrays)]) {
    if (!a) continue;
    for (const p of a.prov) if (p) provIds.add(p);
  }
  const descAll = loadMapDesc(locale);
  const desc = emptyDesc();
  if (descAll.series[id]) desc.series[id] = descAll.series[id];
  const hierarchy = loadHierarchy();
  return {
    summary: loadSummary(),
    hierarchy,
    cells: subsetCells(loadCells(), []),
    pinned: {},
    series: { ...seriesAll, flows: [flow] },
    provenance: subsetProvenance(loadProvenance(), provIds),
    desc,
  };
}

/** The latest period with a main value (the series page's headline year). */
export function latestYear(series: Series, id: string): string {
  const flow = series.flows.find((f) => f.id === id);
  if (!flow) throw new Error(`series ${id} not found`);
  for (let i = series.periods.length - 1; i >= 0; i--) if (flow.main.v[i] !== null) return series.periods[i];
  throw new Error(`series ${id} has no values`);
}
