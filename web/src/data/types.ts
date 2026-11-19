/**
 * The web data contract, PLAN §3.6, as TypeScript types. This is the hand-written
 * mirror the app imports (`@/data/types`). `contract.gen.ts` is generated from
 * pipeline/export/schema/*.schema.json (`npm run gen:contract`); the test
 * tests/unit/platform/contract-gen.test.ts checks both stay in step.
 */
export type Cr = number; // ₹ crore, 2 dp
export type Share = number; // 6 dp
export type Idx = number; // index into hierarchy.accounts
export type Label = "official" | "derived" | "estimated" | "balancing_set";
export type TotalLabel = "official" | "derived";
export type NodeKind = string;
export type Composition = { o: number; d: number; e: number; b: number };
export type FigUnit = "inr" | "pct_gdp" | "per100" | "pct" | "count";

export type DataIndex = {
  schema_version: 2;
  data_version: string;
  fixture: boolean;
  reference_year: "2023-24";
  gdp_base_year: "2022-23";
  inputs: Record<string, string>;
  export_code_hash: string;
  files: Record<string, { sha256: string; bytes: number }>;
};

export type HeadlinePartKey =
  | "consumption"
  | "saving"
  | "taxes"
  | "financial_services_and_interest"
  | "transfers_abroad"
  | "to_government"
  | "unallocated_residual";

export type Summary = {
  gdp: { year: "2023-24"; value: Cr; prov: string; label: "official" };
  headline: {
    hh_outlays: {
      total: Cr;
      total_label: TotalLabel | null;
      prov: string[];
      parts: Array<{
        key: HeadlinePartKey;
        value: Cr;
        per100: number;
        split_label: Label;
        /** whether this part's sum is held to published figures (same rule as sam/pinned.json) */
        total_label: TotalLabel | null;
        /** what holds the total (constraint ids or "ts:<flow>"); empty when total_label is null */
        pins: string[];
      }>;
    };
    gdp_note: string | null;
  };
  sam: {
    accounts: number;
    cells_nonzero: number;
    entries: number;
    refs: number;
    grand_total: Cr;
    composition: Composition;
    labels: Record<Label, { entries: number; abs: Cr }>;
    balancing: {
      status: string;
      iterations: number;
      max_imbalance: number;
      moved_abs: Cr;
      moved_share_of_abs: number;
    };
  };
  methodology: Record<
    string,
    {
      value: number;
      unit: "inr" | "pct_gdp" | "pct" | "count";
      prov: string[];
      /** economic values only (sums of SAM entries); absent on counts, rule constants and zero amounts */
      split_label?: Label;
      total_label?: TotalLabel | null;
      pins?: string[];
    }
  >;
  ts: { flows: number; core: number; memo: number; first: string; last: string; rows: number };
};

export type HierarchyNode = {
  id: string;
  level: 0 | 1 | 2;
  parent: string | null;
  children: string[];
  accounts: string[];
  order: number;
  col: number;
  kind: NodeKind;
  expandable: boolean;
};

export type PresetId = "simple" | "full";

export type Preset = {
  merges: Record<string, string[]>;
  columns: string[][];
  split_node: string;
  return_flows: "arcs" | "stubs";
};

export type Hierarchy = {
  nodes: HierarchyNode[];
  accounts: Array<{ code: string; idx: Idx; group: string; l0: string; l1: string | null; name_tech: string }>;
  columns: string[][];
  split_node: "PRDS" | string;
  presets: Record<PresetId, Preset>;
  ts_nodes: Array<{ id: string; accounts: string[]; order: number; col: number; kind: NodeKind }>;
};

/** Split label codes used in cells.split: 0 official, 1 derived, 2 estimated, 3 balancing_set. */
export type SplitCode = 0 | 1 | 2 | 3;

export type Cells = {
  n: number;
  row: Idx[];
  col: Idx[];
  v: Cr[];
  abs_o: Cr[];
  abs_d: Cr[];
  abs_e: Cr[];
  abs_b: Cr[];
  split: SplitCode[];
  flags: number[];
  n_entries: number[];
  refs: string[][];
};

export type Pinned = Record<string, { total: TotalLabel; pins: string[] }>;

export type Entry = {
  row: string;
  col: string;
  ref: string;
  component: string;
  v: Cr;
  prior: Cr;
  change: Cr;
  pct_change: number | null;
  status: "official" | "derived" | "estimated" | "balanced";
  prior_status: "official" | "derived" | "estimated";
  role: "fixed" | "anchored" | "free";
  label: Label;
  confidence: "high" | "medium" | "low" | null;
  bop_function: string | null;
  prov: string;
  flags: string[];
  verdict: "explained" | "level unexplained" | "unexplained" | null;
  why: string | null;
  binding: string[];
};

export type Entries = { node: string; entries: Entry[] };

export type Constraint = {
  kind: "band" | "equal" | "max" | "min";
  ref: string;
  description: string;
  target: Cr;
  lo: Cr | null;
  hi: Cr | null;
  balanced_sum: Cr;
  binding: boolean;
  judgement: boolean;
  prov: string;
};
export type Constraints = Record<string, Constraint>;

export type Refs = Record<
  string,
  { row_block: string; col_block: string; description: string; gap_status: string; primary_source: string; method: string }
>;

export type Cite = {
  source: string;
  tables: string[];
  urls: Array<string | null>;
  withheld: boolean;
  /** [first, last] retrieval date (ISO); null when the clean record has none */
  retrieved: [string | null, string | null] | (string | null)[];
};

export type ProvRecord = {
  source: string;
  status: "official" | "derived" | "estimated";
  table: string;
  locator: string | null;
  method: string;
  vintage: string | null;
  base_year: string | null;
  price_basis: string;
  unit: string;
  conversion: string | null;
  assumption: boolean;
  depends_on_assumption: boolean;
  cites: Cite[];
};

export type SourceInfo = {
  name: string;
  publisher: string;
  landing: string | null;
  link_mode: "deep" | "landing" | "withheld";
  licence: string;
  attribution: string;
  registry_status: string;
};

export type Provenance = {
  records: Record<string, ProvRecord>;
  sources: Record<string, SourceInfo>;
};

export type SeriesArrays = {
  v: (Cr | null)[];
  share: (Share | null)[];
  base: (string | null)[];
  status: ("official" | "derived" | null)[];
  stage: (string | null)[];
  flags: (string | null)[];
  segment: (string | null)[];
  prov: (string | null)[];
};

export type SeriesMarker = {
  period: string;
  kind: "base_change" | "concept_break" | "segment_join" | "segment" | "break";
  note: string;
};

export type SeriesFlow = {
  id: string;
  tier: "core" | "memo";
  group: string;
  display_sign: 1 | -1;
  name_tech: string;
  check: {
    class: string;
    verdict: "pass" | "explained" | "no_check";
    ts_value: Cr | null;
    sam_value: Cr | null;
    rel_diff: number | null;
    explanation: string | null;
  };
  link_policy: "linked" | "refused";
  link_reason: string | null;
  markers: SeriesMarker[];
  main: SeriesArrays;
  linked: SeriesArrays | null;
  alts: Array<{ variant: "fc16_definition" | "proxy_total_portfolio"; arrays: SeriesArrays }>;
};

export type Series = {
  periods: string[];
  gdp: { main: (Cr | null)[]; main_base: (string | null)[]; linked: (Cr | null)[]; prov: (string | null)[] };
  flows: SeriesFlow[];
};

export type TsView = {
  coverage: number[];
  ribbons: Array<{ flow: string; from: string; to: string; reversible: boolean; reversed_text_key: string | null }>;
  internal: Record<string, string[]>;
  slot_share: Record<string, Share>;
};

export type Cover = Record<string, { cells: Array<[Idx, Idx, Cr]>; abs_total: Cr }>;

export type StoryFigure = {
  value: number;
  unit: "inr" | "pct_gdp" | "per100" | "pct";
  total: TotalLabel | null;
  split: Label;
  composition: Composition;
  flags: string[];
  prov: string[];
  method: string;
  note_key: string | null;
};

export type StoryView = {
  view: "sam" | "ts";
  preset: PresetId;
  year: string;
  expanded: string[];
  highlight: string[];
  select: string | null;
};

export type Story = {
  slug: string;
  figures: Record<string, StoryFigure>;
  steps: Array<{ id: string; view: StoryView; figures: string[] }>;
};

/** Map text content (web/content/<locale>/map-text.json and map-desc.json, PLAN §3.9). */
export type MapText = {
  nodes: Record<string, { label: string; short: string }>;
  links: Record<string, { label: string }>;
  refs: Record<string, { label: string }>;
  series: Record<string, { label: string }>;
};
export type MapDesc = {
  nodes: Record<string, string>;
  links: Record<string, string>;
  refs: Record<string, string>;
  series: Record<string, string>;
  components?: Record<string, string>;
};

/** File paths inside <data_version>/ and the type each holds. */
export type DataFiles = {
  "summary.json": Summary;
  "hierarchy.json": Hierarchy;
  "sam/cells.json": Cells;
  "sam/pinned.json": Pinned;
  "sam/constraints.json": Constraints;
  "sam/refs.json": Refs;
  "provenance.json": Provenance;
  "ts/series.json": Series;
  "ts/view.json": TsView;
  "ts/cover.json": Cover;
};
export type DataFile = keyof DataFiles;

/**
 * Top-level keys each file must have. Both loaders check them and fail loudly on
 * a mismatch (PLAN §4.4). Record-shaped files (pinned, constraints, refs, cover)
 * have no fixed keys and are checked for being plain objects.
 */
export const REQUIRED_KEYS: Record<string, readonly string[]> = {
  "index.json": ["schema_version", "data_version", "fixture", "reference_year", "gdp_base_year", "inputs", "export_code_hash", "files"],
  "summary.json": ["gdp", "headline", "sam", "methodology", "ts"],
  "hierarchy.json": ["nodes", "accounts", "columns", "split_node", "presets", "ts_nodes"],
  "sam/cells.json": ["n", "row", "col", "v", "abs_o", "abs_d", "abs_e", "abs_b", "split", "flags", "n_entries", "refs"],
  "provenance.json": ["records", "sources"],
  "ts/series.json": ["periods", "gdp", "flows"],
  "ts/view.json": ["coverage", "ribbons", "internal", "slot_share"],
  "entries": ["node", "entries"],
  "story": ["slug", "figures", "steps"],
};

export const DATA_VERSION_RE = /^\d{4}-\d{2}\.([0-9a-f]{10}|fixture0000)$/;
