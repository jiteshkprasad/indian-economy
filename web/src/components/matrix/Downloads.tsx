// Download links to every JSON file in the data version, with size and SHA-256 from index.json
// (PLAN §4.8). A server component: it renders at build time and needs no JavaScript.

import { getTranslations } from "next-intl/server";
import s from "./matrix.module.css";

export interface DownloadsProps {
  base: string;
  dataVersion: string;
  fixture: boolean;
  files: Record<string, { sha256: string; bytes: number }>;
}

const kb = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const whole = new Intl.NumberFormat("en-IN");

export async function Downloads({ base, dataVersion, fixture, files }: DownloadsProps) {
  const t = await getTranslations("matrix.downloads");
  const paths = Object.keys(files).sort();
  const size = (bytes: number) =>
    bytes < 1024 ? t("bytes", { n: whole.format(bytes) }) : t("kb", { n: kb.format(bytes / 1024) });
  return (
    <section className={s.downloads} aria-labelledby="mx-downloads">
      <h2 id="mx-downloads">{t("heading")}</h2>
      <p>{t("intro", { version: dataVersion })}</p>
      {fixture && (
        <p role="note">
          <strong>{t("fixture")}</strong>
        </p>
      )}
      <p>
        <a href={`${base}/index.json`}>{t("index")}</a>
      </p>
      <div className={s.downloadsScroll}>
        <table data-testid="downloads">
          <thead>
            <tr>
              <th scope="col">{t("file")}</th>
              <th scope="col">{t("size")}</th>
              <th scope="col">{t("sha")}</th>
            </tr>
          </thead>
          <tbody>
            {paths.map((p) => (
              <tr key={p}>
                <td>
                  <a href={`${base}/${dataVersion}/${p}`}>{p}</a>
                </td>
                <td className="num">{size(files[p].bytes)}</td>
                <td className={s.sha}>{files[p].sha256}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
