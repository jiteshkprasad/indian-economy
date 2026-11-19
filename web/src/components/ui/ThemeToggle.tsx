"use client";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { THEME_STORAGE_KEY as KEY } from "./theme-script";
import s from "./ui.module.css";

export type ThemeChoice = "system" | "light" | "dark";
const NEXT: Record<ThemeChoice, ThemeChoice> = { system: "light", light: "dark", dark: "system" };

export function readStoredTheme(): ThemeChoice {
  try {
    const v = window.localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(choice: ThemeChoice): void {
  const el = document.documentElement;
  if (choice === "system") el.removeAttribute("data-theme");
  else el.setAttribute("data-theme", choice);
  try {
    if (choice === "system") window.localStorage.removeItem(KEY);
    else window.localStorage.setItem(KEY, choice);
  } catch {
    // storage blocked: the choice still applies for this page view
  }
}

// The head script lives in ./theme-script.ts (a plain module), not here: see the note there.

/** Cycles automatic → light → dark. The label is the current state; server HTML shows "automatic". */
export function ThemeToggle() {
  const t = useTranslations("common.theme");
  const [choice, setChoice] = useState<ThemeChoice>("system");
  useEffect(() => {
    // Sync with what the head script applied before hydration.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setChoice(readStoredTheme());
  }, []);
  const short = t(`${choice}Short`);
  return (
    <button
      type="button"
      className={`btn ${s.themeToggle}`}
      data-theme-toggle=""
      data-theme-choice={choice}
      aria-label={t("switchTo", { current: t(choice) })}
      onClick={() => {
        const next = NEXT[choice];
        applyTheme(next);
        setChoice(next);
      }}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M12 3a9 9 0 1 0 0 18z" fill="currentColor" />
        <circle cx="12" cy="12" r="8.25" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
      <span className={s.themeText}>{short}</span>
    </button>
  );
}
