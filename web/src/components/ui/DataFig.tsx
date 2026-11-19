import { summaryPath } from "@/data/server";
import { format, type FmtKind } from "@/lib/format";
import s from "./ui.module.css";

type MethodologyItem = { value: number; unit: FmtKind; prov: string[] };

function isMethodologyItem(x: unknown): x is MethodologyItem {
  return (
    !!x &&
    typeof x === "object" &&
    typeof (x as MethodologyItem).value === "number" &&
    typeof (x as MethodologyItem).unit === "string"
  );
}

/** Units inferred from the summary.json path when it is not a {value, unit} item. */
function inferUnit(path: string): FmtKind | null {
  const last = path.split(".").pop() ?? "";
  if (/^(abs|value|total|grand_total|moved_abs)$/.test(last)) return "inr";
  if (/^(entries|iterations|accounts|cells_nonzero|refs|flows|core|memo|rows)$/.test(last)) return "count";
  if (/^(o|d|e|b|moved_share_of_abs)$/.test(last)) return "pct";
  return null;
}

/**
 * <DataFig path="sam.labels.estimated.abs"/>: a number from summary.json, bound at
 * build time (server component; methodology MDX only, PLAN §3.9). A path that does
 * not exist, or whose value is not a number, fails the build. `fmt` overrides the
 * unit; a `methodology.<key>` item carries its own unit.
 */
export function DataFig({ path, fmt }: { path: string; fmt?: FmtKind }) {
  const v = summaryPath(path);
  let value: number;
  let unit: FmtKind | null;
  if (isMethodologyItem(v)) {
    value = v.value;
    unit = fmt ?? v.unit;
  } else if (typeof v === "number") {
    value = v;
    unit = fmt ?? inferUnit(path);
  } else {
    throw new Error(`DataFig: summary.json path "${path}" is not a number or a {value, unit} item`);
  }
  if (!unit) throw new Error(`DataFig: cannot infer a unit for "${path}"; pass fmt="inr|pct_gdp|pct|per100|count"`);
  return (
    <span className={`num ${s.fig}`} data-fig-path={path} data-num-value={String(value)} data-num-fmt={unit}>
      {format(value, unit)}
    </span>
  );
}
