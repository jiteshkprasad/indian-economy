import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { DataExplorer, Downloads } from "@/components/matrix";
import s from "@/components/matrix/matrix.module.css";
import { IntlClient } from "@/components/ui/IntlClient";
import { aggregate, visibleNodes } from "@/data/aggregate";
import {
  clientDataIndex,
  loadCells,
  loadHierarchy,
  loadIndex,
  loadMapText,
  loadPinned,
  loadSummary,
} from "@/data/server";
import type { Hierarchy, MapText } from "@/data/types";
import { Link } from "@/i18n/navigation";

type Props = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "matrix.meta" });
  return { title: t("title"), description: t("description") };
}

/** One display label per hierarchy node. A missing label fails the build (no silent fallback). */
function nodeLabels(h: Hierarchy, text: MapText): Record<string, string> {
  const out: Record<string, string> = {};
  const missing: string[] = [];
  for (const n of h.nodes) {
    const l = text.nodes[n.id]?.label;
    if (l) out[n.id] = l;
    else missing.push(n.id);
  }
  if (missing.length > 0) {
    throw new Error(`data page: map-text.json has no label for ${missing.length} node(s): ${missing.join(", ")}`);
  }
  return out;
}

export default async function DataPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("matrix.page");
  const index = loadIndex();
  const client = clientDataIndex();
  const summary = loadSummary();
  const hierarchy = loadHierarchy();
  const cells = loadCells();
  const pinned = loadPinned();
  const labels = nodeLabels(hierarchy, loadMapText(locale));
  // level-0 links of the full preset: the ones that have a /flow/<id>/ permalink page
  const flowIds = aggregate(cells, hierarchy, visibleNodes(hierarchy, "full"), pinned).links.map((l) => l.id);
  const year = summary.gdp.year;

  return (
    <div className={`container ${s.page}`}>
      <div className={s.intro}>
        <h1>{t("h1", { year })}</h1>
        <p>{t("intro", { year })}</p>
        <p>{t("units", { year })}</p>
        <p>{t("gdpNote", { year })}</p>
        <p>
          <Link href="/methodology/#status">{t("methodLink")}</Link>
          {" · "}
          <Link href="/">{t("mapLink")}</Link>
        </p>
      </div>
      <IntlClient namespaces={["matrix"]}>
        <DataExplorer
          hierarchy={hierarchy}
          cells={cells}
          pinned={pinned}
          gdp={summary.gdp.value}
          year={year}
          labels={labels}
          flowIds={flowIds}
        />
      </IntlClient>
      <Downloads base={client.base} dataVersion={index.data_version} fixture={index.fixture} files={index.files} />
    </div>
  );
}
