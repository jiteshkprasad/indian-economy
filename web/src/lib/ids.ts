/**
 * Ids used across the site (PLAN §3.6).
 *   link id   "<payer>--<receiver>"       positive part
 *             "<payer>--<receiver>~neg"   negative part (drawn reversed)
 *             "<payer>--<receiver>~pair"  the whole pair (pinned.json only)
 * Money flows from the column account (payer) to the row account (receiver).
 */
export const LINK_SEP = "--";
export type LinkPart = "pos" | "neg" | "pair";
export type ParsedLinkId = { payer: string; receiver: string; part: LinkPart };

const NODE_ID_RE = /^[A-Z][A-Z0-9_]*(\.[A-Z][A-Z0-9_]*)?$/;
const LINK_RE = /^([A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)?)--([A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)?)(~neg|~pair)?$/;
const SERIES_RE = /^[FM]\d{2}$/;

export function isNodeIdShape(id: string): boolean {
  return NODE_ID_RE.test(id);
}

export function linkId(payer: string, receiver: string, part: LinkPart = "pos"): string {
  const base = `${payer}${LINK_SEP}${receiver}`;
  return part === "pos" ? base : `${base}~${part}`;
}

export function parseLinkId(id: string): ParsedLinkId | null {
  const m = LINK_RE.exec(id);
  if (!m) return null;
  return { payer: m[1], receiver: m[2], part: m[3] === "~neg" ? "neg" : m[3] === "~pair" ? "pair" : "pos" };
}

export function isLinkId(id: string): boolean {
  return LINK_RE.test(id);
}

/** "A--B~neg" -> "A--B~pair" (the key for a pin on the whole pair). */
export function pairId(id: string): string | null {
  const p = parseLinkId(id);
  return p ? linkId(p.payer, p.receiver, "pair") : null;
}

/** The other part of the same pair: "A--B" <-> "A--B~neg". */
export function siblingId(id: string): string | null {
  const p = parseLinkId(id);
  if (!p || p.part === "pair") return null;
  return linkId(p.payer, p.receiver, p.part === "pos" ? "neg" : "pos");
}

export function isSeriesId(id: string): boolean {
  return SERIES_RE.test(id);
}

/** The reference year of the balanced SAM; the only year with the complete map. */
export const SAM_YEAR = "2023-24";
