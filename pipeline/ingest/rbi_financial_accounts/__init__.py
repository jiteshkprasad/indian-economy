"""RBI financial accounts: flow of funds, household financial saving, public-debt ownership.

Sources and vintages (all fetched 29 Sep 2026; files pinned in data/raw_pins/rbi_financial_accounts.yaml):
- rbi_fsf_fof: "Financial Stocks and Flow of Funds of the Indian Economy 2023-24" workbook
  FSF2023-24_21012026.xlsx (RBI Bulletin, 21 Jan 2026; rbidocs) plus the Bulletin article page.
  Compiled before the NAS base revision (old 2011-12 series boundaries).
- rbi_hh_fin_savings: RBI Bulletin September 2026 (25 Sep 2026), Current Statistics tables 52(a)
  and 52(b) (PDF, rbidocs).
- rbi_hbs: Handbook of Statistics on the Indian Economy 2025-26 (31 Jul 2026), HTML table views
  on www.rbi.org.in for T11, T12, T49, T107, T109 (and T39, pinned but not ingested).
- dea_public_debt_reports: DEA Quarterly Reports on Public Debt Management Jan-Mar 2023 and
  Jan-Mar 2024, and the Status Paper on Government Debt 2023-24 (PDFs, dea.gov.in).

Datasets (Rs crore, current prices, unless stated):
- _fsf_balance_sheets   FSF St 1-5: 30 sector/sub-sector balance sheets by SNA instrument x
                         counterparty; stocks end-March 2012..2024, transactions and (where printed)
                         valuation changes 2012-13..2023-24.
- _fsf_fwtw             FSF S 6.1-6.13: sector x sector from-whom-to-whom matrices.
- _fsf_instrument_sector FSF S 7.1-7.13: instrument x sector matrices.
- _fsf_financing        FSF S 8.1-8.3: financing of private NFCs, general government, households.
- _hh_finsav_52ab       Bulletin 52(a) household flows (quarterly + annual 2022-23..2025-26) and
                         52(b) household stocks (quarter ends Jun 2022..Mar 2026); per cent of GDP rows.
- _hbs_saving           HBS T11 sector gross saving (base 2011-12 and 2022-23 columns) and T12
                         household financial flows 1983-84..2023-24 (NAS 2025, old base).
- _hbs_gsec_ownership   HBS T107 ownership of Central dated securities, SGS and T-bills (end-March
                         2022..2026; totals Rs crore, shares per cent).
- _hbs_small_savings    HBS T109 small savings receipts and outstandings 1986-87..2024-25.
- _hbs_scb_balance_sheet HBS T49 consolidated SCB balance sheet end-March 2006..2025.
- _dea_gsec_ownership   DEA ownership shares of dated securities / T-bills (QR T4.4/T4.5, Status
                         Paper T2.10 and HB-5 quarterly 2014..2024).
- _dea_central_debt     DEA Status Paper HB-1A/HB-1B Central Government debt and Public Account
                         liabilities by component, end-March 2002..2024.

Skipped, and why: FSF 'Summary' (a re-cut of St 1-5), S 8.4-8.7 (legacy 'Rs Billion' sheets,
2011-12..2017-18), S 9.x (percentage compositions derivable from S 6/S 7); the FSF article's
Table 1 (net financial wealth, per cent of old-base GDP; derivable); HBS T39 (RBI balance sheet;
three-panel HTML with bracketed memo rows; FSF St 1.1 covers RBI); DEA QR Table 4.1 (provisional
duplicate of the Status Paper HB tables). Nothing here is estimated: every row is 'official'.

Access: www.rbi.org.in HTML and dea.gov.in are fetched normally; rbidocs.rbi.org.in files are
fetched last, at most once each per run, >= 10 s apart, stopping at the first challenge
(DECISIONS D1-4). All rbidocs files fetched cleanly on 29 Sep 2026. Problems and publisher
inconsistencies are logged in docs/phase1/issues/rbi_financial_accounts.md.
"""

from __future__ import annotations

from pipeline.ingest.rbi_financial_accounts.building import build  # noqa: F401
from pipeline.ingest.rbi_financial_accounts.fetching import fetch  # noqa: F401

UNIT = "rbi_financial_accounts"
SOURCES = ["rbi_fsf_fof", "rbi_hh_fin_savings", "rbi_hbs", "dea_public_debt_reports"]
