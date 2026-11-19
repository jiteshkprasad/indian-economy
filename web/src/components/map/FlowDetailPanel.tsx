"use client";
/**
 * The flow detail panel (PLAN §4.7) for a link at any zoom, a node, or a time-series flow:
 * value, share of GDP with the gross-flows framing line, the two-part badge, a plain-English
 * explanation, the matched trend, what is inside, sources and flags.
 * A non-modal region: opening it moves focus to its heading; Esc or Close returns focus.
 */
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { ErrorState, Num, SourceCitation, StatusBadge } from "@/components/ui";
import type { AggLink } from "@/data/aggregate";
import { useDataFile, useMapDesc } from "@/data/hooks";
import { useDataIndex } from "@/data/index-data";
import { loadJson } from "@/data/load";
import type {
  Cells,
  Composition,
  Constraints,
  Cover,
  Entries,
  Entry,
  Hierarchy,
  Label,
  MapDesc,
  Pinned,
  Provenance,
  Series,
  SeriesFlow,
  Summary,
} from "@/data/types";
import { Link } from "@/i18n/navigation";
import { formatInr, formatPct } from "@/lib/format";
import { isLinkId, isSeriesId, parseLinkId, SAM_YEAR, siblingId } from "@/lib/ids";
import { entryFilesFor, resolveLink, resolveNode, type LinkSelection, type NodeScope, type NodeSelection } from "@/lib/sankey/select";
import { composition as compOf, flagNames, headlineSplit } from "@/lib/status";
import { matchSeries, type SeriesMatch } from "@/lib/ts-board/match";
import { composeText, discKeyOf, samPointOf, seriesTotal } from "./panel-text";
import { Sub, SubError, SubLevelProvider } from "./heading-level";
import { TrendChart } from "./TrendChart";
import type { FlowDetailPanelProps } from "./types";
import { useMapLabels, type MapLabels } from "./useLabels";
import s from "./map.module.css";

/** Data a static page passes in so the panel renders fully at build time (no fetches). */
export type FlowPreload = {
  summary: Summary;
  hierarchy: Hierarchy;
  cells: Cells;
  pinned: Pinned;
  entries?: Entry[];
  provenance?: Provenance;
  series?: Series;
  cover?: Cover;
  constraints?: Constraints;
  desc?: MapDesc;
};

export type FlowDetailPanelExtra = { onExpand?: (id: string) => void; onSelect?: (id: string) => void };

export function FlowDetailPanel(props: FlowDetailPanelProps & FlowDetailPanelExtra) {
  const t = useTranslations("map.panel");
  const { onClose } = props;
  // Opening the panel (or selecting something else) moves focus to its heading once it renders:
  // the heading may appear only after lazy data arrive, so the request waits for it.
  const [focusFor, setFocusFor] = useState<string | null>(props.id);
  const [prevId, setPrevId] = useState(props.id);
  if (prevId !== props.id) {
    setPrevId(props.id);
    setFocusFor(props.id);
  }
  const onHeading = useCallback(
    (el: HTMLHeadingElement | null) => {
      if (el && focusFor === props.id) {
        el.focus();
        setFocusFor(null);
      }
    },
    [focusFor, props.id],
  );
  return (
    <section
      className={s.panel}
      role="region"
      aria-label={t("label")}
      data-flow-panel=""
      data-id={props.id}
      onKeyDown={(e) => {
        if (e.key === "Escape" && onClose) {
          e.preventDefault();
          onClose();
        }
      }}
    >
      <FlowDetail
        id={props.id}
        year={props.year}
        scope={props.scope}
        onHeading={onHeading}
        onClose={onClose}
        onExpand={props.onExpand}
        onSelect={props.onSelect}
        headingLevel={2}
      />
    </section>
  );
}

export type FlowDetailProps = {
  id: string;
  year: string;
  /** where the selection is drawn: the effective preset of the SAM map, or "ts" for the board */
  scope?: NodeScope;
  /** callback ref of the heading (the panel moves focus there when it opens) */
  onHeading?: (el: HTMLHeadingElement | null) => void;
  onClose?: () => void;
  onExpand?: (id: string) => void;
  onSelect?: (id: string) => void;
  preload?: FlowPreload;
  headingLevel?: 1 | 2;
  /** static pages: no link back to the page itself */
  standalone?: boolean;
};

type Base = { summary: Summary; hierarchy: Hierarchy; cells: Cells; pinned: Pinned };

/** The panel's content; also rendered by the static flow and series pages with `preload`. */
export function FlowDetail(p: FlowDetailProps) {
  return (
    <SubLevelProvider level={p.headingLevel === 1 ? 2 : 3}>
      <FlowDetailBody {...p} />
    </SubLevelProvider>
  );
}

function FlowDetailBody(p: FlowDetailProps) {
  const pre = p.preload;
  // A static page's preload holds SUBSETS (the link's cells only), so it is used directly and never
  // primes the shared client cache that the Map and the stories read (no fetch, no priming).
  const summary = useLazy<Summary>("summary.json", pre?.summary);
  const hierarchy = useLazy<Hierarchy>("hierarchy.json", pre?.hierarchy);
  const cells = useLazy<Cells>("sam/cells.json", pre?.cells);
  const pinned = useLazy<Pinned>("sam/pinned.json", pre?.pinned);
  const L = useMapLabels();
  const t = useTranslations("map.panel");
  const base = useMemo<Base | null>(
    () =>
      summary.data && hierarchy.data && cells.data && pinned.data
        ? { summary: summary.data, hierarchy: hierarchy.data, cells: cells.data, pinned: pinned.data }
        : null,
    [summary.data, hierarchy.data, cells.data, pinned.data],
  );
  const sel = useMemo(() => {
    if (!base || isSeriesId(p.id)) return null;
    return isLinkId(p.id)
      ? resolveLink(base.hierarchy, base.cells, base.pinned, p.id, p.scope)
      : resolveNode(base.hierarchy, base.cells, base.pinned, p.id, p.scope);
  }, [base, p.id, p.scope]);
  const err = (
    [
      ["summary.json", summary.error],
      ["hierarchy.json", hierarchy.error],
      ["sam/cells.json", cells.error],
      ["sam/pinned.json", pinned.error],
    ] as Array<[string, Error | null]>
  ).find(([, e]) => e);
  if (err) return <ErrorState file={err[0]} error={err[1]} headingLevel={2} />;
  if (!base) return <p className={s.muted}>{t("loading")}</p>;
  if (isSeriesId(p.id)) return <SeriesDetail {...p} base={base} L={L} />;
  if (sel?.kind === "link") return <LinkDetail {...p} base={base} sel={sel} L={L} />;
  if (sel?.kind === "node") return <NodeDetail {...p} base={base} sel={sel} L={L} />;
  return (
    <>
      <PanelHead {...p} title={p.id} kicker="" />
      <p role="status">{t("notFound", { id: p.id })}</p>
    </>
  );
}

function PanelHead({
  onHeading,
  onClose,
  headingLevel,
  title,
  kicker,
  children,
}: FlowDetailProps & { title: string; kicker: string; children?: ReactNode }) {
  const t = useTranslations("map.panel");
  const H = headingLevel === 1 ? "h1" : "h2";
  return (
    <div className={s.panelHead}>
      <div>
        {kicker && (
          <p className={s.muted} style={{ margin: 0, fontSize: "0.85rem" }}>
            {kicker}
          </p>
        )}
        <H ref={onHeading} tabIndex={-1} data-panel-heading="">
          {title}
        </H>
        {children}
      </div>
      {onClose && (
        <button type="button" className="btn btn-sm" onClick={onClose} data-panel-close="">
          {t("close")}
        </button>
      )}
    </div>
  );
}

function useLazy<T>(file: string | null, provided: T | undefined) {
  const r = useDataFile<T>(provided !== undefined ? null : file);
  return { data: provided ?? r.data, error: provided !== undefined ? null : r.error };
}

/** Entries of the given level-0 files (lazy), or the preloaded list. */
function useEntryFiles(l0s: string[], provided?: Entry[]) {
  const idx = useDataIndex();
  const key = l0s.join(",");
  const [state, setState] = useState<{ key: string; data?: Entry[]; error?: Error }>({ key: "" });
  useEffect(() => {
    if (provided) return;
    let live = true;
    Promise.all(
      key
        .split(",")
        .filter(Boolean)
        .map((l0) => loadJson<Entries>(idx, `sam/entries/${l0}.json`)),
    ).then(
      (files) => live && setState({ key, data: files.flatMap((f) => f.entries) }),
      (error: Error) => {
        console.error(`[data] ${error.message}`);
        if (live) setState({ key, error });
      },
    );
    return () => {
      live = false;
    };
  }, [idx, key, provided]);
  if (provided) return { data: provided, error: null as Error | null };
  return state.key === key ? { data: state.data, error: state.error ?? null } : { data: undefined, error: null };
}

function useMapDescMaybe(provided?: MapDesc): MapDesc | undefined {
  const r = useMapDesc();
  return provided ?? r.data;
}

/** Share of GDP with the framing line for gross flows (PLAN §3.3). */
function GdpShare({ share }: { share: number }) {
  const t = useTranslations("map");
  return (
    <>
      <p className={s.subFigure} data-panel-share="">
        <Num value={share} fmt="pct_gdp" />
      </p>
      <p className={s.framing}>{t("framing")}</p>
    </>
  );
}

function FlagList({ mask, refs, L }: { mask: number; refs: string[]; L: MapLabels }) {
  const t = useTranslations("map.panel");
  const tf = useTranslations("common.flags");
  const names = flagNames(mask);
  if (!names.length) return null;
  const disc = refs.filter((r) => /^D\d/.test(r));
  return (
    <>
      <Sub>{t("flags")}</Sub>
      <ul className={s.flagList} data-flags={names.join(",")}>
        {names.map((n) => (
          <li key={n}>
            {tf(n)}
            {n === "discrepancy" && disc.length > 0 && <> ({disc.map((r) => L.text.refs[r]?.label ?? r).join("; ")})</>}
          </li>
        ))}
      </ul>
      <p>
        <Link href="/methodology/#status">{t("labelsLink")}</Link> · <Link href="/methodology/#estimates">{t("estimatesLink")}</Link>
      </p>
    </>
  );
}

function compositionOf(abs: { o: number; d: number; e: number; b: number }): Composition | null {
  return compOf(abs.o, abs.d, abs.e, abs.b);
}

// ---------------------------------------------------------------------------------- link ----

function LinkDetail(p: FlowDetailProps & { base: Base; sel: LinkSelection; L: MapLabels }) {
  const { base, sel, L } = p;
  const t = useTranslations("map.panel");
  const l = sel.link;
  const gdp = base.summary.gdp.value;
  const pid = parseLinkId(l.id)!;
  const desc = useMapDescMaybe(p.preload?.desc);
  const files = useMemo(() => entryFilesFor(base.hierarchy, sel.receiverAccounts), [base.hierarchy, sel.receiverAccounts]);
  const entriesAll = useEntryFiles(files, p.preload?.entries);
  const cellKeys = useMemo(() => {
    const codes = base.hierarchy.accounts.map((a) => a.code);
    return new Set(l.cells.map((i) => `${codes[base.cells.row[i]]}|${codes[base.cells.col[i]]}`));
  }, [l.cells, base]);
  const entries = useMemo(
    () =>
      (entriesAll.data ?? [])
        .filter((e) => cellKeys.has(`${e.row}|${e.col}`))
        .sort((a, b) => Math.abs(b.v) - Math.abs(a.v) || (a.ref < b.ref ? -1 : a.ref > b.ref ? 1 : 0)),
    [entriesAll.data, cellKeys],
  );
  const sibling = siblingId(l.id);
  const composed = useMemo(() => composeText(entries, L, t), [entries, L, t]);
  const ownDesc = desc?.links[l.id];
  return (
    <div data-panel-kind="link">
      <PanelHead {...p} title={L.link(l.id)} kicker={`${t("linkKind")} · ${L.node(pid.payer)} → ${L.node(pid.receiver)}`} />
      <p className={s.muted} style={{ margin: "4px 0 0" }}>
        {t("value", { year: base.summary.gdp.year })}
      </p>
      <p className={s.figure} data-panel-value="">
        <Num value={l.value} fmt="inr" />
      </p>
      <GdpShare share={l.value / gdp} />
      {l.split && (
        <div className={s.badgeRow}>
          <StatusBadge
            total={l.total}
            split={l.split}
            composition={l.composition}
            pins={l.pins}
            pairPins={l.total === null && l.pair ? l.pair.pins : undefined}
          />
        </div>
      )}
      {l.total === null && l.pair && <p className={s.framing}>{t("pairNote", { other: sibling ? L.link(sibling) : "" })}</p>}
      {l.part === "neg" && <p className={s.framing}>{t("negativeNote")}</p>}
      {p.year !== SAM_YEAR && <p className={s.notice}>{t("samYearNote", { samYear: SAM_YEAR, year: p.year })}</p>}

      <Sub>{t("explanation")}</Sub>
      {ownDesc ? <p>{ownDesc}</p> : composed ? <p>{composed}</p> : <p className={s.muted}>{t("loading")}</p>}

      <TrendFor cellsIdx={l.cells} base={base} year={p.year} L={L} preload={p.preload} />

      <Sub>{t("inside")}</Sub>
      {entriesAll.error ? (
        <SubError file={`sam/entries/${files.join(",")}.json`} error={entriesAll.error} />
      ) : !entriesAll.data ? (
        <p className={s.muted}>{t("loading")}</p>
      ) : (
        <EntryTable entries={entries} L={L} constraints={p.preload?.constraints} />
      )}

      {entriesAll.data && <DiscText entries={entries} />}
      {entriesAll.data && <Sources entries={entries} preload={p.preload?.provenance} />}
      <FlagList mask={l.flags} refs={l.refs} L={L} />
      {!p.standalone && isLevel0Link(base.hierarchy, l.id) && (
        <p>
          <Link href={`/flow/${l.id}/`}>{t("openFlow")}</Link>
        </p>
      )}
    </div>
  );
}

/** What each X_DISC item in this flow is (PLAN §3.4.4: five different things, never "a residual"). */
function DiscText({ entries }: { entries: Entry[] }) {
  const tm = useTranslations("map");
  const keys: string[] = [];
  for (const e of entries) {
    const k = discKeyOf(e);
    if (k && !keys.includes(k)) keys.push(k);
  }
  if (!keys.length) return null;
  return (
    <>
      <Sub>{tm("panel.discHeading")}</Sub>
      <ul className={s.smallList} data-disc={keys.join(",")}>
        {keys.map((k) => (
          <li key={k}>{tm(`disc.${k}`, { year: SAM_YEAR })}</li>
        ))}
      </ul>
    </>
  );
}

/** Level-0 links (both presets) have static pages (PLAN §4.2). */
function isLevel0Link(h: Hierarchy, id: string): boolean {
  const p = parseLinkId(id);
  if (!p) return false;
  const l0 = (x: string) => h.nodes.some((n) => n.id === x && n.level === 0) || Object.values(h.presets).some((pr) => pr.merges[x]);
  return l0(p.payer) && l0(p.receiver);
}

function EntryTable({ entries, L, constraints }: { entries: Entry[]; L: MapLabels; constraints?: Constraints }) {
  const t = useTranslations("map.panel");
  const ts = useTranslations("common.status");
  const lazy = useLazy<Constraints>(entries.some((e) => e.binding.length) ? "sam/constraints.json" : null, constraints);
  const shown = entries.slice(0, 12);
  if (!entries.length) return null;
  return (
    <>
      <p className={s.framing}>{t("insideIntro")}</p>
      <div className={s.tableWrap} tabIndex={0} role="region" aria-label={t("inside")}>
        <table className={s.table} data-entries="">
          <thead>
            <tr>
              <th scope="col">{t("entryRef")}</th>
              <th scope="col" className={s.numCell}>
                {t("entryValue")}
              </th>
              <th scope="col">{t("entryLabel")}</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((e, i) => (
              <tr key={`${e.row}|${e.col}|${e.ref}|${e.component}|${i}`}>
                <td>
                  {L.text.refs[e.ref]?.label ?? e.ref}
                  <span className={s.muted}>
                    {" "}
                    ({e.ref}
                    {e.component && e.component !== "total" ? ` · ${e.component}` : ""})
                  </span>
                  {e.prior !== e.v && (
                    <div className={s.muted} style={{ fontSize: "0.85rem" }}>
                      {t("entryMove")}: <Num value={e.prior} fmt="inr" /> → <Num value={e.v} fmt="inr" />
                      {e.pct_change !== null && (
                        <>
                          {" "}
                          (<Num value={e.pct_change} fmt="pct" />)
                        </>
                      )}
                    </div>
                  )}
                  {e.verdict && e.why && (
                    <div style={{ fontSize: "0.85rem" }}>
                      {t("entryWhy")}: {e.verdict}. {e.why.length > 220 ? `${e.why.slice(0, 220)}…` : e.why}
                    </div>
                  )}
                  {e.binding.length > 0 && (
                    <div className={s.muted} style={{ fontSize: "0.85rem" }}>
                      {t("binding", { list: e.binding.map((c) => lazy.data?.[c]?.description ?? c).join("; ") })}
                    </div>
                  )}
                </td>
                <td className={s.numCell}>
                  <Num value={e.v} fmt="inr" />
                </td>
                <td>{ts(e.label as Label)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {entries.length > shown.length && <p className={s.framing}>{t("insideMore", { n: String(entries.length - shown.length) })}</p>}
    </>
  );
}

function Sources({ entries, preload }: { entries: Entry[]; preload?: Provenance }) {
  const prov = useLazy<Provenance>("provenance.json", preload);
  const { ids, weights } = useMemo(() => {
    const w: Record<string, number> = {};
    const order: string[] = [];
    for (const e of entries) {
      if (!(e.prov in w)) order.push(e.prov);
      w[e.prov] = (w[e.prov] ?? 0) + 1;
    }
    return { ids: order, weights: w };
  }, [entries]);
  if (prov.error) return <SubError file="provenance.json" error={prov.error} />;
  if (!prov.data || !ids.length) return null;
  return <SourceCitation provIds={ids} provenance={prov.data} weights={weights} />;
}

// ---------------------------------------------------------------------------------- trend ----

function TrendFor({
  cellsIdx,
  base,
  year,
  L,
  preload,
}: {
  cellsIdx: number[];
  base: Base;
  year: string;
  L: MapLabels;
  preload?: FlowPreload;
}) {
  const t = useTranslations("map.panel");
  const series = useLazy<Series>("ts/series.json", preload?.series);
  const cover = useLazy<Cover>("ts/cover.json", preload?.cover);
  const matches = useMemo(() => (cover.data ? matchSeries(base.cells, cellsIdx, cover.data) : null), [cover.data, base.cells, cellsIdx]);
  if (series.error) return <SubError file="ts/series.json" error={series.error} />;
  if (cover.error) return <SubError file="ts/cover.json" error={cover.error} />;
  if (!series.data || !matches) return null;
  const m = matches[0];
  const flow = m ? series.data.flows.find((f) => f.id === m.flow) : undefined;
  if (!m || !flow) {
    return (
      <>
        <Sub>{t("trend")}</Sub>
        <p data-trend="none">{t("noSeries", { samYear: SAM_YEAR })}</p>
      </>
    );
  }
  return <MatchedTrend m={m} flow={flow} series={series.data} base={base} year={year} L={L} />;
}

function MatchedTrend({
  m,
  flow,
  series,
  base,
  year,
  L,
}: {
  m: SeriesMatch;
  flow: SeriesFlow;
  series: Series;
  base: Base;
  year: string;
  L: MapLabels;
}) {
  const t = useTranslations("map.panel");
  const label = L.series(flow.id);
  const where = useMemo(() => {
    if (m.kind !== "overlap") return "";
    const acc = base.hierarchy.accounts;
    const by = new Map<string, number>();
    for (const [r, c, v] of m.rest) {
      const key = `${acc[c].l0}--${acc[r].l0}`;
      by.set(key, (by.get(key) ?? 0) + Math.abs(v));
    }
    return [...by.entries()]
      .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))
      .slice(0, 2)
      .map(([k]) => {
        const [a, b] = k.split("--");
        return a === b ? L.node(a) : L.link(k);
      })
      .join("; ");
  }, [m, base, L]);
  const heading =
    m.kind === "trend"
      ? t("trend")
      : m.kind === "related"
        ? t("related", { covers: formatPct(m.covers) })
        : t("overlap", { inside: formatPct(m.inside), where });
  const sam = samPointOf(flow, base.summary.gdp.value);
  return (
    <div data-trend-kind={m.kind} data-trend-flow={flow.id}>
      <Sub>{heading}</Sub>
      <p style={{ margin: "0 0 4px" }}>
        <strong>{label}</strong>
      </p>
      <TrendChart series={series} flow={flow} label={label} sam={sam} samYear={SAM_YEAR} highlightYear={year} />
      <CheckText flow={flow} />
      <p>
        <Link href={`/series/${flow.id}/`}>{t("openSeries")}</Link>
      </p>
    </div>
  );
}

export function CheckText({ flow }: { flow: SeriesFlow }) {
  const t = useTranslations("map.panel");
  const c = flow.check;
  return (
    <p className={s.framing} data-check={c.verdict}>
      {c.verdict === "pass"
        ? t("checkPass", { samYear: SAM_YEAR })
        : c.verdict === "explained"
          ? t("checkExplained", { samYear: SAM_YEAR, explanation: c.explanation ?? "" })
          : t("checkNone")}
    </p>
  );
}

// ---------------------------------------------------------------------------------- node ----

function NodeDetail(p: FlowDetailProps & { base: Base; sel: NodeSelection; L: MapLabels }) {
  const { base, sel, L } = p;
  const t = useTranslations("map.panel");
  const desc = useMapDescMaybe(p.preload?.desc);
  const gdp = base.summary.gdp.value;
  const abs = { o: 0, d: 0, e: 0, b: 0 };
  for (const l of sel.moneyIn) {
    abs.o += l.abs.o;
    abs.d += l.abs.d;
    abs.e += l.abs.e;
    abs.b += l.abs.b;
  }
  const comp = compositionOf(abs);
  const n = base.hierarchy.nodes.find((x) => x.id === sel.id);
  const expandable = !!p.onExpand && (n ? n.expandable && n.children.length > 0 : true);
  const short = L.text.nodes[sel.id]?.short;
  const long = desc?.nodes[sel.id];
  const top = (ls: AggLink[]) => [...ls].sort((a, b) => Math.abs(b.value) - Math.abs(a.value)).slice(0, 5);
  return (
    <div data-panel-kind="node">
      <PanelHead {...p} title={L.node(sel.id)} kicker={t("nodeKind")} />
      {short && <p>{short}</p>}
      <p className={s.muted} style={{ margin: "4px 0 0" }}>
        {t("valueNode", { year: base.summary.gdp.year })}
      </p>
      <p className={s.figure} data-panel-value="">
        <Num value={sel.through} fmt="inr" />
      </p>
      <GdpShare share={sel.through / gdp} />
      {comp && (
        <div className={s.badgeRow}>
          <StatusBadge total={null} split={headlineSplit(comp)} composition={comp} />
        </div>
      )}
      {expandable && (
        <p>
          <button type="button" className="btn" onClick={() => p.onExpand?.(sel.id)} data-panel-expand="">
            {t("expand")}
          </button>
        </p>
      )}
      {long && (
        <>
          <Sub>{t("explanation")}</Sub>
          <p>{long}</p>
        </>
      )}
      {sel.internal && sel.internal.pos > 0 && <p className={s.framing}>{t("internal", { value: formatInr(sel.internal.pos) })}</p>}
      <PartnerList title={t("moneyIn")} links={top(sel.moneyIn)} L={L} gdp={gdp} other={(l) => l.payer} />
      <PartnerList title={t("moneyOut")} links={top(sel.moneyOut)} L={L} gdp={gdp} other={(l) => l.receiver} />
    </div>
  );
}

/** The largest partners of a node (summaries against the rest of the economy, not map links). */
function PartnerList({
  title,
  links,
  L,
  gdp,
  other,
}: {
  title: string;
  links: AggLink[];
  L: MapLabels;
  gdp: number;
  other: (l: AggLink) => string;
}) {
  const tm = useTranslations("map");
  if (!links.length) return null;
  return (
    <>
      <Sub>{title}</Sub>
      <ul className={s.smallList}>
        {links.map((l) => (
          <li key={l.id}>
            {L.node(other(l))}
            {l.part === "neg" && <span className={s.muted}> ({tm("reversedMark")})</span>}: <Num value={l.value} fmt="inr" /> (
            <Num value={l.value / gdp} fmt="pct_gdp" />) {l.split && <StatusBadge total={l.total} split={l.split} compact />}
          </li>
        ))}
      </ul>
    </>
  );
}

// --------------------------------------------------------------------------------- series ----

function SeriesDetail(p: FlowDetailProps & { base: Base; L: MapLabels }) {
  const { base, L } = p;
  const t = useTranslations("map.panel");
  const series = useLazy<Series>("ts/series.json", p.preload?.series);
  const prov = useLazy<Provenance>("provenance.json", p.preload?.provenance);
  const desc = useMapDescMaybe(p.preload?.desc);
  if (series.error) return <SubError file="ts/series.json" error={series.error} />;
  if (!series.data) return <p className={s.muted}>{t("loading")}</p>;
  const flow = series.data.flows.find((f) => f.id === p.id);
  if (!flow) return <p role="status">{t("notFound", { id: p.id })}</p>;
  const i = series.data.periods.indexOf(p.year);
  const v = i >= 0 ? flow.main.v[i] : null;
  const share = i >= 0 ? flow.main.share[i] : null;
  const status = i >= 0 ? flow.main.status[i] : null;
  const provId = i >= 0 ? flow.main.prov[i] : null;
  const label = L.series(flow.id);
  const sam = samPointOf(flow, base.summary.gdp.value);
  return (
    <div data-panel-kind="series">
      <PanelHead {...p} title={label} kicker={t("seriesKind")} />
      {v !== null && status ? (
        <>
          <p className={s.muted} style={{ margin: "4px 0 0" }}>
            {t("value", { year: p.year })}
          </p>
          <p className={s.figure} data-panel-value="">
            <Num value={v * flow.display_sign} fmt="inr" />
          </p>
          {share !== null && <GdpShare share={share} />}
          <div className={s.badgeRow}>
            {/* one published (or derived) series value: its own total, as in the stories, and not a sum of entries */}
            <StatusBadge total={seriesTotal(status)} split={status} single />
          </div>
        </>
      ) : (
        <p>{t("noDataYear", { year: p.year })}</p>
      )}
      {desc?.series[flow.id] && (
        <>
          <Sub>{t("explanation")}</Sub>
          <p>{desc.series[flow.id]}</p>
        </>
      )}
      <Sub>{t("trend")}</Sub>
      <TrendChart series={series.data} flow={flow} label={label} sam={sam} samYear={SAM_YEAR} highlightYear={p.year} />
      <CheckText flow={flow} />
      {prov.error && <SubError file="provenance.json" error={prov.error} />}
      {prov.data && provId && <SourceCitation provIds={[provId]} provenance={prov.data} />}
      {!p.standalone && (
        <p>
          <Link href={`/series/${flow.id}/`}>{t("openSeries")}</Link>
        </p>
      )}
    </div>
  );
}
