import { describe, expect, it } from "vitest";
import {
  badgeText,
  composition,
  entryLabel,
  flagMask,
  flagNames,
  FLAGS,
  headlineSplit,
  headlineSplitAbs,
  LabelRuleError,
  needsExplanation,
  type EntryLabelInput,
} from "@/lib/status";
import type { Label } from "@/data/types";
import { readGolden } from "./golden";

type EntryCase = EntryLabelInput & { name: string; label: Label | "error" };
type SplitCase = { name: string; abs: { o: number; d: number; e: number; b: number }; composition: Record<string, number>; split: Label };
const golden = readGolden<{
  entry_cases: EntryCase[];
  split_cases: SplitCase[];
  flag_bits: Record<string, number>;
  aggregate_cases: unknown[];
}>("status_cases.json");

describe("status.ts reproduces golden/status_cases.json", () => {
  for (const c of golden.entry_cases) {
    it(`entry: ${c.name}`, () => {
      if (c.label === "error") expect(() => entryLabel(c)).toThrow(LabelRuleError);
      else expect(entryLabel(c)).toBe(c.label);
    });
  }
  for (const c of golden.split_cases) {
    it(`split: ${c.name}`, () => {
      expect(headlineSplitAbs(c.abs)).toBe(c.split);
      const comp = composition(c.abs.o, c.abs.d, c.abs.e, c.abs.b)!;
      for (const k of ["o", "d", "e", "b"] as const) expect(comp[k]).toBeCloseTo(c.composition[k], 4);
      expect(comp.o + comp.d + comp.e + comp.b).toBeCloseTo(1, 9);
      expect(headlineSplit(comp)).toBe(c.split);
    });
  }
  it("flag bits match", () => {
    expect(FLAGS).toEqual(golden.flag_bits);
  });
});

describe("status.ts details", () => {
  it("needsExplanation mirrors pipeline.sam.spec", () => {
    expect(needsExplanation(100000, 105000)).toBe(true);
    expect(needsExplanation(100000, 104999)).toBe(false);
    expect(needsExplanation(1000, 1500)).toBe(true);
    expect(needsExplanation(10000, 10600)).toBe(false);
    expect(needsExplanation(0, 600)).toBe(true);
    expect(needsExplanation(0, 400)).toBe(false);
  });
  it("flag names round-trip", () => {
    expect(flagNames(1 | 16 | 64)).toEqual(["judgement_band", "discrepancy", "depends_on_assumption"]);
    expect(flagMask(["unexplained", "has_negative"])).toBe(34);
    expect(() => flagMask(["nope"])).toThrow();
  });
  it("badge text states total and split separately", () => {
    expect(badgeText("official", "estimated")).toBe("Official total · split estimated");
    expect(badgeText(null, "estimated")).toBe("Estimated");
    expect(badgeText(null, "balancing_set")).toBe("Set by balancing");
    expect(badgeText("official", "official")).toBe("Official total");
    expect(badgeText("derived", "balancing_set")).toBe("Derived total · split set by balancing");
  });
  it("zero aggregate has no composition", () => {
    expect(composition(0, 0, 0, 0)).toBeNull();
    expect(headlineSplitAbs({ o: 0, d: 0, e: 0, b: 0 })).toBeNull();
  });
});
