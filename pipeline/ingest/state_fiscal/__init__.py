"""State and local government finances (Phase 1 ingest unit `state_fiscal`).

Reference year FY 2023-24; history wherever the same files carry it. Every number is published
(status `official`) except where noted `derived` (our sums of published cells). Rs lakh and rupees
are converted to Rs crore on the way in.

Datasets
- state_fiscal_fc16_kfi: Sixteenth Finance Commission 'State Finances - Key Fiscal Indicators'
  (file dated 3 Feb 2026). 92 items (taxes by type, devolution, grants, interest, pensions,
  salaries, capital expenditure, deficits, liabilities, GSDP) for 28 States, NEH / non-NEH groups,
  All_States (28 States, no UTs) and undivided AP, FY 2011-12 to 2023-24. The workbook labels years
  by their ending year ('2024' = FY 2023-24): verified from the file (State GST is 0 under '2017'
  and first positive under '2018'; GST began July 2017) and from the companion accounts dump,
  whose 'Description' sheet says 'Year 2015 means FY 2014-15'. The unlabelled %-of-GSDP rows are
  not ingested (arithmetic on an old-base GSDP). Debt-flow rows that the file leaves at 0 for
  recent years (not compiled) and the totals built on them are dropped, not ingested as zeros.
- state_fiscal_fc16_transfers: FC16 time series of Centre-to-State transfers, 1952-53 to 2025-26
  BE (States' share, FC and non-FC grants, gross tax revenue), and the 'Grants - details RBI'
  sheet (grant composition 1952-53 to 2023-24).
- state_fiscal_fc16_subsidies: FC16 sector-wise subsidies and transfers, 21 States and the Union,
  2018-19 to 2025-26 BE.
- state_fiscal_fc16_state_accounts (derived): FC16's minor-head dump of the CAG State Finance
  Accounts (550,775 rows, Rs lakh) summed to State x year x account x major head, FY 1995-96 to
  2023-24 (States, UTs with legislature, and the Union for 2013-14 to 2020-21). Its 2023-24
  major-head sums reproduce the KFI totals exactly (tested).
- state_fiscal_fc16_local_body_assistance (derived): the same dump's 'assistance to local bodies'
  minor heads 191-193 (urban) and 196-198 (panchayats), summed over major heads.
- state_fiscal_ulb_cityfinance (derived): FC16 ULB data dump (cityfinance.in, 3,725 to 4,620 ULBs,
  2015-16 to 2023-24), summed by State with a count of reporting ULBs per item; balance-sheet items
  (borrowings, receivables, cash) as end-March stocks.
- state_fiscal_rbi_sf_statements: RBI State Finances: A Study of Budgets of 2025-26 (23 Jan 2026),
  Statements 13 (interest, gross/net), 14 and 15 (State shares, per cent), 17 (transfers from the
  Centre, gross/net) and 36 (subsidies, from 2018-19), by State/UT; 2023-24 Accounts, 2024-25 RE,
  2025-26 BE. Variation (per cent) columns are not ingested.
- state_fiscal_rbi_sf_app_tables: Appendix Tables 1 (deficits), 2 (transfers), 3 (development
  expenditure), 9 (GFD financing), 11 (liabilities, end-March stocks), All States and UTs,
  2005-06/2007-08 to 2025-26 BE. Not ingested: the per-cent-of-GDP rows, 5-year averages, App.
  Table 2's column printed '2023-24 (Budget Estimates)' (it sits where 2024-25 BE belongs), and
  App. Table 2 rows III-VI for 2023-24 (Accounts), which repeat 2022-23 and contradict Statement 17
  and Appendices III/IV of the same edition (issues file).
- state_fiscal_rbi_sf_appendices: Appendices I-IV (revenue receipts, revenue expenditure, capital
  receipts, capital expenditure), every line item of the All States and UTs block, Rs lakh -> crore.
  Rows are placed in the table's hierarchy from their printed numbering, and every printed formula
  ('(1 to 3)', '(A+B)') is tested to close.
- state_fiscal_rbi_municipal: RBI Report on Municipal Finances (13 Nov 2024) Statements 1, 4, 8
  (municipal corporations' revenue receipts, revenue expenditure, capital outlay by State; Rs lakh
  and per cent of GSDP), 2019-20 to 2023-24 BE.
- state_fiscal_rbi_pri: RBI Finances of Panchayati Raj Institutions (24 Jan 2024): Appendices I-II
  (Rs per village panchayat, all States/UTs, 2020-21 to 2022-23) and Chapter II Tables II.1-II.3,
  II.5 (counts; balanced-panel aggregates in Rs crore).

Access (DECISIONS D1-1, D1-4): FC16 files are open. RBI XLSX live on rbidocs.rbi.org.in behind an
intermittent F5 challenge: hashed links are read from the www.rbi.org.in listing pages, each rbidocs
file is requested at most once per run with >= 10 s between requests, and the first challenge stops
rbidocs for the run (sources.py). Not used: CAG State Finance Accounts PDFs (the FC16 dump is a
machine-readable compilation of the same accounts at minor-head level), the State-wise parts of
RBI Appendices I-IV and the e-STATES workbook (only the All States and UTs blocks are needed), and
RBI Statements other than 13-15, 17, 36. See docs/phase1/issues/state_fiscal.md.
"""

from __future__ import annotations

from pipeline.core.unit import BuildContext, Dataset, FetchContext
from pipeline.ingest.state_fiscal import fc16, rbi
from pipeline.ingest.state_fiscal import sources as S
from pipeline.ingest.state_fiscal.common import territory_problems

UNIT = "state_fiscal"
SOURCES = [S.FC16, S.FC16_ULB, S.RBI_SF, S.RBI_MUNI, S.RBI_PRI]


def fetch(ctx: FetchContext) -> None:
    S.fetch_all(ctx)


# DECISIONS D1-9: a row's geography means one fixed territory. Rows whose period does not sit inside
# their territory's existence (pipeline/core/geo.py HISTORICAL dates) must be declared here, with the
# reason stated in their provenance notes (checked: common.TERRITORY_NOTE_MARKERS, verify-13); anything
# else fails the build.
_AP_2014_15 = {
    ("IN-XAP", "2014-15", "straddle"): "undivided AP's accounts for 1 April-1 June 2014",
    ("IN-AP", "2014-15", "straddle"): "Andhra Pradesh's accounts from 2 June 2014",
    ("IN-TS", "2014-15", "straddle"): "Telangana's accounts from 2 June 2014",
}
_ACC_2000_01 = {
    ("IN-UP", "2000-01", "straddle"): "UP's accounts, undivided to 8 Nov 2000",
    ("IN-JH", "2000-01", "straddle"): "Jharkhand's accounts from 15 Nov 2000",
}
_JK_2019_20 = {("IN-JK", "2019-20", "straddle"): "printed J&K row; the State became UTs on 31 Oct 2019"}
TERRITORY_DECLARED: dict[str, dict[tuple[str, str, str], str]] = {
    f"{UNIT}_fc16_kfi": _AP_2014_15
    | {(g, p, "before"): "GSDP of the successor territory (own provenance record)"
       for g in ("IN-AP", "IN-TS") for p in ("2011-12", "2012-13", "2013-14")}
    | {("IN-XAP", f"{y}-{(y + 1) % 100:02d}", "after"): "GSDP of the former territory = AP + TS (own record)"
       for y in range(2015, 2024)},
    f"{UNIT}_fc16_state_accounts": _AP_2014_15
    | _ACC_2000_01
    | {("IN-UK", "2000-01", "straddle"): "Uttarakhand's accounts from 9 Nov 2000"},
    f"{UNIT}_fc16_local_body_assistance": _AP_2014_15 | _ACC_2000_01,
    f"{UNIT}_rbi_sf_statements": _JK_2019_20,
    f"{UNIT}_rbi_municipal": _JK_2019_20,
}  # fmt: skip


def build(ctx: BuildContext) -> list[Dataset]:
    out = _build(ctx)
    notes = {k: v["notes"] for k, v in ctx.provenance.items()}
    problems = [
        f"{d.name}: {p}" for d in out for p in territory_problems(d.df, TERRITORY_DECLARED.get(d.name, {}), notes)
    ]
    if problems:
        raise ValueError("State/UT territory check (DECISIONS D1-9):\n" + "\n".join(problems))
    return out


def _build(ctx: BuildContext) -> list[Dataset]:
    return [
        fc16.build_kfi(ctx),
        fc16.build_transfers(ctx),
        fc16.build_subsidies(ctx),
        *fc16.build_state_accounts(ctx),
        fc16.build_ulb(ctx),
        rbi.build_statements(ctx),
        rbi.build_app_tables(ctx),
        rbi.build_appendices(ctx),
        rbi.build_municipal(ctx),
        rbi.build_pri(ctx),
    ]
