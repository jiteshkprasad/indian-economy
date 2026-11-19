import { expect, test } from "@playwright/test";
import { readData, watchConsole } from "./helpers";

// Round 3 (founder, 19 Nov 2026): the home page's rupee tour and guessing game, and the shared
// question page. Figures shown must be the exported story figures, never typed numbers.

type Fig = { value: number; unit: string };
const story = (slug: string) => readData<{ figures: Record<string, Fig> }>(`stories/${slug}.json`).figures;

test.describe("home play", () => {
  test("the rupee tour steps through a story with exported figures", async ({ page }) => {
    const con = watchConsole(page);
    await page.goto("/en/");
    const tour = page.locator("[data-tour]");
    await expect(tour).toHaveAttribute("data-tour-state", "overview");
    await tour.locator('[data-chip="gst-rupee"]').click();
    await expect(tour).toHaveAttribute("data-tour-state", "gst-rupee:0");
    const gst = story("gst-rupee");
    const first = tour.locator("[data-tour-caption] [data-num-value]").first();
    expect(Number(await first.getAttribute("data-num-value"))).toBe(gst.gst_total.value);
    await expect(tour.locator("[data-tour-caption] [data-status-split]").first()).toBeVisible();
    await tour.locator("[data-tour-next]").click();
    await expect(tour).toHaveAttribute("data-tour-state", "gst-rupee:1");
    // the map draws the followed flow, and the list names it
    await expect(tour.locator("[data-map-svg]")).toBeVisible();
    await expect(tour.locator("[data-tour-flows] [data-link-id]").first()).toBeVisible();
    con.assertClean((p) => expect(p).toEqual([]));
  });

  test("a guess reveals the exported answer and opens it on the map", async ({ page }) => {
    const con = watchConsole(page);
    await page.goto("/en/");
    const game = page.locator("[data-guess]");
    await expect(game).toHaveAttribute("data-guess-q", "gst-states");
    await game.locator("[data-guess-slider]").fill("40");
    await game.locator("[data-guess-check]").click();
    const reveal = game.locator("[data-guess-reveal]");
    await expect(reveal).toHaveAttribute("data-guess-reveal", "far");
    const answer = Number(await reveal.locator("[data-num-value]").first().getAttribute("data-num-value"));
    expect(answer).toBe(story("gst-rupee").gst_to_states_kept_per100.value);
    await game.locator("[data-guess-map]").click();
    await expect(page.locator("[data-tour]")).toHaveAttribute("data-tour-state", "gst-rupee:3");
    await game.locator("[data-guess-next]").click();
    await expect(game).toHaveAttribute("data-guess-q", "gst-households");
    con.assertClean((p) => expect(p).toEqual([]));
  });

  test("a shared question shows the friend's guess, then the answer", async ({ page }) => {
    const con = watchConsole(page);
    await page.goto("/en/guess/bonds-households/?g=30");
    await expect(page.locator("h1")).toHaveCount(1);
    const game = page.locator("[data-guess]");
    await expect(game).toHaveAttribute("data-guess-q", "bonds-households");
    await expect(game.locator("[data-guess-friend]")).toContainText("₹30.0");
    await game.locator("[data-guess-check]").click();
    const answer = Number(await game.locator("[data-guess-reveal] [data-num-value]").first().getAttribute("data-num-value"));
    expect(answer).toBe(story("deficit-funding").gsec_hh_per100.value);
    // the answer is not in the page's metadata
    const desc = (await page.locator('meta[name="description"]').getAttribute("content")) ?? "";
    expect(desc).not.toContain(String(answer).slice(0, 3));
    con.assertClean((p) => expect(p).toEqual([]));
  });
});
