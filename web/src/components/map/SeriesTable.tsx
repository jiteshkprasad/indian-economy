/**
 * The all-years view of one time-series flow for its static page (PLAN §4.2, `/en/series/<id>/`):
 * every year with its value, share of GDP (same base), label, base year and estimate stage; the
 * data-driven breaks; the linking decision; and other published versions. Rendered at build time.
 * Values are as exported × display_sign (a subsidy reads as a positive "subsidy paid").
 */
import { useTranslations } from "next-intl";
import { Num, StatusBadge } from "@/components/ui";
import { seriesTotal } from "./panel-text";
import type { Series, SeriesArrays, SeriesFlow } from "@/data/types";
import { flowMarkers } from "@/lib/ts-board/markers";
import s from "./map.module.css";

function YearTable({ series, arrays, sign, caption }: { series: Series; arrays: SeriesArrays; sign: number; caption: string }) {
  const t = useTranslations("map.series");
  const rows = series.periods.map((p, i) => ({ p, i })).filter(({ i }) => arrays.v[i] !== null);
  return (
    <div className={s.tableWrap} tabIndex={0} role="region" aria-label={caption}>
      <table className={s.table} data-series-table="">
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">{t("year")}</th>
            <th scope="col" className={s.numCell}>
              {t("value")}
            </th>
            <th scope="col" className={s.numCell}>
              {t("share")}
            </th>
            <th scope="col">{t("status")}</th>
            <th scope="col">{t("base")}</th>
            <th scope="col">{t("stage")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ p, i }) => {
            const status = arrays.status[i];
            return (
              <tr key={p} data-period={p}>
                <th scope="row">{p}</th>
                <td className={s.numCell}>
                  <Num value={arrays.v[i]! * sign} fmt="inr" />
                </td>
                <td className={s.numCell}>{arrays.share[i] !== null ? <Num value={arrays.share[i]!} fmt="pct_gdp" /> : "·"}</td>
                <td>{status ? <StatusBadge total={seriesTotal(status)} split={status} single compact /> : "·"}</td>
                <td>{arrays.base[i] ?? "·"}</td>
                <td>{arrays.stage[i] ?? "·"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function SeriesTable({ series, flow }: { series: Series; flow: SeriesFlow }) {
  const t = useTranslations("map.series");
  const markers = flowMarkers(series, flow);
  return (
    <section aria-labelledby="series-years" data-series-years="">
      <h2 id="series-years">{t("table")}</h2>
      <YearTable series={series} arrays={flow.main} sign={flow.display_sign} caption={t("table")} />
      <h2>{t("markers")}</h2>
      {markers.length ? (
        <ul className={s.smallList} data-marker-list="">
          {markers.map((m) => (
            <li key={`${m.period}-${m.kind}-${m.note}`}>
              {m.period}: {m.note}
            </li>
          ))}
        </ul>
      ) : (
        <p>{t("noMarkers")}</p>
      )}
      {flow.link_policy === "refused" && flow.link_reason && <p className={s.framing}>{t("linkRefused", { reason: flow.link_reason })}</p>}
      {flow.alts.length > 0 && (
        <>
          <h2>{t("alts")}</h2>
          {flow.alts.map((a) => (
            <div key={a.variant}>
              <h3>{t(`alt_${a.variant}`)}</h3>
              <YearTable series={series} arrays={a.arrays} sign={flow.display_sign} caption={t(`alt_${a.variant}`)} />
            </div>
          ))}
        </>
      )}
    </section>
  );
}
