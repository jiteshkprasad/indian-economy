import fs from "node:fs";
import { chromium, defineConfig, devices, webkit } from "@playwright/test";

// PLAN §5.3. Runs against web/out/ served by scripts/serve-out.mjs on a free port
// (tests/e2e/global-setup.ts starts it and exports PW_BASE_URL to the workers).
// reducedMotion "reduce" by default, fixed workers, seeded samples (SEED=20261002).

function installed(executablePath: () => string): boolean {
  try {
    return fs.existsSync(executablePath());
  } catch {
    return false;
  }
}

const hasChromium = installed(() => chromium.executablePath());
const hasWebkit = installed(() => webkit.executablePath()) && process.env.PW_SKIP_WEBKIT !== "1";
if (!hasChromium) console.error("E2E NOT RUN: Playwright Chromium is not installed (npx playwright install chromium).");
if (!hasWebkit) console.error("WEBKIT E2E NOT RUN ON THIS HOST (browser missing or PW_SKIP_WEBKIT=1).");

const desktop = { viewport: { width: 1280, height: 800 } };
const phone = { viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 };

export default defineConfig({
  testDir: "tests/e2e",
  globalSetup: "./tests/e2e/global-setup.ts",
  fullyParallel: true,
  workers: 2,
  retries: 0,
  forbidOnly: !!process.env.CI,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: process.env.PW_BASE_URL,
    reducedMotion: "reduce",
    trace: "retain-on-failure",
    locale: "en-IN",
    timezoneId: "Asia/Kolkata",
  },
  projects: [
    ...(hasChromium
      ? [
          { name: "chromium-desktop", use: { ...devices["Desktop Chrome"], ...desktop } },
          { name: "chromium-phone", use: { ...devices["Desktop Chrome"], ...phone } },
        ]
      : []),
    ...(hasWebkit
      ? [
          {
            name: "webkit-desktop",
            testMatch: /(smoke|map|story)\.spec\.ts$/,
            use: { ...devices["Desktop Safari"], ...desktop },
          },
        ]
      : []),
  ],
});
