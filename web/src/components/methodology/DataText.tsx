import { summaryPath } from "@/data/server";

/**
 * <DataText path="ts.first"/>: a text value (such as a financial-year label) bound
 * from summary.json at build time, for the methodology MDX. It is the text twin of
 * U2's <DataFig>: a path that does not exist, or whose value is not a string, fails
 * the build. Numbers always go through <DataFig>.
 */
export function DataText({ path }: { path: string }) {
  const v = summaryPath(path);
  if (typeof v !== "string") {
    throw new Error(`DataText: summary.json path "${path}" is not a string`);
  }
  return <span data-fig-path={path}>{v}</span>;
}
