/**
 * PLAN §6.2: the StoryFig stub now re-exports U5's real component
 * (components/story/StoryFig.tsx, a server component taking {slug, id}).
 * It is server-only, so it is not exported from components/ui/index.ts;
 * story pages pass it per page through the MDX `components` prop (PLAN §3.9).
 */
export { StoryFig } from "@/components/story/StoryFig";
