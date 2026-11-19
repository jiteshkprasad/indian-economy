import { expect, test, type Page } from "@playwright/test";
import type { Story } from "../../src/data/types";
import { format } from "../../src/lib/format";
import { STORY_SLUGS } from "../../src/lib/story/registry";
import { noteFixture, readData } from "./helpers";

/**
 * Stories (U5, PLAN §4.9, §5.3): every [data-fig-id] shows format(figure) with a badge;
 * the steps move with buttons, arrow keys, Home/End, the progress list and ?step= links.
 */

async function hydrated(page: Page) {
  await expect(page.locator("[data-ready]")).toHaveCount(1);
}

const visibleStep = (page: Page) => page.locator("section[data-step]:not([hidden])");

for (const slug of STORY_SLUGS) {
  test.describe(`story ${slug}`, () => {
    const story = () => readData<Story>(`stories/${slug}.json`);

    test("every figure on the page equals format(story figure) and carries a badge", async ({ page }, info) => {
      noteFixture(info);
      const figs = story().figures;
      await page.goto(`/en/story/${slug}/`);
      const items = await page.locator("[data-fig-id]").evaluateAll((els) =>
        els.map((el) => ({
          id: el.getAttribute("data-fig-id") ?? "",
          text: (el.textContent ?? "").trim(),
          value: el.getAttribute("data-num-value"),
          fmt: el.getAttribute("data-num-fmt"),
          badge: !!(el.closest("tr") ?? el.parentElement)?.querySelector("[data-status-split]"),
        })),
      );
      expect(items.length).toBeGreaterThan(0);
      for (const it of items) {
        const fig = figs[it.id];
        expect(fig, `figure ${it.id} exists`).toBeTruthy();
        expect(it.text, it.id).toBe(format(fig.value, fig.unit));
        expect(Number(it.value), it.id).toBe(fig.value);
        expect(it.fmt, it.id).toBe(fig.unit);
        expect(it.badge, `${it.id} has a badge`).toBe(true);
      }
    });

    test("steps move with Previous/Next and keep ?step= in the URL", async ({ page }) => {
      const ids = story().steps.map((s) => s.id);
      await page.goto(`/en/story/${slug}/`);
      await hydrated(page);
      await expect(visibleStep(page)).toHaveCount(1);
      await expect(visibleStep(page)).toHaveAttribute("data-step", ids[0]);
      const next = page.getByRole("button", { name: "Next", exact: true });
      const prev = page.getByRole("button", { name: "Previous", exact: true });
      await expect(prev).toHaveAttribute("aria-disabled", "true");
      for (let i = 1; i < ids.length; i++) {
        await next.click();
        await expect(visibleStep(page)).toHaveAttribute("data-step", ids[i]);
        await expect(page).toHaveURL(new RegExp(`[?&]step=${ids[i]}(&|#|$)`));
      }
      await expect(next).toHaveAttribute("aria-disabled", "true");
      // aria-disabled (not `disabled`, so it stays focusable): Playwright treats it as not enabled, so force the click
      await next.click({ force: true }); // stays on the last step
      await expect(visibleStep(page)).toHaveAttribute("data-step", ids[ids.length - 1]);
      await prev.click();
      await expect(visibleStep(page)).toHaveAttribute("data-step", ids[ids.length - 2]);
      // the step change is announced in the polite live region
      await expect(page.locator("[data-live-region]", { hasText: `Step ${ids.length - 1} of ${ids.length}` })).toHaveCount(1);
    });

    test("arrow keys, Home and End step when the player has focus", async ({ page }) => {
      const ids = story().steps.map((s) => s.id);
      await page.goto(`/en/story/${slug}/`);
      await hydrated(page);
      await page.getByRole("button", { name: "Next", exact: true }).focus();
      await page.keyboard.press("ArrowRight");
      await expect(visibleStep(page)).toHaveAttribute("data-step", ids[1]);
      await page.keyboard.press("ArrowLeft");
      await expect(visibleStep(page)).toHaveAttribute("data-step", ids[0]);
      await page.keyboard.press("End");
      await expect(visibleStep(page)).toHaveAttribute("data-step", ids[ids.length - 1]);
      await page.keyboard.press("Home");
      await expect(visibleStep(page)).toHaveAttribute("data-step", ids[0]);
    });

    test("the progress list jumps and moves focus to the step heading", async ({ page }) => {
      const ids = story().steps.map((s) => s.id);
      const target = ids[ids.length - 1];
      await page.goto(`/en/story/${slug}/`);
      await hydrated(page);
      await page.locator(`nav a[href="?step=${target}"]`).click();
      await expect(visibleStep(page)).toHaveAttribute("data-step", target);
      await expect(page.locator(`#step-${target}-h`)).toBeFocused();
      await expect(page.locator(`nav a[href="?step=${target}"]`)).toHaveAttribute("aria-current", "step");
    });

    test("?step= deep-links; an unknown step is reported, not silently ignored", async ({ page }) => {
      const ids = story().steps.map((s) => s.id);
      await page.goto(`/en/story/${slug}/?step=${ids[2]}`);
      await hydrated(page);
      await expect(visibleStep(page)).toHaveAttribute("data-step", ids[2]);
      await page.goto(`/en/story/${slug}/?step=no-such-step`);
      await hydrated(page);
      await expect(visibleStep(page)).toHaveAttribute("data-step", ids[0]);
      await expect(page.getByRole("status").filter({ hasText: "no-such-step" })).toBeVisible();
    });
  });
}

test("without JavaScript every step is readable in order, and the controls that need it are hidden", async ({ browser }) => {
  const ctx = await browser.newContext({ javaScriptEnabled: false });
  const page = await ctx.newPage();
  const slug = STORY_SLUGS[0];
  await page.goto(`/en/story/${slug}/`);
  const ids = readData<Story>(`stories/${slug}.json`).steps.map((s) => s.id);
  // the server HTML has the player's layout (later steps carry `hidden`); a <noscript> style shows them all
  const sections = page.locator("section[data-step]");
  await expect(sections).toHaveCount(ids.length);
  for (let i = 0; i < ids.length; i++) {
    await expect(sections.nth(i)).toHaveAttribute("data-step", ids[i]);
    await expect(sections.nth(i)).toBeVisible();
  }
  await expect(page.getByRole("button", { name: "Next", exact: true })).toBeHidden();
  await ctx.close();
});

test("after Next, the reader's place stays on screen (V3-06)", async ({ page }, info) => {
  const slug = "deficit-funding";
  const ids = readData<Story>(`stories/${slug}.json`).steps.map((s) => s.id);
  await page.goto(`/en/story/${slug}/`);
  await hydrated(page);
  const next = page.getByRole("button", { name: "Next", exact: true });
  const phone = (page.viewportSize()?.width ?? 1280) < 640;
  const inView = async (sel: string) =>
    page.locator(sel).evaluate((el) => {
      const r = el.getBoundingClientRect();
      return r.top >= 0 && r.bottom <= window.innerHeight;
    });
  if (phone) {
    // phones: the controls sit below the text, map and list; the new step's heading comes into view
    await next.click();
    await expect(visibleStep(page)).toHaveAttribute("data-step", ids[1]);
    await expect.poll(() => inView(`#step-${ids[1]}-h`), info.title).toBe(true);
  } else {
    // keyboard: the focused control stays visible after each press and after End
    await next.focus();
    for (let i = 1; i < ids.length; i++) {
      await page.keyboard.press("Enter");
      await expect(visibleStep(page)).toHaveAttribute("data-step", ids[i]);
      await expect(next).toBeFocused();
      await expect.poll(() => next.evaluate((el) => el.getBoundingClientRect().bottom <= window.innerHeight)).toBe(true);
    }
    await page.keyboard.press("Home");
    await page.keyboard.press("End");
    await expect(visibleStep(page)).toHaveAttribute("data-step", ids[ids.length - 1]);
    await expect.poll(() => next.evaluate((el) => el.getBoundingClientRect().bottom <= window.innerHeight)).toBe(true);
  }
});

test("hydration does not shift the story page (V4-03)", async ({ page, browserName }) => {
  test.skip(browserName !== "chromium", "the Layout Instability API is Chromium-only");
  await page.addInitScript(() => {
    (window as unknown as { __cls: number }).__cls = 0;
    new PerformanceObserver((list) => {
      for (const e of list.getEntries() as unknown as { value: number; hadRecentInput: boolean }[]) {
        if (!e.hadRecentInput) (window as unknown as { __cls: number }).__cls += e.value;
      }
    }).observe({ type: "layout-shift", buffered: true });
  });
  for (const slug of STORY_SLUGS) {
    await page.goto(`/en/story/${slug}/`);
    await hydrated(page);
    await expect(page.locator("[data-map-svg]")).toHaveCount(1);
    await page.waitForTimeout(300);
    const cls = await page.evaluate(() => (window as unknown as { __cls: number }).__cls);
    expect(cls, `${slug} cumulative layout shift`).toBeLessThan(0.05);
  }
});

test("the story index links to the three stories", async ({ page }) => {
  await page.goto("/en/story/");
  const cards = page.locator("[data-story-card]");
  await expect(cards).toHaveCount(STORY_SLUGS.length);
  for (const slug of STORY_SLUGS) {
    const card = page.locator(`[data-story-card="${slug}"]`);
    await expect(card).toHaveAttribute("href", `/en/story/${slug}/`);
    const box = await card.boundingBox();
    expect(box && box.height >= 44, `${slug} card is at least 44 px tall`).toBe(true);
  }
});
