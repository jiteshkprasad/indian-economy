import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
// @ts-expect-error: plain ESM script without types
import { generate } from "../../../scripts/gen-contract.mjs";

const web = path.resolve(__dirname, "../../..");

describe("contract.gen.ts", () => {
  it("is up to date with pipeline/export/schema (run `npm run gen:contract`)", async () => {
    const { text, files } = (await generate()) as { text: string; files: string[] };
    expect(files.length, "no schema files in pipeline/export/schema").toBeGreaterThan(0);
    const current = fs.readFileSync(path.join(web, "src/data/contract.gen.ts"), "utf8");
    expect(current === text, "src/data/contract.gen.ts is stale").toBe(true);
  });
  it("generates deterministically", async () => {
    const a = (await generate()) as { text: string };
    const b = (await generate()) as { text: string };
    expect(a.text).toBe(b.text);
  });
});
