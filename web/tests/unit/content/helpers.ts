/**
 * Shared helpers for U6's content tests (tests/unit/content/**). They read the
 * same data root as the build (src/data/root.mjs: public once the real export
 * exists, else the generated fixture), and the content files from disk.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { resolveDataRoot } from "../../../src/data/root.mjs";
import type { DataIndex, Hierarchy, MapDesc, MapText } from "../../../src/data/types";

export const WEB_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
export const CONTENT_DIR = path.join(WEB_DIR, "content");

export function readJson<T>(abs: string): T {
  return JSON.parse(fs.readFileSync(abs, "utf8")) as T;
}

export type DataRoot = {
  kind: string;
  dir: string;
  index: DataIndex;
  /** true when this is the real export (not the generated fixture) */
  real: boolean;
  read<T>(file: string): T;
};

/**
 * The data root the build would use. Throws (fails the test) when no data exist at
 * all: by the time tests run, U1's fixture or real export must be there.
 */
export function dataRoot(): DataRoot {
  const r = resolveDataRoot(WEB_DIR) as { kind: string; dir: string };
  const idxPath = path.join(r.dir, "index.json");
  if (!fs.existsSync(idxPath)) {
    throw new Error(
      `No data at ${idxPath}. Run \`uv run python -m pipeline export --fixture\` (fixture) or \`uv run python -m pipeline export\` (real data).`,
    );
  }
  const index = readJson<DataIndex>(idxPath);
  return {
    kind: r.kind,
    dir: r.dir,
    index,
    real: index.fixture === false,
    read<T>(file: string): T {
      if (!index.files[file]) throw new Error(`${file} is not listed in ${idxPath}`);
      return readJson<T>(path.join(r.dir, index.data_version, file));
    },
  };
}

export function loadMapText(locale = "en"): MapText {
  return readJson<MapText>(path.join(CONTENT_DIR, locale, "map-text.json"));
}

export function loadMapDesc(locale = "en"): MapDesc {
  return readJson<MapDesc>(path.join(CONTENT_DIR, locale, "map-desc.json"));
}

/** Every file under `dir` (recursive) with one of the extensions, sorted. */
export function listFiles(dir: string, exts: readonly string[]): string[] {
  if (!fs.existsSync(dir)) return [];
  const out: string[] = [];
  const walk = (d: string) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) walk(p);
      else if (exts.some((x) => e.name.endsWith(x))) out.push(p);
    }
  };
  walk(dir);
  return out.sort();
}

/**
 * Level-0 link ids for a preset (PLAN §3.6 ids, §4.4 aggregation): each non-zero
 * account cell maps to (payer, receiver) visible nodes; the positive cells of a
 * pair make `<payer>--<receiver>`, the negative cells `<payer>--<receiver>~neg`;
 * cells whose ends map to the same node are internal and are not links. Written
 * here independently of src/data/aggregate.ts.
 */
export function levelZeroLinkIds(
  h: Hierarchy,
  cells: { n: number; row: number[]; col: number[]; v: number[] },
  preset: "simple" | "full",
): Set<string> {
  const merges = h.presets[preset].merges;
  const mergedInto = new Map<string, string>();
  for (const [into, members] of Object.entries(merges)) for (const m of members) mergedInto.set(m, into);
  const nodeOf = (idx: number) => {
    const l0 = h.accounts[idx].l0;
    return mergedInto.get(l0) ?? l0;
  };
  const ids = new Set<string>();
  for (let i = 0; i < cells.n; i++) {
    const v = cells.v[i];
    if (v === 0) continue;
    const payer = nodeOf(cells.col[i]);
    const receiver = nodeOf(cells.row[i]);
    if (payer === receiver) continue;
    ids.add(`${payer}--${receiver}${v < 0 ? "~neg" : ""}`);
  }
  return ids;
}
