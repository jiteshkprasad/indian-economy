"""RBI, banks, NBFCs and corporate finance: RBI accounts, lender-group P&L, BSR-1 headline shares.

Ingested (all from www.rbi.org.in HTML pages, which were never challenged; RBI files are for internal
processing only, DECISIONS D1-1d):
- rbi_banking_corporate_rbi_accounts: RBI Annual Report Chapter XII 'The Reserve Bank's Accounts',
  editions 2023-24 (30 May 2024), 2024-25 (29 May 2025) and 2025-26 (29 May 2026): Table XII.1
  (income, expenditure, net income, surplus transferred), XII.10 (expenditure by head), XII.8
  (foreign currency assets and earnings), the income statement, the balance sheet and Schedules
  1-15; accounting years 2021-22 to 2025-26 (see ar.py for why 2019-20/2020-21 are skipped).
- rbi_banking_corporate_rbi_surplus_timing: two derived series for gap-map R6/K9b: the surplus the
  Centre received in cash in each fiscal year (= the RBI surplus of the previous accounting year),
  and the change in RBI's 'surplus payable to the Central Government' liability (accrued - paid).
- rbi_banking_corporate_rtp_banks / _rtp_coop / _rtp_nbfi: Report on Trend and Progress of Banking
  in India 2023-24 and 2024-25, chapter tables of income, expenditure, profit and (for SCBs) the
  balance sheet and cost/return of funds, by lender group: SCBs by bank group, RRBs, LABs, SFBs,
  payments banks, UCBs, StCBs, DCCBs, NBFCs (all/UL/ML, appendix VI.6/VI.7), HFCs, AIFIs, SPDs,
  plus NBFC ownership (government/non-government). 2021-22 to 2024-25 depending on the table.
- rbi_banking_corporate_bsr1_mar2024: the per-cent figures printed in the annual BSR-1 March 2024
  press release (household share of bank credit, merger-adjusted credit growth, bank-group shares).
- rbi_banking_corporate_pcbs_2324: the growth rates and ratios printed in the 'Performance of Private
  Corporate Business Sector during 2023-24' press release (listed NGNF companies).

Skipped, and why (details and gap-map consequences in docs/phase1/issues/rbi_banking_corporate.md):
- STRBI (bank-wise P&L and balance sheets): DBIE-only, manual (ACCESS_PLAN s5); the RTP chapter
  tables above are the substitute, at lender-group level only. SCB tax provisions are not printed
  separately in RTP (they sit inside 'provisions and contingencies').
- BSR-1 detailed tables and the corporate-finance level data (sales, interest, tax, dividends of
  NGNF companies): DBIE-only. The PDF versions of the two press releases (rbidocs.rbi.org.in, tried
  once per run under DECISIONS D1-4) turned out to hold the same text as the HTML and no tables; they
  are pinned and used only by the unit tests as an independent copy of the printed figures.
- Public financial institutions' annual reports (PFC, REC, IRFC, LIC, NABARD, ...): not in the
  registry and not fetched; AIFIs are covered in aggregate by RTP Table VI.18.
- Half-year (H1) columns and growth / variation columns (arithmetic on the levels).
"""

from __future__ import annotations

import time
from typing import Any

import polars as pl

from pipeline.core.fetch import AccessBlocked
from pipeline.core.unit import BuildContext, Dataset, FetchContext

from . import _html as H
from . import ar, bsr, pcbs, rtp

UNIT = "rbi_banking_corporate"
SOURCES = ["rbi_annual_report", "rbi_trend_progress", "rbi_bsr", "rbi_corporate_finances"]

BSR_PDF = "bsr1_mar2024_pr_annex.pdf"
PCBS_PDF = "pcbs_2023_24_pr_annex.pdf"

RBIDOCS_HOST = "rbidocs.rbi.org.in"
RBIDOCS_GAP_S = 10.0  # DECISIONS D1-4: at least 10 s between rbidocs requests


class _RbidocsGate:
    """D1-4: one pass per run over rbidocs, >= 10 s between requests, stop at the first challenge."""

    def __init__(self, ctx: FetchContext) -> None:
        self.ctx = ctx
        self.blocked: str | None = None
        self.last = 0.0
        self.skipped: list[str] = []

    def fetch(self, source_id: str, url: str, name: str, referer: str) -> None:
        ctx = self.ctx
        if self.blocked:
            self.skipped.append(name)
            ctx.warn(f"rbidocs: skipped {name} (host challenged earlier in this run; D1-4)")
            return
        key = f"{source_id}/{name}"
        cached = ctx.store is not None and key in ctx.store.pins and not ctx.refresh
        if ctx.offline and not cached:
            ctx.warn(f"offline: {name} was never pinned (rbidocs blocked or not tried); the build does not use it")
            return
        if not cached:
            wait = RBIDOCS_GAP_S - (time.monotonic() - self.last)
            if self.last and wait > 0:
                time.sleep(wait)
        try:
            ctx.fetch(source_id, url, name=name, referer=referer, expect="pdf")
        except AccessBlocked as e:
            self.blocked = str(e)
            ctx.warn(f"rbidocs BLOCKED on {name}: {e}. No further rbidocs request this run (D1-4).")
        finally:
            if not cached:
                self.last = time.monotonic()


def _rbidocs_links(path: Any, kind: str = ".pdf") -> list[str]:
    doc = H.soup(path)
    links = [a.get("href", "") for a in doc.find_all("a")]
    return sorted({u for u in links if RBIDOCS_HOST in u and "/PressRelease/" in u and u.lower().endswith(kind)})


def fetch(ctx: FetchContext) -> None:
    # 1. RBI Annual Report, Chapter XII (HTML) of three editions
    for ed in ar.EDITIONS:
        ctx.fetch(ar.SRC, ed.url, name=ed.name, referer=ar.LANDING, expect="html")
    # 2. Trend and Progress chapters and NBFC appendix pages (HTML), two editions
    for page in rtp.PAGES:
        ctx.fetch(rtp.SRC, page.url, name=page.name, referer=rtp.LANDING, expect="html")
    # 3. Press releases (HTML): BSR-1 March 2024 and PCBS 2023-24
    bsr_pr = ctx.fetch(bsr.SRC, bsr.URL, name=bsr.NAME, referer=bsr.LISTING, expect="html")
    pcbs_pr = ctx.fetch(pcbs.SRC, pcbs.URL, name=pcbs.NAME, referer=pcbs.LISTING, expect="html")
    # 4. rbidocs, last: the PDF versions of the two releases (test cross-check only; build does not need them)
    gate = _RbidocsGate(ctx)
    for src, pr, name, referer in (
        (bsr.SRC, bsr_pr, BSR_PDF, bsr.URL),
        (pcbs.SRC, pcbs_pr, PCBS_PDF, pcbs.URL),
    ):
        links = _rbidocs_links(pr.path)
        if len(links) != 1:
            ctx.warn(f"{pr.name}: expected one press-release PDF link on rbidocs, found {links}")
            continue
        gate.fetch(src, links[0], name, referer)
    if gate.blocked:
        ctx.log(f"rbidocs challenged; skipped this run: {gate.skipped}. See docs/phase1/issues/{UNIT}.md")


# ---------------------------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------------------------


def _surplus_timing(ctx: BuildContext, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derived series for R6 (cash basis) and K9b (accrued-minus-paid timing item)."""
    latest = ar.EDITIONS[-1]
    out: list[dict[str, Any]] = []
    xii1 = sorted((r for r in rows if r["series_id"] == "xii_1.surplus_transferred.current" and r["vintage"] == latest.vintage),
                  key=lambda r: r["period"])
    if len(xii1) != 5:
        raise ValueError(f"expected 5 years of XII.1 surplus in the {latest.key} edition, got {len(xii1)}")
    pid = ctx.prov(
        raw=None, source_id=ar.SRC, table_id="Table XII.1 (re-dated)", status="derived",
        locator="derived from rbi_banking_corporate_rbi_accounts series xii_1.surplus_transferred.current "
                f"(vintage {latest.vintage})",
        unit_as_published="Rs crore", conversion="none", price_basis="current", vintage=latest.vintage,
        release=latest.release, inputs=sorted({r["prov_id"] for r in xii1}),
        method="Cash-basis surplus received by the Central Government in fiscal year t+1 = RBI surplus for its accounting "
               "year t (April-March since 2021-22), which the RBI Central Board approves and transfers in May of t+1 "
               "(e.g. the 2022-23 surplus of Rs 87,416.22 crore was paid in May 2023, FY 2023-24). Values are copied; "
               "only the period changes (gap-map R6, DECISIONS D0-7).",
    )
    for r in xii1:
        y0 = int(r["period"][:4]) + 1
        out.append({**r, "series_id": "r6.surplus_received_by_centre_cash.current", "table_id": "Table XII.1 (re-dated)",
                    "item_code": "surplus_received_by_centre_cash",
                    "item_label": "RBI surplus received by the Central Government in the fiscal year (cash basis)",
                    "counterparty": "gg_centre", "period": f"{y0}-{(y0 + 1) % 100:02d}", "status": "derived",
                    "prov_id": pid})
    for ed in ar.EDITIONS:
        pay = {r["period"]: r for r in rows if r["vintage"] == ed.vintage
               and r["series_id"] == "sch4.x.surplus_payable_to_the_central_government.current"}
        end, start = ar.fy_end_date(ed.year), ar.fy_end_date(f"{int(ed.year[:4]) - 1}-{int(ed.year[5:]) - 1:02d}")
        if set(pay) != {start, end}:
            raise ValueError(f"{ed.key}: surplus payable stocks {sorted(pay)}")
        pid_k = ctx.prov(
            raw=None, source_id=ar.SRC, table_id="Schedule 4 (difference)", status="derived",
            locator=f"derived from Schedule 4 item '(iv) Surplus payable to the Central Government' as on {start} and {end} "
                    f"({ed.key} edition)",
            unit_as_published="Rs crore", conversion="none", price_basis="current", vintage=ed.vintage,
            release=ed.release, inputs=sorted({pay[start]["prov_id"], pay[end]["prov_id"]}),
            method="Change during the fiscal year in the RBI liability 'surplus payable to the Central Government' "
                   "(Schedule 4) = surplus accrued for the year minus the previous year's surplus paid in the year: the "
                   "timing item of gap-map K9b (RBI side). Arithmetic on two official stocks.",
        )
        out.append({**pay[end], "series_id": "k9b.change_in_surplus_payable.current", "table_id": "Schedule 4 (difference)",
                    "item_code": "change_in_surplus_payable",
                    "item_label": "Change in 'surplus payable to the Central Government' (accrued minus paid)",
                    "counterparty": "gg_centre", "stock_flow": "flow", "period": ed.year, "period_type": "fy",
                    "value": round(pay[end]["value"] - pay[start]["value"], 2), "side": "liabilities",
                    "status": "derived", "prov_id": pid_k})
    return out


def build(ctx: BuildContext) -> list[Dataset]:
    ar_rows: list[dict[str, Any]] = []
    for ed in ar.EDITIONS:
        ar_rows += ar.build_edition(ctx, ed)
    timing = _surplus_timing(ctx, ar_rows)
    r = rtp.build(ctx)
    bsr_rows = bsr.build(ctx)
    pcbs_rows = pcbs.build(ctx)

    def frame(rows: list[dict[str, Any]]) -> pl.DataFrame:
        return pl.DataFrame(rows, infer_schema_length=None).sort(["series_id", "vintage", "period"])

    return [
        Dataset(f"{UNIT}_rbi_accounts", frame(ar_rows),
                "RBI Annual Report Ch XII accounts (XII.1, XII.8, XII.10, income statement, balance sheet, schedules), 2021-22 to 2025-26, 3 editions"),
        Dataset(f"{UNIT}_rbi_surplus_timing", frame(timing),
                "Derived: RBI surplus received by the Centre in cash by fiscal year (R6) and change in surplus payable (K9b)"),
        Dataset(f"{UNIT}_rtp_banks", frame(r["banks"]),
                "RTP 2023-24 and 2024-25: SCB P&L and balance sheet by bank group, cost/return of funds, RRB/LAB/SFB/PB P&L"),
        Dataset(f"{UNIT}_rtp_coop", frame(r["coop"]),
                "RTP 2023-24 and 2024-25: income, expenditure and profit of UCBs, StCBs and DCCBs"),
        Dataset(f"{UNIT}_rtp_nbfi", frame(r["nbfi"]),
                "RTP 2023-24 and 2024-25: NBFC (all/UL/ML), HFC, AIFI, SPD income, expenditure, profit; NBFC ownership"),
        Dataset(f"{UNIT}_bsr1_mar2024", frame(bsr_rows),
                "Annual BSR-1 March 2024 press release: household share of bank credit, merger-adjusted growth, group shares"),
        Dataset(f"{UNIT}_pcbs_2324", frame(pcbs_rows),
                "PCBS 2023-24 press release: growth rates and ratios of listed private non-financial companies"),
    ]
