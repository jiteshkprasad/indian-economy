import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { builtData, OUT, WEB } from "./helpers";

// PLAN §5.3 and §4.14: vercel.json parses and carries the deploy rules; the data
// folder names in out/ match index.json; the local server applies the same headers.
const vercel = JSON.parse(fs.readFileSync(path.join(WEB, "vercel.json"), "utf8"));

test.describe("headers and data folders", () => {
  test.skip(({ isMobile }) => isMobile, "desktop project only");

  test("vercel.json has the §4.14 rules", () => {
    expect(vercel.framework).toBeNull();
    expect(vercel.outputDirectory).toBe("out");
    expect(vercel.buildCommand).toBe("npm run build");
    expect(vercel.redirects).toEqual([{ source: "/", destination: "/en/", permanent: true }]);
    // /en -> /en/ on Vercel too, as next.config.ts trailingSlash does (verify V4-05)
    expect(vercel.trailingSlash).toBe(true);
    const by = Object.fromEntries(vercel.headers.map((h: { source: string; headers: unknown[] }) => [h.source, h.headers]));
    // Content-hashed build output is immutable; with framework: null Vercel adds no rule of its own (verify V4-05)
    expect(by["/_next/static/(.*)"]).toEqual([{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }]);
    expect(by["/data/(.*)"]).toEqual([{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }]);
    expect(by["/data/index.json"]).toEqual([{ key: "Cache-Control", value: "public, max-age=0, must-revalidate" }]);
    const order = vercel.headers.map((h: { source: string }) => h.source);
    expect(order.indexOf("/data/index.json")).toBeGreaterThan(order.indexOf("/data/(.*)"));
    const all = Object.fromEntries((by["/(.*)"] as Array<{ key: string; value: string }>).map((h) => [h.key, h.value]));
    expect(all["Content-Security-Policy"]).toContain("default-src 'self'");
    expect(all["Content-Security-Policy"]).toContain("frame-ancestors 'none'");
    expect(all["Content-Security-Policy"]).not.toContain("unsafe-eval");
    expect(all["X-Content-Type-Options"]).toBe("nosniff");
    expect(all["Referrer-Policy"]).toBe("strict-origin-when-cross-origin");
    expect(all["Permissions-Policy"]).toBe("camera=(), microphone=(), geolocation=()");
  });

  test("out/ ships exactly one data version, the one index.json names", () => {
    const { index, base } = builtData();
    const dir = path.join(OUT, base.slice(1));
    const versions = fs.readdirSync(dir).filter((n) => /^\d{4}-\d{2}\.([0-9a-f]{10}|fixture0000)$/.test(n));
    expect(versions).toEqual([index.data_version]);
    for (const f of Object.keys(index.files)) expect(fs.existsSync(path.join(dir, index.data_version, f)), f).toBe(true);
    if (base === "/data") expect(fs.existsSync(path.join(OUT, "data-fixture"))).toBe(false);
  });

  test("the local server applies the CSP and the data cache headers", async ({ request }) => {
    const { index, base } = builtData();
    const home = await request.get("/en/");
    expect(home.headers()["content-security-policy"]).toContain("default-src 'self'");
    expect(home.headers()["x-content-type-options"]).toBe("nosniff");
    if (base === "/data") {
      const f = Object.keys(index.files)[0];
      const res = await request.get(`/data/${index.data_version}/${f}`);
      expect(res.headers()["cache-control"]).toBe("public, max-age=31536000, immutable");
    }
    // a content-hashed chunk that the home page references
    const html = await home.text();
    const chunk = html.match(/\/_next\/static\/chunks\/[\w.-]+\.js/)?.[0];
    expect(chunk, "a /_next/static chunk referenced by /en/").toBeTruthy();
    const js = await request.get(chunk!);
    expect(js.status()).toBe(200);
    expect(js.headers()["cache-control"]).toBe("public, max-age=31536000, immutable");
    const page = await request.get("/en/methodology/");
    expect(page.headers()["cache-control"] ?? "").not.toContain("immutable");
    const root = await request.get("/", { maxRedirects: 0 });
    expect(root.status()).toBe(308);
    expect(root.headers()["location"]).toBe("/en/");
  });
});
