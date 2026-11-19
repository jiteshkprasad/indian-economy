import { useTranslations } from "next-intl";
import { Num, StatusBadge } from "@/components/ui";
import type { HeadlinePartKey } from "@/data/types";
import type { FirstScreenProps } from "./types";
import s from "./map.module.css";

/** Colour of each part of "each ₹100 of household income" (kind hue tokens). */
const PART_KIND: Record<HeadlinePartKey, string> = {
  consumption: "production",
  saving: "capital",
  taxes: "government",
  financial_services_and_interest: "corporations",
  transfers_abroad: "row",
  to_government: "government",
  unallocated_residual: "discrepancy",
};

/**
 * The headline figures with their badges (PLAN §4.0). Since round 3 (19 Nov 2026) they sit below
 * the hero, the game and the stories; the hero holds the page's h1. Rendered at build time.
 */
export function FirstScreen({ summary }: FirstScreenProps) {
  const t = useTranslations("map.first");
  const hh = summary.headline.hh_outlays;
  const parts = hh.parts.filter((p) => p.value !== 0);
  return (
    <section className={s.first} aria-labelledby="first-h2" data-first-screen="">
      <h2 id="first-h2" className={s.storiesHead}>
        {t("heading")}
      </h2>
      <div className={s.headCards}>
        <article className={s.headCard} data-headline="gdp">
          <h2>{t("gdp.title", { year: summary.gdp.year })}</h2>
          <p style={{ margin: 0 }}>
            <Num value={summary.gdp.value} fmt="inr" className={s.headValue} />{" "}
            {/* GDP is one published figure (series M01, PLAN §3.3): its own total, and not a sum of entries */}
            <StatusBadge total={summary.gdp.label} split={summary.gdp.label} single />
          </p>
          <p className={s.cardNote}>{t("gdp.note")}</p>
        </article>
        <article className={s.headCard} data-headline="hh_outlays">
          <h2>{t("hh.title")}</h2>
          <div className={s.per100Bar} aria-hidden="true">
            {parts.map((p) => (
              <span
                key={p.key}
                style={{ width: `${Math.max(0, p.per100)}%`, background: `var(--k-${PART_KIND[p.key]})` }}
              />
            ))}
          </div>
          <ul className={s.per100}>
            {parts.map((p) => (
              <li key={p.key} data-part={p.key}>
                <span>
                  <span aria-hidden="true" className={s.swatchSm} style={{ background: `var(--k-${PART_KIND[p.key]})` }} />
                  {t(`hh.parts.${p.key}`)}
                </span>
                <Num value={p.per100} fmt="per100" />
                {/* each part's own total label (V1-03 / V5-04): consumption and saving are held to NAS totals */}
                <StatusBadge total={p.total_label} split={p.split_label} pins={p.pins} compact />
              </li>
            ))}
          </ul>
          {/* the "taxes" part is the household → TAX node flow (personal income tax); GST is paid inside purchases */}
          <p className={s.cardNote}>
            {parts.some((p) => p.key === "taxes") && t("hh.taxNote")}
            {parts.some((p) => p.key === "taxes") && parts.some((p) => p.key === "unallocated_residual") && " "}
            {parts.some((p) => p.key === "unallocated_residual") && t("hh.residualNote")}
          </p>
        </article>
      </div>
    </section>
  );
}
