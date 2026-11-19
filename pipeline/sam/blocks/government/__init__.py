"""Government block: the Centre (G_CEN) and the States (G_STA, incl. local bodies) in the SAM, FY 2023-24.

Refs written: C2a, R1, R2, R2k, T2b, R6, R7, R7x, R9 (constraint only), R9a, R9b, R9d, R10, R18, K3 (constraint
only), K3a, K6, K8e. Not implemented (no entries, reasons in docs/phase2/issues/government.md): R15 (NAS 6.1 books
GG transfers with the RoW as capital: they are in K6) and R16 (fees are sales of non-market output; vehicle tax
is a product tax, DECISIONS D2-4; old-base NAS households pay no D59/D7 to GG).

Reads (vintage 'latest' everywhere; each dataset carries one vintage for 2023-24 today):
- union_fiscal: Finance Accounts 2023-24 (fa_receipts, fa_expenditure, fa_gia; 2024-12-10, audited), AFS,
  Expenditure Profile St 7 / St 18, GCCA St 6 and Receipt Budget (2025-02-01, actuals).
- state_fiscal: RBI State Finances appendices (2026-01-23, all States + UTs with legislature), FC16 KFI, State
  Finance Accounts and subsidy data (2026-02-03/05).
- mospi_nas_2026 (2026-08-31): St 1.1, 1.9, 1.14 (GG totals), 4.2 (COFOG transfers), 6.1 (RoW capital
  transfers), 7.1 / 7.1A / 7.1B / 7.1C (payer keys, net production taxes).
- external_sector invisibles (official transfers), finsector_markets PFRDA (State NPS employer contribution),
  rbi_banking_corporate RBI surplus timing (check).
- DEPENDS: production (GFCE targets, P9 on C_RPET), factors (F4b, F2 non-farm, public_sector_wage_key),
  households (hh_keys pop_persons), taxes (G <- T_PIT/T_CIT, for the D2-5 evidence only), factors'
  gg_centre_state_key (the K3a remainder key). See deps.py.
- state_fiscal FC16 cityfinance ULB dump (2026-02-19): urban local bodies' revenues and revenue expenditure (K3a).

What is estimated and how (details in each provenance record):
- C2a: free grain 100% Centre (fixed); own output split by a 5x2 RAS with the F4b institutional key as the Centre
  column total (D2-8) and cash functional revenue expenditure as seed (public works seeded once, in CNST).
- R2/R2k: treasury receipts (RBI SF) less T2b(i) and R2k; plus, under the institutional boundary (D2-8, XR-7),
  CSS released outside State treasuries (St 18 CSS - MH 3601.06 net releases), current/capital by the IGAS-2
  'Others' capital share.
- R7x (D2-9): Union interest from PSUs / other parties / government servants, petroleum rents, telecom licence
  fee and USO levy; States' interest receipts (less the 14-day treasury-bill interest from the Centre, intra-GG),
  mining royalties (FC16 MH 0853) and petroleum royalties; payers by NAS 7.1A/B/C GOS keys. Spectrum (WPC)
  receipts are excluded pending the NAD answer (rent vs asset sale).
- R9a/R9d/R10: official totals split over the 10 groups by the public-sector wage key (pensions) or population
  (R10): low confidence. R9b's variant is chosen by the D2-5 GG-GDI evidence test; DECISIONS D2-20 allows 'none',
  which fits best and is written (no R9b entries; the Centre-only and Centre + States values are a memo).
- K3a: cash-to-NAS gross-saving bridge (no CFC step: CFC cancels in gross saving) plus the urban local bodies'
  revenue surplus (FC16 cityfinance) for the States; the unexplained remainder is allocated by the NVA of the GG
  units outside the treasury accounts (NAS 4.1, factors' F4b split); written as +/- pairs.
- K6: RoW on the NAS 6.1 basis (fixed); domestic from NAS 4.2 COFOG by recipient, Centre = identifiable IGAS-2
  non-government grantees (statutory bodies are GG: their grants are intra-G_CEN), States the residual.
- R6/R7: Union FA MH 0050 minor heads and RBI SF App. I ii.c.2; R7 on a mixed head (101 public undertakings,
  States' dividends) is `derived` (payer by assumption), fixed at the published total.
Writes the satellites gov_c2a_keys, gov_grants_bridge, gov_r7x_items, gov_transfer_classification,
gov_fiscal_bridge and gov_r9b_sensitivity.
"""

from __future__ import annotations

from pipeline.sam.blocks.government.deps import read_deps
from pipeline.sam.blocks.government.parts import assemble
from pipeline.sam.framework import BlockContext, BlockResult

BLOCK = "government"
REFS = ["C2a", "R1", "R2", "R2k", "T2b", "R6", "R7", "R7x", "R9", "R9a", "R9b", "R9d", "R10", "R18", "K3", "K3a",
        "K6", "K8e"]  # fmt: skip
DEPENDS = ["production", "households", "factors", "taxes"]


def build(ctx: BlockContext) -> BlockResult:
    return assemble(ctx, read_deps(ctx))
