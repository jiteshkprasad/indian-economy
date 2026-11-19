import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { STORY_SLUGS, storyKey } from "@/lib/story/registry";
import s from "./story.module.css";

/**
 * The three story cards (PLAN §4.0 item 3, §4.9): each a link at least 44 px tall.
 * Works in server and client trees; a client tree needs the "story" message namespace.
 * `headingLevel` sets the card title element (h2 on the story index, h3 under the first screen).
 */
export function StoryCards({ headingLevel = 3 }: { headingLevel?: 2 | 3 }) {
  const t = useTranslations("story");
  const H = headingLevel === 2 ? "h2" : "h3";
  return (
    <ul className={s.cards} aria-label={t("cards.label")}>
      {STORY_SLUGS.map((slug) => (
        <li key={slug} className={s.card}>
          <Link href={`/story/${slug}/`} className={s.cardLink} data-story-card={slug}>
            <H className={s.cardTitle}>{t(storyKey.title(slug))}</H>
            <span className={s.cardBlurb}>{t(storyKey.blurb(slug))}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
