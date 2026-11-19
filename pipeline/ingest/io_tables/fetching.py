"""Downloads for the io_tables unit (the only network code in the unit; everything goes through ctx.fetch)."""

from __future__ import annotations

from typing import Any

from pipeline.core.fetch import AccessBlocked, OfflineMissing
from pipeline.core.unit import FetchContext

MOSPI_CHAPTER_API = "https://www.mospi.gov.in/api/publications-reports/get-web-chapter-data"
MOSPI_ROOT = "https://www.mospi.gov.in/"
MOSPI_UPLOADS = MOSPI_ROOT + "uploads/"

# --- MoSPI Supply and Use Tables (publication 847) --------------------------------------------
SUT_SRC = "mospi_sut_2022base"
SUT_PUB = 847
SUT_LANDING = f"https://www.mospi.gov.in/publications-reports/innerpage/{SUT_PUB}"
# Pin names (stable) -> the tail of the file name in the MoSPI listing. The listing is matched by
# this tail, so a re-upload under a new timestamp prefix is found, re-downloaded and re-pinned.
SUT_FILES = {
    "sut_2022_23.xlsx": "_Supply_Use_table_2022-23_(1).xlsx",
    "sut_2023_24.xlsx": "_Supply_Use_table_2023-24_(1).xlsx",
    "sut_note_2022_23_2023_24.pdf": "_Note_Supply_Use_Tables_2022-23,2023-24_(1).pdf",
}

# --- MoSPI Energy Statistics India 2026 (publication 2817) ------------------------------------
ENERGY_SRC = "mospi_energy_statistics"
ENERGY_PUB = 2817
ENERGY_LANDING = f"https://www.mospi.gov.in/publications-reports/innerpage/{ENERGY_PUB}"
ENERGY_FILES = {"es2026_chapter_9.pdf": "_Chapter-9.pdf"}

# --- ADB Key Indicators Database: India national IOT -------------------------------------------
ADB_SRC = "adb_mrio"
ADB_LANDING = "https://kidb.adb.org/globalization/current"
ADB_FILES = {"adb_ind_iot_2000_2007_2024.xlsx": "https://kidb.adb.org/download/mrio-file/211"}

# --- OECD ICIO 2025 (small, 2016-2022) ---------------------------------------------------------
ICIO_SRC = "oecd_icio_2025"
ICIO_LANDING = "https://www.oecd.org/en/data/datasets/inter-country-input-output-tables.html"
ICIO_ZIP = "https://webfs-sti.oecd.org/files/STI-PIE/ICIO/2025/2016-2022_SML.zip"
ICIO_README = "https://webfs-sti.oecd.org/files/STI-PIE/ICIO/2025/ReadMe_ICIO_small.xlsx"


# --- IFPRI Nexus SAM India 2022/23: the open data paper only (dataset is guestbook-gated) ---------
IFPRI_SRC = "ifpri_nexus_sam_india_2022_23_paper"
IFPRI_LANDING = "https://hdl.handle.net/10568/155099"
IFPRI_PAPER = "https://cgspace.cgiar.org/server/api/core/bitstreams/ff7b1ece-8897-4567-be3a-4c99db75dca3/content"


def _listing(ctx: FetchContext, src: str, pub: int, landing: str) -> list[str]:
    doc = ctx.fetch(
        src,
        MOSPI_CHAPTER_API,
        name=f"chapters_{pub}.json",
        method="POST",
        json_body={"publication_id": str(pub)},
        referer=landing,
    ).read_json()
    urls: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "path" and isinstance(v, str):
                    # new uploads are listed relative to the site root ('uploads/...')
                    url = MOSPI_ROOT + v if v.startswith("uploads/") else v
                    if url.startswith(MOSPI_UPLOADS):
                        urls.append(url)
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc)
    return urls


def _pick(urls: list[str], tail: str, what: str) -> str:
    hits = sorted({u for u in urls if u.endswith(tail)})
    if len(hits) != 1:
        raise RuntimeError(f"{what}: expected exactly one listing entry ending in {tail!r}, found {hits}")
    return hits[0]


def fetch_all(ctx: FetchContext) -> None:
    urls = _listing(ctx, SUT_SRC, SUT_PUB, SUT_LANDING)
    for name, tail in SUT_FILES.items():
        ctx.fetch(SUT_SRC, _pick(urls, tail, "SUT publication 847"), name=name, referer=SUT_LANDING)

    urls = _listing(ctx, ENERGY_SRC, ENERGY_PUB, ENERGY_LANDING)
    for name, tail in ENERGY_FILES.items():
        ctx.fetch(ENERGY_SRC, _pick(urls, tail, "Energy Statistics publication 2817"), name=name, referer=ENERGY_LANDING)

    for name, url in ADB_FILES.items():
        ctx.fetch(ADB_SRC, url, name=name, referer=ADB_LANDING, expect="xlsx")

    ctx.fetch(IFPRI_SRC, IFPRI_PAPER, name="ifpri_sam_india_2022_23_data_paper.pdf", referer=IFPRI_LANDING, expect="pdf")

    # ICIO: optional prior. A Cloudflare challenge is logged (issues file) and never worked around;
    # the build does not need this file (P6a falls back to the ADB table).
    try:
        ctx.fetch(ICIO_SRC, ICIO_README, name="icio2025_readme_small.xlsx", referer=ICIO_LANDING)
        ctx.fetch(ICIO_SRC, ICIO_ZIP, name="icio2025_2016_2022_sml.zip", referer=ICIO_LANDING, expect="zip")
    except AccessBlocked as e:
        ctx.warn(f"OECD ICIO zip blocked, not retried (D1-1b); P6a uses the ADB table: {e}")
    except OfflineMissing as e:
        ctx.log(f"OECD ICIO zip was never pinned (blocked on the last online run); skipped offline: {e}")
