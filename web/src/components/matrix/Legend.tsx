"use client";

import { useTranslations } from "next-intl";
import { format } from "@/lib/format";
import { RAMPS, rgbCss, type Theme } from "@/lib/matrix/colour";
import s from "./matrix.module.css";

const gradient = (stops: readonly (readonly [number, number, number])[]) =>
  `linear-gradient(to right, ${stops.map((c) => rgbCss(c)).join(", ")})`;

/** Below this |value| (Rs crore) the inr format rounds to "0.0 crore", so the key says "less than" it. */
const TINY = 0.05;

export interface LegendProps {
  theme: Theme;
  /** Smallest and largest non-zero |net value| in the current view: the ends of the log scale. */
  domain: [number, number] | null;
}

/**
 * Colour key for the heat-map. The two scale ends are axis labels computed from the cells in view
 * (like chart ticks, they carry no status badge); every flow figure is in the info box and table.
 */
export function Legend({ theme, domain }: LegendProps) {
  const t = useTranslations("matrix.heatmap");
  const r = RAMPS[theme];
  return (
    <ul className={s.legend} aria-label={t("legendLabel")}>
      <li>
        <span className={s.ramp} style={{ background: gradient(r.pos) }} aria-hidden="true" />
        {t("legendPos")}
      </li>
      <li>
        <span className={s.ramp} style={{ background: gradient(r.neg) }} aria-hidden="true" />
        {t("legendNeg")}
      </li>
      <li>
        <span className={s.swatch} style={{ background: rgbCss(r.zeroNet) }} aria-hidden="true" />
        {t("legendZeroNet")}
      </li>
      <li>
        <span className={s.swatch} style={{ background: "transparent" }} aria-hidden="true" />
        {t("legendEmpty")}
      </li>
      {domain && (
        <li className={s.muted} data-testid="legend-scale">
          {domain[0] < TINY
            ? t("legendScaleTiny", { floor: format(TINY, "inr"), hi: format(domain[1], "inr") })
            : t("legendScale", { lo: format(domain[0], "inr"), hi: format(domain[1], "inr") })}
        </li>
      )}
    </ul>
  );
}
