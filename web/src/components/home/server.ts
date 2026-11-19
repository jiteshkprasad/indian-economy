import "server-only";
import { GUESSES, TOURS } from "@/data/play";
import { loadFile, loadStory } from "@/data/server";
import type { Provenance } from "@/data/types";
import type { GuessData } from "./GuessGame";
import type { TourData, TourFig } from "./HeroTour";

function pickFig(slug: string, figs: Record<string, TourFig>, id: string): TourFig {
  const f = figs[id];
  if (!f) throw new Error(`home: figure ${slug}.${id} is not in the story export`);
  return { value: f.value, unit: f.unit, total: f.total, split: f.split };
}

/** The rupee tours, with each stop's map view and figures, read at build time. */
export function loadTours(): TourData[] {
  return TOURS.map((tour) => {
    const story = loadStory(tour.slug);
    return {
      slug: tour.slug,
      stops: tour.stops.map((st) => {
        const step = story.steps.find((x) => x.id === st.step);
        if (!step) throw new Error(`home: step ${tour.slug}.${st.step} is not in the story export`);
        return {
          step: st.step,
          view: step.view,
          a: pickFig(tour.slug, story.figures, st.fig),
          b: st.fig2 ? pickFig(tour.slug, story.figures, st.fig2) : null,
        };
      }),
    };
  });
}

/** The guessing game's questions with their answers, read at build time. */
export function loadGuesses(): GuessData[] {
  return GUESSES.map((q) => {
    const story = loadStory(q.slug);
    if (!story.steps.some((x) => x.id === q.step)) throw new Error(`home: step ${q.slug}.${q.step} is not in the story export`);
    return { id: q.id, slug: q.slug, step: q.step, min: q.min, max: q.max, step_: q.step_, fig: pickFig(q.slug, story.figures, q.fig) };
  });
}

/** How many official sources the site cites. */
export function sourceCount(): number {
  return Object.keys(loadFile<Provenance>("provenance.json").sources).length;
}
