"""HTML table helpers for www.rbi.org.in pages (RBI Annual Report chapters, RTP chapters, press releases).

The RBI site renders every report table as a plain <table> with colspan/rowspan headers. `grid()`
expands one table into a rectangular list of rows of cell texts, so headers can be read by column
position. Nothing here guesses: callers match rows by label and raise on anything unexpected.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from pipeline.core.units import clean_label


def soup(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_bytes(), "lxml")


def cell_text(c: Tag) -> str:
    # <sup> footnote markers become separate tokens ("Total Expenditure 1"), keep them spaced out
    return clean_label(unicodedata.normalize("NFKC", c.get_text(" ", strip=True)))


def grid(table: Tag) -> list[list[str]]:
    """Expand colspan/rowspan into a rectangular grid of cell texts (spanned cells repeat)."""
    rows = table.find_all("tr")
    pending: dict[tuple[int, int], str] = {}  # (row, col) -> text carried down by a rowspan
    out: list[list[str]] = []
    for r, tr in enumerate(rows):
        line: list[str] = []
        col = 0
        cells = tr.find_all(["td", "th"], recursive=False) or tr.find_all(["td", "th"])
        for c in cells:
            while (r, col) in pending:
                line.append(pending.pop((r, col)))
                col += 1
            txt = cell_text(c)
            cs = int(c.get("colspan") or 1)
            rs = int(c.get("rowspan") or 1)
            for k in range(cs):
                line.append(txt)
                for dr in range(1, rs):
                    pending[(r + dr, col + k)] = txt
            col += cs
        while (r, col) in pending:
            line.append(pending.pop((r, col)))
            col += 1
        out.append(line)
    width = max((len(x) for x in out), default=0)
    return [x + [""] * (width - len(x)) for x in out]


def find_table(doc: BeautifulSoup, title_re: str) -> tuple[str, list[list[str]]]:
    """The one table whose first row (the caption row) matches `title_re` (case-insensitive).

    Returns (caption text, grid). Raises if there is not exactly one match."""
    pat = re.compile(title_re, re.I)
    hits = []
    for t in doc.find_all("table"):
        g = grid(t)
        if g and pat.search(g[0][0]) and len(g[0][0]) < 300:
            hits.append((g[0][0], g))
    if len(hits) != 1:
        raise ValueError(f"expected exactly one table titled /{title_re}/, found {len(hits)}: {[h[0] for h in hits]}")
    return hits[0]


def page_heading(doc: BeautifulSoup) -> tuple[str, str]:
    """(release date text, heading) as printed at the top of a www.rbi.org.in content page."""
    for s in doc(["script", "style"]):
        s.decompose()
    lines = [clean_label(x) for x in doc.get_text("\n").split("\n") if x.strip()]
    for i, line in enumerate(lines):
        if line.startswith("Date :"):
            return line[len("Date :") :].strip(), lines[i + 1]
    raise ValueError("no 'Date :' line on the page")


_ENUM = re.compile(r"^(?:\(?(?:[a-zA-Z]|[ivxIVX]{1,4})[\.\):]|\d+(?:\.\d+)*\.?)\s+")
_TRAIL_FORMULA = re.compile(
    r"\s*[\(\[](?:[a-z0-9]{1,4}\s*[+\-]\s*)+[a-z0-9]{1,4}[\)\]]\s*$|\s*[\(\[][a-z]+ to [a-z]+[\)\]]\s*$", re.I
)


def norm_label(label: str) -> str:
    """Comparable form of a row label: no enumerator ('A.', 'ii)', '(iii)', '3.1'), no 'of which'
    prefix, no trailing formula ('(i+ii)', '(Ai-Bi)', '(i to iii)'), no footnote marks; lower case."""
    s = clean_label(label)
    s = re.sub(r"^of which\s*[:,]?\s*", "", s, flags=re.I)
    for _ in range(2):
        s = _ENUM.sub("", s)
    s = re.sub(r"^of which\s*[:,]?\s*", "", s, flags=re.I)
    s = re.sub(r"[\*#@\^]+", "", s).strip()
    s = _TRAIL_FORMULA.sub("", s)
    s = s.replace("’", "'").replace("–", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def is_growth_cell(text: str) -> bool:
    """'(24.8)' style cells: per cent variation printed under a level row."""
    return bool(re.fullmatch(r"\(\s*-?[\d.,]+\s*\)", text.strip()))


@dataclass(frozen=True)
class Header:
    """The header texts above one data column, outermost first (spans repeated)."""

    parts: tuple[str, ...]

    @property
    def text(self) -> str:
        out: list[str] = []
        for p in self.parts:  # spans repeat a cell down/right: keep each text once
            if p and (not out or out[-1] != p):
                out.append(p)
        return " | ".join(out)


def split_table(
    g: list[list[str]], *, label_cols: int, header_from: int, number_row_first: str = "1"
) -> tuple[list[Header], list[list[str]], int]:
    """Split a grid into (column headers of the data columns, data rows, index of first data row).

    Header rows run from `header_from` to the row whose first cell is the column-number row
    ('1 | 2 | 3 ...'), which every RBI report table has; data rows follow it."""
    num_row = next((i for i in range(header_from, len(g)) if g[i][0].strip() == number_row_first), None)
    if num_row is None:
        raise ValueError("no column-number row ('1 | 2 | ...') found")
    width = len(g[0])
    headers = [Header(tuple(g[r][c] for r in range(header_from, num_row))) for c in range(label_cols, width)]
    return headers, g[num_row + 1 :], num_row + 1


def is_note_row(row: list[str]) -> bool:
    """A notes/source footer: one merged cell repeated across the row."""
    first = row[0]
    return len(set(row)) == 1 and len(first) > 20
