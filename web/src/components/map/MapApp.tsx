"use client";
/**
 * The interactive Map page (PLAN §2.1, §4.3, §4.5, §4.6): view toggle, detail (preset), time
 * slider, the Sankey (desktop) or the phone list, the list/table alternative, and the detail panel.
 * The server renders the default state; this client child reads the URL after mount and applies it.
 * Slider moves use replaceState; selection, zoom and preset changes use pushState; Back restores
 * selection and zoom.
 */
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSeries } from "@/data/hooks";
import { SAM_YEAR } from "@/lib/ids";
import { buildSamModel } from "@/lib/sankey/model";
import { MAX_LINKS_PHONE } from "@/lib/sankey/style";
import { sliderMarkers, stageMarkers } from "@/lib/ts-board/markers";
import {
  DEFAULT_STATE,
  historyModeFor,
  normaliseState,
  parseUrlState,
  writeUrlState,
  type MapUrlState,
  type UrlNotice,
} from "@/lib/url-state";
import { FlowDetailPanel } from "./FlowDetailPanel";
import { collapseState, expandState, fyRange, keepYear } from "./state";
import { GroupButtons, LinkTable } from "./LinkTable";
import { MapMobile } from "./MapMobile";
import { defaultReturnFlows, MapView, type MapData } from "./MapView";
import { TsLists } from "./TsLists";
import { useMapLabels } from "./useLabels";
import { YearSlider, type YearChange } from "./YearSlider";
import s from "./map.module.css";

export function MapApp({ data }: { data: MapData }) {
  const t = useTranslations("map");
  const tc = useTranslations("common");
  const L = useMapLabels();
  const h = data.hierarchy;
  const series = useSeries();
  const periods = useMemo(
    () => series.data?.periods ?? fyRange(data.summary.ts.first, data.summary.ts.last),
    [series.data, data.summary.ts.first, data.summary.ts.last],
  );
  const ctx = useMemo(() => ({ hierarchy: h, years: periods }), [h, periods]);
  const [st, setSt] = useState<MapUrlState>(DEFAULT_STATE);
  const [notices, setNotices] = useState<UrlNotice[]>([]);
  const [arcs, setArcs] = useState(false);
  const [phoneDiagram, setPhoneDiagram] = useState(false);
  const opener = useRef<Element | null>(null);
  // the latest state for event handlers; written wherever the state is set
  const stRef = useRef(st);

  // apply the URL after mount, and again on Back/Forward
  useEffect(() => {
    const apply = (back: boolean) => {
      const r = parseUrlState(window.location.search, ctx);
      // Back/Forward restore selection and zoom, never the year (PLAN §2.1 item 10): slider moves
      // were replaceState, so an older entry may carry an older year; keep the one on screen.
      const next = back ? keepYear(r.state, stRef.current, ctx) : r.state;
      stRef.current = next;
      setSt(next);
      setNotices(r.notices);
      if (back && next.year !== r.state.year) writeUrlState(next, "replace");
    };
    apply(false);
    const onPop = () => apply(true);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [ctx]);

  const update = useCallback(
    (next: MapUrlState, mode?: "push" | "replace") => {
      const prev = stRef.current;
      const n = normaliseState(next, ctx);
      stRef.current = n;
      setSt(n);
      writeUrlState(n, mode ?? historyModeFor(prev, n));
    },
    [ctx],
  );

  const onSelect = useCallback(
    (id: string | null) => {
      if (id && typeof document !== "undefined") opener.current = document.activeElement;
      update({ ...stRef.current, selected: id });
    },
    [update],
  );
  const onClose = useCallback(() => {
    update({ ...stRef.current, selected: null });
    const el = opener.current as (Element & { focus?: () => void }) | null;
    requestAnimationFrame(() => {
      if (el && document.contains(el)) el.focus?.();
    });
  }, [update]);
  const onExpand = useCallback((id: string) => update(expandState(h, stRef.current, id)), [h, update]);
  const onCollapse = useCallback((id: string) => update(collapseState(h, stRef.current, id)), [h, update]);
  const onYear = useCallback(
    (year: string, how: YearChange) => {
      const cur = stRef.current;
      const view: "sam" | "ts" = year !== SAM_YEAR ? "ts" : how === "tick" ? "sam" : cur.view;
      update({ ...cur, year, view }, "replace");
    },
    [update],
  );

  const view: "sam" | "ts" = st.year !== SAM_YEAR ? "ts" : st.view;
  const returnFlows = arcs ? "arcs" : defaultReturnFlows(st.preset, st.expanded);
  const model = useMemo(
    () =>
      view === "sam"
        ? buildSamModel(
            { hierarchy: h, cells: data.cells, pinned: data.pinned, gdp: data.summary.gdp.value },
            st.preset,
            st.expanded,
            returnFlows,
          )
        : null,
    [view, h, data, st.preset, st.expanded, returnFlows],
  );
  const markers = useMemo(() => (series.data ? sliderMarkers(series.data) : []), [series.data]);
  const stages = useMemo(() => (series.data ? stageMarkers(series.data) : []), [series.data]);
  const yearIdx = periods.indexOf(st.year);
  const drawnTs = useMemo(() => {
    if (!series.data || yearIdx < 0) return 0;
    const byId = new Map(series.data.flows.map((f) => [f.id, f]));
    return data.tsView.ribbons.filter((r) => byId.get(r.flow)?.main.share[yearIdx] != null).length;
  }, [series.data, data.tsView, yearIdx]);

  const mapProps = {
    view,
    preset: st.preset,
    year: st.year,
    expanded: st.expanded,
    selected: st.selected,
    onSelect,
    returnFlows,
    initialData: data,
  } as const;

  const crumbs = st.expanded.map((id) => ({ id, label: L.node(id) }));

  return (
    <section className={s.mapSection} aria-labelledby="map-h2" data-map-app="" data-view={view} data-preset={st.preset}>
      <h2 id="map-h2">{t("section.heading")}</h2>
      <p className={s.intro}>{view === "sam" ? t("section.intro", { year: SAM_YEAR }) : t("section.introTs")}</p>
      {notices.length > 0 && (
        <div className={s.notice} role="status" data-url-notices="">
          {notices.map((n, i) => (
            <p key={i}>{tc(`url.${n.key.replace(/^url\./, "")}` as "url.invalidView", n.values)}</p>
          ))}
        </div>
      )}
      <div className={s.toolbar}>
        <div className={s.segmented} role="group" aria-label={t("controls.view")}>
          <button
            type="button"
            aria-pressed={view === "sam"}
            onClick={() => update({ ...st, view: "sam", year: SAM_YEAR }, "replace")}
            data-view-button="sam"
          >
            {t("controls.viewSam", { year: SAM_YEAR })}
          </button>
          <button type="button" aria-pressed={view === "ts"} onClick={() => update({ ...st, view: "ts" }, "replace")} data-view-button="ts">
            {t("controls.viewTs")}
          </button>
        </div>
        {view === "sam" && (
          <div className={s.segmented} role="group" aria-label={t("controls.detail")}>
            <button
              type="button"
              aria-pressed={st.preset === "simple"}
              onClick={() => update({ ...st, preset: "simple", expanded: [] })}
              data-preset-button="simple"
            >
              {t("controls.simple")}
            </button>
            <button
              type="button"
              aria-pressed={st.preset === "full"}
              onClick={() => update({ ...st, preset: "full" })}
              data-preset-button="full"
            >
              {t("controls.full")}
            </button>
          </div>
        )}
        {view === "sam" && st.preset === "simple" && st.expanded.length === 0 && (
          <label className={s.switch}>
            <input type="checkbox" checked={arcs} onChange={(e) => setArcs(e.currentTarget.checked)} />
            {t("controls.returnFlows")}
          </label>
        )}
        {view === "sam" && (
          <button
            type="button"
            className="btn btn-sm"
            aria-pressed={st.table}
            onClick={() => update({ ...st, table: !st.table }, "replace")}
            data-table-toggle=""
          >
            {st.table ? t("controls.hideList") : t("controls.table")}
          </button>
        )}
      </div>

      <YearSlider
        periods={periods}
        year={st.year}
        samYear={SAM_YEAR}
        coverage={data.tsView.coverage}
        totalFlows={data.summary.ts.flows}
        markers={markers}
        stages={stages}
        onChange={onYear}
      />

      {view === "ts" && (
        <div className={s.banner} data-ts-banner="">
          <p>{t("ts.banner", { year: st.year, n: String(drawnTs), samYear: SAM_YEAR })}</p>
          <p>
            <button type="button" className="btn btn-sm" onClick={() => onYear(SAM_YEAR, "tick")} data-see-complete="">
              {t("ts.seeComplete", { year: SAM_YEAR })}
            </button>
          </p>
        </div>
      )}

      {view === "sam" && st.expanded.length > 0 && (
        <nav className={s.crumbs} aria-label={t("controls.crumbs")}>
          <button type="button" className="btn btn-sm" onClick={() => update({ ...st, expanded: [] })}>
            {t("controls.crumbAll")}
          </button>
          {crumbs.map((c) => (
            <button
              key={c.id}
              type="button"
              className="btn btn-sm"
              onClick={() => update({ ...st, expanded: st.expanded.filter((x) => x !== c.id) })}
              aria-label={t("controls.collapse", { name: c.label })}
            >
              {c.label} −
            </button>
          ))}
        </nav>
      )}

      <div className={`${s.layout} ${st.selected ? s.layoutWithPanel : ""}`}>
        <div>
          {/* switching between the complete picture and top flows is an explicit 300 ms fade (none under reduced motion) */}
          <div key={view} className={`${s.desktopOnly} ${s.viewFade}`} data-desktop-map="">
            <MapView mode="interactive" {...mapProps} onExpand={onExpand} onCollapse={onCollapse} />
          </div>
          <div className={s.phoneOnly} data-phone-map="">
            <MapMobile mode="interactive" {...mapProps} />
            {view === "sam" && (
              <p>
                <button
                  type="button"
                  className="btn"
                  aria-expanded={phoneDiagram}
                  onClick={() => setPhoneDiagram((x) => !x)}
                  data-full-diagram=""
                >
                  {phoneDiagram ? t("controls.hideDiagram") : t("controls.fullDiagram")}
                </button>
              </p>
            )}
            {view === "sam" && phoneDiagram && (
              <div className={s.scrollRegion} role="region" tabIndex={0} aria-label={t("controls.fullDiagramRegion")}>
                <div className={s.scrollInner}>
                  <MapView mode="interactive" {...mapProps} onExpand={onExpand} onCollapse={onCollapse} maxLinks={MAX_LINKS_PHONE} />
                </div>
              </div>
            )}
          </div>
          {view === "sam" && model && st.table && (
            <div className={s.lists}>
              <GroupButtons nodes={model.nodes} L={L} onSelect={onSelect} selected={st.selected} />
              <LinkTable links={model.links} gdp={model.gdp} L={L} onSelect={onSelect} selected={st.selected} />
            </div>
          )}
          {view === "sam" && model && <SmallNote model={model} />}
          {view === "ts" && series.data && (
            <div className={s.desktopOnly}>
              <TsLists data={data} series={series.data} year={st.year} onSelect={onSelect} selected={st.selected} />
            </div>
          )}
        </div>
        {st.selected && (
          <FlowDetailPanel
            id={st.selected}
            year={st.year}
            scope={view === "ts" ? "ts" : st.expanded.length > 0 ? "full" : st.preset}
            onClose={onClose}
            onExpand={onExpand}
          />
        )}
      </div>
    </section>
  );
}

function SmallNote({ model }: { model: NonNullable<ReturnType<typeof buildSamModel>> }) {
  const t = useTranslations("map.list");
  const small = model.layout.links.filter((l) => !l.drawn);
  if (!small.length) return null;
  return (
    <p className={s.framing} data-small-links="">
      {t("small", { count: String(small.length) })}
    </p>
  );
}
