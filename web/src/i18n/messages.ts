import type { Namespace } from "./routing";
import { NAMESPACES } from "./routing";

export type Messages = Record<string, unknown>;

/**
 * Loads every namespace file for a locale and merges them under their namespace
 * key: { common: {...}, map: {...}, ... }. A namespace file that does not exist
 * yet is reported on stderr (not silently ignored); its keys then render as
 * next-intl's visible "namespace.key" fallback and log MISSING_MESSAGE.
 */
export async function loadMessages(locale: string): Promise<Messages> {
  const out: Messages = {};
  for (const ns of NAMESPACES) {
    try {
      out[ns] = (await import(`@messages/${locale}/${ns}.json`)).default;
    } catch (e) {
      console.error(`[i18n] messages/${locale}/${ns}.json could not be loaded: ${(e as Error).message}`);
      out[ns] = {};
    }
  }
  return out;
}

/** Picks the namespaces a client subtree needs ("common" is always included). */
export function pickMessages(all: Messages, namespaces: readonly Namespace[]): Messages {
  const out: Messages = { common: all.common ?? {} };
  for (const ns of namespaces) out[ns] = all[ns] ?? {};
  return out;
}
