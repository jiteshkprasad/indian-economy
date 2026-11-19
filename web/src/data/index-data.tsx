"use client";
/**
 * The data version and URL base, injected at build time by the [locale] layout
 * from src/data/server.ts (PLAN §4.4). There is deliberately no static import of
 * public/data/index.json, which would break before the first export.
 */
import { createContext, useContext, type ReactNode } from "react";

export type ClientDataIndex = { dataVersion: string; base: string; fixture: boolean };

const Ctx = createContext<ClientDataIndex | null>(null);

export function DataIndexProvider({ value, children }: { value: ClientDataIndex; children: ReactNode }) {
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useDataIndex(): ClientDataIndex {
  const v = useContext(Ctx);
  if (!v) throw new Error("useDataIndex: no <DataIndexProvider> above this component (it is set in app/[locale]/layout.tsx)");
  return v;
}

/** URL of a file inside the current data version, e.g. dataUrl(idx, "ts/series.json"). */
export function dataUrl(idx: ClientDataIndex, file: string): string {
  return `${idx.base}/${idx.dataVersion}/${file}`;
}
