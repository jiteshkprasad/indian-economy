import { StatusBadge } from "@/components/ui/StatusBadge";
import { loadStory } from "@/data/server";
import type { StoryFigure } from "@/data/types";
import { format } from "@/lib/format";
import s from "./story.module.css";

/** A story figure from <v>/stories/<slug>.json; an unknown id fails the build (never a made-up number). */
export function storyFigure(slug: string, id: string): StoryFigure {
  const fig = loadStory(slug).figures[id];
  if (!fig) throw new Error(`StoryFig: figure "${id}" is not in stories/${slug}.json`);
  return fig;
}

/**
 * `<StoryFig id="gst_total"/>` in story MDX (PLAN §3.9, §4.9). Server component, bound to
 * its story by the page (`slug`). Renders the formatted number, carrying data-fig-id,
 * data-num-value and data-num-fmt for the fidelity tests, followed by its badge
 * (total label and split label). The badge is the compact one because a figure sits
 * inside a paragraph; each step's "How these figures were made" shows the composition.
 */
export function StoryFig({ slug, id }: { slug: string; id: string }) {
  const fig = storyFigure(slug, id);
  return (
    <span className={s.fig}>
      <span className="num" data-fig-id={id} data-num-value={String(fig.value)} data-num-fmt={fig.unit}>
        {format(fig.value, fig.unit)}
      </span>{" "}
      <StatusBadge total={fig.total} split={fig.split} composition={fig.composition} compact />
    </span>
  );
}
