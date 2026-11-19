"use client";
/**
 * Labels and accessible names for map marks. English text comes from `map-text.json` (U6) for
 * node, link and series labels and from `messages/en/map.json` for sentences.
 * A missing label is a content bug: it is logged and the id is shown, never invented.
 */
import { useTranslations } from "next-intl";
import { useMemo } from "react";
import type { AggLink } from "@/data/aggregate";
import { useMapText } from "@/data/hooks";
import type { Label, MapText, TotalLabel } from "@/data/types";
import { formatInr, formatPctGdp } from "@/lib/format";
import { parseLinkId } from "@/lib/ids";

const reported = new Set<string>();
function missing(kind: string, id: string) {
  const k = `${kind}:${id}`;
  if (reported.has(k)) return;
  reported.add(k);
  console.error(`[map-text] no ${kind} label for "${id}"`);
}

export function nodeLabelOf(text: MapText, id: string): string {
  const l = text.nodes[id]?.label;
  if (!l) missing("node", id);
  return l ?? id;
}

export function seriesLabelOf(text: MapText, id: string): string {
  const l = text.series[id]?.label;
  if (!l) missing("series", id);
  return l ?? id;
}

export type MapLabels = ReturnType<typeof useMapLabels>;

export function useMapLabels() {
  const text = useMapText();
  const t = useTranslations("map");
  const ts = useTranslations("common.status");
  return useMemo(() => {
    const node = (id: string) => nodeLabelOf(text, id);
    const series = (id: string) => seriesLabelOf(text, id);
    /** a link's own label: map-text for level-0 links; composed for deeper ones */
    const link = (id: string): string => {
      const own = text.links[id]?.label;
      if (own) return own;
      const p = parseLinkId(id);
      if (!p) return id;
      return t(p.part === "neg" ? "link.composedNeg" : "link.composed", {
        payer: node(p.payer),
        receiver: node(p.receiver),
      });
    };
    const badge = (total: TotalLabel | null, split: Label | null): string => {
      if (split === null) return total ? ts(`total_${total}`) : "";
      if (total === null) return ts(split);
      if (total === split) return ts(`total_${total}`);
      return `${ts(`total_${total}`)}${ts("badgeSep")}${ts(`split_${split}`)}`;
    };
    /** the accessible name of a drawn SAM link (PLAN §4.5.10) */
    const linkAria = (l: AggLink, gdp: number): string => {
      const v = Math.abs(l.value);
      const values = {
        payer: node(l.payer),
        receiver: node(l.receiver),
        label: link(l.id),
        value: formatInr(v),
        pct: formatPctGdp(v / gdp),
        badge: badge(l.total, l.split),
      };
      return t(l.part === "neg" ? "aria.linkNeg" : "aria.link", values);
    };
    return { text, node, series, link, badge, linkAria, t };
  }, [text, t, ts]);
}
