import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { DataFig } from "@/components/ui/DataFig";
import { DataText } from "@/components/methodology/DataText";
import { DataVersion } from "@/components/methodology/DataVersion";
import { METHODOLOGY_MDX } from "@/components/methodology/content-map";
import { SECTIONS } from "@/components/methodology/sections";
import { SourcesTable } from "@/components/methodology/SourcesTable";
import { sourceRows, sourceUsage } from "@/components/methodology/source-usage";
import { SummaryBadge } from "@/components/methodology/SummaryBadge";
import s from "@/components/methodology/methodology.module.css";
import {
  loadConstraints,
  loadEntries,
  loadIndex,
  loadProvenance,
  loadSeries,
  loadStory,
  storySlugs,
} from "@/data/server";

type Props = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "methodology.meta" });
  return { title: t("title"), description: t("description") };
}

/** Numbers in the MDX come only through these bindings (PLAN §3.9). */
const MDX_COMPONENTS = { DataFig, DataText, SummaryBadge };

function sourceTableRows() {
  const index = loadIndex();
  const provenance = loadProvenance();
  const entryFiles = Object.keys(index.files)
    .map((f) => /^sam\/entries\/([A-Za-z0-9_.-]+)\.json$/.exec(f)?.[1])
    .filter((x): x is string => !!x)
    .sort();
  const usage = sourceUsage({
    provenance,
    entries: entryFiles.map((l0) => loadEntries(l0)),
    series: loadSeries(),
    constraints: loadConstraints(),
    stories: storySlugs().map((slug) => loadStory(slug)),
  });
  return sourceRows(provenance, usage);
}

export default async function MethodologyPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "methodology" });
  const content = METHODOLOGY_MDX[locale];
  if (!content) throw new Error(`methodology: no content for locale "${locale}" in content-map.ts`);
  const index = loadIndex();
  const rows = sourceTableRows();

  return (
    <article className={`container ${s.page}`}>
      <header className={s.header}>
        <h1>{t("h1")}</h1>
        <p className={s.lede}>{t("lede")}</p>
        <p className={s.notForecast}>
          <strong>{t("notForecastLabel")}</strong> {t("notForecast")}
        </p>
      </header>

      <nav className={s.toc} aria-labelledby="methodology-toc">
        <h2 id="methodology-toc" className={s.tocHeading}>
          {t("toc")}
        </h2>
        <ol>
          {SECTIONS.map((sec) => (
            <li key={sec.id}>
              <a href={`#${sec.id}`}>{t(`sections.${sec.key}`)}</a>
            </li>
          ))}
        </ol>
      </nav>

      {SECTIONS.map((sec) => {
        const Body = content[sec.mdx];
        if (!Body) throw new Error(`methodology: missing content/${locale}/methodology/${sec.mdx}.mdx`);
        return (
          <section key={sec.id} id={sec.id} aria-labelledby={`${sec.id}-h`} className={s.section}>
            <h2 id={`${sec.id}-h`}>{t(`sections.${sec.key}`)}</h2>
            <div className={`prose ${s.prose}`}>
              <Body components={MDX_COMPONENTS} />
            </div>
            {sec.id === "sources" && <SourcesTable rows={rows} locale={locale} />}
            {sec.id === "data-version" && <DataVersion index={index} locale={locale} />}
          </section>
        );
      })}
    </article>
  );
}
