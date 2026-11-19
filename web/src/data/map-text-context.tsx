"use client";
import { createContext, useContext, type ReactNode } from "react";
import type { MapText } from "./types";

const Ctx = createContext<MapText | null>(null);

/** Server pages pass loadMapText(locale) here; client components read it with useMapText(). */
export function MapTextProvider({ value, children }: { value: MapText; children: ReactNode }) {
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useMapTextContext(): MapText {
  const v = useContext(Ctx);
  if (!v) throw new Error("useMapText: no <MapTextProvider> above this component; pass loadMapText(locale) from the page");
  return v;
}

/** The labels when a page provides them, else null (for shared components used on every page). */
export function useOptionalMapText(): MapText | null {
  return useContext(Ctx);
}
