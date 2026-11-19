import { StatusBadge } from "@/components/ui";
import { summaryPath } from "@/data/server";
import type { Label, TotalLabel } from "@/data/types";

const LABELS: readonly Label[] = ["official", "derived", "estimated", "balancing_set"];
const TOTALS: readonly TotalLabel[] = ["official", "derived"];

function isLabel(x: unknown): x is Label {
  return typeof x === "string" && (LABELS as readonly string[]).includes(x);
}

/**
 * <SummaryBadge path="gdp"/>: the status badge of a summary.json figure that carries
 * its own status, bound at build time. Two shapes are read, both exported by U1:
 * `{label}` (a single label, e.g. `gdp`) and `{split_label, total_label}` (the
 * headline-part shape, also used by the `methodology.*` items that are economic
 * values). A missing or unknown label fails the build, so a badge is never guessed.
 */
export function SummaryBadge({ path }: { path: string }) {
  const item = summaryPath(path);
  if (!item || typeof item !== "object") {
    throw new Error(`SummaryBadge: summary.json path "${path}" is not an object`);
  }
  const rec = item as { label?: unknown; split_label?: unknown; total_label?: unknown };
  if ("label" in rec) {
    if (!isLabel(rec.label)) throw new Error(`SummaryBadge: "${path}.label" is not a status label`);
    return <StatusBadge total={null} split={rec.label} compact />;
  }
  if (!isLabel(rec.split_label)) {
    throw new Error(`SummaryBadge: "${path}" has no status label (label or split_label)`);
  }
  const total = rec.total_label ?? null;
  if (total !== null && !(TOTALS as readonly unknown[]).includes(total)) {
    throw new Error(`SummaryBadge: "${path}.total_label" is not a total label`);
  }
  return <StatusBadge total={total as TotalLabel | null} split={rec.split_label} compact />;
}
