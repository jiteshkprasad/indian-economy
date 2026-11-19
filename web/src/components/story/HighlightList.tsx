"use client";
import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { Num } from "@/components/ui/Num";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { AggLink } from "@/data/aggregate";
import { useMapText } from "@/data/hooks";
import type { Cells, Hierarchy, MapText, Pinned, StoryView } from "@/data/types";
import { parseLinkId } from "@/lib/ids";
import { highlightedLinks } from "@/lib/story/highlights";
import s from "./story.module.css";

function nodeLabel(mt: MapText, id: string): string | null {
  return mt.nodes[id]?.label ?? null;
}

/** A link's label: map-text.json for level-0 links, else "<payer> pays <receiver>" from node labels. */
export function linkLabel(mt: MapText, id: string, t: (k: string, v?: Record<string, string>) => string): string {
  const own = mt.links[id]?.label;
  if (own) return own;
  const p = parseLinkId(id);
  const payer = p && nodeLabel(mt, p.payer);
  const receiver = p && nodeLabel(mt, p.receiver);
  if (!p || !payer || !receiver) {
    console.error(`[story] no label for link ${id} in map-text.json`);
    return id;
  }
  return t(p.part === "neg" ? "list.linkReversed" : "list.link", { payer, receiver });
}

/**
 * The step's highlighted flows as a list with values, share of GDP and badges
 * (PLAN §4.9). This is also the accessible alternative to the compact map.
 */
export function HighlightList({
  cells,
  hierarchy,
  pinned,
  gdp,
  view,
}: {
  cells: Cells;
  hierarchy: Hierarchy;
  pinned: Pinned;
  gdp: number;
  view: StoryView;
}) {
  const t = useTranslations("story");
  const mt = useMapText();
  const { links, missing } = useMemo(() => highlightedLinks(cells, hierarchy, pinned, view), [cells, hierarchy, pinned, view]);
  if (missing.length) console.error(`[story] highlighted ids not drawn at this zoom: ${missing.join(", ")}`);
  if (links.length === 0) return null;
  return (
    <div className={s.flows}>
      <h3 className={s.flowsHeading}>{t("player.flowsHeading")}</h3>
      <ul className={s.flowList}>
        {links.map((l: AggLink) => (
          <li key={l.id} className={s.flowItem} data-link-id={l.id}>
            <span className={s.flowName}>{linkLabel(mt, l.id, t)}</span>
            <span className={s.flowValues}>
              <Num value={Math.abs(l.value)} fmt="inr" />
              <span className={s.muted}>
                {" · "}
                <Num value={Math.abs(l.value) / gdp} fmt="pct_gdp" />
              </span>
            </span>
            {l.split && (
              <StatusBadge
                total={l.total}
                split={l.split}
                composition={l.composition}
                pins={l.pins}
                pairPins={l.pair?.pins}
                compact
              />
            )}
          </li>
        ))}
      </ul>
      {missing.length > 0 && (
        <p className={s.notice} role="note">
          {t("player.missingFlows", { ids: missing.join(", ") })}
        </p>
      )}
    </div>
  );
}
