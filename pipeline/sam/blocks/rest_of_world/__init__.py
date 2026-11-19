"""Rest of the world block: India's current account (R_ROW) and capital and financial account (K_ROW) with
the rest of the world, FY 2023-24, Rs crore, current prices. Plan: docs/phase2/plans/rest_of_world.md (its s.8
and DECISIONS D2-1..D2-18 override the plan body). Issues: docs/phase2/issues/rest_of_world.md.

Reads (clean data; vintages named where a series has several):
- mospi_nas_2026_s6_1, mospi_nas_2026_s1_9 (NAS 2026, 31 Aug 2026): every control total (R11, R12, R13, R14,
  R14a, K5, K8b totals, BoP acceptance totals).
- external_sector_bop_bpm6_annual, _bop_overall_annual, _invisibles_annual, _bop_bpm6_quarterly (RBI HBS BoP,
  31 Jul 2026): primary income by type, the financial account by functional line, checks.
- keys: rbi_financial_accounts_fsf_balance_sheets (FSF RoW stocks by counterparty, vintage 2026-01-21),
  external_sector_fla_census (2023-24 round, 2024-10-11), rbi_banking_corporate_rtp_banks (2025-12-29),
  rbi_banking_corporate_rbi_accounts (RBI AR, 2025-05-29), rbi_financial_accounts_hbs_gsec_ownership (T107),
  union_fiscal_fa_expenditure / _fa_receipts, state_fiscal_rbi_sf_appendices, external_sector_nri_deposits,
  external_sector_remittance_survey (2023-24 round, 2025-03-19), external_sector_ecb_monthly_2324,
  external_sector_lrs_outward (evidence only), io_tables_sut_supply (the CIF memo row, D2).
- satellites: trade_satellites_imf_imts_fy, _comtrade_fy_2324, _batis_2023_2024, external_sector_ites_survey,
  external_sector_fx_inr_usd (S1, S2).
- DEPENDS: production (P5/P6 entries: D2 and R_ROW closure checks); households (hh_state_xwalk consumption
  levels for R11a; hh_keys pfce_total for R12a).

Writes entries: R11a (H_* <- R_ROW, remittances by group, estimated, free low); R12a (R_ROW <- H_U4/H_U5,
estimated, free low); R13 (E_*/G_* <- R_ROW by BoP type; E_RBI in two components per D2-7: RBI AR reserve
income anchored 2% + the unexplained BoP excess free low); R14 (R_ROW <- E_*/G_*: DI distributed, FPI interest
on government paper with fincorp's formula (XR-12), other portfolio income, external-assistance interest
(anchored 10%), NRI-deposit interest, other interest, reserve-asset debit, other primary income); R14a
(reinvested earnings, NAS 1.9 total, FLA/RTP payer split); K5 (K_ROW <- R_ROW, fixed); K8b (one fixed entry per
BoP functional line with its bop_function tag, the FPI-debt split I_GSEC/I_CBND free medium, two derived NAS
reconciliation lines); K8c (I_RESV <- K_RBI, fixed); D2 (R_ROW <- X_DISC, the SUT CIF memo, fixed).
Constraints: R11, R12, R13, R14 (+ BoP debit type totals), R14a, K8b totals, FPI debt, and the BoP acceptance
totals (current receipts / disbursements over every block's entries). R11 and R12 are constraint-only refs.
Satellites: row_property_income and row_financial_counterparts (interfaces for fincorp and capital_financial),
s3_remittance_sources (S3), s2_services_by_partner (S2), s1_goods_by_partner (S1), and the memo sensitivity bands
r11a_sensitivity (R11a: prior, hub-neutral, consumption-only) and r12a_sensitivity (R12a: BoP 1.C.1.2 on all groups).

Estimated and how: remittances by household group (State survey shares x households' State consumption key),
payers/recipients of property income (FSF, FLA, RTP, T107 keys), the FPI-debt split (T107), the S1/S2/S3
partner splits. Not written: R15 (government's current transfers with RoW: NAS books them as capital, K6; owned
by government). No FISIM adjustment on RoW property income (XR-13).
"""

from __future__ import annotations

from typing import Any

import polars as pl

from pipeline.sam.blocks.rest_of_world import _common as c
from pipeline.sam.blocks.rest_of_world._common import Out
from pipeline.sam.blocks.rest_of_world._current import build_current, transfer_sensitivities
from pipeline.sam.blocks.rest_of_world._financial import build_financial
from pipeline.sam.blocks.rest_of_world._trade import build_trade
from pipeline.sam.framework import BlockContext, BlockResult, SamError, Satellite

BLOCK = "rest_of_world"
REFS = ["R11", "R11a", "R12", "R12a", "R13", "R14", "R14a", "K5", "K8b", "K8c", "D2", "S1", "S2", "S3"]
DEPENDS = ["production", "households"]


def build(ctx: BlockContext) -> BlockResult:
    out = Out()
    build_current(ctx, out)
    build_financial(ctx, out)
    sats = interface_satellites(ctx, out)
    sats.update(build_trade(ctx, out))
    sats.update(transfer_sensitivities(ctx, out))
    return BlockResult(entries=out.entries, constraints=out.constraints, satellites=sats)


def _frame(rows: list[dict[str, Any]], dims: list[str]) -> pl.DataFrame:
    schema: dict[str, pl.DataType] = {"series_id": pl.String()}
    schema.update({d: pl.String() for d in dims})
    schema.update({"value": pl.Float64(), "unit": pl.String(), "status": pl.String(), "prov_id": pl.String()})
    return pl.DataFrame([{k: r.get(k) for k in schema} for r in rows], schema=schema, orient="row").sort("series_id")


def interface_satellites(ctx: BlockContext, out: Out) -> dict[str, Satellite]:
    """row_property_income (fincorp, government) and row_financial_counterparts (capital_financial K7b)."""
    rows = out.rows("row_property_income")
    if not rows:
        raise SamError("row_property_income: no rows")
    pid = ctx.prov(
        ref="R14",
        status="estimated",
        inputs=sorted({r["entry_prov_id"] for r in rows}),
        method=(
            "Interface table (CROSS_REVIEW s.4.3): every R13, R14 and R14a entry of this block, one row per "
            "(direction, BoP type, component, domestic account), value as written in the prior; entry_status and "
            "entry_prov_id give each entry's own status and provenance. fincorp subtracts these RoW parts from its "
            "interest/dividend totals (XR-4, XR-12) and reads E_RBI's two reserve-income components."
        ),
        source_id="rbi_hbs_external",
        notes="A copy of this block's own entries (BoP type totals from RBI HBS).",
    )
    for r in rows:
        r["status"], r["prov_id"] = "estimated", pid
    prop = _frame(rows, ["direction", "bop_type", "component", "account", "ref", "entry_status", "entry_prov_id"])

    crow = out.rows("row_financial_counterparts")
    if not crow:
        raise SamError("row_financial_counterparts: no rows")
    pid = ctx.prov(
        ref="K8b",
        status="estimated",
        inputs=sorted({r["entry_prov_id"] for r in crow} | set(out.memo["counterpart_key_pids"])),
        method=(
            "Interface table for capital_financial's K7b (CROSS_REVIEW s.4.3): for every K8b entry, the domestic "
            "counterpart capital account that issues the liability (direction row_acquires) or holds the asset "
            "(row_incurs), in the same instrument and with the same bop_function; value = the entry x the "
            "counterpart's share (key_method says which key: FLA t8 equity/debt, the R14a payer split, FSF F51 "
            "stocks, ECB registrations by borrower industry, HBS T107 for government paper, or a single named "
            "counterpart). 'unallocated_k9' lines (errors and omissions, NAS reconciliation) get no posting: "
            "capital_financial's K9 residuals absorb them. Rows of each entry add up to it exactly."
        ),
        source_id="rbi_hbs_external",
        notes="K8b entries from the RBI HBS BoP (and NAS 6.1); keys from FLA, FSF, ECB, T107, RTP.",
    )
    for r in crow:
        r["status"], r["prov_id"] = "estimated", pid
    cp = _frame(crow, ["line", "instrument", "bop_function", "direction", "counterpart", "key_method", "entry_prov_id"])
    return {
        "row_property_income": Satellite(
            "R14",
            prop,
            "RoW property income by direction x BoP type x component x "
            "domestic account (interface for fincorp and government)",
        ),
        "row_financial_counterparts": Satellite(
            "K8b",
            cp,
            "K8b lines x instrument x bop_function x direction x "
            "domestic counterpart K_* (interface for capital_financial K7b)",
        ),
    }


__all__ = ["BLOCK", "DEPENDS", "REFS", "build", "c"]
