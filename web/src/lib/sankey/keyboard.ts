/**
 * The diagram's keyboard model (PLAN §4.5.10), as pure functions over a layout:
 * ↑/↓ within a column, ←/→ to the nearest node (by centre) in the next non-empty column,
 * L lists a node's drawn links (outgoing, then incoming, each top to bottom).
 */
import type { Layout } from "./types";

export type Dir = "up" | "down" | "left" | "right";

export function moveFocus(L: Layout, key: string, dir: Dir): string {
  const node = L.nodes.find((n) => n.key === key);
  if (!node) return L.columns.find((c) => c.length)?.[0] ?? key;
  const col = L.columns[node.col];
  const i = col.indexOf(key);
  if (dir === "up") return i > 0 ? col[i - 1] : key;
  if (dir === "down") return i < col.length - 1 ? col[i + 1] : key;
  const step = dir === "right" ? 1 : -1;
  const cy = node.y + node.h / 2;
  for (let c = node.col + step; c >= 0 && c < L.columns.length; c += step) {
    const keys = L.columns[c];
    if (!keys.length) continue;
    let best = keys[0];
    let bestD = Infinity;
    for (const k of keys) {
      const n = L.nodes.find((m) => m.key === k)!;
      const d = Math.abs(n.y + n.h / 2 - cy);
      if (d < bestD - 1e-9) {
        bestD = d;
        best = k;
      }
    }
    return best;
  }
  return key;
}

/** Drawn links of a node copy: outgoing (top to bottom), then incoming (top to bottom). */
export function linksOfKey(L: Layout, key: string): string[] {
  const out = L.links.filter((l) => l.drawn && l.sourceKey === key).sort((a, b) => a.sPort.y0 - b.sPort.y0);
  const inn = L.links.filter((l) => l.drawn && l.targetKey === key).sort((a, b) => a.tPort.y0 - b.tPort.y0);
  return [...out.map((l) => l.id), ...inn.map((l) => l.id)];
}

/** The first node key in reading order (top of the first non-empty column). */
export function firstKey(L: Layout): string | null {
  return L.columns.find((c) => c.length)?.[0] ?? null;
}
