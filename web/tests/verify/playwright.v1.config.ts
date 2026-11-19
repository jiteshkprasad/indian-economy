import { defineConfig, devices } from "@playwright/test";

// V1 data-fidelity run (verifier-owned). Same server as the e2e suite (web/out/ via serve-out.mjs on a free
// port), Chromium desktop only, its own output folder so it never collides with other runs.
export default defineConfig({
  testDir: ".",
  testMatch: /v1_fidelity\.spec\.ts$/,
  globalSetup: "../e2e/global-setup.ts",
  outputDir: "../../test-results-v1",
  workers: 2,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: [["list"]],
  use: {
    baseURL: process.env.PW_BASE_URL,
    reducedMotion: "reduce",
    locale: "en-IN",
    timezoneId: "Asia/Kolkata",
    viewport: { width: 1280, height: 800 },
  },
  projects: [{ name: "chromium-desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } }],
});
