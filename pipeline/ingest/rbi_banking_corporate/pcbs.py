"""'Performance of Private Corporate Business Sector during 2023-24' press release (RBI, 28 Jun 2024).

Levels (sales, staff cost, interest, tax, dividends) of listed non-government non-financial (NGNF)
companies are published only on DBIE (manual-only). The press-release HTML on www.rbi.org.in prints
headline growth rates and ratios in its text; they are read by exact sentence patterns (a reworded
release fails). All values are per cent. Sample: 3,281 listed NGNF companies (also ingested).
"""

from __future__ import annotations

import re
from typing import Any

from pipeline.core.unit import BuildContext
from pipeline.core.units import clean_label

from . import _html as H

SRC = "rbi_corporate_finances"
PRID = 58186
URL = f"https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid={PRID}"
LISTING = "https://www.rbi.org.in/Scripts/Pr_DataRelease.aspx?SectionID=378&DateFilter=Year"
NAME = "pcbs_2023_24_pr.html"
VINTAGE = "2024-06-28"
RELEASE = "RBI press release 2024-2025/589 'Performance of Private Corporate Business Sector during 2023-24', 28 Jun 2024"
TITLE = "Performance of Private Corporate Business Sector during 2023-24"

# (regex, [(group, item_code, industry, period, unit, label)])
PATTERNS: list[tuple[str, list[tuple[int, str, str, str, str, str]]]] = [
    (r"drawn from abridged financial results of ([\d,]+) listed non-government non-financial \(NGNF\) companies",
     [(1, "sample_companies", "all", "2023-24", "count", "Number of listed NGNF companies in the sample")]),
    (r"Annual sales growth of listed private non-financial companies moderated to ([\d.]+) per cent during 2023-24 "
     r"from the high of ([\d.]+) per cent in 2022-23",
     [(1, "sales_growth", "all", "2023-24", "percent", "Sales growth (y-o-y), listed private non-financial companies"),
      (2, "sales_growth", "all", "2022-23", "percent", "Sales growth (y-o-y), listed private non-financial companies")]),
    (r"sales of manufacturing, information technology \(IT\) and non-IT services companies rose by ([\d.]+) per cent, "
     r"([\d.]+) per cent and ([\d.]+) per cent, respectively, during 2023-24 as compared with ([\d.]+) per cent, "
     r"([\d.]+) per cent and ([\d.]+) per cent, respectively, in the previous year",
     [(1, "sales_growth", "manufacturing", "2023-24", "percent", "Sales growth (y-o-y), manufacturing companies"),
      (2, "sales_growth", "it_services", "2023-24", "percent", "Sales growth (y-o-y), IT companies"),
      (3, "sales_growth", "non_it_services", "2023-24", "percent", "Sales growth (y-o-y), non-IT services companies"),
      (4, "sales_growth", "manufacturing", "2022-23", "percent", "Sales growth (y-o-y), manufacturing companies"),
      (5, "sales_growth", "it_services", "2022-23", "percent", "Sales growth (y-o-y), IT companies"),
      (6, "sales_growth", "non_it_services", "2022-23", "percent", "Sales growth (y-o-y), non-IT services companies")]),
    (r"raw material to sales ratio moderated to ([\d.]+) per cent in 2023-24 from ([\d.]+) per cent a year ago",
     [(1, "raw_material_to_sales", "manufacturing", "2023-24", "percent", "Raw material to sales ratio, manufacturing companies"),
      (2, "raw_material_to_sales", "manufacturing", "2022-23", "percent", "Raw material to sales ratio, manufacturing companies")]),
    (r"Staff cost rose by ([\d.]+) per cent, ([\d.]+) per cent and ([\d.]+) per cent \(y-o-y\) during 2023-24 for "
     r"manufacturing, IT and non-IT services companies, respectively",
     [(1, "staff_cost_growth", "manufacturing", "2023-24", "percent", "Staff cost growth (y-o-y), manufacturing companies"),
      (2, "staff_cost_growth", "it_services", "2023-24", "percent", "Staff cost growth (y-o-y), IT companies"),
      (3, "staff_cost_growth", "non_it_services", "2023-24", "percent", "Staff cost growth (y-o-y), non-IT services companies")]),
    (r"operating profit growth accelerated for manufacturing companies \(([\d.]+) per cent\) and non-IT services "
     r"companies \(([\d.]+) per cent\), while it moderated for IT companies \(([\d.]+) per cent\)",
     [(1, "operating_profit_growth", "manufacturing", "2023-24", "percent", "Operating profit growth (y-o-y), manufacturing"),
      (2, "operating_profit_growth", "non_it_services", "2023-24", "percent", "Operating profit growth (y-o-y), non-IT services"),
      (3, "operating_profit_growth", "it_services", "2023-24", "percent", "Operating profit growth (y-o-y), IT")]),
    (r"Operating profit margin improved across major sectors during 2023-24; it stood at ([\d.]+) per cent, "
     r"([\d.]+) per cent and ([\d.]+) per cent for manufacturing, non-IT services and IT companies, respectively",
     [(1, "operating_profit_margin", "manufacturing", "2023-24", "percent", "Operating profit margin, manufacturing"),
      (2, "operating_profit_margin", "non_it_services", "2023-24", "percent", "Operating profit margin, non-IT services"),
      (3, "operating_profit_margin", "it_services", "2023-24", "percent", "Operating profit margin, IT")]),
]


def release_text(path: Any) -> str:
    doc = H.soup(path)
    for s in doc(["script", "style"]):
        s.decompose()
    return clean_label(doc.get_text(" "))


def build(ctx: BuildContext) -> list[dict[str, Any]]:
    raw = ctx.raw(SRC, NAME)
    date, heading = H.page_heading(H.soup(raw.path))
    if date != "Jun 28, 2024" or clean_label(heading) != TITLE:
        raise ValueError(f"{NAME}: page is {date!r} {heading!r}")
    text = release_text(raw.path)
    rows: list[dict[str, Any]] = []
    for pat, outs in PATTERNS:
        m = re.search(pat, text)
        if not m:
            raise ValueError(f"{NAME}: sentence not found (release reworded?): /{pat[:80]}.../")
        unit = outs[0][4]
        pid = ctx.prov(raw=raw, table_id="Press release text (Highlights)",
                       locator=f"{URL}, press-release text: \"{m.group(0)[:160]}\"",
                       unit_as_published="number of companies" if unit == "count" else "per cent",
                       conversion="none", price_basis="n/a", vintage=VINTAGE, release=RELEASE)
        for grp, code, ind, period, unit, label in outs:
            rows.append({
                "series_id": f"pcbs.{code}.{ind}", "source_id": SRC, "table_id": "Press release text (Highlights)",
                "item_code": code, "item_label": label, "institution": "nfc_private_listed", "industry": ind,
                "geography": "IN", "stock_flow": "n/a", "period": period, "period_type": "fy",
                "value": float(m.group(grp).replace(",", "")), "unit": unit, "price_basis": "n/a",
                "vintage": VINTAGE, "estimate_stage": "n.a.", "status": "official", "prov_id": pid,
            })
    return rows
