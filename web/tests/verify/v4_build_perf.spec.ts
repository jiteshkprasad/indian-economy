import fs from "node:fs";
import http from "node:http";
import type { AddressInfo } from "node:net";
import path from "node:path";
import zlib from "node:zlib";
import { expect, test, type Page } from "@playwright/test";
import { STORY_SLUGS } from "../../src/lib/story/registry";
import { OUT, WEB } from "../e2e/helpers";

// V4 build / performance checks (docs/phase3/verify/V4_build_perf.md), written by the V4 verifier, who built
// nothing in Phase 3. Each test names the finding it guards. A fixed finding's test passes normally; a finding
// that is still open is marked test.fail(), so it turns red once fixed and the mark must then go.
//
// V4-02 and V4-03 only showed under compressed delivery with a warm connection (what Vercel serves), which the
// e2e suite's uncompressed serve-out.mjs never produces. So this spec serves web/out/ itself, like V4's
// docs/phase3/verify/V4_scripts/vserve.mjs: vercel.json redirects and headers (last matching rule wins per
// key), directory index.html, 404.html, brotli or gzip for text types.

const vercel = JSON.parse(fs.readFileSync(path.join(WEB, "vercel.json"), "utf8")) as {
  redirects: { source: string; destination: string; permanent: boolean }[];
  headers: { source: string; headers: { key: string; value: string }[] }[];
};
const rx = (s: string) => new RegExp("^" + s.replace(/\(\.\*\)/g, "(.*)") + "$");
const TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".txt": "text/plain; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
};

/** vercel.json headers for a path, last matching rule winning per key (lower-cased keys). */
function vercelHeaders(p: string): Record<string, string> {
  const h: Record<string, string> = {};
  for (const rule of vercel.headers) if (rx(rule.source).test(p)) for (const kv of rule.headers) h[kv.key.toLowerCase()] = kv.value;
  return h;
}

let server: http.Server | undefined;
let VB = ""; // the compressing server's origin

test.beforeAll(async () => {
  test.skip(!fs.existsSync(path.join(OUT, "en", "index.html")), "web/out/ not built: run `npm --prefix web run build`");
  server = http.createServer((req, res) => {
    const p = decodeURIComponent(new URL(req.url ?? "/", "http://x").pathname);
    const hdrs = vercelHeaders(p);
    for (const r of vercel.redirects)
      if (rx(r.source).test(p)) {
        res.writeHead(r.permanent ? 308 : 307, { ...hdrs, location: r.destination });
        return res.end();
      }
    let f = path.join(OUT, p);
    let status = 200;
    if (fs.existsSync(f) && fs.statSync(f).isDirectory()) {
      if (!p.endsWith("/")) {
        res.writeHead(308, { location: p + "/" });
        return res.end();
      }
      f = path.join(f, "index.html");
    }
    if (!fs.existsSync(f)) {
      f = path.join(OUT, "404.html");
      status = 404;
    }
    let body: Buffer = fs.readFileSync(f);
    const ct = TYPES[path.extname(f)] ?? "application/octet-stream";
    const ae = String(req.headers["accept-encoding"] ?? "");
    const h: Record<string, string | number> = { ...hdrs, "content-type": ct };
    if (/text|javascript|json|svg/.test(ct)) {
      if (ae.includes("br")) {
        body = zlib.brotliCompressSync(body);
        h["content-encoding"] = "br";
      } else if (ae.includes("gzip")) {
        body = zlib.gzipSync(body);
        h["content-encoding"] = "gzip";
      }
      h["vary"] = "Accept-Encoding";
    }
    h["content-length"] = body.length;
    res.writeHead(status, h);
    res.end(req.method === "HEAD" ? undefined : body);
  });
  await new Promise<void>((ok) => server!.listen(0, "127.0.0.1", () => ok()));
  VB = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

test.afterAll(async () => {
  if (server) await new Promise<void>((ok) => server!.close(() => ok()));
});

const ROUTES = [
  "/en/",
  "/en/story/",
  ...STORY_SLUGS.map((s) => `/en/story/${s}/`),
  "/en/data/",
  "/en/methodology/",
  "/en/flow/CEN--HH/",
  "/en/series/F01/",
  "/en/?y=2010-11",
  "/en/no-such-page/",
];

function isRsc(url: string, headers: Record<string, string>): boolean {
  return /\.txt(\?|$)/.test(url) || url.includes("_rsc=") || "rsc" in headers || "next-router-prefetch" in headers;
}

async function scrollThrough(page: Page) {
  for (let i = 0; i < 12; i++) {
    await page.mouse.wheel(0, 700);
    await page.waitForTimeout(100);
  }
}

test.describe("V4 build and performance", () => {
  test("V4-02: no hydration failure on sequential loads in one context, compressed delivery", async ({ browser, isMobile }) => {
    test.skip(isMobile, "desktop project only (the defect was not viewport-dependent)");
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const failures: string[] = [];
    for (let pass = 0; pass < 2; pass++)
      for (const r of ROUTES) {
        const page = await ctx.newPage();
        const errors: string[] = [];
        page.on("pageerror", (e) => errors.push(e.message));
        await page.goto(VB + r, { waitUntil: "networkidle" });
        await page.waitForTimeout(700);
        if (errors.some((e) => /#418|#423|hydrat/i.test(e))) failures.push(`${r}: ${errors.join(" | ").slice(0, 200)}`);
        await page.close();
      }
    await ctx.close();
    expect(failures).toEqual([]);
  });

  test("V4-03: story pages do not shift after hydration (compressed delivery)", async ({ browser, isMobile }) => {
    const sizes = isMobile ? [[375, 812], [412, 823]] : [[1280, 800]];
    const bad: string[] = [];
    for (const [width, height] of sizes) {
      const ctx = await browser.newContext({ viewport: { width, height }, isMobile, hasTouch: isMobile, deviceScaleFactor: isMobile ? 1.75 : 1 });
      for (const slug of STORY_SLUGS) {
        const page = await ctx.newPage();
        await page.addInitScript(() => {
          const w = window as unknown as { __cls: number };
          w.__cls = 0;
          new PerformanceObserver((list) => {
            for (const e of list.getEntries() as unknown as { value: number; hadRecentInput: boolean }[]) if (!e.hadRecentInput) w.__cls += e.value;
          }).observe({ type: "layout-shift", buffered: true });
        });
        await page.goto(`${VB}/en/story/${slug}/`, { waitUntil: "networkidle" });
        await page.waitForTimeout(1200);
        const cls = await page.evaluate(() => (window as unknown as { __cls: number }).__cls);
        if (cls >= 0.05) bad.push(`${width}px ${slug}: CLS ${cls.toFixed(3)}`);
        await page.close();
      }
      await ctx.close();
    }
    expect(bad).toEqual([]);
  });

  test("V4-04: no RSC payload is prefetched on view, scroll or hover", async ({ page }) => {
    const fetched: string[] = [];
    page.on("request", (req) => {
      if (isRsc(req.url(), req.headers())) fetched.push(req.url().replace(VB, ""));
    });
    for (const r of ["/en/", "/en/story/", "/en/data/", "/en/methodology/", "/en/flow/CEN--HH/", "/en/series/F01/"]) {
      await page.goto(VB + r, { waitUntil: "networkidle" });
      await scrollThrough(page);
      for (const a of (await page.locator("header a[href^='/'], [data-story-card]").all()).slice(0, 20)) {
        await a.hover({ timeout: 1000 }).catch(() => undefined);
      }
      await page.waitForTimeout(800);
    }
    expect(fetched).toEqual([]);
  });

  test("V4-04: a click still navigates softly and fetches only the one payload it needs", async ({ page, isMobile }) => {
    test.skip(isMobile, "desktop project only");
    const fetched: string[] = [];
    page.on("request", (req) => {
      if (isRsc(req.url(), req.headers())) fetched.push(new URL(req.url()).pathname);
    });
    await page.goto(`${VB}/en/`, { waitUntil: "networkidle" });
    await page.evaluate(() => ((window as unknown as { __kept: number }).__kept = 1));
    const slug = STORY_SLUGS[0];
    await page.locator(`a[href="/en/story/${slug}/"]`).first().click();
    await page.waitForURL(new RegExp(`/en/story/${slug}/$`));
    await expect(page.locator("h1").first()).toBeVisible();
    expect(await page.evaluate(() => (window as unknown as { __kept?: number }).__kept)).toBe(1); // no full reload
    expect(fetched.every((p) => p.startsWith(`/en/story/${slug}/`)), fetched.join(", ")).toBe(true);
    expect(fetched.length).toBeGreaterThan(0);
  });

  test("V4-05: every /_next/static file is served immutable; HTML never is", async ({ request, isMobile }) => {
    test.skip(isMobile, "desktop project only");
    const files: string[] = [];
    const walk = (d: string) => {
      for (const e of fs.readdirSync(d, { withFileTypes: true })) {
        const p = path.join(d, e.name);
        if (e.isDirectory()) walk(p);
        else files.push("/" + path.relative(OUT, p).split(path.sep).join("/"));
      }
    };
    walk(path.join(OUT, "_next", "static"));
    expect(files.length).toBeGreaterThan(10);
    const notImmutable = files.filter((f) => vercelHeaders(f)["cache-control"] !== "public, max-age=31536000, immutable");
    expect(notImmutable).toEqual([]);
    for (const r of ["/en/", "/en/story/", "/en/flow/CEN--HH/", "/404.html"])
      expect(vercelHeaders(r)["cache-control"] ?? "", r).not.toContain("immutable");
    // and the rule as served (the emulating server), for one chunk the home page loads
    const html = await (await request.get(`${VB}/en/`)).text();
    const chunk = html.match(/\/_next\/static\/chunks\/[\w.-]+\.js/)?.[0];
    const res = await request.get(`${VB}${chunk}`);
    expect(res.headers()["cache-control"]).toBe("public, max-age=31536000, immutable");
  });

  // V4-06 (low, still open): serve-out.mjs, the e2e and `npm run start:out` server, does not compress, so a
  // Lighthouse run against it reports a misleading Performance (about 0.72) and LCP (about 6.6 s).
  test("V4-06: the local serve-out server compresses text responses", async ({ request, baseURL, isMobile }) => {
    test.skip(isMobile, "desktop project only");
    test.fail(true, "V4-06 still open: serve-out.mjs sends no Content-Encoding");
    const res = await request.get(`${baseURL}/en/`, { headers: { "accept-encoding": "br, gzip" } });
    expect(res.headers()["content-encoding"] ?? "").toMatch(/br|gzip/);
  });
});
