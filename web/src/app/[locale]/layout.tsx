import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import { hasLocale } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { AppShell } from "@/components/ui/AppShell";
import { IntlClient } from "@/components/ui/IntlClient";
import { THEME_HEAD_SCRIPT } from "@/components/ui/theme-script";
import { DataIndexProvider } from "@/data/index-data";
import { clientDataIndex, loadIndex } from "@/data/server";
import { routing } from "@/i18n/routing";
import "@/styles/globals.css";

type Props = { children: ReactNode; params: Promise<{ locale: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({ params }: Omit<Props, "children">): Promise<Metadata> {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "common.site" });
  // Social images need an absolute URL; SITE_URL is set for a real deployment only.
  const site = process.env.SITE_URL;
  return {
    ...(site ? { metadataBase: new URL(site) } : {}),
    title: { default: t("title"), template: `%s · ${t("shortTitle")}` },
    description: t("description"),
    icons: { icon: "/favicon.svg" },
    openGraph: { title: t("title"), description: t("description"), type: "website", ...(site ? { images: ["/og.png"] } : {}) },
  };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fbfaf7" },
    { media: "(prefers-color-scheme: dark)", color: "#121317" },
  ],
};

export default async function LocaleLayout({ children, params }: Props) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);
  const index = loadIndex();
  return (
    <html lang={locale} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_HEAD_SCRIPT }} />
      </head>
      <body>
        <IntlClient>
          <DataIndexProvider value={clientDataIndex()}>
            <AppShell index={index} locale={locale}>
              {children}
            </AppShell>
          </DataIndexProvider>
        </IntlClient>
        {/* Cloudflare Web Analytics (cookieless): only in a real deployment build, when CF_BEACON_TOKEN is set. */}
        {process.env.CF_BEACON_TOKEN && (
          <script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon={JSON.stringify({ token: process.env.CF_BEACON_TOKEN })} />
        )}
      </body>
    </html>
  );
}
