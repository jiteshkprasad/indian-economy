"use client";
import { useId, useMemo, useState, useSyncExternalStore } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Num, StatusBadge, useAnnounce } from "@/components/ui";
import { closeness, displayValue, storedValue } from "@/data/play";
import { format, type FmtKind } from "@/lib/format";
import type { StorySlug } from "@/lib/story/registry";
import type { TourFig } from "./HeroTour";
import s from "./home.module.css";

export type GuessData = {
  id: string;
  slug: StorySlug;
  step: string;
  min: number;
  max: number;
  step_: number;
  fig: TourFig;
};

const noSubscribe = () => () => {};

type Result = { guess: number; verdict: "spot" | "close" | "far" };

/** Rounds a slider value to its step, without float noise. */
function snap(v: number, step: number): number {
  const d = step < 1 ? 1 : 0;
  return Number((Math.round(v / step) * step).toFixed(d));
}

/**
 * "Guess, then see": one question at a time, a slider in the answer's own unit, then the model's
 * figure with its status label, how far off the guess was, and a link that opens the matching tour
 * stop on the map (home) or the story. A share link carries the guess (?g=) to /<locale>/guess/<id>/.
 */
export function GuessGame({
  questions,
  startId,
  onHome = true,
}: {
  questions: GuessData[];
  startId?: string;
  /** on the home page the answer can open the tour on the map; the share page has its heading as h1 */
  onHome?: boolean;
}) {
  const t = useTranslations("map.guess");
  const locale = useLocale();
  const announce = useAnnounce();
  const uid = useId();
  const first = Math.max(0, startId ? questions.findIndex((q) => q.id === startId) : 0);
  const [i, setI] = useState(first);
  const q = questions[i];
  const mid = (qq: GuessData) => snap((qq.min + qq.max) / 2, qq.step_);
  const [guess, setGuess] = useState(() => mid(q));
  const [results, setResults] = useState<Record<string, Result>>({});
  const search = useSyncExternalStore(
    noSubscribe,
    () => window.location.search,
    () => "",
  );
  const [friendGone, setFriendGone] = useState(false);
  const [copied, setCopied] = useState(false);
  const res = results[q.id];
  const answer = displayValue(q.fig.value, q.fig.unit);
  const fmt = q.fig.unit as FmtKind;
  const show = (v: number) => format(storedValue(v, q.fig.unit), fmt);

  // a friend's guess from a share link (/guess/<id>/?g=<value>), shown until the reader moves on
  const friend = useMemo(() => {
    if (!startId || friendGone || i !== first) return null;
    const raw = new URLSearchParams(search).get("g");
    const g = raw === null ? NaN : Number(raw);
    return Number.isFinite(g) && g >= q.min && g <= q.max ? g : null;
  }, [startId, friendGone, i, first, search, q.min, q.max]);

  const done = useMemo(() => Object.values(results).filter((r) => r.verdict !== "far").length, [results]);

  const check = () => {
    const verdict = closeness(guess, answer, q);
    setResults((r) => ({ ...r, [q.id]: { guess, verdict } }));
    announce(`${t(verdict)} ${t("answer")}: ${format(q.fig.value, fmt)}`);
  };
  const next = () => {
    const n = (i + 1) % questions.length;
    if (n === 0) setResults({});
    setI(n);
    setGuess(mid(questions[n]));
    setFriendGone(true);
    setCopied(false);
  };
  const share = async () => {
    if (!res) return;
    const url = `${window.location.origin}/${locale}/guess/${q.id}/?g=${res.guess}`;
    const text = t("shareText", { guess: show(res.guess) });
    try {
      if (navigator.share) {
        await navigator.share({ title: t(`q.${q.id}`), text, url });
        return;
      }
      await navigator.clipboard.writeText(`${t(`q.${q.id}`)} ${text} ${url}`);
      setCopied(true);
      announce(t("copied"));
    } catch {
      /* the reader closed the share sheet */
    }
  };
  const openOnMap = () => {
    window.dispatchEvent(new CustomEvent("iem:tour", { detail: { slug: q.slug, step: q.step } }));
  };

  const pos = (v: number) => `${(100 * (v - q.min)) / (q.max - q.min)}%`;
  const sliderId = `${uid}-slider`;

  return (
    <section className={s.game} id="guess" aria-labelledby={`${uid}-h`} data-guess="" data-guess-q={q.id}>
      {onHome ? <h2 id={`${uid}-h`}>{t("heading")}</h2> : <h1 id={`${uid}-h`}>{t("heading")}</h1>}
      <p className={s.gameIntro}>{t("intro")}</p>
      <div className={s.gameTop}>
        <span>{t("progress", { n: i + 1, total: questions.length })}</span>
        <span>{t("score", { n: done, total: questions.length })}</span>
      </div>
      <p className={s.question}>
        <label htmlFor={sliderId}>{t(`q.${q.id}`)}</label>
      </p>
      {friend !== null && !res && (
        <p className={s.friend} data-guess-friend="">
          {t("friend", { guess: show(friend) })}
        </p>
      )}
      <div className={s.sliderRow}>
        <input
          id={sliderId}
          className={s.slider}
          type="range"
          min={q.min}
          max={q.max}
          step={q.step_}
          value={res ? res.guess : guess}
          disabled={!!res}
          aria-valuetext={show(res ? res.guess : guess)}
          onChange={(e) => setGuess(snap(Number(e.target.value), q.step_))}
          data-guess-slider=""
        />
        <output htmlFor={sliderId} className={s.guessOut} aria-label={t("yourGuess")}>
          {show(res ? res.guess : guess)}
        </output>
      </div>
      <p className={s.unit}>{fmt === "per100" ? t("unitPer100") : t("unitPct")}</p>

      {!res ? (
        <button type="button" className={`${s.navBtn} ${s.navPrimary}`} onClick={check} data-guess-check="">
          {t("check")}
        </button>
      ) : (
        <>
          <div className={s.scale} aria-hidden="true">
            <span className={`${s.marker} ${s.markerGuess}`} style={{ left: pos(res.guess) }}>
              <span className={s.markerLabel}>{t("yourGuess")}</span>
            </span>
            <span className={`${s.marker} ${s.markerAnswer}`} style={{ left: pos(Math.min(q.max, Math.max(q.min, answer))) }}>
              <span className={s.markerLabel} style={{ top: "auto", bottom: "100%" }}>
                {t("answer")}
              </span>
            </span>
          </div>
          <div className={s.reveal} data-guess-reveal={res.verdict}>
            <p className={s.verdict}>
              <strong>{t(res.verdict)}</strong> {t("answer")}: <Num value={q.fig.value} fmt={fmt} className={s.answerNum} />{" "}
              <StatusBadge total={q.fig.total} split={q.fig.split} compact />
            </p>
            {res.verdict !== "spot" && <p>{t("off", { diff: show(Math.abs(res.guess - answer)) })}</p>}
            <p className={s.why}>{t(`why.${q.id}`)}</p>
            <div className={s.actions}>
              <button type="button" className={`${s.navBtn} ${s.navPrimary}`} onClick={next} data-guess-next="">
                {i === questions.length - 1 ? t("again") : t("next")}
              </button>
              <button type="button" className={s.navBtn} onClick={share} data-guess-share="">
                {copied ? t("copied") : t("share")}
              </button>
              {onHome ? (
                <button type="button" className={s.navBtn} onClick={openOnMap} data-guess-map="">
                  {t("see")}
                </button>
              ) : null}
              <Link className={s.linkBtn} href={`/story/${q.slug}/?step=${q.step}`}>
                {t("story")}
              </Link>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
