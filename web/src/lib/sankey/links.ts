import type { LayoutLinkInput } from "./types";

/** One directed pair of visible nodes, split into its positive and negative parts (PLAN §4.4). */
export type PairPart = {
  payer: string;
  receiver: string;
  /** Σ of positive account cells (₹ crore, ≥ 0). */
  pos: number;
  /** Σ of negative account cells (₹ crore, ≤ 0). */
  neg: number;
};

/** Link id of the positive part: `<payer>--<receiver>` (PLAN §3.6). */
export function linkId(payer: string, receiver: string, negative = false): string {
  return `${payer}--${receiver}${negative ? "~neg" : ""}`;
}

export type ParsedLinkId = { payer: string; receiver: string; negative: boolean; pair: boolean };

/** Parse `<payer>--<receiver>`, `…~neg` or `…~pair`; null when malformed. */
export function parseLinkId(id: string): ParsedLinkId | null {
  const m = /^(.+?)--(.+?)(~neg|~pair)?$/.exec(id);
  if (!m) return null;
  return { payer: m[1], receiver: m[2], negative: m[3] === "~neg", pair: m[3] === "~pair" };
}

/**
 * Turn pair parts into drawn links. Money flows from the payer (column) to the receiver (row). A
 * positive part is drawn payer → receiver; a negative part is drawn reversed, receiver → payer,
 * with its absolute value (PLAN §4.5.4). Zero parts are omitted.
 */
export function drawnLinks(parts: PairPart[]): LayoutLinkInput[] {
  const out: LayoutLinkInput[] = [];
  for (const p of parts) {
    if (p.payer === p.receiver) continue;
    if (p.pos > 0) out.push({ id: linkId(p.payer, p.receiver), source: p.payer, target: p.receiver, value: p.pos });
    if (p.neg < 0)
      out.push({
        id: linkId(p.payer, p.receiver, true),
        source: p.receiver,
        target: p.payer,
        value: -p.neg,
        reversed: true,
      });
  }
  return out;
}
