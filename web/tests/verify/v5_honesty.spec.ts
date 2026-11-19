import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

// V5 (honesty and licences) checks on client-rendered states. Each test names its finding id in
// docs/phase3/verify/V5_honesty_licences.md. Run:
//   npx playwright test -c tests/verify/playwright.v5.config.ts
// Static checks on web/out/ and the export are in tests/verify/test_phase3_honesty.py.

const NO_TOTAL = /not held to a single published figure/i;
const PIN_ID = /\b(?:closure|households|capital_financial|rest_of_world|factors|production|taxes|government|fincorp):[a-z0-9_.]+|\bts:[FM]\d+\b/;

function summary() {
  const pub = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "public", "data");
  const idx = JSON.parse(fs.readFileSync(path.join(pub, "index.json"), "utf8"));
  return JSON.parse(fs.readFileSync(path.join(pub, idx.data_version, "summary.json"), "utf8"));
}

/** Opens the badge button inside `scope` and returns its disclosure text (after pins have loaded). */
async function badgeDisclosure(page: Page, scope = "body") {
  const b = page.locator(`${scope} button[data-status-split]`).first();
  await b.click();
  const id = await b.getAttribute("aria-controls");
  const panel = page.locator(`[id="${id}"]`);
  await expect(panel).toBeVisible();
  await expect(panel).not.toContainText("Loading");
  return (await panel.innerText()).replace(/\s+/g, " ");
}

test("V5-01: the live panel shows a balancing move as its true percentage", async ({ page }) => {
  await page.goto("/en/?p=full&x=HH,SI&s=H_U5--K_HH");
  await page.waitForLoadState("networkidle");
  const line = page.getByText(/Before → after balancing/).first();
  await expect(line).toContainText("₹12.00 lakh crore → ₹12.87 lakh crore (7.3%)");
});

test("V5-02: GDP and a series value never say the total is not held to a published figure", async ({ page }) => {
  await page.goto("/en/");
  await page.waitForLoadState("networkidle");
  const gdp = page.locator("article").filter({ hasText: "India's GDP in" }).first();
  const t = await badgeDisclosure(page, `article:has-text("India's GDP in")`);
  expect(t).not.toMatch(NO_TOTAL);
  expect(t).toContain("Taken from a published official statistic");
  await expect(gdp.locator("button[data-status-split]")).toHaveAttribute("data-status-split", summary().gdp.label);
  for (const sid of ["F01", "M01"]) {
    await page.goto(`/en/series/${sid}/`);
    await page.waitForLoadState("networkidle");
    const s = await badgeDisclosure(page, "[data-panel-kind=series]");
    expect(s, sid).not.toMatch(NO_TOTAL);
  }
});

test("V5-04: each household part on the first screen shows its own total label", async ({ page }) => {
  await page.goto("/en/");
  await page.waitForLoadState("networkidle");
  for (const p of summary().headline.hh_outlays.parts) {
    const b = page.locator(`li[data-part="${p.key}"] [data-status-split]`);
    await expect(b, p.key).toHaveAttribute("data-status-total", p.total_label ?? "");
    await expect(b, p.key).toHaveAttribute("data-status-split", p.split_label);
    if (p.total_label) await expect(b, p.key).toContainText(p.total_label === "official" ? "Official total" : "Derived total");
  }
});

test("V5-05: pinned totals are explained by the published figure, not by an id", async ({ page }) => {
  const cases: [string, RegExp][] = [
    ["/en/flow/DISC--ROW/", /The time series “[^”]+” \(M05\)/],
    ["/en/flow/HH--DISC/", /Target ₹[\d.,]+ lakh crore; the balanced total is within/],
    ["/en/flow/HH--SI/", /household saving/i],
    ["/en/flow/SI--PRODUCERS/", /Together with the other part of this pair/],
  ];
  for (const [url, want] of cases) {
    await page.goto(url);
    await page.waitForLoadState("networkidle");
    const t = await badgeDisclosure(page, "[data-panel-kind]");
    expect(t, url).toMatch(want);
    expect(t.replace(/\(M\d+\)|\(F\d+\)/g, ""), url).not.toMatch(PIN_ID);
  }
});

test("V5-03: every methodology figure with a status in summary.json carries that badge", async ({ page }) => {
  await page.goto("/en/methodology/");
  await page.waitForLoadState("networkidle");
  const m = summary().methodology as Record<string, { value: number; split_label?: string; total_label?: string | null }>;
  const got = await page.locator("[data-num-value]").evaluateAll((els) =>
    els.map((e) => {
      const n = e.nextElementSibling;
      return {
        v: Number(e.getAttribute("data-num-value")),
        total: n?.getAttribute("data-status-total") ?? null,
        split: n?.getAttribute("data-status-split") ?? null,
      };
    }),
  );
  let n = 0;
  for (const [k, it] of Object.entries(m)) {
    if (!it || typeof it !== "object" || !it.split_label) continue;
    const hit = got.find((g) => Math.abs(g.v - it.value) < 0.6 && g.split === it.split_label && g.total === (it.total_label ?? ""));
    expect(hit, `methodology.${k}`).toBeTruthy();
    n++;
  }
  expect(n).toBeGreaterThanOrEqual(8);
});

test("V5-09 (open): a series headline value says its estimate stage", async ({ page }) => {
  test.fail(true, "V5-09 open: the stage shows only in the yearly table");
  await page.goto("/en/series/F01/");
  await page.waitForLoadState("networkidle");
  const head = page.locator("[data-panel-kind=series] [data-panel-value]").locator("xpath=..");
  await expect(head).toContainText(/provisional|\bPE\b/i, { timeout: 2000 });
});

test("V5-14 (open): the top-flows banner does not call curated ribbons 'the largest flows'", async ({ page }) => {
  test.fail(true, "V5-14 open: banner wording");
  await page.goto("/en/?view=ts&y=2004-05");
  await page.waitForLoadState("networkidle");
  const banner = page.getByText(/not a complete, balanced account of the economy/).first();
  await expect(banner).toBeVisible();
  await expect(banner).not.toContainText("largest", { timeout: 2000 });
});
