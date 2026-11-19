"use client";

import { useCallback, useEffect, useState } from "react";
import { parseCssColour, themeFromBackground, type Theme } from "@/lib/matrix/colour";

export interface CanvasTheme {
  theme: Theme;
  block: string;
  grid: string;
  text: string;
  halo: string;
  focus: string;
}

/** Light or dark ramp from the resolved page background; follows the theme toggle and the OS. */
export function useCanvasTheme(): CanvasTheme {
  const read = useCallback(() => {
    const cs = getComputedStyle(document.documentElement);
    const v = (name: string, dflt: string) => cs.getPropertyValue(name).trim() || dflt;
    const bg = parseCssColour(v("--bg", "")) ?? parseCssColour(getComputedStyle(document.body).backgroundColor);
    const theme = themeFromBackground(bg);
    return {
      theme,
      block: v("--text-muted", theme === "dark" ? "#b0b0b0" : "#555555"),
      grid: v("--border", theme === "dark" ? "#333333" : "#dddddd"),
      text: v("--text", theme === "dark" ? "#f0f0f0" : "#111111"),
      halo: v("--bg", theme === "dark" ? "#111111" : "#ffffff"),
      focus: v("--focus", theme === "dark" ? "#7cc4ff" : "#0050b3"),
    };
  }, []);
  const [state, setState] = useState<CanvasTheme>(() => ({
    theme: "light",
    block: "#555555",
    grid: "#dddddd",
    text: "#111111",
    halo: "#ffffff",
    focus: "#0050b3",
  }));
  useEffect(() => {
    const update = () => setState(read());
    update();
    const mo = new MutationObserver(update);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class", "style"] });
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", update);
    return () => {
      mo.disconnect();
      mq.removeEventListener("change", update);
    };
  }, [read]);
  return state;
}

