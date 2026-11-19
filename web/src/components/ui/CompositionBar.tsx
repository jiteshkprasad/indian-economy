"use client";
import { useTranslations } from "next-intl";
import { formatPct } from "@/lib/format";
import type { Composition, Label } from "@/data/types";
import s from "./ui.module.css";

const ORDER: Array<[keyof Composition, Label]> = [
  ["o", "official"],
  ["d", "derived"],
  ["e", "estimated"],
  ["b", "balancing_set"],
];

/**
 * Shares of an aggregate's absolute value by entry label (PLAN §3.4.2). Patterns
 * (hatch = estimated, cross-hatch = set by balancing) so colour is not the only
 * signal; the legend states every share in text.
 */
export function CompositionBar({ composition, legend = true }: { composition: Composition; legend?: boolean }) {
  const t = useTranslations("common.status");
  const parts = ORDER.filter(([k]) => composition[k] > 0);
  const text = parts.map(([k, label]) => t("compositionItem", { label: t(label), share: formatPct(composition[k]) })).join(", ");
  return (
    <span className={s.comp}>
      <span className={s.compBar} role="img" aria-label={`${t("composition")}: ${text}`}>
        {parts.map(([k, label]) => (
          <span key={k} className={`${s.compSeg} ${s[`seg_${label}`]}`} style={{ width: `${composition[k] * 100}%` }} />
        ))}
      </span>
      {legend && (
        <ul className={s.compLegend} aria-hidden="true">
          {parts.map(([k, label]) => (
            <li key={k}>
              <span className={`${s.compKey} ${s[`seg_${label}`]}`} />
              {t("compositionItem", { label: t(label), share: formatPct(composition[k]) })}
            </li>
          ))}
        </ul>
      )}
    </span>
  );
}
