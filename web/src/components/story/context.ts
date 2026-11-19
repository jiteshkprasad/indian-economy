"use client";
import { createContext, useContext } from "react";
import type { StorySlug } from "@/lib/story/registry";

export type StoryCtx = {
  slug: StorySlug;
  /** the active step id (step 1 in the server HTML; without JavaScript a <noscript> style shows every step) */
  active: string | null;
  /** 1-based position and count, for headings */
  position: (id: string) => number;
  count: number;
};

export const StoryContext = createContext<StoryCtx | null>(null);

export function useStoryContext(): StoryCtx {
  const v = useContext(StoryContext);
  if (!v) throw new Error("<Step> must be rendered inside <StoryPlayer>");
  return v;
}
