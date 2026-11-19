import type { ReactNode } from "react";

// PLAN §4.12: the root layout is a pass-through; <html> lives in app/[locale]/layout.tsx
// (and in app/not-found.tsx and app/page.tsx, which render outside any locale).
export default function RootLayout({ children }: { children: ReactNode }) {
  return children;
}
