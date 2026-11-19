"use client";

// The SAM heat-map (PLAN §4.8): cells on a devicePixelRatio-aware <canvas>, labels, block names,
// the keyboard cursor and the highlighted row and column on an SVG overlay. The wrapper is one Tab
// stop with role="application" and its own keyboard model (lib/matrix/cursor.ts).

import { useTranslations } from "next-intl";
import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { absDomain, type Grid } from "@/lib/matrix/grid";
import { RAMPS, logScale } from "@/lib/matrix/colour";
import { useCanvasTheme } from "./useCanvasTheme";
import { drawGrid } from "@/lib/matrix/draw";
import { cellRectCss, hitColHeader, hitRowHeader, hitTest, layoutGrid, type GridLayout } from "@/lib/matrix/hit";
import { keyAction, type Cursor } from "@/lib/matrix/cursor";
import s from "./matrix.module.css";

export interface HeatmapProps {
  grid: Grid;
  /** Display label per row item and per column item. */
  rowLabels: string[];
  colLabels: string[];
  /** Label per block id, used when cells are too small to label one by one. */
  blockLabel: (id: string) => string;
  cursor: Cursor;
  onCursor: (c: Cursor) => void;
  onZoomIn: (c: Cursor) => void;
  onZoomOut: () => void;
  onTable: () => void;
  onHeader: (axis: "rows" | "cols", index: number) => void;
  onHover?: (c: Cursor | null) => void;
  compact: boolean;
}

const FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';

/** Labels per item when cells are at least this tall (CSS px); otherwise per block. */
const ITEM_LABEL_MIN = 11;

function useDpr(): number {
  const [dpr, setDpr] = useState(1);
  useEffect(() => {
    const update = () => setDpr(window.devicePixelRatio || 1);
    update();
    const mq = window.matchMedia(`(resolution: ${window.devicePixelRatio || 1}dppx)`);
    mq.addEventListener("change", update);
    window.addEventListener("resize", update);
    return () => {
      mq.removeEventListener("change", update);
      window.removeEventListener("resize", update);
    };
  }, []);
  return dpr;
}

function truncate(text: string, maxChars: number): string {
  if (maxChars < 2) return "";
  return text.length <= maxChars ? text : `${text.slice(0, Math.max(1, maxChars - 1)).trimEnd()}…`;
}

interface Run {
  start: number;
  end: number; // exclusive
  label: string;
  index: number; // header index to zoom (first item of the run)
}

/**
 * Drop labels that would overlap a neighbour: bigger blocks keep their label first. A dropped
 * label is still available on hover, in the info box and in the table.
 */
function placeRuns(runs: Run[], cell: number, minGap: number): Run[] {
  const centre = (r: Run) => ((r.start + r.end) / 2) * cell;
  const kept: Run[] = [];
  const byPriority = [...runs].sort((a, b) => b.end - b.start - (a.end - a.start) || a.start - b.start);
  for (const r of byPriority) {
    const c = centre(r);
    if (kept.every((k) => Math.abs(centre(k) - c) >= minGap)) kept.push(r);
  }
  return kept.sort((a, b) => a.start - b.start);
}

function labelRuns(n: number, perItem: boolean, labels: string[], blocks: string[], blockLabel: (id: string) => string): Run[] {
  const runs: Run[] = [];
  if (perItem) {
    for (let i = 0; i < n; i++) runs.push({ start: i, end: i + 1, label: labels[i], index: i });
    return runs;
  }
  let st = 0;
  for (let i = 1; i <= n; i++) {
    if (i === n || blocks[i] !== blocks[st]) {
      runs.push({ start: st, end: i, label: blockLabel(blocks[st]), index: st });
      st = i;
    }
  }
  return runs;
}

export function SamHeatmap(props: HeatmapProps) {
  const t = useTranslations("matrix.heatmap");
  const { grid, cursor, compact } = props;
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState<Cursor | null>(null);
  const [focused, setFocused] = useState(false);
  const [canvasOk, setCanvasOk] = useState(true);
  const dpr = useDpr();
  const helpId = useId();
  const colours = useCanvasTheme();

  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = Math.floor(entries[0].contentRect.width);
      setWidth((prev) => (prev === w ? prev : w));
    });
    ro.observe(el);
    setWidth(Math.floor(el.getBoundingClientRect().width));
    return () => ro.disconnect();
  }, []);

  const left = compact ? 96 : 176;
  const top = compact ? 92 : 140;
  // rotated column labels lean right past the last column: keep room for them
  const rightPad = Math.ceil(top * 0.58);
  const layout: GridLayout | null = useMemo(() => {
    if (width <= 0) return null;
    return layoutGrid({
      cssWidth: width - rightPad,
      nR: grid.nR,
      nC: grid.nC,
      dpr,
      left,
      top,
      maxCell: compact ? 40 : 56,
      minCell: 4,
    });
  }, [width, grid.nR, grid.nC, dpr, left, top, compact, rightPad]);

  const scale = useMemo(() => {
    const d = absDomain(grid);
    return d ? logScale(d) : null;
  }, [grid]);

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv || !layout) return;
    cv.width = layout.devWidth;
    cv.height = layout.devHeight;
    const ctx = cv.getContext("2d");
    if (!ctx) {
      setCanvasOk(false);
      return;
    }
    drawGrid(ctx, layout, grid, RAMPS[colours.theme], scale, { block: colours.block, grid: colours.grid });
  }, [layout, grid, scale, colours]);

  const point = (e: { clientX: number; clientY: number }) => {
    const cv = canvasRef.current!;
    const r = cv.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };

  const onPointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!layout) return;
    const { x, y } = point(e);
    const h = hitTest(layout, x, y);
    const same = h && hover && h.i === hover.i && h.j === hover.j;
    if (!same && (h || hover)) {
      setHover(h);
      props.onHover?.(h);
    }
  };
  const onPointerLeave = () => {
    if (hover) {
      setHover(null);
      props.onHover?.(null);
    }
  };
  const onClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!layout) return;
    const { x, y } = point(e);
    const h = hitTest(layout, x, y);
    if (h) {
      props.onCursor(h);
      wrapRef.current?.focus({ preventScroll: true });
      return;
    }
    const r = hitRowHeader(layout, x, y);
    if (r !== null) return props.onHeader("rows", r);
    const c = hitColHeader(layout, x, y);
    if (c !== null) props.onHeader("cols", c);
  };
  const onDoubleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!layout) return;
    const { x, y } = point(e);
    const h = hitTest(layout, x, y);
    if (h) props.onZoomIn(h);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const a = keyAction(e.key, cursor, grid.nR, grid.nC, { ctrl: e.ctrlKey, meta: e.metaKey, alt: e.altKey });
    if (a.type === "none") return;
    e.preventDefault();
    if (a.type === "move") props.onCursor(a.to);
    else if (a.type === "zoomIn") props.onZoomIn(cursor);
    else if (a.type === "zoomOut") props.onZoomOut();
    else if (a.type === "table") props.onTable();
  };

  // keep the cursor cell in view inside the scroll box
  useEffect(() => {
    const el = wrapRef.current;
    if (!el || !layout || !focused) return;
    const [x, y, w, h] = cellRectCss(layout, cursor.i, cursor.j);
    if (x < el.scrollLeft + left) el.scrollLeft = Math.max(0, x - left);
    else if (x + w > el.scrollLeft + el.clientWidth) el.scrollLeft = x + w - el.clientWidth;
    const box = el.getBoundingClientRect();
    const cellTop = box.top + y - el.scrollTop;
    if (cellTop < 0 || cellTop + h > window.innerHeight) {
      window.scrollBy({ top: cellTop - window.innerHeight / 2, behavior: "auto" });
    }
  }, [cursor, layout, focused, left]);

  const overlay = layout ? (
    <Overlay
      layout={layout}
      grid={grid}
      rowLabels={props.rowLabels}
      colLabels={props.colLabels}
      blockLabel={props.blockLabel}
      cursor={cursor}
      hover={hover}
      showCursor={focused}
      colours={colours}
    />
  ) : null;

  return (
    <div className={s.heatmap}>
      <p className={s.help} id={helpId}>
        {t("help")} <span>{t("helpPointer")}</span>
      </p>
      {!canvasOk && <p role="note">{t("noCanvas")}</p>}
      {scale === null && <p role="note">{t("emptyView")}</p>}
      <div
        ref={wrapRef}
        className={s.canvasWrap}
        role="application"
        aria-roledescription={t("roledesc")}
        aria-label={t("label", { rows: grid.nR, cols: grid.nC })}
        aria-describedby={helpId}
        tabIndex={0}
        onKeyDown={onKeyDown}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        data-rows={grid.nR}
        data-cols={grid.nC}
        data-cursor={`${cursor.i},${cursor.j}`}
      >
        <div
          className={s.canvasBox}
          style={layout ? { width: layout.width + rightPad, height: layout.height } : { height: compact ? 343 : 600 }}
        >
          <canvas
            ref={canvasRef}
            aria-hidden="true"
            data-testid="sam-canvas"
            style={layout ? { width: layout.width, height: layout.height } : undefined}
            onPointerMove={onPointerMove}
            onPointerLeave={onPointerLeave}
            onClick={onClick}
            onDoubleClick={onDoubleClick}
          />
          {overlay}
        </div>
      </div>
    </div>
  );
}

function Overlay(props: {
  layout: GridLayout;
  grid: Grid;
  rowLabels: string[];
  colLabels: string[];
  blockLabel: (id: string) => string;
  cursor: Cursor;
  hover: Cursor | null;
  showCursor: boolean;
  colours: { text: string; halo: string; focus: string };
}) {
  const { layout: l, grid: g, cursor, hover, colours } = props;
  const perItem = l.cellCss >= ITEM_LABEL_MIN;
  const fs = perItem ? Math.min(12, Math.max(9, l.cellCss * 0.75)) : 11;
  const minGap = fs * 0.9; // roughly the cap height plus a little air
  const rowRuns = placeRuns(
    labelRuns(g.nR, perItem, props.rowLabels, g.rows.map((r) => r.block), props.blockLabel),
    l.cellCss,
    minGap,
  );
  const colRuns = placeRuns(
    labelRuns(g.nC, perItem, props.colLabels, g.cols.map((c) => c.block), props.blockLabel),
    l.cellCss,
    minGap / Math.sin(Math.PI / 3),
  );
  const charW = fs * 0.56;
  const rowChars = Math.floor((l.left - 10) / charW);
  // column labels are rotated by -60°: the room along the text is the gutter height / sin 60°
  const colChars = Math.floor((l.top - 8) / Math.sin(Math.PI / 3) / charW);
  const [cx, cy, cw] = cellRectCss(l, cursor.i, cursor.j);
  const x0 = l.left;
  const y0 = l.top;
  const W = l.cellCss * g.nC;
  const H = l.cellCss * g.nR;
  const textStyle = {
    fontFamily: FONT,
    fontSize: fs,
    fill: colours.text,
    stroke: colours.halo,
    strokeWidth: 3,
    paintOrder: "stroke" as const,
  };
  return (
    <svg
      width={l.width}
      height={l.height}
      aria-hidden="true"
      focusable="false"
    >
      {/* highlighted row and column of the cursor */}
      <rect x={x0} y={cy} width={W} height={cw} fill={colours.focus} opacity={0.12} />
      <rect x={cx} y={y0} width={cw} height={H} fill={colours.focus} opacity={0.12} />
      {rowRuns.map((r) => {
        const yc = y0 + ((r.start + r.end) / 2) * l.cellCss;
        const on = cursor.i >= r.start && cursor.i < r.end;
        return (
          <text
            key={`r${r.start}`}
            x={x0 - 6}
            y={yc}
            textAnchor="end"
            dominantBaseline="central"
            style={{ ...textStyle, fontWeight: on ? 700 : 400 }}
          >
            <title>{r.label}</title>
            {truncate(r.label, rowChars)}
          </text>
        );
      })}
      {colRuns.map((c) => {
        const xc = x0 + ((c.start + c.end) / 2) * l.cellCss;
        const on = cursor.j >= c.start && cursor.j < c.end;
        return (
          <text
            key={`c${c.start}`}
            x={xc}
            y={y0 - 6}
            transform={`rotate(-60 ${xc} ${y0 - 6})`}
            textAnchor="start"
            dominantBaseline="central"
            style={{ ...textStyle, fontWeight: on ? 700 : 400 }}
          >
            <title>{c.label}</title>
            {truncate(c.label, colChars)}
          </text>
        );
      })}
      {hover && (
        <rect
          x={cellRectCss(l, hover.i, hover.j)[0]}
          y={cellRectCss(l, hover.i, hover.j)[1]}
          width={l.cellCss}
          height={l.cellCss}
          fill="none"
          stroke={colours.text}
          strokeWidth={1}
        />
      )}
      {/* the cursor: a 2 px focus ring plus a halo, visible whether or not the grid has focus */}
      <rect
        x={cx - 1.5}
        y={cy - 1.5}
        width={cw + 3}
        height={cw + 3}
        fill="none"
        stroke={colours.halo}
        strokeWidth={props.showCursor ? 4 : 3}
      />
      <rect
        data-testid="mx-cursor"
        x={cx - 1}
        y={cy - 1}
        width={cw + 2}
        height={cw + 2}
        fill="none"
        stroke={colours.focus}
        strokeWidth={2}
        strokeDasharray={props.showCursor ? undefined : "3 2"}
      />
    </svg>
  );
}
