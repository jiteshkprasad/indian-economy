"""Household consumption distribution: HCES 2023-24 and 2022-23 published tables, CPI 2024 weights,
and the NSS 2025 health and education reports (published tables only; no unit-level data, D1-2).

Datasets (all in data/clean/hces_consumption/):
- hces_consumption_a2_fractile_persons: Table A2, households / adults / children (and derived
  persons) and average MPCE by State/UT x rural/urban x 12 MPCE fractile classes (+ all classes).
- hces_consumption_a6_group_fractile: Table A6, value per person per 30 days of ~35 item groups by
  State x R/U x fractile, incl. memo lines (imputed rent, free cooked meals, second-hand goods).
- hces_consumption_a10f_item_fractile: Table A10F, ~440 item codes x R/U x 12 fractiles, All-India:
  value, quantity (kg -> tonnes, or numbers) and households reporting. Every code carries
  `item_role` (leaf / subtotal / total / aggregate / memo_detail / memo) and `group` in dim_other;
  only `leaf` rows are additive. Free PDS items have quantities but no value ('##').
- hces_consumption_a10s_state_item: Table A10S, items by State x R/U (2022-23 and 2023-24).
- hces_consumption_a10sw_state_item_imputed: Table A10SW (2023-24), as A10S with the imputed value of
  free / PDS items (MPCE 'with imputation').
- hces_consumption_report592_mpce: Report 592 Tables 3.17-3.19 (MPCE with/without imputation by State
  and item group; MPCE trend 1999-2000 to 2023-24 nominal and at 2011-12 prices).
- hces_consumption_cpi2024_weights: CPI 2024=100 weights (Expert Group report Annexure 5.3).
- hces_consumption_health596: NSS Report 596 (Jan-Dec 2025) Tables 2.21 and 2.24.
- hces_consumption_cms_education_2025: NSS Report 595 (Apr-Jun 2025) Statement 2.3.

Vintages: HCES 2023-24 tables 30 Jan 2025; HCES 2022-23 tables June 2024; CPI weights Jan 2026;
Report 596 April 2026; Report 595 August 2025.

Periods: HCES survey years run August-July, so HCES 2023-24 rows carry period '2023-08/2024-07' and
HCES 2022-23 rows '2022-08/2023-07', with period_type 'sy' (survey window). Report 592 Table 3.18's
NSS rounds are July-June windows ('1999-07/2000-06' ... '2011-07/2012-06'). The round's own name
('HCES 2023-24') is in the series ids ('hces2324'), the provenance release and notes. Use the surveys
for shares/distributions applied to NAS FY totals, never as FY levels. Report 596 (Jan-Dec 2025) is
'cy' 2025, Report 595 (Apr-Jun 2025) 'cq' 2025-Q2, and the CPI weights 'cy' 2024 (the index base year).
State/UT codes come from pipeline/core/geo.py (D1-9).

Skipped, and why (details in docs/phase1/issues/hces_consumption.md):
- Unit-level data (mospi_hces_unit_data, nss_health_2025, nss_cms_education_2025 registry entries):
  registration-gated, D1-2. The published-report counterparts of the last two are registry additions.
- eSankhyiki HCES API (api.mospi.gov.in, reachable since D1-6): not used. Its 9 indicators repeat the
  Excel tables at a coarser level; the only content not already here is the 2022-23 'with imputation'
  broad-category MPCE by State, which no gap-map cell needs (issue hces_consumption-10).
- Quantities in litre / gram / metre / standard unit / box: not ingested (issue hces_consumption-9;
  the units now exist, but no gap-map cell needs these quantities).
- Tables A1, A3, A4, A5, A7, A9 (sample sizes, household size, cereal detail by State x fractile,
  household distribution, social groups): not needed by any gap-map cell.
"""

from __future__ import annotations

from pipeline.core.unit import BuildContext, Dataset, FetchContext

from . import cpi_weights, hces_tables, pdf_tables
from ._common import ROUNDS, UNIT

SOURCES = [
    "mospi_hces_2023_24",
    "mospi_hces_2022_23",
    "mospi_cpi_2024base",
    "nss_health_2025_report",
    "nss_cms_education_2025_report",
]

__all__ = ["SOURCES", "UNIT", "build", "fetch"]


def fetch(ctx: FetchContext) -> None:
    for period in ("2023-24", "2022-23"):
        rd = ROUNDS[period]
        for remote, local in rd["files"].values():
            ctx.fetch(rd["src"], rd["base"] + remote, name=local)
    ctx.fetch("mospi_hces_2023_24", pdf_tables.R592_URL, name=pdf_tables.R592_FILE)
    ctx.fetch(cpi_weights.SRC, cpi_weights.URL, name=cpi_weights.FILE, referer=cpi_weights.REPORT_URL)
    ctx.fetch("nss_health_2025_report", pdf_tables.H596_URL, name=pdf_tables.H596_FILE)
    ctx.fetch("nss_cms_education_2025_report", pdf_tables.E595_URL, name=pdf_tables.E595_FILE)


def build(ctx: BuildContext) -> list[Dataset]:
    a2 = hces_tables.build_a2_dataset(ctx)
    return [
        a2,
        hces_tables.build_a6_dataset(ctx, a2),
        hces_tables.build_a10f_dataset(ctx),
        hces_tables.build_a10s_dataset(ctx),
        hces_tables.build_a10sw_dataset(ctx),
        pdf_tables.build_report592(ctx),
        cpi_weights.build_cpi_weights(ctx),
        pdf_tables.build_health596(ctx),
        pdf_tables.build_cms_education(ctx),
    ]
