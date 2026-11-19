"use client";

// The /en/data/ explorer (PLAN §4.8): zoom controls, the canvas heat-map (or its table) sharing
// one zoom state, the selected-cell box with its live-region announcements, and the list of all
// non-zero cells. Data arrives as props from the server page; nothing here invents a number.

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { LiveRegion } from "@/components/ui/LiveRegion";
import { Tabs } from "@/components/ui/Tabs";
import { badgeText } from "@/lib/status";
import { format } from "@/lib/format";
import {
  ROOT_ACCOUNTS,
  ROOT_BLOCKS,
  axisItems,
  indexHierarchy,
  sameZoom,
  zoomAxis,
  zoomInto,
  type AxisState,
  type ZoomState,
} from "@/lib/matrix/axes";
import { clampCursor, type Cursor } from "@/lib/matrix/cursor";
import { cellFacts } from "@/lib/matrix/describe";
import { absDomain, buildGrid } from "@/lib/matrix/grid";
import type { MatrixCells, MatrixHierarchy, MatrixPinned } from "@/lib/matrix/types";
import { CellInfo } from "./CellInfo";
import { CellsList } from "./CellsList";
import { Legend } from "./Legend";
import { MatrixTable } from "./MatrixTable";
import { SamHeatmap } from "./SamHeatmap";
import { ZoomBar } from "./ZoomBar";
import { useCanvasTheme } from "./useCanvasTheme";
import s from "./matrix.module.css";

export interface DataExplorerProps {
  hierarchy: MatrixHierarchy;
  cells: MatrixCells;
  pinned: MatrixPinned;
  /** GDP 2023-24 from summary.json (the share-of-GDP denominator). */
  gdp: number;
  year: string;
  /** Display label per hierarchy node id (from content/<locale>/map-text.json). */
  labels: Record<string, string>;
  /** Level-0 link ids that have a /flow/<id>/ permalink page. */
  flowIds: string[];
}

const PHONE = "(max-width: 639px)";
const ANNOUNCE_MS = 150;

type View = "heatmap" | "table";
interface Frame {
  zoom: ZoomState;
  cursor: Cursor;
}

/** Table axes: the heat-map's axes, but blocks instead of single accounts (128 columns cannot be read). */
function tableZoom(z: ZoomState): ZoomState {
  const g = (a: AxisState): AxisState => (a.grain === "accounts" ? { parent: a.parent, grain: "children" } : a);
  return { rows: g(z.rows), cols: g(z.cols) };
}

export function DataExplorer(props: DataExplorerProps) {
  const t = useTranslations("matrix");
  const { hierarchy, cells, pinned, gdp, labels } = props;
  const ix = useMemo(() => indexHierarchy(hierarchy), [hierarchy]);
  const nAccounts = hierarchy.accounts.length;
  const flowSet = useMemo(() => new Set(props.flowIds), [props.flowIds]);
  const label = useCallback((id: string) => labels[id] ?? id, [labels]);

  // The server renders the phone default (13 × 13); wide screens switch to 128 × 128 after mount.
  const [compact, setCompact] = useState(true);
  const [zoom, setZoom] = useState<ZoomState>(ROOT_BLOCKS);
  const [stack, setStack] = useState<Frame[]>([]);
  const [cursor, setCursor] = useState<Cursor>({ i: 0, j: 0 });
  const [hover, setHover] = useState<Cursor | null>(null);
  const [view, setView] = useState<View>("heatmap");
  const [message, setMessage] = useState("");
  const tableRef = useRef<HTMLDivElement>(null);
  const announceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const theme = useCanvasTheme();

  useEffect(() => {
    const mq = window.matchMedia(PHONE);
    const apply = (phone: boolean, first: boolean) => {
      setCompact(phone);
      // only change the default zoom while the user is still at the root
      setZoom((z) => {
        if (!first && !(sameZoom(z, ROOT_BLOCKS) || sameZoom(z, ROOT_ACCOUNTS))) return z;
        return phone ? ROOT_BLOCKS : ROOT_ACCOUNTS;
      });
    };
    apply(mq.matches, true);
    const onChange = (e: MediaQueryListEvent) => apply(e.matches, false);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const rootZoom = compact ? ROOT_BLOCKS : ROOT_ACCOUNTS;
  const rootGrain = compact ? "children" : "accounts";

  const grid = useMemo(
    () => buildGrid(cells, axisItems(ix, zoom.rows), axisItems(ix, zoom.cols), nAccounts),
    [cells, ix, zoom, nAccounts],
  );
  const tZoom = useMemo(() => tableZoom(zoom), [zoom]);
  const tableGrid = useMemo(
    () => (sameZoom(tZoom, zoom) ? grid : buildGrid(cells, axisItems(ix, tZoom.rows), axisItems(ix, tZoom.cols), nAccounts)),
    [cells, ix, tZoom, zoom, grid, nAccounts],
  );

  const cur = clampCursor(cursor, grid.nR, grid.nC);
  const active = hover ?? cur;
  const facts = cellFacts(grid, active.i, active.j, pinned, gdp);
  // the zoom target for a cell, or null when there is nothing deeper or the block holds no flows
  const zoomTarget = (c: Cursor): ZoomState | null => {
    const next = zoomInto(ix, zoom, grid.rows[c.i], grid.cols[c.j]);
    if (!next) return null;
    const g = buildGrid(cells, axisItems(ix, next.rows), axisItems(ix, next.cols), nAccounts);
    return g.nCells.some((k) => k > 0) ? next : null;
  };
  const canZoom = zoomTarget(active) !== null;

  // level-0 flow permalinks exist only for level-0 pairs
  const flowLinks: string[] = [];
  const isL0 = (id: string) => ix.byId.get(id)?.level === 0;
  if (!facts.empty && facts.payer !== facts.receiver && isL0(facts.payer) && isL0(facts.receiver)) {
    const base = `${facts.payer}--${facts.receiver}`;
    if (facts.pos > 0 && flowSet.has(base)) flowLinks.push(base);
    if (facts.neg < 0 && flowSet.has(`${base}~neg`)) flowLinks.push(`${base}~neg`);
  }

  const say = useCallback((text: string, debounce: boolean) => {
    if (announceTimer.current) clearTimeout(announceTimer.current);
    if (!debounce) {
      setMessage(text);
      return;
    }
    announceTimer.current = setTimeout(() => setMessage(text), ANNOUNCE_MS);
  }, []);
  useEffect(() => () => {
    if (announceTimer.current) clearTimeout(announceTimer.current);
  }, []);

  const describe = useCallback(
    (c: Cursor) => {
      const f = cellFacts(grid, c.i, c.j, pinned, gdp);
      const payer = label(f.payer);
      const receiver = label(f.receiver);
      if (f.empty || f.split === null) return t("cell.announceEmpty", { payer, receiver });
      return t("cell.announce", {
        payer,
        receiver,
        value: format(f.v, "inr"),
        share: format(f.share, "pct_gdp"),
        labels: badgeText(f.total, f.split),
      });
    },
    [grid, pinned, gdp, label, t],
  );

  const moveCursor = (c: Cursor) => {
    setCursor(c);
    say(describe(c), true);
  };

  const go = (next: ZoomState, nextCursor: Cursor = { i: 0, j: 0 }) => {
    setStack((st) => [...st, { zoom, cursor: cur }]);
    setZoom(next);
    setCursor(nextCursor);
    setHover(null);
    const r = axisItems(ix, next.rows).length;
    const c = axisItems(ix, next.cols).length;
    say(t("cell.announceZoom", { rows: r, cols: c }), false);
  };

  const zoomIn = (c: Cursor) => {
    const next = zoomTarget(c);
    if (next) go(next);
    else say(t("heatmap.noZoom"), false);
  };
  const zoomOut = () => {
    const prev = stack[stack.length - 1];
    if (prev) {
      setStack((st) => st.slice(0, -1));
      setZoom(prev.zoom);
      setCursor(prev.cursor);
      setHover(null);
      const r = axisItems(ix, prev.zoom.rows).length;
      const c = axisItems(ix, prev.zoom.cols).length;
      say(t("cell.announceZoom", { rows: r, cols: c }), false);
    } else if (!sameZoom(zoom, rootZoom)) {
      go(rootZoom);
    }
  };
  const reset = () => {
    setStack([]);
    setZoom(rootZoom);
    setCursor({ i: 0, j: 0 });
    setHover(null);
  };
  const onHeader = (axis: "rows" | "cols", index: number) => {
    const item = axis === "rows" ? grid.rows[index] : grid.cols[index];
    const next = zoomAxis(ix, zoom[axis], item);
    if (next) go({ ...zoom, [axis]: next });
  };
  const onAxis = (axis: "rows" | "cols", next: AxisState) => go({ ...zoom, [axis]: next });
  const onGrain = (grain: "children" | "accounts") =>
    go({ rows: { parent: null, grain }, cols: { parent: null, grain } });
  const openTable = () => {
    setView("table");
    requestAnimationFrame(() => tableRef.current?.focus());
  };

  const heatmap = (
    <div className={s.heatmap}>
      <SamHeatmap
        grid={grid}
        rowLabels={grid.rows.map((r) => label(r.id))}
        colLabels={grid.cols.map((c) => label(c.id))}
        blockLabel={label}
        cursor={cur}
        onCursor={moveCursor}
        onZoomIn={zoomIn}
        onZoomOut={zoomOut}
        onTable={openTable}
        onHeader={onHeader}
        onHover={setHover}
        compact={compact}
      />
      <Legend theme={theme.theme} domain={absDomain(grid)} />
    </div>
  );
  const table = (
    <MatrixTable
      ref={tableRef}
      grid={tableGrid}
      label={label}
      pinned={pinned}
      gdp={gdp}
      year={props.year}
      groupedFrom={tableGrid === grid ? null : grid.nR}
    />
  );

  return (
    <div className={s.explorer} data-testid="data-explorer">
      <ZoomBar
        ix={ix}
        zoom={zoom}
        nRows={grid.nR}
        nCols={grid.nC}
        label={label}
        onAxis={onAxis}
        onGrain={onGrain}
        onZoomOut={zoomOut}
        onReset={reset}
        canZoomOut={stack.length > 0 || !sameZoom(zoom, rootZoom)}
        rootGrain={rootGrain}
      />
      <Tabs
        label={t("views.label")}
        selected={view}
        onSelect={(id) => setView(id as View)}
        items={[
          { id: "heatmap", label: t("views.heatmap"), panel: heatmap },
          { id: "table", label: t("views.table"), panel: table },
        ]}
      />
      {view === "heatmap" && (
        <CellInfo
          facts={facts}
          label={label}
          canZoom={canZoom}
          onZoomIn={() => zoomIn(active)}
          onZoomRows={
            zoomAxis(ix, zoom.rows, grid.rows[active.i])
              ? { name: label(grid.rows[active.i].block), go: () => onHeader("rows", active.i) }
              : null
          }
          onZoomCols={
            zoomAxis(ix, zoom.cols, grid.cols[active.j])
              ? { name: label(grid.cols[active.j].block), go: () => onHeader("cols", active.j) }
              : null
          }
          flowLinks={flowLinks}
          source={hover ? "hover" : "cursor"}
        />
      )}
      <LiveRegion message={message} />
      <section className={s.list} aria-labelledby="mx-all-cells">
        <h2 id="mx-all-cells">{t("list.heading")}</h2>
        <p style={{ margin: 0 }}>{t("list.intro", { n: format(cells.n, "count") })}</p>
        <CellsList cells={cells} hierarchy={hierarchy} ix={ix} pinned={pinned} gdp={gdp} label={label} />
      </section>
    </div>
  );
}
