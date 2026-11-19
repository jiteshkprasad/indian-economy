"use client";

import { useTranslations } from "next-intl";
import { CompositionBar } from "@/components/ui/CompositionBar";
import { Num } from "@/components/ui/Num";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Link } from "@/i18n/navigation";
import type { CellFacts } from "@/lib/matrix/describe";
import s from "./matrix.module.css";

export interface CellInfoProps {
  facts: CellFacts;
  label: (id: string) => string;
  /** True when Enter / the zoom button would show something deeper. */
  canZoom: boolean;
  onZoomIn: () => void;
  /** Zoom only the receivers (rows) or only the payers (columns) into this cell's block. */
  onZoomRows: { name: string; go: () => void } | null;
  onZoomCols: { name: string; go: () => void } | null;
  /** Level-0 flow permalink ids that exist for this cell (positive and/or negative part). */
  flowLinks: string[];
  /** "hover" while the pointer previews a cell; "cursor" for the selected one. */
  source: "hover" | "cursor";
}

export function CellInfo({ facts, label, canZoom, onZoomIn, onZoomRows, onZoomCols, flowLinks, source }: CellInfoProps) {
  const t = useTranslations("matrix.cell");
  const tz = useTranslations("matrix.zoom");
  const tf = useTranslations("matrix.flags");
  const payer = label(facts.payer);
  const receiver = label(facts.receiver);
  const title = facts.internal ? t("internal", { name: payer }) : t("pays", { payer, receiver });
  return (
    <section className={s.info} aria-label={t("heading")} data-cell={`${facts.payer}--${facts.receiver}`} data-source={source}>
      <h2>{t("heading")}</h2>
      <p>
        <strong>{title}</strong>
      </p>
      {facts.empty || facts.split === null ? (
        <p>{t("none", { payer, receiver })}</p>
      ) : (
        <>
          <dl className={s.facts}>
            <dt>{t("value")}</dt>
            <dd>
              <Num value={facts.v} fmt="inr" />
            </dd>
            <dt>{t("share")}</dt>
            <dd>
              <Num value={facts.share} fmt="pct_gdp" />
            </dd>
            <dt>{t("status")}</dt>
            <dd>
              <StatusBadge total={facts.total} split={facts.split} composition={facts.composition} pins={facts.pins} />
            </dd>
          </dl>
          {facts.pos > 0 && facts.neg < 0 && (
            <p className={s.muted} data-testid="net-of">
              {t.rich("netOf", {
                pos: () => <Num value={facts.pos} fmt="inr" />,
                neg: () => <Num value={facts.neg} fmt="inr" />,
              })}
            </p>
          )}
          {facts.composition && <CompositionBar composition={facts.composition} />}
          {facts.flags.length > 0 && (
            <ul className={s.flagList}>
              {facts.flags.map((f) => (
                <li key={f}>{tf(f)}</li>
              ))}
            </ul>
          )}
          <p className={s.muted}>{t("cellsCount", { n: facts.nCells })}</p>
        </>
      )}
      <div className={s.zoomActions}>
        {canZoom && (
          <button type="button" className="btn btn-sm" onClick={onZoomIn}>
            {t("zoomIn")}
          </button>
        )}
        {onZoomRows && (
          <button type="button" className="btn btn-sm" onClick={onZoomRows.go}>
            {tz("zoomRowsInto", { name: onZoomRows.name })}
          </button>
        )}
        {onZoomCols && (
          <button type="button" className="btn btn-sm" onClick={onZoomCols.go}>
            {tz("zoomColsInto", { name: onZoomCols.name })}
          </button>
        )}
        {flowLinks.map((id) => (
          <Link key={id} className="btn btn-sm" href={`/flow/${id}/`}>
            {id.endsWith("~neg") ? t("flowPageNeg") : t("flowPage")}
          </Link>
        ))}
      </div>
    </section>
  );
}
