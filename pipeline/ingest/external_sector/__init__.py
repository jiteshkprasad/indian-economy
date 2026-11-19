"""External sector: RBI balance of payments, invisibles, exchange rate, NRI deposits, foreign
investment, reserves, external debt, IIP, ECB registrations, FLA census, remittances survey,
software/ITES exports survey and LRS outward remittances.

Everything is read from HTML pages on www.rbi.org.in (never challenged); no rbidocs.rbi.org.in
file is needed (DECISIONS D1-4), so the unit never touches the F5-challenged host.

Datasets (all `external_sector_*`)
- fx_inr_usd: Rs per US$ (unit INR_per_USD), FY average and end-March 1986-87..2025-26 (HBS
  2025-26 T133) and monthly average / end-month Jan 2022..Jun 2026 (T205). This is the project's
  rate series for US$ -> Rs conversion (DECISIONS D1-8; trade_satellites in Phase 2). How to use
  it, and what it does not cover (calendar years, months before 2022): docs/phase1/issues/
  external_sector.md, section "INR/USD exchange rate: guide for Phase 2".
- bop_bpm6_annual: BPM6 standard presentation 2022-23..2025-26, Rs crore and US$ mn (T126/T127).
- bop_bpm6_quarterly: BPM6 quarterly Q1 2023-24..Q4 2025-26 (HBS 2024-25 T196/T197 and
  2025-26 T197/T198; 2024-25 quarters in both vintages).
- bop_overall_annual: old-format BoP 2020-21..2025-26 with ECB / NRI deposit / short-term credit
  lines (T124/T125).
- invisibles_annual: invisibles by category 2006-07..2025-26 (T130/T131): the long history of
  services, income and remittance (private transfers) flows.
- nri_deposits (T139-T142), foreign_investment (T143), fx_reserves (T144), external_debt
  (T145/T146), iip_quarterly (compact IIP, HBS 2024-25 T198/T199 and 2025-26 T199/T200).
- external_debt_by_sector: external debt by borrowing sector and instrument, end-March 2023-2026,
  and key indicators since 1991 (press release of 29 Jun 2026, prid 63041).
- ecb_monthly_2324: loan-level ECB/FCCB registrations Apr 2023-Mar 2024 (ECBUserView 235-246)
  with the published route totals.
- fla_census: FLA census 2023-24 and 2024-25 rounds (positions end-March 2023, 2024 and 2025;
  FC/NFC and activity splits at end-March 2024 and 2025).
- remittance_survey: RBI remittances survey rounds 2016-17/2020-21/2023-24, source-country and
  destination-State shares (Bulletin, Mar 2025). State codes from pipeline/core/geo.py (D1-9).

Estimate stages are those printed: RBI's "PR" (IIP, external-debt release) is `Partially
Revised`, "R" `Revised`, "P" `Provisional`; HBS preliminary-year notes give `Preliminary` or
`Provisional`; unflagged years are `n.a.`.
- ites_survey: software/ITES exports by activity, destination, currency, mode (2024-25 and
  2025-26 survey releases; years 2023-24..2025-26).
- lrs_outward: LRS outward remittances by purpose (Bulletin table 35/36, June 2024/2025/2026
  issues) with derived Rs crore for the annual totals.

Skipped (see docs/phase1/issues/external_sector.md): detailed BPM6 IIP (T149/T150), BPM5 IIP
(T147/T148), exchange rates for currencies other than the US dollar, trade tables T111-T123
(trade_satellites unit), FLA census tables 1, 2A, 7, 9-10.
"""

from __future__ import annotations

from pipeline.core.unit import BuildContext, Dataset, FetchContext

from . import debt_release, hbs, surveys

UNIT = "external_sector"
SOURCES = [
    "rbi_hbs_external",
    "rbi_bop_quarterly",
    "rbi_external_debt",
    "rbi_nri_deposits",
    "rbi_ecb_monthly",
    "rbi_fla_census",
    "rbi_remittances_survey",
    "rbi_ites_survey",
    "rbi_lrs_outward_remittances",
    "rbi_intl_investment_position",
]


def fetch(ctx: FetchContext) -> None:
    hbs.fetch_all(ctx)
    debt_release.fetch(ctx)
    surveys.fetch_all(ctx)


def build(ctx: BuildContext) -> list[Dataset]:
    out = hbs.build_all(ctx)
    out.append(debt_release.build(ctx))
    fx = next(d for d in out if d.name == f"{UNIT}_fx_inr_usd")
    out += surveys.build_all(ctx, fx.df)
    return out
