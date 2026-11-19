import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import { describe, expect, it } from "vitest";
import { resolveDataRoot } from "@/data/root.mjs";
// @ts-expect-error: plain ESM script without types
import { checkData } from "../../../scripts/check-data.mjs";
// @ts-expect-error: plain ESM script without types
import { serveConfig } from "../../../scripts/serve-out.mjs";
import { checkTopLevel } from "@/data/validate";

function tmpData(fixture: boolean, corrupt = false): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "u2-data-"));
  const v = "2023-24.fixture0000";
  fs.mkdirSync(path.join(dir, v));
  const body = Buffer.from('{"a":1}');
  fs.writeFileSync(path.join(dir, v, "x.json"), corrupt ? Buffer.from('{"a":2}') : body);
  const sha = crypto.createHash("sha256").update(body).digest("hex");
  fs.writeFileSync(path.join(dir, "index.json"), JSON.stringify({ data_version: v, fixture, files: { "x.json": { sha256: sha, bytes: body.length } } }));
  return dir;
}

describe("data root and fixture guard (PLAN §3.10)", () => {
  it("resolves DATA_ROOT", () => {
    expect(resolveDataRoot("/w", { DATA_ROOT: "public" })).toMatchObject({ kind: "public", dir: "/w/public/data", base: "/data" });
    expect(resolveDataRoot("/w", { DATA_ROOT: "fixtures" })).toMatchObject({ kind: "fixtures", dir: "/w/fixtures/data", base: "/data-fixture" });
    expect(resolveDataRoot("/w", { DATA_ROOT: "/abs/x" })).toMatchObject({ kind: "custom", dir: "/abs/x", base: "/data-fixture" });
    expect(() => resolveDataRoot("/w", { DATA_ROOT: "rel" })).toThrow();
  });
  it("a fixture build fails without ALLOW_FIXTURE=1 and passes with it", () => {
    const dir = tmpData(true);
    expect(checkData({ DATA_ROOT: dir }).ok).toBe(false);
    expect(checkData({ DATA_ROOT: dir }).msg).toMatch(/fixture/);
    expect(checkData({ DATA_ROOT: dir, ALLOW_FIXTURE: "1" })).toMatchObject({ ok: true, fixture: true });
  });
  it("fails when a file does not match its sha256", () => {
    const dir = tmpData(true, true);
    const r = checkData({ DATA_ROOT: dir, ALLOW_FIXTURE: "1" });
    expect(r.ok).toBe(false);
    expect(r.msg).toMatch(/sha256 mismatch x.json/);
  });
  it("fails when index.json is missing", () => {
    expect(checkData({ DATA_ROOT: fs.mkdtempSync(path.join(os.tmpdir(), "u2-empty-")) }).ok).toBe(false);
  });
});

describe("serve-out mirrors vercel.json", () => {
  it("turns vercel sources into serve-handler globs, keeping order", () => {
    const c = serveConfig();
    expect(c.redirects).toEqual([{ source: "/", destination: "/en/", type: 308 }]);
    expect(c.headers.map((h: { source: string }) => h.source)).toEqual(["/_next/static/**", "/data/**", "/data/index.json", "/**"]);
    expect(c.trailingSlash).toBe(true);
  });
});

describe("loader validation", () => {
  it("names missing top-level keys", () => {
    expect(() => checkTopLevel("sam/cells.json", { n: 1 })).toThrow(/sam\/cells.json: missing top-level keys: row, col/);
    expect(() => checkTopLevel("sam/entries/HH.json", { node: "HH" })).toThrow(/entries/);
    expect(() => checkTopLevel("summary.json", [])).toThrow(/JSON object/);
    expect(() => checkTopLevel("sam/pinned.json", {})).not.toThrow();
  });
});

describe("first-load chunk parsing (PLAN §4.13)", () => {
  it("counts script and preload chunks plus payload chunks, not noModule polyfills", async () => {
    // @ts-expect-error: plain ESM script without types
    const { referencedChunks } = await import("../../../scripts/first-load.mjs");
    const html =
      '<link rel="preload" as="script" href="/_next/static/chunks/a.js"/>' +
      '<script src="/_next/static/chunks/b.js" async=""></script>' +
      '<script src="/_next/static/chunks/poly.js" noModule=""></script>' +
      '<script>self.__next_f.push([1,"I:[\\"/_next/static/chunks/c.js\\"]"])</script>';
    expect(referencedChunks(html)).toEqual(["/_next/static/chunks/a.js", "/_next/static/chunks/b.js", "/_next/static/chunks/c.js"]);
  });
});
