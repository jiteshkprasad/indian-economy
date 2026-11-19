/**
 * Resolving a selection (a link at any zoom, or a node) without knowing the current view: the ids
 * name the nodes, the nodes name their accounts, and the platform's `aggregate` does the sums with
 * the same rules as the map (account cells as atoms, positive and negative parts apart).
 */
import { aggregate, type AggInternal, type AggLink, type Visible } from "@/data/aggregate";
import type { Cells, Hierarchy, Pinned, PresetId } from "@/data/types";
import { parseLinkId } from "@/lib/ids";

const REST = "__REST__";

function mergedAccounts(h: Hierarchy, members: readonly string[]): string[] | null {
  const out: string[] = [];
  for (const m of members) {
    const mn = h.nodes.find((x) => x.id === m);
    if (!mn) return null;
    out.push(...mn.accounts);
  }
  return out;
}

/**
 * Where a selection is drawn: a preset of the SAM map (the effective one: "full" once anything is
 * expanded) or the top-flows board ("ts"). The same id can name different accounts in each.
 */
export type NodeScope = PresetId | "ts";

/**
 * Accounts of a node as drawn in `scope`: that scope's own nodes come first, because an id can name
 * a merged node there (the simple preset's SI and the board's SI are SI + FINM) and a hierarchy node
 * elsewhere. Then the hierarchy node, any preset's merge (PRODUCERS) and a top-flows node (GOV).
 */
export function nodeAccounts(h: Hierarchy, id: string, scope?: NodeScope): string[] | null {
  if (scope === "ts") {
    const ts = h.ts_nodes.find((x) => x.id === id);
    if (ts) return [...ts.accounts];
  }
  const own = scope && scope !== "ts" ? h.presets[scope]?.merges[id] : undefined;
  if (own) return mergedAccounts(h, own);
  const n = h.nodes.find((x) => x.id === id);
  if (n) return [...n.accounts];
  for (const p of Object.values(h.presets)) {
    const members = p.merges[id];
    if (members) return mergedAccounts(h, members);
  }
  const ts = h.ts_nodes.find((x) => x.id === id);
  return ts ? [...ts.accounts] : null;
}

function twoNodeVisible(h: Hierarchy, groups: Array<[string, string[]]>): Visible {
  const accountToNode: string[] = h.accounts.map(() => REST);
  const members: Record<string, string[]> = { [REST]: [] };
  const idx = new Map(h.accounts.map((a) => [a.code, a.idx]));
  for (const [id, accounts] of groups) {
    members[id] = accounts;
    for (const a of accounts) {
      const i = idx.get(a);
      if (i === undefined) throw new Error(`select: unknown account ${a}`);
      accountToNode[i] = id;
    }
  }
  for (const a of h.accounts) if (accountToNode[a.idx] === REST) members[REST].push(a.code);
  return { preset: "full", ids: [...groups.map(([id]) => id), REST], accountToNode, members };
}

export type LinkSelection = { kind: "link"; link: AggLink; payerAccounts: string[]; receiverAccounts: string[] };

/**
 * The link `id` (any zoom; `~neg` for the negative part) as drawn in `scope`, or null when it has no cells.
 */
export function resolveLink(h: Hierarchy, cells: Cells, pinned: Pinned, id: string, scope?: NodeScope): LinkSelection | null {
  const p = parseLinkId(id);
  if (!p || p.part === "pair" || p.payer === p.receiver) return null;
  const pa = nodeAccounts(h, p.payer, scope);
  const ra = nodeAccounts(h, p.receiver, scope);
  if (!pa || !ra) return null;
  if (pa.some((a) => ra.includes(a))) return null;
  const vis = twoNodeVisible(h, [
    [p.payer, pa],
    [p.receiver, ra],
  ]);
  const agg = aggregate(cells, h, vis, pinned);
  const link = agg.links.find((l) => l.id === id);
  return link ? { kind: "link", link, payerAccounts: pa, receiverAccounts: ra } : null;
}

export type NodeSelection = {
  kind: "node";
  id: string;
  accounts: string[];
  /** money in from outside the node: positive receipts (pos) and negative receipts (neg) */
  moneyIn: AggLink[];
  moneyOut: AggLink[];
  internal: AggInternal | null;
  /** drawn height in ₹ crore: positive receipts + |negative payments| */
  through: number;
};

/** The node `id` as drawn in `scope`, with its partners and drawn height. */
export function resolveNode(h: Hierarchy, cells: Cells, pinned: Pinned, id: string, scope?: NodeScope): NodeSelection | null {
  const accounts = nodeAccounts(h, id, scope);
  if (!accounts) return null;
  // partners, so "money in / out" says who pays and who is paid: the node's siblings and its
  // ancestors' siblings (e.g. urban households for a rural group), then every other level-0 group
  const byId = new Map(h.nodes.map((n) => [n.id, n]));
  const used = new Set(accounts);
  const groups: Array<[string, string[]]> = [[id, accounts]];
  const add = (gid: string, accs: readonly string[]) => {
    const rest = accs.filter((a) => !used.has(a));
    if (!rest.length) return;
    rest.forEach((a) => used.add(a));
    groups.push([gid, rest]);
  };
  let cur = byId.get(id);
  const topLevel = !cur?.parent;
  while (cur?.parent) {
    const parent = byId.get(cur.parent);
    if (!parent) break;
    for (const sib of parent.children) if (sib !== cur.id) add(sib, byId.get(sib)?.accounts ?? []);
    cur = parent;
  }
  // a top-level node: its partners are the nodes drawn beside it (the preset's merges such as
  // PRODUCERS, or the board's nodes such as GOV), then the level-0 groups that are left
  if (topLevel) {
    if (scope === "ts") for (const n of h.ts_nodes) add(n.id, n.accounts);
    else if (scope) for (const [mid, members] of Object.entries(h.presets[scope]?.merges ?? {})) add(mid, mergedAccounts(h, members) ?? []);
  }
  for (const n of [...h.nodes].filter((x) => x.level === 0).sort((a, b) => a.order - b.order)) add(n.id, n.accounts);
  const vis = twoNodeVisible(h, groups);
  const agg = aggregate(cells, h, vis, pinned);
  const moneyIn = agg.links.filter((l) => l.receiver === id);
  const moneyOut = agg.links.filter((l) => l.payer === id);
  const through =
    moneyIn.filter((l) => l.part === "pos").reduce((a, l) => a + l.value, 0) +
    moneyOut.filter((l) => l.part === "neg").reduce((a, l) => a + Math.abs(l.value), 0);
  // cells inside PRDS stay internal at every zoom: aggregate files them under "PRDS"
  const internal = agg.internal[id] ?? null;
  return { kind: "node", id, accounts, moneyIn, moneyOut, internal, through };
}

/** Level-0 ids whose entry files hold the given receiving accounts (entries are filed by row). */
export function entryFilesFor(h: Hierarchy, receiverAccounts: readonly string[]): string[] {
  const l0 = new Set<string>();
  for (const a of h.accounts) if (receiverAccounts.includes(a.code)) l0.add(a.l0);
  const order = new Map(h.nodes.map((n) => [n.id, n.order]));
  return [...l0].sort((a, b) => (order.get(a) ?? 0) - (order.get(b) ?? 0));
}
