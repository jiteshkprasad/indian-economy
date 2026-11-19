import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ConsoleMessage, Page, TestInfo } from "@playwright/test";

/** Shared e2e helpers (U2). Everything reads the built site in web/out/. */
export const WEB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
export const OUT = path.join(WEB, "out");
export const SEED = 20261002;

/** Every route of the static export: each out/**\/index.html as "/en/…/", sorted. */
export function allRoutes(): string[] {
  const routes: string[] = [];
  const walk = (dir: string) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) {
        // build artefacts and data; 404/ and _not-found/ are copies of 404.html, not routes
        if (["_next", "data", "data-fixture", "404", "_not-found"].includes(e.name) && dir === OUT) continue;
        walk(p);
      } else if (e.name === "index.html") {
        routes.push(`/${path.relative(OUT, path.dirname(p)).split(path.sep).join("/")}/`.replace(/\/+/g, "/"));
      }
    }
  };
  if (!fs.existsSync(OUT)) throw new Error("web/out/ does not exist: build first");
  walk(OUT);
  return routes.sort();
}

/** Mulberry32, seeded: deterministic samples (PLAN §5.3). */
export function rng(seed = SEED): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function sample<T>(items: readonly T[], n: number, seed = SEED): T[] {
  const r = rng(seed);
  const pool = [...items];
  const out: T[] = [];
  while (out.length < n && pool.length) out.push(pool.splice(Math.floor(r() * pool.length), 1)[0]);
  return out;
}

/** Route types for a11y and mobile checks (PLAN §5.3): home, 5 flow, 5 series, story index, stories, data, methodology, gaps, one shared guess page. */
export function routeTypes(): string[] {
  const all = allRoutes();
  const flows = all.filter((r) => /^\/en\/flow\/[^/]+\/$/.test(r));
  const series = all.filter((r) => /^\/en\/series\/[^/]+\/$/.test(r));
  const stories = all.filter((r) => /^\/en\/story\/[^/]+\/$/.test(r));
  const fixed = ["/en/", "/en/story/", "/en/data/", "/en/methodology/", "/en/gaps/", "/en/guess/gst-states/"].filter((r) => all.includes(r));
  return [...fixed, ...sample(flows, 5), ...sample(series, 5, SEED + 1), ...stories];
}

/** The data folder that the build shipped (real export or fixture copy). */
export function builtData(): { dir: string; base: string; index: { data_version: string; fixture: boolean; files: Record<string, { sha256: string; bytes: number }> } } {
  for (const base of ["data", "data-fixture"]) {
    const p = path.join(OUT, base, "index.json");
    if (fs.existsSync(p)) {
      const index = JSON.parse(fs.readFileSync(p, "utf8"));
      return { dir: path.join(OUT, base, index.data_version), base: `/${base}`, index };
    }
  }
  throw new Error("out/ contains neither data/index.json nor data-fixture/index.json");
}

export function readData<T>(file: string): T {
  return JSON.parse(fs.readFileSync(path.join(builtData().dir, file), "utf8")) as T;
}

/** Marks a run on fixture data loudly in the report (Checkpoint C may not cite it). */
export function noteFixture(info: TestInfo): boolean {
  const fx = builtData().index.fixture;
  if (fx) info.annotations.push({ type: "warning", description: "E2E ON FIXTURE DATA" });
  return fx;
}

const HYDRATION = /hydrat|did not match|server rendered HTML|Text content does not match/i;

/** Collects console errors, page errors and hydration warnings; call assertClean() at the end. */
export function watchConsole(page: Page) {
  const problems: string[] = [];
  const onConsole = (m: ConsoleMessage) => {
    const t = m.text();
    if (m.type() === "error") problems.push(`console.error: ${t}`);
    else if (m.type() === "warning" && HYDRATION.test(t)) problems.push(`hydration: ${t}`);
  };
  page.on("console", onConsole);
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("response", (r) => {
    if (r.status() >= 400) problems.push(`HTTP ${r.status()}: ${r.url()}`);
  });
  return {
    problems,
    assertClean(expectFn: (v: string[]) => void) {
      expectFn(problems);
    },
  };
}
