"use client";
import { createContext, useContext, type ReactNode } from "react";
import { ErrorState } from "@/components/ui";
import s from "./map.module.css";

/**
 * Heading level of the detail panel's sections. In the Map the panel's title is an h2, so its
 * sections are h3; on the flow and series permalink pages the title is the page's h1, so the
 * sections are h2 (no skipped level, V4-08).
 */
const SubLevel = createContext<2 | 3>(3);

export function SubLevelProvider({ level, children }: { level: 2 | 3; children: ReactNode }) {
  return <SubLevel.Provider value={level}>{children}</SubLevel.Provider>;
}

export function useSubLevel(): 2 | 3 {
  return useContext(SubLevel);
}

/** A section heading inside the panel, one level below the panel's title. */
export function Sub({ children, id }: { children: ReactNode; id?: string }) {
  const H = useSubLevel() === 2 ? "h2" : "h3";
  return (
    <H id={id} className={s.subHead}>
      {children}
    </H>
  );
}

/** ErrorState at the panel's section level. */
export function SubError({ file, error }: { file: string; error?: Error | null }) {
  return <ErrorState file={file} error={error} headingLevel={useSubLevel()} />;
}
