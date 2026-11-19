import { describe, expect, it } from "vitest";
import { DEFAULT_STATE, historyModeFor, normaliseState, parseUrlState, serialiseUrlState } from "@/lib/url-state";
import { isLinkId, linkId, pairId, parseLinkId, siblingId } from "@/lib/ids";
import { miniHierarchy } from "./mini";

const ctx = { hierarchy: miniHierarchy(), years: ["1950-51", "2022-23", "2023-24", "2024-25"] };

describe("ids", () => {
  it("builds and parses link ids", () => {
    expect(linkId("HH", "PRDS")).toBe("HH--PRDS");
    expect(linkId("PRDS", "TAX", "neg")).toBe("PRDS--TAX~neg");
    expect(parseLinkId("HH.RUR--PRDS.AGRI")).toEqual({ payer: "HH.RUR", receiver: "PRDS.AGRI", part: "pos" });
    expect(parseLinkId("PRDS--TAX~pair")?.part).toBe("pair");
    expect(parseLinkId("HH")).toBeNull();
    expect(isLinkId("H_R1--C_CROP")).toBe(true);
    expect(pairId("PRDS--TAX~neg")).toBe("PRDS--TAX~pair");
    expect(siblingId("PRDS--TAX")).toBe("PRDS--TAX~neg");
  });
});

describe("url-state", () => {
  it("empty query is the default state", () => {
    expect(parseUrlState("", ctx)).toEqual({ state: DEFAULT_STATE, notices: [] });
    expect(serialiseUrlState(DEFAULT_STATE)).toBe("");
  });
  it("parses a full query and keeps x in hierarchy order (x implies full)", () => {
    const { state, notices } = parseUrlState("?view=sam&p=simple&y=2023-24&x=HH,PRDS&s=HH--PRDS&t=table", ctx);
    expect(notices).toEqual([]);
    expect(state).toEqual({ view: "sam", preset: "full", year: "2023-24", expanded: ["PRDS", "HH"], selected: "HH--PRDS", table: true });
  });
  it("forces the top-flows view off the SAM year", () => {
    const { state } = parseUrlState("?view=sam&y=2004-05", { ...ctx, years: [...ctx.years, "2004-05"] });
    expect(state.view).toBe("ts");
  });
  it("drops invalid values with a visible notice, never silently", () => {
    const { state, notices } = parseUrlState("?view=x&p=zz&y=1900-01&x=NOPE,FACT&s=HH--NOPE&t=list", ctx);
    expect(state).toEqual(DEFAULT_STATE);
    expect(notices.map((n) => n.key)).toEqual([
      "url.invalidView",
      "url.invalidPreset",
      "url.invalidYear",
      "url.nodeNotFound",
      "url.notExpandable",
      "url.linkNotFound",
      "url.invalidTable",
    ]);
    expect(notices[5].values.value).toBe("HH--NOPE");
  });
  it("accepts preset node ids, negative parts and series ids as selections", () => {
    expect(parseUrlState("?s=TAX--PRODUCERS~neg", ctx).state.selected).toBe("TAX--PRODUCERS~neg");
    expect(parseUrlState("?s=PRODUCERS", ctx).state.selected).toBe("PRODUCERS");
    expect(parseUrlState("?s=F01", ctx).state.selected).toBe("F01");
    expect(parseUrlState("?s=HH--PRDS~pair", ctx).notices[0].key).toBe("url.linkNotFound");
  });
  it("round-trips through serialise", () => {
    for (const q of ["?p=full", "?y=1950-51", "?view=ts", "?x=PRDS,PRDS.X&s=C_A--PROD", "?s=HH--PRODUCERS&t=table"]) {
      const { state } = parseUrlState(q, ctx);
      expect(serialiseUrlState(state)).toBe(q);
      expect(parseUrlState(serialiseUrlState(state), ctx).state).toEqual(state);
    }
  });
  it("adds ancestors of expanded nodes", () => {
    expect(normaliseState({ ...DEFAULT_STATE, expanded: ["PRDS.X"] }, ctx).expanded).toEqual(["PRDS", "PRDS.X"]);
  });
  it("slider moves replace history; selection and zoom push", () => {
    const a = DEFAULT_STATE;
    expect(historyModeFor(a, { ...a, year: "1950-51", view: "ts" })).toBe("replace");
    expect(historyModeFor(a, { ...a, selected: "HH--PRDS" })).toBe("push");
    expect(historyModeFor(a, { ...a, expanded: ["HH"], preset: "full" })).toBe("push");
  });
});
