"""Insurance, pensions and securities markets (IRDAI, EPFO, PFRDA, SEBI).

Ingested (all current prices, Rs crore unless stated; stocks dated end-March or month-end):

- IRDAI Handbook on Indian Insurance Statistics 2024-25 (listed 03-02-2026; zip of XLSX):
  Summary tables A/B/C (all, life, general insurers; 2013-14..2024-25), life premium (T2), life AUM by
  fund x asset (T20, 31 Mar 2016..2025), life policyholders' and shareholders' accounts for LIC and
  the industry (T24, T25; published in Rs lakh), general/health premium by group and segment (T40,
  T41), net premium earned and incurred claims by segment (T44), general AUM by asset (T46) and the
  shareholders' account by insurer group (T51). Datasets finsector_markets_irdai_{summary,life,nonlife}.
- EPFO Annual Reports 2023-24 (PDF created Dec 2024) and 2024-25 (Feb 2026), as two vintages:
  contributions and payments of EPF/EPS/EDLI (un-exempted sector, five-year tables and Appendix-5(i)),
  investments by scheme x category (face value), exempted-establishment investments 2023-24 and EPF
  interest rates. Dataset finsector_markets_epfo_ar.
- PFRDA NPS/APY statistics (A2, A5, M2, M4, M6, M7; regenerated files dated by Last-Modified): sector AUM,
  cumulative contributions (M4) with derived annual contributions, AUM by asset class, Tier-II
  contributions. Dataset finsector_markets_pfrda_nps. Table M7 (SG-sector contributions received
  per month, all-India 'Total' row, with employer/employee split and derived FY sums; it confirms the
  cumulative reading of M4): dataset finsector_markets_pfrda_sg.
- SEBI Handbook of Statistics 2025-26 (17 Aug 2026; per-table XLSX): primary market (T1, T7, T8, T13,
  T14), outstanding corporate bonds (T11), market capitalisation (T23), foreign investment (T58-T60,
  T62, T63), mutual funds (T64, T69, T70, T72). Datasets finsector_markets_sebi_*.

Skipped, and why:
- NSDL FPI Monitor and AMFI: their terms forbid reproduction/derivative works (ACCESS_PLAN s.5); not
  fetched. SEBI Handbook tables that carry NSDL/AMFI figures (T59, T60, T63, T69, T72) are used instead.
- EPFO Consolidated Annual Accounts (audited): latest is 2022-23, older than the reference year.
- SEBI T67 (MF assets by investment objective) is pinned but not parsed; IRDAI insurer-level rows,
  growth and share rows, and IRDAI Swiss Re penetration/density figures are not ingested.
- PFRDA Handbook of NPS Statistics 2024-25 PDF is pinned only as the evidence for the unit captions
  (it has definitions, no data tables).
See docs/phase1/issues/finsector_markets.md for every quirk, gap and assumption.
"""

from __future__ import annotations

import re
from pathlib import Path

from pipeline.core.unit import BuildContext, Dataset, FetchContext

from . import epfo, irdai, pfrda, sebi

UNIT = "finsector_markets"
SOURCES = ["irdai_handbook_insurance", "epfo_annual_report_accounts", "pfrda_nps_statistics", "sebi_handbook_statistics"]

IRDAI_LANDING = "https://irdai.gov.in/handbook-of-indian-insurance"
IRDAI_ZIP = (
    "https://irdai.gov.in/documents/37343/825690/Handbook+on+Indian+Insurance+Statistics+2024-25.zip/"
    "c754826c-a24f-6adf-65d9-bba0e1bb8d2a?version=1.1&t=1770357151427&download=true"
)
SEBI_LANDING = (
    "https://www.sebi.gov.in/reports-and-statistics/publications/aug-2026/handbook-of-statistics-2025-26_103700.html"
)
SEBI_CONTENTS = "https://www.sebi.gov.in/sebi_data/attachdocs/aug-2026/1786967914812.pdf"
SEBI_TABLES = {  # published table number -> annual|monthly file
    "1": "annual", "7": "annual", "8": "annual", "11": "annual", "13": "annual", "14": "annual",
    "23": "annual", "58": "annual", "59": "annual", "60": "annual", "62": "annual", "63": "annual",
    "64": "annual", "67": "annual", "69": "annual", "70": "annual", "72": "monthly",
}
PFRDA_LANDING = "https://www.pfrda.org.in/research-publications/statistics/statistical-data"
PFRDA_FILES = (  # path under /documents/33652/ (the ?v= query is PFRDA's cache-buster, as linked on 29 Sep 2026)
    "202494/A2_sector-wise_asset_under_management.xlsx?v=1.82",
    "202494/A5_sector-wise_contribution_in_tier.xlsx?v=1.80",
    "202496/M6_asset_class_wise_classification.xlsx?v=1.241",
    "202496/M2_sector_wise_asset_under_management.xlsx?v=1.238",
    "202496/M4_sector_wise_nps_contribution.xlsx?v=1.239",
    "202496/M7_state_wise_subscribers.xlsx?v=1.239",  # SG monthly contributions: validates the M4 reading
    "203559/HoNPSS+2024-25.pdf",
)
EPFO_LANDING = "https://www.epfo.gov.in/annual-reports/"
EPFO_FILES = {  # the annual-reports page links '71.pdf' under 'Annual Report 2023-24'
    "epfo_annual_report_2023_24.pdf": "https://pmvbry-cdn.epfindia.gov.in/wp-content/uploads/2025/08/71.pdf",
    "epfo_annual_report_2024_25.pdf": "https://pmvbry-cdn.epfindia.gov.in/wp-content/uploads/2025/08/Annual-Report-2024-25.pdf",
}


def sebi_links(pdf_path: Path) -> dict[tuple[str, str], str]:
    """{(table number, 'annual'|'monthly'): url} from the Handbook's contents PDF (153 links)."""
    import pypdf

    out: dict[tuple[str, str], str] = {}
    for page in pypdf.PdfReader(pdf_path).pages:
        for annot in page.get("/Annots") or []:
            action = annot.get_object().get("/A")
            if action and "/URI" in action:
                url = str(action["/URI"])
                m = re.search(r"/hbs2025-26/(annual|monthly)/Table%20(\d+)%20", url)
                if m:
                    key = (m.group(2), m.group(1))
                    if key in out and out[key] != url:
                        raise ValueError(f"SEBI contents PDF: two links for table {key}")
                    out[key] = url
    return out


def fetch(ctx: FetchContext) -> None:
    contents = ctx.fetch("sebi_handbook_statistics", SEBI_CONTENTS, name="hbs2025_26_contents.pdf", referer=SEBI_LANDING)
    links = sebi_links(contents.path)
    for t, kind in SEBI_TABLES.items():
        ctx.fetch("sebi_handbook_statistics", links[(t, kind)], name=f"hbs2526_t{t}_{kind[0]}.xlsx", referer=SEBI_LANDING)
    ctx.fetch("irdai_handbook_insurance", IRDAI_ZIP, name="irdai_handbook_2024_25.zip", referer=IRDAI_LANDING)
    for f in PFRDA_FILES:
        name = f.split("/")[1].split("?")[0].replace("+", "_")
        ctx.fetch("pfrda_nps_statistics", f"https://www.pfrda.org.in/documents/33652/{f}", name=name, referer=PFRDA_LANDING)
    for name, url in EPFO_FILES.items():
        ctx.fetch("epfo_annual_report_accounts", url, name=name, referer=EPFO_LANDING)


def build(ctx: BuildContext) -> list[Dataset]:
    return [
        *irdai.build(ctx, UNIT),
        *epfo.build(ctx, UNIT),
        *pfrda.build(ctx, UNIT),
        *sebi.build(ctx, UNIT),
    ]
