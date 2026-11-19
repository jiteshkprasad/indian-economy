"use client";
/**
 * The phone map (PLAN §4.5.9): below 640 px the Sankey is not squeezed. The simple view's nodes
 * are a list of cards (name, money flowing through, share of GDP, badge). Opening a card shows its
 * "Money in" and "Money out" lists, each row ≥ 44 px, largest first, with a bar scaled to its share
 * of GDP; a row opens the flow panel. In the top-flows view the list of the year's flows is shown.
 */
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { ErrorState, Num, StatusBadge } from "@/components/ui";
import type { AggLink } from "@/data/aggregate";
import { useSeries } from "@/data/hooks";
import { buildSamModel, moneyInOut } from "@/lib/sankey/model";
import { composition, headlineSplit } from "@/lib/status";
import { nodeValues, useMapData, type MapData } from "./MapView";
import { TsLists } from "./TsLists";
import type { MapViewProps } from "./types";
import { useMapLabels, type MapLabels } from "./useLabels";
import s from "./map.module.css";

export function MapMobile(props: Omit<MapViewProps, "height">) {
  const { data, error } = useMapData(props.initialData);
  if (error) return <ErrorState file={error.file} error={error.error} />;
  if (!data) return <div style={{ minHeight: 200 }} aria-busy="true" />;
  if (props.view === "ts") return <MobileTs {...props} data={data} />;
  return <MobileSam {...props} data={data} />;
}

function MobileTs(props: Omit<MapViewProps, "height"> & { data: MapData }) {
  const series = useSeries();
  if (series.error) return <ErrorState file="ts/series.json" error={series.error} />;
  if (!series.data) return <div style={{ minHeight: 200 }} aria-busy="true" />;
  return <TsLists data={props.data} series={series.data} year={props.year} onSelect={props.onSelect} selected={props.selected ?? null} />;
}

function MobileSam(props: Omit<MapViewProps, "height"> & { data: MapData }) {
  const { data } = props;
  const L = useMapLabels();
  const t = useTranslations("map.mobile");
  const tm = useTranslations("map");
  const [open, setOpen] = useState<string | null>(null);
  const model = useMemo(
    () =>
      buildSamModel(
        { hierarchy: data.hierarchy, cells: data.cells, pinned: data.pinned, gdp: data.summary.gdp.value },
        "simple",
        [],
        "stubs",
      ),
    [data],
  );
  const values = useMemo(() => nodeValues(model), [model]);
  const gdp = model.gdp;
  const maxShare = Math.max(...model.links.map((l) => Math.abs(l.value) / gdp));
  const kindOf = (id: string) => model.nodeById.get(id)?.kind ?? "capital";
  return (
    <div data-map-mobile="">
      <p className={s.intro}>{t("intro")}</p>
      <p className={s.framing}>{tm("framing")}</p>
      <ul className={s.cards}>
        {model.nodes.map((n) => {
          const v = values.get(n.id) ?? 0;
          const io = moneyInOut(model, n.id);
          const abs = io.in.reduce(
            (a, l) => ({ o: a.o + l.abs.o, d: a.d + l.abs.d, e: a.e + l.abs.e, b: a.b + l.abs.b }),
            { o: 0, d: 0, e: 0, b: 0 },
          );
          const comp = composition(abs.o, abs.d, abs.e, abs.b);
          const isOpen = open === n.id;
          const bodyId = `mob-${n.id}`;
          return (
            <li key={n.id} className={s.card} data-mobile-node={n.id} data-node-card={n.id}>
              <button
                type="button"
                className={s.cardHead}
                aria-expanded={isOpen}
                aria-controls={bodyId}
                onClick={() => setOpen(isOpen ? null : n.id)}
              >
                <span className={s.swatch} style={{ background: `var(--k-${n.kind})` }} aria-hidden="true" />
                <span className={s.rowMain}>
                  <span className={s.cardTitle}>{L.node(n.id)}</span>
                  <span className={s.cardMeta}>
                    <Num value={v} fmt="inr" /> · <Num value={v / gdp} fmt="pct_gdp" />
                  </span>
                </span>
                {comp && <StatusBadge total={null} split={headlineSplit(comp)} compact />}
              </button>
              <div id={bodyId} className={s.cardBody} hidden={!isOpen}>
                {isOpen && (
                  <>
                    <FlowRows title={t("moneyIn")} links={io.in} other={(l) => l.payer} kindOf={kindOf} {...{ L, gdp, maxShare }} onSelect={props.onSelect} />
                    <FlowRows title={t("moneyOut")} links={io.out} other={(l) => l.receiver} kindOf={kindOf} {...{ L, gdp, maxShare }} onSelect={props.onSelect} />
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function FlowRows({
  title,
  links,
  other,
  kindOf,
  L,
  gdp,
  maxShare,
  onSelect,
}: {
  title: string;
  links: AggLink[];
  other: (l: AggLink) => string;
  kindOf: (id: string) => string;
  L: MapLabels;
  gdp: number;
  maxShare: number;
  onSelect?: (id: string | null) => void;
}) {
  const t = useTranslations("map");
  return (
    <>
      <h3 style={{ fontSize: "0.95rem", margin: "12px 0 4px" }}>{title}</h3>
      {links.length === 0 ? (
        <p className={s.muted}>{t("mobile.none")}</p>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {links.map((l) => {
            const share = Math.abs(l.value) / gdp;
            return (
              <li key={l.id}>
                <button type="button" className={s.rowButton} onClick={() => onSelect?.(l.id)} data-mobile-link={l.id}>
                  <span className={s.rowMain}>
                    {L.node(other(l))}
                    {l.part === "neg" && <span className={s.muted}> ({t("reversedMark")})</span>}
                    <span
                      className={s.bar}
                      aria-hidden="true"
                      style={{ width: `${Math.max(1, (share / maxShare) * 100)}%`, background: `var(--k-${kindOf(other(l))})` }}
                    />
                  </span>
                  <span className={s.rowValue}>
                    <Num value={l.value} fmt="inr" />
                    <br />
                    <Num value={l.value / gdp} fmt="pct_gdp" />
                  </span>
                  {l.split && <StatusBadge total={l.total} split={l.split} compact />}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
