"use client";
/**
 * Data hooks (PLAN §4.4). Each returns { data, error, loading }. Pass `initial`
 * when a server component already read the file, so the client does not fetch it
 * again. On error, render <ErrorState file={...} error={...}/>; never partial numbers.
 */
import { useLocale } from "next-intl";
import { useEffect, useState } from "react";
import { useDataIndex } from "./index-data";
import { loadJson, primeJson } from "./load";
import type {
  Cells,
  Constraints,
  Cover,
  Entries,
  Hierarchy,
  MapDesc,
  MapText,
  Pinned,
  Provenance,
  Refs,
  Series,
  Story,
  Summary,
  TsView,
} from "./types";
import { useMapTextContext, useOptionalMapText } from "./map-text-context";

export type Loaded<T> = { data: T | undefined; error: Error | null; loading: boolean };

export function useDataFile<T>(file: string | null, initial?: T): Loaded<T> {
  const idx = useDataIndex();
  const [st, setSt] = useState<{ file: string | null; data: T | undefined; error: Error | null }>({
    file: null,
    data: undefined,
    error: null,
  });
  useEffect(() => {
    if (file === null) return;
    if (initial !== undefined) {
      primeJson(idx, file, initial);
      return;
    }
    let live = true;
    loadJson<T>(idx, file).then(
      (data) => {
        if (live) setSt({ file, data, error: null });
      },
      (error: Error) => {
        console.error(`[data] ${error.message}`);
        if (live) setSt({ file, data: undefined, error });
      },
    );
    return () => {
      live = false;
    };
  }, [idx, file, initial]);
  if (initial !== undefined) return { data: initial, error: null, loading: false };
  if (file === null) return { data: undefined, error: null, loading: false };
  if (st.file !== file) return { data: undefined, error: null, loading: true };
  return { data: st.data, error: st.error, loading: false };
}

export const useSummary = (initial?: Summary) => useDataFile<Summary>("summary.json", initial);
export const useHierarchy = (initial?: Hierarchy) => useDataFile<Hierarchy>("hierarchy.json", initial);
export const useCells = (initial?: Cells) => useDataFile<Cells>("sam/cells.json", initial);
export const usePinned = (initial?: Pinned) => useDataFile<Pinned>("sam/pinned.json", initial);
export const useEntries = (l0: string | null) => useDataFile<Entries>(l0 ? `sam/entries/${l0}.json` : null);
/** `need` = false defers the (large) file until a component actually needs it. */
export const useConstraints = (need = true) => useDataFile<Constraints>(need ? "sam/constraints.json" : null);
export const useRefs = () => useDataFile<Refs>("sam/refs.json");
export const useProvenance = () => useDataFile<Provenance>("provenance.json");
export const useSeries = () => useDataFile<Series>("ts/series.json");
export const useTsView = (initial?: TsView) => useDataFile<TsView>("ts/view.json", initial);
export const useCover = () => useDataFile<Cover>("ts/cover.json");
export const useStory = (slug: string | null) => useDataFile<Story>(slug ? `stories/${slug}.json` : null);

/** Labels (first view): provided by <MapTextProvider> from the server; throws if missing. */
export function useMapText(): MapText {
  return useMapTextContext();
}

const textCache = new Map<string, Promise<MapText>>();

/**
 * Labels for a shared component that may render on a page without <MapTextProvider>
 * (e.g. /data/): the provided labels when present, else content/<locale>/map-text.json
 * loaded lazily, and only once `need` is true.
 */
export function useMapTextLazy(need: boolean): Loaded<MapText> {
  const provided = useOptionalMapText();
  const locale = useLocale();
  const [state, setState] = useState<{ locale: string; data?: MapText; error: Error | null } | null>(null);
  const fetchIt = need && provided === null;
  useEffect(() => {
    if (!fetchIt) return;
    let live = true;
    let p = textCache.get(locale);
    if (!p) {
      p = import(`@content/${locale}/map-text.json`).then((m) => m.default as MapText);
      textCache.set(locale, p);
      p.catch(() => textCache.delete(locale));
    }
    p.then(
      (data) => live && setState({ locale, data, error: null }),
      (error: Error) => {
        console.error(`[data] content/${locale}/map-text.json: ${error.message}`);
        if (live) setState({ locale, error });
      },
    );
    return () => {
      live = false;
    };
  }, [fetchIt, locale]);
  if (provided) return { data: provided, error: null, loading: false };
  if (!need) return { data: undefined, error: null, loading: false };
  if (!state || state.locale !== locale) return { data: undefined, error: null, loading: true };
  return { data: state.data, error: state.error, loading: false };
}

const descCache = new Map<string, Promise<MapDesc>>();

/** Long descriptions, loaded lazily as a separate chunk after first paint. */
export function useMapDesc(): Loaded<MapDesc> {
  const locale = useLocale();
  const [state, setState] = useState<Loaded<MapDesc>>({ data: undefined, error: null, loading: true });
  useEffect(() => {
    let live = true;
    let p = descCache.get(locale);
    if (!p) {
      p = import(`@content/${locale}/map-desc.json`).then((m) => m.default as MapDesc);
      descCache.set(locale, p);
      p.catch(() => descCache.delete(locale));
    }
    p.then(
      (data) => live && setState({ data, error: null, loading: false }),
      (error: Error) => {
        console.error(`[data] content/${locale}/map-desc.json: ${error.message}`);
        if (live) setState({ data: undefined, error, loading: false });
      },
    );
    return () => {
      live = false;
    };
  }, [locale]);
  return state;
}
