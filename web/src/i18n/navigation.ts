import { createElement, type ComponentProps } from "react";
import { createNavigation } from "next-intl/navigation";
import { routing } from "./routing";

// Locale-aware Link and helpers. Use these instead of next/link inside [locale].
const nav = createNavigation(routing);
export const { getPathname, usePathname, useRouter } = nav;

/**
 * The locale-aware Link, with Next's viewport prefetch OFF unless a caller passes
 * `prefetch`. On a static export every prefetch downloads the target's whole RSC
 * payload: on /en/ the header, story-card and footer links fetched about 300 KB gzipped
 * (1.7 MB raw) on first view, more than the 200 KB first-load JS budget (verify V4-04).
 * A click fetches the one payload it needs.
 */
export function Link(props: ComponentProps<typeof nav.Link>) {
  return createElement(nav.Link, { prefetch: false, ...props });
}
