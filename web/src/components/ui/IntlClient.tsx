import type { ReactNode } from "react";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { pickMessages } from "@/i18n/messages";
import type { Namespace } from "@/i18n/routing";

/**
 * Server component: provides only the namespaces a client subtree needs (plus
 * "common") to NextIntlClientProvider, so the client bundle carries no other
 * text (PLAN §4.12). Each page wraps its client parts:
 *   <IntlClient namespaces={["map"]}>…</IntlClient>
 */
export async function IntlClient({ namespaces = [], children }: { namespaces?: Namespace[]; children: ReactNode }) {
  const all = await getMessages();
  return <NextIntlClientProvider messages={pickMessages(all, namespaces)}>{children}</NextIntlClientProvider>;
}
