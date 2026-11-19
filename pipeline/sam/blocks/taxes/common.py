"""Shared names and small readers for the taxes block (private to the package)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import polars as pl

from pipeline.sam.framework import BlockContext, SamError

# clean datasets read by the block
RB = "union_fiscal_rb_receipts"  # Union Receipt Budget (actuals of year t in the budget of t+2)
FA = "union_fiscal_fa_receipts"  # Union Finance Accounts Statement 8 (audited)
FA_EXP = "union_fiscal_fa_expenditure"  # Union Finance Accounts Statement 9
EXP = "union_fiscal_exp_profile"  # Union Expenditure Profile (Statement 7, subsidies)
PPAC = "union_fiscal_ppac_exchequer"  # PPAC contribution of the petroleum sector to the exchequer
PIB = "union_fiscal_pib_gst"  # PIB monthly GST releases
SF = "state_fiscal_rbi_sf_appendices"  # RBI State Finances, Appendix I (all States + UTs with legislature)
FC16_SUB = "state_fiscal_fc16_subsidies"  # 16th Finance Commission subsidy tables (Centre + 21 States)
FC16_ACC = "state_fiscal_fc16_state_accounts"  # 16th FC compilation of State Finance Accounts
ULB = "state_fiscal_ulb_cityfinance"  # cityfinance.in ULB dump (284 ULBs)
SUPPLY, USE = "io_tables_sut_supply", "io_tables_sut_use"
IFPRI = "io_tables_ifpri_2223_datapaper"
NAS11, NAS42, NAS71 = "mospi_nas_2026_s1_1", "mospi_nas_2026_s4_2", "mospi_nas_2026_s7_1"
OLD = "mospi_nas_2026_oldbase_soa_{}"  # old-base (2011-12) NAS 2024 sequence of accounts, 2022-23 FRE
IRDAI_LIFE, IRDAI_NONLIFE = "finsector_markets_irdai_life", "finsector_markets_irdai_nonlife"
RTP_BANKS, RTP_NBFI, RTP_COOP = (
    "rbi_banking_corporate_rtp_banks",
    "rbi_banking_corporate_rtp_nbfi",
    "rbi_banking_corporate_rtp_coop",
)
FSF_BS = "rbi_financial_accounts_fsf_balance_sheets"
HCES_A2 = "hces_consumption_a2_fractile_persons"
PRODUCT_MAP = "io_tables_sut_product_to_sam34"

HCES_PERIOD = "2023-08/2024-07"  # HCES 2023-24 survey window (not the fiscal year)
OLD_YEAR = "2022-23"  # the last year of the old-base sequence of accounts
RTP_VINTAGE = "2025-12-29"  # RBI Report on Trend and Progress 2024-25 (latest revision of 2023-24)

PRODUCT_TAX_ACCOUNTS = ["T_CGST", "T_SGST", "T_GCES", "T_UEXC", "T_SVAT", "T_SEXC", "T_OPRT"]
GST_ACCOUNTS = ("T_CGST", "T_SGST", "T_GCES")


def sf_series(code: str) -> str:
    """RBI State Finances Appendix I series for all States + UTs with legislature, accounts (actuals)."""
    return f"app1.total_revenue.{code}.in.all_states_uts.actuals"


def total(
    ctx: BlockContext, dataset: str, series: Sequence[str], period: str | None = None, **kw
) -> tuple[float, list[str]]:
    """Sum of several single-row series (each must match exactly one row) and their prov_ids."""
    v, pids = 0.0, []
    for s in series:
        x, p = ctx.value(dataset, s, **({"period": period} if period else {}), **kw)
        v += x
        pids.append(p)
    return v, sorted(set(pids))


def prefixed(ctx: BlockContext, dataset: str, prefix: str, period: str, **kw) -> pl.DataFrame:
    """All rows whose series_id starts with `prefix` for `period` (fails if there are none)."""
    ids = sorted(s for s in ctx.frame(dataset)["series_id"].unique().to_list() if s.startswith(prefix))
    if not ids:
        raise SamError(f"{dataset}: no series starting with {prefix!r}")
    return ctx.rows(dataset, series_id=ids, period=period, **kw)


def pids(*groups: Iterable[str]) -> list[str]:
    out: set[str] = set()
    for g in groups:
        out |= set(g)
    return sorted(out)
