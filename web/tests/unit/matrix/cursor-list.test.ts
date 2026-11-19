import { describe, expect, it } from "vitest";
import { indexHierarchy } from "../../../src/lib/matrix/axes";
import { NO_FILTER, listCells } from "../../../src/lib/matrix/cells-list";
import { PAGE, clampCursor, keyAction } from "../../../src/lib/matrix/cursor";
import { tinyCells, tinyHierarchy } from "./tiny";

describe("keyboard cursor", () => {
  const c = { i: 2, j: 2 };
  it("arrows move one cell and stop at the edges", () => {
    expect(keyAction("ArrowUp", c, 13, 13)).toEqual({ type: "move", to: { i: 1, j: 2 } });
    expect(keyAction("ArrowRight", c, 13, 13)).toEqual({ type: "move", to: { i: 2, j: 3 } });
    expect(keyAction("ArrowLeft", { i: 0, j: 0 }, 13, 13)).toEqual({ type: "none" });
    expect(keyAction("ArrowDown", { i: 12, j: 0 }, 13, 13)).toEqual({ type: "none" });
  });
  it("Home/End move along the row; with Ctrl to the corners; PageUp/Down jump", () => {
    expect(keyAction("Home", c, 13, 13)).toEqual({ type: "move", to: { i: 2, j: 0 } });
    expect(keyAction("End", c, 13, 13)).toEqual({ type: "move", to: { i: 2, j: 12 } });
    expect(keyAction("End", c, 13, 13, { ctrl: true })).toEqual({ type: "move", to: { i: 12, j: 12 } });
    expect(keyAction("Home", c, 13, 13, { meta: true })).toEqual({ type: "move", to: { i: 0, j: 0 } });
    expect(keyAction("PageDown", c, 128, 128)).toEqual({ type: "move", to: { i: 2 + PAGE, j: 2 } });
  });
  it("Enter zooms in, Escape zooms out, T opens the table", () => {
    expect(keyAction("Enter", c, 13, 13).type).toBe("zoomIn");
    expect(keyAction("Escape", c, 13, 13).type).toBe("zoomOut");
    expect(keyAction("t", c, 13, 13).type).toBe("table");
    expect(keyAction("T", c, 13, 13).type).toBe("table");
    expect(keyAction("t", c, 13, 13, { ctrl: true }).type).toBe("none");
    expect(keyAction("Tab", c, 13, 13).type).toBe("none");
  });
  it("clamps the cursor into a smaller grid", () => {
    expect(clampCursor({ i: 100, j: 5 }, 13, 3)).toEqual({ i: 12, j: 2 });
  });
});

describe("all non-zero cells list", () => {
  const ix = indexHierarchy(tinyHierarchy);
  const label = (code: string) => code.toUpperCase();
  const code = (idx: number) => tinyHierarchy.accounts[idx].code;

  it("lists every cell once, by |value| descending by default", () => {
    const out = listCells(tinyCells, tinyHierarchy, ix, NO_FILTER, "abs", "desc", label);
    expect(out.length).toBe(tinyCells.n);
    expect(new Set(out).size).toBe(tinyCells.n);
    const abs = out.map((k) => Math.abs(tinyCells.v[k]));
    expect(abs).toEqual([...abs].sort((a, b) => b - a));
  });

  it("filters by payer and receiver at any level", () => {
    const f = { payer: "P", receiver: "Q", text: "" };
    const out = listCells(tinyCells, tinyHierarchy, ix, f, "value", "asc", label);
    // P pays Q: p3 → q1 (60) and p1 → q1 (90), ascending by value
    expect(out.map((k) => [code(tinyCells.col[k]), code(tinyCells.row[k])])).toEqual([
      ["p3", "q1"],
      ["p1", "q1"],
    ]);
    const px = listCells(tinyCells, tinyHierarchy, ix, { ...NO_FILTER, payer: "P.X" }, "abs", "desc", label);
    expect(px.every((k) => ["p1", "p2"].includes(code(tinyCells.col[k])))).toBe(true);
    expect(px.length).toBe(4);
  });

  it("text filter matches codes and labels, case-insensitively", () => {
    const out = listCells(tinyCells, tinyHierarchy, ix, { ...NO_FILTER, text: "R2" }, "abs", "desc", label);
    expect(out.length).toBe(3);
  });

  it("sorts by value with signs, and the order is total (deterministic ties)", () => {
    const asc = listCells(tinyCells, tinyHierarchy, ix, NO_FILTER, "value", "asc", label);
    expect(tinyCells.v[asc[0]]).toBe(-20);
    const byPayer = listCells(tinyCells, tinyHierarchy, ix, NO_FILTER, "payer", "asc", label);
    const again = listCells(tinyCells, tinyHierarchy, ix, NO_FILTER, "payer", "asc", label);
    expect(byPayer).toEqual(again);
    const names = byPayer.map((k) => label(code(tinyCells.col[k])));
    expect(names).toEqual([...names].sort());
  });

  it("rejects an unknown filter node", () => {
    expect(() =>
      listCells(tinyCells, tinyHierarchy, ix, { ...NO_FILTER, payer: "ZZ" }, "abs", "desc", label),
    ).toThrow(/unknown node/);
  });
});
