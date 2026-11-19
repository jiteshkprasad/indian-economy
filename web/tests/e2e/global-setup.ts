import type { FullConfig } from "@playwright/test";
// @ts-expect-error: plain ESM script without types
import { startServer } from "../../scripts/serve-out.mjs";

/** Serves out/ on a free port and hands the URL to the workers via PW_BASE_URL. */
export default async function globalSetup(_config: FullConfig) {
  if (process.env.PW_BASE_URL) return;
  const { server, url } = (await startServer(0)) as { server: import("node:http").Server; url: string };
  process.env.PW_BASE_URL = url;
  console.log(`e2e: serving out/ at ${url}/`);
  if (process.env.E2E_FIXTURE_NOTE) console.warn(process.env.E2E_FIXTURE_NOTE);
  return async () => {
    await new Promise<void>((res) => server.close(() => res()));
  };
}
