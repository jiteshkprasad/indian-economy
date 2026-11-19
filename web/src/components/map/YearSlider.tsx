"use client";
/**
 * The time slider (PLAN §2.1, §4.6): a native range input (thumb ≥ 24 px) with aria-valuetext, a
 * year <select> (the precise control), ◀ ▶ step buttons, Play/Pause (kept under reduced motion:
 * steps are instant), data-driven marker ticks and the "complete map" tick. A polite live region
 * announces "2004-05: 24 of 69 flows have data" on manual steps and when Play stops, never on
 * every tick of Play.
 */
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import type { PeriodMarker } from "@/lib/ts-board/markers";
import s from "./map.module.css";

/** Width of the range thumb in CSS px (map.module.css .range::-webkit-slider-thumb). */
const THUMB = 24;

export type YearChange = "step" | "scrub" | "select" | "tick" | "play";

export type YearSliderProps = {
  periods: string[];
  year: string;
  samYear: string;
  coverage: number[];
  totalFlows: number;
  markers: PeriodMarker[];
  stages: Array<{ period: string; index: number; stages: string[] }>;
  onChange: (year: string, how: YearChange) => void;
};

export function YearSlider(p: YearSliderProps) {
  const t = useTranslations("map");
  const idx = Math.max(0, p.periods.indexOf(p.year));
  const last = p.periods.length - 1;
  const [playing, setPlaying] = useState(false);
  const [message, setMessage] = useState("");
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const idxRef = useRef(idx);
  useEffect(() => {
    idxRef.current = idx;
  }, [idx]);

  const announce = (i: number) =>
    setMessage(
      t("ts.announce", { year: p.periods[i], n: String(p.coverage[i] ?? 0), total: String(p.totalFlows) }),
    );

  const go = (i: number, how: YearChange) => {
    const j = Math.max(0, Math.min(last, i));
    p.onChange(p.periods[j], how);
    if (how !== "play") announce(j);
  };

  // `i` is the year Play stopped on: inside the interval idxRef still holds the year before the
  // last onChange (the re-render has not happened yet), so the caller passes the index it set.
  const stop = (i: number = idxRef.current) => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    setPlaying(false);
    announce(i);
  };

  useEffect(
    () => () => {
      if (timer.current) clearInterval(timer.current);
    },
    [],
  );

  const play = () => {
    if (playing) return stop();
    let i = idx >= last ? 0 : idx;
    if (idx >= last) p.onChange(p.periods[0], "play");
    setPlaying(true);
    timer.current = setInterval(() => {
      i += 1;
      if (i > last) {
        stop(last);
        return;
      }
      p.onChange(p.periods[i], "play");
      if (i === last) stop(i);
    }, 1000);
  };

  const here = p.markers.find((m) => m.index === idx);
  const stageHere = p.stages.find((m) => m.index === idx);
  const samIdx = p.periods.indexOf(p.samYear);
  // where the thumb's centre sits for index i (thumb 24 px wide: see .range in map.module.css)
  const pos = (i: number) => `calc(${THUMB / 2}px + (100% - ${THUMB}px) * ${last > 0 ? i / last : 0})`;

  return (
    <div className={s.slider} data-year-slider="">
      <div className={s.sliderRow}>
        <button
          type="button"
          className="btn btn-sm"
          onClick={() => {
            if (playing) stop();
            go(idx - 1, "step");
          }}
          disabled={idx <= 0}
          aria-label={t("slider.prev")}
        >
          ◀
        </button>
        <div className={s.rangeBox}>
        <input
          type="range"
          className={s.range}
          min={0}
          max={last}
          step={1}
          value={idx}
          aria-label={t("slider.label")}
          aria-valuetext={p.periods[idx]}
          onChange={(e) => {
            if (playing) stop();
            go(Number(e.currentTarget.value), "scrub");
          }}
          data-year-range=""
        />
          {/* the ticks share the range input's box: the thumb's centre runs from 12 px to (width − 12 px) */}
          <div className={s.ticks} aria-hidden="true">
            {p.markers.map((m) => (
              <span key={m.period} className={s.tick} style={{ left: pos(m.index) }} title={`${m.period}: ${m.notes.join("; ")}`} data-marker={m.period} />
            ))}
            {samIdx >= 0 && <span className={s.tickSam} style={{ left: pos(samIdx) }} title={t("slider.completeTick")} data-tick-sam="" />}
          </div>
        </div>
        <button
          type="button"
          className="btn btn-sm"
          onClick={() => {
            if (playing) stop();
            go(idx + 1, "step");
          }}
          disabled={idx >= last}
          aria-label={t("slider.next")}
        >
          ▶
        </button>
        <label>
          <span className="visually-hidden">{t("slider.select")}</span>
          <select
            className={s.yearSelect}
            value={p.periods[idx]}
            onChange={(e) => {
              if (playing) stop();
              go(p.periods.indexOf(e.currentTarget.value), "select");
            }}
            data-year-select=""
          >
            {p.periods.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn btn-sm" onClick={play} aria-pressed={playing} data-play="">
          {playing ? t("slider.pause") : t("slider.play")}
        </button>
        {samIdx >= 0 && (
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => {
              if (playing) stop();
              p.onChange(p.samYear, "tick");
              announce(samIdx);
            }}
            data-complete-tick=""
          >
            {t("slider.completeTick")} ({p.samYear})
          </button>
        )}
      </div>
      <p className={s.sliderLegend}>{t("slider.legend", { year: p.samYear })}</p>
      {(here || stageHere) && (
        <div data-year-notes="">
          {here && (
            <details className={s.sliderLegend}>
              <summary className={s.summary}>{t("slider.markersHeading", { n: String(here.notes.length) })}</summary>
              <ul className={s.markerList}>
                {here.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </details>
          )}
          {stageHere && <p className={s.sliderLegend}>{t("slider.stage", { stages: stageHere.stages.join(", ") })}</p>}
        </div>
      )}
      <p className="visually-hidden" aria-live="polite" data-live="">
        {message}
      </p>
    </div>
  );
}
