import { expect, test, type Page } from "@playwright/test";

// V3 (accessibility, mobile, theme) regression checks. Each test names its finding id in
// docs/phase3/verify/V3_a11y_mobile_theme.md. Run:
//   npx playwright test -c tests/verify/playwright.v3.config.ts
// Round 2 (re-verification): V3-01 to V3-07 are fixed and their tests pass normally. Findings that are
// still open are encoded with test.fail(): they pass while the defect is present, and Playwright reports
// them as "unexpectedly passed" (a failure) once the defect is fixed, so the mark must then be removed.

const active = (page: Page) =>
  page.evaluate(() => {
    const e = document.activeElement as HTMLElement | null;
    return { tag: e?.tagName ?? null, mark: e?.getAttribute("data-mark") ?? null, node: e?.getAttribute("data-node") ?? null };
  });

/** True when the focused element's outline (width + offset) is fully visible, i.e. not clipped by an
 * ancestor with overflow other than visible. */
const focusRingUnclipped = (page: Page) =>
  page.evaluate(() => {
    const el = document.activeElement as HTMLElement;
    const cs = getComputedStyle(el);
    const grow = parseFloat(cs.outlineWidth || "0") + parseFloat(cs.outlineOffset || "0");
    if (cs.outlineStyle === "none" || grow <= 0) return { ok: false, why: "no outline" };
    const r = el.getBoundingClientRect();
    const ring = { l: r.left - grow, t: r.top - grow, r: r.right + grow, b: r.bottom + grow };
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const o = getComputedStyle(p);
      if (o.overflowX !== "visible" || o.overflowY !== "visible") {
        const q = p.getBoundingClientRect();
        if (ring.l < q.left - 0.5 || ring.t < q.top - 0.5 || ring.r > q.right + 0.5 || ring.b > q.bottom + 0.5)
          return { ok: false, why: `outline clipped by ${p.tagName}.${p.className}` };
      }
    }
    return { ok: true, why: "" };
  });

test.describe("V3 desktop", () => {
  test.skip(({ isMobile }) => isMobile, "desktop project only");

  test("V3-01: + and − keep keyboard focus inside the diagram", async ({ page }) => {
    await page.goto("/en/");
    await page.waitForLoadState("networkidle");
    await page.locator('[data-mark="node"][data-node="HH"]').first().focus();
    await page.keyboard.press("+");
    await expect(page).toHaveURL(/x=HH/);
    await expect.poll(async () => (await active(page)).mark, { message: "focus after + (was lost to <body>)" }).toBe("node");
    await page.goto("/en/?x=HH");
    await page.waitForLoadState("networkidle");
    await page.locator('[data-mark="node"][data-node="HH.RUR"]').first().focus();
    await page.keyboard.press("-");
    await expect.poll(async () => (await active(page)).mark, { message: "focus after − (was lost to <body>)" }).toBe("node");
  });

  test("V3-02: segmented toggle buttons show an unclipped focus ring", async ({ page }) => {
    await page.goto("/en/");
    await page.waitForLoadState("networkidle");
    for (const name of ["Complete picture (2023-24)", "Top flows over time", "Simple", "Full map"]) {
      const b = page.getByRole("button", { name, exact: true });
      await b.focus();
      await page.keyboard.press("Shift+Tab");
      await page.keyboard.press("Tab");
      await expect(b).toBeFocused();
      const res = await focusRingUnclipped(page);
      expect(res.ok, `${name}: ${res.why}`).toBe(true);
    }
  });

  test("V3-03: diagram node marks are >= 24 px wide or have a visible non-diagram equivalent", async ({ page }) => {
    await page.goto("/en/?t=table");
    await page.waitForLoadState("networkidle");
    const bad = await page.evaluate(() => {
      const visible = (el: Element) => {
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden";
      };
      const alt = [...document.querySelectorAll("button, a")].filter((b) => !b.closest("[data-mark]") && visible(b));
      return [...document.querySelectorAll('[data-mark="node"]')]
        .map((g) => {
          const r = g.querySelector("rect")!.getBoundingClientRect();
          const id = g.getAttribute("data-node")!;
          const hasAlt = alt.some(
            (b) => b.closest(`[data-node-card="${id}"]`) || b.getAttribute("data-select-node") === id || b.getAttribute("data-group-button") === id,
          );
          return { id, w: r.width, h: r.height, hasAlt };
        })
        .filter((n) => (n.w < 24 || n.h < 24) && !n.hasAlt)
        .map((n) => `${n.id} ${n.w.toFixed(1)}x${n.h.toFixed(1)}`);
    });
    expect(bad, "node marks under 24 px with no visible equivalent control on desktop").toEqual([]);
  });

  test("V3-04: Play announces the year it stopped on", async ({ page }) => {
    await page.clock.install();
    await page.goto("/en/?y=2023-24&view=ts");
    await page.waitForLoadState("networkidle");
    await page.locator("[data-play]").click();
    for (let i = 0; i < 4; i++) await page.clock.runFor(1000);
    await expect(page.locator("[data-play]")).toHaveText(/play/i);
    const shown = await page.locator("[data-year-range]").getAttribute("aria-valuetext");
    await expect(page.locator("[data-year-slider] [data-live]")).toContainText(shown!);
  });

  test("V3-05: slider marker ticks line up with the range track", async ({ page }) => {
    await page.goto("/en/");
    await page.waitForLoadState("networkidle");
    const r = await page.evaluate(() => {
      const range = document.querySelector("[data-year-range]") as HTMLInputElement;
      const rb = range.getBoundingClientRect();
      const sam = document.querySelector('[data-year-slider] [title]:not([data-marker])') as HTMLElement | null;
      const sb = sam?.getBoundingClientRect();
      const frac = Number(range.value) / Number(range.max);
      return { expected: rb.left + 12 + frac * (rb.width - 24), got: sb ? sb.left + sb.width / 2 : null };
    });
    expect(r.got, "2023-24 'complete map' tick").not.toBeNull();
    expect(Math.abs(r.got! - r.expected), `tick at ${r.got}, thumb centre at ~${r.expected}`).toBeLessThan(16);
  });
});

test.describe("V3 desktop, round 2", () => {
  test.skip(({ isMobile }) => isMobile, "desktop project only");

  test("V3-01 (round 2): + on every expandable group keeps focus on a node and announces it", async ({ page }) => {
    for (const id of ["PRODUCERS", "FACT", "HH", "NFC", "FC", "TAX", "SI"]) {
      await page.goto("/en/");
      await page.waitForLoadState("networkidle");
      await page.locator(`[data-mark="node"][data-node="${id}"]`).first().focus();
      await page.keyboard.press("+");
      await expect.poll(async () => (await active(page)).mark, { message: `focus after + on ${id}` }).toBe("node");
      expect((await active(page)).node, `focus moved to a part of ${id}, not back to ${id}`).not.toBe(id);
      await expect(page.locator("[data-map-svg] ~ [data-live-region]").first()).toContainText(/opened into its parts/);
    }
  });

  test("V3-03 (round 2): the centre of every node mark hits that node, also in a dense full map with the panel open", async ({ page }) => {
    for (const url of ["/en/", "/en/?p=full", "/en/?x=HH,TAX,PRDS,PROD,NFC,FC&s=TAX"]) {
      await page.goto(url);
      await page.waitForLoadState("networkidle");
      const miss = await page.evaluate(() =>
        [...document.querySelectorAll('[data-mark="node"]')].flatMap((g) => {
          g.scrollIntoView({ block: "center" });
          const v = g.querySelector("rect:not([data-node-hit])")!.getBoundingClientRect();
          const hit = g.querySelector("[data-node-hit]")?.getBoundingClientRect();
          const el = document.elementFromPoint(v.left + v.width / 2, v.top + v.height / 2);
          const bad: string[] = [];
          if (!hit || hit.width < 23.9 || hit.height < 23.9) bad.push(`${g.getAttribute("data-key")} hit area ${hit?.width}x${hit?.height}`);
          if (el?.closest('[data-mark="node"]') !== g) bad.push(`${g.getAttribute("data-key")} centre hits ${el?.closest("[data-key]")?.getAttribute("data-key")}`);
          return bad;
        }),
      );
      expect(miss, url).toEqual([]);
    }
  });

  test("V3-05 (round 2): every marker tick sits on its year's thumb position, and a click there selects that year", async ({ page }) => {
    await page.goto("/en/?view=ts&y=2015-16");
    await page.waitForLoadState("networkidle");
    const range = page.locator("[data-year-range]");
    await range.scrollIntoViewIfNeeded();
    const ticks = await page.evaluate(() => {
      const r = document.querySelector("[data-year-range]") as HTMLInputElement;
      const rb = r.getBoundingClientRect();
      const periods = [...document.querySelectorAll("[data-year-slider] select option")].map((o) => o.textContent!.trim());
      return [...document.querySelectorAll("[data-year-slider] [data-marker]")].map((t) => {
        const b = t.getBoundingClientRect();
        const i = periods.indexOf(t.getAttribute("data-marker")!);
        return { year: t.getAttribute("data-marker")!, x: b.left + b.width / 2, expected: rb.left + 12 + ((rb.width - 24) * i) / Number(r.max) };
      });
    });
    expect(ticks.length).toBeGreaterThan(0);
    for (const t of ticks) expect(Math.abs(t.x - t.expected), t.year).toBeLessThan(1.5);
    const box = (await range.boundingBox())!;
    const last = ticks[ticks.length - 1];
    await page.mouse.click(last.x, box.y + box.height / 2);
    await expect(range).toHaveAttribute("aria-valuetext", last.year);
  });

  test("V3-06 (round 2): after Next, Previous, Home and End the focused story button stays on screen", async ({ page }) => {
    for (const slug of ["deficit-funding", "gst-rupee", "remittance-dubai"]) {
      await page.goto(`/en/story/${slug}/`);
      await page.waitForLoadState("networkidle");
      await page.locator("[data-story-player] button", { hasText: /next/i }).focus();
      for (const key of ["Enter", "Enter", "Enter", "End", "Home"]) {
        await page.keyboard.press(key);
        await expect
          .poll(() => page.evaluate(() => { const b = document.activeElement!.getBoundingClientRect(); return b.top >= 0 && b.bottom <= innerHeight; }), { message: `${slug} after ${key}` })
          .toBe(true);
      }
    }
  });

  test("V3-07 (round 2): diagram labels are at least 12 px (groups) and 11 px (values) in every view", async ({ page }) => {
    for (const [w, url] of [[1280, "/en/?s=HH"], [1280, "/en/?p=full"], [1280, "/en/story/deficit-funding/?step=3"], [640, "/en/"], [640, "/en/?x=HH,TAX"]] as const) {
      await page.setViewportSize({ width: w, height: 800 });
      await page.goto(url);
      await page.waitForLoadState("networkidle");
      const small = await page.evaluate(() =>
        [...document.querySelectorAll<SVGSVGElement>("[data-map-svg]")]
          .filter((svg) => svg.getBoundingClientRect().width > 0)
          .flatMap((svg) => {
            const k = svg.getBoundingClientRect().width / svg.viewBox.baseVal.width;
            return [...svg.querySelectorAll("text")]
              .map((t) => ({ t: t.textContent, px: parseFloat(getComputedStyle(t).fontSize) * k, node: !!t.closest('[data-mark="node"]') }))
              .filter((x) => x.px < (x.node ? 11.95 : 10.95))
              .map((x) => `${x.t} ${x.px.toFixed(1)}px`);
          }),
      );
      expect(small, `${w} ${url}`).toEqual([]);
    }
  });

  test("V3-09 (still open): the two Producers copies have distinct accessible names", async ({ page }) => {
    test.fail(true, "V3-09 open: both copies are named identically");
    await page.goto("/en/");
    await page.waitForLoadState("networkidle");
    const names = await page.locator('[data-mark="node"][data-node="PRODUCERS"]').evaluateAll((els) => els.map((e) => e.getAttribute("aria-label")));
    expect(names).toHaveLength(2);
    expect(names[0]).not.toBe(names[1]);
  });

  test("V3-14 (still open, second half): series pages have no nested region with the same name", async ({ page }) => {
    test.fail(true, "V3-14 open: region 'Every year' contains a region with the same name");
    await page.goto("/en/series/F49/");
    await page.waitForLoadState("networkidle");
    const dup = await page.evaluate(() => {
      const name = (e: Element) => e.getAttribute("aria-label") ?? document.getElementById(e.getAttribute("aria-labelledby") ?? "")?.textContent?.trim();
      return [...document.querySelectorAll('section[aria-labelledby], [role="region"]')].filter((r) =>
        [...r.querySelectorAll('[role="region"], section[aria-labelledby]')].some((c) => name(c) === name(r)),
      ).length;
    });
    expect(dup).toBe(0);
  });
});

test.describe("V3 phone", () => {
  test.skip(({ isMobile }) => !isMobile, "phone project only");

  test("V3-02: phone node cards show an unclipped focus ring", async ({ page }) => {
    await page.goto("/en/");
    await page.waitForLoadState("networkidle");
    const b = page.locator("[data-node-card] button").nth(3);
    await b.focus();
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Tab");
    await expect(b).toBeFocused();
    const res = await focusRingUnclipped(page);
    expect(res.ok, res.why).toBe(true);
  });
});

test.describe("V3 phone, round 2", () => {
  test.skip(({ isMobile }) => !isMobile, "phone project only");

  test("V3-06 (round 2): on phones, Next brings the new step's heading into view", async ({ page }) => {
    await page.goto("/en/story/deficit-funding/");
    await page.waitForLoadState("networkidle");
    await page.locator("[data-story-player] button", { hasText: /next/i }).focus();
    for (let i = 0; i < 3; i++) {
      await page.keyboard.press("Enter");
      await expect
        .poll(() =>
          page.evaluate(() => {
            const h = document.querySelector("[data-story-player] section[data-step]:not([hidden]) :is(h2, h3)");
            const b = h?.getBoundingClientRect();
            return !!b && b.top >= 0 && b.top < innerHeight;
          }),
        )
        .toBe(true);
    }
  });

  test("V3-19 (new, low): the phone header links show the whole focus ring", async ({ page }) => {
    test.fail(true, "V3-19 open: the scrolling phone nav clips the top and bottom of the ring");
    await page.goto("/en/data/");
    await page.waitForLoadState("networkidle");
    const a = page.locator("header nav a", { hasText: "Stories" });
    await a.focus();
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Tab");
    await expect(a).toBeFocused();
    const res = await focusRingUnclipped(page);
    expect(res.ok, res.why).toBe(true);
  });

  test("V3-20 (new, low): story-map group labels do not overlap at 375 px", async ({ page }) => {
    test.fail(true, "V3-20 open: counter-scaled labels collide ('Compa…' over 'Taxes')");
    await page.goto("/en/story/gst-rupee/?step=2");
    await page.waitForLoadState("networkidle");
    const overlaps = await page.evaluate(() => {
      const svg = [...document.querySelectorAll("[data-map-svg]")].find((x) => x.getBoundingClientRect().width > 0)!;
      const rs = [...svg.querySelectorAll('[data-mark="node"] text')].map((t) => ({ t: t.textContent, r: t.getBoundingClientRect() }));
      const out: string[] = [];
      for (let i = 0; i < rs.length; i++)
        for (let j = i + 1; j < rs.length; j++) {
          const a = rs[i].r, b = rs[j].r;
          if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2) out.push(`${rs[i].t} / ${rs[j].t}`);
        }
      return out;
    });
    expect(overlaps).toEqual([]);
  });
});
