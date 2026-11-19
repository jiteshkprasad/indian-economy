"use client";
/**
 * The Map (PLAN §4.5): the unrolled circular Sankey of the 2023-24 SAM, or the top-flows board
 * for any year. `mode="interactive"` is the Map page; `mode="controlled"` is driven by props
 * (stories) and draws a static figure with an accessible name.
 */
import { useMemo } from "react";
import { ErrorState } from "@/components/ui";
import { useCells, useHierarchy, usePinned, useSeries, useSummary, useTsView } from "@/data/hooks";
import type { Cells, Hierarchy, Pinned, Series, Summary, TsView } from "@/data/types";
import { formatInr, formatPctGdp } from "@/lib/format";
import { buildSamModel, type SamModel } from "@/lib/sankey/model";
import { MAX_LINKS_DESKTOP } from "@/lib/sankey/style";
import { buildBoard, type Board } from "@/lib/ts-board/board";
import { seriesTotal } from "./panel-text";
import { SankeySvg, type LinkMeta, type NodeMeta, type ZoomFocus } from "./SankeySvg";
import type { MapViewProps } from "./types";
import { useMapLabels, type MapLabels } from "./useLabels";
import s from "./map.module.css";

/** Optional handlers used by the interactive Map page (not part of the stories' contract). */
export type MapViewExtra = {
  onExpand?: (id: string) => void;
  onCollapse?: (id: string) => void;
  /** link guard (PLAN §4.5.9): 400 on desktop, 60 below 640 px */
  maxLinks?: number;
  /** home hero: money moving along the bright forward flows (off under reduced motion) */
  flowing?: boolean;
};

export type MapData = { summary: Summary; hierarchy: Hierarchy; cells: Cells; pinned: Pinned; tsView: TsView };

/** First-view data: from props when the server passed it, else fetched. */
export function useMapData(initial?: MapViewProps["initialData"]) {
  const summary = useSummary(initial?.summary);
  const hierarchy = useHierarchy(initial?.hierarchy);
  const cells = useCells(initial?.cells);
  const pinned = usePinned(initial?.pinned);
  const tsView = useTsView(initial?.tsView);
  const parts = [
    ["summary.json", summary],
    ["hierarchy.json", hierarchy],
    ["sam/cells.json", cells],
    ["sam/pinned.json", pinned],
    ["ts/view.json", tsView],
  ] as const;
  const failed = parts.find(([, p]) => p.error);
  const data: MapData | null = useMemo(
    () =>
      summary.data && hierarchy.data && cells.data && pinned.data && tsView.data
        ? { summary: summary.data, hierarchy: hierarchy.data, cells: cells.data, pinned: pinned.data, tsView: tsView.data }
        : null,
    [summary.data, hierarchy.data, cells.data, pinned.data, tsView.data],
  );
  return { data, error: failed ? { file: failed[0], error: failed[1].error } : null };
}

export function MapView(props: MapViewProps & MapViewExtra) {
  const { data, error } = useMapData(props.initialData);
  if (error) return <ErrorState file={error.file} error={error.error} />;
  if (!data) return <div className={s.svgWrap} style={{ minHeight: props.height ?? 320 }} aria-busy="true" />;
  if (props.view === "ts") return <TsMap {...props} data={data} />;
  return <SamMap {...props} data={data} />;
}

export function defaultReturnFlows(preset: "simple" | "full", expanded: readonly string[]): "stubs" | "arcs" {
  return preset === "simple" && expanded.length === 0 ? "stubs" : "arcs";
}

/** Drawn height of each visible node in ₹ crore (the larger copy for the split node). */
export function nodeValues(m: SamModel): Map<string, number> {
  const out = new Map<string, number>();
  for (const n of m.layout.nodes) out.set(n.id, Math.max(out.get(n.id) ?? 0, n.h / m.layout.unit));
  return out;
}

/** Meta for the marks of a SAM model. */
export function samMeta(m: SamModel, L: MapLabels, interactive: boolean) {
  const gdp = m.gdp;
  const nodeMeta: Record<string, NodeMeta> = {};
  const values = nodeValues(m);
  for (const n of m.nodes) {
    const v = values.get(n.id) ?? 0;
    const name = L.node(n.id);
    nodeMeta[n.id] = {
      label: name,
      kind: n.kind,
      expandable: interactive && n.expandable,
      collapsible: interactive && n.level > 0,
      aria: L.t(n.expandable && interactive ? "aria.nodeExpandable" : "aria.node", {
        name,
        value: formatInr(v),
        pct: formatPctGdp(v / gdp),
      }),
    };
  }
  const laidById = new Map(m.layout.links.map((l) => [l.id, l]));
  const linkMeta: Record<string, LinkMeta> = {};
  for (const l of m.links) {
    const payer = m.nodeById.get(l.payer);
    const laid = laidById.get(l.id);
    const v = Math.abs(l.value);
    linkMeta[l.id] = {
      kind: payer?.kind ?? "capital",
      aria: L.linkAria(l, gdp),
      split: l.split,
      reversed: l.part === "neg",
      valueLabel: laid?.stub
        ? L.t(laid.cls === "same" ? "stubSame" : "stub", {
            value: formatInr(v),
            node: L.node(l.part === "pos" ? l.receiver : l.payer),
          })
        : formatInr(v),
      marker: l.part === "neg" ? L.t("reversedMark") : undefined,
    };
  }
  return { nodeMeta, linkMeta };
}

type HlModel = { links: Array<{ id: string; payer: string; receiver: string }>; hasNode: (id: string) => boolean };

/** Highlight set: requested ids (unknown ids are reported), plus the selection and its links. */
export function highlightSet(
  m: HlModel,
  highlight: readonly string[] | undefined,
  selected: string | null | undefined,
  report = true,
): Set<string> | null {
  const ids = new Set<string>();
  const add = (h: string) => {
    if (m.links.some((l) => l.id === h)) {
      ids.add(h);
      return true;
    }
    if (m.hasNode(h)) {
      ids.add(h);
      for (const l of m.links) if (l.payer === h || l.receiver === h) ids.add(l.id);
      return true;
    }
    return false;
  };
  for (const h of highlight ?? []) {
    if (!add(h) && report) console.error(`[map] highlight id "${h}" is not on this map`);
  }
  if (selected) add(selected);
  if (!ids.size) return null;
  // nodes at the ends of highlighted links stay bright
  for (const l of m.links) if (ids.has(l.id)) ids.add(l.payer).add(l.receiver);
  return ids;
}

function SamMap(props: MapViewProps & MapViewExtra & { data: MapData }) {
  const { data } = props;
  const L = useMapLabels();
  const interactive = props.mode === "interactive";
  const returnFlows = props.returnFlows ?? defaultReturnFlows(props.preset, props.expanded);
  const model = useMemo(
    () =>
      buildSamModel(
        { hierarchy: data.hierarchy, cells: data.cells, pinned: data.pinned, gdp: data.summary.gdp.value },
        props.preset,
        props.expanded,
        returnFlows,
      ),
    [data, props.preset, props.expanded, returnFlows],
  );
  const meta = useMemo(() => samMeta(model, L, interactive), [model, L, interactive]);
  const zoom = useMemo(() => zoomFocus(data.hierarchy, L), [data.hierarchy, L]);
  const hl = useMemo(
    () => highlightSet({ links: model.links, hasNode: (id) => model.nodeById.has(id) }, props.highlight, props.selected),
    [model, props.highlight, props.selected],
  );
  const drawn = model.layout.links.filter((l) => l.drawn).length;
  const maxLinks = props.maxLinks ?? MAX_LINKS_DESKTOP;
  if (drawn > maxLinks) {
    return (
      <div className={s.notice} role="status" data-map-guard="">
        <p>{L.t("guard", { n: String(drawn), max: String(maxLinks) })}</p>
      </div>
    );
  }
  const version = `${model.visible.preset}|${model.visible.ids.join(",")}|${returnFlows}`;
  return (
    <SankeySvg
      layout={model.layout}
      nodeMeta={meta.nodeMeta}
      linkMeta={meta.linkMeta}
      selected={props.selected ?? null}
      highlight={hl}
      onlyHighlighted={props.onlyHighlighted}
      ariaLabel={L.t("aria.diagram", {
        year: data.summary.gdp.year,
        nodes: String(model.nodes.length),
        links: String(drawn),
      })}
      helpText={L.t("help")}
      interactive={interactive}
      onSelect={props.onSelect}
      onExpand={props.onExpand}
      onCollapse={props.onCollapse}
      height={props.height}
      version={version}
      zoom={interactive ? zoom : undefined}
      flowing={props.flowing}
    />
  );
}

/**
 * Where keyboard focus goes after + / − (PLAN §4.5.10): + moves to the group's first part in
 * hierarchy order (a preset merge such as PRODUCERS opens into its members); − moves to the parent
 * the parts folded into.
 */
export function zoomFocus(h: Hierarchy, L: MapLabels): ZoomFocus {
  const byId = new Map(h.nodes.map((n) => [n.id, n]));
  const merge = (id: string) => Object.values(h.presets).find((p) => p.merges[id])?.merges[id] ?? [];
  const byOrder = (ids: readonly string[]) => [...ids].sort((a, b) => (byId.get(a)?.order ?? 0) - (byId.get(b)?.order ?? 0));
  const parents = (id: string) => {
    const out: string[] = [];
    for (let n = byId.get(id); n?.parent; n = byId.get(n.parent)) out.push(n.parent);
    return out;
  };
  return {
    targets: (kind, id) => {
      if (kind === "collapse") return parents(id);
      const n = byId.get(id);
      // the simple preset's merged SI opens as the full preset's SI, then its parts
      return [...byOrder(n?.children ?? []), ...byOrder(merge(id).filter((m) => m !== id))];
    },
    announce: (kind, id) =>
      kind === "expand"
        ? L.t("aria.expanded", { name: L.node(id) })
        : L.t("aria.collapsed", { name: L.node(parents(id)[0] ?? id) }),
  };
}

function TsMap(props: MapViewProps & MapViewExtra & { data: MapData }) {
  const series = useSeries();
  if (series.error) return <ErrorState file="ts/series.json" error={series.error} />;
  if (!series.data) return <div className={s.svgWrap} style={{ minHeight: props.height ?? 320 }} aria-busy="true" />;
  return <TsBoardSvg {...props} series={series.data} />;
}

/** Meta for the ribbons and nodes of the top-flows board. */
export function boardMeta(b: Board, L: MapLabels) {
  const nodeMeta: Record<string, NodeMeta> = {};
  for (const n of b.nodes) {
    const name = L.node(n.id);
    nodeMeta[n.id] = { label: name, kind: n.kind, expandable: false, collapsible: false, aria: L.t("aria.tsNode", { name }) };
  }
  const kindOf = new Map(b.nodes.map((n) => [n.id, n.kind]));
  const linkMeta: Record<string, LinkMeta> = {};
  for (const r of b.ribbons) {
    if (r.share === null || r.value === null) continue;
    const values = {
      label: L.series(r.flow),
      from: L.node(r.from),
      to: L.node(r.to),
      year: b.year,
      value: formatInr(Math.abs(r.value)),
      pct: formatPctGdp(Math.abs(r.share)),
      status: r.status ? L.badge(seriesTotal(r.status), r.status) : "",
    };
    linkMeta[r.flow] = {
      kind: kindOf.get(r.from) ?? "capital",
      aria: L.t(r.reversed ? "aria.tsLinkReversed" : "aria.tsLink", values),
      split: r.status,
      reversed: r.reversed,
      valueLabel: formatPctGdp(Math.abs(r.share)),
      marker: r.reversed ? L.t("reversedYear") : undefined,
    };
  }
  return { nodeMeta, linkMeta };
}

export function useSeriesBoard(data: MapData, series: Series, year: string): Board {
  return useMemo(() => buildBoard(data.hierarchy, data.tsView, series, year), [data.hierarchy, data.tsView, series, year]);
}

function TsBoardSvg(props: MapViewProps & MapViewExtra & { data: MapData; series: Series }) {
  const L = useMapLabels();
  const board = useSeriesBoard(props.data, props.series, props.year);
  const interactive = props.mode === "interactive";
  const meta = useMemo(() => boardMeta(board, L), [board, L]);
  const hl = useMemo(
    () =>
      highlightSet(
        {
          links: board.ribbons.map((r) => ({ id: r.flow, payer: r.from, receiver: r.to })),
          hasNode: (id) => board.nodes.some((n) => n.id === id),
        },
        props.highlight,
        props.selected,
      ),
    [board, props.highlight, props.selected],
  );
  return (
    <SankeySvg
      layout={board.layout}
      nodeMeta={meta.nodeMeta}
      linkMeta={meta.linkMeta}
      selected={props.selected ?? null}
      highlight={hl}
      onlyHighlighted={props.onlyHighlighted}
      ariaLabel={L.t("aria.tsDiagram", {
        year: board.year,
        n: String(board.ribbons.filter((r) => r.share !== null).length),
      })}
      helpText={L.t("helpTs")}
      interactive={interactive}
      onSelect={props.onSelect}
      height={props.height}
      version={`ts|${board.year}`}
    />
  );
}
