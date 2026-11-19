/**
 * Aggregation of account cells to visible nodes, PLAN §4.4 and §4.5.3.
 *
 * The account cell is the atom. For each directed pair of visible nodes, positive
 * cells sum into one link ("<payer>--<receiver>") and negative cells into another
 * ("<payer>--<receiver>~neg"), each with abs-by-label, OR'd flags and refs. Cells
 * whose two ends fall in the same visible node are internal to that node; cells
 * with both ends inside PRDS (trade and transport margins, intermediate product
 * flows) stay internal at every zoom. Total labels come from pinned.json.
 *
 * Rows receive, columns pay: cell (row r, col c) is money paid by account c to account r.
 */
import { linkId, type LinkPart } from "@/lib/ids";
import { composition, headlineSplitAbs } from "@/lib/status";
import type { Cells, Composition, Hierarchy, HierarchyNode, Label, Pinned, PresetId, TotalLabel } from "./types";

export type Visible = {
  preset: PresetId;
  /** visible node ids in hierarchy order (merged preset nodes take their first member's place) */
  ids: string[];
  /** visible node id for each account index */
  accountToNode: string[];
  /** accounts in each visible node */
  members: Record<string, string[]>;
};

export type AbsByLabel = { o: number; d: number; e: number; b: number };

export type AggLink = {
  id: string;
  payer: string;
  receiver: string;
  part: Exclude<LinkPart, "pair">;
  /** signed sum of the cells (negative for the ~neg part) */
  value: number;
  abs: AbsByLabel;
  composition: Composition | null;
  split: Label | null;
  flags: number;
  refs: string[];
  cells: number[];
  n_cells: number;
  n_entries: number;
  total: TotalLabel | null;
  pins: string[];
  /** pin on the whole pair ("<id>~pair"), when the parts are only held together */
  pair: { total: TotalLabel; pins: string[] } | null;
};

export type AggInternal = {
  node: string;
  pos: number;
  neg: number;
  abs: AbsByLabel;
  flags: number;
  refs: string[];
  cells: number[];
};

export type Aggregate = { links: AggLink[]; internal: Record<string, AggInternal> };

const PRDS = "PRDS";

function nodeIndex(h: Hierarchy): Map<string, HierarchyNode> {
  return new Map(h.nodes.map((n) => [n.id, n]));
}

/** Adds every ancestor of an expanded id and returns the set in hierarchy order. */
export function normaliseExpanded(h: Hierarchy, expanded: readonly string[]): string[] {
  const byId = nodeIndex(h);
  const set = new Set<string>();
  for (const id of expanded) {
    let n = byId.get(id);
    while (n) {
      if (n.expandable) set.add(n.id);
      n = n.parent ? byId.get(n.parent) : undefined;
    }
  }
  return h.nodes.filter((n) => set.has(n.id)).sort((a, b) => a.order - b.order).map((n) => n.id);
}

/**
 * The visible nodes for a preset and a set of expanded nodes. Expanding anything
 * switches to the full preset first (PLAN §3.2), so zoom always starts from the 13 groups.
 */
export function visibleNodes(h: Hierarchy, preset: PresetId, expanded: readonly string[] = []): Visible {
  const byId = nodeIndex(h);
  const exp = new Set(normaliseExpanded(h, expanded));
  const effPreset: PresetId = exp.size > 0 ? "full" : preset;
  const roots = h.nodes.filter((n) => n.level === 0).sort((a, b) => a.order - b.order);
  const out: HierarchyNode[] = [];
  const walk = (n: HierarchyNode) => {
    if (exp.has(n.id) && n.children.length > 0) {
      const kids = n.children
        .map((c) => byId.get(c))
        .filter((c): c is HierarchyNode => !!c)
        .sort((a, b) => a.order - b.order);
      kids.forEach(walk);
    } else out.push(n);
  };
  roots.forEach(walk);

  const accIdx = new Map(h.accounts.map((a) => [a.code, a.idx]));
  const accountToNode: string[] = new Array(h.accounts.length);
  const members: Record<string, string[]> = {};
  let ids = out.map((n) => n.id);
  for (const n of out) {
    members[n.id] = [...n.accounts];
  }
  const merges = h.presets[effPreset]?.merges ?? {};
  for (const [mergedId, parts] of Object.entries(merges)) {
    const present = parts.filter((p) => members[p]);
    if (present.length === 0) continue;
    const accounts = present.flatMap((p) => members[p]);
    const firstPos = Math.min(...present.map((p) => ids.indexOf(p)));
    for (const p of present) delete members[p];
    ids = ids.filter((id) => !present.includes(id));
    ids.splice(Math.min(firstPos, ids.length), 0, mergedId);
    members[mergedId] = accounts;
  }
  for (const id of ids) {
    for (const code of members[id]) {
      const i = accIdx.get(code);
      if (i === undefined) throw new Error(`visibleNodes: account ${code} of node ${id} is not in hierarchy.accounts`);
      accountToNode[i] = id;
    }
  }
  for (let i = 0; i < accountToNode.length; i++) {
    if (accountToNode[i] === undefined) {
      throw new Error(`visibleNodes: account ${h.accounts[i]?.code ?? i} belongs to no visible node`);
    }
  }
  return { preset: effPreset, ids, accountToNode, members };
}

const zeroAbs = (): AbsByLabel => ({ o: 0, d: 0, e: 0, b: 0 });

type RefWeights = Map<string, { w: number; first: number }>;

function addRefs(weights: RefWeights, refs: readonly string[], w: number, seq: number) {
  for (const r of refs) {
    const cur = weights.get(r);
    if (cur) cur.w += w;
    else weights.set(r, { w, first: seq });
  }
}

/** Refs ordered by the total |value| of the cells they appear in, then first appearance. */
function orderedRefs(weights: RefWeights): string[] {
  return [...weights.entries()].sort((a, b) => b[1].w - a[1].w || a[1].first - b[1].first).map(([r]) => r);
}

/** Aggregates the cells to the visible nodes. Deterministic order: payer, receiver (visible order), pos before neg. */
export function aggregate(cells: Cells, h: Hierarchy, visible: Visible, pinned: Pinned = {}): Aggregate {
  const isPrds = h.accounts.map((a) => a.l0 === PRDS);
  type Acc = {
    payer: string;
    receiver: string;
    part: "pos" | "neg";
    value: number;
    abs: AbsByLabel;
    flags: number;
    refs: RefWeights;
    cells: number[];
    n_entries: number;
  };
  const links = new Map<string, Acc>();
  const internal: Record<string, AggInternal & { _refs: RefWeights }> = {};
  for (let i = 0; i < cells.n; i++) {
    const v = cells.v[i];
    if (v === 0) continue;
    const r = cells.row[i];
    const c = cells.col[i];
    const payer = visible.accountToNode[c];
    const receiver = visible.accountToNode[r];
    const bothPrds = isPrds[r] && isPrds[c];
    if (payer === receiver || bothPrds) {
      const key = payer === receiver ? payer : PRDS;
      const it = (internal[key] ??= { node: key, pos: 0, neg: 0, abs: zeroAbs(), flags: 0, refs: [], cells: [], _refs: new Map() });
      if (v > 0) it.pos += v;
      else it.neg += v;
      it.abs.o += cells.abs_o[i];
      it.abs.d += cells.abs_d[i];
      it.abs.e += cells.abs_e[i];
      it.abs.b += cells.abs_b[i];
      it.flags |= cells.flags[i];
      it.cells.push(i);
      addRefs(it._refs, cells.refs[i], Math.abs(v), i);
      continue;
    }
    const part = v > 0 ? "pos" : "neg";
    const id = linkId(payer, receiver, part);
    let acc = links.get(id);
    if (!acc) {
      acc = { payer, receiver, part, value: 0, abs: zeroAbs(), flags: 0, refs: new Map(), cells: [], n_entries: 0 };
      links.set(id, acc);
    }
    acc.value += v;
    acc.abs.o += cells.abs_o[i];
    acc.abs.d += cells.abs_d[i];
    acc.abs.e += cells.abs_e[i];
    acc.abs.b += cells.abs_b[i];
    acc.flags |= cells.flags[i];
    acc.cells.push(i);
    acc.n_entries += cells.n_entries[i];
    addRefs(acc.refs, cells.refs[i], Math.abs(v), i);
  }
  const pos = new Map(visible.ids.map((id, k) => [id, k]));
  const out: AggLink[] = [...links.entries()]
    .map(([id, a]) => {
      const comp = composition(a.abs.o, a.abs.d, a.abs.e, a.abs.b);
      const pin = pinned[id] ?? null;
      const pairPin = pinned[linkId(a.payer, a.receiver, "pair")] ?? null;
      return {
        id,
        payer: a.payer,
        receiver: a.receiver,
        part: a.part,
        value: a.value,
        abs: a.abs,
        composition: comp,
        split: headlineSplitAbs(a.abs),
        flags: a.flags,
        refs: orderedRefs(a.refs),
        cells: a.cells,
        n_cells: a.cells.length,
        n_entries: a.n_entries,
        total: pin?.total ?? null,
        pins: pin?.pins ?? [],
        pair: pairPin,
      } satisfies AggLink;
    })
    .sort(
      (x, y) =>
        (pos.get(x.payer) ?? 0) - (pos.get(y.payer) ?? 0) ||
        (pos.get(x.receiver) ?? 0) - (pos.get(y.receiver) ?? 0) ||
        (x.part === "pos" ? 0 : 1) - (y.part === "pos" ? 0 : 1),
    );
  const internalOut: Record<string, AggInternal> = {};
  for (const [k, it] of Object.entries(internal)) {
    const { _refs, ...rest } = it;
    internalOut[k] = { ...rest, refs: orderedRefs(_refs) };
  }
  return { links: out, internal: internalOut };
}

/**
 * Drawn inflow and outflow of each visible node (PLAN §4.5.3): inflow = positive
 * receipts + |negative payments| (reversed links arrive at the payer); outflow =
 * positive payments + |negative receipts|. They are equal when every account balances.
 */
export function nodeFlows(links: readonly AggLink[]): Record<string, { inflow: number; outflow: number }> {
  const out: Record<string, { inflow: number; outflow: number }> = {};
  const get = (id: string) => (out[id] ??= { inflow: 0, outflow: 0 });
  for (const l of links) {
    const w = Math.abs(l.value);
    if (l.part === "pos") {
      get(l.payer).outflow += w;
      get(l.receiver).inflow += w;
    } else {
      get(l.receiver).outflow += w;
      get(l.payer).inflow += w;
    }
  }
  return out;
}
