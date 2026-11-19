// @vitest-environment happy-dom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import common from "../../../messages/en/common.json";
import matrix from "../../../messages/en/matrix.json";
import { DataExplorer } from "../../../src/components/matrix/DataExplorer";
import { MatrixTable } from "../../../src/components/matrix/MatrixTable";
import { format } from "../../../src/lib/format";
import { ROOT_BLOCKS, axisItems, indexHierarchy } from "../../../src/lib/matrix/axes";
import { buildGrid } from "../../../src/lib/matrix/grid";
import { tinyCells, tinyHierarchy } from "./tiny";

// next-intl's navigation helpers need the Next.js router, which unit tests do not have.
vi.mock("../../../src/i18n/navigation", () => ({
  Link: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={`/en${href}`} {...rest}>
      {children}
    </a>
  ),
}));

const GDP = 1000;
const labels: Record<string, string> = Object.fromEntries(
  tinyHierarchy.nodes.map((n) => [n.id, `Node ${n.id}`]),
);

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={{ common, matrix }} timeZone="Asia/Kolkata">
      {children}
    </NextIntlClientProvider>
  );
}

afterEach(() => cleanup());

describe("MatrixTable", () => {
  const ix = indexHierarchy(tinyHierarchy);
  const g = buildGrid(tinyCells, axisItems(ix, ROOT_BLOCKS.rows), axisItems(ix, ROOT_BLOCKS.cols), 6);

  it("renders scoped headers, formatted figures with badges, and a dot for empty cells", () => {
    const pinned = { "Q--P~pair": { total: "official" as const, pins: ["c1"] } };
    const { container } = render(
      wrap(<MatrixTable grid={g} label={(id) => labels[id]} pinned={pinned} gdp={GDP} year="2023-24" groupedFrom={null} />),
    );
    expect(container.querySelectorAll('thead th[scope="col"]').length).toBe(3);
    expect(container.querySelectorAll('tbody th[scope="row"]').length).toBe(3);
    // P receives from Q: 130 net, with an official total from the pair pin
    const td = container.querySelector('td[data-cell="Q--P"]')!;
    const num = td.querySelector("[data-num-value]")!;
    expect(Number(num.getAttribute("data-num-value"))).toBe(130);
    expect(num.textContent).toBe(format(130, "inr"));
    expect(td.querySelector("[data-status-total]")!.getAttribute("data-status-total")).toBe("official");
    // Q pays nothing to itself: an empty cell shows "·" and a hidden "no flow"
    const empty = container.querySelectorAll("tbody tr")[1].querySelectorAll("td")[1];
    expect(empty.textContent).toContain(matrix.table.zero);
    expect(screen.getByRole("region", { name: matrix.table.region })).toBeTruthy();
  });
});

describe("DataExplorer keyboard model", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("moves the cursor with arrows, announces after a short delay, zooms with Enter and Esc", async () => {
    const { container } = render(
      wrap(
        <DataExplorer
          hierarchy={tinyHierarchy}
          cells={tinyCells}
          pinned={{}}
          gdp={GDP}
          year="2023-24"
          labels={labels}
          flowIds={[]}
        />,
      ),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    const app = container.querySelector('[role="application"]') as HTMLElement;
    expect(app.getAttribute("aria-roledescription")).toBe("matrix");
    // wide screen default: every account (6 in the tiny SAM)
    expect(app.getAttribute("data-rows")).toBe("6");
    expect(app.getAttribute("data-cursor")).toBe("0,0");

    fireEvent.keyDown(app, { key: "ArrowRight" });
    fireEvent.keyDown(app, { key: "ArrowRight" });
    fireEvent.keyDown(app, { key: "ArrowRight" });
    expect(app.getAttribute("data-cursor")).toBe("0,3");
    const live = container.querySelector("[data-live-region]") as HTMLElement;
    // debounced: nothing yet, then one announcement for the final position
    expect(live.textContent?.trim()).toBe("");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });
    // row p1 receives from column q1: 100
    expect(live.textContent).toContain("Node q1 pays Node p1");
    expect(live.textContent).toContain(format(100, "inr"));
    expect(live.textContent).toContain(format(100 / GDP, "pct_gdp"));
    expect(live.textContent).toContain("Official");

    // the info box shows the same cell with a badge
    const info = container.querySelector('[data-cell="q1--p1"]') as HTMLElement;
    expect(info.querySelector("[data-num-value]")!.getAttribute("data-num-value")).toBe("100");
    expect(info.querySelector("[data-status-split]")!.getAttribute("data-status-split")).toBe("official");

    fireEvent.keyDown(app, { key: "Enter" });
    // into block P (rows) × Q (cols): P has 2 children, Q has 1
    expect(app.getAttribute("data-rows")).toBe("2");
    expect(app.getAttribute("data-cols")).toBe("1");
    expect(live.textContent).toContain("2 receivers by 1 payers");
    fireEvent.keyDown(app, { key: "Escape" });
    expect(app.getAttribute("data-rows")).toBe("6");
    expect(app.getAttribute("data-cursor")).toBe("0,3");
  });

  it("T opens the table view", async () => {
    const { container } = render(
      wrap(
        <DataExplorer
          hierarchy={tinyHierarchy}
          cells={tinyCells}
          pinned={{}}
          gdp={GDP}
          year="2023-24"
          labels={labels}
          flowIds={[]}
        />,
      ),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    const app = container.querySelector('[role="application"]') as HTMLElement;
    fireEvent.keyDown(app, { key: "t" });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });
    const table = container.querySelector('[data-testid="matrix-table"]') as HTMLElement;
    expect(table).toBeTruthy();
    // the heat-map shows accounts, so the table groups them into the 3 level-0 blocks
    expect(table.getAttribute("data-rows")).toBe("3");
  });
});

describe("Legend and cell info honesty", () => {
  it("states the ends of the log scale from the cells in view, with 'less than' for sub-rounding values", async () => {
    const { Legend } = await import("../../../src/components/matrix/Legend");
    const { container, rerender } = render(wrap(<Legend theme="light" domain={[61, 5756400]} />));
    const scale = container.querySelector('[data-testid="legend-scale"]')!;
    expect(scale.textContent).toContain(format(61, "inr"));
    expect(scale.textContent).toContain(format(5756400, "inr"));
    rerender(wrap(<Legend theme="light" domain={[0.01, 100]} />));
    const tiny = container.querySelector('[data-testid="legend-scale"]')!;
    expect(tiny.textContent).toContain("less than");
    expect(tiny.textContent).not.toContain(format(0.01, "inr"));
    rerender(wrap(<Legend theme="dark" domain={null} />));
    expect(container.querySelector('[data-testid="legend-scale"]')).toBeNull();
  });

  it("a block with positive and negative cells says its amount is net, with both parts", async () => {
    const { CellInfo } = await import("../../../src/components/matrix/CellInfo");
    const { cellFacts } = await import("../../../src/lib/matrix/describe");
    const ix = indexHierarchy(tinyHierarchy);
    const g = buildGrid(tinyCells, axisItems(ix, ROOT_BLOCKS.rows), axisItems(ix, ROOT_BLOCKS.cols), 6);
    // row P (0) receives from column Q (1): 100 + 50 - 20 = 130 net
    const f = cellFacts(g, 0, 1, {}, GDP);
    const { container } = render(
      wrap(
        <CellInfo
          facts={f}
          label={(id) => labels[id]}
          canZoom={false}
          onZoomIn={() => {}}
          onZoomRows={null}
          onZoomCols={null}
          flowLinks={[]}
          source="cursor"
        />,
      ),
    );
    const net = container.querySelector('[data-testid="net-of"]')!;
    const nums = [...net.querySelectorAll("[data-num-value]")].map((n) => Number(n.getAttribute("data-num-value")));
    expect(nums).toEqual([150, -20]);
    expect(f.v).toBe(130);
  });
});
