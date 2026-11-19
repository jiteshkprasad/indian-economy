import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { allRoutes, noteFixture, OUT, watchConsole } from "./helpers";

// PLAN §5.3: every route in §4.2 returns 200 from out/, has an <h1>, logs no console
// error and no hydration warning. Desktop projects only (the phone project repeats nothing new here).
const routes = allRoutes();

test.describe("smoke", () => {
  test.skip(({ isMobile }) => isMobile, "desktop projects only");

  test("the export has the expected route families", async () => {
    expect(routes).toContain("/en/");
    for (const prefix of ["/en/flow/", "/en/series/", "/en/story/", "/en/data/", "/en/methodology/"]) {
      expect(routes.some((r) => r.startsWith(prefix)), prefix).toBe(true);
    }
  });

  test("/ redirects to /en/", async ({ page }) => {
    const res = await page.goto("/");
    expect(res?.status()).toBe(200);
    await expect(page).toHaveURL(/\/en\/$/);
  });

  test("an unknown path serves the 404 page", async ({ page }) => {
    const res = await page.goto("/en/no-such-page/");
    expect(res?.status()).toBe(404);
    await expect(page.locator("h1")).toHaveCount(1);
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
  });

  for (const route of routes) {
    test(`route ${route}`, async ({ page }, info) => {
      noteFixture(info);
      const watch = watchConsole(page);
      const res = await page.goto(route, { waitUntil: "load" });
      expect(res?.status(), route).toBe(200);
      await expect(page.locator("h1").first()).toBeVisible();
      await expect(page.locator("html")).toHaveAttribute("lang", "en");
      // let client effects (lazy fetches, URL state) settle
      await page.waitForLoadState("networkidle");
      watch.assertClean((p) => expect(p, `${route}\n${p.join("\n")}`).toEqual([]));
    });
  }

  // Verify V4-02: a server component that imports a VALUE (not a component) from a
  // "use client" module gets a client reference in the RSC payload. If that chunk is late,
  // hydration suspends inside <head> and React throws #418 and re-renders the whole
  // document. Every client reference in the inline payloads must name a component.
  test("inline RSC payloads reference only client components, never client values", () => {
    const bad: string[] = [];
    for (const route of [...routes, "/404.html"]) {
      const file = route.endsWith(".html") ? path.join(OUT, route) : path.join(OUT, route, "index.html");
      const html = fs.readFileSync(file, "utf8");
      for (const m of html.matchAll(/I\[\d+,\[[^\]]*\],\\"([^\\"]+)\\"/g)) {
        const name = m[1];
        if (name !== "default" && !/^[A-Z][a-z0-9]\w*$/.test(name)) bad.push(`${route}: ${name}`);
      }
    }
    expect([...new Set(bad)]).toEqual([]);
  });

  // The same failure, end to end: hold back one script chunk at a time and require that
  // hydration still succeeds (no React #418, no whole-document client re-render).
  test("hydration survives any one late script chunk", async ({ browser, browserName, baseURL }) => {
    test.skip(browserName !== "chromium", "timing test, Chromium only");
    test.setTimeout(240_000);
    const failures: string[] = [];
    for (const route of ["/en/no-such-page/", "/en/methodology/"]) {
      const html = await (await fetch(new URL(route, baseURL))).text();
      const chunks = [...new Set([...html.matchAll(/\/_next\/static\/chunks\/[\w.-]+\.js/g)].map((m) => m[0]))];
      expect(chunks.length, route).toBeGreaterThan(3);
      for (const late of chunks) {
        const ctx = await browser.newContext();
        await ctx.route(
          (u) => u.pathname === late,
          async (r) => {
            await new Promise((res) => setTimeout(res, 1200));
            await r.continue();
          },
        );
        const page = await ctx.newPage();
        const errors: string[] = [];
        page.on("pageerror", (e) => errors.push(e.message));
        await page.goto(route, { waitUntil: "networkidle" });
        await page.waitForTimeout(200);
        if (errors.some((e) => /#418|#423|Hydration/i.test(e))) failures.push(`${route} with ${late} late: ${errors.join(" | ")}`);
        await ctx.close();
      }
    }
    expect(failures).toEqual([]);
  });
});
