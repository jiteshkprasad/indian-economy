"""Annual BSR-1 March 2024 press release (RBI, 4 Jun 2024): the shares and growth rates it prints.

The BSR-1 detailed tables (credit by borrower category, occupation, organisation) are published
only on DBIE (manual-only). The press-release HTML on www.rbi.org.in prints a handful of headline
ratios in its text; they are read here by exact sentence patterns, so a reworded release fails.
All values are per cent. The same release's PDF annex (rbidocs) is tried by fetch() but not needed.
"""

from __future__ import annotations

import re
from typing import Any

from pipeline.core.unit import BuildContext
from pipeline.core.units import clean_label

from . import _html as H

SRC = "rbi_bsr"
PRID = 58036
URL = f"https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid={PRID}"
LISTING = "https://www.rbi.org.in/Scripts/Pr_DataRelease.aspx?SectionID=376&DateFilter=Year"
NAME = "bsr1_mar2024_pr.html"
VINTAGE = "2024-06-04"
RELEASE = "RBI press release 2024-2025/439 'Credit by Scheduled Commercial Banks - March 2024 (Annual BSR-1)', 4 Jun 2024"
TITLE = "Credit by Scheduled Commercial Banks – March 2024 (Annual BSR-1)"
BSR_POPULATION = "scb_incl_rrb"  # annual BSR-1 reporters: SCBs including RRBs (not the RTP 'scb', which excludes RRBs)

# (regex over the release text, [(group index, item_code, institution, period, period_type, label)])
PATTERNS: list[tuple[str, list[tuple[int, str, str, str, str, str]]]] = [
    (
        r"Bank credit growth \(y-o-y\) increased by ([\d.]+) per cent, net of merger \d? ?\(([\d.]+) per cent "
        r"including the merger impact\) during 2023-24 as compared to ([\d.]+) per cent rise in the previous financial year",
        [
            (1, "credit_growth_net_of_merger", "scb", "2023-24", "fy", "Bank credit growth (y-o-y), net of merger"),
            (2, "credit_growth_incl_merger", "scb", "2023-24", "fy", "Bank credit growth (y-o-y), including the merger impact"),
            (3, "credit_growth_incl_merger", "scb", "2022-23", "fy", "Bank credit growth (y-o-y), previous financial year"),
        ],
    ),
    (
        r"Individuals in the household sector accounted for ([\d.]+) per cent of total bank credit in March 2024, "
        r"and other households .{0,120}? had another ([\d.]+) per cent share",
        [
            (1, "share_credit_individuals", "scb", "2024-03-31", "date", "Share of individuals (household sector) in total bank credit"),
            (2, "share_credit_other_households", "scb", "2024-03-31", "date",
             "Share of other households (proprietary concerns, HUF, partnership firms) in total bank credit"),
        ],
    ),
    (
        r"share of personal loans in total bank credit, which has been consistently rising, stood at ([\d.]+) per cent "
        r"in March 2024 whereas the corresponding share of industry declined to ([\d.]+) per cent",
        [
            (1, "share_credit_personal_loans", "scb", "2024-03-31", "date", "Share of personal loans in total bank credit"),
            (2, "share_credit_industry", "scb", "2024-03-31", "date", "Share of industry in total bank credit"),
        ],
    ),
    (
        r"their share in total credit by SCBs rose to ([\d.]+) per cent in March 2024 .{0,80}? the corresponding share "
        r"of public sector banks declined to ([\d.]+) per cent",
        [
            (1, "share_credit_by_group", "pvb", "2024-03-31", "date", "Share of private sector banks in total credit by SCBs"),
            (2, "share_credit_by_group", "psb", "2024-03-31", "date", "Share of public sector banks in total credit by SCBs"),
        ],
    ),
    (
        r"share in total credit by SCBs rising to ([\d.]+) per cent in March 2024",
        [(1, "share_credit_by_group", "sfb", "2024-03-31", "date", "Share of small finance banks in total credit by SCBs")],
    ),
]


def build(ctx: BuildContext) -> list[dict[str, Any]]:
    raw = ctx.raw(SRC, NAME)
    date, heading = H.page_heading(H.soup(raw.path))
    if date != "Jun 04, 2024" or clean_label(heading) != TITLE:
        raise ValueError(f"{NAME}: page is {date!r} {heading!r}")
    doc = H.soup(raw.path)
    for s in doc(["script", "style"]):
        s.decompose()
    text = clean_label(doc.get_text(" "))
    if not re.search(r"data submitted by SCBs \{including Regional Rural Banks \(RRBs\)\}", text):
        raise ValueError(f"{NAME}: reporting population (SCBs including RRBs) not stated as expected")
    rows: list[dict[str, Any]] = []
    for pat, outs in PATTERNS:
        m = re.search(pat, text)
        if not m:
            raise ValueError(f"{NAME}: sentence not found (release reworded?): /{pat[:80]}.../")
        pid = ctx.prov(raw=raw, table_id="Press release text (Highlights)",
                       locator=f"{URL}, 'Highlights' bullet: \"{m.group(0)[:160]}\"",
                       unit_as_published="per cent", conversion="none", price_basis="n/a",
                       vintage=VINTAGE, release=RELEASE)
        for grp, code, inst, period, ptype, label in outs:
            # BSR-1 covers SCBs *including* RRBs (release text: 'data submitted by SCBs {including Regional
            # Rural Banks (RRBs)}'), whereas the RTP 'scb' rows exclude RRBs (RTP Table IV.3 note 1). The
            # all-SCB rows therefore carry the distinct slug 'scb_incl_rrb'; the bank-group shares name the
            # same denominator in dim_other. The series_id keeps its original '.scb' suffix (stable key).
            rows.append({
                "series_id": f"bsr1.{code}.{inst}", "source_id": SRC, "table_id": "Press release text (Highlights)",
                "item_code": code, "item_label": label, "institution": BSR_POPULATION if inst == "scb" else inst,
                "dim_other": f"denominator={BSR_POPULATION}" if inst != "scb" else None, "geography": "IN",
                "stock_flow": "n/a", "period": period, "period_type": ptype, "value": float(m.group(grp)),
                "unit": "percent", "price_basis": "n/a", "vintage": VINTAGE, "estimate_stage": "n.a.",
                "status": "official", "prov_id": pid,
            })
    return rows
