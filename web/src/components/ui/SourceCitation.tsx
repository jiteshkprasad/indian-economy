"use client";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { Provenance } from "@/data/types";
import { mergeCites, type MergedCite } from "./cites";
import s from "./ui.module.css";

const RBI_HOST = /(^|\.)rbi\.org\.in$/i;

function hostOf(u: string): string {
  try {
    return new URL(u).hostname;
  } catch {
    return "";
  }
}

/** "host: file" so that several links to one publisher read differently (2.4.4). */
function linkLabel(u: string): string {
  try {
    const url = new URL(u);
    const seg = url.pathname.split("/").filter(Boolean).pop();
    if (!seg) return url.hostname;
    let name = seg;
    try {
      name = decodeURIComponent(seg);
    } catch {
      // keep the raw segment
    }
    return `${url.hostname}: ${name.length > 48 ? `${name.slice(0, 45)}…` : name}`;
  } catch {
    return u;
  }
}

/**
 * Citations for a figure (PLAN §3.5, §4.7 item 5): the top `limit` sources, then
 * "All N sources". Withheld sources (RBI until permission) show name, table and
 * retrieval date with no link; a URL on an RBI host is never rendered as a link
 * even if the data were wrong.
 */
export function SourceCitation({
  provIds,
  provenance,
  weights,
  limit = 5,
  headingLevel = 3,
}: {
  provIds: readonly string[];
  provenance: Provenance;
  weights?: Record<string, number>;
  limit?: number;
  headingLevel?: 2 | 3 | 4;
}) {
  const t = useTranslations("common.sources");
  const [all, setAll] = useState(false);
  const cites = mergeCites(provIds, provenance.records, weights);
  const shown = all ? cites : cites.slice(0, limit);
  const H = `h${headingLevel}` as "h2" | "h3" | "h4";
  return (
    <section aria-label={t("heading")} data-sources="">
      <H>{t("heading")}</H>
      {cites.length === 0 ? (
        <p>{t("none")}</p>
      ) : (
        <ul className={s.sources}>
          {shown.map((c) => (
            <CiteItem key={c.source} cite={c} provenance={provenance} />
          ))}
        </ul>
      )}
      {cites.length > limit && (
        <button type="button" className="btn btn-sm" aria-expanded={all} onClick={() => setAll(!all)}>
          {all ? t("showFewer") : t("showAll", { count: cites.length })}
        </button>
      )}
    </section>
  );
}

function CiteItem({ cite, provenance }: { cite: MergedCite; provenance: Provenance }) {
  const t = useTranslations("common.sources");
  const src = provenance.sources[cite.source];
  const name = src?.name ?? cite.source;
  const mode = src?.link_mode ?? "deep";
  const withheld = cite.withheld || mode === "withheld";
  const [from, to] = cite.retrieved;
  const links: Array<{ href: string; label: string }> = [];
  if (!withheld) {
    if (mode === "landing") {
      if (src?.landing) links.push({ href: src.landing, label: t("landing") });
    } else {
      // a cite can list the same URL more than once (several tables in one file): link it once
      const seen = new Set<string>();
      for (const u of cite.urls) {
        if (!u || seen.has(u) || RBI_HOST.test(hostOf(u))) continue;
        seen.add(u);
        links.push({ href: u, label: linkLabel(u) });
      }
    }
  }
  return (
    <li data-source={cite.source} data-link-mode={withheld ? "withheld" : mode}>
      <div className={s.sourceName}>{name}</div>
      <div className={s.sourceMeta}>
        {src?.publisher && <span>{src.publisher}. </span>}
        {cite.tables.length > 0 && <span>{t("table", { tables: cite.tables.join(", ") })}. </span>}
        {from && <span>{!to || from === to ? t("retrieved", { date: from }) : t("retrievedRange", { from, to })}.</span>}
      </div>
      {withheld ? (
        <div className={s.withheld}>{t("withheld")}</div>
      ) : links.length > 0 ? (
        <div>
          {links.slice(0, 3).map((l) => (
            <a key={l.href} className={s.sourceLink} href={l.href} rel="noopener noreferrer" target="_blank">
              {l.label}
            </a>
          ))}
        </div>
      ) : (
        <div className={s.sourceMeta}>{t("noUrl")}</div>
      )}
    </li>
  );
}
