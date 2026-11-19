import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { Num } from "@/components/ui";
import type { Summary } from "@/data/types";
import { HeroTour, type TourData } from "./HeroTour";
import s from "./home.module.css";

export type HeroProps = {
  summary: Summary;
  /** number of official sources the site cites (provenance.json) */
  sources: number;
  tours: TourData[];
};

/** Financial years from "1950-51" to "2025-26", both included. */
function yearCount(first: string, last: string): number {
  return Number(last.slice(0, 4)) - Number(first.slice(0, 4)) + 1;
}

/**
 * The first screen (round 3): what this project is, the proof that it is the whole economy, and
 * the map itself, playable at once. Every number comes from summary.json or provenance.json.
 */
export async function Hero({ summary, sources, tours }: HeroProps) {
  const t = await getTranslations("map.hero");
  const sam = summary.sam;
  const official = sam.labels.official.abs / Object.values(sam.labels).reduce((a, l) => a + l.abs, 0);
  const proof: Array<{ key: "accounts" | "flows" | "sources" | "years"; value: number; text: string }> = [
    { key: "accounts", value: sam.accounts, text: t("proof.accounts") },
    { key: "flows", value: sam.entries, text: t("proof.flows") },
    { key: "sources", value: sources, text: t("proof.sources") },
    { key: "years", value: yearCount(summary.ts.first, summary.ts.last), text: t("proof.years", { first: summary.ts.first, last: summary.ts.last }) },
  ];
  return (
    <section className={s.hero} aria-labelledby="first-h1" data-hero="">
      <h1 id="first-h1" className={s.h1}>
        {t("h1")}
      </h1>
      <p className={s.sub}>{t("sub", { year: summary.gdp.year })}</p>
      <ul className={s.proof} aria-label={t("label")} data-proof="">
        {proof.map((p) => (
          <li key={p.key} data-proof-item={p.key}>
            <Num value={p.value} fmt="count" className={s.proofNum} /> <span className={s.proofLong}>{p.text}</span>
            <span className={s.proofShort}>{t(`proofShort.${p.key}`)}</span>
          </li>
        ))}
      </ul>
      <p className={s.proofNote}>
        {sam.balancing.max_imbalance === 0 && <>{t("proof.balanced")} </>}
        <Num value={official} fmt="pct" className={s.proofInline} /> {t("proof.official")}{" "}
        <Link href="/gaps/">{t("honest")}</Link>
      </p>
      <HeroTour tours={tours} />
    </section>
  );
}
