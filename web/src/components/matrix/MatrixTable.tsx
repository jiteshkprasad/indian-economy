"use client";

import { useTranslations } from "next-intl";
import { forwardRef } from "react";
import { Num } from "@/components/ui/Num";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { cellFacts } from "@/lib/matrix/describe";
import type { Grid } from "@/lib/matrix/grid";
import type { MatrixPinned } from "@/lib/matrix/types";
import s from "./matrix.module.css";

export interface MatrixTableProps {
  grid: Grid;
  label: (id: string) => string;
  pinned: MatrixPinned;
  gdp: number;
  year: string;
  /** Set when the heat-map shows accounts but this table shows their blocks. */
  groupedFrom: number | null;
}

/**
 * The accessible alternative to the heat-map (PLAN §4.8): an HTML table of the current zoom
 * matrix with <th scope> headers. Rows receive, columns pay. Empty cells show "·".
 */
export const MatrixTable = forwardRef<HTMLDivElement, MatrixTableProps>(function MatrixTable(p, ref) {
  const t = useTranslations("matrix.table");
  const g = p.grid;
  return (
    <div ref={ref} className={s.tableRegion} role="region" aria-label={t("region")} tabIndex={0}>
      <table className={s.matrixTable} data-testid="matrix-table" data-rows={g.nR} data-cols={g.nC}>
        <caption>
          {t("caption", { year: p.year, rows: g.nR, cols: g.nC })}
          {p.groupedFrom !== null && <> {t("captionBlocks", { n: Math.max(g.nR, g.nC) })}</>}
        </caption>
        <thead>
          <tr>
            <td>{t("corner")}</td>
            {g.cols.map((c) => (
              <th key={c.id} scope="col">
                {p.label(c.id)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {g.rows.map((r, i) => (
            <tr key={r.id}>
              <th scope="row">{p.label(r.id)}</th>
              {g.cols.map((c, j) => {
                const f = cellFacts(g, i, j, p.pinned, p.gdp);
                if (f.empty || f.split === null) {
                  return (
                    <td key={c.id} className={s.zeroCell}>
                      <span aria-hidden="true">{t("zero")}</span>
                      <span className="visually-hidden">{t("zeroLabel")}</span>
                    </td>
                  );
                }
                return (
                  <td key={c.id} data-cell={`${c.id}--${r.id}`}>
                    <Num value={f.v} fmt="inr" />
                    <span className={s.badgeLine}>
                      <StatusBadge total={f.total} split={f.split} composition={f.composition} pins={f.pins} compact />
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
});
