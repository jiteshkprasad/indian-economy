import { expect, test, type Page } from "@playwright/test";
import { noteFixture, watchConsole } from "./helpers";

// PLAN §5.3 map.spec: the keyboard model (§4.5.10), the slider and its announcements (§2.1),
// views at the 2023-24 boundary, history (Back restores selection and zoom, not the year),
// "view as table", and the phone view.

const DESK = "[data-desktop-map]";

async function active(page: Page) {
  return page.evaluate(() => {
    const a = document.activeElement as HTMLElement | null;
    return {
      mark: a?.getAttribute("data-mark") ?? null,
      node: a?.closest("[data-node]")?.getAttribute("data-node") ?? null,
      key: a?.getAttribute("data-key") ?? null,
      link: a?.closest("[data-link]")?.getAttribute("data-link") ?? null,
      heading: a?.hasAttribute("data-panel-heading") ?? false,
    };
  });
}

test.describe("map (desktop)", () => {
  test.beforeEach(({ isMobile }, info) => {
    test.skip(isMobile, "desktop projects only");
    noteFixture(info);
  });

  test("keyboard: one tab stop, arrows, Enter, Esc, +, L", async ({ page }) => {
    const con = watchConsole(page);
    await page.goto("/en/");
    const svg = page.locator(`${DESK} [data-map-svg]`);
    await expect(svg).toBeVisible();
    // one Tab stop for the whole diagram
    await expect(svg.locator('[tabindex="0"]')).toHaveCount(1);
    const stop = svg.locator('[tabindex="0"]');
    // Tab into it from the control just before it
    await page.locator("[data-table-toggle]").focus();
    for (let i = 0; i < 12 && (await active(page)).mark !== "node"; i++) await page.keyboard.press("Tab");
    expect((await active(page)).mark, "Tab reaches the diagram").toBe("node");
    await expect(stop).toBeFocused();
    // → moves to the nearest node in the next column; ↓ moves within a column (focus moves on the next frame)
    const moved = async (from: string | null) => {
      await expect.poll(async () => (await active(page)).key).not.toBe(from);
      const a = await active(page);
      expect(a.mark).toBe("node");
      return a.key;
    };
    const first = (await active(page)).key;
    await page.keyboard.press("ArrowRight");
    let k = await moved(first);
    await expect(svg.locator("[data-focus-ring]")).toHaveCount(1);
    await page.keyboard.press("ArrowRight");
    k = await moved(k);
    await page.keyboard.press("ArrowRight");
    const col = await moved(k);
    await page.keyboard.press("ArrowDown");
    await moved(col);
    await page.keyboard.press("ArrowUp");
    await expect.poll(async () => (await active(page)).key).toBe(col);
    // Enter opens the panel and moves focus to its heading
    const opened = (await active(page)).node!;
    await page.keyboard.press("Enter");
    const panel = page.locator(`[data-flow-panel][data-id="${opened}"]`);
    await expect(panel).toBeVisible();
    await expect(panel.locator("[data-panel-heading]")).toBeFocused();
    expect(page.url()).toContain(`s=${encodeURIComponent(opened)}`);
    // Esc closes it and returns focus to the mark
    await page.keyboard.press("Escape");
    await expect(panel).toHaveCount(0);
    await expect.poll(async () => (await active(page)).node).toBe(opened);
    // + on Households: the map switches to the full preset, opens the group, and focus follows
    // into it (the first part), with no re-focusing by script (WCAG 2.4.3)
    await svg.locator('[data-node="HH"]').first().focus();
    await page.keyboard.press("+");
    await expect(page.locator("[data-map-app]")).toHaveAttribute("data-preset", "full");
    await expect.poll(() => page.url()).toContain("x=HH");
    await expect(svg.locator('[data-node="HH.RUR"]')).toHaveCount(1);
    await expect.poll(async () => (await active(page)).node, "focus moves to the first part").toBe("HH.RUR");
    await expect(svg.locator("[data-focus-ring]")).toHaveCount(1);
    await expect(page.locator("[data-desktop-map] [data-live-region]")).toContainText("opened");
    // − folds the parts back and focus returns to the group
    await page.keyboard.press("-");
    await expect.poll(() => page.url()).not.toContain("x=HH");
    await expect.poll(async () => (await active(page)).node, "focus returns to the group").toBe("HH");
    // the keys keep working from there: + again, then L enters the focused part's link list
    await page.keyboard.press("+");
    await expect.poll(async () => (await active(page)).node).toBe("HH.RUR");
    // L enters a group's link list; ↓ moves; Enter opens the link
    await page.keyboard.press("l");
    await expect.poll(async () => (await active(page)).link).not.toBeNull();
    const l1 = (await active(page)).link;
    expect(l1, "L focuses a link of the group").not.toBeNull();
    await page.keyboard.press("ArrowDown");
    await expect.poll(async () => (await active(page)).link).not.toBe(l1);
    const l2 = (await active(page)).link;
    expect(l2).not.toBeNull();
    expect(l2).not.toBe(l1);
    await page.keyboard.press("Enter");
    await expect(page.locator(`[data-flow-panel][data-id="${l2}"]`)).toBeVisible();
    con.assertClean((p) => expect(p).toEqual([]));
  });

  test("slider: arrows step, announcements on manual steps only, top-flows view off 2023-24", async ({ page }) => {
    await page.clock.install();
    await page.goto("/en/");
    const live = page.locator("[data-year-slider] [data-live]");
    const range = page.locator("[data-year-range]");
    await expect(range).toHaveAttribute("aria-valuetext", "2023-24");
    await range.focus();
    await page.keyboard.press("ArrowLeft");
    await expect(range).toHaveAttribute("aria-valuetext", "2022-23");
    await expect(page.locator("[data-map-app]")).toHaveAttribute("data-view", "ts");
    await expect(page.locator("[data-ts-banner]")).toBeVisible();
    await expect(live).toContainText("2022-23");
    expect(page.url()).toContain("y=2022-23");
    // scrubbing back into 2023-24 keeps the top-flows view; the banner offers the complete map
    await page.keyboard.press("ArrowRight");
    await expect(range).toHaveAttribute("aria-valuetext", "2023-24");
    await expect(page.locator("[data-map-app]")).toHaveAttribute("data-view", "ts");
    await page.locator("[data-see-complete]").click();
    await expect(page.locator("[data-map-app]")).toHaveAttribute("data-view", "sam");
    // Play does not announce every tick; pausing does
    await page.locator("[data-year-select]").selectOption("1990-91");
    await expect(live).toContainText("1990-91");
    await page.locator("[data-play]").click();
    await page.clock.runFor(3100);
    await expect(range).toHaveAttribute("aria-valuetext", "1993-94");
    await expect(live).toContainText("1990-91");
    await page.locator("[data-play]").click();
    await expect(live).toContainText("1993-94");
  });

  test("Back restores selection and zoom, not the year", async ({ page }) => {
    await page.goto("/en/?p=full");
    await page.locator("[data-table-toggle]").click();
    const row = page.locator('[data-link-table] [data-row-link="HH--PRDS"] button');
    await row.click();
    await expect(page.locator('[data-flow-panel][data-id="HH--PRDS"]')).toBeVisible();
    await page.locator("[data-year-select]").selectOption("2010-11");
    await expect.poll(() => page.url()).toContain("y=2010-11");
    await page.goBack();
    await expect(page.locator("[data-flow-panel]")).toHaveCount(0);
    await expect(page.locator("[data-year-range]")).toHaveAttribute("aria-valuetext", "2010-11");
    await expect(page.locator("[data-map-app]")).toHaveAttribute("data-preset", "full");
  });

  test("view as table lists every visible link", async ({ page }) => {
    await page.goto("/en/");
    await page.locator("[data-table-toggle]").click();
    const rows = page.locator("[data-link-table] [data-row-link]");
    const ids = await rows.evaluateAll((els) => els.map((e) => e.getAttribute("data-row-link")));
    const drawn = await page.locator(`${DESK} [data-link]`).evaluateAll((els) => els.map((e) => e.getAttribute("data-link")));
    expect(ids.length).toBeGreaterThan(0);
    for (const d of drawn) expect(ids).toContain(d);
    // every row carries its value, share of GDP and badge
    const r0 = rows.first();
    await expect(r0.locator('[data-num-fmt="inr"]')).toHaveCount(1);
    await expect(r0.locator('[data-num-fmt="pct_gdp"]')).toHaveCount(1);
    await expect(r0.locator("[data-status-split]")).toHaveCount(1);
  });

  test("focus rings of the toggles are not clipped (WCAG 2.4.7)", async ({ page }) => {
    await page.goto("/en/?s=HH--PRDS");
    await expect(page.locator('[data-flow-panel] [data-trend="chart"]')).toBeVisible();
    for (const sel of ['[data-view-button="sam"]', '[data-view-button="ts"]', '[data-preset-button="simple"]', '[data-preset-button="full"]', '[data-flow-panel] [data-trend="chart"] button']) {
      const el = page.locator(sel).first();
      await el.focus();
      const clip = await el.evaluate((e) => {
        const cs = getComputedStyle(e);
        if (cs.outlineStyle === "none" || parseFloat(cs.outlineWidth) === 0) return "no outline";
        const pad = parseFloat(cs.outlineOffset) + parseFloat(cs.outlineWidth);
        const r = e.getBoundingClientRect();
        for (let a = e.parentElement; a; a = a.parentElement) {
          const s = getComputedStyle(a);
          if (s.overflowX === "visible" && s.overflowY === "visible") continue;
          const b = a.getBoundingClientRect();
          if (r.left - pad < b.left - 0.5 || r.right + pad > b.right + 0.5 || r.top - pad < b.top - 0.5 || r.bottom + pad > b.bottom + 0.5)
            return `clipped by ${a.tagName}.${a.className}`;
        }
        return null;
      });
      expect(clip, sel).toBeNull();
    }
  });

  test("node marks are at least 24 × 24 px; groups are also buttons in the table view (WCAG 2.5.8)", async ({ page }) => {
    for (const url of ["/en/", "/en/?p=full&s=HH", "/en/?x=HH,SI&s=FACT"]) {
      await page.goto(url);
      const nodes = page.locator(`${DESK} [data-mark="node"]`);
      await expect(nodes.first()).toBeVisible();
      await expect
        .poll(async () => Math.min(...(await nodes.evaluateAll((els) => els.map((e) => Math.min(e.getBoundingClientRect().width, e.getBoundingClientRect().height))))), url)
        .toBeGreaterThanOrEqual(23.9);
    }
    await page.goto("/en/");
    await page.locator("[data-table-toggle]").click();
    const drawn = await page.locator(`${DESK} [data-mark="node"]`).evaluateAll((els) => [...new Set(els.map((e) => e.getAttribute("data-node")))]);
    const buttons = page.locator("[data-group-buttons] [data-group-button]");
    expect((await buttons.evaluateAll((els) => els.map((e) => e.getAttribute("data-group-button")))).sort()).toEqual(drawn.sort());
    await page.locator('[data-group-buttons] [data-group-button="HH"]').click();
    const panel = page.locator('[data-flow-panel][data-id="HH"]');
    await expect(panel).toBeVisible();
    await panel.locator("[data-panel-expand]").click();
    await expect.poll(() => page.url()).toContain("x=HH");
  });

  test("labels stay readable when the diagram is drawn small (≥ 12 px nodes, ≥ 11 px values)", async ({ page }) => {
    for (const url of ["/en/?x=HH,SI&s=FACT", "/en/?p=full"]) {
      await page.goto(url);
      const svg = page.locator(`${DESK} [data-map-svg]`);
      await expect(svg).toBeVisible();
      const sizes = async () =>
        svg.evaluate((el) => {
          const vb = (el as SVGSVGElement).viewBox.baseVal;
          const r = el.getBoundingClientRect();
          const k = Math.min(r.width / vb.width, r.height / vb.height);
          const px = (sel: string) => [...el.querySelectorAll(sel)].map((t) => parseFloat(getComputedStyle(t).fontSize) * k);
          return { node: Math.min(...px("[data-node] text")), value: Math.min(...px("g[aria-hidden] > text")) };
        });
      await expect.poll(async () => (await sizes()).node, url).toBeGreaterThanOrEqual(11.95);
      expect((await sizes()).value, url).toBeGreaterThanOrEqual(10.95);
    }
  });

  test("slider ticks sit under the thumb's positions; Play announces the year it stops on", async ({ page }) => {
    await page.clock.install();
    await page.goto("/en/");
    const range = page.locator("[data-year-range]");
    await expect(range).toHaveAttribute("aria-valuetext", "2023-24");
    const geo = await page.locator("[data-year-slider]").evaluate((el) => {
      const r = el.querySelector("[data-year-range]") as HTMLInputElement;
      const tick = el.querySelector("[data-tick-sam]")!.getBoundingClientRect();
      const b = r.getBoundingClientRect();
      const last = Number(r.max);
      const i = Number(r.value);
      return { tick: tick.left + tick.width / 2, thumb: b.left + 12 + ((b.width - 24) * i) / last, left: b.left, right: b.right };
    });
    expect(Math.abs(geo.tick - geo.thumb), `tick ${geo.tick} vs thumb ${geo.thumb}`).toBeLessThanOrEqual(1.5);
    // Play to the last year: the live region names the year it stopped on
    const live = page.locator("[data-year-slider] [data-live]");
    const options = await page.locator("[data-year-select] option").evaluateAll((els) => els.map((e) => (e as HTMLOptionElement).value));
    await page.locator("[data-year-select]").selectOption(options[options.length - 3]);
    await page.locator("[data-play]").click();
    await page.clock.runFor(2100);
    await expect(range).toHaveAttribute("aria-valuetext", options[options.length - 1]);
    await expect(page.locator("[data-play]")).toHaveAttribute("aria-pressed", "false");
    await expect(live).toContainText(options[options.length - 1]);
  });

  test("an invalid link in the URL is reported, not silently dropped", async ({ page }) => {
    await page.goto("/en/?s=NOPE--HH");
    await expect(page.locator("[data-url-notices]")).toBeVisible();
  });
});

test.describe("map (phone)", () => {
  test("shows lists, not the Sankey; a card opens money in / money out", async ({ page, isMobile }, info) => {
    test.skip(!isMobile, "phone project only");
    noteFixture(info);
    await page.goto("/en/");
    await expect(page.locator("[data-phone-map]")).toBeVisible();
    await expect(page.locator(DESK)).toBeHidden();
    const card = page.locator("[data-node-card]").first();
    await card.locator("button").first().click();
    const rows = card.locator("[data-mobile-link]");
    expect(await rows.count()).toBeGreaterThan(0);
    for (const r of (await rows.all()).slice(0, 5)) expect((await r.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await rows.first().click();
    await expect(page.locator("[data-flow-panel]")).toBeVisible();
    const sw = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(sw).toBeLessThanOrEqual(375);
  });

  test("a focused group card shows its focus ring, unclipped (WCAG 2.4.7)", async ({ page, isMobile }, info) => {
    test.skip(!isMobile, "phone project only");
    noteFixture(info);
    await page.goto("/en/");
    const head = page.locator("[data-node-card] button").first();
    await head.focus();
    const clip = await head.evaluate((e) => {
      const cs = getComputedStyle(e);
      if (cs.outlineStyle === "none" || parseFloat(cs.outlineWidth) === 0) return "no outline";
      const pad = parseFloat(cs.outlineOffset) + parseFloat(cs.outlineWidth);
      const r = e.getBoundingClientRect();
      for (let a = e.parentElement; a; a = a.parentElement) {
        const s = getComputedStyle(a);
        if (s.overflowX === "visible" && s.overflowY === "visible") continue;
        const b = a.getBoundingClientRect();
        if (r.left - pad < b.left - 0.5 || r.right + pad > b.right + 0.5 || r.top - pad < b.top - 0.5 || r.bottom + pad > b.bottom + 0.5)
          return `clipped by ${a.tagName}.${a.className}`;
      }
      return null;
    });
    expect(clip).toBeNull();
  });
});
