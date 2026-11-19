import type { Cite, ProvRecord } from "@/data/types";

export type MergedCite = {
  source: string;
  tables: string[];
  urls: Array<string | null>;
  withheld: boolean;
  retrieved: [string | null, string | null];
  /** how many of the given prov ids cite this source */
  count: number;
};

/**
 * Merges the cites of several provenance records for one aggregate, in the order
 * of PLAN §3.5: direct-input order (best position in any record's cites list),
 * then how many records cite the source (weighted by `weights`, e.g. entry
 * counts), then source id.
 */
export function mergeCites(
  provIds: readonly string[],
  records: Record<string, ProvRecord>,
  weights?: Record<string, number>,
): MergedCite[] {
  const by = new Map<string, MergedCite & { rank: number }>();
  for (const pid of provIds) {
    const rec = records[pid];
    if (!rec) throw new Error(`mergeCites: provenance record "${pid}" not found`);
    const w = weights?.[pid] ?? 1;
    rec.cites.forEach((c: Cite, i: number) => {
      const cur = by.get(c.source);
      if (!cur) {
        by.set(c.source, {
          source: c.source,
          tables: [...c.tables],
          urls: [...new Set(c.urls)],
          withheld: c.withheld,
          retrieved: [c.retrieved[0] ?? null, c.retrieved[1] ?? null],
          count: w,
          rank: i,
        });
        return;
      }
      cur.rank = Math.min(cur.rank, i);
      cur.count += w;
      for (const t of c.tables) if (!cur.tables.includes(t)) cur.tables.push(t);
      for (const u of c.urls) if (!cur.urls.includes(u)) cur.urls.push(u);
      cur.withheld ||= c.withheld;
      const [from, to] = [c.retrieved[0] ?? null, c.retrieved[1] ?? null];
      if (from && (!cur.retrieved[0] || from < cur.retrieved[0])) cur.retrieved[0] = from;
      if (to && (!cur.retrieved[1] || to > cur.retrieved[1])) cur.retrieved[1] = to;
    });
  }
  return [...by.values()]
    .sort((a, b) => a.rank - b.rank || b.count - a.count || (a.source < b.source ? -1 : a.source > b.source ? 1 : 0))
    .map(({ rank: _rank, ...c }) => c);
}
