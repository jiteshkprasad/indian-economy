/**
 * The sections of /<locale>/methodology/, in page order. `id` is the anchor other
 * pages link to (PLAN §4.2: #status, #estimates, #limits, #sources, #data-version
 * are required); `mdx` names content/<locale>/methodology/<mdx>.mdx; the heading
 * text is messages/<locale>/methodology.json `sections.<key>`.
 */
export const SECTIONS = [
  { id: "what", key: "what", mdx: "what" },
  { id: "build", key: "build", mdx: "build" },
  { id: "status", key: "status", mdx: "status" },
  { id: "estimates", key: "estimates", mdx: "estimates" },
  { id: "limits", key: "limits", mdx: "limits" },
  { id: "time-series", key: "timeSeries", mdx: "time-series" },
  { id: "provisional", key: "provisional", mdx: "provisional" },
  { id: "sources", key: "sources", mdx: "sources" },
  { id: "data-version", key: "dataVersion", mdx: "reproduce" },
  { id: "issues", key: "issues", mdx: "issues" },
] as const;

export type SectionId = (typeof SECTIONS)[number]["id"];

/** Anchors other units link to; tests check they exist. */
export const REQUIRED_ANCHORS = ["status", "estimates", "limits", "sources", "data-version"] as const;
