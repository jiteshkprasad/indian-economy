// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import common from "../../../messages/en/common.json";
import { CompositionBar } from "@/components/ui/CompositionBar";
import { ErrorState } from "@/components/ui/ErrorState";
import { Num } from "@/components/ui/Num";
import { SourceCitation } from "@/components/ui/SourceCitation";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { mergeCites } from "@/components/ui/cites";
import { DataIndexProvider, type ClientDataIndex } from "@/data/index-data";
import { primeJson } from "@/data/load";
import { MapTextProvider } from "@/data/map-text-context";
import type { Constraints, MapText, Provenance } from "@/data/types";

afterEach(cleanup);

const IDX: ClientDataIndex = { dataVersion: "2023-24.uitest00000", base: "/data", fixture: true };

function wrap(ui: ReactNode, mapText?: MapText) {
  const inner = mapText ? <MapTextProvider value={mapText}>{ui}</MapTextProvider> : ui;
  return render(
    <NextIntlClientProvider locale="en" messages={{ common }}>
      <DataIndexProvider value={IDX}>{inner}</DataIndexProvider>
    </NextIntlClientProvider>,
  );
}

const prov: Provenance = {
  records: {
    a: {
      source: "mospi",
      status: "official",
      table: "1.1",
      locator: null,
      method: "m",
      vintage: null,
      base_year: "2022-23",
      price_basis: "current",
      unit: "INR crore",
      conversion: null,
      assumption: false,
      depends_on_assumption: false,
      cites: [
        { source: "mospi_nas", tables: ["S1.1"], urls: ["https://www.mospi.gov.in/x.pdf"], withheld: false, retrieved: ["2026-09-01", "2026-09-01"] },
        { source: "rbi_hbs", tables: ["T5"], urls: ["https://rbi.org.in/x"], withheld: true, retrieved: ["2026-09-02", "2026-09-02"] },
      ],
    },
    b: {
      source: "x",
      status: "derived",
      table: "",
      locator: null,
      method: "m",
      vintage: null,
      base_year: null,
      price_basis: "current",
      unit: "INR crore",
      conversion: null,
      assumption: false,
      depends_on_assumption: false,
      cites: [
        { source: "rbi_hbs", tables: ["T6"], urls: [null], withheld: true, retrieved: ["2026-09-03", "2026-09-04"] },
        { source: "cga", tables: ["A"], urls: [null], withheld: false, retrieved: [null, null] },
      ],
    },
  },
  sources: {
    mospi_nas: { name: "National Accounts Statistics 2026", publisher: "MoSPI", landing: null, link_mode: "deep", licence: "GODL", attribution: "MoSPI", registry_status: "verified" },
    rbi_hbs: { name: "Handbook of Statistics", publisher: "RBI", landing: "https://rbi.org.in", link_mode: "withheld", licence: "?", attribution: "RBI", registry_status: "verified" },
    cga: { name: "CGA accounts", publisher: "CGA", landing: null, link_mode: "deep", licence: "GODL", attribution: "CGA", registry_status: "verified" },
  },
};

describe("Num", () => {
  it("carries data-num-value and data-num-fmt and formats", () => {
    wrap(<Num value={576422.4} fmt="inr" />);
    const el = screen.getByText("₹5.76 lakh crore");
    expect(el.getAttribute("data-num-value")).toBe("576422.4");
    expect(el.getAttribute("data-num-fmt")).toBe("inr");
  });
});

describe("StatusBadge", () => {
  const constraints = {
    "closure:d1.published_total": {
      kind: "band",
      ref: "D1",
      description: "Published NAS household residual",
      target: 571133.27,
      lo: 571132.27,
      hi: 571134.27,
      balanced_sum: 571133.17,
      binding: false,
      judgement: false,
      prov: "sam_closure:x",
    },
  } as unknown as Constraints;
  const mapText = { nodes: {}, links: {}, refs: {}, series: { F01: { label: "Household consumption (PFCE)" } } } as MapText;
  primeJson(IDX, "sam/constraints.json", constraints);

  it("states the total and the split separately and names what pins the total (not by id)", async () => {
    wrap(
      <StatusBadge
        total="official"
        split="estimated"
        composition={{ o: 0.2, d: 0, e: 0.8, b: 0 }}
        pins={["ts:F01", "closure:d1.published_total"]}
      />,
      mapText,
    );
    const btn = screen.getByRole("button");
    expect(btn.textContent).toContain("Official total · split estimated");
    expect(btn.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText(/held to these figures from published statistics/)).toBeTruthy();
    expect(screen.getByRole("img").getAttribute("aria-label")).toContain("Estimated: 80.0%");
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(2));
    const items = screen.getAllByRole("listitem").map((li) => li.textContent ?? "");
    expect(items[0]).toContain("Household consumption (PFCE)");
    expect(items[0]).toContain("check passes");
    expect(items[1]).toContain("Published NAS household residual");
    expect(items[1]).toContain("₹5.71 lakh crore");
    expect(items[1]).toContain("within ₹1.0 crore");
    for (const it of items) expect(it).not.toMatch(/ts:F01|closure:d1/);
  });

  it("a single published figure (no parts) has no total line", () => {
    const { container } = wrap(<StatusBadge total={null} split="official" />);
    fireEvent.click(screen.getByRole("button"));
    const panel = container.querySelector('[role="note"]')!;
    expect(panel.getAttribute("data-badge-kind")).toBe("single");
    expect(panel.textContent).toContain("Taken from a published official statistic.");
    expect(panel.textContent).not.toMatch(/held to|sum itself|adds up/);
  });

  it("an unpinned aggregate says the sum is not held to one figure, and why its label can still be official", () => {
    const { container } = wrap(<StatusBadge total={null} split="official" composition={{ o: 1, d: 0, e: 0, b: 0 }} />);
    const panel = container.querySelector('[role="note"]')!;
    expect(panel.getAttribute("data-badge-kind")).toBe("aggregate");
    expect(panel.textContent).toContain("adds up several entries");
    expect(panel.textContent).toContain("The sum itself is not held to a single published figure.");
  });

  it("`single` overrides the default either way", () => {
    const { container } = wrap(<StatusBadge total={null} split="derived" composition={null} single />);
    expect(container.querySelector('[role="note"]')!.getAttribute("data-badge-kind")).toBe("single");
  });

  it("shows the split label alone when there is no total", () => {
    wrap(<StatusBadge total={null} split="balancing_set" compact />);
    expect(screen.getByText("Set by balancing")).toBeTruthy();
  });

  it("a two-part compact badge keeps its words, in pieces a narrow layout can stack (first screen, V1-03)", () => {
    const { container } = wrap(<StatusBadge total="official" split="estimated" pins={["households:hh.c1.total"]} compact />);
    const badge = container.querySelector("[data-status-split]")!;
    expect(badge.getAttribute("data-status-total")).toBe("official");
    expect(badge.textContent).toBe("Official total · split estimated");
    const pieces = [...badge.querySelectorAll("[data-badge-text] > span")].map((x) => x.textContent);
    expect(pieces).toEqual(["Official total", " · ", "split estimated"]);
  });
});

describe("CompositionBar", () => {
  it("lists every non-zero share in text", () => {
    wrap(<CompositionBar composition={{ o: 0.5, d: 0.25, e: 0, b: 0.25 }} />);
    const label = screen.getByRole("img").getAttribute("aria-label")!;
    expect(label).toContain("Official: 50.0%");
    expect(label).toContain("Derived: 25.0%");
    expect(label).toContain("Set by balancing: 25.0%");
    expect(label).not.toContain("Estimated");
  });
});

describe("SourceCitation", () => {
  it("merges cites in direct-input order, then frequency, then source id", () => {
    // mospi_nas and rbi_hbs are both first in some record; rbi_hbs is cited by two records
    expect(mergeCites(["a", "b"], prov.records).map((c) => c.source)).toEqual(["rbi_hbs", "mospi_nas", "cga"]);
    expect(mergeCites(["a"], prov.records).map((c) => c.source)).toEqual(["mospi_nas", "rbi_hbs"]);
    const rbi = mergeCites(["a", "b"], prov.records)[0];
    expect(rbi.tables).toEqual(["T5", "T6"]);
    expect(rbi.retrieved).toEqual(["2026-09-02", "2026-09-04"]);
    expect(() => mergeCites(["zz"], prov.records)).toThrow();
  });
  it("never links a withheld (RBI) source and says why; URL-less sources say so", () => {
    const { container } = wrap(<SourceCitation provIds={["a", "b"]} provenance={prov} />);
    const hrefs = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    expect(hrefs).toEqual(["https://www.mospi.gov.in/x.pdf"]);
    expect(screen.getByText(/Direct link not given \(ISSUES P1-9\)/)).toBeTruthy();
    expect(screen.getByText("No public URL recorded")).toBeTruthy();
  });
  it("links a URL that a cite lists twice only once, labelled by host and file", () => {
    const dup: Provenance = {
      ...prov,
      records: { d: { ...prov.records.a, cites: [{ source: "mospi_nas", tables: ["1.1", "1.2"], urls: ["https://www.mospi.gov.in/x.pdf", "https://www.mospi.gov.in/x.pdf", "https://www.mospi.gov.in/y.xlsx"], withheld: false, retrieved: ["2026-09-02", "2026-09-02"] }] } },
    };
    expect(mergeCites(["d"], dup.records)[0].urls).toEqual(["https://www.mospi.gov.in/x.pdf", "https://www.mospi.gov.in/y.xlsx"]);
    const { container } = wrap(<SourceCitation provIds={["d"]} provenance={dup} />);
    const links = [...container.querySelectorAll("a")].map((a) => [a.getAttribute("href"), a.textContent]);
    expect(links).toEqual([
      ["https://www.mospi.gov.in/x.pdf", "www.mospi.gov.in: x.pdf"],
      ["https://www.mospi.gov.in/y.xlsx", "www.mospi.gov.in: y.xlsx"],
    ]);
  });
  it("shows the top N then 'All N sources'", () => {
    wrap(<SourceCitation provIds={["a", "b"]} provenance={prov} limit={1} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    fireEvent.click(screen.getByText("All 3 sources"));
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
  });
});

describe("ErrorState", () => {
  it("names the file, logs, and shows no numbers", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    wrap(<ErrorState file="sam/cells.json" error={new Error("HTTP 404")} />);
    expect(screen.getByRole("alert").textContent).toContain("sam/cells.json");
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });
});
