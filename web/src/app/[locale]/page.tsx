import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { FirstScreen } from "@/components/map";
import { GuessGame } from "@/components/home/GuessGame";
import { Hero } from "@/components/home/Hero";
import { loadGuesses, loadTours, sourceCount } from "@/components/home/server";
import { MapApp } from "@/components/map/MapApp";
import { StoryCards } from "@/components/story/StoryCards";
import { IntlClient } from "@/components/ui/IntlClient";
import { LiveRegionProvider } from "@/components/ui/LiveRegion";
import s from "@/components/map/map.module.css";
import { MapTextProvider } from "@/data/map-text-context";
import { loadCells, loadHierarchy, loadMapText, loadPinned, loadSummary, loadTsView } from "@/data/server";

type Props = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "common.site" });
  return { title: { absolute: t("title") }, description: t("description") };
}

/**
 * `/en/` (round 3, founder 19 Nov 2026: show the project's strength first, and make it playable):
 * the hero (what this is, the proof strip, the map with the rupee tour), the guessing game, the
 * three stories, the household ₹100 and GDP cards, then the full Map. Everything is rendered at
 * build time in its default state; the client parts (tour map, game, Map) take over after mount.
 */
export default async function HomePage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "map.first" });
  const summary = loadSummary();
  const data = {
    summary,
    hierarchy: loadHierarchy(),
    cells: loadCells(),
    pinned: loadPinned(),
    tsView: loadTsView(),
  };
  return (
    <div className="container">
      <IntlClient namespaces={["map", "story"]}>
        <MapTextProvider value={loadMapText(locale)}>
          <LiveRegionProvider>
            <Hero summary={summary} sources={sourceCount()} tours={loadTours()} />
            <GuessGame questions={loadGuesses()} />
          </LiveRegionProvider>
          <section aria-labelledby="stories-h2" data-first-stories="">
            <h2 id="stories-h2" className={s.storiesHead}>
              {t("storiesHeading")}
            </h2>
            <StoryCards headingLevel={3} />
          </section>
          <FirstScreen summary={summary} />
          <MapApp data={data} />
        </MapTextProvider>
      </IntlClient>
    </div>
  );
}
