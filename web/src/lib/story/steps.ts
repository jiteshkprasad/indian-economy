/**
 * The story engine's state machine (PLAN §4.9). Pure functions, no React, so vitest
 * can check every transition. One step is active at a time; Previous/Next and the
 * arrow keys move by one, the progress list jumps, `?step=<id>` deep-links.
 */

export type StepState = { ids: readonly string[]; index: number };

export type StepAction =
  | { type: "next" }
  | { type: "prev" }
  | { type: "first" }
  | { type: "last" }
  | { type: "goto"; id: string };

export function initialStepState(ids: readonly string[], requested: string | null = null): StepState {
  if (ids.length === 0) throw new Error("story: a story needs at least one step");
  const i = requested === null ? -1 : ids.indexOf(requested);
  return { ids, index: i >= 0 ? i : 0 };
}

/** Moves never wrap around; an unknown id leaves the state unchanged. */
export function stepReducer(state: StepState, action: StepAction): StepState {
  const last = state.ids.length - 1;
  let index = state.index;
  switch (action.type) {
    case "next":
      index = Math.min(last, state.index + 1);
      break;
    case "prev":
      index = Math.max(0, state.index - 1);
      break;
    case "first":
      index = 0;
      break;
    case "last":
      index = last;
      break;
    case "goto": {
      const i = state.ids.indexOf(action.id);
      if (i >= 0) index = i;
      break;
    }
  }
  return index === state.index ? state : { ids: state.ids, index };
}

export const activeId = (s: StepState): string => s.ids[s.index];
export const isFirst = (s: StepState): boolean => s.index === 0;
export const isLast = (s: StepState): boolean => s.index === s.ids.length - 1;

/**
 * Reads `?step=<id>` from a query string. Returns `{ id }` when it names a step,
 * `{ invalid }` when the parameter is present but unknown (the page shows a notice;
 * PLAN §4.3: invalid values are dropped visibly, not silently), or nulls.
 */
export function parseStepParam(search: string, ids: readonly string[]): { id: string | null; invalid: string | null } {
  const raw = new URLSearchParams(search).get("step");
  if (raw === null || raw === "") return { id: null, invalid: null };
  return ids.includes(raw) ? { id: raw, invalid: null } : { id: null, invalid: raw };
}

/** The query string with `step` set (other parameters kept, in order). */
export function withStepParam(search: string, id: string): string {
  const p = new URLSearchParams(search);
  p.set("step", id);
  return `?${p.toString()}`;
}

/** Keyboard: ←/→ step, Home/End jump. Returns null for keys the player ignores. */
export function keyToAction(key: string): StepAction | null {
  switch (key) {
    case "ArrowRight":
      return { type: "next" };
    case "ArrowLeft":
      return { type: "prev" };
    case "Home":
      return { type: "first" };
    case "End":
      return { type: "last" };
    default:
      return null;
  }
}
