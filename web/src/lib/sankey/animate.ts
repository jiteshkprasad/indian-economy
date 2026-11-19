"use client";
/**
 * FLIP-style tween of path data (PLAN §4.5.11). React renders the final `d` of every mark; after a
 * render this effect interpolates each changed path from its previous geometry to the new one with
 * requestAnimationFrame, writing only during the tween's frames. A new render cancels a running
 * tween (and leaves React's final values in place). Under reduced motion nothing is tweened.
 * Paths whose command structure differs are not tweened (they jump), never distorted.
 */
import { useLayoutEffect, useRef, type RefObject } from "react";

const NUM = /-?\d+(?:\.\d+)?(?:e[-+]?\d+)?/gi;

function shape(d: string): string {
  return d.replace(NUM, "#");
}

function numbers(d: string): number[] {
  return (d.match(NUM) ?? []).map(Number);
}

function fill(template: string, vals: number[]): string {
  let i = 0;
  return template.replace(/#/g, () => String(Math.round(vals[i++] * 100) / 100));
}

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return true;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Tween every `path[data-tween]` inside `root` whose `d` changed since the previous render.
 * `version` must change whenever the geometry changes (e.g. a layout key).
 */
export function usePathTween(root: RefObject<SVGElement | null>, version: string, duration = 300): void {
  const prev = useRef<Map<string, string>>(new Map());
  const raf = useRef<number | null>(null);
  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    if (raf.current !== null) cancelAnimationFrame(raf.current);
    const paths = Array.from(el.querySelectorAll<SVGPathElement>("path[data-tween]"));
    const next = new Map<string, string>();
    const jobs: Array<{ p: SVGPathElement; tpl: string; a: number[]; b: number[]; final: string }> = [];
    for (const p of paths) {
      const key = p.getAttribute("data-tween")!;
      const d = p.getAttribute("d") ?? "";
      next.set(key, d);
      const old = prev.current.get(key);
      if (old && old !== d && shape(old) === shape(d)) {
        jobs.push({ p, tpl: shape(d), a: numbers(old), b: numbers(d), final: d });
      }
    }
    prev.current = next;
    if (!jobs.length || prefersReducedMotion()) return;
    const t0 = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - t0) / duration);
      const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      for (const j of jobs) {
        j.p.setAttribute("d", t >= 1 ? j.final : fill(j.tpl, j.a.map((x, i) => x + (j.b[i] - x) * e)));
      }
      raf.current = t < 1 ? requestAnimationFrame(step) : null;
    };
    for (const j of jobs) j.p.setAttribute("d", fill(j.tpl, j.a));
    raf.current = requestAnimationFrame(step);
    return () => {
      if (raf.current !== null) cancelAnimationFrame(raf.current);
      raf.current = null;
      for (const j of jobs) j.p.setAttribute("d", j.final);
    };
  }, [root, version, duration]);
}
