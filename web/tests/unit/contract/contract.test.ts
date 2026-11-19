// Contract test (PLAN §3.10, §5.2; owner U1): every exported JSON file validates against its JSON Schema
// (pipeline/export/schema/*.schema.json) with ajv, for the generated fixture and for the real export.
// The real-data half reports "REAL EXPORT NOT VALIDATED" when web/public/data/index.json does not exist.
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import Ajv from "ajv";
import { describe, expect, it } from "vitest";

const WEB = path.resolve(__dirname, "../../..");
const SCHEMA_DIR = path.resolve(WEB, "../pipeline/export/schema");
const ROOTS = {
  fixture: path.join(WEB, "fixtures/data"),
  real: path.join(WEB, "public/data"),
} as const;

// Mirrors FILE_SCHEMAS in pipeline/export/schemas.py (paths relative to the data version folder).
const FILE_SCHEMAS: Array<[RegExp, string]> = [
  [/^summary\.json$/, "summary"],
  [/^hierarchy\.json$/, "hierarchy"],
  [/^sam\/cells\.json$/, "cells"],
  [/^sam\/pinned\.json$/, "pinned"],
  [/^sam\/entries\/[A-Z]+\.json$/, "entries"],
  [/^sam\/constraints\.json$/, "constraints"],
  [/^sam\/refs\.json$/, "refs"],
  [/^provenance\.json$/, "provenance"],
  [/^ts\/series\.json$/, "series"],
  [/^ts\/view\.json$/, "ts_view"],
  [/^ts\/cover\.json$/, "cover"],
  [/^stories\/[a-z0-9-]+\.json$/, "story"],
];

type Index = { data_version: string; fixture: boolean; files: Record<string, { sha256: string; bytes: number }> };

function ajvFor(name: string) {
  const schema = JSON.parse(fs.readFileSync(path.join(SCHEMA_DIR, `${name}.schema.json`), "utf8"));
  const ajv = new Ajv({ allErrors: true, strict: false });
  return ajv.compile(schema);
}

const validators = new Map<string, ReturnType<typeof ajvFor>>();
function validator(name: string) {
  let v = validators.get(name);
  if (!v) {
    v = ajvFor(name);
    validators.set(name, v);
  }
  return v;
}

function schemaFor(rel: string): string {
  const hit = FILE_SCHEMAS.find(([re]) => re.test(rel));
  if (!hit) throw new Error(`no schema for exported file ${rel}`);
  return hit[1];
}

function checkRoot(root: string, expectFixture: boolean) {
  const index = JSON.parse(fs.readFileSync(path.join(root, "index.json"), "utf8")) as Index;
  const vIndex = validator("index");
  expect(vIndex(index), JSON.stringify(vIndex.errors?.slice(0, 3))).toBe(true);
  expect(index.fixture).toBe(expectFixture);
  const vdir = path.join(root, index.data_version);
  const files = Object.keys(index.files).sort();
  expect(files.length).toBeGreaterThanOrEqual(26);
  for (const rel of files) {
    const bytes = fs.readFileSync(path.join(vdir, rel));
    expect(createHash("sha256").update(bytes).digest("hex"), rel).toBe(index.files[rel].sha256);
    const v = validator(schemaFor(rel));
    const ok = v(JSON.parse(bytes.toString("utf8")));
    expect(ok, `${rel}: ${JSON.stringify(v.errors?.slice(0, 3))}`).toBe(true);
  }
}

describe("data contract", () => {
  it("every schema compiles", () => {
    const names = fs.readdirSync(SCHEMA_DIR).filter((f) => f.endsWith(".schema.json"));
    expect(names.length).toBe(13);
    for (const n of names) validator(n.replace(/\.schema\.json$/, ""));
  });

  it("the generated fixture validates", () => {
    expect(fs.existsSync(path.join(ROOTS.fixture, "index.json"))).toBe(true);
    checkRoot(ROOTS.fixture, true);
  });

  it("the real export validates", () => {
    const idx = path.join(ROOTS.real, "index.json");
    if (!fs.existsSync(idx)) {
      console.warn("REAL EXPORT NOT VALIDATED: web/public/data/index.json does not exist");
      return;
    }
    checkRoot(ROOTS.real, false);
  });
});
