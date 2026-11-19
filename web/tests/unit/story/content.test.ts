/**
 * Story content against story data (PLAN §5.2, U5): every <StoryFig id> and <FigList ids>
 * in the MDX exists in the exported story JSON; the MDX steps are the JSON steps, in order;
 * each step shows exactly the figures its JSON step lists (so "How these figures were made"
 * is complete); every heading, label, caption and note has its message; no digits in prose.
 * Reads the same data root as the build: the real export when present, else the fixture.
 */
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { resolveDataRoot } from "@/data/root.mjs";
import type { DataIndex, Story } from "@/data/types";
import { STORY_SLUGS, storyKey } from "@/lib/story/registry";
import messages from "@messages/en/story.json";

const WEB = path.resolve(import.meta.dirname, "../../..");

function storyJson(slug: string): Story {
  const r = resolveDataRoot(WEB) as { dir: string };
  const idxPath = path.join(r.dir, "index.json");
  if (!fs.existsSync(idxPath)) {
    throw new Error(`No data at ${idxPath}: run \`uv run python -m pipeline export --fixture\` or \`uv run python -m pipeline export\``);
  }
  const idx = JSON.parse(fs.readFileSync(idxPath, "utf8")) as DataIndex;
  const rel = `stories/${slug}.json`;
  if (!idx.files[rel]) throw new Error(`${rel} is not listed in ${idxPath}`);
  return JSON.parse(fs.readFileSync(path.join(r.dir, idx.data_version, rel), "utf8")) as Story;
}

function mdx(slug: string): string {
  return fs.readFileSync(path.join(WEB, "content", "en", "stories", `${slug}.mdx`), "utf8");
}

type Block = { id: string; figs: string[] };

/** The <Step> blocks of an MDX file and the figure ids each one shows. */
function stepBlocks(src: string): Block[] {
  const out: Block[] = [];
  const re = /<Step id="([^"]+)">([\s\S]*?)<\/Step>/g;
  for (const m of src.matchAll(re)) {
    const body = m[2];
    const figs = [...body.matchAll(/<StoryFig id="([^"]+)"/g)].map((x) => x[1]);
    for (const l of body.matchAll(/<FigList ids="([^"]+)"/g)) figs.push(...l[1].split(/[\s,]+/).filter(Boolean));
    out.push({ id: m[1], figs });
  }
  return out;
}

function get(obj: unknown, dotted: string): unknown {
  return dotted.split(".").reduce<unknown>((o, k) => (o && typeof o === "object" ? (o as Record<string, unknown>)[k] : undefined), obj);
}

describe.each(STORY_SLUGS)("story %s", (slug) => {
  const src = mdx(slug);
  const blocks = stepBlocks(src);

  it("every <StoryFig id> and <FigList ids> exists in the story JSON", () => {
    const story = storyJson(slug);
    const unknown = blocks.flatMap((b) => b.figs).filter((id) => !(id in story.figures));
    expect(unknown).toEqual([]);
    // nothing outside a <Step>: every figure tag sits in a step
    const outside = src.replace(/\{\/\*[\s\S]*?\*\/\}/g, "").replace(/<Step id="[^"]+">[\s\S]*?<\/Step>/g, "");
    expect(outside).not.toMatch(/<StoryFig|<FigList/);
  });

  it("the MDX steps are the JSON steps, in order, and each shows exactly its listed figures", () => {
    const story = storyJson(slug);
    expect(blocks.map((b) => b.id)).toEqual(story.steps.map((s) => s.id));
    for (const b of blocks) {
      const listed = story.steps.find((s) => s.id === b.id)!.figures;
      expect([...new Set(b.figs)].sort(), `step ${b.id}`).toEqual([...listed].sort());
    }
  });

  it("every step title, figure label, caption and note key has a message", () => {
    const story = storyJson(slug);
    const missing: string[] = [];
    const need = (k: string) => typeof get(messages, k) !== "string" && missing.push(k);
    need(storyKey.title(slug));
    need(storyKey.blurb(slug));
    for (const s of story.steps) {
      need(storyKey.stepTitle(slug, s.id));
      for (const f of s.figures) need(storyKey.figLabel(slug, f));
    }
    for (const c of src.matchAll(/caption="([^"]+)"/g)) need(`captions.${slug}.${c[1]}`);
    for (const f of Object.values(story.figures)) if (f.note_key) need(f.note_key);
    expect(missing).toEqual([]);
  });

  it("no figure presented as borrowing is negative (a negative 'net borrowing' would read as net lending)", () => {
    const story = storyJson(slug);
    const value = (id: string) => story.figures[id]?.value ?? 0;
    const says = (text: unknown) => typeof text === "string" && /\bborrowing\b/i.test(text);
    const bad: string[] = [];
    // a figure whose own label says borrowing
    for (const id of Object.keys(story.figures)) {
      if (says(get(messages, storyKey.figLabel(slug, id))) && value(id) < 0) bad.push(`${id} (label)`);
    }
    // every figure in a table whose caption says borrowing
    for (const m of src.matchAll(/<FigList ids="([^"]+)"\s+caption="([^"]+)"/g)) {
      if (!says(get(messages, `captions.${slug}.${m[2]}`))) continue;
      for (const id of m[1].split(/[\s,]+/).filter(Boolean)) if (value(id) < 0) bad.push(`${id} (caption ${m[2]})`);
    }
    // every figure in a sentence of prose that says borrowing
    const prose = src.replace(/\{\/\*[\s\S]*?\*\/\}/g, "");
    for (const sentence of prose.split(/(?<=[.!?])\s+|\n\s*\n/)) {
      if (!says(sentence)) continue;
      for (const m of sentence.matchAll(/<StoryFig id="([^"]+)"/g)) if (value(m[1]) < 0) bad.push(`${m[1]} (prose)`);
    }
    expect(bad).toEqual([]);
  });

  it("states no number in prose: figures come only from bindings", () => {
    const prose = src
      .replace(/\{\/\*[\s\S]*?\*\/\}/g, "") // MDX comments
      .replace(/<[A-Z][A-Za-z]*\b[^>]*\/?>/g, "") // component tags and their attributes
      .replace(/<\/[A-Z][A-Za-z]*>/g, "")
      .replace(/\b\d{4}-\d{2}\b/g, ""); // fiscal-year labels such as 2023-24
    expect(prose.match(/\d+/g) ?? []).toEqual([]);
  });
});

describe("story.json messages", () => {
  it("contain no numbers except fiscal-year labels and ICU placeholders", () => {
    const values: string[] = [];
    const walk = (o: unknown) => {
      if (typeof o === "string") values.push(o);
      else if (o && typeof o === "object") Object.values(o).forEach(walk);
    };
    walk(messages);
    const bad = values.filter((v) => /\d/.test(v.replace(/\b\d{4}-\d{2}\b/g, "")));
    expect(bad).toEqual([]);
  });
});
