"use client";

import { useTranslations } from "next-intl";
import type { AxisState, HierIndex, ZoomState } from "@/lib/matrix/axes";
import { axisTrail } from "@/lib/matrix/axes";
import s from "./matrix.module.css";

export interface ZoomBarProps {
  ix: HierIndex;
  zoom: ZoomState;
  nRows: number;
  nCols: number;
  label: (id: string) => string;
  /** Set one axis (breadcrumb click). */
  onAxis: (axis: "rows" | "cols", next: AxisState) => void;
  onGrain: (grain: "children" | "accounts") => void;
  onZoomOut: () => void;
  onReset: () => void;
  canZoomOut: boolean;
  /** The root grain the reset goes to (accounts on wide screens, groups on phones). */
  rootGrain: "children" | "accounts";
}

function AxisCrumbs({
  name,
  axis,
  state,
  ix,
  label,
  onAxis,
  rootGrain,
}: {
  name: string;
  axis: "rows" | "cols";
  state: AxisState;
  ix: HierIndex;
  label: (id: string) => string;
  onAxis: ZoomBarProps["onAxis"];
  rootGrain: ZoomBarProps["rootGrain"];
}) {
  const t = useTranslations("matrix.zoom");
  const trail = axisTrail(ix, state);
  const nAccounts = ix.matrixOrder.length;
  const rootText =
    state.parent === null
      ? `${t("whole")} (${state.grain === "accounts" ? t("grainAccounts", { n: nAccounts }) : t("grainGroups", { n: ix.roots.length })})`
      : t("whole");
  return (
    <div className={s.axisRow}>
      <span className={s.axisName}>{name}</span>
      <nav aria-label={name}>
        <ol className={s.crumbs}>
          <li>
            {trail.length === 0 ? (
              <span className={s.crumbCurrent} aria-current="location">
                {rootText}
              </span>
            ) : (
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => onAxis(axis, { parent: null, grain: rootGrain })}
                aria-label={t("axisUp", { name: t("whole") })}
              >
                {rootText}
              </button>
            )}
          </li>
          {trail.map((id, k) => (
            <li key={id}>
              {k === trail.length - 1 ? (
                <span className={s.crumbCurrent} aria-current="location">
                  {label(id)}
                </span>
              ) : (
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => onAxis(axis, { parent: id, grain: "children" })}
                  aria-label={t("axisUp", { name: label(id) })}
                >
                  {label(id)}
                </button>
              )}
            </li>
          ))}
        </ol>
      </nav>
    </div>
  );
}

export function ZoomBar(p: ZoomBarProps) {
  const t = useTranslations("matrix.zoom");
  const atRoot = p.zoom.rows.parent === null && p.zoom.cols.parent === null;
  const grain = p.zoom.rows.grain === "accounts" && p.zoom.cols.grain === "accounts" ? "accounts" : "children";
  return (
    <div className={s.zoombar}>
      <h2>{t("heading")}</h2>
      <AxisCrumbs name={t("rows")} axis="rows" state={p.zoom.rows} ix={p.ix} label={p.label} onAxis={p.onAxis} rootGrain={p.rootGrain} />
      <AxisCrumbs name={t("cols")} axis="cols" state={p.zoom.cols} ix={p.ix} label={p.label} onAxis={p.onAxis} rootGrain={p.rootGrain} />
      <p className={s.muted} style={{ margin: 0 }}>
        {t("size", { rows: p.nRows, cols: p.nCols })}
      </p>
      <div className={s.zoomActions}>
        {atRoot && (
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => p.onGrain(grain === "accounts" ? "children" : "accounts")}
          >
            {grain === "accounts" ? t("showGroups") : t("showAccounts")}
          </button>
        )}
        <button type="button" className="btn btn-sm" onClick={p.onZoomOut} disabled={!p.canZoomOut}>
          {t("zoomOut")}
        </button>
        <button type="button" className="btn btn-sm" onClick={p.onReset} disabled={!p.canZoomOut && atRoot}>
          {t("reset")}
        </button>
      </div>
    </div>
  );
}
