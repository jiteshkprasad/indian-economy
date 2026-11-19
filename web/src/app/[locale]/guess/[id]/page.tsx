import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { GuessGame } from "@/components/home/GuessGame";
import { loadGuesses } from "@/components/home/server";
import { IntlClient } from "@/components/ui/IntlClient";
import { LiveRegionProvider } from "@/components/ui/LiveRegion";
import { Link } from "@/i18n/navigation";
import { GUESSES } from "@/data/play";
import { routing } from "@/i18n/routing";

type Props = { params: Promise<{ locale: string; id: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return routing.locales.flatMap((locale) => GUESSES.map((q) => ({ locale, id: q.id })));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, id } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "map.guess" });
  const q = t(`q.${id}`);
  // a page's openGraph replaces the layout's, so carry the site image here too (SITE_URL is set for real deployments)
  const site = process.env.SITE_URL;
  return {
    title: q,
    description: t("intro"),
    openGraph: { title: q, description: t("intro"), type: "website", ...(site ? { images: ["/og.png"] } : {}) },
  };
}

/**
 * A shared question (round 3): /<locale>/guess/<id>/?g=<a friend's guess>. The same game as on
 * the home page, opened at this question, with the friend's guess shown until the reader checks
 * their own. The answer is never in the page's metadata.
 */
export default async function GuessPage({ params }: Props) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "map.guess" });
  return (
    <div className="container">
      <IntlClient namespaces={["map", "story"]}>
        <LiveRegionProvider>
          <GuessGame questions={loadGuesses()} startId={id} onHome={false} />
        </LiveRegionProvider>
      </IntlClient>
      <p>
        <Link href="/">{t("home")}</Link>
      </p>
    </div>
  );
}
