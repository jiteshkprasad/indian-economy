"use client";
import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { ThemeToggle } from "./ThemeToggle";
import s from "./ui.module.css";

// Header links do not prefetch (verify V4-04; also the default of @/i18n/navigation's
// Link): Next's viewport prefetch fetched the RSC payload of every nav target on every
// page view (about 130 KB gzipped). A click fetches the one payload it needs.
// `short`: a shorter label for phones (< 640 px), so the header stays two short rows there
// and the first screen fits in 812 px (PLAN §4.0).
const NAV: Array<{ href: string; key: string; short?: string; match: (p: string) => boolean }> = [
  { href: "/", key: "map", match: (p) => p === "/" || p.startsWith("/flow") || p.startsWith("/series") },
  { href: "/story/", key: "stories", match: (p) => p.startsWith("/story") },
  { href: "/data/", key: "data", match: (p) => p.startsWith("/data") },
  { href: "/gaps/", key: "gaps", short: "gapsShort", match: (p) => p.startsWith("/gaps") },
  { href: "/methodology/", key: "methodology", short: "methodologyShort", match: (p) => p.startsWith("/methodology") },
];

export function Header() {
  const t = useTranslations("common");
  const pathname = usePathname() ?? "/";
  const path = pathname.replace(/\/+$/, "") || "/";
  return (
    <header className={s.header}>
      <div className={`container ${s.headerInner}`}>
        <Link href="/" className={s.brand} prefetch={false}>
          <span className={s.wide}>{t("site.title")}</span>
          <span className={s.narrow}>{t("site.shortTitle")}</span>
        </Link>
        <nav aria-label={t("nav.label")} className={s.nav}>
          <ul>
            {NAV.map((n) => (
              <li key={n.key}>
                <Link href={n.href} prefetch={false} aria-current={n.match(path) ? "page" : undefined}>
                  {n.short ? (
                    <>
                      <span className={s.wide}>{t(`nav.${n.key}`)}</span>
                      <span className={s.narrow}>{t(`nav.${n.short}`)}</span>
                    </>
                  ) : (
                    t(`nav.${n.key}`)
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <ThemeToggle />
      </div>
    </header>
  );
}
