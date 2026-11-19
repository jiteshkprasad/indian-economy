"use client";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { useTranslations } from "next-intl";
import { MapView } from "@/components/map";
import type { MapInitialData } from "@/components/map/types";
import { useAnnounce } from "@/components/ui/LiveRegion";
import type { Story } from "@/data/types";
import { storyKey, type StorySlug } from "@/lib/story/registry";
import {
  activeId,
  initialStepState,
  isFirst,
  isLast,
  keyToAction,
  parseStepParam,
  stepReducer,
  withStepParam,
  type StepAction,
  type StepState,
} from "@/lib/story/steps";
import { StoryContext, type StoryCtx } from "./context";
import { HighlightList } from "./HighlightList";
import { StepNotes } from "./StepNotes";
import s from "./story.module.css";

export type StoryPlayerProps = {
  slug: StorySlug;
  /** <v>/stories/<slug>.json, read at build time by the page */
  story: Story;
  /** first-view data for the controlled map and the flow list (passed as props, not fetched again) */
  mapData: MapInitialData;
  /** the story MDX, made of <Step id> sections */
  children: ReactNode;
};

const PHONE = "(max-width: 639.98px)";
const PHONE_MAP_HEIGHT = 280;
const DESKTOP_MAP_HEIGHT = 560;

const noSubscribe = () => () => {};

/** true below 640 px; false on the server and during hydration. */
function usePhone(): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const mq = window.matchMedia(PHONE);
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    },
    () => window.matchMedia(PHONE).matches,
    () => false,
  );
}

/** The page's query string after hydration; null on the server and during hydration. */
function useSearch(): string | null {
  return useSyncExternalStore(
    noSubscribe,
    () => window.location.search,
    () => null,
  );
}

type Trigger = "button" | "key" | "jump" | null;

/**
 * CSS for readers without JavaScript: every step, every progress title and no player controls or map
 * (they need JavaScript). With JavaScript the server HTML already has the player's layout (V4-03), so
 * hydration does not move the page. Selectors use data attributes because CSS-module names are hashed.
 */
const NO_JS_CSS =
  "[data-story-player] section[data-step][hidden]{display:block}" +
  "[data-story-player] [data-progress-text]{display:inline}" +
  "[data-story-player] [data-story-js]{display:none}";

/**
 * After a Previous/Next press or an arrow key, keep the reader's place visible (V3-06). The step
 * change can move the focused control out of the viewport. Phone: bring the new step's heading to
 * the top (the controls sit below the text, map and list). Wider screens: bring the heading into view
 * if it is above the viewport, then keep the focused control in view. Focus itself does not move.
 */
function revealAfterMove(player: HTMLElement | null, headingId: string, phone: boolean) {
  const heading = document.getElementById(headingId);
  if (phone) {
    heading?.scrollIntoView({ block: "start" });
    return;
  }
  if (heading && heading.getBoundingClientRect().top < 0) heading.scrollIntoView({ block: "start" });
  const focused = document.activeElement;
  if (focused instanceof HTMLElement && player?.contains(focused)) focused.scrollIntoView({ block: "nearest" });
}

/**
 * The story engine (PLAN §4.9). Desktop: the step text beside a sticky, controlled map.
 * Phone: the step text, then a compact map that draws only the highlighted flows,
 * then the list of those flows. Previous/Next stay in the page flow. ←/→ (and Home/End)
 * step when focus is in the player but not in the map. Deep links: ?step=<id>.
 * The server renders the player as it looks after hydration with no ?step= (step 1 shown, the
 * map box reserved by CSS), so hydration causes no layout shift; the controlled map itself mounts
 * after hydration. Without JavaScript a <noscript> style shows every step and hides the controls.
 */
export function StoryPlayer({ slug, story, mapData, children }: StoryPlayerProps) {
  const t = useTranslations("story");
  const announce = useAnnounce();
  const ids = useMemo(() => story.steps.map((st) => st.id), [story]);
  const search = useSearch();
  const ready = search !== null;
  const param = useMemo(() => (search === null ? { id: null, invalid: null } : parseStepParam(search, ids)), [search, ids]);
  // Until the reader moves, the step comes from ?step=; afterwards from their moves.
  const [moved, setMoved] = useState<StepState | null>(null);
  const state = moved ?? initialStepState(ids, param.id);
  const trigger = useRef<Trigger>(null);
  const phone = usePhone();
  const active = activeId(state);
  const step = story.steps[state.index];
  const mapRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<HTMLDivElement>(null);

  const stepTitle = useCallback((id: string) => t(storyKey.stepTitle(slug, id)), [t, slug]);

  // After a reader's move: keep the URL in step (replaceState), announce, move focus for jumps,
  // and keep the reader's place on screen for button and key moves.
  useEffect(() => {
    const how = trigger.current;
    trigger.current = null;
    if (how === null) return;
    window.history.replaceState(window.history.state, "", withStepParam(window.location.search, active) + window.location.hash);
    announce(t("player.announce", { n: state.index + 1, total: ids.length, title: stepTitle(active) }));
    if (how === "jump") document.getElementById(`step-${active}-h`)?.focus();
    else revealAfterMove(playerRef.current, `step-${active}-h`, phone);
  }, [active, announce, t, state.index, ids.length, stepTitle, phone]);

  const go = (action: StepAction, how: Trigger) => {
    const next = stepReducer(state, action);
    if (next === state) return;
    trigger.current = how;
    setMoved(next);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    const target = e.target as HTMLElement;
    if (mapRef.current?.contains(target)) return; // the map has its own arrow-key model
    if (target.closest("input, select, textarea, [contenteditable]")) return;
    const action = keyToAction(e.key);
    if (!action) return;
    e.preventDefault();
    go(action, "key");
  };

  const ctx: StoryCtx = useMemo(
    () => ({
      slug,
      active,
      position: (id: string) => ids.indexOf(id) + 1,
      count: ids.length,
    }),
    [slug, active, ids],
  );

  const gdp = mapData.summary.gdp.value;

  return (
    <StoryContext.Provider value={ctx}>
      <div ref={playerRef} className={s.player} data-story-player="" data-ready={ready ? "" : undefined} onKeyDown={onKeyDown}>
        <noscript dangerouslySetInnerHTML={{ __html: `<style>${NO_JS_CSS}</style>` }} />
        {param.invalid && (
          <p className={s.notice} role="status">
            {t("player.badStep", { step: param.invalid })}
          </p>
        )}
        <nav className={s.progress} aria-label={t("player.progressLabel")}>
          <ol>
            {ids.map((id, i) => (
              <li key={id}>
                <a
                  href={`?step=${id}`}
                  className={s.progressItem}
                  aria-current={id === active ? "step" : undefined}
                  onClick={(e) => {
                    e.preventDefault();
                    go({ type: "goto", id }, "jump");
                  }}
                >
                  <span className={s.progressNo}>{i + 1}</span>
                  <span className={s.progressText} data-progress-text="">
                    {stepTitle(id)}
                  </span>
                </a>
              </li>
            ))}
          </ol>
        </nav>
        <p className={s.help} data-story-js="">
          {t("player.help")}
        </p>

        <div className={s.grid}>
          <div className={s.text}>
            {children}
            <div data-story-js="">
              <StepNotes slug={slug} story={story} stepId={active} />
            </div>
          </div>

          <div className={s.mapCol} data-story-js="">
            {/* The box keeps the map's height from the first paint (story.module.css: 280 px below 640 px,
                560 px above), so mounting the map after hydration does not shift the page. */}
            <div
              ref={mapRef}
              className={s.mapBox}
              role="region"
              aria-label={t("player.mapLabel", { title: stepTitle(active) })}
              aria-busy={ready ? undefined : true}
            >
              {ready && (
                <MapView
                  mode="controlled"
                  view={step.view.view}
                  preset={step.view.preset}
                  year={step.view.year}
                  expanded={step.view.expanded}
                  selected={step.view.select}
                  highlight={step.view.highlight}
                  onlyHighlighted={phone}
                  height={phone ? PHONE_MAP_HEIGHT : DESKTOP_MAP_HEIGHT}
                  initialData={mapData}
                />
              )}
            </div>
            <HighlightList
              cells={mapData.cells}
              hierarchy={mapData.hierarchy}
              pinned={mapData.pinned}
              gdp={gdp}
              view={step.view}
            />
            <p className={s.muted}>{t("player.grossNote")}</p>
          </div>
        </div>

        <div className={s.nav} data-story-js="">
          <button
            type="button"
            className={s.navBtn}
            aria-disabled={isFirst(state)}
            onClick={() => !isFirst(state) && go({ type: "prev" }, "button")}
          >
            {t("player.prev")}
          </button>
          <span className={s.navPos} aria-hidden="true">
            {t("player.position", { n: state.index + 1, total: ids.length })}
          </span>
          <button
            type="button"
            className={s.navBtn}
            aria-disabled={isLast(state)}
            onClick={() => !isLast(state) && go({ type: "next" }, "button")}
          >
            {t("player.next")}
          </button>
        </div>
      </div>
    </StoryContext.Provider>
  );
}
