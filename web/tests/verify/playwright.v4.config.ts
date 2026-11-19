import { defineConfig, devices } from "@playwright/test";

// V4 build / performance run (verifier-owned; docs/phase3/verify/V4_build_perf.md). The spec starts its own
// Vercel-like server over web/out/ (vercel.json redirects and headers, brotli/gzip), because two V4 findings
// only showed under compressed delivery; the global setup still starts serve-out.mjs (PW_BASE_URL) for the
// test about that server. Chromium desktop and phone; no reducedMotion override (a real first visit).
// Run: npx playwright test -c tests/verify/playwright.v4.config.ts --output=<your own folder>
export default defineConfig({
  testDir: ".",
  testMatch: /v4_build_perf\.spec\.ts$/,
  globalSetup: "../e2e/global-setup.ts",
  outputDir: "../../test-results-v4",
  workers: 2,
  retries: 0,
  timeout: 180_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: {
    baseURL: process.env.PW_BASE_URL,
    locale: "en-IN",
    timezoneId: "Asia/Kolkata",
  },
  projects: [
    { name: "chromium-desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } },
    {
      name: "chromium-phone",
      use: { ...devices["Desktop Chrome"], viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
    },
  ],
});
