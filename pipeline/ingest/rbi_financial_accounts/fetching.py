"""fetch() for rbi_financial_accounts: www.rbi.org.in HTML pages, DEA PDFs and (at most one
pass per run) rbidocs.rbi.org.in files, following DECISIONS D1-1 and D1-4."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from pipeline.core.fetch import AccessBlocked
from pipeline.core.unit import FetchContext
from pipeline.ingest.rbi_financial_accounts import common as C


@dataclass
class _RbidocsGate:
    """D1-4: each run tries rbidocs at most once per file, >= 10 s apart, and stops at the first
    challenge (every later rbidocs file of the run is skipped and reported)."""

    blocked: str | None = None
    last: float = 0.0
    skipped: list[str] = field(default_factory=list)

    def fetch(self, ctx: FetchContext, source_id: str, url: str, name: str, referer: str) -> None:
        if self.blocked:
            self.skipped.append(name)
            ctx.warn(f"rbidocs: skipped {name} (host challenged earlier in this run; D1-4)")
            return
        assert ctx.store is not None
        if ctx.offline and f"{source_id}/{name}" not in ctx.store.pins:
            self.skipped.append(name)
            ctx.warn(f"offline: {name} was never pinned (rbidocs blocked when fetched); the build skips it")
            return
        network = not ctx.offline and not _is_cached(ctx, source_id, name, url)
        if network:
            # >= 10 s from the end of the previous rbidocs response to the start of this request
            wait = self.last + C.RBIDOCS_GAP_S - time.monotonic()
            if wait > 0:
                time.sleep(wait)
        try:
            ctx.fetch(source_id, url, name=name, referer=referer)
        except AccessBlocked as e:
            self.blocked = str(e)
            ctx.warn(f"rbidocs BLOCKED on {name}: {e}. No further rbidocs request this run (D1-4).")
        finally:
            if network:
                self.last = time.monotonic()


def _is_cached(ctx: FetchContext, source_id: str, name: str, url: str) -> bool:
    assert ctx.store is not None
    pin = ctx.store.pins.get(f"{source_id}/{name}")
    if not pin or pin.get("url") != url or ctx.refresh:
        return False
    return ctx.layout.raw_abs(pin["path"]).exists()


def hbs_table_ids(html: bytes) -> dict[int, int]:
    """{Handbook table number: PublicationsView id} from the Handbook listing page."""
    soup = BeautifulSoup(html, "lxml")
    out: dict[int, int] = {}
    for tr in soup.find_all("tr"):
        text = tr.get_text(" ", strip=True)
        m = re.match(r"Table (\d+)\s*:", text)
        if not m:
            continue
        ids = {
            int(g.group(1))
            for a in tr.find_all("a", href=True)
            if (g := re.search(r"PublicationsView\.aspx\?id=(\d+)", a["href"]))
        }
        if len(ids) != 1:
            continue
        n = int(m.group(1))
        if n in out and out[n] != next(iter(ids)):
            raise RuntimeError(f"HBS listing: table {n} has two PublicationsView ids")
        out[n] = next(iter(ids))
    return out


def fetch(ctx: FetchContext) -> None:
    # 1. Handbook 2025-26: listing, then the HTML view of each table (www.rbi.org.in, not challenged).
    listing = ctx.fetch(C.SRC_HBS, C.HBS_LANDING, name=C.HBS_LISTING_NAME, expect="html")
    ids = hbs_table_ids(listing.read_bytes())
    for t in C.HBS_TABLES:
        if t not in ids:
            raise RuntimeError(f"HBS table {t} is not on the Handbook listing page")
        ctx.fetch(C.SRC_HBS, C.HBS_VIEW.format(id=ids[t]), name=f"hbs_t{t}.html", referer=C.HBS_LANDING, expect="html")

    # 2. FSF 2023-24 Bulletin article (HTML; carries Table 1 and the link to the workbook).
    ctx.fetch(C.SRC_FSF, C.FSF_ARTICLE, name=C.FSF_ARTICLE_NAME, referer=C.FSF_LANDING, expect="html")

    # 3. DEA public-debt reports (open host; the fetch layer uses the OS trust store).
    for name, url in C.DEA_FILES.items():
        ctx.fetch(C.SRC_DEA, url, name=name, referer=C.DEA_LANDING)

    # 4. rbidocs, last and in priority order: the FSF workbook, then Bulletin tables 52(a)/(b).
    gate = _RbidocsGate()
    gate.fetch(ctx, C.SRC_FSF, C.FSF_XLSX, C.FSF_XLSX_NAME, C.FSF_ARTICLE)
    gate.fetch(ctx, C.SRC_HHFS, C.HHFS_52A, C.HHFS_52A_NAME, C.BULLETIN_LANDING)
    gate.fetch(ctx, C.SRC_HHFS, C.HHFS_52B, C.HHFS_52B_NAME, C.BULLETIN_LANDING)
    if gate.blocked:
        ctx.log(f"rbidocs challenged; skipped this run: {gate.skipped}. See docs/phase1/issues/{C.UNIT}.md")
