// Keyboard model for the heat-map grid (PLAN §4.8): arrow keys move the cursor, Enter zooms into
// the block under it, Escape zooms out, T opens the table. Pure: maps a key to an action.

export interface Cursor {
  i: number;
  j: number;
}

export type KeyAction =
  | { type: "move"; to: Cursor }
  | { type: "zoomIn" }
  | { type: "zoomOut" }
  | { type: "table" }
  | { type: "none" };

const clamp = (x: number, lo: number, hi: number) => (x < lo ? lo : x > hi ? hi : x);

/** Rows/columns moved by PageUp/PageDown. */
export const PAGE = 8;

export function keyAction(
  key: string,
  c: Cursor,
  nR: number,
  nC: number,
  mods: { ctrl?: boolean; meta?: boolean; alt?: boolean } = {},
): KeyAction {
  if (mods.alt) return { type: "none" };
  const ctrl = !!(mods.ctrl || mods.meta);
  const move = (i: number, j: number): KeyAction => {
    const to = { i: clamp(i, 0, nR - 1), j: clamp(j, 0, nC - 1) };
    return to.i === c.i && to.j === c.j ? { type: "none" } : { type: "move", to };
  };
  switch (key) {
    case "ArrowUp":
      return move(c.i - 1, c.j);
    case "ArrowDown":
      return move(c.i + 1, c.j);
    case "ArrowLeft":
      return move(c.i, c.j - 1);
    case "ArrowRight":
      return move(c.i, c.j + 1);
    case "Home":
      return ctrl ? move(0, 0) : move(c.i, 0);
    case "End":
      return ctrl ? move(nR - 1, nC - 1) : move(c.i, nC - 1);
    case "PageUp":
      return move(c.i - PAGE, c.j);
    case "PageDown":
      return move(c.i + PAGE, c.j);
    case "Enter":
    case " ":
      return ctrl ? { type: "none" } : { type: "zoomIn" };
    case "Escape":
    case "Backspace":
      return ctrl ? { type: "none" } : { type: "zoomOut" };
    case "t":
    case "T":
      return ctrl ? { type: "none" } : { type: "table" };
    default:
      return { type: "none" };
  }
}

/** Keep a cursor inside a (possibly smaller) new grid. */
export function clampCursor(c: Cursor, nR: number, nC: number): Cursor {
  return { i: clamp(c.i, 0, nR - 1), j: clamp(c.j, 0, nC - 1) };
}
