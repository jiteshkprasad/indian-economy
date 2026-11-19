import fs from "node:fs";
import path from "node:path";

/** Reads a golden file from pipeline/export/golden/ (owner U1). Missing = test failure, not a skip. */
export function readGolden<T>(name: string): T {
  const p = path.resolve(__dirname, "../../../../pipeline/export/golden", name);
  if (!fs.existsSync(p)) throw new Error(`golden file missing: ${p} (owner U1)`);
  return JSON.parse(fs.readFileSync(p, "utf8")) as T;
}
