import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { FlowDetail } from "@/components/map/FlowDetailPanel";
import { SeriesTable } from "@/components/map/SeriesTable";
import { latestYear, seriesIds, seriesPreload } from "@/components/map/server";
import { IntlClient } from "@/components/ui/IntlClient";
import { MapTextProvider } from "@/data/map-text-context";
import { loadMapText } from "@/data/server";
import { Link } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";

type Props = { params: Promise<{ locale: string; id: string }> };

export const dynamicParams = false;

/** The 69 time-series flows (PLAN §4.2). */
export function generateStaticParams() {
  const ids = seriesIds();
  return routing.locales.flatMap((locale) => ids.map((id) => ({ locale, id })));
}

function seriesLabel(locale: string, id: string): string {
  const label = loadMapText(locale).series[id]?.label;
  if (!label) throw new Error(`series page: map-text.json has no label for series ${id}`);
  return label;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, id } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "map.series" });
  return { title: seriesLabel(locale, id), description: t("kicker") };
}

/** `/en/series/<id>/`: one annual series with every year, its breaks and its sources. */
export default async function SeriesPage({ params }: Props) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "map.series" });
  const preload = seriesPreload(id, locale);
  const year = latestYear(preload.series, id);
  const flow = preload.series.flows[0];
  return (
    <div className="container" data-series-page={id}>
      <p style={{ margin: "12px 0 0" }}>
        <Link href={`/?view=ts&y=${year}&s=${id}`} data-on-map="">
          {t("onMap")}
        </Link>
      </p>
      <IntlClient namespaces={["map"]}>
        <MapTextProvider value={loadMapText(locale)}>
          <article data-flow-panel="" data-id={id}>
            <FlowDetail id={id} year={year} preload={preload} headingLevel={1} standalone />
          </article>
        </MapTextProvider>
      </IntlClient>
      <SeriesTable series={preload.series} flow={flow} />
    </div>
  );
}
