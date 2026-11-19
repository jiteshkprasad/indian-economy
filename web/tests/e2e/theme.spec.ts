import { expect, test } from "@playwright/test";
import { watchConsole } from "./helpers";

// PLAN §5.3: the toggle persists; prefers-color-scheme is respected; no hydration
// warning after the head script sets data-theme before paint.
test.describe("theme", () => {
  test.skip(({ isMobile }) => isMobile, "desktop project only");

  const bg = (page: import("@playwright/test").Page) =>
    page.evaluate(() => getComputedStyle(document.body).backgroundColor);

  test("follows prefers-color-scheme when nothing is stored", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/en/story/");
    const light = await bg(page);
    await page.emulateMedia({ colorScheme: "dark" });
    await page.reload();
    const dark = await bg(page);
    expect(light).not.toBe(dark);
    expect(await page.evaluate(() => document.documentElement.getAttribute("data-theme"))).toBeNull();
  });

  test("the toggle cycles automatic → light → dark and persists across reloads", async ({ page }) => {
    const watch = watchConsole(page);
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/en/story/");
    const toggle = page.locator("[data-theme-toggle]");
    await expect(toggle).toHaveAttribute("data-theme-choice", "system");
    const auto = await bg(page);
    await toggle.click();
    await expect(toggle).toHaveAttribute("data-theme-choice", "light");
    await toggle.click();
    await expect(toggle).toHaveAttribute("data-theme-choice", "dark");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    const dark = await bg(page);
    expect(dark).not.toBe(auto);
    await page.reload();
    // set by the head script before paint, then the toggle syncs after hydration
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.locator("[data-theme-toggle]")).toHaveAttribute("data-theme-choice", "dark");
    expect(await bg(page)).toBe(dark);
    await page.goto("/en/");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.locator("[data-theme-toggle]").click();
    await expect(page.locator("html")).not.toHaveAttribute("data-theme", /./);
    watch.assertClean((p) => expect(p).toEqual([]));
  });

  test("a stored dark theme beats a light system preference", async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem("theme", "dark");
      } catch {}
    });
    await page.emulateMedia({ colorScheme: "light" });
    const watch = watchConsole(page);
    await page.goto("/en/data/");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.waitForLoadState("networkidle");
    watch.assertClean((p) => expect(p).toEqual([]));
  });
});
