import { hasLocale } from "next-intl";
import { getRequestConfig } from "next-intl/server";
import { loadMessages } from "./messages";
import { routing } from "./routing";

// PLAN §4.12: merges messages/<locale>/*.json under their namespace keys.
export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = hasLocale(routing.locales, requested) ? requested : routing.defaultLocale;
  return {
    locale,
    messages: await loadMessages(locale),
    timeZone: "Asia/Kolkata",
    onError(error) {
      // Missing keys are a bug, never a silent fallback: fail the build loudly in CI output.
      console.error(`[i18n] ${error.code}: ${error.message}`);
    },
  };
});
