import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { noteFixture, routeTypes } from "./helpers";

// PLAN §5.3: axe with WCAG 2.0/2.1/2.2 A and AA tags on every route type, in light
// and dark, at both viewports (the two Chromium projects), plus map states.
//
// Target size (2.5.8): node marks carry a >= 24 x 24 px hit rect (V3-03), so they are
// checked like any other target. Ribbons ([data-mark="link"]) can be thinner than 24 px;
// they rely on the WCAG 2.5.8 "equivalent" exception: the same function is always
// available on the same page through the list/table alternative, whose targets are
// >= 24 px (PLAN §4.5.10, proposed D3-17). So `target-size` runs separately with only
// [data-mark="link"] excluded; every other rule runs on the whole page.
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function audit(page: Page, label: string) {
  const main = await new AxeBuilder({ page }).withTags(TAGS).disableRules(["target-size"]).analyze();
  const target = await new AxeBuilder({ page }).withRules(["target-size"]).exclude('[data-mark="link"]').analyze();
  const violations = [...main.violations, ...target.violations].map(
    (v) => `${v.id} (${v.impact}): ${v.help}\n    ${v.nodes.slice(0, 5).map((n) => n.target.join(" ")).join("\n    ")}`,
  );
  expect(violations, `${label}\n${violations.join("\n")}`).toEqual([]);
}

const routes = [...routeTypes(), "/en/no-such-page/"];
const states = [
  { name: "map with a link panel open", url: "/en/?s=HH--PRODUCERS" },
  { name: "map with a node panel open", url: "/en/?s=HH" },
  { name: "map table open", url: "/en/?t=table" },
  { name: "full map with a group expanded", url: "/en/?x=HH&s=HH.RUR--PRDS" },
  { name: "top-flows view", url: "/en/?y=2004-05" },
];

for (const scheme of ["light", "dark"] as const) {
  test.describe(`axe, ${scheme}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    });
    for (const route of routes) {
      test(`${route}`, async ({ page }, info) => {
        noteFixture(info);
        await page.goto(route);
        await page.waitForLoadState("networkidle");
        await audit(page, `${route} (${scheme})`);
      });
    }
    for (const s of states) {
      test(`state: ${s.name}`, async ({ page }, info) => {
        noteFixture(info);
        await page.goto(s.url);
        await page.waitForLoadState("networkidle");
        await audit(page, `${s.url} (${scheme})`);
      });
    }
    test("state: phone view with a node opened", async ({ page, isMobile }, info) => {
      test.skip(!isMobile, "phone project only");
      noteFixture(info);
      await page.goto("/en/");
      await page.waitForLoadState("networkidle");
      // The phone map is a list of node cards (PLAN §4.5.9); open the first one.
      const card = page.locator("[data-node-card] button, [data-node-card][role=button], [data-node-card] summary").first();
      await expect(card, "phone map node card ([data-node-card], U3)").toBeVisible();
      await card.click();
      await audit(page, `phone node opened (${scheme})`);
    });
  });
}
