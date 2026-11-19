"use client";
import { useId, useState, type ReactNode } from "react";
import s from "./ui.module.css";

/** A button that shows and hides a region (WAI-ARIA disclosure pattern). */
export function Disclosure({
  summary,
  children,
  defaultOpen = false,
  onToggle,
}: {
  summary: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  onToggle?: (open: boolean) => void;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <div>
      <button
        type="button"
        className={s.disclosureBtn}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => {
          setOpen(!open);
          onToggle?.(!open);
        }}
      >
        {summary}
      </button>
      <div id={id} hidden={!open}>
        {children}
      </div>
    </div>
  );
}
