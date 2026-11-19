"use client";
import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { storyKey } from "@/lib/story/registry";
import { useStoryContext } from "./context";
import s from "./story.module.css";

/**
 * One step of a story: `<Step id="total">…prose…</Step>` in the MDX. The heading comes
 * from messages/<locale>/story.json. Only the active step is shown (step 1 in the server HTML);
 * without JavaScript, StoryPlayer's <noscript> style shows every step, so the story reads top to bottom.
 */
export function Step({ id, children }: { id: string; children: ReactNode }) {
  const ctx = useStoryContext();
  const t = useTranslations("story");
  const pos = ctx.position(id);
  if (pos < 1) throw new Error(`<Step id="${id}"> is not a step of stories/${ctx.slug}.json`);
  const hidden = ctx.active !== null && ctx.active !== id;
  return (
    <section
      id={`step-${id}`}
      className={s.step}
      data-step={id}
      data-active={ctx.active === id ? "" : undefined}
      hidden={hidden}
      aria-labelledby={`step-${id}-h`}
    >
      <h2 id={`step-${id}-h`} className={s.stepHeading} tabIndex={-1}>
        <span className={s.stepNo}>{t("player.stepOf", { n: pos, total: ctx.count })}</span>
        {t(storyKey.stepTitle(ctx.slug, id))}
      </h2>
      {children}
    </section>
  );
}
