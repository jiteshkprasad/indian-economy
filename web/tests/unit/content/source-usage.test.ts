/**
 * The sources table's counts and link rules (src/components/methodology/source-usage.ts)
 * on small in-test data, plus one run on the current data root.
 */
import { describe, expect, it } from "vitest";
import { sourceRows, sourceUsage } from "../../../src/components/methodology/source-usage";
import type { Constraints, Entries, Provenance, Series, Story } from "../../../src/data/types";
import { dataRoot } from "./helpers";

const cite = (source: string, url: string | null = null, withheld = false) => ({
  source,
  tables: ["T1"],
  urls: [url],
  withheld,
  retrieved: ["2026-09-29", "2026-09-29"] as [string, string],
});
const rec = (cites: ReturnType<typeof cite>[]) => ({
  source: cites[0]?.source ?? "",
  status: "official" as const,
  table: "T",
  locator: null,
  method: "m",
  vintage: null,
  base_year: null,
  price_basis: "current",
  unit: "INR_crore",
  conversion: null,
  assumption: false,
  depends_on_assumption: false,
  cites,
});
const src = (name: string, link_mode: "deep" | "landing" | "withheld", landing: string | null) => ({
  name,
  publisher: `${name} publisher`,
  landing,
  link_mode,
  licence: "lic",
  attribution: "attr",
  registry_status: "verified",
});

const provenance: Provenance = {
  records: {
    p1: rec([cite("nas", "https://mospi.gov.in/a")]),
    p2: rec([cite("nas"), cite("rbi_bop", "https://rbi.org.in/x", true)]),
    p3: rec([cite("budget", "https://indiabudget.gov.in/b")]),
  },
  sources: {
    nas: src("NAS", "deep", "https://mospi.gov.in/"),
    rbi_bop: src("BoP", "withheld", "https://www.rbi.org.in/"),
    budget: src("Budget", "landing", "https://indiabudget.gov.in/"),
    unused: src("Unused", "deep", null),
  },
};

const entry = (prov: string) =>
  ({ row: "A", col: "B", ref: "R", component: "c", v: 1, prior: 1, change: 0, pct_change: 0, status: "official",
    prior_status: "official", role: "fixed", label: "official", confidence: null, bop_function: null, prov, flags: [],
    verdict: null, why: null, binding: [] }) as Entries["entries"][number];

const arrays = (prov: (string | null)[]) => ({
  v: prov.map(() => 1), share: prov.map(() => 0.1), base: prov.map(() => null), status: prov.map(() => "official" as const),
  stage: prov.map(() => null), flags: prov.map(() => null), segment: prov.map(() => null), prov,
});

describe("sourceUsage", () => {
  const usage = sourceUsage({
    provenance,
    entries: [{ node: "HH", entries: [entry("p1"), entry("p2"), entry("p2")] }],
    series: {
      periods: ["2022-23", "2023-24"],
      gdp: { main: [1, 1], main_base: [null, null], linked: [null, null], prov: [null, null] },
      flows: [
        { id: "F01", tier: "core", group: "g", display_sign: 1, name_tech: "x",
          check: { class: "A", verdict: "pass", ts_value: null, sam_value: null, rel_diff: null, explanation: null },
          link_policy: "refused", link_reason: null, markers: [], main: arrays(["p1", "p2"]), linked: null, alts: [] },
      ],
    } as Series,
    constraints: { c1: { kind: "equal", ref: "R", description: "d", target: 1, lo: null, hi: null, balanced_sum: 1,
      binding: true, judgement: false, prov: "p3" } } as Constraints,
    stories: [{ slug: "s", figures: { f: { value: 1, unit: "inr", total: null, split: "official",
      composition: { o: 1, d: 0, e: 0, b: 0 }, flags: [], prov: ["p1", "p3"], method: "m", note_key: null } }, steps: [] } as Story],
  });

  it("counts each thing once per source", () => {
    expect(usage.get("nas")).toEqual({ entries: 3, series: 1, constraints: 0, storyFigures: 1 });
    expect(usage.get("rbi_bop")).toEqual({ entries: 2, series: 1, constraints: 0, storyFigures: 0 });
    expect(usage.get("budget")).toEqual({ entries: 0, series: 0, constraints: 1, storyFigures: 1 });
    expect(usage.get("unused")).toEqual({ entries: 0, series: 0, constraints: 0, storyFigures: 0 });
  });

  it("fails loudly on a prov id missing from provenance.json", () => {
    expect(() =>
      sourceUsage({ provenance, entries: [{ node: "HH", entries: [entry("nope")] }], series: null, constraints: null, stories: [] }),
    ).toThrow(/nope/);
  });

  it("orders rows by use and never links a withheld or RBI source", () => {
    const rows = sourceRows(provenance, usage);
    expect(rows.map((r) => r.id)).toEqual(["nas", "rbi_bop", "budget", "unused"]);
    const byId = Object.fromEntries(rows.map((r) => [r.id, r]));
    expect(byId.rbi_bop.href).toBeNull();
    expect(byId.nas.href).toBe("https://mospi.gov.in/");
    expect(byId.budget.href).toBe("https://indiabudget.gov.in/");
    expect(byId.unused.href).toBeNull();
    // even if the data wrongly mark an RBI landing page as "deep", no link is produced
    const bad: Provenance = { records: {}, sources: { x: src("X", "deep", "https://dbie.rbi.org.in/") } };
    expect(sourceRows(bad, new Map())[0].href).toBeNull();
  });
});

describe("sourceUsage on the current data root", () => {
  it("resolves every prov id the page will count", () => {
    const data = dataRoot();
    const prov = data.read<Provenance>("provenance.json");
    const entryFiles = Object.keys(data.index.files).filter((f) => /^sam\/entries\/.+\.json$/.test(f));
    expect(entryFiles.length).toBeGreaterThan(0);
    const storyFiles = Object.keys(data.index.files).filter((f) => /^stories\/.+\.json$/.test(f));
    const usage = sourceUsage({
      provenance: prov,
      entries: entryFiles.map((f) => data.read<Entries>(f)),
      series: data.read<Series>("ts/series.json"),
      constraints: data.read<Constraints>("sam/constraints.json"),
      stories: storyFiles.map((f) => data.read<Story>(f)),
    });
    expect(usage.size).toBe(Object.keys(prov.sources).length);
    const rows = sourceRows(prov, usage);
    for (const r of rows) {
      if (r.linkMode === "withheld") expect(r.href, r.id).toBeNull();
      if (r.href) expect(new URL(r.href).hostname, r.id).not.toMatch(/(^|\.)rbi\.org\.in$/i);
    }
  });
});
