import { describe, expect, it } from "vitest";
import {
  activeId,
  initialStepState,
  isFirst,
  isLast,
  keyToAction,
  parseStepParam,
  stepReducer,
  withStepParam,
} from "@/lib/story/steps";
import { isStorySlug, STORY_SLUGS, storyKey } from "@/lib/story/registry";

const IDS = ["a", "b", "c"] as const;

describe("story step state machine (PLAN §4.9)", () => {
  it("starts at the first step, or at a requested known step", () => {
    expect(activeId(initialStepState(IDS))).toBe("a");
    expect(activeId(initialStepState(IDS, "c"))).toBe("c");
    expect(activeId(initialStepState(IDS, "zzz"))).toBe("a");
  });

  it("refuses a story without steps", () => {
    expect(() => initialStepState([])).toThrow();
  });

  it("moves by one without wrapping", () => {
    let s = initialStepState(IDS);
    expect(isFirst(s)).toBe(true);
    s = stepReducer(s, { type: "prev" });
    expect(activeId(s)).toBe("a");
    s = stepReducer(s, { type: "next" });
    s = stepReducer(s, { type: "next" });
    expect(activeId(s)).toBe("c");
    expect(isLast(s)).toBe(true);
    const same = stepReducer(s, { type: "next" });
    expect(same).toBe(s); // unchanged state object: no re-render, no announcement
  });

  it("jumps with goto, first and last; ignores unknown ids", () => {
    let s = initialStepState(IDS);
    s = stepReducer(s, { type: "goto", id: "b" });
    expect(activeId(s)).toBe("b");
    expect(stepReducer(s, { type: "goto", id: "nope" })).toBe(s);
    expect(activeId(stepReducer(s, { type: "last" }))).toBe("c");
    expect(activeId(stepReducer(s, { type: "first" }))).toBe("a");
  });

  it("maps keys: arrows step, Home/End jump, others ignored", () => {
    expect(keyToAction("ArrowRight")).toEqual({ type: "next" });
    expect(keyToAction("ArrowLeft")).toEqual({ type: "prev" });
    expect(keyToAction("Home")).toEqual({ type: "first" });
    expect(keyToAction("End")).toEqual({ type: "last" });
    expect(keyToAction("ArrowDown")).toBeNull();
    expect(keyToAction("Enter")).toBeNull();
  });

  it("reads ?step= and reports an unknown step visibly instead of dropping it silently", () => {
    expect(parseStepParam("", IDS)).toEqual({ id: null, invalid: null });
    expect(parseStepParam("?step=b", IDS)).toEqual({ id: "b", invalid: null });
    expect(parseStepParam("?x=1&step=zzz", IDS)).toEqual({ id: null, invalid: "zzz" });
    expect(parseStepParam("?step=", IDS)).toEqual({ id: null, invalid: null });
  });

  it("writes ?step= keeping other parameters", () => {
    expect(withStepParam("", "b")).toBe("?step=b");
    expect(withStepParam("?x=1&step=a", "c")).toBe("?x=1&step=c");
  });
});

describe("story registry", () => {
  it("has the three PLAN §4.9 stories and their message keys", () => {
    expect([...STORY_SLUGS]).toEqual(["gst-rupee", "remittance-dubai", "deficit-funding"]);
    expect(isStorySlug("gst-rupee")).toBe(true);
    expect(isStorySlug("nope")).toBe(false);
    expect(storyKey.stepTitle("gst-rupee", "total")).toBe("stories.gst-rupee.steps.total");
    expect(storyKey.figLabel("deficit-funding", "nl_cen")).toBe("figs.deficit-funding.nl_cen");
  });
});
