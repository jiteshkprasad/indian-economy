import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";

// Rendered inside the [locale] layout when a page calls notFound().
export default async function LocaleNotFound() {
  const t = await getTranslations({ locale: routing.defaultLocale, namespace: "common.notFound" });
  return (
    <div className="container">
      <h1>{t("title")}</h1>
      <p>{t("body")}</p>
      <p>
        <Link className="btn" href="/">
          {t("home")}
        </Link>
      </p>
    </div>
  );
}
