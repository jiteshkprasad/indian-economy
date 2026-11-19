/**
 * Matching a clicked SAM link to the time series (PLAN §3.7.4). `ts/cover.json` gives, for each
 * series, the SAM cells it measures in 2023-24 (signed) and Σ|covered|.
 *   inside = Σ|covered cells in L| / abs_total   (how much of the series lies in L)
 *   covers = Σ|covered cells in L| / Σ|cells of L| (how much of L the series explains)
 */
import type { Cells, Cover } from "@/data/types";

export type MatchKind = "trend" | "related" | "overlap";

export type SeriesMatch = {
  flow: string;
  kind: MatchKind;
  inside: number;
  covers: number;
  /** cells of the series outside L, as [rowIdx, colIdx, value] (for "the rest is …") */
  rest: Array<[number, number, number]>;
};

export const INSIDE_SAME = 0.95;
export const COVERS_SAME = 0.995;
export const INSIDE_MIN = 0.5;

/** Classify one (inside, covers) pair by the §3.7.4 table; null = not shown. */
export function classify(inside: number, covers: number): MatchKind | null {
  if (inside >= INSIDE_SAME) return covers >= COVERS_SAME ? "trend" : "related";
  if (inside >= INSIDE_MIN) return "overlap";
  return null;
}

/** Series matched to a link made of the given cell indices; best match first. */
export function matchSeries(cells: Cells, linkCells: readonly number[], cover: Cover): SeriesMatch[] {
  const inL = new Set<string>();
  let absL = 0;
  for (const i of linkCells) {
    inL.add(`${cells.row[i]}|${cells.col[i]}`);
    absL += Math.abs(cells.v[i]);
  }
  const out: SeriesMatch[] = [];
  for (const flow of Object.keys(cover).sort()) {
    const c = cover[flow];
    if (!(c.abs_total > 0)) continue;
    let covered = 0;
    const rest: Array<[number, number, number]> = [];
    for (const [r, k, v] of c.cells) {
      if (inL.has(`${r}|${k}`)) covered += Math.abs(v);
      else rest.push([r, k, v]);
    }
    if (covered === 0) continue;
    const inside = covered / c.abs_total;
    const covers = absL > 0 ? covered / absL : 0;
    const kind = classify(inside, covers);
    if (kind) out.push({ flow, kind, inside, covers, rest });
  }
  const rank: Record<MatchKind, number> = { trend: 0, related: 1, overlap: 2 };
  return out.sort((a, b) => rank[a.kind] - rank[b.kind] || b.covers - a.covers || b.inside - a.inside || (a.flow < b.flow ? -1 : 1));
}
