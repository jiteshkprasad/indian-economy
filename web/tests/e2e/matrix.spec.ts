// U4 matrix e2e (PLAN §5.3): the canvas renders; the table toggle shows <th scope>; the keyboard
// cursor moves and is announced; Enter zooms into a block and Esc zooms out; 13 × 13 by default
// at 375 px and 128 × 128 above 640 px. Counts come from the hierarchy contract (PLAN §3.2:
// 13 level-0 groups, 128 accounts; Goods & services has 8 children).
import { expect, test, type Page } from "@playwright/test";

const L0 = 13;
const ACCOUNTS = 128;
const PRDS_CHILDREN = 8;

async function open(page: Page) {
  await page.goto("/en/data/");
  const grid = page.locator('[role="application"][aria-roledescription="matrix"]');
  await expect(grid).toBeVisible();
  return grid;
}

const isPhone = (page: Page) => (page.viewportSize()?.width ?? 1280) < 640;

test.describe("matrix", () => {
  test("canvas renders cells and the default zoom fits the screen", async ({ page }) => {
    const grid = await open(page);
    const n = isPhone(page) ? L0 : ACCOUNTS;
    await expect(grid).toHaveAttribute("data-rows", String(n));
    await expect(grid).toHaveAttribute("data-cols", String(n));
    const canvas = page.getByTestId("sam-canvas");
    await expect(canvas).toBeVisible();
    const painted = await canvas.evaluate((el) => {
      const c = el as HTMLCanvasElement;
      const ctx = c.getContext("2d");
      if (!ctx || c.width === 0 || c.height === 0) return 0;
      const d = ctx.getImageData(0, 0, c.width, c.height).data;
      let k = 0;
      for (let i = 3; i < d.length; i += 4 * 7) if (d[i] > 0) k++;
      return k;
    });
    expect(painted).toBeGreaterThan(50);
    // devicePixelRatio-aware: the backing store is CSS size × dpr
    const ratio = await canvas.evaluate((el) => {
      const c = el as HTMLCanvasElement;
      return c.width / c.getBoundingClientRect().width / window.devicePixelRatio;
    });
    expect(ratio).toBeCloseTo(1, 1);
  });

  test("keyboard cursor moves, is announced, and Enter/Esc zoom in and out", async ({ page }) => {
    const grid = await open(page);
    const n = isPhone(page) ? L0 : ACCOUNTS;
    await expect(grid).toHaveAttribute("data-rows", String(n));
    await grid.focus();
    await expect(grid).toHaveAttribute("data-cursor", "0,0");
    await page.keyboard.press("ArrowRight");
    await expect(grid).toHaveAttribute("data-cursor", "0,1");
    await page.keyboard.press("ArrowDown");
    await expect(grid).toHaveAttribute("data-cursor", "1,1");
    const live = page.getByTestId("data-explorer").locator("[data-live-region]");
    await expect(live).toContainText(" pays ");
    // walk the grid row by row until a cell with a flow: its announcement has the value, share and label
    const cols = Number(await grid.getAttribute("data-cols"));
    for (let k = 0; k < 400 && !/of GDP/.test((await live.textContent()) ?? ""); k++) {
      const [, j] = ((await grid.getAttribute("data-cursor")) ?? "0,0").split(",").map(Number);
      if (j === cols - 1) {
        await page.keyboard.press("Home");
        await page.keyboard.press("ArrowDown");
      } else await page.keyboard.press("ArrowRight");
      await page.waitForTimeout(200);
    }
    await expect(live).toContainText("of GDP");
    await expect(live).toContainText(/₹/);
    // the info box follows the cursor
    await expect(page.locator('[data-source="cursor"]')).toBeVisible();

    // back to the top-left cell (Goods & services pays Goods & services in matrix order) and zoom in
    await page.keyboard.press("Control+Home");
    await expect(grid).toHaveAttribute("data-cursor", "0,0");
    await page.keyboard.press("Enter");
    await expect(grid).toHaveAttribute("data-rows", String(PRDS_CHILDREN));
    await expect(grid).toHaveAttribute("data-cols", String(PRDS_CHILDREN));
    await expect(live).toContainText(`${PRDS_CHILDREN} receivers by ${PRDS_CHILDREN} payers`);
    await page.keyboard.press("Escape");
    await expect(grid).toHaveAttribute("data-rows", String(n));
  });

  test("the table alternative has scoped headers, and T opens it", async ({ page }) => {
    const grid = await open(page);
    await grid.focus();
    await page.keyboard.press("t");
    const table = page.getByTestId("matrix-table");
    await expect(table).toBeVisible();
    await expect(page.getByRole("region", { name: /Matrix table/ })).toBeFocused();
    await expect(table.locator('thead th[scope="col"]')).toHaveCount(L0);
    await expect(table.locator('tbody th[scope="row"]')).toHaveCount(L0);
    // every non-empty cell carries a figure and a status badge
    const cells = table.locator("td[data-cell]");
    const k = await cells.count();
    expect(k).toBeGreaterThan(20);
    await expect(table.locator("td[data-cell] [data-num-value]")).toHaveCount(k);
    await expect(table.locator("td[data-cell] [data-status-split]")).toHaveCount(k);
    // switching back via the tab shows the heat-map again
    await page.getByRole("tab", { name: "Heat-map" }).click();
    await expect(page.getByTestId("sam-canvas")).toBeVisible();
  });

  test("zoom buttons and breadcrumbs: zoom into a block and back to the whole economy", async ({ page }) => {
    const grid = await open(page);
    await grid.focus();
    await page.getByRole("button", { name: "Zoom into this block" }).click();
    await expect(grid).toHaveAttribute("data-rows", String(PRDS_CHILDREN));
    await page.getByRole("button", { name: /^Up to Whole economy/ }).first().click();
    await expect(grid).not.toHaveAttribute("data-rows", String(PRDS_CHILDREN));
    await page.getByRole("button", { name: "Start again" }).click();
    const n = isPhone(page) ? L0 : ACCOUNTS;
    await expect(grid).toHaveAttribute("data-rows", String(n));
  });

  test("all non-zero cells list filters and lists every cell", async ({ page }) => {
    await open(page);
    const list = page.getByTestId("cells-list");
    await expect(list).toBeVisible();
    const total = Number(await list.getAttribute("aria-rowcount")) - 1;
    expect(total).toBeGreaterThan(100);
    await page.getByLabel("Receiver", { exact: true }).selectOption({ label: "Households" });
    const filtered = Number(await list.getAttribute("aria-rowcount")) - 1;
    expect(filtered).toBeGreaterThan(0);
    expect(filtered).toBeLessThan(total);
    await expect(list.locator("tbody tr[data-cell]").first()).toBeVisible();
  });

  test("downloads list every data file with its fingerprint", async ({ page }) => {
    await open(page);
    const rows = page.getByTestId("downloads").locator("tbody tr");
    expect(await rows.count()).toBeGreaterThan(5);
    const href = await rows.first().locator("a").getAttribute("href");
    expect(href).toMatch(/^\/data(-fixture)?\/\d{4}-\d{2}\.([0-9a-f]{10}|fixture0000)\//);
    const res = await page.request.get(href!);
    expect(res.status()).toBe(200);
  });
});
