import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { FlowDetail } from "@/components/map/FlowDetailPanel";
import { flowPreload, level0LinkIds, presetOf } from "@/components/map/server";
import { IntlClient } from "@/components/ui/IntlClient";
import { MapTextProvider } from "@/data/map-text-context";
import { loadMapText } from "@/data/server";
import { Link } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { SAM_YEAR } from "@/lib/ids";

type Props = { params: Promise<{ locale: string; id: string }> };

export const dynamicParams = false;

/** Every level-0 link of both presets (positive and `~neg` parts), PLAN §4.2 and D3-12. */
export function generateStaticParams() {
  const ids = level0LinkIds();
  return routing.locales.flatMap((locale) => ids.map((id) => ({ locale, id })));
}

function linkLabel(locale: string, id: string): string {
  const label = loadMapText(locale).links[id]?.label;
  // map-text covers every level-0 link (U6); a gap is a content bug and fails the build
  if (!label) throw new Error(`flow page: map-text.json has no label for link ${id}`);
  return label;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, id } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "map.flow" });
  return { title: linkLabel(locale, decodeURIComponent(id)), description: t("kicker", { year: SAM_YEAR }) };
}

/** `/en/flow/<link id>/`: one level-0 flow, rendered at build time (readable without JavaScript). */
export default async function FlowPage({ params }: Props) {
  const { locale, id: raw } = await params;
  setRequestLocale(locale);
  const id = decodeURIComponent(raw);
  const t = await getTranslations({ locale, namespace: "map.flow" });
  const preload = flowPreload(id, locale);
  const preset = presetOf(id);
  return (
    <div className="container" data-flow-page={id}>
      <p style={{ margin: "12px 0 0" }}>
        <Link href={`/?p=${preset}&s=${encodeURIComponent(id)}`} data-on-map="">
          {t("onMap")}
        </Link>{" "}
        · {t("preset", { preset: t(preset) })}
      </p>
      <IntlClient namespaces={["map"]}>
        <MapTextProvider value={loadMapText(locale)}>
          <article data-flow-panel="" data-id={id}>
            <FlowDetail id={id} year={SAM_YEAR} scope={preset} preload={preload} headingLevel={1} standalone />
          </article>
        </MapTextProvider>
      </IntlClient>
    </div>
  );
}
