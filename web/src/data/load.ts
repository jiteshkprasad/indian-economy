/**
 * Client fetch with an in-memory promise cache (PLAN §4.4). A failed fetch or a
 * top-level shape mismatch rejects with an error naming the file; callers render
 * <ErrorState>. Nothing here substitutes made-up or partial data.
 */
import type { ClientDataIndex } from "./index-data";
import { dataUrl } from "./index-data";
import { checkTopLevel, DataContractError } from "./validate";

const cache = new Map<string, Promise<unknown>>();

export class DataLoadError extends Error {
  constructor(
    public file: string,
    message: string,
  ) {
    super(`${file}: ${message}`);
    this.name = "DataLoadError";
  }
}

export function loadJson<T>(idx: ClientDataIndex, file: string, fetchImpl: typeof fetch = fetch): Promise<T> {
  const url = dataUrl(idx, file);
  let p = cache.get(url) as Promise<T> | undefined;
  if (!p) {
    p = (async () => {
      let res: Response;
      try {
        res = await fetchImpl(url);
      } catch (e) {
        throw new DataLoadError(file, `network error: ${(e as Error).message}`);
      }
      if (!res.ok) throw new DataLoadError(file, `HTTP ${res.status} for ${url}`);
      let data: unknown;
      try {
        data = await res.json();
      } catch (e) {
        throw new DataLoadError(file, `invalid JSON: ${(e as Error).message}`);
      }
      try {
        checkTopLevel(file, data);
      } catch (e) {
        throw new DataLoadError(file, (e as DataContractError).message);
      }
      return data as T;
    })();
    cache.set(url, p);
    // A failed request may be retried later (e.g. after a network blip).
    p.catch(() => cache.delete(url));
  }
  return p;
}

/** Seeds the cache with data the server already passed as props (no second fetch). */
export function primeJson<T>(idx: ClientDataIndex, file: string, data: T): void {
  const url = dataUrl(idx, file);
  if (!cache.has(url)) cache.set(url, Promise.resolve(data));
}

/** For tests. */
export function clearDataCache(): void {
  cache.clear();
}
