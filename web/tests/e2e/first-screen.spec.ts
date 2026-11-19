import { expect, test, type Locator, type Page } from "@playwright/test";
import { noteFixture, readData, watchConsole } from "./helpers";

// PLAN §4.0, revised in round 3 (founder, 19 Nov 2026: show the project's strength first and make it
// playable): at 375×812, with no scrolling and no input, the first viewport holds the h1, the proof
// strip (four figures from the export), the rupee-tour chips and the top of the map. The story links
// and the headline cards (GDP, each ₹100 of household income) follow below and keep their checks.
// The default state is rendered at build time, so the same holds with JavaScript off.

async function inViewport(page: Page, el: Locator, what: string) {
  const vp = page.viewportSize()!;
  const box = await el.boundingBox();
  expect(box, `${what} is rendered`).not.toBeNull();
  expect(box!.y, `${what} top`).toBeGreaterThanOrEqual(0);
  expect(box!.y + box!.height, `${what} bottom (${Math.round(box!.y + box!.height)} px) inside the ${vp.height} px viewport`).toBeLessThanOrEqual(vp.height);
}

async function firstScreen(page: Page) {
  await inViewport(page, page.locator("h1").first(), "h1");
  const proof = page.locator("[data-proof] [data-proof-item]");
  await expect(proof).toHaveCount(4);
  for (const li of await proof.all()) await inViewport(page, li.locator('[data-num-value][data-num-fmt="count"]'), "proof figure");
  for (const chip of await page.locator("[data-tour] [data-chip]").all()) {
    const b = (await chip.boundingBox())!;
    expect(b.height, "tour chip is at least 24 px tall").toBeGreaterThanOrEqual(24);
  }
  await inViewport(page, page.locator('[data-tour] [data-chip="overview"]'), "first tour chip");
  // the map (or its reserved box before hydration) starts inside the first viewport
  const map = (await page.locator("[data-tour] [role=region]").boundingBox())!;
  expect(map.y, "tour map starts inside the first viewport").toBeLessThan(page.viewportSize()!.height - 120);
  // the story links follow, still at least 44 px tall
  const story = page.locator("[data-first-stories] a[data-story-card]").first();
  const h = (await story.boundingBox())!.height;
  expect(h, "story link is at least 44 px tall").toBeGreaterThanOrEqual(44);
}

test.describe("first screen", () => {
  test("teaches without scrolling at 375×812", async ({ page, isMobile }, info) => {
    test.skip(!isMobile, "phone project only");
    noteFixture(info);
    const con = watchConsole(page);
    await page.goto("/en/");
    expect(await page.evaluate(() => window.scrollY)).toBe(0);
    await firstScreen(page);
    // the headline figures come from summary.json and carry badges
    await expect(page.locator('[data-headline="gdp"] [data-num-fmt="inr"]')).toHaveCount(1);
    const parts = page.locator('[data-headline="hh_outlays"] li[data-part]');
    expect(await parts.count()).toBeGreaterThanOrEqual(3);
    for (const li of await parts.all()) {
      await expect(li.locator('[data-num-fmt="per100"]')).toHaveCount(1);
      await expect(li.locator("[data-status-split]")).toHaveCount(1);
    }
    // the unallocated residual is its own line, never folded into consumption or saving
    await expect(page.locator('[data-part="unallocated_residual"]')).toHaveCount(1);
    // each part shows its own total label from summary.json (V1-03 / V5-04: consumption and saving are
    // held to NAS totals), and its split label; the card heading itself has no badge
    type Part = { key: string; value: number; split_label: string; total_label: string | null };
    const want = readData<{ headline: { hh_outlays: { parts: Part[] } } }>("summary.json").headline.hh_outlays.parts;
    for (const p of want.filter((x) => x.value !== 0)) {
      const badge = page.locator(`[data-part="${p.key}"] [data-status-split]`);
      await expect(badge).toHaveAttribute("data-status-split", p.split_label);
      await expect(badge).toHaveAttribute("data-status-total", p.total_label ?? "");
    }
    await expect(page.locator('[data-headline="hh_outlays"] h2 [data-status-split]')).toHaveCount(0);
    // every badge and part name fits its row: nothing in the list is wider than the card
    const overflow = await page.locator('[data-headline="hh_outlays"] li[data-part]').evaluateAll((lis) =>
      lis.filter((li) => li.scrollWidth > li.clientWidth + 1).map((li) => li.getAttribute("data-part")),
    );
    expect(overflow, "household parts that overflow their row").toEqual([]);
    // the tour map keeps every label inside its frame, with no empty band under it (CPO, 19 Nov)
    await expect(page.locator("[data-tour] svg[data-map-svg] text").first()).toBeVisible();
    await page.waitForTimeout(500);
    const fit = await page.evaluate(() => {
      const svg = document.querySelector("[data-tour] svg[data-map-svg]")!;
      const sb = svg.getBoundingClientRect();
      const ts = [...svg.querySelectorAll("text")].map((t) => t.getBoundingClientRect()).filter((r) => r.width > 0);
      const cap = document.querySelector("[data-tour-caption]")!.getBoundingClientRect();
      return { left: Math.min(...ts.map((r) => r.left)) - sb.left, right: sb.right - Math.max(...ts.map((r) => r.right)), gap: cap.top - sb.bottom };
    });
    expect(fit.left, "left-most label inside the map frame").toBeGreaterThanOrEqual(-1);
    expect(fit.right, "right-most label inside the map frame").toBeGreaterThanOrEqual(-1);
    expect(fit.gap, "gap between map and caption").toBeLessThan(40);
    con.assertClean((p) => expect(p).toEqual([]));
  });

  test("is in the HTML without JavaScript", async ({ browser }) => {
    const ctx = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 375, height: 812 } });
    const page = await ctx.newPage();
    await page.goto("/en/");
    await firstScreen(page);
    // the tour's opening text is in the HTML; the phone map's node cards are in the HTML as well
    await expect(page.locator("[data-tour-caption]")).toContainText(/./);
    expect(await page.locator("[data-node-card]").count()).toBeGreaterThan(5);
    await ctx.close();
  });
});
