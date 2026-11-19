/** Test data for the Map's unit tests: the generated fixture and (when present) the real export. */
import fs from "node:fs";
import path from "node:path";
import type { Cells, Cover, Hierarchy, Pinned, Series, Summary, TsView } from "@/data/types";

const WEB = path.resolve(__dirname, "../../..");

export type MapTestData = {
  label: string;
  summary: Summary;
  hierarchy: Hierarchy;
  cells: Cells;
  pinned: Pinned;
  tsView: TsView;
  series: Series;
  cover: Cover;
};

function load(root: string, label: string): MapTestData {
  const idx = JSON.parse(fs.readFileSync(path.join(root, "index.json"), "utf8")) as { data_version: string };
  const dir = path.join(root, idx.data_version);
  const read = <T,>(f: string) => JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")) as T;
  return {
    label: `${label} ${idx.data_version}`,
    summary: read("summary.json"),
    hierarchy: read("hierarchy.json"),
    cells: read("sam/cells.json"),
    pinned: read("sam/pinned.json"),
    tsView: read("ts/view.json"),
    series: read("ts/series.json"),
    cover: read("ts/cover.json"),
  };
}

export function fixtureData(): MapTestData {
  return load(path.join(WEB, "fixtures/data"), "fixture");
}

/** The real export, or null (with a loud note) when only the fixture exists. */
export function realData(): MapTestData | null {
  const root = path.join(WEB, "public/data");
  const p = path.join(root, "index.json");
  if (!fs.existsSync(p) || JSON.parse(fs.readFileSync(p, "utf8")).fixture) {
    console.warn("REAL-DATA INVARIANTS NOT RUN (web/public/data/index.json is missing or is the fixture)");
    return null;
  }
  return load(root, "real export");
}
