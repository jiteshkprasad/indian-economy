"use client";
/**
 * The list/table alternative to the diagram (PLAN §4.5.10): the visible links with payer, receiver,
 * value, share of GDP, total and split labels and flags. "View as list" is the default on phones.
 * Every row's button is ≥ 24 px (the 2.5.8 route for the thin diagram marks).
 */
import { useTranslations } from "next-intl";
import { Num, StatusBadge } from "@/components/ui";
import type { AggLink } from "@/data/aggregate";
import { flagNames } from "@/lib/status";
import type { MapLabels } from "./useLabels";
import s from "./map.module.css";

export function LinkTable({
  links,
  gdp,
  L,
  onSelect,
  selected,
}: {
  links: AggLink[];
  gdp: number;
  L: MapLabels;
  onSelect?: (id: string) => void;
  selected?: string | null;
}) {
  const t = useTranslations("map.list");
  const tf = useTranslations("common.flags");
  const rows = [...links].sort((a, b) => Math.abs(b.value) - Math.abs(a.value) || (a.id < b.id ? -1 : 1));
  if (!rows.length) return <p>{t("empty")}</p>;
  return (
    <div className={s.tableWrap} data-link-table="" tabIndex={0} role="region" aria-label={t("caption")}>
      <table className={s.table}>
        <caption className="visually-hidden">{t("caption")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("flow")}</th>
            <th scope="col">{t("payer")}</th>
            <th scope="col">{t("receiver")}</th>
            <th scope="col" className={s.numCell}>
              {t("value")}
            </th>
            <th scope="col" className={s.numCell}>
              {t("pctGdp")}
            </th>
            <th scope="col">{t("labels")}</th>
            <th scope="col">{t("flags")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((l) => (
            <tr key={l.id} data-row-link={l.id} aria-current={selected === l.id ? "true" : undefined}>
              <th scope="row" style={{ fontWeight: 500 }}>
                {onSelect ? (
                  <button type="button" className="btn btn-sm" onClick={() => onSelect(l.id)} style={{ textAlign: "left" }}>
                    {L.link(l.id)}
                  </button>
                ) : (
                  L.link(l.id)
                )}
              </th>
              <td>{L.node(l.payer)}</td>
              <td>{L.node(l.receiver)}</td>
              <td className={s.numCell}>
                <Num value={l.value} fmt="inr" />
              </td>
              <td className={s.numCell}>
                <Num value={l.value / gdp} fmt="pct_gdp" />
              </td>
              <td>
                {l.split && <StatusBadge total={l.total} split={l.split} compact />}
              </td>
              <td>{flagNames(l.flags).map((n) => tf(n)).join("; ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * The groups on the map as buttons (≥ 24 px): the pointer and keyboard route to a group's details
 * and its "Show its parts" button that does not need the diagram's thin node marks (WCAG 2.5.8).
 */
export function GroupButtons({
  nodes,
  L,
  onSelect,
  selected,
}: {
  nodes: ReadonlyArray<{ id: string }>;
  L: MapLabels;
  onSelect: (id: string) => void;
  selected?: string | null;
}) {
  const t = useTranslations("map.list");
  if (!nodes.length) return null;
  return (
    <div role="group" aria-labelledby="map-groups-h" data-group-buttons="">
      <h3 id="map-groups-h">{t("groups")}</h3>
      <p className={s.framing}>{t("groupsIntro")}</p>
      <ul className={s.groupButtons}>
        {nodes.map((n) => (
          <li key={n.id}>
            <button type="button" className="btn btn-sm" aria-pressed={selected === n.id} onClick={() => onSelect(n.id)} data-group-button={n.id}>
              {L.node(n.id)}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
