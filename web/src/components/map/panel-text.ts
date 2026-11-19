/**
 * Pure text helpers of the flow detail panel (PLAN §4.7, §3.4.4): no React, no Next.
 */
import type { Entry, Label, SeriesFlow, TotalLabel } from "@/data/types";
import { formatPct } from "@/lib/format";

/** The part of the map labels the text helpers need. */
export type RefLabels = { text: { refs: Record<string, { label: string } | undefined> } };

export const DISC_ACCOUNT = "X_DISC";

/**
 * The message key of an X_DISC entry (pipeline/export/disc_text.yaml): by ref, and for D3 by
 * component. Null for an entry outside X_DISC; an X_DISC entry that matches no key is logged.
 */
export function discKeyOf(e: Pick<Entry, "row" | "col" | "ref" | "component">): string | null {
  if (e.row !== DISC_ACCOUNT && e.col !== DISC_ACCOUNT) return null;
  if (e.ref === "D3") {
    if (e.component === "unsectored_valuables") return "D3_valuables";
    if (e.component === "si_errors") return "D3_si_errors";
  } else if (["D1", "D2", "D4"].includes(e.ref)) return e.ref;
  console.error(`[map] no discrepancy text for X_DISC entry ${e.ref}.${e.component}`);
  return null;
}

/** "Mostly {ref} (x%), {ref} (y%)…" from the entries' absolute values by ref. */
export function composeText(entries: Entry[], L: RefLabels, t: (k: string, v?: Record<string, string>) => string): string | null {
  if (!entries.length) return null;
  const by = new Map<string, number>();
  let total = 0;
  for (const e of entries) {
    by.set(e.ref, (by.get(e.ref) ?? 0) + Math.abs(e.v));
    total += Math.abs(e.v);
  }
  if (!(total > 0)) return null;
  const items = [...by.entries()]
    .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))
    .slice(0, 3)
    .map(([ref, v]) => t("composedItem", { label: L.text.refs[ref]?.label ?? ref, share: formatPct(v / total) }));
  return t("composed", { items: items.join(", ") });
}


export type SamPoint = { value: number; share: number } | null;

/**
 * The SAM's value for a series, signed like the series is shown (`display_sign`): the exported
 * `sam_value` is in SAM sign (a subsidy is negative), while the drawn line and its shares are
 * display-signed (V1-02).
 */
export function samPointOf(flow: Pick<SeriesFlow, "check" | "display_sign">, gdp: number): SamPoint {
  if (flow.check.sam_value === null) return null;
  const value = flow.check.sam_value * flow.display_sign;
  return { value, share: value / gdp };
}

/**
 * A single series value is its own total when it is official or derived: the story evaluator's
 * rule (pipeline/export/stories.py), so a figure reads the same on every page (V1-08).
 */
export function seriesTotal(status: Label | null): TotalLabel | null {
  return status === "official" || status === "derived" ? status : null;
}
