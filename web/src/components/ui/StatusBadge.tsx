"use client";
import { useTranslations } from "next-intl";
import { useId, useState } from "react";
import { useConstraints, useMapTextLazy } from "@/data/hooks";
import type { Composition, Constraint, Label, TotalLabel } from "@/data/types";
import { CompositionBar } from "./CompositionBar";
import { Num } from "./Num";
import s from "./ui.module.css";

export type StatusBadgeProps = {
  /** total label from pinned.json (or a story/summary figure); null = no published total */
  total: TotalLabel | null;
  /** headline split label (for a single figure: its own label) */
  split: Label;
  composition?: Composition | null;
  /** what pins the total (constraint ids or "ts:F01"); the panel shows each as the published figure it is */
  pins?: string[];
  /** set when only the whole pair (with its other part) is pinned */
  pairPins?: string[];
  /**
   * The figure is ONE published or derived value (GDP, one year of a time series), not a
   * sum of SAM entries, so "is the sum held to a published figure?" does not apply and the
   * panel has no total line. Defaults to true when no composition, pins or pairPins are
   * given: a figure with no parts is not a sum. Aggregates always pass their composition.
   */
  single?: boolean;
  /** static: no disclosure (e.g. inside a list row that is itself a button) */
  compact?: boolean;
};

const EXPLAIN: Record<Label, string> = {
  official: "explainOfficial",
  derived: "explainDerived",
  estimated: "explainEstimated",
  balancing_set: "explainBalancing",
};

/**
 * The two-part label of PLAN §3.4: "Official total · split estimated", or the
 * split label alone when there is no published total. Activating the badge shows
 * what the label means, the composition, and the published figures that pin the
 * total (by their description, not by id).
 */
export function StatusBadge({ total, split, composition, pins, pairPins, single, compact }: StatusBadgeProps) {
  const t = useTranslations("common.status");
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const tone = total ?? split;
  const isSingle = single ?? (composition === undefined && pins === undefined && pairPins === undefined);
  const pieces =
    total === null ? [t(split)] : total === split ? [t(`total_${total}`)] : [t(`total_${total}`), t(`split_${split}`)];
  const text = pieces.join(t("badgeSep"));
  // the two parts are separate spans, so a narrow layout can stack them on two lines (the first screen at
  // 375 px) without shortening the words; the text content is the same either way
  const inner = (
    <>
      <span className={`${s.badgeDot} ${s[`dot_${split}`]}`} aria-hidden="true" />
      {pieces.length === 1 ? (
        <span>{text}</span>
      ) : (
        <span data-badge-text="">
          <span>{pieces[0]}</span>
          <span data-badge-sep="">{t("badgeSep")}</span>
          <span>{pieces[1]}</span>
        </span>
      )}
    </>
  );
  if (compact) {
    return (
      <span className={`${s.badge} ${s[`st_${tone}`]}`} data-status-total={total ?? ""} data-status-split={split}>
        {inner}
      </span>
    );
  }
  const ownPins = pins && pins.length > 0 ? pins : null;
  const sharedPins = !ownPins && pairPins && pairPins.length > 0 ? pairPins : null;
  const shownPins = ownPins ?? sharedPins;
  return (
    <span className={s.badgeWrap}>
      <button
        type="button"
        className={`${s.badge} ${s[`st_${tone}`]}`}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={`${text}. ${t("details")}`}
        data-status-total={total ?? ""}
        data-status-split={split}
        onClick={() => setOpen((o) => !o)}
      >
        {inner}
      </button>
      <span id={panelId} className={s.badgePanel} hidden={!open} role="note" data-badge-kind={isSingle ? "single" : "aggregate"}>
        {!isSingle && <span className={s.badgeLine}>{t("aggregateNote")}</span>}
        <span className={isSingle ? s.badgeLineLast : s.badgeLine}>{t(EXPLAIN[split])}</span>
        {composition && (
          <span className={s.badgeLine}>
            <strong>{t("composition")}</strong>
            <CompositionBar composition={composition} />
          </span>
        )}
        {!isSingle && (
          <span className={s.badgeLineLast} data-badge-total="">
            {ownPins ? t("pinnedBy") : sharedPins ? t("pairPinnedBy") : t("noTotal")}
          </span>
        )}
        {!isSingle && open && shownPins && <PinList pins={shownPins} />}
      </span>
    </span>
  );
}

/** Half-width of a pin's tolerance around its target (null when it has no bounds). */
function tolerance(c: Constraint): number | null {
  if (c.lo === null && c.hi === null) return null;
  return Math.max(c.hi === null ? 0 : c.hi - c.target, c.lo === null ? 0 : c.target - c.lo);
}

/**
 * Each pin as the published figure it is (PLAN §3.4.2: "Held to NAS Statement 1.14 PFCE
 * within ₹1 crore"): a constraint by its description, target and tolerance from
 * sam/constraints.json; a time-series pin ("ts:F01") by the series' name. Loaded only when
 * the panel opens. If a file fails to load, the panel says so and shows the ids instead.
 */
function PinList({ pins }: { pins: string[] }) {
  const t = useTranslations("common.status");
  const needConstraints = pins.some((p) => !p.startsWith("ts:"));
  const needSeries = pins.some((p) => p.startsWith("ts:"));
  const cons = useConstraints(needConstraints);
  const text = useMapTextLazy(needSeries);
  if ((needConstraints && cons.loading) || (needSeries && text.loading)) {
    return <span className={s.badgeLineLast}>{t("pinsLoading")}</span>;
  }
  const failed = [needConstraints && cons.error ? "sam/constraints.json" : null, needSeries && text.error ? "map-text.json" : null].filter(
    (f): f is string => f !== null,
  );
  return (
    <>
      {failed.length > 0 && (
        <span className={s.badgeLineLast} data-pins-error="">
          {t("pinsError", { files: failed.join(", ") })}
        </span>
      )}
      <span className={s.pinList} role="list">
        {pins.map((id) => {
          if (id.startsWith("ts:")) {
            const sid = id.slice(3);
            const name = text.data?.series[sid]?.label;
            return (
              <span key={id} role="listitem" data-pin={id}>
                {name ? t("pinSeries", { name, id: sid }) : t("pinSeriesId", { id: sid })}
              </span>
            );
          }
          const c = cons.data?.[id];
          if (!c) {
            if (cons.data) console.error(`[StatusBadge] pin ${id} is not in sam/constraints.json`);
            return (
              <span key={id} role="listitem" data-pin={id}>
                {t("pinUnknown", { id })}
              </span>
            );
          }
          const tol = tolerance(c);
          return (
            <span key={id} role="listitem" data-pin={id}>
              {c.description.replace(/\.$/, "")}.{" "}
              {tol === null
                ? t.rich("pinTarget", { target: () => <Num value={c.target} fmt="inr" /> })
                : t.rich("pinTargetTol", {
                    target: () => <Num value={c.target} fmt="inr" />,
                    tol: () => <Num value={tol} fmt="inr" />,
                  })}
            </span>
          );
        })}
      </span>
    </>
  );
}
