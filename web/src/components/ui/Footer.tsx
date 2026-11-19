import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import type { DataIndex } from "@/data/types";
import s from "./ui.module.css";

export async function Footer({ index, locale }: { index: DataIndex; locale: string }) {
  const t = await getTranslations({ locale, namespace: "common" });
  return (
    <footer className={s.footer}>
      <div className="container">
        {index.fixture && (
          <p className={s.fixtureNote} data-fixture-banner="">
            {t("footer.fixture")}
          </p>
        )}
        <p>{t.rich("footer.attribution", { link: (c) => <a href="https://jiteshkprasad.com">{c}</a> })}</p>
        <p>
          {t("footer.referenceYear", { year: index.reference_year, base: index.gdp_base_year })}.{" "}
          <span data-data-version={index.data_version}>{t("footer.dataVersion", { version: index.data_version })}</span>.{" "}
          <Link href="/methodology/#data-version" prefetch={false}>{t("footer.methodologyLink")}</Link>
        </p>
        <p>{t("footer.rechecked")}.</p>
      </div>
    </footer>
  );
}
