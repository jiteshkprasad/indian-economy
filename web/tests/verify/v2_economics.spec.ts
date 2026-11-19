import { expect, test, type Locator, type Page } from "@playwright/test";

// V2 economics (PLAN §7, row V2). Owned by the verifier, not by any builder unit. Imports nothing from src/:
// it opens status badges on the rendered site and reads what a reader gets.
// Run: npx playwright test -c tests/verify/playwright.v2.config.ts

const NO_TOTAL = /not held to a single published figure/;

async function openBadge(page: Page, scope: Locator): Promise<string> {
  const btn = scope.locator("button[aria-controls][data-status-total]").first();
  await expect(btn).toBeVisible();
  await btn.click();
  const id = await btn.getAttribute("aria-controls");
  const panel = page.locator(`[id="${id}"]`);
  await expect(panel).toBeVisible();
  await page.waitForLoadState("networkidle");
  await expect(panel).not.toContainText("Loading these figures");
  return ((await panel.innerText()) ?? "").replace(/\s+/g, " ");
}

test("V2-08: the GDP badge does not contradict itself", async ({ page }) => {
  await page.goto("/en/");
  const text = await openBadge(page, page.locator('[data-headline="gdp"]'));
  expect(text).toContain("Taken from a published official statistic");
  expect(text).not.toMatch(NO_TOTAL);
});

test("V2-15: pins are named, not shown as raw constraint ids (DISC--ROW, HH--DISC)", async ({ page }) => {
  for (const [id, raw] of [
    ["DISC--ROW", "ts:M05"],
    ["HH--DISC", "closure:d1.published_total"],
  ] as const) {
    await page.goto(`/en/flow/${id}/`);
    const text = await openBadge(page, page.locator("main"));
    expect(text, id).toContain("held to these figures from published statistics");
    expect(text, id).not.toContain(raw);
    expect(text, id).not.toMatch(NO_TOTAL);
  }
});

test("V2-02: the D3 link shows the whole derived residual and its two parts", async ({ page }) => {
  await page.goto("/en/flow/DISC--SI/");
  const main = page.locator("main");
  await expect(main).toContainText("₹3.59 lakh crore");
  await expect(main).toContainText("one residual derived from the published national accounts");
  await expect(main).toContainText("The whole residual is derived from published national-accounts figures");
  await expect(main).not.toContainText("Two published items");
});

test("V2-01: the deficit story's net-borrowing figures are positive", async ({ page }) => {
  await page.goto("/en/story/deficit-funding/?step=gap");
  const step = page.locator("main");
  await expect(step).toContainText("Net borrowing by the Centre came to");
  const text = ((await step.innerText()) ?? "").replace(/\s+/g, " ");
  const m = text.match(/Net borrowing by the Centre came to (\S+)/);
  expect(m, "sentence rendered").not.toBeNull();
  expect(m![1].startsWith("−") || m![1].startsWith("-")).toBe(false);
});
