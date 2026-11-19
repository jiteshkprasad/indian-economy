import { defineConfig, devices } from "@playwright/test";

// V5 honesty / licences run (verifier-owned). Same server as the e2e suite (web/out/ via serve-out.mjs on a
// free port, or PW_BASE_URL if set). Chromium desktop and phone; its own output folder. Each test names its
// finding id in docs/phase3/verify/V5_honesty_licences.md; open findings are marked test.fail.
export default defineConfig({
  testDir: ".",
  testMatch: /v5_honesty\.spec\.ts$/,
  globalSetup: "../e2e/global-setup.ts",
  outputDir: "../../test-results/v5",
  workers: 2,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: {
    baseURL: process.env.PW_BASE_URL,
    reducedMotion: "reduce",
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
