"use client";
import { useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import s from "./ui.module.css";

export type TabItem = { id: string; label: ReactNode; panel: ReactNode };

/** WAI-ARIA tabs with automatic activation: ←/→ move, Home/End jump. Controlled. */
export function Tabs({
  items,
  selected,
  onSelect,
  label,
}: {
  items: TabItem[];
  selected: string;
  onSelect: (id: string) => void;
  label: string;
}) {
  const base = useId();
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const idx = Math.max(
    0,
    items.findIndex((i) => i.id === selected),
  );
  const move = (to: number) => {
    const it = items[(to + items.length) % items.length];
    onSelect(it.id);
    refs.current[it.id]?.focus();
  };
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "ArrowRight") move(idx + 1);
    else if (e.key === "ArrowLeft") move(idx - 1);
    else if (e.key === "Home") move(0);
    else if (e.key === "End") move(items.length - 1);
    else return;
    e.preventDefault();
  };
  return (
    <div>
      <div role="tablist" aria-label={label} className={s.tablist} onKeyDown={onKey}>
        {items.map((it) => (
          <button
            key={it.id}
            ref={(el) => {
              refs.current[it.id] = el;
            }}
            role="tab"
            type="button"
            id={`${base}-tab-${it.id}`}
            aria-selected={it.id === items[idx].id}
            aria-controls={`${base}-panel-${it.id}`}
            tabIndex={it.id === items[idx].id ? 0 : -1}
            className={s.tab}
            onClick={() => onSelect(it.id)}
          >
            {it.label}
          </button>
        ))}
      </div>
      {items.map((it) => (
        <div
          key={it.id}
          role="tabpanel"
          id={`${base}-panel-${it.id}`}
          aria-labelledby={`${base}-tab-${it.id}`}
          hidden={it.id !== items[idx].id}
          tabIndex={0}
          className={s.tabpanel}
        >
          {it.id === items[idx].id ? it.panel : null}
        </div>
      ))}
    </div>
  );
}
