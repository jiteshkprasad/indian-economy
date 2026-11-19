/**
 * The home page's playable parts: the rupee tour (follow one rupee through the map) and the
 * guessing game. Both only point at figures already exported for the stories
 * (stories/<slug>.json `figures.<id>`) and at story steps (their map views); no number is typed
 * here except the slider ranges, which are question settings, not data. Wording lives in
 * messages/en/map.json (`tour`, `guess`); the no-digits test covers those namespaces too.
 */
import type { StorySlug } from "@/lib/story/registry";

export type TourStop = {
  /** story step whose map view this stop shows */
  step: string;
  /** main figure ("<id>" in the story's figures) */
  fig: string;
  /** optional second figure, between `middle` and `after` */
  fig2?: string;
};

export type Tour = { slug: StorySlug; stops: TourStop[] };

/** The three rupees a visitor can follow. Stop order follows the story; each stop has one caption. */
export const TOURS: Tour[] = [
  {
    slug: "gst-rupee",
    stops: [
      { step: "total", fig: "gst_total", fig2: "gst_total_gdp" },
      { step: "till", fig: "till_pfce_per100" },
      { step: "lands", fig: "gst_centre_per100", fig2: "gst_states_per100" },
      { step: "onwards", fig: "gst_to_states_kept_per100" },
      { step: "spend", fig: "gg_goods_services_per100", fig2: "gg_interest_per100" },
    ],
  },
  {
    slug: "remittance-dubai",
    stops: [
      { step: "arrive", fig: "remit_total", fig2: "remit_gdp" },
      { step: "uae", fig: "uae_share", fig2: "usa_share" },
      { step: "who", fig: "remit_urban_per100", fig2: "remit_rural_per100" },
      { step: "use", fig: "hh_consumption_per100", fig2: "hh_saving_per100" },
      { step: "buys", fig: "pfce_gst_per100", fig2: "pfce_imports_per100" },
    ],
  },
  {
    slug: "deficit-funding",
    stops: [
      { step: "saving", fig: "saving_cen" },
      { step: "gap", fig: "nb_gg", fig2: "nb_gg_gdp" },
      { step: "buyers", fig: "gsec_bank_per100", fig2: "gsec_insp_per100" },
      { step: "households", fig: "hhfin_depo" },
      { step: "cost", fig: "int_cen", fig2: "int_cen_gdp" },
    ],
  },
];

export type GuessQuestion = {
  id: string;
  slug: StorySlug;
  /** story step to open from the answer */
  step: string;
  fig: string;
  /** slider settings, in the figure's display unit (₹ per ₹100, or percent) */
  min: number;
  max: number;
  step_: number;
};

/**
 * Questions with a surprising answer, each a figure with its own status label. Units are
 * per100 or a share (pct / pct_gdp), so a slider from 0 to 100 (or 0 to 10 for shares of GDP)
 * fits every answer without hinting at it.
 */
export const GUESSES: GuessQuestion[] = [
  { id: "gst-states", slug: "gst-rupee", step: "onwards", fig: "gst_to_states_kept_per100", min: 0, max: 100, step_: 1 },
  { id: "gst-households", slug: "gst-rupee", step: "till", fig: "till_pfce_per100", min: 0, max: 100, step_: 1 },
  { id: "bonds-banks", slug: "deficit-funding", step: "buyers", fig: "gsec_bank_per100", min: 0, max: 100, step_: 1 },
  { id: "bonds-households", slug: "deficit-funding", step: "buyers", fig: "gsec_hh_per100", min: 0, max: 100, step_: 1 },
  { id: "remit-gdp", slug: "remittance-dubai", step: "arrive", fig: "remit_gdp", min: 0, max: 10, step_: 0.1 },
  { id: "interest-gdp", slug: "deficit-funding", step: "cost", fig: "int_cen_gdp", min: 0, max: 10, step_: 0.1 },
];

/** A figure's value in the slider's display unit. */
export function displayValue(value: number, unit: string): number {
  return unit === "pct" || unit === "pct_gdp" ? value * 100 : value;
}

/** Slider value back to the stored unit, for formatting with format(). */
export function storedValue(display: number, unit: string): number {
  return unit === "pct" || unit === "pct_gdp" ? display / 100 : display;
}

/** How close a guess was, as a word key: within a tenth of the range is "close". */
export function closeness(guess: number, answer: number, q: Pick<GuessQuestion, "min" | "max">): "spot" | "close" | "far" {
  const d = Math.abs(guess - answer) / (q.max - q.min);
  return d <= 0.03 ? "spot" : d <= 0.1 ? "close" : "far";
}
