"use client";
/**
 * A small trend chart of one series (PLAN §3.7.4, §4.7 item 3): share of GDP (default) or ₹ crore,
 * data-driven markers for every break, and the SAM 2023-24 value as a separate point. Gaps stay
 * gaps: nothing is interpolated. Fewer than three values are shown as values, not as a trend.
 */
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Num } from "@/components/ui";
import type { Series, SeriesArrays, SeriesFlow } from "@/data/types";
import { formatInr, formatPctGdp } from "@/lib/format";
import { flowMarkers } from "@/lib/ts-board/markers";
import { useSubLevel } from "./heading-level";
import type { SamPoint } from "./panel-text";
import s from "./map.module.css";

const W = 360;
const H = 170;
const PAD = { l: 44, r: 10, t: 10, b: 24 };

function pathOf(xs: number[], ys: Array<number | null>): string {
  let d = "";
  let pen = false;
  ys.forEach((y, i) => {
    if (y === null || !Number.isFinite(y)) {
      pen = false;
      return;
    }
    d += `${pen ? "L" : "M"}${xs[i].toFixed(1)},${y.toFixed(1)}`;
    pen = true;
  });
  return d;
}

function valuesOf(a: SeriesArrays, mode: "share" | "value", sign: number): Array<number | null> {
  return mode === "share" ? a.share.map((v) => (v === null ? null : v)) : a.v.map((v) => (v === null ? null : v * sign));
}

export function TrendChart({
  series,
  flow,
  label,
  sam,
  samYear,
  highlightYear,
}: {
  series: Series;
  flow: SeriesFlow;
  label: string;
  sam: SamPoint;
  samYear: string;
  highlightYear?: string;
}) {
  const t = useTranslations("map.panel");
  const H4 = useSubLevel() === 2 ? "h3" : "h4"; // one below the panel's section headings (V4-08)
  const [mode, setMode] = useState<"share" | "value">("share");
  const [linked, setLinked] = useState(false);
  const main = valuesOf(flow.main, mode, flow.display_sign);
  const lin = linked && flow.linked ? valuesOf(flow.linked, mode, flow.display_sign) : null;
  const idx = main.map((v, i) => (v === null ? -1 : i)).filter((i) => i >= 0);
  if (idx.length < 3) {
    return (
      <div data-trend="values">
        <H4>{t("values")}</H4>
        <ul className={s.smallList}>
          {idx.map((i) => (
            <li key={i}>
              {series.periods[i]}: <Num value={flow.main.v[i]! * flow.display_sign} fmt="inr" />
              {flow.main.share[i] !== null && (
                <>
                  {" "}
                  (<Num value={flow.main.share[i]!} fmt="pct_gdp" />)
                </>
              )}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  const i0 = Math.min(idx[0], ...(lin ? lin.map((v, i) => (v === null ? Infinity : i)) : []));
  const i1 = idx[idx.length - 1];
  const samIdx = series.periods.indexOf(samYear);
  const samY = sam ? (mode === "share" ? sam.share : sam.value) : null;
  const all = [...main, ...(lin ?? []), samY].filter((v): v is number => v !== null && Number.isFinite(v));
  const dataMax = Math.max(...all);
  const dataMin = Math.min(...all);
  let lo = Math.min(0, dataMin);
  let hi = Math.max(0, dataMax);
  if (hi === lo) hi = lo + 1;
  const span = hi - lo;
  lo -= span * 0.05;
  hi += span * 0.08;
  const x = (i: number) => PAD.l + ((i - i0) / Math.max(1, i1 - i0)) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - (v - lo) / (hi - lo)) * (H - PAD.t - PAD.b);
  const xs = series.periods.map((_, i) => x(i));
  const ysMain = main.map((v) => (v === null ? null : y(v)));
  const ysLin = lin ? lin.map((v) => (v === null ? null : y(v))) : null;
  const fmt = (v: number) => (mode === "share" ? formatPctGdp(v).replace(" of GDP", "") : formatInr(v));
  const markers = flowMarkers(series, flow).filter((m) => m.index >= i0 && m.index <= i1);
  const hiIdx = highlightYear ? series.periods.indexOf(highlightYear) : -1;
  const aria = t("chartLabel", { label, first: series.periods[i0], last: series.periods[i1] });
  return (
    <div data-trend="chart">
      <div className="sliderRow" style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <div className={s.segmented} role="group" aria-label={t("trend")}>
          <button type="button" aria-pressed={mode === "share"} onClick={() => setMode("share")}>
            {t("asShare")}
          </button>
          <button type="button" aria-pressed={mode === "value"} onClick={() => setMode("value")}>
            {t("asValue")}
          </button>
        </div>
        {flow.linked && flow.link_policy === "linked" && (
          <label className={s.switch}>
            <input type="checkbox" checked={linked} onChange={(e) => setLinked(e.currentTarget.checked)} />
            {t("linked")}
          </label>
        )}
      </div>
      {linked && flow.linked && <p className={s.framing}>{t("linkedNote", { base: flow.linked.base.find((b) => b) ?? "" })}</p>}
      <svg className={s.chart} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={aria}>
        <line x1={PAD.l} x2={W - PAD.r} y1={y(0)} y2={y(0)} className={s.chartAxis} />
        <line x1={PAD.l} x2={PAD.l} y1={PAD.t} y2={H - PAD.b} className={s.chartAxis} />
        <text x={PAD.l - 4} y={y(dataMax) + 4} textAnchor="end" className={s.chartText}>
          {fmt(dataMax)}
        </text>
        <text x={PAD.l - 4} y={y(Math.min(0, dataMin)) + 4} textAnchor="end" className={s.chartText}>
          {dataMin < 0 ? fmt(dataMin) : "0"}
        </text>
        <text x={PAD.l} y={H - 6} className={s.chartText}>
          {series.periods[i0]}
        </text>
        <text x={W - PAD.r} y={H - 6} textAnchor="end" className={s.chartText}>
          {series.periods[i1]}
        </text>
        {markers.map((m) => (
          <line key={`${m.period}-${m.kind}`} x1={x(m.index)} x2={x(m.index)} y1={PAD.t} y2={H - PAD.b} className={s.chartMarker} data-chart-marker={m.kind}>
            <title>{`${m.period}: ${m.note}`}</title>
          </line>
        ))}
        {ysLin && <path d={pathOf(xs, ysLin)} className={s.chartLinked} />}
        <path d={pathOf(xs, ysMain)} className={s.chartLine} />
        {hiIdx >= 0 && main[hiIdx] !== null && <circle cx={x(hiIdx)} cy={y(main[hiIdx]!)} r={4} className={s.chartDot} />}
        {samY !== null && samIdx >= 0 && (
          <g data-sam-point="">
            <rect x={x(samIdx) - 4} y={y(samY) - 4} width={8} height={8} className={s.chartSam} transform={`rotate(45 ${x(samIdx)} ${y(samY)})`} />
            <title>{`${t("samPoint", { samYear })}: ${fmt(samY)}`}</title>
          </g>
        )}
      </svg>
      <p className={s.framing}>
        <span aria-hidden="true" style={{ color: "var(--st-balancing)" }}>
          ◆
        </span>{" "}
        {t("samPoint", { samYear })}
        {sam && (
          <>
            {": "}
            {mode === "share" ? <Num value={sam.share} fmt="pct_gdp" /> : <Num value={sam.value} fmt="inr" />}
          </>
        )}
      </p>
      {markers.length > 0 && (
        <ul className={s.smallList} data-marker-list="">
          {markers.map((m) => (
            <li key={`${m.period}-${m.kind}-${m.note}`}>
              {m.period}: {m.note}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
