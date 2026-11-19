import { describe, expect, it } from "vitest";
import { format, formatCount, formatInr, groupIndian, MINUS, type FmtKind } from "@/lib/format";
import { readGolden } from "./golden";

type Case = { kind: FmtKind; value: number; out: string };
const golden = readGolden<{ cases: Case[] }>("format_cases.json");

describe("format.ts reproduces golden/format_cases.json", () => {
  it("has cases for every kind", () => {
    const kinds = new Set(golden.cases.map((c) => c.kind));
    for (const k of ["inr", "pct_gdp", "per100", "pct"]) expect(kinds.has(k as FmtKind)).toBe(true);
  });
  for (const c of golden.cases) {
    it(`${c.kind}(${c.value}) = ${c.out}`, () => {
      expect(format(c.value, c.kind)).toBe(c.out);
    });
  }
});

describe("format.ts details", () => {
  it("uses Indian grouping", () => {
    expect(groupIndian("29073287")).toBe("2,90,73,287");
    expect(groupIndian("1234.57")).toBe("1,234.57");
    expect(groupIndian("999")).toBe("999");
    expect(formatCount(2169)).toBe("2,169");
    expect(formatCount(128)).toBe("128");
  });
  it("uses U+2212 for negatives and never prints −0", () => {
    expect(formatInr(-576422.4).startsWith(MINUS)).toBe(true);
    expect(formatInr(-0.04)).toBe("₹0.0 crore");
    expect(formatInr(-0)).toBe("₹0.0 crore");
  });
  it("throws on non-finite values (no silent fallbacks)", () => {
    expect(() => format(Number.NaN, "inr")).toThrow();
    expect(() => format(Number.POSITIVE_INFINITY, "pct_gdp")).toThrow();
  });
});
