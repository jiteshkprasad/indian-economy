import { defineRouting } from "next-intl/routing";

// PLAN §4.12. Static export: no middleware; every page lives under /<locale>/.
export const routing = defineRouting({
  locales: ["en"],
  defaultLocale: "en",
  localePrefix: "always",
});

export type Locale = (typeof routing.locales)[number];

/** Message namespaces: one file per owner in messages/<locale>/<ns>.json (PLAN §3.9). */
export const NAMESPACES = ["common", "map", "matrix", "story", "methodology"] as const;
export type Namespace = (typeof NAMESPACES)[number];
