"""fincorp block: financial corporations' income, government interest by holder, interest and dividends
between sectors, D44, non-life insurance, FC saving by sub-sector (gap-map refs F4a R3 R3a R3b R4 R5 R8 R8a
R9c R17 K2 K2a, satellite S9). Plan: docs/phase2/plans/fincorp.md (its s.8 and DECISIONS D2-x override the
body); issues: docs/phase2/issues/fincorp.md.

Reads (clean data, period 2023-24 unless stated; vintages named in each module):
- NAS 2026 (vintage 2026-08-31): St 1.9 (FC saving), 1.13 (FISIM by user), 7.1A/B/C (IC and OS/CFC by
  sector), 8.12 (FC GVA by sub-sector), 8.15.1 (GG IC); SUT 2023-24 value added of industries 55 and 56.
- Old-base NAS 2024 St 2.2 (private NFCs, 2022-23; vintage 2024-06-05): D4 resources and uses, NOS, CFC, as the
  DECISIONS D2-21 prior for private NFCs' net property income (dividends.py, R8 `distributed_income`).
- RBI Annual Report 2023-24 (`rbi_banking_corporate_rbi_accounts`, vintage 2024-05-30): employee cost,
  depreciation, Sch. 13/14 interest; RBI Trend & Progress 2023-24 (latest vintage, 2025-12-29 where present):
  bank, co-op, NBFC, HFC, AIFI, SPD P&L, wage bills, operating profits, cost/return rates.
- RBI FSF 2023-24 who-to-whom balance sheets (vintage 2026-01-21), end-March 2023 and 2024 averaged;
  HBS T107 G-sec ownership (vintage 2026-07-31); SEBI MF T72 AUM by investor class.
- Union Finance Accounts 2023-24 MH 2049 and Receipt MH 0049 (re-issue accrued interest/premium),
  Statement 14 (provident funds); RBI State Finances 2025-26 App. I-IV; FC16 KFI (cross-check); NSSF.
- IRDAI 2023-24 life (T24/T25), non-life (T44/T51), summary; EPFO AR 2023-24 (vintage 2024-12); PFRDA NPS.
- Other blocks (deps.py): households hh_keys and C4b FISIM by group; factors F1a wages, public-sector wage
  key, NFC GOS; government R6, R7, R7x (R7x only to measure E_NFPR's net D4); rest_of_world R13/R14 (RoW parts
  are never re-derived here).

Writes: entries for F4a, R3, R3a, R4, R5, R8, R8a, R9c, R17, K2a; constraints for F4a, K2, R3b, R9c, R17;
satellites fc_public_private, gov_interest_bridge, interest_fisim_bridge, dividend_matrix, mf_lookthrough,
d44_by_scheme, s9_funded_schemes (S9).

Estimated (and how): see each module's docstring and the provenance methods. Assumption parameters are their
own records: FISIM reference rate r*, corporate-bond rate, EPS/exempted-PF yield, private dividend/GOS ratio,
R17 payer split by line, MF 'corporates' -> E_NFPR.

Not written here (owned elsewhere): R_ROW rows/columns (rest_of_world R14/R13), GG dividends (R7) and the RBI
surplus (R6) (government), government property income from non-financial payers (R7x, government). Interest
received by GG from banks and NBFCs (deposits, and the bank/NBFC bonds and loans FSF shows GG holding) is R4 here
(verifier V-FIN-4, government-29). Dividends: the government parts of each issuer's total are government's R7 as
booked; the rest goes to non-government holders by FSF shares (V-FIN-3, V-FIN-6).

Checks on E_RBI: `k2a.rbi_cash_basis_evidence` (plan C3, D0-7) uses the RBI AR basis, i.e. the SAM entries
without rest_of_world's R14 reserve-asset debit; `k2a.rbi_prior_vs_nas` compares the K2a prior itself (all
entries, D2-7) and fails while that debit sits on E_RBI (issues fincorp-1, rest_of_world-26).
"""

from __future__ import annotations

from pipeline.sam.blocks.fincorp.assemble import assemble
from pipeline.sam.blocks.fincorp.deps import read_deps
from pipeline.sam.framework import BlockContext, BlockResult

BLOCK = "fincorp"
REFS = ["F4a", "R3", "R3a", "R3b", "R4", "R5", "R8", "R8a", "R9c", "R17", "K2", "K2a", "S9"]
DEPENDS = ["production", "households", "factors", "government", "rest_of_world"]


def build(ctx: BlockContext) -> BlockResult:
    return assemble(ctx, read_deps(ctx))
