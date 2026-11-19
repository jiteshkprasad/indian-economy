"use client";
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

type Announce = (message: string) => void;
const Ctx = createContext<Announce | null>(null);

/**
 * A polite live region. Wrap a page section in <LiveRegionProvider> and call
 * useAnnounce()(text) on manual user actions only (PLAN §2.1 item 2).
 * Repeating the same text re-announces it.
 */
export function LiveRegionProvider({ children }: { children: ReactNode }) {
  const [msg, setMsg] = useState("");
  const flip = useRef(false);
  const announce = useCallback<Announce>((m) => {
    flip.current = !flip.current;
    // A trailing no-break space toggles so identical messages are announced again.
    setMsg(flip.current ? m : `${m} `);
  }, []);
  return (
    <Ctx.Provider value={announce}>
      {children}
      <LiveRegion message={msg} />
    </Ctx.Provider>
  );
}

export function useAnnounce(): Announce {
  const a = useContext(Ctx);
  if (!a) throw new Error("useAnnounce: no <LiveRegionProvider> above this component");
  return a;
}

/** A visually hidden aria-live region showing `message`. */
export function LiveRegion({ message, politeness = "polite" }: { message: string; politeness?: "polite" | "assertive" }) {
  return (
    <div className="visually-hidden" aria-live={politeness} aria-atomic="true" data-live-region="">
      {message}
    </div>
  );
}
