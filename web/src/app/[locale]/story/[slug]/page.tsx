import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { FigList } from "@/components/story/FigList";
import { Step } from "@/components/story/Step";
import { StoryFig } from "@/components/story/StoryFig";
import { StoryPlayer } from "@/components/story/StoryPlayer";
import s from "@/components/story/story.module.css";
import { IntlClient } from "@/components/ui/IntlClient";
import { LiveRegionProvider } from "@/components/ui/LiveRegion";
import { MapTextProvider } from "@/data/map-text-context";
import {
  loadCells,
  loadHierarchy,
  loadMapText,
  loadPinned,
  loadStory,
  loadSummary,
  loadTsView,
} from "@/data/server";
import { Link } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { isStorySlug, STORY_SLUGS, storyKey } from "@/lib/story/registry";

type Props = { params: Promise<{ locale: string; slug: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return routing.locales.flatMap((locale) => STORY_SLUGS.map((slug) => ({ locale, slug })));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, slug } = await params;
  setRequestLocale(locale);
  if (!isStorySlug(slug)) return {};
  const t = await getTranslations({ locale, namespace: "story" });
  return { title: t(storyKey.title(slug)), description: t(storyKey.blurb(slug)) };
}

/** /en/story/<slug>/: one story (PLAN §4.9). Every number comes from <v>/stories/<slug>.json. */
export default async function StoryPage({ params }: Props) {
  const { locale, slug } = await params;
  setRequestLocale(locale);
  if (!isStorySlug(slug)) notFound();
  const t = await getTranslations({ locale, namespace: "story" });
  const story = loadStory(slug); // throws (fails the build) if the export lacks this story
  const mdx = await import(`@content/${locale}/stories/${slug}.mdx`);
  const Content = mdx.default as (props: { components: Record<string, unknown> }) => React.ReactNode;
  const mapData = {
    summary: loadSummary(),
    hierarchy: loadHierarchy(),
    cells: loadCells(),
    pinned: loadPinned(),
    tsView: loadTsView(),
  };
  // Bound per page (PLAN §3.9): never registered globally.
  const components = {
    Step,
    StoryFig: ({ id }: { id: string }) => <StoryFig slug={slug} id={id} />,
    FigList: ({ ids, caption }: { ids: string; caption?: string }) => <FigList slug={slug} ids={ids} caption={caption} />,
  };
  return (
    <div className={`container ${s.page}`}>
      <p>
        <Link href="/story/" className={s.back}>
          {t("player.allStories")}
        </Link>
      </p>
      <h1>{t(storyKey.title(slug))}</h1>
      <p className={s.lede}>{t(storyKey.blurb(slug))}</p>
      <IntlClient namespaces={["story", "map"]}>
        <MapTextProvider value={loadMapText(locale)}>
          <LiveRegionProvider>
            <StoryPlayer slug={slug} story={story} mapData={mapData}>
              <Content components={components} />
            </StoryPlayer>
          </LiveRegionProvider>
        </MapTextProvider>
      </IntlClient>
    </div>
  );
}
