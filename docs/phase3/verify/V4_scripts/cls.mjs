import { chromium } from "@playwright/test";
const B = process.argv[2]; const browser = await chromium.launch();
for (const [w, h] of [[412, 823], [375, 812], [1280, 800]]) for (const r of ["/en/story/gst-rupee/", "/en/story/deficit-funding/"]) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, isMobile: w < 500, deviceScaleFactor: w < 500 ? 1.75 : 1 });
  const page = await ctx.newPage();
  await page.addInitScript(() => { window.__s = []; new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__s.push([Math.round(e.startTime), +e.value.toFixed(3), e.sources?.map((s) => s.node?.className?.toString().slice(0, 40) + ` ${s.previousRect.height}->${s.currentRect.height} y${s.previousRect.y}->${s.currentRect.y}`)]); }).observe({ type: "layout-shift", buffered: true }); });
  await page.goto(B + r, { waitUntil: "networkidle" }); await page.waitForTimeout(1500);
  console.log(w, r, JSON.stringify(await page.evaluate(() => window.__s)));
  await ctx.close();
}
await browser.close();
