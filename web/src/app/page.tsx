import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { routing } from "@/i18n/routing";
import "@/styles/globals.css";

// `/` -> `/en/`. On Vercel, vercel.json answers with a 308 before this page is
// served; this static page is the fallback for other hosts (meta refresh, plus a link).
const target = `/${routing.defaultLocale}/`;

export const metadata: Metadata = {
  title: "India's Economy as a Working Model",
  robots: { index: false },
};

export default async function RootPage() {
  const t = await getTranslations({ locale: routing.defaultLocale, namespace: "common.redirect" });
  return (
    <html lang={routing.defaultLocale}>
      <head>
        <meta httpEquiv="refresh" content={`0; url=${target}`} />
        <link rel="canonical" href={target} />
      </head>
      <body>
        <main className="container" id="main">
          <h1>{t("title")}</h1>
          <p>{t("body")}</p>
          <p>
            <a href={target}>{t("link")}</a>
          </p>
        </main>
      </body>
    </html>
  );
}
