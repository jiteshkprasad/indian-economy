import type { ReactNode } from "react";
import { getTranslations } from "next-intl/server";
import type { DataIndex } from "@/data/types";
import { Footer } from "./Footer";
import { Header } from "./Header";
import s from "./ui.module.css";

/** Skip link, header with navigation and theme toggle, <main id="main">, footer. */
export async function AppShell({ children, index, locale }: { children: ReactNode; index: DataIndex; locale: string }) {
  const t = await getTranslations({ locale, namespace: "common" });
  return (
    <>
      <a href="#main" className={s.skip}>
        {t("nav.skip")}
      </a>
      <Header />
      <main id="main" tabIndex={-1} className={s.main}>
        {children}
      </main>
      <Footer index={index} locale={locale} />
    </>
  );
}
