/**
 * No number is ever typed into prose (PLAN §3.9, D3-9): figures reach the reader
 * only through data bindings (<DataFig>, <DataText>, <StoryFig>), so content cannot
 * drift from data. This test bans digit runs in every MDX file under content/
 * (methodology and stories) and in every string value of map-text.json and
 * map-desc.json.
 *
 * Allowed, because they are names or references and not data:
 * - financial-year labels such as 2023-24;
 * - SNA codes in parentheses, e.g. (D44), (P51g), (D612);
 * - decision and issue references in parentheses, e.g. (D2-21), (ISSUES P1-9);
 * - ordinal names such as "15th Finance Commission";
 * - the unit phrase "₹100" in "of every ₹100" / "per ₹100".
 * Markup is removed before the check: JSX/HTML tags and their attributes, import and
 * export lines, link targets, code spans and comments.
 */
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { CONTENT_DIR, listFiles, loadMapDesc, loadMapText } from "./helpers";

const ALLOWED: RegExp[] = [
  /\b\d{4}-\d{2}\b/g, // FY label
  /\((?:[A-Z]{1,3}\d{1,4}[a-z]?)(?:\s*(?:,|and|or|\+)\s*[A-Z]{1,3}\d{1,4}[a-z]?)*\)/g, // SNA codes
  /\((?:(?:ISSUES|DECISIONS)\s+)?[DP]\d+-\d+[a-z]?(?:\s*(?:,|and)\s*(?:(?:ISSUES|DECISIONS)\s+)?[DP]\d+-\d+[a-z]?)*\)/g, // refs
  /\b\d+(?:st|nd|rd|th) Finance Commission\b/g, // ordinal names
  /₹100\b/g, // "of every ₹100"
];

/** Removes markup that may legitimately contain digits; keeps line breaks for line numbers. */
export function stripMarkup(src: string): string {
  return (
    src
      // MDX import/export statements
      .replace(/^(?:import|export)\s.*$/gm, "")
      // HTML/MDX comments
      .replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, " "))
      .replace(/\{\/\*[\s\S]*?\*\/\}/g, (m) => m.replace(/[^\n]/g, " "))
      // fenced code blocks and inline code
      .replace(/```[\s\S]*?```/g, (m) => m.replace(/[^\n]/g, " "))
      .replace(/`[^`\n]*`/g, " ")
      // JSX/HTML tags, including their attributes
      .replace(/<\/?[A-Za-z][^<>]*>/g, " ")
      // markdown link targets and heading ids
      .replace(/\]\([^)\s]*\)/g, "] ")
      .replace(/\{#[^}]*\}/g, " ")
  );
}

/** Digit runs left after removing allowed patterns: [line, snippet][]. */
export function findDigits(text: string): Array<[number, string]> {
  const out: Array<[number, string]> = [];
  const lines = text.split("\n");
  lines.forEach((line, i) => {
    let rest = line;
    for (const re of ALLOWED) rest = rest.replace(re, " ");
    const m = rest.match(/\d+/g);
    if (m) out.push([i + 1, line.trim().slice(0, 160)]);
  });
  return out;
}

describe("no-digits: the checker itself", () => {
  it("allows FY labels, SNA codes, references, ordinal names and ₹100", () => {
    expect(findDigits("In 2023-24 the base year is 2022-23.")).toEqual([]);
    expect(findDigits("Investment income (D44) and (D612) and (P51g)")).toEqual([]);
    expect(findDigits("Decisions (D2-21) and (ISSUES P1-9) and (D2-19, D2-24)")).toEqual([]);
    expect(findDigits("devolution by the 15th Finance Commission")).toEqual([]);
    expect(findDigits('Of every ₹100 households pay out')).toEqual([]);
  });
  it("catches typed numbers", () => {
    expect(findDigits("GDP was ₹290 lakh crore")).not.toEqual([]);
    expect(findDigits("about 44.3% of consumption")).not.toEqual([]);
    expect(findDigits("128 accounts")).not.toEqual([]);
    expect(findDigits("D2-21 without parentheses")).not.toEqual([]);
    expect(findDigits("in 2024")).not.toEqual([]);
  });
  it("ignores digits inside tags, attributes, links and code", () => {
    const src = 'Text <DataFig path="methodology.disc_d1"/> and [a link](/en/flow/F01/) and `code 42`.\nimport X from "./x1.mdx"';
    expect(findDigits(stripMarkup(src))).toEqual([]);
  });
});

describe("no-digits: MDX content", () => {
  const files = listFiles(CONTENT_DIR, [".mdx", ".md"]);
  it("finds the methodology MDX files", () => {
    expect(files.some((f) => f.includes(`${path.sep}methodology${path.sep}`))).toBe(true);
  });
  for (const f of files) {
    it(path.relative(CONTENT_DIR, f), () => {
      const hits = findDigits(stripMarkup(fs.readFileSync(f, "utf8")));
      expect(hits.map(([l, s]) => `${path.relative(CONTENT_DIR, f)}:${l}: ${s}`)).toEqual([]);
    });
  }
});

describe("no-digits: map text", () => {
  const sources = { "map-text.json": loadMapText(), "map-desc.json": loadMapDesc() };
  for (const [name, obj] of Object.entries(sources)) {
    it(name, () => {
      const hits: string[] = [];
      const walk = (o: unknown, p: string) => {
        if (typeof o === "string") {
          for (const [, s] of findDigits(o)) hits.push(`${p}: ${s}`);
        } else if (o && typeof o === "object") {
          for (const [k, v] of Object.entries(o)) walk(v, p ? `${p}.${k}` : k);
        }
      };
      walk(obj, "");
      expect(hits).toEqual([]);
    });
  }
});

describe("no-digits: home page play text (round 3)", () => {
  // the hero, the rupee tour and the guessing game put figures in through bindings only
  const map = JSON.parse(fs.readFileSync(path.join(process.cwd(), "messages", "en", "map.json"), "utf8")) as Record<string, unknown>;
  for (const ns of ["hero", "tour", "guess"]) {
    it(`map.json ${ns}`, () => {
      const hits: string[] = [];
      const walk = (o: unknown, p: string) => {
        if (typeof o === "string") {
          for (const [, s] of findDigits(o)) hits.push(`${p}: ${s}`);
        } else if (o && typeof o === "object") {
          for (const [k, v] of Object.entries(o)) walk(v, `${p}.${k}`);
        }
      };
      expect(map[ns], `namespace ${ns}`).toBeTruthy();
      walk(map[ns], ns);
      expect(hits).toEqual([]);
    });
  }
});
