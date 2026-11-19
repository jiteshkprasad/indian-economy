import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { StoryCards } from "@/components/story/StoryCards";
import s from "@/components/story/story.module.css";

type Props = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "story.index" });
  return { title: t("title"), description: t("description") };
}

/** /en/story/: the story index (PLAN §4.2). */
export default async function StoryIndexPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "story.index" });
  return (
    <div className={`container ${s.page}`}>
      <h1>{t("title")}</h1>
      <p className={s.lede}>{t("lede")}</p>
      <StoryCards headingLevel={2} />
      <p className={s.lede}>{t("honesty")}</p>
    </div>
  );
}
