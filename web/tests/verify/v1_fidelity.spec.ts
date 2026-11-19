import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

// V1 data fidelity (PLAN §7, row V1). Owned by the verifier, not by any builder unit.
// Expectations come from tests/verify/test_phase3_data_fidelity.py (DuckDB on the parquet files, its own
// aggregation and its own Python formatter); regenerate them with
//   uv run python tests/verify/test_phase3_data_fidelity.py
// This spec imports nothing from src/: it reads what the rendered page shows and compares it with
// those files. Everything it saw is also written to <outputDir>/v1_observed.json for the Python side.
// Run: npx playwright test -c tests/verify/playwright.v1.config.ts

const HERE = path.dirname(fileURLToPath(import.meta.url));
type State = {
  kind: "link" | "node"; id: string; preset: "simple" | "full"; x: string[];
  value: number; share: number; value_text: string; share_text: string; split?: string; total?: string;
  moves?: number[];
};
type FigExp = { value: number; unit: string; text: string; split: string; total: string };
const PS = JSON.parse(fs.readFileSync(path.join(HERE, "panel_states.json"), "utf8"));
// round 2: the 30 seeded states plus every top-level node in both presets (V1-05 regression guard)
const STATES: State[] = [...PS.states, ...(PS.nodes ?? []).map((n: State) => ({ ...n, all: true }))];
const STORIES: Record<string, Record<string, FigExp>> = JSON.parse(fs.readFileSync(path.join(HERE, "story_expect.json"), "utf8"));

const observed: Record<string, unknown> = {};
test.afterAll(async ({}, info) => {
  const file = path.join(info.project.outputDir, `v1_observed.${process.pid}.json`);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(observed, null, 1));
});

test.describe("V1 panel states", () => {
  for (const st of STATES) {
    const name = `${(st as { all?: boolean }).all ? "all-nodes " : ""}${st.kind} ${st.id} (${st.preset}${st.x.length ? ` x=${st.x.join(",")}` : ""})`;
    test(name, async ({ page }) => {
      // V1-05 (the simple-view SI node panel) was a test.fail in round 1; fixed in round 2, so it runs normally.
      const q = new URLSearchParams();
      if (st.x.length) q.set("x", st.x.join(","));
      else if (st.preset !== "simple") q.set("p", st.preset);
      q.set("s", st.id);
      await page.goto(`/en/?${q.toString()}`);
      const panel = page.locator(`[data-flow-panel][data-id="${st.id}"]`);
      await expect(panel).toBeVisible();
      await page.waitForLoadState("networkidle");
      const nums = await panel.locator("[data-num-value]").evaluateAll((els) =>
        els.map((e) => ({ value: Number(e.getAttribute("data-num-value")), fmt: e.getAttribute("data-num-fmt"), text: (e.textContent ?? "").trim() })),
      );
      const valueEl = panel.locator("[data-panel-value] [data-num-value]").first();
      const shareEl = panel.locator("[data-panel-share] [data-num-value]").first();
      const got = {
        value: Number(await valueEl.getAttribute("data-num-value")),
        value_text: ((await valueEl.textContent()) ?? "").trim(),
        share_text: (await shareEl.count()) ? ((await shareEl.textContent()) ?? "").trim() : null,
        total: await panel.locator("[data-status-total]").first().getAttribute("data-status-total"),
        split: await panel.locator("[data-status-split]").first().getAttribute("data-status-split"),
        text: ((await panel.innerText()) ?? "").replace(/\s+/g, " ").slice(0, 4000),
        nums,
      };
      observed[name] = { expected: st, got };
      expect.soft(Math.abs(got.value - st.value), `value ${got.value} vs ${st.value}`).toBeLessThanOrEqual(0.011);
      expect.soft(got.value_text).toBe(st.value_text);
      expect.soft(got.share_text).toBe(st.share_text);
      if (st.kind === "link") {
        expect.soft(got.total ?? "", "total label").toBe(st.total ?? "");
        expect.soft(got.split, "split label").toBe(st.split);
        // V1-01: every "before → after (x%)" in the entry list is a fraction of the prior that one of this link's
        // entries actually moved by (expected moves from the parquet, not from the export).
        const moves = await panel.locator('[data-entries] [data-num-fmt="pct"]').evaluateAll((els) =>
          els.map((e) => Number(e.getAttribute("data-num-value"))),
        );
        const unmatched = moves.filter((m) => !(st.moves ?? []).some((w) => Math.abs(w - m) <= 1e-4));
        expect.soft(unmatched, `entry moves not among this link's entries' moves`).toEqual([]);
        (observed[name] as { moves?: number[] }).moves = moves;
      }
    });
  }
});

test.describe("V1 stories", () => {
  for (const [slug, figs] of Object.entries(STORIES)) {
    test(`story ${slug}`, async ({ page }) => {
      await page.goto(`/en/story/${slug}/`);
      await page.waitForLoadState("networkidle");
      const shown = await page.locator("[data-fig-id]").evaluateAll((els) =>
        els.map((e) => {
          const badge = e.parentElement?.querySelector("[data-status-split]");
          return {
            id: e.getAttribute("data-fig-id") ?? "",
            value: Number(e.getAttribute("data-num-value")),
            text: (e.textContent ?? "").trim(),
            split: badge?.getAttribute("data-status-split") ?? null,
            total: badge?.getAttribute("data-status-total") ?? null,
          };
        }),
      );
      observed[`story ${slug}`] = shown;
      expect(shown.length).toBeGreaterThan(0);
      for (const s of shown) {
        const e = figs[s.id];
        expect.soft(e, `figure ${s.id} unknown`).toBeTruthy();
        if (!e) continue;
        expect.soft(s.text, `${s.id} text`).toBe(e.text);
        expect.soft(s.split, `${s.id} split`).toBe(e.split);
        expect.soft(s.total ?? "", `${s.id} total`).toBe(e.total);
      }
    });
  }
});
