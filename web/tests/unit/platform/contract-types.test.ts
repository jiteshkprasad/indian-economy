import { describe, expect, expectTypeOf, it } from "vitest";
import type * as Gen from "@/data/contract.gen";
import type * as T from "@/data/types";
import { REQUIRED_KEYS } from "@/data/types";

// The hand-written types the app uses must accept every value the generated
// (schema) types describe, and the top-level keys the loaders check must be
// the schema's required keys. Compile-time checks run under `tsc --noEmit`.
describe("types.ts vs contract.gen.ts", () => {
  it("generated shapes are assignable to the app types", () => {
    expectTypeOf<Gen.Summary>().toExtend<T.Summary>();
    expectTypeOf<Gen.Hierarchy>().toExtend<T.Hierarchy>();
    expectTypeOf<Gen.Cells>().toExtend<T.Cells>();
    expectTypeOf<Gen.Pinned>().toExtend<T.Pinned>();
    expectTypeOf<Gen.TsView>().toExtend<T.TsView>();
    expectTypeOf<Gen.Entries>().toExtend<T.Entries>();
    expectTypeOf<Gen.Constraints>().toExtend<T.Constraints>();
    expectTypeOf<Gen.Refs>().toExtend<T.Refs>();
    expectTypeOf<Gen.Provenance>().toExtend<T.Provenance>();
    expectTypeOf<Gen.Series>().toExtend<T.Series>();
    // the schema cannot express the [row, col, value] tuple without minItems; check the other way
    expectTypeOf<T.Cover>().toExtend<Gen.Cover>();
    expectTypeOf<Gen.Story>().toExtend<T.Story>();
    expectTypeOf<Gen.DataIndex>().toExtend<T.DataIndex>();
    expect(true).toBe(true);
  });
  it("REQUIRED_KEYS match the schemas' required top-level keys", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const dir = path.resolve(__dirname, "../../../../pipeline/export/schema");
    const map: Record<string, string> = {
      "index.json": "index",
      "summary.json": "summary",
      "hierarchy.json": "hierarchy",
      "sam/cells.json": "cells",
      "provenance.json": "provenance",
      "ts/series.json": "series",
      "ts/view.json": "ts_view",
      entries: "entries",
      story: "story",
    };
    for (const [k, schema] of Object.entries(map)) {
      const s = JSON.parse(fs.readFileSync(path.join(dir, `${schema}.schema.json`), "utf8"));
      expect([...(s.required ?? [])].sort(), k).toEqual([...REQUIRED_KEYS[k]].sort());
    }
  });
});
