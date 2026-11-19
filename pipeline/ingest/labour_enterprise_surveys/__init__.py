"""Labour, enterprise and wealth surveys: published report tables only (DECISIONS D1-2, no unit data).

Sources and vintages (all MoSPI/NSO PDFs under www.mospi.gov.in or mospi.gov.in, fetched with
ctx.fetch; see data/raw_pins/labour_enterprise_surveys.yaml):
- PLFS Annual Report July 2023-June 2024 (23 Sep 2024)            -> plfs.py
- ASUSE 2023-24 factsheet (Dec 2024) and full report (Jan 2025)     -> asuse.py
- ASI 2023-24 Summary Results and Volume I (30 Sep 2025)            -> asi.py
- AIDIS 2019 (NSS 77th round, Report 588) press note (10 Sep 2021)  -> aidis.py
- SAS 2019 (NSS 77th round, Report 587) full report (10 Sep 2021)   -> sas.py
- eSankhyiki API (api.mospi.gov.in, JSON pages; legacy TLS opt-in D1-6) -> esankhyiki.py:
  NSS-77 AIDIS indicators 5 and 9, PLFS indicators 6-8 (agricultural years 2022-23 and 2023-24),
  ASUSE indicator 36 (ASUSE 2025)

Datasets (prefix labour_enterprise_surveys_):
- plfs_lfs_indicators: LFPR/WPR/UR, usual status and CWS, 2017-18..2023-24 (survey years).
- plfs_status_dist: Statement 6, workers by status in employment, 2021-22..2023-24.
- plfs_industry_dist: Statement 7 (broad industry, 3 years) + Table 26 (NIC-2008 detail, 2023-24).
- plfs_industry_status: Table (20), status in employment within 11 NIC-2008 division groups, 2023-24.
- plfs_enterprise_type: Table (35) all-India rows, non-agricultural workers by enterprise type
  (incl. government/public sector), 2023-24.
- plfs_earnings: Statements 10-12 (regular, casual, self-employed earnings by quarter, fq periods)
  + Table 51 (casual wage per day by NIC-2008 section).
- asuse_key_indicators: factsheet Tables 1-6, 2022-23 and 2023-24.
- asuse_2324_activity: report Tables 4, 6, 29, 31, 33, 35, 37 by activity category.
- asi_principal_characteristics: Statement 3A, 2019-20..2023-24.
- asi_2324_industry: Statement 5A (NIC 2-digit) + Volume I Table 3 (NIC 4-digit employment and
  emoluments by type).
- aidis_2019_press_note: rural/urban x household-type assets, debt, capital expenditure.
  Percentages printed in the prose as whole numbers ('about 35%') sit on a separate provenance
  record whose notes list them.
- sas_2019_income_by_landclass: agricultural household income by source and land class, loans.
- aidis_2019_quintile (API): assets, cash loans, indebtedness by expenditure quintile class and
  asset-holding class x rural/urban x household type, as on 30.06.2018.
- plfs_earnings_api (API): PLFS quarterly earnings Q2 2022-23..Q1 2024-25 (adds Apr-Jun 2023).
- asuse_2025_assets_loans (API): ASUSE 2025 land/fixed assets, loans, interest and rent payable per
  establishment by activity x rural/urban x establishment type.

Survey periods are not fiscal years. PLFS and SAS years run July-June, ASUSE 2022-23/2023-24 run
October-September; those rows carry `sy` periods ('2023-07/2024-06', '2023-10/2024-09'; built in
_pdf.frame() from the parsers' survey_year tag), so Phase 2 applies only their shares and ratios to
FY totals. ASI is a true fiscal year. AIDIS stocks are dated 2018-06-30. ASUSE 2025 is calendar 2025.
Geography: all rows are all-India ('IN'); API state labels go through pipeline.core.geo (D1-9).
PLFS Statement 10 wages refer to the calendar month before the interview (one-month lag behind
the quarter label). On ASUSE rows household_group is the establishment's rural/urban location.

Skipped, and why (details in docs/phase1/issues/labour_enterprise_surveys.md):
- AIDIS Report 588 PDF: not located on the MoSPI site (its quintile tables come from the API).
- eSankhyiki PLFS indicator 4, the ASUSE indicators that repeat the 2023-24 report tables, and
  the ASI API: they repeat tables already ingested from the PDFs.
- Unit-level data (PLFS, ASUSE, AIDIS/SAS, ASI): D1-2; mospi_*_unit_data are not in SOURCES.
- ASI 2024-25: not released at build time (due 29 Sep 2026); ASI Vol I Table 2b: no unit caption.
- PLFS State tables (19, 27, 38-40, 50; State rows of Table 35) and ASUSE State tables: not
  needed by the gap map yet.
"""

from __future__ import annotations

from pipeline.core.unit import BuildContext, Dataset, FetchContext

UNIT = "labour_enterprise_surveys"
SOURCES = [
    "mospi_plfs_annual",
    "mospi_asuse",
    "mospi_asi",
    "mospi_aidis_2019",
    "mospi_sas_2019",
    "mospi_esankhyiki_api",
]

MOSPI = "https://www.mospi.gov.in"
FILES = [
    # (source id, URL, pin name)
    (
        "mospi_plfs_annual",
        f"{MOSPI}/sites/default/files/publication_reports/AnnualReport_PLFS2023-24L2.pdf",
        "plfs_ar_2023_24.pdf",
    ),
    (
        "mospi_asuse",
        f"{MOSPI}/sites/default/files/publication_reports/ASUSE_2023_24_Full_Report-L.pdf",
        "asuse_2023_24_full_report.pdf",
    ),
    (
        "mospi_asuse",
        f"{MOSPI}/sites/default/files/publication_reports/Factsheet_of_ASUSE_2023_24.pdf",
        "asuse_2023_24_factsheet.pdf",
    ),
    (
        "mospi_asi",
        f"{MOSPI}/uploads/publications_reports/publications_reports1759229789833_2b8ed8ad-314e-46b7-b123-b08cb17f1233_ASI_Summary_Results_2023-24C.pdf",
        "asi_2023_24_summary_results.pdf",
    ),
    (
        "mospi_asi",
        f"{MOSPI}/uploads/publications_reports/publications_reports1759229853481_27d8e959-0ae4-40fe-b9ff-d666b8aeb06d_ASI_Vol_I_2023-24C-2.pdf",
        "asi_2023_24_vol_i.pdf",
    ),
    (
        "mospi_aidis_2019",
        "https://mospi.gov.in/sites/default/files/press_release/press_note-AIDIS--240821%20update.pdf",
        "aidis_2019_press_note.pdf",
    ),
    (
        "mospi_sas_2019",
        "https://mospi.gov.in/sites/default/files/publication_reports/Report_587m_0.pdf",
        "sas_2019_report_587.pdf",
    ),
]


def fetch(ctx: FetchContext) -> None:
    from . import esankhyiki

    for src, url, name in FILES:
        ctx.fetch(src, url, name=name, expect="pdf")
    esankhyiki.fetch(ctx)


def build(ctx: BuildContext) -> list[Dataset]:
    from . import aidis, asi, asuse, esankhyiki, plfs, sas

    return [
        *plfs.build(ctx, UNIT),
        *asuse.build(ctx, UNIT),
        *asi.build(ctx, UNIT),
        *aidis.build(ctx, UNIT),
        *sas.build(ctx, UNIT),
        *esankhyiki.build(ctx, UNIT),
    ]
