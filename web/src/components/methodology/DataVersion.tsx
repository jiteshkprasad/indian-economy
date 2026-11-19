import { getTranslations } from "next-intl/server";
import type { DataIndex } from "@/data/types";
import s from "./methodology.module.css";

/**
 * The data version this page was built from, its inputs and code hash, and the
 * commands that reproduce it (PLAN §4.10 item 7). Everything shown comes from
 * index.json; the commands are message strings.
 */
export async function DataVersion({ index, locale }: { index: DataIndex; locale: string }) {
  const t = await getTranslations({ locale, namespace: "methodology.version" });
  const inputs = Object.entries(index.inputs).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  const files = Object.keys(index.files).length;
  return (
    <div data-data-version={index.data_version}>
      {index.fixture && (
        <p className={s.fixtureWarning} role="note">
          {t("fixture")}
        </p>
      )}
      <dl className={s.versionDl}>
        <dt>{t("version")}</dt>
        <dd>
          <code>{index.data_version}</code>
        </dd>
        <dt>{t("referenceYear")}</dt>
        <dd>{index.reference_year}</dd>
        <dt>{t("baseYear")}</dt>
        <dd>{index.gdp_base_year}</dd>
        <dt>{t("vintage")}</dt>
        <dd>{t("vintageValue")}</dd>
        <dt>{t("files")}</dt>
        <dd>{t("filesValue", { count: files })}</dd>
        <dt>{t("codeHash")}</dt>
        <dd>
          <code className={s.hash}>{index.export_code_hash}</code>
        </dd>
      </dl>

      <h3>{t("commandsHeading")}</h3>
      <p>{t("commandsIntro")}</p>
      <pre className={s.commands}>
        <code>{t("commands")}</code>
      </pre>

      <details className={s.inputs}>
        <summary>{t("inputsSummary", { count: inputs.length })}</summary>
        <ul className={s.inputList}>
          {inputs.map(([p, sha]) => (
            <li key={p}>
              <code className={s.inputPath}>{p}</code>
              <code className={s.hash}>{sha}</code>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
