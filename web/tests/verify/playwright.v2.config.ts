import { defineConfig, devices } from "@playwright/test";

// V2 economics run (verifier-owned). Same server as the e2e suite (web/out/ via serve-out.mjs on a free port,
// or PW_BASE_URL if set). Chromium desktop only; its own output folder so it never collides with other runs.
// Encodes the client-rendered parts of docs/phase3/verify/V2_economics.md; the rest is in
// tests/verify/test_phase3_economics.py (static build, export and parquet).
export default defineConfig({
  testDir: ".",
  testMatch: /v2_economics\.spec\.ts$/,
  globalSetup: "../e2e/global-setup.ts",
  outputDir: "../../test-results-v2",
  workers: 2,
  retries: 0,
  timeout: 60_000,
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
