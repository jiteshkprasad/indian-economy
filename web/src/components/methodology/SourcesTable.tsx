import { getTranslations } from "next-intl/server";
import type { SourceRow } from "./source-usage";
import s from "./methodology.module.css";

/**
 * Every source in provenance.sources (PLAN §4.10 item 6): publisher, licence,
 * attribution (copied from data/registry.yaml by the exporter), link mode and how
 * many SAM entries, series, constraints and story figures cite it. A list of
 * cards rather than a wide table, so it reads on a phone without sideways scroll.
 * Withheld sources (RBI until permission) never get a link.
 */
export async function SourcesTable({ rows, locale }: { rows: SourceRow[]; locale: string }) {
  const t = await getTranslations({ locale, namespace: "methodology.sources" });
  return (
    <ul className={s.sourceList} aria-label={t("listLabel", { count: rows.length })} data-sources-table="">
      {rows.map((r) => {
        const u = r.usage;
        const cited = [
          u.entries > 0 ? t("usageEntries", { count: u.entries }) : null,
          u.series > 0 ? t("usageSeries", { count: u.series }) : null,
          u.constraints > 0 ? t("usageConstraints", { count: u.constraints }) : null,
          u.storyFigures > 0 ? t("usageStories", { count: u.storyFigures }) : null,
        ].filter((x): x is string => x !== null);
        return (
          <li key={r.id} className={s.sourceCard} data-source-id={r.id} data-link-mode={r.linkMode}>
            <h3 className={s.sourceTitle}>{r.name}</h3>
            <dl className={s.sourceDl}>
              <dt>{t("publisher")}</dt>
              <dd>{r.publisher || t("unknown")}</dd>
              <dt>{t("licence")}</dt>
              <dd>{r.licence || t("unknown")}</dd>
              <dt>{t("attribution")}</dt>
              <dd>{r.attribution || t("unknown")}</dd>
              <dt>{t("link")}</dt>
              <dd>
                {r.linkMode === "withheld" ? (
                  <span className={s.withheld}>{t("withheld")}</span>
                ) : r.href ? (
                  <a href={r.href} rel="noopener noreferrer" target="_blank" className={s.sourceLink}>
                    {r.linkMode === "landing" ? t("landingLink") : t("deepLink")}
                    <span className="visually-hidden">{t("opensNewTab", { name: r.name })}</span>
                  </a>
                ) : (
                  <span>{t("noLink")}</span>
                )}
              </dd>
              <dt>{t("citedBy")}</dt>
              <dd>{cited.length > 0 ? cited.join(t("listSep")) : t("notCited")}</dd>
              <dt>{t("registryStatus")}</dt>
              <dd>
                <code>{r.id}</code>
                {r.registryStatus ? ` · ${r.registryStatus}` : null}
              </dd>
            </dl>
          </li>
        );
      })}
    </ul>
  );
}
