import { expect, test } from "@playwright/test";
import { format, type FmtKind } from "../../src/lib/format";
import { noteFixture, readData } from "./helpers";

// PLAN §5.3: open 10 listed links at levels 0, 1 and 2 (both presets). Every
// [data-num-value] in the panel must read format(value); the headline value and
// share must equal an aggregation written HERE from cells.json (this spec does not
// import src/data/aggregate.ts). Money flows from the column account to the row account.
type Hier = {
  nodes: Array<{ id: string; accounts: string[] }>;
  accounts: Array<{ code: string; idx: number; l0: string }>;
  presets: Record<string, { merges: Record<string, string[]> }>;
};
type CellsT = { n: number; row: number[]; col: number[]; v: number[] };

const LINKS: Array<{ id: string; p: "simple" | "full"; x: string[] }> = [
  { id: "HH--PRODUCERS", p: "simple", x: [] },
  { id: "PRODUCERS--FACT", p: "simple", x: [] },
  { id: "TAX--CEN~neg", p: "simple", x: [] },
  { id: "HH--PRDS", p: "full", x: [] },
  { id: "PRDS--TAX~neg", p: "full", x: [] },
  { id: "FINM--SI", p: "full", x: [] },
  { id: "HH.RUR--PRDS", p: "full", x: ["HH"] },
  { id: "FACT.LAB--HH.URB", p: "full", x: ["FACT", "HH"] },
  { id: "H_R1--PRDS", p: "full", x: ["HH", "HH.RUR"] },
  { id: "H_U1--C_CROP", p: "full", x: ["PRDS", "PRDS.AGRI", "HH", "HH.URB"] },
];

function expected(h: Hier, cells: CellsT, gdp: number, id: string, preset: "simple" | "full", expanded: string[]) {
  const m = /^(.+)--(.+?)(~neg)?$/.exec(id)!;
  const [payer, receiver, neg] = [m[1], m[2], !!m[3]];
  const byId = new Map(h.nodes.map((n) => [n.id, n]));
  const accountsOf = (nid: string): Set<string> => {
    const merges = expanded.length === 0 ? h.presets[preset].merges : {};
    const parts = merges[nid] ?? [nid];
    const out = new Set<string>();
    for (const p of parts) {
      const n = byId.get(p);
      if (!n) throw new Error(`node ${p} not in hierarchy`);
      n.accounts.forEach((a) => out.add(a));
    }
    return out;
  };
  const pay = accountsOf(payer);
  const rec = accountsOf(receiver);
  const code = h.accounts.map((a) => a.code);
  const l0 = h.accounts.map((a) => a.l0);
  let sum = 0;
  for (let i = 0; i < cells.n; i++) {
    const r = cells.row[i];
    const c = cells.col[i];
    const v = cells.v[i];
    if (!pay.has(code[c]) || !rec.has(code[r])) continue;
    if (l0[r] === "PRDS" && l0[c] === "PRDS") continue; // flows inside product markets stay internal
    if (neg ? v < 0 : v > 0) sum += v;
  }
  return { value: sum, share: sum / gdp };
}

test.describe("fidelity", () => {
  const h = readData<Hier>("hierarchy.json");
  const cells = readData<CellsT>("sam/cells.json");
  const gdp = readData<{ gdp: { value: number } }>("summary.json").gdp.value;

  for (const L of LINKS) {
    test(`${L.id} (${L.p}${L.x.length ? `, x=${L.x.join(",")}` : ""})`, async ({ page, isMobile }, info) => {
      test.skip(isMobile, "desktop project only");
      const fixture = noteFixture(info);
      const exp = expected(h, cells, gdp, L.id, L.p, L.x);
      if (exp.value === 0) {
        // On real data every listed link exists; the fixture has only two negative cells.
        expect(fixture, `${L.id} has no cells in the real export`).toBe(true);
        test.skip(true, `FIXTURE: ${L.id} absent from fixture data`);
      }
      const q = new URLSearchParams();
      if (L.x.length) q.set("x", L.x.join(","));
      else q.set("p", L.p);
      q.set("s", L.id);
      await page.goto(`/en/?${q.toString()}`);
      const panel = page.locator(`[data-flow-panel][data-id="${L.id}"]`);
      await expect(panel, "detail panel ([data-flow-panel][data-id], U3)").toBeVisible();
      await page.waitForLoadState("networkidle");

      const nums = await panel.locator("[data-num-value]").evaluateAll((els) =>
        els.map((e) => ({ value: Number(e.getAttribute("data-num-value")), fmt: e.getAttribute("data-num-fmt"), text: (e.textContent ?? "").trim() })),
      );
      expect(nums.length).toBeGreaterThan(0);
      for (const n of nums) expect(n.text, `${n.fmt} ${n.value}`).toBe(format(n.value, n.fmt as FmtKind));

      const value = Number(await panel.locator("[data-panel-value] [data-num-value]").first().getAttribute("data-num-value"));
      expect(Math.abs(value - exp.value), `value ${value} vs ${exp.value}`).toBeLessThanOrEqual(0.011);
      const share = Number(await panel.locator("[data-panel-share] [data-num-value]").first().getAttribute("data-num-value"));
      expect(Math.abs(share - exp.share), `share ${share} vs ${exp.share}`).toBeLessThanOrEqual(1e-6);
    });
  }
});
