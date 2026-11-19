"use client";

import { useVirtualizer } from "@tanstack/react-virtual";
import { useTranslations } from "next-intl";
import { useDeferredValue, useId, useMemo, useRef, useState } from "react";
import { Num } from "@/components/ui/Num";
import { format } from "@/lib/format";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { HierIndex } from "@/lib/matrix/axes";
import { NO_FILTER, listCells, type ListFilter, type SortDir, type SortKey } from "@/lib/matrix/cells-list";
import { accountCellFacts } from "@/lib/matrix/describe";
import type { MatrixCells, MatrixHierarchy, MatrixPinned } from "@/lib/matrix/types";
import s from "./matrix.module.css";

export interface CellsListProps {
  cells: MatrixCells;
  hierarchy: MatrixHierarchy;
  ix: HierIndex;
  pinned: MatrixPinned;
  gdp: number;
  label: (id: string) => string;
}

const ROW_H = 44;

/** "All non-zero cells" (PLAN §4.8): sortable, filterable, virtualised, with a "show all" switch. */
export function CellsList(p: CellsListProps) {
  const t = useTranslations("matrix.list");
  const tf = useTranslations("matrix.flags");
  const tfs = useTranslations("matrix.flagsShort");
  const uid = useId();
  const [filter, setFilter] = useState<ListFilter>(NO_FILTER);
  const [sort, setSort] = useState<SortKey>("abs");
  const [dir, setDir] = useState<SortDir>("desc");
  const [showAll, setShowAll] = useState(false);
  const text = useDeferredValue(filter.text);
  const scrollRef = useRef<HTMLDivElement>(null);

  const codeOf = (idx: number) => p.hierarchy.accounts[idx].code;
  const order = useMemo(
    () => listCells(p.cells, p.hierarchy, p.ix, { ...filter, text }, sort, dir, p.label),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- label is stable for a page
    [p.cells, p.hierarchy, p.ix, filter.payer, filter.receiver, text, sort, dir],
  );

  // Filter choices: every level-0 and level-1 group, indented under its parent, in matrix order.
  const groups = useMemo(() => {
    const out: Array<{ id: string; depth: number }> = [];
    for (const r of p.ix.roots) {
      out.push({ id: r.id, depth: 0 });
      for (const c of r.children) {
        const n = p.ix.byId.get(c);
        if (n && n.children.length > 0) out.push({ id: c, depth: 1 });
      }
    }
    return out;
  }, [p.ix]);

  // TanStack Virtual is the virtualiser PLAN §4.8 names; this component is not memoised by the compiler.
  // eslint-disable-next-line react-hooks/incompatible-library
  const virt = useVirtualizer({
    count: order.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_H,
    overscan: 12,
    // the sticky header row sits inside the scroll box above the first data row
    paddingStart: ROW_H,
  });
  const items = virt.getVirtualItems();
  const rows = showAll ? order.map((k, i) => ({ k, i })) : items.map((it) => ({ k: order[it.index], i: it.index }));
  const padTop = showAll || items.length === 0 ? 0 : items[0].start - ROW_H;
  const padBottom = showAll || items.length === 0 ? 0 : virt.getTotalSize() - items[items.length - 1].end;

  const sel = (key: "payer" | "receiver") => (
    <div className={s.field}>
      <label htmlFor={`${uid}-${key}`}>{t(key)}</label>
      <select
        id={`${uid}-${key}`}
        value={filter[key] ?? ""}
        onChange={(e) => setFilter((f) => ({ ...f, [key]: e.target.value || null }))}
      >
        <option value="">{t("any")}</option>
        {groups.map((g) => (
          <option key={g.id} value={g.id}>
            {`${g.depth ? "\u00a0\u00a0\u00a0" : ""}${p.label(g.id)}`}
          </option>
        ))}
      </select>
    </div>
  );

  return (
    <div className={s.list}>
      <div className={s.filters}>
        {sel("payer")}
        {sel("receiver")}
        <div className={s.field}>
          <label htmlFor={`${uid}-search`}>{t("search")}</label>
          <input
            id={`${uid}-search`}
            type="search"
            value={filter.text}
            onChange={(e) => setFilter((f) => ({ ...f, text: e.target.value }))}
          />
        </div>
        <div className={s.field}>
          <label htmlFor={`${uid}-sort`}>{t("sortBy")}</label>
          <select id={`${uid}-sort`} value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
            <option value="abs">{t("sortAbs")}</option>
            <option value="value">{t("sortValue")}</option>
            <option value="payer">{t("sortPayer")}</option>
            <option value="receiver">{t("sortReceiver")}</option>
          </select>
        </div>
        <button
          type="button"
          className="btn btn-sm"
          aria-pressed={dir === "asc"}
          onClick={() => setDir((d) => (d === "asc" ? "desc" : "asc"))}
        >
          {dir === "asc" ? t("asc") : t("desc")}
        </button>
        <label className={s.check}>
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
          {t("showAll")}
        </label>
      </div>
      <p aria-live="polite" id={`${uid}-count`} style={{ margin: 0 }}>
        {t("count", { shown: order.length, shownText: format(order.length, "count"), total: format(p.cells.n, "count") })}
      </p>
      {order.length === 0 ? (
        <p>{t("empty")}</p>
      ) : (
        <div
          ref={scrollRef}
          className={s.listScroll}
          role="region"
          aria-label={t("region")}
          tabIndex={0}
          style={showAll ? { maxHeight: "none" } : undefined}
        >
          <table
            className={s.listTable}
            aria-rowcount={order.length + 1}
            aria-describedby={`${uid}-count`}
            data-testid="cells-list"
          >
            <thead>
              <tr aria-rowindex={1}>
                <th scope="col">{t("payer")}</th>
                <th scope="col">{t("receiver")}</th>
                <th scope="col" className={s.numCol}>
                  {t("value")}
                </th>
                <th scope="col" className={s.numCol}>
                  {t("share")}
                </th>
                <th scope="col">{t("status")}</th>
                <th scope="col">{t("flags")}</th>
              </tr>
            </thead>
            <tbody>
              {padTop > 0 && (
                <tr aria-hidden="true" style={{ height: padTop }}>
                  <td colSpan={6} style={{ padding: 0, border: 0, height: padTop }} />
                </tr>
              )}
              {rows.map(({ k, i }) => {
                const f = accountCellFacts(p.cells, k, codeOf, p.pinned, p.gdp);
                return (
                  <tr
                    key={k}
                    ref={showAll ? undefined : virt.measureElement}
                    data-index={i}
                    aria-rowindex={i + 2}
                    data-cell={`${f.payer}--${f.receiver}`}
                  >
                    <td>{p.label(f.payer)}</td>
                    <td>{p.label(f.receiver)}</td>
                    <td className={s.numCol}>
                      <Num value={f.v} fmt="inr" />
                    </td>
                    <td className={s.numCol}>
                      <Num value={f.share} fmt="pct_gdp" />
                    </td>
                    <td>
                      <StatusBadge total={f.total} split={f.split!} composition={f.composition} pins={f.pins} compact />
                    </td>
                    <td className={s.notes} title={f.flags.map((fl) => tf(fl)).join("; ") || undefined}>
                      {f.flags.map((fl) => tfs(fl)).join("; ")}
                    </td>
                  </tr>
                );
              })}
              {padBottom > 0 && (
                <tr aria-hidden="true" style={{ height: padBottom }}>
                  <td colSpan={6} style={{ padding: 0, border: 0, height: padBottom }} />
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
