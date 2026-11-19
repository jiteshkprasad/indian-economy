import { REQUIRED_KEYS } from "./types";

export class DataContractError extends Error {
  constructor(
    public file: string,
    message: string,
  ) {
    super(`${file}: ${message}`);
    this.name = "DataContractError";
  }
}

/** Which REQUIRED_KEYS entry applies to a file path inside <data_version>/. */
export function keySetFor(file: string): string | null {
  if (REQUIRED_KEYS[file]) return file;
  if (/^sam\/entries\/[A-Z]+\.json$/.test(file)) return "entries";
  if (/^stories\/[a-z0-9-]+\.json$/.test(file)) return "story";
  return null;
}

/**
 * Checks top-level shape: a plain object with every required key (PLAN §4.4).
 * Throws DataContractError naming the file and the missing keys.
 */
export function checkTopLevel(file: string, data: unknown): void {
  if (data === null || typeof data !== "object" || Array.isArray(data)) {
    throw new DataContractError(file, "expected a JSON object at the top level");
  }
  const set = keySetFor(file);
  if (!set) return;
  const missing = REQUIRED_KEYS[set].filter((k) => !(k in (data as Record<string, unknown>)));
  if (missing.length) throw new DataContractError(file, `missing top-level keys: ${missing.join(", ")}`);
}
