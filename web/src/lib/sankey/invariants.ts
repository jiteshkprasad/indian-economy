/**
 * Layout invariants (PLAN §4.5, unit tests). Each check returns a list of human-readable violations
 * (empty = pass), so a test failure names what broke.
 */
import { GEOMETRY } from "./style";
import { crosses, sampleRibbon, sampleRoute, segments } from "./geometry";
import type { Layout, NodeBox } from "./types";

const EPS = 0.01;

/**
 * Σ drawn inflow widths = Σ drawn outflow widths = node height; split copies equal; ports fill the node.
 * `equalCopies` limits the copy check to those ids: the level-0 split node (PRDS, PRODUCERS) balances,
 * but its children do not on their own, because trade margins circulate inside product markets and
 * stay internal at every zoom (PLAN §4.5.7); their two copies differ by that internal flow.
 */
export function balanceViolations(L: Layout, fixedHeights = false, equalCopies?: ReadonlySet<string>): string[] {
  const out: string[] = [];
  const byKey = new Map(L.nodes.map((n) => [n.key, n]));
  for (const n of L.nodes) {
    const ins = L.links.filter((l) => l.targetKey === n.key);
    const outs = L.links.filter((l) => l.sourceKey === n.key);
    const inW = ins.reduce((s, l) => s + l.width, 0);
    const outW = outs.reduce((s, l) => s + l.width, 0);
    if (Math.abs(inW - n.inSum) > EPS || Math.abs(outW - n.outSum) > EPS) out.push(`${n.key}: sums disagree`);
    if (!fixedHeights) {
      if (n.copy === "only" && Math.abs(inW - outW) > EPS) out.push(`${n.key}: in ${inW} ≠ out ${outW}`);
      if (n.copy !== "in" && outs.length && Math.abs(outW - n.h) > EPS) out.push(`${n.key}: out ${outW} ≠ h ${n.h}`);
      if (n.copy !== "out" && ins.length && Math.abs(inW - n.h) > EPS) out.push(`${n.key}: in ${inW} ≠ h ${n.h}`);
    } else if (inW > n.h + EPS || outW > n.h + EPS) {
      out.push(`${n.key}: flows exceed the slot`);
    }
    // ports: contiguous, inside the node, ending at the sum
    const portEnd = (ps: Array<{ y0: number; y1: number }>) => (ps.length ? Math.max(...ps.map((p) => p.y1)) : n.y);
    const sEnd = portEnd(outs.map((l) => l.sPort));
    const tEnd = portEnd(ins.map((l) => l.tPort));
    if (fixedHeights) {
      // reserved ports: each port lies inside the slot
      const bad = [...outs.map((l) => l.sPort), ...ins.map((l) => l.tPort)].some((p) => p.y0 < n.y - EPS || p.y1 > n.y + n.h + EPS);
      if (bad) out.push(`${n.key}: a port lies outside the slot`);
    } else {
      if (outs.length && Math.abs(sEnd - (n.y + outW)) > EPS) out.push(`${n.key}: right ports end at ${sEnd}`);
      if (ins.length && Math.abs(tEnd - (n.y + inW)) > EPS) out.push(`${n.key}: left ports end at ${tEnd}`);
    }
  }
  // the split node's two copies have the same height
  for (const n of L.nodes) {
    if (n.copy !== "out" || (equalCopies && !equalCopies.has(n.id))) continue;
    const twin = byKey.get(`${n.id}@in`);
    if (twin && !fixedHeights && Math.abs(twin.h - n.h) > EPS) out.push(`${n.id}: copies ${n.h} ≠ ${twin.h}`);
  }
  return out;
}

/** Every link is classed forward / same-column / return by the column rule. */
export function classViolations(L: Layout): string[] {
  const byKey = new Map(L.nodes.map((n) => [n.key, n]));
  const out: string[] = [];
  for (const l of L.links) {
    const sc = byKey.get(l.sourceKey)!.col;
    const tc = byKey.get(l.targetKey)!.col;
    const want = tc > sc ? "forward" : tc === sc ? "same" : "return";
    if (l.cls !== want) out.push(`${l.id}: ${l.cls} ≠ ${want}`);
  }
  return out;
}

/** No NaN or infinite coordinate anywhere. */
export function nanViolations(L: Layout): string[] {
  const out: string[] = [];
  const bad = (v: number) => !Number.isFinite(v);
  for (const n of L.nodes) if ([n.x, n.y, n.w, n.h].some(bad)) out.push(`node ${n.key}`);
  for (const l of L.links) {
    if ([l.width, l.sPort.y0, l.tPort.y0].some(bad) || /NaN|Infinity/.test(l.d)) out.push(`link ${l.id}`);
    if (l.stations.some((s) => [s.x0, s.x1, s.y].some(bad))) out.push(`stations ${l.id}`);
    if (l.route.some((p) => bad(p.x) || bad(p.y))) out.push(`route ${l.id}`);
  }
  if ([L.width, L.height].some(bad)) out.push("size");
  return out;
}

function inside(n: NodeBox, x: number, y: number): boolean {
  const h = Math.max(n.h, GEOMETRY.minNodeH);
  return x > n.x + EPS && x < n.x + n.w - EPS && y > n.y + EPS && y < n.y + h - EPS;
}

/** No drawn ribbon passes through a node rectangle that is not one of its endpoints. */
export function throughNodeViolations(L: Layout): string[] {
  const out: string[] = [];
  for (const l of L.links) {
    if (!l.drawn || l.stub) continue;
    const pts = l.cls === "forward" ? sampleRibbon(l.stations, l.width) : sampleRoute(l.route, l.width);
    for (const n of L.nodes) {
      if (n.key === l.sourceKey || n.key === l.targetKey) continue;
      if (pts.some((p) => inside(n, p.x, p.y))) out.push(`${l.id} passes through ${n.key}`);
    }
  }
  return out;
}

/** Crossings between the centrelines of return arcs (drawn, arc mode). */
export function returnCrossings(L: Layout): number {
  const arcs = L.links.filter((l) => l.cls === "return" && l.drawn && !l.stub);
  let n = 0;
  for (let i = 0; i < arcs.length; i++) {
    const si = segments(arcs[i].route);
    for (let j = i + 1; j < arcs.length; j++) {
      const sj = segments(arcs[j].route);
      for (const a of si) for (const b of sj) if (crosses(a, b)) n++;
    }
  }
  return n;
}

/**
 * The fewest return-arc crossings any lane order allows, given the ports (the floor the layout is
 * held to). Two arcs must cross once when their column spans overlap without nesting (touching at
 * one column counts as overlapping, because one arc's lane reaches the gutter where the other
 * drops). Two arcs leaving (or entering) the same column from different nodes must also cross once
 * when the arc on the outer lane starts (or ends) at the lower node. Nested or disjoint spans
 * need not cross, and the layout draws them without crossings.
 */
export function returnCrossingFloor(L: Layout): number {
  const byKey = new Map(L.nodes.map((n) => [n.key, n]));
  const arcs = L.links
    .filter((l) => l.cls === "return" && l.drawn && !l.stub && l.lane !== null)
    .map((l) => ({
      a: byKey.get(l.targetKey)!.col,
      b: byKey.get(l.sourceKey)!.col,
      sKey: l.sourceKey,
      tKey: l.targetKey,
      sy: byKey.get(l.sourceKey)!.y,
      ty: byKey.get(l.targetKey)!.y,
      lane: l.lane!,
    }));
  let n = 0;
  for (let i = 0; i < arcs.length; i++) {
    for (let j = i + 1; j < arcs.length; j++) {
      const p = arcs[i];
      const q = arcs[j];
      const partial = (p.a < q.a && q.a <= p.b && p.b < q.b) || (q.a < p.a && p.a <= q.b && q.b < p.b);
      if (partial) {
        n++;
        continue;
      }
      const [inner, outer] = p.lane < q.lane ? [p, q] : [q, p];
      if (inner.b === outer.b && inner.sKey !== outer.sKey && outer.sy > inner.sy) n++;
      if (inner.a === outer.a && inner.tKey !== outer.tKey && outer.ty > inner.ty) n++;
    }
  }
  return n;
}

/** Return lanes nest by span: a longer span is never inside a shorter one. */
export function laneNestingViolations(L: Layout): string[] {
  const byKey = new Map(L.nodes.map((n) => [n.key, n]));
  const arcs = L.links.filter((l) => l.lane !== null);
  const span = (l: (typeof arcs)[number]) => byKey.get(l.sourceKey)!.col - byKey.get(l.targetKey)!.col;
  const out: string[] = [];
  for (const a of arcs) for (const b of arcs) if (span(a) < span(b) && a.lane! > b.lane!) out.push(`${a.id} outside ${b.id}`);
  return out;
}
