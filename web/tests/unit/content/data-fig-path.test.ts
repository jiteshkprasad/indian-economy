/**
 * Every binding in the methodology MDX resolves in summary.json (PLAN §3.9, §5.2 U6):
 * <DataFig path> to a number or a {value, unit, prov} item with a unit the formatter
 * knows; <DataText path> to a string; <SummaryBadge path> to an object with a status
 * label. A DataFig whose path is not a methodology item must say its unit with
 * `fmt`, so nothing depends on guessing. Also checks that every methodology MDX
 * file is a section of the page, and every section has its MDX file.
 */
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { SECTIONS } from "../../../src/components/methodology/sections";
import { CONTENT_DIR, dataRoot, listFiles } from "./helpers";
import type { Summary } from "../../../src/data/types";

const FMT = new Set(["inr", "pct_gdp", "per100", "pct", "count"]);
const LABELS = new Set(["official", "derived", "estimated", "balancing_set"]);

type Binding = { tag: string; path: string; fmt: string | null; file: string; line: number };

function attr(tag: string, name: string): string | null {
  const m = new RegExp(`\\b${name}\\s*=\\s*"([^"]*)"`).exec(tag);
  return m ? m[1] : null;
}

export function bindingsIn(file: string, src: string): Binding[] {
  const out: Binding[] = [];
  const re = /<(DataFig|DataText|SummaryBadge)\b[^>]*\/?>/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(src))) {
    const line = src.slice(0, m.index).split("\n").length;
    const p = attr(m[0], "path");
    if (p === null) throw new Error(`${file}:${line}: <${m[1]}> has no path="..."`);
    out.push({ tag: m[1], path: p, fmt: attr(m[0], "fmt"), file, line });
  }
  return out;
}

function resolve(obj: unknown, p: string): { ok: true; value: unknown } | { ok: false; at: string } {
  let cur: unknown = obj;
  for (const part of p.split(".")) {
    if (cur === null || typeof cur !== "object" || !(part in (cur as Record<string, unknown>))) {
      return { ok: false, at: part };
    }
    cur = (cur as Record<string, unknown>)[part];
  }
  return { ok: true, value: cur };
}

/**
 * The status a summary.json figure carries, in either exported shape: `{label}`
 * (e.g. gdp) or `{split_label, total_label}` (headline parts and the methodology
 * items that are economic values). null when it carries none.
 */
function statusOf(v: unknown): { split: string; total: string | null } | null {
  if (!v || typeof v !== "object") return null;
  const o = v as { label?: unknown; split_label?: unknown; total_label?: unknown };
  if ("label" in o) return typeof o.label === "string" && LABELS.has(o.label) ? { split: o.label, total: null } : null;
  if (typeof o.split_label !== "string" || !LABELS.has(o.split_label)) return null;
  const t = o.total_label ?? null;
  if (t !== null && t !== "official" && t !== "derived") return null;
  return { split: o.split_label, total: t as string | null };
}

const methDir = path.join(CONTENT_DIR, "en", "methodology");
const files = listFiles(methDir, [".mdx"]);
const data = dataRoot();
const summary = data.read<Summary>("summary.json");

describe("methodology MDX bindings", () => {
  it("has methodology MDX files with bindings", () => {
    const all = files.flatMap((f) => bindingsIn(f, fs.readFileSync(f, "utf8")));
    expect(all.length).toBeGreaterThan(20);
  });

  for (const f of files) {
    const rel = path.relative(CONTENT_DIR, f);
    it(`${rel}: every binding resolves in summary.json (${data.real ? "real export" : "FIXTURE"})`, () => {
      const problems: string[] = [];
      for (const b of bindingsIn(f, fs.readFileSync(f, "utf8"))) {
        const where = `${rel}:${b.line} <${b.tag} path="${b.path}">`;
        if (b.tag === "SummaryBadge") {
          const r = resolve(summary, b.path);
          const st = r.ok ? statusOf(r.value) : null;
          if (!st) problems.push(`${where}: no status label (label, or split_label with total_label)`);
          continue;
        }
        const r = resolve(summary, b.path);
        if (!r.ok) {
          problems.push(`${where}: missing (stopped at "${r.at}")`);
          continue;
        }
        const v = r.value;
        if (b.tag === "DataText") {
          if (typeof v !== "string") problems.push(`${where}: not a string`);
          continue;
        }
        if (b.fmt !== null && !FMT.has(b.fmt)) problems.push(`${where}: unknown fmt "${b.fmt}"`);
        if (typeof v === "number") {
          if (!Number.isFinite(v)) problems.push(`${where}: not finite`);
          if (b.fmt === null) problems.push(`${where}: a plain number needs fmt="..."`);
        } else if (v && typeof v === "object" && typeof (v as { value?: unknown }).value === "number") {
          const item = v as { value: number; unit?: unknown; prov?: unknown };
          if (!Number.isFinite(item.value)) problems.push(`${where}: value not finite`);
          if (typeof item.unit !== "string" || !FMT.has(item.unit)) problems.push(`${where}: unit "${String(item.unit)}"`);
          if (!Array.isArray(item.prov)) problems.push(`${where}: prov is not a list`);
        } else {
          problems.push(`${where}: not a number or a {value, unit} item`);
        }
      }
      expect(problems).toEqual([]);
    });
  }
});

describe("methodology figures that carry a status show its badge (V5-03)", () => {
  // A figure U1 exports with a status label is an economic value: the page must show
  // its badge right after it, as every figure on the map and in the stories does.
  // Counts and rule constants carry no label and need none.
  for (const f of files) {
    const rel = path.relative(CONTENT_DIR, f);
    it(`${rel}: a <SummaryBadge> follows every labelled figure`, () => {
      const bs = bindingsIn(f, fs.readFileSync(f, "utf8"));
      const missing: string[] = [];
      bs.forEach((b, i) => {
        if (b.tag !== "DataFig") return;
        const r = resolve(summary, b.path);
        if (!r.ok || !statusOf(r.value)) return;
        const next = bs[i + 1];
        if (!next || next.tag !== "SummaryBadge" || next.path !== b.path) {
          missing.push(`${rel}:${b.line} <DataFig path="${b.path}"> has a status label but no <SummaryBadge path="${b.path}"/> after it`);
        }
      });
      expect(missing).toEqual([]);
    });
  }
});

describe("methodology sections and MDX files match", () => {
  it("every MDX file is a page section and every section has a file", () => {
    const names = files.map((f) => path.basename(f, ".mdx")).sort();
    expect(names).toEqual(SECTIONS.map((s) => s.mdx as string).sort());
  });
});
