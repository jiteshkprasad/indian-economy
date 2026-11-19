"""Where every raw file of the state_fiscal unit comes from, and the polite rbidocs fetch loop.

rbidocs.rbi.org.in (DECISIONS D1-4): at most one attempt per file per run, at least 10 s between
rbidocs requests, and the first challenge (AccessBlocked) stops every further rbidocs request in
this run. Files already pinned are never re-requested (no network I/O), so a later run only asks
for what is still missing. The hashed rbidocs URLs are read from the www.rbi.org.in listing pages,
which were never challenged, instead of being hard-coded.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from bs4 import BeautifulSoup

from pipeline.core.fetch import AccessBlocked, FetchError, OfflineMissing
from pipeline.core.unit import FetchContext

FC16 = "fc16_relevant_data"
FC16_ULB = "fc16_ulb_cityfinance_dump"
RBI_SF = "rbi_state_finances_study"
RBI_MUNI = "rbi_municipal_finances"
RBI_PRI = "rbi_pri_finances"

FC16_BASE = "https://fincomindia.nic.in/asset/doc/commission-reports/16th-FC/relevant-data/"
FC16_LANDING = "https://fincomindia.nic.in/commission-reports-sixteenth"
FC16_FILES = {
    "fc16_kfi.xlsx": "State%20Finances%20-%20Key%20Fiscal%20Indicators.xlsx",
    "fc16_transfers.xlsx": "Time%20series%20of%20transfer%20of%20resources%20from%20Centre%20to%20States.xlsx",
    "fc16_subsidies.xlsx": "Sector%20wise%20Subsidies%20and%20Transfers.xlsx",
    "fc16_state_accounts.xlsx": "State%20Finance%20Accounts%20-%20Revenue%20and%20Expenditure.xlsx",
}
FC16_ULB_FILE = ("fc16_ulb_cityfinance.xlsx", "FC16%20ULB%20Data%20Dump%20Cityfinance.xlsx")

RBI_SF_LISTING = (
    "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=State%20Finances%20:%20A%20Study%20of%20Budgets"
)
RBI_MUNI_LISTING = "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Report%20on%20Municipal%20Finances"
RBI_PRI_LISTING = (
    "https://www.rbi.org.in/Scripts/OccasionalPublications.aspx?head=Finances%20of%20Panchayati%20Raj%20Institutions"
)
LISTINGS = {
    RBI_SF: ("rbi_sf_listing.html", RBI_SF_LISTING),
    RBI_MUNI: ("rbi_muni_listing.html", RBI_MUNI_LISTING),
    RBI_PRI: ("rbi_pri_listing.html", RBI_PRI_LISTING),
}

RBIDOCS_GAP_S = 10.0  # DECISIONS D1-4: at least 10 s between rbidocs requests


@dataclass(frozen=True)
class RbiFile:
    """One rbidocs XLSX, found on its listing page by the start of the row text and the start of
    the file name (both needed: appendix parts share row texts across Appendices I-IV)."""

    source_id: str
    name: str  # our pin name
    row_prefix: str  # the listing row text starts with this (case-insensitive, spaces collapsed)
    file_prefix: str  # the rbidocs file name starts with this
    row_contains: str = ""


def _sf(name: str, row: str, file: str, contains: str = "") -> RbiFile:
    return RbiFile(RBI_SF, name, row, file, contains)


# In priority order: the all-States aggregates the SAM needs first, then State-wise detail.
RBI_FILES: tuple[RbiFile, ...] = (
    _sf("sf2526_app_t02.xlsx", "Appendix Table 2:", "02_APP"),
    _sf("sf2526_appx1_all.xlsx", "States:", "1APPENDIX", "All States"),
    _sf("sf2526_appx2_all.xlsx", "States:", "2APPENDIX", "All States"),
    _sf("sf2526_appx3_all.xlsx", "States:", "3APPENDIX", "All States"),
    _sf("sf2526_appx4_all.xlsx", "States: All States", "4APPENDIX"),
    _sf("sf2526_st13.xlsx", "Statement 13:", "13_ST"),
    _sf("sf2526_st14.xlsx", "Statement 14:", "14_ST"),
    _sf("sf2526_st15.xlsx", "Statement 15:", "15_ST"),
    _sf("sf2526_st17.xlsx", "Statement 17:", "17_ST"),
    _sf("sf2526_st36.xlsx", "Statement 36:", "36_ST"),
    _sf("sf2526_app_t01.xlsx", "Appendix Table 1:", "01_APP"),
    _sf("sf2526_app_t03.xlsx", "Appendix Table 3:", "03_APP"),
    _sf("sf2526_app_t09.xlsx", "Appendix Table 9:", "09_APP"),
    _sf("sf2526_app_t11.xlsx", "Appendix Table 11:", "11_APP"),
    RbiFile(RBI_PRI, "pri_app1_part7.xlsx", "States: Uttarakhand, West Bengal, All States", "7APPENDIXI2"),
    RbiFile(RBI_PRI, "pri_app2_part7.xlsx", "States: Uttarakhand, West Bengal, All States", "7APPENDIXII"),
    RbiFile(RBI_PRI, "pri_ch2.pdf", "II. Fiscal Position of Panchayati Raj Institutions", "2FISCALPOSITION"),
    RbiFile(RBI_MUNI, "muni_st01.xlsx", "Statement 1:", "01STATEMENTS"),
    RbiFile(RBI_MUNI, "muni_st04.xlsx", "Statement 4:", "04STATEMENTS"),
    RbiFile(RBI_MUNI, "muni_st08.xlsx", "Statement 8:", "08STATEMENTS"),
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def listing_xlsx_links(html: bytes) -> list[tuple[str, str]]:
    """(row text, url) for every rbidocs .XLSX/.PDF link in the innermost table rows of a listing page."""
    soup = BeautifulSoup(html, "lxml")
    out: list[tuple[str, str]] = []
    for tr in soup.find_all("tr"):
        if tr.find("tr") is not None:
            continue
        text = _norm(tr.get_text(" ", strip=True))
        for a in tr.find_all("a", href=True):
            href = a["href"].strip()
            if "rbidocs.rbi.org.in" in href and href.lower().endswith((".xlsx", ".pdf")):
                out.append((text, href))
    return out


def resolve(f: RbiFile, links: list[tuple[str, str]]) -> str:
    """The unique URL for one wanted file, or a loud error if the listing changed."""
    hits = sorted(
        {
            url
            for text, url in links
            if text.startswith(_norm(f.row_prefix))
            and _norm(f.row_contains) in text
            and url.rsplit("/", 1)[-1].upper().startswith(f.file_prefix.upper())
            and url.lower().endswith(f.name.rsplit(".", 1)[-1])
        }
    )
    if len(hits) != 1:
        raise RuntimeError(f"{f.name}: expected exactly one listing link for {f}, found {hits}")
    return hits[0]


def fetch_all(ctx: FetchContext) -> None:
    for name, path in FC16_FILES.items():
        ctx.fetch(FC16, FC16_BASE + path, name=name, referer=FC16_LANDING)
    ctx.fetch(FC16_ULB, FC16_BASE + FC16_ULB_FILE[1], name=FC16_ULB_FILE[0], referer=FC16_LANDING)

    links: dict[str, list[tuple[str, str]]] = {}
    for sid, (name, url) in LISTINGS.items():
        links[sid] = listing_xlsx_links(ctx.fetch(sid, url, name=name, expect="html").read_bytes())

    blocked: str | None = None
    last = 0.0
    for f in RBI_FILES:
        url = resolve(f, links[f.source_id])
        pinned = _is_pinned(ctx, f)
        if pinned and not ctx.refresh:
            ctx.fetch(f.source_id, url, name=f.name, referer=LISTINGS[f.source_id][1])  # cache only
            continue
        if ctx.offline:
            ctx.fetch(f.source_id, url, name=f.name)  # raises OfflineMissing for an unpinned file
            continue
        if blocked:
            ctx.warn(f"{f.source_id}/{f.name}: not requested (rbidocs challenged earlier in this run: {blocked})")
            continue
        wait = RBIDOCS_GAP_S - (time.monotonic() - last)
        if last and wait > 0:
            time.sleep(wait)
        try:
            ctx.fetch(f.source_id, url, name=f.name, referer=LISTINGS[f.source_id][1])
        except AccessBlocked as e:
            blocked = str(e)[:300]
            ctx.warn(f"{f.source_id}/{f.name}: rbidocs BLOCKED, stopping rbidocs for this run (D1-4): {blocked}")
        finally:
            last = time.monotonic()


def _is_pinned(ctx: FetchContext, f: RbiFile) -> bool:
    try:
        ctx.raw(f.source_id, f.name)
    except OfflineMissing, FetchError:
        return False
    return True
