import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { routing } from "@/i18n/routing";
import { THEME_HEAD_SCRIPT } from "@/components/ui/theme-script";
import "@/styles/globals.css";

// Root 404: static export writes out/404.html from this file. It renders outside
// any [locale] layout, so it has its own <html lang> and <body> (PLAN §4.12).
export const metadata: Metadata = { title: "Page not found · India's Economy as a Working Model" };

export default async function RootNotFound() {
  const locale = routing.defaultLocale;
  const t = await getTranslations({ locale, namespace: "common" });
  return (
    <html lang={locale} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_HEAD_SCRIPT }} />
      </head>
      <body>
        <main className="container" id="main">
          <p>
            <a href={`/${locale}/`}>{t("site.title")}</a>
          </p>
          <h1>{t("notFound.title")}</h1>
          <p>{t("notFound.body")}</p>
          <p>
            <a className="btn" href={`/${locale}/`}>
              {t("notFound.home")}
            </a>
          </p>
        </main>
      </body>
    </html>
  );
}
