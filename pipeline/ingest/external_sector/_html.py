"""HTML table reading for RBI pages (www.rbi.org.in PublicationsView / Bulletin / press releases).

RBI serves every Handbook (HBS) table, Bulletin table and press-release table as plain HTML. A
table that runs over several printed pages is split into several <table> elements ("parts"), each
repeating its header block. `leaf_tables()` returns every innermost table as a grid with colspan
and rowspan expanded, so a header cell spanning three columns is repeated in each of them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

from pipeline.core.units import clean_label


@dataclass
class Grid:
    index: int  # position among the page's innermost tables (0-based)
    rows: list[list[str]]

    @property
    def title(self) -> str:
        return self.rows[0][0] if self.rows and self.rows[0] else ""

    def text(self) -> str:
        return " ".join(" ".join(r) for r in self.rows)


def _cell_text(cell) -> str:
    return clean_label(" ".join(cell.get_text(" ").split()))


def leaf_tables(path: Path) -> list[Grid]:
    """Every innermost <table> of the page as a colspan/rowspan-expanded grid of cleaned strings."""
    soup = BeautifulSoup(path.read_bytes(), "lxml")
    out: list[Grid] = []
    for t in soup.find_all("table"):
        if t.find("table") is not None:
            continue
        grid: list[list[str]] = []
        pending: dict[tuple[int, int], str] = {}  # (row, col) -> text carried down by rowspan
        for r, tr in enumerate(t.find_all("tr")):
            row: list[str] = []
            c = 0
            for cell in tr.find_all(["td", "th"]):
                while (r, c) in pending:
                    row.append(pending.pop((r, c)))
                    c += 1
                text = _cell_text(cell)
                cs = int(cell.get("colspan") or 1)
                rs = int(cell.get("rowspan") or 1)
                for k in range(cs):
                    row.append(text)
                    for dr in range(1, rs):
                        pending[(r + dr, c + k)] = text
                c += cs
            while (r, c) in pending:
                row.append(pending.pop((r, c)))
                c += 1
            grid.append(row)
        out.append(Grid(len(out), grid))
    return out


def page_date(path: Path) -> str:
    """The 'Date : Mon DD, YYYY' stamp RBI prints above a publication, as YYYY-MM-DD."""
    text = " ".join(BeautifulSoup(path.read_bytes(), "lxml").get_text(" ").split())
    m = re.search(r"Date\s*:\s*([A-Z][a-z]{2})\w*\s+(\d{1,2}),\s+(\d{4})", text)
    if not m:
        raise ValueError(f"{path.name}: no 'Date : Mon DD, YYYY' stamp on the page")
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    return f"{m.group(3)}-{months.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}"


def page_text(path: Path) -> str:
    return clean_label(" ".join(BeautifulSoup(path.read_bytes(), "lxml").get_text(" ").split()))


def find_grid(grids: list[Grid], needle: str) -> Grid:
    """The one grid whose first rows mention `needle` (case-insensitive)."""
    hits = [g for g in grids if needle.lower() in " ".join(" ".join(r) for r in g.rows[:3]).lower()]
    if len(hits) != 1:
        raise ValueError(f"expected exactly one table headed {needle!r}, found {len(hits)}")
    return hits[0]


def is_colnum_row(row: list[str]) -> bool:
    """The printed column-number row ('1 | 2 | 3 ...')."""
    vals = [v for v in row if v != ""]
    return bool(vals) and all(re.fullmatch(r"\d+", v) for v in vals) and vals[0] == "1"
