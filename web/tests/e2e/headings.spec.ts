import { expect, test } from "@playwright/test";

// V4-08: no page skips a heading level (h1 then h3). The flow and series permalink pages reuse the
// detail panel, whose section headings sit one level below the panel's title (h2 under the page's h1).
const pages = ["/en/", "/en/flow/CEN--HH/", "/en/flow/HH--PRODUCERS/", "/en/series/F01/", "/en/methodology/", "/en/data/"];

test.describe("heading order", () => {
  test.skip(({ isMobile }) => isMobile, "desktop project only (same HTML)");
  for (const route of pages) {
    test(route, async ({ page }) => {
      await page.goto(route);
      await page.waitForLoadState("networkidle");
      const levels = await page.locator("main h1, main h2, main h3, main h4, main h5, main h6").evaluateAll((hs) =>
        hs.filter((h) => (h as HTMLElement).offsetParent !== null).map((h) => Number(h.tagName[1])),
      );
      expect(levels[0], `${route}: first heading`).toBe(1);
      const skips = levels.flatMap((l, i) => (i > 0 && l > levels[i - 1] + 1 ? [`h${levels[i - 1]} -> h${l}`] : []));
      expect(skips, `${route}: heading levels ${levels.join(",")}`).toEqual([]);
    });
  }
});
