"use client";
/**
 * The top-flows board's lists (PLAN §4.6): every flow of the year with its value, share of GDP and
 * label — drawn ribbons, flows inside a node (listed, not drawn), other flows not drawn, and the
 * ribbons with no data this year. Nothing is interpolated or carried forward.
 */
import { useTranslations } from "next-intl";
import { useMemo } from "react";
import { Num, StatusBadge } from "@/components/ui";
import { seriesTotal } from "./panel-text";
import type { Series } from "@/data/types";
import { buildBoard, type BoardYearFlow } from "@/lib/ts-board/board";
import type { MapData } from "./MapView";
import { useMapLabels, type MapLabels } from "./useLabels";
import s from "./map.module.css";

export function TsLists({
  data,
  series,
  year,
  onSelect,
  selected,
}: {
  data: MapData;
  series: Series;
  year: string;
  onSelect?: (id: string | null) => void;
  selected: string | null;
}) {
  const t = useTranslations("map.ts");
  const L = useMapLabels();
  const board = useMemo(() => buildBoard(data.hierarchy, data.tsView, series, year), [data, series, year]);
  const ribbonIds = new Set(board.ribbons.map((r) => r.flow));
  const drawn = board.flows.filter((f) => ribbonIds.has(f.flow) && f.share !== null);
  const internal = new Map<string, BoardYearFlow[]>();
  for (const f of board.flows) {
    if (f.internalTo && f.share !== null) internal.set(f.internalTo, [...(internal.get(f.internalTo) ?? []), f]);
  }
  const other = board.flows.filter((f) => !ribbonIds.has(f.flow) && !f.internalTo && f.share !== null);
  const reversed = new Map(board.ribbons.filter((r) => r.reversed).map((r) => [r.flow, r.reversedTextKey]));
  return (
    <div className={s.lists} data-ts-lists="">
      <p data-ts-coverage="">{t("coverage", { n: String(board.coverage), total: String(board.totalFlows), year })}</p>
      <h3>{t("allFlows", { year })}</h3>
      <FlowList flows={drawn} L={L} onSelect={onSelect} selected={selected} reversed={reversed} />
      {[...internal.entries()].map(([node, flows]) => (
        <div key={node}>
          <h3>{t("internal", { node: L.node(node) })}</h3>
          <FlowList flows={flows} L={L} onSelect={onSelect} selected={selected} reversed={reversed} />
        </div>
      ))}
      {other.length > 0 && (
        <>
          <h3>{t("otherFlows")}</h3>
          <FlowList flows={other} L={L} onSelect={onSelect} selected={selected} reversed={reversed} />
        </>
      )}
      <h3>{t("noData", { year })}</h3>
      {board.noData.length ? (
        <ul className={s.smallList} data-ts-nodata="">
          {board.noData.map((f) => (
            <li key={f}>{L.series(f)}</li>
          ))}
        </ul>
      ) : (
        <p className={s.muted}>{t("noDataNone")}</p>
      )}
    </div>
  );
}

function FlowList({
  flows,
  L,
  onSelect,
  selected,
  reversed,
}: {
  flows: BoardYearFlow[];
  L: MapLabels;
  onSelect?: (id: string | null) => void;
  selected: string | null;
  reversed: Map<string, string | null>;
}) {
  const t = useTranslations("map");
  const rows = [...flows].sort((a, b) => Math.abs(b.share ?? 0) - Math.abs(a.share ?? 0) || (a.flow < b.flow ? -1 : 1));
  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {rows.map((f) => {
        const rk = reversed.get(f.flow);
        return (
          <li key={f.flow}>
            <button
              type="button"
              className={s.rowButton}
              onClick={() => onSelect?.(f.flow)}
              aria-pressed={selected === f.flow}
              data-ts-flow={f.flow}
            >
              <span className={s.rowMain}>
                {L.series(f.flow)}
                {f.base && <span className={s.muted}> ({t("ts.base", { base: f.base })})</span>}
                {rk && <span className={s.muted}> · {t(rk)}</span>}
              </span>
              <span className={s.rowValue}>
                {f.value !== null && <Num value={f.value} fmt="inr" />}
                <br />
                {f.share !== null && <Num value={f.share} fmt="pct_gdp" />}
              </span>
              {f.status && <StatusBadge total={seriesTotal(f.status)} split={f.status} single compact />}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
