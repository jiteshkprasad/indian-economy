/**
 * Labels and flags, PLAN §3.4. pipeline/export/status.py implements the same
 * rules; both pass pipeline/export/golden/status_cases.json.
 */
import type { Composition, Label, SplitCode, TotalLabel } from "@/data/types";

/** Least certain last. Order matters for the headline split label (§3.4.2). */
export const LABELS: readonly Label[] = ["official", "derived", "estimated", "balancing_set"];
export const SPLIT_CODE_LABEL: Record<SplitCode, Label> = { 0: "official", 1: "derived", 2: "estimated", 3: "balancing_set" };
export const LABEL_CODE: Record<Label, SplitCode> = { official: 0, derived: 1, estimated: 2, balancing_set: 3 };

/** The headline split label is the least certain label carrying at least this share of |value|. */
export const HEADLINE_MIN_SHARE = 0.1;

/** pipeline.sam.spec.needs_explanation: moved >= ₹5,000 crore, or >= ₹500 crore and >= 10%. */
export const EXPLAIN_ABS = 5000;
export const EXPLAIN_MIN_ABS = 500;
export const EXPLAIN_REL = 0.1;

export function needsExplanation(prior: number, balanced: number): boolean {
  const d = Math.abs(balanced - prior);
  if (d >= EXPLAIN_ABS) return true;
  return d >= EXPLAIN_MIN_ABS && (prior === 0 || d / Math.abs(prior) >= EXPLAIN_REL);
}

export type EntryLabelInput = {
  role: "fixed" | "anchored" | "free";
  status: "official" | "derived" | "estimated" | "balanced";
  prior_status: "official" | "derived" | "estimated" | string;
  /** balancing_log.explanation_required */
  explanation_required: boolean;
  /** the entry or its cell has a current explanation item (any verdict) */
  has_item: boolean;
  /** member of a binding constraint listed in judgement_bands.yaml */
  in_judgement_band: boolean;
};

export class LabelRuleError extends Error {}

/** §3.4.1, branches in order. An entry matching none throws (the export fails the same way). */
export function entryLabel(e: EntryLabelInput): Label {
  const matters = e.explanation_required || e.has_item || e.in_judgement_band;
  if (e.role === "free" && e.status === "balanced" && matters) return "balancing_set";
  if (e.prior_status === "official") return "official";
  if (e.prior_status === "derived") return "derived";
  if (e.prior_status === "estimated") return "estimated";
  throw new LabelRuleError(`entry matches no label branch: ${JSON.stringify(e)}`);
}

/** Shares of absolute value by entry label (sum 1), or null when everything is zero. */
export function composition(absO: number, absD: number, absE: number, absB: number): Composition | null {
  const t = absO + absD + absE + absB;
  if (!(t > 0)) return null;
  return { o: absO / t, d: absD / t, e: absE / t, b: absB / t };
}

/**
 * §3.4.2 on absolute values (exactly as the golden file states it): with
 * total = o + d + e + b, the least certain label L with abs_L >= 0.1 * total.
 * Null when the total is zero.
 */
export function headlineSplitAbs(abs: { o: number; d: number; e: number; b: number }): Label | null {
  const total = abs.o + abs.d + abs.e + abs.b;
  if (!(total > 0)) return null;
  const by: Record<Label, number> = { official: abs.o, derived: abs.d, estimated: abs.e, balancing_set: abs.b };
  for (let i = LABELS.length - 1; i >= 0; i--) if (by[LABELS[i]] >= HEADLINE_MIN_SHARE * total) return LABELS[i];
  throw new LabelRuleError(`no label carries 10% of ${JSON.stringify(abs)}`);
}

/** §3.4.2 on a composition (shares): the least certain label carrying >= 10%. */
export function headlineSplit(c: Composition): Label {
  const shares: Record<Label, number> = { official: c.o, derived: c.d, estimated: c.e, balancing_set: c.b };
  for (let i = LABELS.length - 1; i >= 0; i--) {
    if (shares[LABELS[i]] >= HEADLINE_MIN_SHARE) return LABELS[i];
  }
  // Unreachable when shares sum to 1 (some label has >= 25%).
  throw new LabelRuleError(`composition does not sum to 1: ${JSON.stringify(c)}`);
}

/** Flag bits on cells and links, §3.4.4. */
export const FLAGS = {
  judgement_band: 1,
  unexplained: 2,
  level_unexplained: 4,
  old_base_structure: 8,
  discrepancy: 16,
  has_negative: 32,
  depends_on_assumption: 64,
} as const;
export type FlagName = keyof typeof FLAGS;
export const FLAG_NAMES = Object.keys(FLAGS) as FlagName[];

export function flagNames(mask: number): FlagName[] {
  return FLAG_NAMES.filter((n) => (mask & FLAGS[n]) !== 0);
}

export function flagMask(names: readonly string[]): number {
  let m = 0;
  for (const n of names) {
    const bit = FLAGS[n as FlagName];
    if (bit === undefined) throw new LabelRuleError(`unknown flag "${n}"`);
    m |= bit;
  }
  return m;
}

/**
 * What a badge says, as message keys in the `common` namespace (status.*):
 *  - no total:                 split label alone              "Estimated"
 *  - total and split the same: total alone                    "Official total"
 *  - otherwise:                total, then split              "Official total · split estimated"
 */
export type BadgeParts = { total: TotalLabel | null; split: Label; sameAsTotal: boolean };

export function badgeParts(total: TotalLabel | null, split: Label): BadgeParts {
  return { total, split, sameAsTotal: total !== null && total === split };
}

/** Plain-text badge (English), used for aria-labels and tests; the UI uses the messages. */
export function badgeText(total: TotalLabel | null, split: Label): string {
  const name: Record<Label, string> = {
    official: "official",
    derived: "derived",
    estimated: "estimated",
    balancing_set: "set by balancing",
  };
  const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
  if (total === null) return cap(name[split]);
  if (total === split) return `${cap(total)} total`;
  return `${cap(total)} total · split ${name[split]}`;
}
