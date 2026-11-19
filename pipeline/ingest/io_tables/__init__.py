"""Supply-use tables and input-output priors (ingest unit io_tables).

Datasets (data/clean/io_tables/):
- io_tables_sut_supply, io_tables_sut_use, io_tables_sut_va: MoSPI Supply and Use Tables 2022-23
  and 2023-24 on the 2022-23 base, 155 products x 67 industries, current prices, Rs crore, every
  published cell in long form (sut.py). Vintage: the revised files uploaded 31 Aug 2026 with NAS
  2026 (HTTP Last-Modified 31 Aug 2026). MoSPI replaced the May-2026 files without a version stamp,
  so the build refuses any file whose sha256 is not the 31-Aug one (415955ee... / 6fbaa0e9...).
- io_tables_sut_note_totals: the SUT note's Tables 9.1/9.2 (GVA/GDP by production, expenditure and
  income approach), the published control totals of the two SUTs (sut_note.py).
- io_tables_adb_ind_iot: ADB India national IOT, 35 x 35, domestic and imported use, US$ million,
  FY 2000-01 and 2007-08 to 2024-25 (old base; prior for the optional import matrix) (adb.py).
- io_tables_icio_india: OECD ICIO 2025 India slice, 50 ISIC industries, FY 2016-17 to 2022-23, US$
  million; imports summed over origin economies (derived) (icio.py).
- io_tables_ifpri_2223_datapaper: IFPRI India SAM 2022/23 data paper Tables 8, 10, 11 (macro SAM,
  household income sources and spending by quintile), status 'estimated', priors only (ifpri.py).
- io_tables_energy_psut: Energy Statistics 2026 Ch. 9 physical supply and use tables for energy,
  2023-24 and 2024-25 (P), petajoules as printed, by ISIC industry group, households, rest of the
  world and environment (energy.py; gap map S6).

The 34-sector SAM concordance (ACCOUNT_STRUCTURE s.2) is committed as data/concordance/io_tables_*.csv
(sam34_sectors, sut_industry_to_sam34, sut_product_to_sam34) and tested in
tests/units/test_io_tables_concordance.py. Aggregation to 34 x 34 is Phase 2.

Skipped: Eurostat FIGARO (EUR_million now exists, but India cells are non-commercial only and ADB
and ICIO already give the import prior; licence and ingest decision open, io_tables-10); the
old-base SUTs 2011-12 to 2021-22 (different files, units and layouts; not on the new base); the
IFPRI SAM.tab itself (Dataverse guestbook = registration, D1-1). Details and every quirk found:
docs/phase1/issues/io_tables.md.
"""

from __future__ import annotations

from pipeline.core.unit import BuildContext, Dataset, FetchContext

from . import adb, energy, fetching, icio, ifpri, sut, sut_note

UNIT = "io_tables"
SOURCES = [
    "mospi_sut_2022base",
    "mospi_energy_statistics",
    "adb_mrio",
    "oecd_icio_2025",
    "ifpri_nexus_sam_india_2022_23_paper",
]


def fetch(ctx: FetchContext) -> None:
    fetching.fetch_all(ctx)


def build(ctx: BuildContext) -> list[Dataset]:
    return [
        *sut.build_sut(ctx),
        sut_note.build_note_totals(ctx),
        adb.build_adb(ctx),
        icio.build_icio(ctx),
        ifpri.build_ifpri(ctx),
        *energy.build_energy(ctx),
    ]
