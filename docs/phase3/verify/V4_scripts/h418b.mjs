import { chromium } from "@playwright/test";
const B = process.argv[2]; const shared = process.argv[3] === "shared";
const routes = ["/en/", "/en/story/", "/en/story/gst-rupee/", "/en/story/remittance-dubai/", "/en/story/deficit-funding/", "/en/data/", "/en/methodology/", "/en/flow/CEN--HH/", "/en/series/F01/", "/en/?y=2010-11"];
const browser = await chromium.launch(); const hits = {};
let ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
for (let k = 0; k < 4; k++) for (const r of routes) {
  if (!shared) { await ctx.close(); ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } }); }
  const page = await ctx.newPage(); let hit = 0;
  page.on("pageerror", (e) => { if (e.message.includes("418")) hit = 1; else console.log("other", e.message.slice(0, 100)); });
  await page.goto(B + r, { waitUntil: "networkidle" }); await page.waitForTimeout(1500);
  hits[r] = (hits[r] || 0) + hit; await page.close();
}
console.log(shared ? "shared" : "fresh", JSON.stringify(hits)); await browser.close();
