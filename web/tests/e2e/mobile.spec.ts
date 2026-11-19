import { expect, test } from "@playwright/test";
import { noteFixture, routeTypes } from "./helpers";

// PLAN §5.3 at 375 px: no horizontal scroll; every interactive element outside
// [data-mark] is >= 24x24 px or meets the WCAG 2.5.8 spacing exception. Inline
// links inside running text are exempt (2.5.8 "inline" exception). Diagram marks
// ([data-mark]) rely on the "equivalent" exception (see a11y.spec.ts).
test.describe("mobile", () => {
  test.skip(({ isMobile }) => !isMobile, "phone project only");

  for (const route of routeTypes()) {
    test(`${route}`, async ({ page }, info) => {
      noteFixture(info);
      await page.goto(route);
      await page.waitForLoadState("networkidle");
      const scroll = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, w: window.innerWidth }));
      expect(scroll.sw, `horizontal scroll on ${route}`).toBeLessThanOrEqual(scroll.w);

      const failures = await page.evaluate(() => {
        const sel = 'a[href], button, input:not([type="hidden"]), select, textarea, summary, [role="button"], [role="link"], [role="tab"], [role="checkbox"], [role="switch"], [role="slider"], [tabindex]:not([tabindex="-1"])';
        const visible = (el: Element) => {
          const r = el.getBoundingClientRect();
          const cs = getComputedStyle(el);
          return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none";
        };
        const isInlineInText = (el: Element) => {
          if (el.tagName !== "A") return false;
          if (getComputedStyle(el).display !== "inline") return false;
          const block = el.closest("p, li, td, dd, figcaption, blockquote");
          if (!block) return false;
          return (block.textContent ?? "").trim().length > (el.textContent ?? "").trim().length + 10;
        };
        const els = [...document.querySelectorAll(sel)].filter((el) => !el.closest("[data-mark]") && !el.closest(".visually-hidden") && visible(el));
        // the skip link is off-screen until focused
        const targets = els.filter((el) => el.getBoundingClientRect().bottom > -50);
        const rects = targets.map((el) => el.getBoundingClientRect());
        const small = targets.map((el, i) => !isInlineInText(el) && (rects[i].width < 24 - 0.5 || rects[i].height < 24 - 0.5));
        const center = (r: DOMRect) => [r.left + r.width / 2, r.top + r.height / 2];
        const distToRect = (p: number[], r: DOMRect) => {
          const dx = Math.max(r.left - p[0], 0, p[0] - r.right);
          const dy = Math.max(r.top - p[1], 0, p[1] - r.bottom);
          return Math.hypot(dx, dy);
        };
        const out: string[] = [];
        targets.forEach((el, i) => {
          if (!small[i]) return;
          const c = center(rects[i]);
          const clash = targets.some((other, j) => {
            if (j === i || other.contains(el) || el.contains(other)) return false;
            return small[j] ? Math.hypot(c[0] - center(rects[j])[0], c[1] - center(rects[j])[1]) < 24 : distToRect(c, rects[j]) < 12;
          });
          if (clash) {
            const label = (el.getAttribute("aria-label") ?? el.textContent ?? "").trim().slice(0, 40);
            out.push(`${el.tagName.toLowerCase()} "${label}" ${Math.round(rects[i].width)}x${Math.round(rects[i].height)}`);
          }
        });
        return out;
      });
      expect(failures, `targets under 24 px without spacing on ${route}:\n${failures.join("\n")}`).toEqual([]);
    });
  }
});
