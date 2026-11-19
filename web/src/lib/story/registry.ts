/**
 * The three stories (PLAN §4.9). The slugs are fixed here so that a story missing
 * from the export fails the build (loadStory throws) instead of silently vanishing.
 */
export const STORY_SLUGS = ["gst-rupee", "remittance-dubai", "deficit-funding"] as const;
export type StorySlug = (typeof STORY_SLUGS)[number];

export function isStorySlug(s: string): s is StorySlug {
  return (STORY_SLUGS as readonly string[]).includes(s);
}

/** Message keys (messages/<locale>/story.json) for a story's texts. */
export const storyKey = {
  title: (slug: StorySlug) => `stories.${slug}.title`,
  blurb: (slug: StorySlug) => `stories.${slug}.blurb`,
  stepTitle: (slug: StorySlug, step: string) => `stories.${slug}.steps.${step}`,
  figLabel: (slug: StorySlug, fig: string) => `figs.${slug}.${fig}`,
} as const;
