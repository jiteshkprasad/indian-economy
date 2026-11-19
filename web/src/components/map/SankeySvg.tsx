"use client";
/**
 * The SVG renderer shared by the SAM map and the top-flows board (PLAN §4.5.10–11).
 * React renders every final attribute; `usePathTween` animates changes.
 * One Tab stop: the diagram uses a roving tabindex over its nodes (and, after L, a node's links).
 */
import { useId, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type RefObject } from "react";
import { LiveRegion } from "@/components/ui";
import type { Label } from "@/data/types";
import { usePathTween } from "@/lib/sankey/animate";
import { firstKey, linksOfKey, moveFocus } from "@/lib/sankey/keyboard";
import {
  DIMMED_OPACITY,
  EDGE_STROKE_WIDTH,
  FORWARD_OPACITY,
  LABEL_HALO_WIDTH,
  MIN_PATTERN_PX,
  RETURN_OPACITY,
  STUB_OPACITY,
} from "@/lib/sankey/style";
import type { Layout } from "@/lib/sankey/types";
import s from "./map.module.css";

export type NodeMeta = { label: string; aria: string; kind: string; expandable: boolean; collapsible: boolean };
export type LinkMeta = {
  /** kind of the payer (ribbon colour) */
  kind: string;
  aria: string;
  split: Label | null;
  reversed: boolean;
  /** short text drawn on wide ribbons and stubs */
  valueLabel?: string;
  /** marker drawn on the ribbon, e.g. "reversed this year" */
  marker?: string;
};

/** What + / − did, so focus can follow the group into the new layout (PLAN §4.5.10, WCAG 2.4.3). */
export type ZoomKind = "expand" | "collapse";
export type ZoomFocus = {
  /** node ids to focus after the zoom, best first (e.g. the first child; the parent after −) */
  targets: (kind: ZoomKind, id: string) => string[];
  /** the polite announcement of the change */
  announce: (kind: ZoomKind, id: string) => string;
};

export type SankeySvgProps = {
  layout: Layout;
  nodeMeta: Record<string, NodeMeta>;
  linkMeta: Record<string, LinkMeta>;
  selected: string | null;
  /** ids of links and nodes to emphasise; others are dimmed. Null = nothing dimmed. */
  highlight: Set<string> | null;
  onlyHighlighted?: boolean;
  ariaLabel: string;
  helpText: string;
  interactive: boolean;
  onSelect?: (id: string | null) => void;
  onExpand?: (id: string) => void;
  onCollapse?: (id: string) => void;
  height?: number;
  /** changes whenever the geometry changes (enables the tween) */
  version: string;
  /** keyboard zoom: where focus goes and what is announced */
  zoom?: ZoomFocus;
  /** draw moving stripes on bright forward ribbons: money visibly flowing (home hero only) */
  flowing?: boolean;
};

/** Smallest rendered size of node and value labels, in CSS px (they are drawn in viewBox units). */
const NODE_LABEL_MIN_PX = 12;
const VALUE_LABEL_MIN_PX = 11;
/** Their size at a scale of 1 (map.module.css .nodeLabel / .valueLabel). */
const NODE_LABEL_UNITS = 13;
const VALUE_LABEL_UNITS = 11.5;
/** Pointer target of a node, in CSS px (WCAG 2.5.8). */
const NODE_TARGET_PX = 24;

/** Rendered CSS px per viewBox unit (preserveAspectRatio "meet"), or null before the first measure. */
function useSvgScale(ref: RefObject<SVGSVGElement | null>, w: number, h: number): number | null {
  const [scale, setScale] = useState<number | null>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || w <= 0 || h <= 0) return;
    const measure = () => {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) setScale(Math.min(r.width / w, r.height / h));
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref, w, h]);
  return scale;
}

type Focus = { node: string; link: number | null };

export function SankeySvg(p: SankeySvgProps) {
  const L = p.layout;
  const uid = useId().replace(/:/g, "");
  const helpId = `${uid}-help`;
  const svgRef = useRef<SVGSVGElement | null>(null);
  const refs = useRef(new Map<string, SVGElement>());
  const [focus, setFocus] = useState<Focus | null>(null);
  const [hasFocus, setHasFocus] = useState(false);
  const [zoomMsg, setZoomMsg] = useState("");
  // set by + / −: the layout it was pressed on, so focus moves once the new layout is drawn
  const pendingZoom = useRef<{ kind: ZoomKind; id: string; from: Layout } | null>(null);
  usePathTween(svgRef, p.version);
  const scale = useSvgScale(svgRef, L.width, L.height);
  const unitPx = scale ?? 1;
  // labels keep a readable size however small the diagram is drawn (and grow with browser zoom)
  const nodeFont = Math.max(NODE_LABEL_UNITS, NODE_LABEL_MIN_PX / unitPx);
  const valueFont = Math.max(VALUE_LABEL_UNITS, VALUE_LABEL_MIN_PX / unitPx);
  const minTarget = NODE_TARGET_PX / unitPx;

  const nodeByKey = useMemo(() => new Map(L.nodes.map((n) => [n.key, n])), [L]);
  const linkById = useMemo(() => new Map(L.links.map((l) => [l.id, l])), [L]);

  // which node key holds the tab stop
  const validFocus = focus && nodeByKey.has(focus.node) ? focus : null;
  const tabNode = validFocus?.node ?? selectedKey(L, p.selected) ?? firstKey(L);
  const focusLinks = validFocus && validFocus.link !== null ? linksOfKey(L, validFocus.node) : [];
  const focusLinkId = validFocus && validFocus.link !== null ? (focusLinks[validFocus.link] ?? null) : null;

  // After + / −, the focused node may have left the layout: move focus to the zoom's target
  // (the first child, or the parent) as soon as the new layout is committed, and announce it.
  useLayoutEffect(() => {
    const z = pendingZoom.current;
    if (!z || z.from === L) return;
    pendingZoom.current = null;
    const ids = p.zoom?.targets(z.kind, z.id) ?? [];
    let key: string | null = null;
    for (const id of [...ids, z.id]) {
      key = L.nodes.find((n) => n.id === id)?.key ?? null;
      if (key) break;
    }
    key ??= firstKey(L);
    if (!key) return;
    setFocus({ node: key, link: null });
    (refs.current.get(`n:${key}`) as (SVGElement & { focus?: () => void }) | undefined)?.focus?.();
    if (p.zoom) setZoomMsg(p.zoom.announce(z.kind, z.id));
  }, [L, p.zoom]);

  const expectZoom = (kind: ZoomKind, id: string) => {
    const z = { kind, id, from: L };
    pendingZoom.current = z;
    // a zoom that changes nothing must not move focus on some later, unrelated layout change
    setTimeout(() => {
      if (pendingZoom.current === z) pendingZoom.current = null;
    }, 1500);
  };

  const moveTo = (f: Focus) => {
    setFocus(f);
    const key = f.link !== null ? `l:${linksOfKey(L, f.node)[f.link]}` : `n:${f.node}`;
    requestAnimationFrame(() => (refs.current.get(key) as SVGElement & { focus?: () => void })?.focus?.());
  };

  const onKeyDown = (e: KeyboardEvent) => {
    if (!p.interactive) return;
    const cur = validFocus ?? (tabNode ? { node: tabNode, link: null } : null);
    if (!cur) return;
    const node = nodeByKey.get(cur.node);
    if (!node) return;
    const k = e.key;
    let handled = true;
    if (cur.link !== null) {
      const ids = linksOfKey(L, cur.node);
      if (k === "ArrowDown") moveTo({ node: cur.node, link: Math.min(ids.length - 1, cur.link + 1) });
      else if (k === "ArrowUp") moveTo({ node: cur.node, link: Math.max(0, cur.link - 1) });
      else if (k === "Enter" || k === " ") p.onSelect?.(ids[cur.link] ?? null);
      else if (k === "Escape") moveTo({ node: cur.node, link: null });
      else handled = false;
    } else if (k === "ArrowUp" || k === "ArrowDown" || k === "ArrowLeft" || k === "ArrowRight") {
      const dir = k === "ArrowUp" ? "up" : k === "ArrowDown" ? "down" : k === "ArrowLeft" ? "left" : "right";
      moveTo({ node: moveFocus(L, cur.node, dir), link: null });
    } else if (k === "Enter" || k === " ") p.onSelect?.(node.id);
    else if (k === "Escape") p.onSelect?.(null);
    else if (k === "+" || k === "=") {
      if (p.nodeMeta[node.id]?.expandable && p.onExpand) {
        expectZoom("expand", node.id);
        p.onExpand(node.id);
      }
    } else if (k === "-" || k === "−" || k === "_") {
      if (p.nodeMeta[node.id]?.collapsible && p.onCollapse) {
        expectZoom("collapse", node.id);
        p.onCollapse(node.id);
      }
    } else if (k === "l" || k === "L") {
      if (linksOfKey(L, cur.node).length) moveTo({ node: cur.node, link: 0 });
    } else handled = false;
    if (handled) e.preventDefault();
  };

  const isDim = (id: string) => p.highlight !== null && !p.highlight.has(id);

  // value labels: on wide forward ribbons (at their target) and on stubs; a label that would
  // overlap the one above it at the same x is left out (the value is in the aria-label and the table)
  const valueLabels = useMemo(() => {
    const cands: Array<{ id: string; x: number; y: number; anchor: "start" | "end"; text: string }> = [];
    for (const l of L.links) {
      const m = p.linkMeta[l.id];
      if (!l.drawn || !m || (!m.valueLabel && !m.marker)) continue;
      if (p.onlyHighlighted && p.highlight && !p.highlight.has(l.id)) continue;
      if (p.highlight !== null && !p.highlight.has(l.id)) continue;
      const text = [m.valueLabel, m.marker].filter(Boolean).join(" · ");
      if (l.stub) {
        if (l.width < 9) continue;
        const src = nodeByKey.get(l.sourceKey);
        cands.push({ id: l.id, x: (src?.x ?? 0) + (src?.w ?? 0) + 26, y: (l.sPort.y0 + l.sPort.y1) / 2 + valueFont / 3, anchor: "start", text });
      } else if (l.cls === "forward" && l.width >= 22) {
        const x = (nodeByKey.get(l.targetKey)?.x ?? 0) - 6;
        cands.push({ id: l.id, x, y: (l.tPort.y0 + l.tPort.y1) / 2 + valueFont / 3, anchor: "end", text });
      }
    }
    // boxes already taken: node labels (estimated from the label's length), then kept value labels
    type Box = { x0: number; x1: number; y0: number; y1: number };
    const taken: Box[] = [];
    const nodeCharW = (7.2 * nodeFont) / NODE_LABEL_UNITS;
    for (const n of L.nodes) {
      const m = p.nodeMeta[n.id];
      if (!m) continue;
      const w = fitLabel(m.label, labelRoom(L, n.col), nodeFont).length * nodeCharW;
      const x0 = n.copy === "in" ? n.x + n.w - w : n.x;
      taken.push({ x0, x1: x0 + w, y0: n.y - 7 - nodeFont * 0.8, y1: n.y - 7 + nodeFont * 0.25 });
    }
    const valueCharW = 0.58 * valueFont;
    const kept: typeof cands = [];
    for (const c of [...cands].sort((a, b) => a.x - b.x || a.y - b.y)) {
      const w = c.text.length * valueCharW;
      const box = { x0: c.anchor === "end" ? c.x - w : c.x, x1: c.anchor === "end" ? c.x : c.x + w, y0: c.y - valueFont * 0.8, y1: c.y + valueFont * 0.25 };
      if (taken.some((b) => box.x0 < b.x1 && b.x0 < box.x1 && box.y0 < b.y1 && b.y0 < box.y1)) continue;
      taken.push(box);
      kept.push(c);
    }
    return kept;
  }, [L, p.linkMeta, p.nodeMeta, p.onlyHighlighted, p.highlight, nodeByKey, valueFont, nodeFont]);
  const viewH = L.height;
  const focusNode = hasFocus && validFocus && validFocus.link === null ? nodeByKey.get(validFocus.node) : undefined;
  const focusLink = hasFocus && focusLinkId ? linkById.get(focusLinkId) : undefined;

  return (
    <div className={s.svgWrap} style={p.height ? { height: p.height } : undefined}>
      <p id={helpId} className={p.interactive ? s.help : "visually-hidden"}>
        {p.helpText}
      </p>
      <svg
        ref={svgRef}
        className={s.svg}
        viewBox={`0 0 ${round(L.width)} ${round(viewH)}`}
        preserveAspectRatio="xMidYMin meet"
        style={p.height ? { height: p.height - 24 } : undefined}
        data-map-svg=""
      >
        <defs>
          <pattern id={`${uid}-hatch`} width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="9" className={s.hatchLine} />
          </pattern>
          {p.flowing && (
            <pattern id={`${uid}-flow`} width="28" height="28" patternUnits="userSpaceOnUse">
              <rect x="0" y="0" width="7" height="28" className={s.flowStripe} />
              <animateTransform attributeName="patternTransform" type="translate" from="0 0" to="28 0" dur="1.4s" repeatCount="indefinite" />
            </pattern>
          )}
          <pattern id={`${uid}-cross`} width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="9" className={s.hatchLine} />
            <line x1="0" y1="0" x2="9" y2="0" className={s.hatchLine} />
          </pattern>
        </defs>
        <g
          role="group"
          aria-roledescription="flow map"
          aria-label={p.ariaLabel}
          aria-describedby={helpId}
          onKeyDown={onKeyDown}
          onFocus={() => setHasFocus(true)}
          onBlur={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setHasFocus(false);
          }}
        >
          <g className={s.links}>
            {L.links.map((l) => {
              if (!l.drawn) return null;
              const m = p.linkMeta[l.id];
              if (!m) return null;
              if (p.onlyHighlighted && p.highlight && !p.highlight.has(l.id)) return null;
              const opacity = isDim(l.id)
                ? DIMMED_OPACITY
                : l.stub
                  ? STUB_OPACITY
                  : l.cls === "forward"
                    ? FORWARD_OPACITY
                    : RETURN_OPACITY;
              const pattern =
                l.width >= MIN_PATTERN_PX && (m.split === "estimated" || m.split === "balancing_set")
                  ? m.split === "estimated"
                    ? `url(#${uid}-hatch)`
                    : `url(#${uid}-cross)`
                  : null;
              const isSel = p.selected === l.id;
              const tab = focusLinkId === l.id ? 0 : -1;
              return (
                <g key={l.id} data-link={l.id} data-cls={l.cls} data-reversed={l.reversed ? "" : undefined}>
                  <path
                    data-tween={`l:${l.id}`}
                    d={l.d}
                    className={s.ribbon}
                    style={{
                      fill: `var(--k-${m.kind})`,
                      fillOpacity: opacity,
                      stroke: `var(--k-${m.kind}-edge)`,
                      strokeWidth: isSel ? 2 : EDGE_STROKE_WIDTH,
                      strokeOpacity: isDim(l.id) ? 0.4 : 1,
                    }}
                  />
                  {p.flowing && !isDim(l.id) && l.cls === "forward" && !l.stub && (
                    <path data-tween={`f:${l.id}`} d={l.d} fill={`url(#${uid}-flow)`} className={s.flowing} aria-hidden="true" />
                  )}
                  {pattern && !isDim(l.id) && (
                    <path data-tween={`p:${l.id}`} d={l.d} fill={pattern} className={s.pattern} aria-hidden="true" />
                  )}
                  <path
                    ref={(el) => {
                      if (el) refs.current.set(`l:${l.id}`, el);
                      else refs.current.delete(`l:${l.id}`);
                    }}
                    data-tween={`h:${l.id}`}
                    d={l.d}
                    className={s.hit}
                    data-mark="link"
                    role={p.interactive ? "button" : undefined}
                    tabIndex={p.interactive ? tab : undefined}
                    aria-label={p.interactive ? m.aria : undefined}
                    aria-pressed={p.interactive ? isSel : undefined}
                    onClick={p.interactive ? () => p.onSelect?.(l.id) : undefined}
                  >
                    <title>{m.aria}</title>
                  </path>
                </g>
              );
            })}
          </g>
          <g className={s.nodes}>
            {L.nodes.map((n) => {
              const m = p.nodeMeta[n.id];
              if (!m) return null;
              const h = Math.max(n.h, 2);
              const isSel = p.selected === n.id;
              const tab = p.interactive && !focusLinkId && tabNode === n.key ? 0 : -1;
              return (
                <g
                  key={n.key}
                  ref={(el) => {
                    if (el) refs.current.set(`n:${n.key}`, el);
                    else refs.current.delete(`n:${n.key}`);
                  }}
                  data-node={n.id}
                  data-key={n.key}
                  data-mark="node"
                  role={p.interactive ? "button" : undefined}
                  tabIndex={p.interactive ? tab : undefined}
                  aria-label={p.interactive ? m.aria : undefined}
                  aria-pressed={p.interactive ? isSel : undefined}
                  onClick={
                    p.interactive
                      ? () => {
                          setFocus({ node: n.key, link: null });
                          p.onSelect?.(n.id);
                        }
                      : undefined
                  }
                  onFocus={() => {
                    if (!validFocus || validFocus.node !== n.key || validFocus.link !== null)
                      setFocus({ node: n.key, link: null });
                  }}
                  className={s.node}
                >
                  {p.interactive && (
                    // the pointer target: at least 24 × 24 CSS px around the (often thinner) node
                    <rect
                      x={round(n.x + n.w / 2 - Math.max(n.w, minTarget) / 2)}
                      y={round(n.y + h / 2 - Math.max(h, minTarget) / 2)}
                      width={round(Math.max(n.w, minTarget))}
                      height={round(Math.max(h, minTarget))}
                      className={s.nodeHit}
                      data-node-hit=""
                    />
                  )}
                  <rect
                    x={round(n.x)}
                    y={round(n.y)}
                    width={n.w}
                    height={round(h)}
                    style={{ fill: `var(--k-${m.kind}-edge)`, opacity: isDim(n.id) ? 0.5 : 1 }}
                    className={isSel ? s.nodeSel : undefined}
                  />
                  <text
                    x={round(n.copy === "in" ? n.x + n.w : n.x)}
                    y={round(n.y - 7)}
                    textAnchor={n.copy === "in" ? "end" : "start"}
                    className={s.nodeLabel}
                    style={{ fontSize: round(nodeFont), strokeWidth: round((LABEL_HALO_WIDTH * nodeFont) / NODE_LABEL_UNITS) }}
                    aria-hidden="true"
                  >
                    {fitLabel(m.label, labelRoom(L, n.col), nodeFont)}
                  </text>
                </g>
              );
            })}
          </g>
          <g className={s.valueLabels} aria-hidden="true">
            {valueLabels.map((v) => (
              <text
                key={v.id}
                x={round(v.x)}
                y={round(v.y)}
                textAnchor={v.anchor}
                className={s.valueLabel}
                style={{ fontSize: round(valueFont), strokeWidth: round((LABEL_HALO_WIDTH * valueFont) / VALUE_LABEL_UNITS) }}
              >
                {v.text}
              </text>
            ))}
          </g>
          {focusNode && (
            <g className={s.focusRing} aria-hidden="true" data-focus-ring="">
              <rect
                x={round(focusNode.x - 4)}
                y={round(focusNode.y - 4)}
                width={focusNode.w + 8}
                height={round(Math.max(focusNode.h, 2) + 8)}
                className={s.focusHalo}
              />
              <rect
                x={round(focusNode.x - 4)}
                y={round(focusNode.y - 4)}
                width={focusNode.w + 8}
                height={round(Math.max(focusNode.h, 2) + 8)}
                className={s.focusStroke}
              />
            </g>
          )}
          {focusLink && (
            <g className={s.focusRing} aria-hidden="true" data-focus-ring="">
              <path d={focusLink.d} className={s.focusHalo} />
              <path d={focusLink.d} className={s.focusStroke} />
            </g>
          )}
        </g>
      </svg>
      {p.interactive && p.zoom && <LiveRegion message={zoomMsg} />}
    </div>
  );
}

/** Horizontal room for a node's label: up to the next column (or the previous, for the last). */
function labelRoom(L: Layout, col: number): number {
  const xs = L.colX;
  if (xs.length < 2) return L.width;
  const gap = col < xs.length - 1 ? xs[col + 1] - xs[col] : xs[col] - xs[col - 1];
  return gap - 8;
}

/** Truncate a label to fit (≈ 7.2 units per character at 13 units); the full name is in the aria-label. */
function fitLabel(label: string, room: number, font: number): string {
  const max = Math.max(6, Math.floor(room / ((7.2 * font) / NODE_LABEL_UNITS)));
  return label.length <= max ? label : `${label.slice(0, max - 1).trimEnd()}…`;
}

function round(n: number): number {
  return Math.round(n * 100) / 100;
}

function selectedKey(L: Layout, selected: string | null): string | null {
  if (!selected) return null;
  const n = L.nodes.find((x) => x.id === selected);
  if (n) return n.key;
  const l = L.links.find((x) => x.id === selected);
  return l ? l.sourceKey : null;
}
