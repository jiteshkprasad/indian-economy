"use client";
import { useTranslations } from "next-intl";
import { CompositionBar } from "@/components/ui/CompositionBar";
import { Disclosure } from "@/components/ui/Disclosure";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Link } from "@/i18n/navigation";
import { FLAG_NAMES, type FlagName } from "@/lib/status";
import type { Story } from "@/data/types";
import { storyKey, type StorySlug } from "@/lib/story/registry";
import s from "./story.module.css";

const isFlag = (f: string): f is FlagName => (FLAG_NAMES as readonly string[]).includes(f);

/**
 * "How these figures were made": for every figure of the active step, its label, the
 * exporter's method text, its flags in plain words and any note (PLAN §3.8, §4.9).
 */
export function StepNotes({ slug, story, stepId }: { slug: StorySlug; story: Story; stepId: string }) {
  const t = useTranslations("story");
  const tc = useTranslations("common.flags");
  const step = story.steps.find((st) => st.id === stepId);
  if (!step) return null;
  return (
    <div className={s.notes}>
      <Disclosure summary={t("player.methodsToggle")}>
        <dl className={s.notesList}>
          {step.figures.map((id) => {
            const fig = story.figures[id];
            if (!fig) throw new Error(`stories/${slug}.json: step ${stepId} names unknown figure ${id}`);
            return (
              <div key={id} className={s.noteItem}>
                <dt>{t(storyKey.figLabel(slug, id))}</dt>
                <dd>
                  <span>
                    <StatusBadge total={fig.total} split={fig.split} compact />
                  </span>
                  <CompositionBar composition={fig.composition} />
                  <span>{fig.method}</span>
                  {fig.flags.filter(isFlag).map((f) => (
                    <span key={f} className={s.flag}>
                      {tc(f)}
                    </span>
                  ))}
                  {fig.note_key && <span className={s.flag}>{t(fig.note_key)}</span>}
                </dd>
              </div>
            );
          })}
        </dl>
        <p>
          <Link href="/methodology/#status">{t("player.labelsLink")}</Link>
        </p>
      </Disclosure>
    </div>
  );
}
