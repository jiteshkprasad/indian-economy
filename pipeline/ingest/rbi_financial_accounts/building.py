"""build() for rbi_financial_accounts."""

from __future__ import annotations

from pipeline.core.unit import BuildContext, Dataset
from pipeline.ingest.rbi_financial_accounts import dea, fsf, hbs, hhfs


def build(ctx: BuildContext) -> list[Dataset]:
    raw, wb = fsf.load(ctx)
    return [
        fsf.build_balance_sheets(ctx, raw, wb),
        fsf.build_fwtw(ctx, raw, wb),
        fsf.build_instrument_sector(ctx, raw, wb),
        fsf.build_financing(ctx, raw, wb),
        hhfs.build(ctx),
        *hbs.build(ctx),
        *dea.build(ctx),
    ]
