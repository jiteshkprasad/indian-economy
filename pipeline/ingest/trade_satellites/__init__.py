"""Trade satellites S1 (goods by partner and product group) and S2 (services by partner and EBOPS
item) for the FY 2023-24 SAM, plus the history the same files give cheaply.

Sources and datasets (every value in US$ million, current prices; the calendar-year vs Indian
fiscal-year basis is explicit in `period_type`):
- IMF IMTS (`imf_sdmx`), India as reporter, exports FOB and imports CIF by partner:
  `_imf_imts_monthly` (Jan 2011 to latest month), `_imf_imts_fy` (fiscal years summed from
  complete monthly data, `derived`), `_imf_imts_annual` (calendar years, 1948 on). Vintage = the
  IMF publication date in the attribute file (31 Aug 2026).
- UN Comtrade keyless preview (`un_comtrade`, the fw-15 public part): `_comtrade_monthly_2324`
  (Apr 2023 to Mar 2024: totals by every partner, HS chapters x World, HS chapters x the top 30
  partners) and `_comtrade_fy_2324` (FY 2023-24 sums, `derived`). Vintage = each month's
  Comtrade release date.
- OECD-WTO BaTIS (`oecd_wto_batis`): `_batis_2023_2024` (every partner x EBOPS item, three
  measures) and `_batis_history` (2005-2022, total services by partner and World by item).
  Calendar years only.

Skipped, and why (details in docs/phase1/issues/trade_satellites.md):
- Commerce TradeStat / DGCI&S (`commerce_tradestat`): not fetched. Its tables come only from a
  Laravel form POST that needs a CSRF token and a session cookie, which `ctx.fetch` cannot send
  (framework request filed), and DGCI&S requires written permission to re-disseminate.
- No rupee conversion: US$ -> Rs crore needs an INR_per_USD series from another unit (DEPENDS).
  external_sector builds one but is not yet committed and verified (issue trade_satellites-9).
  No FY estimate for BaTIS (0.75/0.25 calendar weighting is Phase 2).
"""

from __future__ import annotations

from pipeline.core.fetch import AccessBlocked, FetchError
from pipeline.core.unit import BuildContext, Dataset, FetchContext

from . import batis, comtrade, imf
from ._common import UNIT as _UNIT

UNIT = _UNIT
SOURCES = ["imf_sdmx", "un_comtrade", "oecd_wto_batis"]


def fetch(ctx: FetchContext) -> None:
    blocked: list[str] = []
    for src, mod in (("imf_sdmx", imf), ("oecd_wto_batis", batis), ("un_comtrade", comtrade)):
        try:
            mod.fetch(ctx)
        except AccessBlocked as e:  # stop this host for the run (D1-1b); keep the other sources going
            ctx.warn(f"{src}: access blocked; the rest of this source was skipped: {e}")
            blocked.append(src)
    if blocked:
        raise FetchError(f"access blocked for {blocked}; see the warnings and log it in the issues file")


def build(ctx: BuildContext) -> list[Dataset]:
    return [*imf.build(ctx), *comtrade.build(ctx), *batis.build(ctx)]
