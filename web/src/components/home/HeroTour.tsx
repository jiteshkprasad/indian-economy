"use client";
import { useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { MapView } from "@/components/map";
import { useMapData } from "@/components/map/MapView";
import { HighlightList } from "@/components/story/HighlightList";
import { Num, StatusBadge, useAnnounce } from "@/components/ui";
import type { FmtKind } from "@/lib/format";
import type { Label, StoryView, TotalLabel } from "@/data/types";
import type { StorySlug } from "@/lib/story/registry";
import { prefersReducedMotion } from "@/lib/sankey/animate";
import { MAX_LINKS_DESKTOP } from "@/lib/sankey/style";
import s from "./home.module.css";

/** A story figure, only the fields shown here. */
export type TourFig = { value: number; unit: string; total: TotalLabel | null; split: Label };
export type TourStopData = { step: string; view: StoryView; a: TourFig; b: TourFig | null };
export type TourData = { slug: StorySlug; stops: TourStopData[] };

const PHONE = "(max-width: 639.98px)";
const noSubscribe = () => () => {};

function usePhone(): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const mq = window.matchMedia(PHONE);
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    },
    () => window.matchMedia(PHONE).matches,
    () => false,
  );
}

/** true after hydration (the map mounts then, as in the story player). */
function useMounted(): boolean {
  return useSyncExternalStore(
    noSubscribe,
    () => true,
    () => false,
  );
}

/** false under prefers-reduced-motion, and on the server (no moving stripes until hydrated). */
function useMotion(): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    },
    () => !prefersReducedMotion(),
    () => false,
  );
}

const OVERVIEW: StoryView = { view: "sam", preset: "simple", year: "2023-24", expanded: [], highlight: [], select: null };

function Fig({ f }: { f: TourFig }) {
  return <Num value={f.value} fmt={f.unit as FmtKind} className={s.capNum} />;
}

/**
 * "Follow a rupee": the map on the first screen, first as the whole economy with money moving
 * along it, then one rupee at a time (GST, a remittance, a borrowed rupee), five stops each.
 * Each stop is a story step's map view with a one-line caption around exported figures.
 * Another component (the guessing game) can open a stop through the `iem:tour` window event.
 */
export function HeroTour({ tours }: { tours: TourData[] }) {
  const t = useTranslations("map.tour");
  const ts = useTranslations("story");
  const announce = useAnnounce();
  const phone = usePhone();
  const mounted = useMounted();
  const [pick, setPick] = useState<{ slug: StorySlug; i: number } | null>(null);
  const motion = useMotion();
  const regionRef = useRef<HTMLDivElement>(null);
  const { data: mapData } = useMapData();
  useEffect(() => {
    const on = (e: Event) => {
      const d = (e as CustomEvent<{ slug: StorySlug; step: string }>).detail;
      const tour = tours.find((x) => x.slug === d.slug);
      const i = tour?.stops.findIndex((st) => st.step === d.step) ?? -1;
      if (tour && i >= 0) {
        setPick({ slug: d.slug, i });
        announce(t("announce", { chip: t(`chips.${d.slug}`), n: i + 1, total: tour.stops.length, title: ts(`stories.${d.slug}.steps.${d.step}`) }));
        // after the new stop has rendered, bring the map into view
        requestAnimationFrame(() => document.getElementById("tour")?.scrollIntoView({ block: "start" }));
      }
    };
    window.addEventListener("iem:tour", on);
    return () => window.removeEventListener("iem:tour", on);
  }, [tours, announce, t, ts]);

  const tour = pick ? tours.find((x) => x.slug === pick.slug)! : null;
  const stop = tour && pick ? tour.stops[pick.i] : null;
  const view = stop?.view ?? OVERVIEW;
  const title = (slug: StorySlug, step: string) => ts(`stories.${slug}.steps.${step}`);

  const go = (slug: StorySlug, i: number) => {
    const tr = tours.find((x) => x.slug === slug)!;
    setPick({ slug, i });
    announce(t("announce", { chip: t(`chips.${slug}`), n: i + 1, total: tr.stops.length, title: title(slug, tr.stops[i].step) }));
  };

  // Keep every label inside the frame: node and value labels near the edges are drawn past the
  // viewBox (they keep a minimum on-screen size), so widen the viewBox to the drawing's own box.
  // Re-measured after the path tween (300 ms) settles.
  const viewKey = `${pick ? `${pick.slug}:${pick.i}` : "overview"}|${phone}`;
  useLayoutEffect(() => {
    const fit = () => {
      const svg = regionRef.current?.querySelector<SVGSVGElement>("svg[data-map-svg]");
      const g = svg?.querySelector<SVGGElement>("g[role=group]");
      if (!svg || !g) return;
      // the map's own viewBox, unless the attribute still holds the one set here last time
      const cur = svg.getAttribute("viewBox");
      const vb = cur === svg.getAttribute("data-vb-fit") ? svg.getAttribute("data-vb0") : cur;
      if (!vb) return;
      svg.setAttribute("data-vb0", vb);
      const [x0, y0, w0, h0] = vb.split(" ").map(Number);
      const b = g.getBBox();
      const pad = 0.02 * w0; // room for labels to grow a little as the drawing shrinks
      const x = Math.min(x0, b.x - pad);
      const w = Math.max(x0 + w0, b.x + b.width + pad) - x;
      const fitted = `${x.toFixed(1)} ${y0} ${w.toFixed(1)} ${h0}`;
      svg.setAttribute("viewBox", fitted);
      svg.setAttribute("data-vb-fit", fitted);
    };
    // Widening the viewBox shrinks the drawing, which makes the minimum-size labels larger in
    // viewBox units, so fit again whenever the map resizes, and after the tween, until it settles.
    fit();
    const ids = [150, 350, 700, 1200].map((ms) => window.setTimeout(fit, ms));
    const svg = regionRef.current?.querySelector("svg[data-map-svg]");
    const ro = typeof ResizeObserver !== "undefined" && svg ? new ResizeObserver(() => requestAnimationFrame(fit)) : null;
    if (ro && svg) ro.observe(svg);
    return () => {
      ids.forEach((id) => window.clearTimeout(id));
      ro?.disconnect();
    };
  }, [viewKey, mounted]);

  return (
    <div className={s.tour} id="tour" data-tour="" data-tour-state={pick ? `${pick.slug}:${pick.i}` : "overview"}>
      <div className={s.chips} role="group" aria-label={t("pick")}>
        <button type="button" className={s.chip} aria-pressed={pick === null} onClick={() => setPick(null)} data-chip="overview">
          {t("overview")}
        </button>
        {tours.map((x) => (
          <button
            key={x.slug}
            type="button"
            className={s.chip}
            aria-pressed={pick?.slug === x.slug}
            onClick={() => go(x.slug, 0)}
            data-chip={x.slug}
          >
            {t(`chips.${x.slug}`)}
          </button>
        ))}
      </div>

      <div className={s.tourGrid}>
        <div className={s.caption} aria-live="off" data-tour-caption="">
          {tour && stop && pick ? (
            <>
              <p className={s.capStep}>
                {t("position", { n: pick.i + 1, total: tour.stops.length })} · {title(tour.slug, stop.step)}
              </p>
              <p className={s.capText}>
                {t(`${tour.slug}.${stop.step}.before`)}
                <Fig f={stop.a} />
                {stop.b && (
                  <>
                    {t(`${tour.slug}.${stop.step}.middle`)}
                    <Fig f={stop.b} />
                  </>
                )}
                {t(`${tour.slug}.${stop.step}.after`)}
              </p>
              <p className={s.capMeta}>
                <StatusBadge total={stop.a.total} split={stop.a.split} compact />{" "}
                <Link href={`/story/${tour.slug}/?step=${stop.step}`}>{t("full")}</Link>
              </p>
              <div className={s.capNav}>
                <button type="button" className={s.navBtn} aria-disabled={pick.i === 0} onClick={() => pick.i > 0 && go(tour.slug, pick.i - 1)}>
                  {t("prev")}
                </button>
                <button
                  type="button"
                  className={`${s.navBtn} ${s.navPrimary}`}
                  aria-disabled={pick.i === tour.stops.length - 1}
                  onClick={() => pick.i < tour.stops.length - 1 && go(tour.slug, pick.i + 1)}
                  data-tour-next=""
                >
                  {t("next")}
                </button>
              </div>
            </>
          ) : (
            <>
              <p className={s.capText}>{t("overviewText")}</p>
              <div className={s.capNav}>
                <button type="button" className={`${s.navBtn} ${s.navPrimary}`} onClick={() => go(tours[0].slug, 0)} data-tour-start="">
                  {t("start")}: {t(`chips.${tours[0].slug}`)}
                </button>
              </div>
            </>
          )}
          <p className={s.capMeta}>
            <a href="#map-h2">{t("explore")}</a>
          </p>
        </div>

        <div
          ref={regionRef}
          className={s.tourMap}
          role="region"
          aria-label={t("mapLabel", { title: tour && stop ? title(tour.slug, stop.step) : t("overview") })}
          aria-busy={mounted ? undefined : true}
        >
          {mounted && (
            <MapView
              mode="controlled"
              view={view.view}
              preset={view.preset}
              year={view.year}
              expanded={view.expanded}
              selected={view.select}
              highlight={view.highlight}
              onlyHighlighted={view.highlight.length > 0}
              height={phone ? undefined : 460}
              maxLinks={MAX_LINKS_DESKTOP}
              flowing={motion}
            />
          )}
        </div>
        {mounted && mapData && stop && (
          <div className={s.flowList} data-tour-flows="">
            <HighlightList
              cells={mapData.cells}
              hierarchy={mapData.hierarchy}
              pinned={mapData.pinned}
              gdp={mapData.summary.gdp.value}
              view={stop.view}
            />
          </div>
        )}
      </div>
    </div>
  );
}
