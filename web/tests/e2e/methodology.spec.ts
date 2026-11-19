// U6 methodology e2e (PLAN §5.3): every source in provenance.sources is listed; withheld
// sources have no link, and no link on the page points at an RBI host; the anchors other
// pages link to exist; every bound figure shows exactly format(value) of its summary.json
// value; the page does not scroll sideways on a phone.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { REQUIRED_ANCHORS, SECTIONS } from "../../src/components/methodology/sections";
import { resolveDataRoot } from "../../src/data/root.mjs";
import type { DataIndex, Provenance } from "../../src/data/types";
import { format, type FmtKind } from "../../src/lib/format";

const WEB_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

function readData<T>(file: string): T {
  const root = resolveDataRoot(WEB_DIR);
  const index = JSON.parse(fs.readFileSync(path.join(root.dir, "index.json"), "utf8")) as DataIndex;
  if (file === "index.json") return index as T;
  return JSON.parse(fs.readFileSync(path.join(root.dir, index.data_version, file), "utf8")) as T;
}

const RBI = /(^|\.)rbi\.org\.in$/i;

test.describe("methodology page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/en/methodology/");
  });

  test("has its heading, the not-a-forecast note and every section anchor", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    for (const sec of SECTIONS) {
      await expect(page.locator(`section#${sec.id}`), sec.id).toHaveCount(1);
      await expect(page.locator(`section#${sec.id} h2`).first(), sec.id).toBeVisible();
    }
    for (const id of REQUIRED_ANCHORS) {
      await expect(page.locator(`#${id}`), id).toHaveCount(1);
    }
    // the table of contents links to every section
    for (const sec of SECTIONS) {
      await expect(page.locator(`nav a[href="#${sec.id}"]`), sec.id).toHaveCount(1);
    }
  });

  test("lists every source, and never links an RBI page", async ({ page }) => {
    const prov = readData<Provenance>("provenance.json");
    const ids = Object.keys(prov.sources);
    expect(ids.length).toBeGreaterThan(0);
    const listed = await page.locator("[data-source-id]").evaluateAll((els) => els.map((e) => e.getAttribute("data-source-id")));
    expect([...listed].sort()).toEqual([...ids].sort());

    for (const [id, src] of Object.entries(prov.sources)) {
      if (src.link_mode !== "withheld") continue;
      const card = page.locator(`[data-source-id="${id}"]`);
      await expect(card.locator("a[href]"), id).toHaveCount(0);
      await expect(card).toHaveAttribute("data-link-mode", "withheld");
    }

    const hrefs = await page.locator("a[href]").evaluateAll((els) => els.map((e) => (e as HTMLAnchorElement).href));
    for (const h of hrefs) {
      const host = new URL(h).hostname;
      expect(RBI.test(host), h).toBe(false);
    }
  });

  test("every bound figure shows format(value) of summary.json", async ({ page }) => {
    const figs = await page.locator("[data-fig-path][data-num-value]").evaluateAll((els) =>
      els.map((e) => ({
        path: e.getAttribute("data-fig-path")!,
        value: Number(e.getAttribute("data-num-value")),
        fmt: e.getAttribute("data-num-fmt")!,
        text: (e.textContent ?? "").trim(),
      })),
    );
    expect(figs.length).toBeGreaterThan(20);
    const summary = readData<Record<string, unknown>>("summary.json");
    for (const f of figs) {
      let cur: unknown = summary;
      for (const part of f.path.split(".")) cur = (cur as Record<string, unknown>)[part];
      const expected = typeof cur === "number" ? cur : (cur as { value: number }).value;
      expect(f.value, f.path).toBe(expected);
      expect(f.text, f.path).toBe(format(expected, f.fmt as FmtKind));
    }
    // text bindings (FY labels) show their summary.json string
    const texts = await page.locator("[data-fig-path]:not([data-num-value])").evaluateAll((els) =>
      els.map((e) => ({ path: e.getAttribute("data-fig-path")!, text: (e.textContent ?? "").trim() })),
    );
    for (const t of texts) {
      let cur: unknown = summary;
      for (const part of t.path.split(".")) cur = (cur as Record<string, unknown>)[part];
      expect(t.text, t.path).toBe(cur);
    }
  });

  test("shows the data version this page was built from", async ({ page }) => {
    const index = readData<DataIndex>("index.json");
    await expect(page.locator(`section#data-version [data-data-version="${index.data_version}"]`)).toHaveCount(1);
  });

  test("does not scroll sideways", async ({ page }) => {
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
