/**
 * "What this model can't tell you yet, and why" (/<locale>/gaps/).
 *
 * Every number here is either a `summary.json` path (bound at build time, like <DataFig>)
 * or a figure copied from the repository's issue log, with the ISSUES id it comes from.
 * Amounts are ₹ crore (1 lakh crore = 1,00,000 crore), FY 2023-24. Shares of GDP are
 * computed at build time against summary.gdp (NAS 2023-24 GDP); none is typed in.
 * Nothing is estimated here that the issue log does not already state.
 */

export type GapFigure =
  | { kind: "issues"; crore: number; ref: string; label: string } // a figure from ISSUES.md
  | { kind: "summary"; path: string; label: string }; // a figure from the export

export type GapItem = {
  title: string;
  plain: string; // what is missing, in plain words
  why: string; // why it is missing
  fix: string; // what would close it
  refs: string[]; // ISSUES ids
  figures: GapFigure[];
  /** shown when the repo gives no size in GDP terms */
  noSize?: string;
};

export type GapCause = {
  id: string;
  name: string;
  short: string; // one-line cause, for the overview diagram
  tone: "data" | "disagree" | "judgement" | "framework" | "base" | "saving" | "coverage";
  items: GapItem[];
};

export const GAP_CAUSES: GapCause[] = [
  {
    id: "saving",
    name: "The saving numbers don't add up by sector",
    short: "Sector accounts give a different saving than the national total",
    tone: "saving",
    items: [
      {
        title: "Households",
        plain:
          "When we add up what households earn and spend, they save less than the national accounts say they save.",
        why:
          "The new GDP series does not yet publish who pays interest, dividends and transfers to whom. Our build of those flows falls short of the published household saving. Documented repairs closed most of the gap; balancing closed the rest, mostly through property income.",
        fix: "New-base sector accounts from MoSPI's National Accounts Division.",
        refs: ["P2-1"],
        figures: [{ kind: "issues", crore: 385000, ref: "P2-1", label: "Gap left after documented repairs" }],
      },
      {
        title: "Centre vs States",
        plain:
          "Before balancing, the States' accounts showed more saving than the published total, and the Centre's showed less.",
        why:
          "Money for central schemes is spent outside State treasuries with no record of what the agencies spent, and several government items are recorded differently in budgets and in the national accounts.",
        fix: "Spending records for central schemes held outside treasuries; answers from MoSPI on how government items are classified.",
        refs: ["P2-2"],
        figures: [
          { kind: "issues", crore: 450000, ref: "P2-2", label: "States, before balancing" },
          { kind: "issues", crore: 299000, ref: "P2-2", label: "Centre, before balancing (shortfall)" },
        ],
      },
      {
        title: "Public sector companies",
        plain: "Public sector companies keep more than the national accounts say they save, and there is no evidenced place to put the difference.",
        why: "Most likely, the surplus of departmental enterprises (railways, posts) that flows to government is not written anywhere we can read.",
        fix: "One answer from MoSPI on how departmental enterprises' surplus is recorded.",
        refs: ["P2-3"],
        figures: [{ kind: "issues", crore: 313000, ref: "P2-3", label: "Unplaced saving" }],
      },
    ],
  },
  {
    id: "disagree",
    name: "Official sources disagree",
    short: "Two official publications give different numbers for the same thing",
    tone: "disagree",
    items: [
      {
        title: "Who lends and who borrows",
        plain:
          "The RBI's flow of funds and MoSPI's national accounts disagree on how much each sector lends or borrows. Companies differ most.",
        why: "They measure slightly different things, and the flow of funds is still on the old GDP base. We use the national accounts as the control and keep the difference as a named residual, not hidden.",
        fix: "A new-base flow of funds, or a published bridge between the two.",
        refs: ["P1-2", "P2-9"],
        figures: [{ kind: "issues", crore: 573000, ref: "P1-2", label: "Companies' net lending: RBI vs MoSPI" }],
      },
      {
        title: "Taxes and grants",
        plain:
          "Product taxes in the supply-use tables exceed what the Union and States report collecting, and grants to States differ between two views of the same Finance Accounts.",
        why: "Different timing and classification across publications. A documented decision cut the tax gap; the rest is logged.",
        fix: "Reconciliation notes from the publishers.",
        refs: ["P1-2"],
        figures: [
          { kind: "issues", crore: 161000, ref: "P1-2", label: "Product taxes: supply-use tables vs budgets (before the fix)" },
          { kind: "issues", crore: 141000, ref: "P1-2", label: "Grants to States: two Finance Accounts views" },
        ],
      },
    ],
  },
  {
    id: "judgement",
    name: "Some levels are judgement calls",
    short: "Where no source pins a number, a chosen tolerance sets it",
    tone: "judgement",
    items: [
      {
        title: "Tolerance bands",
        plain:
          "Where no source pins a flow, balancing may move it only within a band we chose, for example a tenth either side of a related published figure. Many flows ended exactly on the edge of their band, so the band width, a judgement, sets their level.",
        why: "No published figure exists for these flows. Without a band, balancing could move them anywhere.",
        fix: "A sensitivity run (halve and double the bands) shows how much they matter; it has not been run yet.",
        refs: ["P2-4"],
        figures: [{ kind: "summary", path: "methodology.judgement_band_abs", label: "Value in flows set by a band edge" }],
      },
    ],
  },
  {
    id: "base",
    name: "Old and new GDP series don't line up",
    short: "Gaps are filled with patterns from the old GDP series",
    tone: "base",
    items: [
      {
        title: "Old-base patterns",
        plain:
          "India moved its GDP series to a new base year (2022-23) in 2026. The new series does not yet publish who pays whom, so we use the old series' pattern and hold it to the new totals.",
        why: "MoSPI has not published the new-base back series or its sector accounts. The two series do not line up evenly, so this is the weakest part of the map.",
        fix: "MoSPI's new-base back series, expected around December 2026.",
        refs: ["P1-6", "P2-11"],
        figures: [{ kind: "summary", path: "methodology.old_base_abs", label: "Value in flows built on old-base patterns" }],
      },
    ],
  },
  {
    id: "data",
    name: "Data that is not public",
    short: "The data exists but is not open, or a site blocks automated download",
    tone: "data",
    items: [
      {
        title: "Income tax by household group",
        plain: "No open source says how income tax splits across rich and poor, rural and urban households. Our split is an estimate.",
        why: "It needs income-tax return data from CBDT or household survey microdata, which are not open or need registration that this project does not use.",
        fix: "Access to CBDT's return distribution, or unit-level survey data.",
        refs: ["P1-4", "P2-13"],
        figures: [{ kind: "summary", path: "headline.hh_outlays.parts.2.value", label: "Household income tax whose split is estimated" }],
      },
      {
        title: "Blocked or restricted sources",
        plain:
          "Some official sites block automated downloads, and some terms forbid reuse. We do not get around either, so a few figures come from substitutes and RBI tables are cited without direct links.",
        why: "The RBI's document server serves a bot challenge; GSTN, CBDT and several market sources restrict access or reuse.",
        fix: "Nothing planned: this is a personal project and no permissions are being sought. The site shows only the model's own computed figures, credited, and never the publishers' files.",
        refs: ["P1-3", "P1-4", "P2-13"],
        figures: [],
        noSize: "No size in GDP terms: this affects how easily the numbers can be refreshed and linked, not their level.",
      },
    ],
  },
  {
    id: "coverage",
    name: "Partial coverage",
    short: "A few parts of the official picture are only partly published",
    tone: "coverage",
    items: [
      {
        title: "Partly covered cells",
        plain:
          "A few blocks of the map are only partly covered by official data. Their published totals are held, and the splits inside them are estimated.",
        why: "The publishers release only part of the breakdown, for example Union and State halves separately, or totals without the split by activity.",
        fix: "Fuller official tables; for some blocks, combining sources already closes the gap.",
        refs: ["P1-1"],
        figures: [],
        noSize: "No single GDP-terms size in the repo: the published totals are held; only splits are estimated.",
      },
    ],
  },
  {
    id: "framework",
    name: "Not built yet",
    short: "Parts of the model that are planned but not built",
    tone: "framework",
    items: [
      {
        title: "Imports by industry, energy accounts, insurance",
        plain:
          "The map does not yet show which industries use imports, energy flows by industry, or insurance premiums matched to claims by who pays.",
        why: "These need extra pieces in the model's framework that have not been built.",
        fix: "Build them in a later phase.",
        refs: ["P2-14"],
        figures: [],
        noSize: "No size given in the repo; it is logged as minor.",
      },
    ],
  },
];
