/**
 * The unrolled circular Sankey layout (PLAN §4.5; proposed D3-5). Pure and deterministic.
 *
 * - Columns are fixed by the caller; the split node is drawn twice (payer copy, receiver copy).
 * - Node order inside a column is the hierarchy order.
 * - A node's height is the sum of its drawn inflow widths, which equals the sum of its drawn outflow
 *   widths because every account balances; widths are a share of GDP with one constant scale.
 * - Forward links skipping columns pass through reserved gutters between nodes; same-column links
 *   are side arcs through the gap next to their target; return links are nested lanes under the
 *   diagram (or stubs in the simple preset).
 */
import { GEOMETRY, MIN_DRAW_PX } from "./style";
import { ribbonD, routeOutlineD, f2 } from "./geometry";
import type {
  LaidLink,
  Layout,
  LayoutLinkInput,
  LayoutNodeInput,
  LayoutOptions,
  LinkClass,
  NodeBox,
  Pt,
  Station,
} from "./types";

type WLink = {
  inp: LayoutLinkInput;
  id: string;
  sourceKey: string;
  targetKey: string;
  sc: number;
  tc: number;
  so: number;
  to: number;
  cls: LinkClass;
  width: number;
  reserve: number;
  drawn: boolean;
  routed: boolean;
  stub: boolean;
  lane: number | null;
  sOff: number;
  tOff: number;
  rsOff: number;
  rtOff: number;
  gaps: Array<{ col: number; gap: number }>;
};

const CLS_RANK: Record<LinkClass, number> = { forward: 0, same: 1, return: 2 };

function cmpStr(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/** Return-lane order: innermost first (shorter span, then narrower, then id). */
function laneCmp(a: WLink, b: WLink): number {
  const sa = a.sc - a.tc;
  const sb = b.sc - b.tc;
  if (sa !== sb) return sa - sb;
  if (a.reserve !== b.reserve) return a.reserve - b.reserve;
  return cmpStr(a.id, b.id);
}

export function layoutSankey(nodesIn: LayoutNodeInput[], linksIn: LayoutLinkInput[], opts: LayoutOptions): Layout {
  const G = GEOMETRY;
  if (!(opts.gdp > 0)) throw new Error("layoutSankey: GDP must be positive");
  const unit = (opts.pxPerPct * 100) / opts.gdp;

  // ---- nodes and their copies -------------------------------------------------------------
  const byId = new Map<string, LayoutNodeInput>();
  for (const n of nodesIn) {
    if (byId.has(n.id)) throw new Error(`layoutSankey: duplicate node ${n.id}`);
    byId.set(n.id, n);
  }
  type Copy = { key: string; node: LayoutNodeInput; col: number; copy: NodeBox["copy"] };
  const copies: Copy[] = [];
  for (const n of nodesIn) {
    if (n.inCol !== undefined && n.inCol !== n.col) {
      copies.push({ key: `${n.id}@out`, node: n, col: n.col, copy: "out" });
      copies.push({ key: `${n.id}@in`, node: n, col: n.inCol, copy: "in" });
    } else {
      copies.push({ key: n.id, node: n, col: n.col, copy: "only" });
    }
  }
  const copyByKey = new Map(copies.map((c) => [c.key, c]));
  const ncols = Math.max(0, ...copies.map((c) => c.col)) + 1;
  const outKey = (id: string) => {
    const n = byId.get(id);
    if (!n) throw new Error(`layoutSankey: unknown node ${id}`);
    return n.inCol !== undefined && n.inCol !== n.col ? `${id}@out` : id;
  };
  const inKey = (id: string) => {
    const n = byId.get(id);
    if (!n) throw new Error(`layoutSankey: unknown node ${id}`);
    return n.inCol !== undefined && n.inCol !== n.col ? `${id}@in` : id;
  };

  // ---- links ------------------------------------------------------------------------------
  const seen = new Set<string>();
  const links: WLink[] = linksIn.map((inp) => {
    if (seen.has(inp.id)) throw new Error(`layoutSankey: duplicate link ${inp.id}`);
    seen.add(inp.id);
    if (inp.source === inp.target) throw new Error(`layoutSankey: link ${inp.id} is internal to ${inp.source}`);
    if (!(inp.value >= 0) || !Number.isFinite(inp.value)) throw new Error(`layoutSankey: bad value on ${inp.id}`);
    const sourceKey = outKey(inp.source);
    const targetKey = inKey(inp.target);
    const sc = copyByKey.get(sourceKey)!.col;
    const tc = copyByKey.get(targetKey)!.col;
    const cls: LinkClass = tc > sc ? "forward" : tc === sc ? "same" : "return";
    const width = inp.value * unit;
    const reserve = Math.max(width, (inp.reserve ?? inp.value) * unit);
    const drawn = width >= MIN_DRAW_PX;
    const routed = (opts.reservePorts ? reserve : width) >= MIN_DRAW_PX;
    return {
      inp,
      id: inp.id,
      sourceKey,
      targetKey,
      sc,
      tc,
      so: byId.get(inp.source)!.order,
      to: byId.get(inp.target)!.order,
      cls,
      width,
      reserve: opts.reservePorts ? reserve : width,
      drawn,
      routed,
      // the simple preset draws return and same-column links as labelled stubs (PLAN §4.5.6)
      stub: (cls === "return" || cls === "same") && opts.returnFlows === "stubs",
      lane: null,
      sOff: 0,
      tOff: 0,
      rsOff: 0,
      rtOff: 0,
      gaps: [],
    };
  });

  // ---- return lanes (depend on spans and widths only) ---------------------------------------
  const arcs = links.filter((l) => l.cls === "return" && !l.stub && l.routed).sort(laneCmp);
  arcs.forEach((l, i) => (l.lane = i));

  // ---- ports --------------------------------------------------------------------------------
  const outs = new Map<string, WLink[]>();
  const ins = new Map<string, WLink[]>();
  for (const c of copies) {
    outs.set(c.key, []);
    ins.set(c.key, []);
  }
  for (const l of links) {
    outs.get(l.sourceKey)!.push(l);
    ins.get(l.targetKey)!.push(l);
  }
  const outCmp = (a: WLink, b: WLink) => {
    if (a.cls !== b.cls) return CLS_RANK[a.cls] - CLS_RANK[b.cls];
    if (a.cls === "return") return -laneCmp(a, b); // outermost lane at the top
    if (a.tc !== b.tc) return a.tc - b.tc;
    if (a.to !== b.to) return a.to - b.to;
    return cmpStr(a.id, b.id);
  };
  const inCmp = (a: WLink, b: WLink) => {
    if (a.cls !== b.cls) return CLS_RANK[a.cls] - CLS_RANK[b.cls];
    if (a.cls === "return") return -laneCmp(a, b);
    if (a.sc !== b.sc) return a.sc - b.sc;
    if (a.so !== b.so) return a.so - b.so;
    return cmpStr(a.id, b.id);
  };
  const inSum = new Map<string, number>();
  const outSum = new Map<string, number>();
  const rInSum = new Map<string, number>();
  const rOutSum = new Map<string, number>();
  for (const c of copies) {
    let o = 0;
    let ro = 0;
    for (const l of outs.get(c.key)!.sort(outCmp)) {
      l.sOff = o;
      l.rsOff = ro;
      o += l.width;
      ro += l.reserve;
    }
    let i = 0;
    let ri = 0;
    for (const l of ins.get(c.key)!.sort(inCmp)) {
      l.tOff = i;
      l.rtOff = ri;
      i += l.width;
      ri += l.reserve;
    }
    outSum.set(c.key, o);
    inSum.set(c.key, i);
    rOutSum.set(c.key, ro);
    rInSum.set(c.key, ri);
  }
  const heightOf = (c: Copy): number => {
    const flows =
      c.copy === "out"
        ? opts.reservePorts
          ? rOutSum.get(c.key)!
          : outSum.get(c.key)!
        : c.copy === "in"
          ? opts.reservePorts
            ? rInSum.get(c.key)!
            : inSum.get(c.key)!
          : opts.reservePorts
            ? Math.max(rInSum.get(c.key)!, rOutSum.get(c.key)!)
            : Math.max(inSum.get(c.key)!, outSum.get(c.key)!);
    const fixed = opts.fixedHeights?.[c.node.id];
    // A fixed slot (top-flows board) is a floor: with reserved ports every ribbon keeps the room of
    // its own largest year, and those maxima can add up to more than any single year's total.
    if (fixed !== undefined) return opts.reservePorts ? Math.max(fixed, flows) : fixed;
    return flows;
  };
  const H = new Map(copies.map((c) => [c.key, heightOf(c)]));

  // ---- columns ------------------------------------------------------------------------------
  const columns: string[][] = Array.from({ length: ncols }, () => []);
  for (const c of [...copies].sort((a, b) => a.node.order - b.node.order || cmpStr(a.key, b.key))) {
    columns[c.col].push(c.key);
  }
  const indexInCol = new Map<string, number>();
  columns.forEach((keys) => keys.forEach((k, i) => indexInCol.set(k, i)));

  // ---- vertical channels beside each column and x positions ---------------------------------
  const sameLinks = links.filter((l) => l.cls === "same" && l.drawn && !l.stub);
  const rightCh: WLink[][] = Array.from({ length: ncols }, () => []);
  const leftCh: WLink[][] = Array.from({ length: ncols }, () => []);
  for (const l of [...sameLinks].sort((a, b) => a.so - b.so || a.to - b.to || cmpStr(a.id, b.id))) {
    rightCh[l.sc].push(l);
    leftCh[l.tc].push(l);
  }
  for (const l of arcs) {
    rightCh[l.sc].push(l);
    leftCh[l.tc].push(l);
  }
  const rightOff = new Map<string, number>();
  const leftOff = new Map<string, number>();
  const rightNeed: number[] = [];
  const leftNeed: number[] = [];
  for (let c = 0; c < ncols; c++) {
    let off = G.channelInset;
    for (const l of rightCh[c]) {
      rightOff.set(l.id, off + l.reserve / 2);
      off += l.reserve + G.bandPad;
    }
    rightNeed[c] = rightCh[c].length ? off : 0;
    off = G.channelInset;
    for (const l of leftCh[c]) {
      leftOff.set(l.id, off + l.reserve / 2);
      off += l.reserve + G.bandPad;
    }
    leftNeed[c] = leftCh[c].length ? off : 0;
  }
  const hasStubs = links.some((l) => l.stub && l.drawn);
  const stubNeed = hasStubs ? G.stubLength + 4 : 0;
  const colX: number[] = [];
  let x = G.marginX + leftNeed[0];
  for (let c = 0; c < ncols; c++) {
    colX.push(x);
    if (c < ncols - 1) {
      const need = Math.max(rightNeed[c], stubNeed) + Math.max(leftNeed[c + 1], stubNeed) + 48;
      x += G.nodeWidth + Math.max(G.minColGap, need);
    }
  }
  const width = colX[ncols - 1] + G.nodeWidth + Math.max(rightNeed[ncols - 1], stubNeed) + G.marginX;

  // ---- vertical positions with gutter reservations -------------------------------------------
  // Same-column bands pass through the gap next to their target, on the source's side.
  for (const l of sameLinks) {
    const si = indexInCol.get(l.sourceKey)!;
    const ti = indexInCol.get(l.targetKey)!;
    l.gaps = [{ col: l.tc, gap: si < ti ? ti : ti + 1 }];
  }
  const skipping = links.filter((l) => l.cls === "forward" && l.routed && l.tc - l.sc >= 2);
  const Y = new Map<string, number>();
  let colTop: number[] = [];
  let colH: number[] = [];
  const idealY = new Map<string, number>(); // `${id}|${col}` -> y

  const place = () => {
    // gap band sums
    const gapSum: number[][] = columns.map((keys) => new Array(keys.length + 1).fill(0));
    for (const l of [...skipping, ...sameLinks]) {
      for (const g of l.gaps) gapSum[g.col][g.gap] += l.reserve + G.bandPad;
    }
    colH = columns.map((keys, c) => {
      let h = 0;
      keys.forEach((k, i) => {
        h += (gapSum[c][i] ? gapSum[c][i] + G.bandPad : 0) + G.labelSpace + Math.max(H.get(k)!, G.minNodeH);
      });
      const last = gapSum[c][keys.length];
      h += (last ? last + G.bandPad : 0) + G.bottomPad;
      return h;
    });
    const hMax = Math.max(0, ...colH);
    colTop = colH.map((h) => G.marginTop + (hMax - h) / 2);
    columns.forEach((keys, c) => {
      let y = colTop[c];
      keys.forEach((k, i) => {
        y += (gapSum[c][i] ? gapSum[c][i] + G.bandPad : 0) + G.labelSpace;
        Y.set(k, y);
        y += Math.max(H.get(k)!, G.minNodeH);
      });
    });
  };
  const assign = () => {
    for (const l of skipping) {
      const ys = Y.get(l.sourceKey)! + l.rsOff + l.reserve / 2;
      const yt = Y.get(l.targetKey)! + l.rtOff + l.reserve / 2;
      const xs = colX[l.sc] + G.nodeWidth;
      const xt = colX[l.tc];
      l.gaps = [];
      for (let c = l.sc + 1; c < l.tc; c++) {
        const xc = colX[c] + G.nodeWidth / 2;
        const y = ys + ((yt - ys) * (xc - xs)) / (xt - xs);
        idealY.set(`${l.id}|${c}`, y);
        const keys = columns[c];
        let best = 0;
        let bestD = Infinity;
        for (let g = 0; g <= keys.length; g++) {
          const lo = g === 0 ? -Infinity : Y.get(keys[g - 1])! + Math.max(H.get(keys[g - 1])!, G.minNodeH);
          const hi = g === keys.length ? Infinity : Y.get(keys[g])!;
          const d = y < lo ? lo - y : y > hi ? y - hi : 0;
          if (d < bestD - 1e-9) {
            bestD = d;
            best = g;
          }
        }
        l.gaps.push({ col: c, gap: best });
      }
    }
  };
  place();
  assign();
  place();
  assign();
  place();

  // ---- stations inside gaps ----------------------------------------------------------------
  const stationY = new Map<string, number>(); // `${id}|${col}` -> top y of the band in the gap
  columns.forEach((keys, c) => {
    for (let g = 0; g <= keys.length; g++) {
      const members = [...skipping, ...sameLinks].filter((l) => l.gaps.some((q) => q.col === c && q.gap === g));
      if (!members.length) continue;
      members.sort((a, b) => {
        if (a.cls !== b.cls) return CLS_RANK[a.cls] - CLS_RANK[b.cls];
        const ya = idealY.get(`${a.id}|${c}`) ?? 0;
        const yb = idealY.get(`${b.id}|${c}`) ?? 0;
        if (Math.abs(ya - yb) > 1e-9) return ya - yb;
        return cmpStr(a.id, b.id);
      });
      let y =
        g === 0
          ? colTop[c] + G.bandPad
          : Y.get(keys[g - 1])! + Math.max(H.get(keys[g - 1])!, G.minNodeH) + G.bandPad;
      for (const l of members) {
        stationY.set(`${l.id}|${c}`, y);
        y += l.reserve + G.bandPad;
      }
    }
  });

  const diagramBottom = Math.max(0, ...colH.map((h, c) => colTop[c] + h));
  let laneY = diagramBottom + G.laneTop;
  const laneCenter = new Map<string, number>();
  for (const l of arcs) {
    laneCenter.set(l.id, laneY + l.reserve / 2);
    laneY += l.reserve + G.bandPad;
  }
  const height = (arcs.length ? laneY : diagramBottom) + G.bottomPad;

  // ---- nodes out -----------------------------------------------------------------------------
  const small = new Map<string, { count: number; value: number }>();
  for (const c of copies) small.set(c.key, { count: 0, value: 0 });
  for (const l of links) {
    if (l.drawn) continue;
    for (const k of [l.sourceKey, l.targetKey]) {
      const s = small.get(k)!;
      s.count += 1;
      s.value += l.inp.value;
    }
  }
  const nodes: NodeBox[] = copies.map((c) => ({
    key: c.key,
    id: c.node.id,
    copy: c.copy,
    col: c.col,
    order: c.node.order,
    kind: c.node.kind,
    x: colX[c.col],
    y: Y.get(c.key)!,
    w: G.nodeWidth,
    h: H.get(c.key)!,
    inSum: inSum.get(c.key)!,
    outSum: outSum.get(c.key)!,
    small: small.get(c.key)!,
  }));

  // ---- link geometry -------------------------------------------------------------------------
  const laid: LaidLink[] = links.map((l) => {
    // with reserved ports (top-flows board) a ribbon sits in its own reserved slot, so it does not
    // move when other ribbons change width or vanish while scrubbing
    const ys0 = Y.get(l.sourceKey)! + (opts.reservePorts ? l.rsOff : l.sOff);
    const yt0 = Y.get(l.targetKey)! + (opts.reservePorts ? l.rtOff : l.tOff);
    const xr = colX[l.sc] + G.nodeWidth;
    const xl = colX[l.tc];
    const w = l.width;
    let d = "";
    const stations: Station[] = [];
    let route: Pt[] = [];
    if (l.drawn) {
      if (l.cls === "forward") {
        stations.push({ x0: xr, x1: xr, y: ys0, col: l.sc, gap: -1 });
        for (const g of l.gaps) {
          stations.push({
            x0: colX[g.col],
            x1: colX[g.col] + G.nodeWidth,
            y: stationY.get(`${l.id}|${g.col}`)!,
            col: g.col,
            gap: g.gap,
          });
        }
        stations.push({ x0: xl, x1: xl, y: yt0, col: l.tc, gap: -1 });
        d = ribbonD(stations, w);
      } else if (l.cls === "same" && !l.stub) {
        const xls = colX[l.sc];
        const yg = stationY.get(`${l.id}|${l.tc}`)! + w / 2;
        const xa = xr + rightOff.get(l.id)!;
        const xb = xls - leftOff.get(l.id)!;
        route = [
          { x: xr, y: ys0 + w / 2 },
          { x: xa, y: ys0 + w / 2 },
          { x: xa, y: yg },
          { x: xb, y: yg },
          { x: xb, y: yt0 + w / 2 },
          { x: xl, y: yt0 + w / 2 },
        ];
        d = routeOutlineD(route, w);
      } else if (l.stub) {
        const s = G.stubLength;
        d =
          `M${f2(xr)},${f2(ys0)}h${s}v${f2(w)}h${-s}Z` +
          `M${f2(xl - s)},${f2(yt0)}h${s}v${f2(w)}h${-s}Z`;
      } else {
        const lc = laneCenter.get(l.id)!;
        const xa = xr + rightOff.get(l.id)!;
        const xb = xl - leftOff.get(l.id)!;
        route = [
          { x: xr, y: ys0 + w / 2 },
          { x: xa, y: ys0 + w / 2 },
          { x: xa, y: lc },
          { x: xb, y: lc },
          { x: xb, y: yt0 + w / 2 },
          { x: xl, y: yt0 + w / 2 },
        ];
        d = routeOutlineD(route, w);
      }
    }
    return {
      id: l.id,
      source: l.inp.source,
      target: l.inp.target,
      sourceKey: l.sourceKey,
      targetKey: l.targetKey,
      cls: l.cls,
      reversed: !!l.inp.reversed,
      value: l.inp.value,
      width: w,
      reserve: l.reserve,
      drawn: l.drawn,
      stub: l.stub,
      sPort: { y0: ys0, y1: ys0 + w },
      tPort: { y0: yt0, y1: yt0 + w },
      stations,
      route,
      lane: l.lane,
      d,
    };
  });

  return { nodes, links: laid, width, height, diagramBottom, columns, colX, unit, options: opts };
}
