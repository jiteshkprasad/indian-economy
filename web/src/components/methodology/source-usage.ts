/**
 * How many SAM entries, time series, constraints and story figures cite each source
 * (PLAN §4.10 item 6). Pure functions over the exported JSON, so they run at build
 * time in the methodology page and in vitest on small in-test data.
 *
 * A thing cites a source when the provenance record it points to lists that source
 * in `cites` (the exporter has already walked `inputs` down to the clean-data
 * leaves, PLAN §3.5). A prov id that is missing from provenance.json is an error,
 * never skipped: the page would otherwise under-count silently.
 */
import type { Constraints, Entries, Provenance, Series, Story } from "@/data/types";

export type SourceUsage = { entries: number; series: number; constraints: number; storyFigures: number };

export type UsageInput = {
  provenance: Provenance;
  entries: Entries[];
  series: Series | null;
  constraints: Constraints | null;
  stories: Story[];
};

function sourcesOf(provenance: Provenance, provId: string, what: string): Set<string> {
  const rec = provenance.records[provId];
  if (!rec) throw new Error(`source-usage: ${what} cites prov id "${provId}", which is not in provenance.json`);
  return new Set(rec.cites.map((c) => c.source));
}

function addAll(target: Map<string, SourceUsage>, sources: Iterable<string>, key: keyof SourceUsage) {
  for (const s of sources) {
    const u = target.get(s);
    if (!u) throw new Error(`source-usage: source "${s}" is cited but not listed in provenance.sources`);
    u[key] += 1;
  }
}

/** Usage per source id, for every source in provenance.sources (zero counts included). */
export function sourceUsage(input: UsageInput): Map<string, SourceUsage> {
  const { provenance } = input;
  const out = new Map<string, SourceUsage>();
  for (const id of Object.keys(provenance.sources).sort()) {
    out.set(id, { entries: 0, series: 0, constraints: 0, storyFigures: 0 });
  }

  for (const file of input.entries) {
    for (const e of file.entries) {
      addAll(out, sourcesOf(provenance, e.prov, `entry ${e.row}<-${e.col} ${e.ref}`), "entries");
    }
  }

  if (input.series) {
    for (const f of input.series.flows) {
      const ids = new Set<string>();
      const arrays = [f.main, ...(f.linked ? [f.linked] : []), ...f.alts.map((a) => a.arrays)];
      for (const a of arrays) for (const p of a.prov) if (p !== null) ids.add(p);
      const srcs = new Set<string>();
      for (const p of ids) for (const s of sourcesOf(provenance, p, `series ${f.id}`)) srcs.add(s);
      addAll(out, srcs, "series");
    }
  }

  if (input.constraints) {
    for (const [cid, c] of Object.entries(input.constraints)) {
      if (!c.prov) continue; // empty target-0 placeholders carry no source
      addAll(out, sourcesOf(provenance, c.prov, `constraint ${cid}`), "constraints");
    }
  }

  for (const story of input.stories) {
    for (const [fid, fig] of Object.entries(story.figures)) {
      const srcs = new Set<string>();
      for (const p of fig.prov) for (const s of sourcesOf(provenance, p, `story ${story.slug} figure ${fid}`)) srcs.add(s);
      addAll(out, srcs, "storyFigures");
    }
  }
  return out;
}

export type SourceRow = {
  id: string;
  name: string;
  publisher: string;
  licence: string;
  attribution: string;
  linkMode: "deep" | "landing" | "withheld";
  registryStatus: string;
  /** A link to show, or null. Never an RBI host, whatever the data say. */
  href: string | null;
  usage: SourceUsage;
};

const RBI_HOST = /(^|\.)rbi\.org\.in$/i;

function safeHref(url: string | null): string | null {
  if (!url) return null;
  let host: string;
  try {
    const u = new URL(url);
    if (u.protocol !== "https:" && u.protocol !== "http:") return null;
    host = u.hostname;
  } catch {
    return null;
  }
  return RBI_HOST.test(host) ? null : url;
}

/** Table rows, most-cited first (entries, then series, constraints, story figures), then by name. */
export function sourceRows(provenance: Provenance, usage: Map<string, SourceUsage>): SourceRow[] {
  const rows: SourceRow[] = Object.entries(provenance.sources).map(([id, s]) => ({
    id,
    name: s.name,
    publisher: s.publisher,
    licence: s.licence,
    attribution: s.attribution,
    linkMode: s.link_mode,
    registryStatus: s.registry_status,
    href: s.link_mode === "withheld" ? null : safeHref(s.landing),
    usage: usage.get(id) ?? { entries: 0, series: 0, constraints: 0, storyFigures: 0 },
  }));
  rows.sort(
    (a, b) =>
      b.usage.entries - a.usage.entries ||
      b.usage.series - a.usage.series ||
      b.usage.constraints - a.usage.constraints ||
      b.usage.storyFigures - a.usage.storyFigures ||
      a.name.localeCompare(b.name, "en") ||
      a.id.localeCompare(b.id, "en"),
  );
  return rows;
}
