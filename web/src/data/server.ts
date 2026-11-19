/**
 * Build-time data loader (server components, permalink pages, first screen).
 * PLAN §4.4. Reads index.json and <data_version>/*.json with fs from the data
 * root and validates top-level keys; any problem throws, which fails the build.
 */
import "server-only";
import fs from "node:fs";
import path from "node:path";
import { resolveDataRoot } from "./root.mjs";
import type { DataFile, DataFiles, DataIndex, Entries, MapDesc, MapText, Story } from "./types";
import { DATA_VERSION_RE } from "./types";
import { checkTopLevel, DataContractError } from "./validate";

const WEB_DIR = process.cwd();

export type ClientDataIndex = { dataVersion: string; base: string; fixture: boolean };

const cache = new Map<string, unknown>();

function root() {
  return resolveDataRoot(WEB_DIR);
}

function readJson(abs: string, label: string): unknown {
  let text: string;
  try {
    text = fs.readFileSync(abs, "utf8");
  } catch (e) {
    throw new DataContractError(label, `cannot read ${abs}: ${(e as Error).message}`);
  }
  try {
    return JSON.parse(text);
  } catch (e) {
    throw new DataContractError(label, `invalid JSON: ${(e as Error).message}`);
  }
}

export function loadIndex(): DataIndex {
  const r = root();
  const key = `index:${r.dir}`;
  if (cache.has(key)) return cache.get(key) as DataIndex;
  const idx = readJson(path.join(r.dir, "index.json"), "index.json");
  checkTopLevel("index.json", idx);
  const di = idx as DataIndex;
  if (di.schema_version !== 2) throw new DataContractError("index.json", `schema_version ${di.schema_version} != 2`);
  if (!DATA_VERSION_RE.test(di.data_version)) {
    throw new DataContractError("index.json", `data_version "${di.data_version}" does not match ${DATA_VERSION_RE}`);
  }
  cache.set(key, di);
  return di;
}

/** What the client needs to fetch lazily: version folder and URL base. */
export function clientDataIndex(): ClientDataIndex {
  const idx = loadIndex();
  return { dataVersion: idx.data_version, base: root().base, fixture: idx.fixture };
}

/** Reads <data_version>/<file>; the file must be listed in index.json. */
export function loadFile<T = unknown>(file: string): T {
  const r = root();
  const idx = loadIndex();
  const key = `${r.dir}/${idx.data_version}/${file}`;
  if (cache.has(key)) return cache.get(key) as T;
  if (!idx.files[file]) {
    throw new DataContractError(file, `not listed in index.json (data_version ${idx.data_version})`);
  }
  const data = readJson(path.join(r.dir, idx.data_version, file), file);
  checkTopLevel(file, data);
  cache.set(key, data);
  return data as T;
}

export function loadData<K extends DataFile>(file: K): DataFiles[K] {
  return loadFile<DataFiles[K]>(file);
}

export const loadSummary = () => loadData("summary.json");
export const loadHierarchy = () => loadData("hierarchy.json");
export const loadCells = () => loadData("sam/cells.json");
export const loadPinned = () => loadData("sam/pinned.json");
export const loadConstraints = () => loadData("sam/constraints.json");
export const loadRefs = () => loadData("sam/refs.json");
export const loadProvenance = () => loadData("provenance.json");
export const loadSeries = () => loadData("ts/series.json");
export const loadTsView = () => loadData("ts/view.json");
export const loadCover = () => loadData("ts/cover.json");
export const loadEntries = (l0: string) => loadFile<Entries>(`sam/entries/${l0}.json`);
export const loadStory = (slug: string) => loadFile<Story>(`stories/${slug}.json`);

/** Story slugs present in this data version. */
export function storySlugs(): string[] {
  return Object.keys(loadIndex().files)
    .map((f) => /^stories\/([a-z0-9-]+)\.json$/.exec(f)?.[1])
    .filter((s): s is string => !!s)
    .sort();
}

function loadContent<T>(locale: string, name: string): T {
  const key = `content:${locale}/${name}`;
  if (cache.has(key)) return cache.get(key) as T;
  const data = readJson(path.join(WEB_DIR, "content", locale, name), `content/${locale}/${name}`) as T;
  cache.set(key, data);
  return data;
}

/** Node, link, ref and series labels (first view; pass to the client as props). */
export const loadMapText = (locale: string) => loadContent<MapText>(locale, "map-text.json");
/** Long descriptions (normally lazy on the client; permalink pages read them at build time). */
export const loadMapDesc = (locale: string) => loadContent<MapDesc>(locale, "map-desc.json");

/** Resolves a dotted path ("sam.labels.estimated.abs") in summary.json; throws if absent. */
export function summaryPath(p: string): unknown {
  let cur: unknown = loadSummary();
  for (const part of p.split(".")) {
    if (cur === null || typeof cur !== "object" || !(part in (cur as Record<string, unknown>))) {
      throw new DataContractError("summary.json", `path "${p}" does not exist (stopped at "${part}")`);
    }
    cur = (cur as Record<string, unknown>)[part];
  }
  return cur;
}
