"""Sheet-reading helpers for the NAS statements (MoSPI XLSX, bilingual, merged headers).

A statement is read as a grid: value columns (each with a period, price basis and, for
two-level headers, a column variable) crossed with labelled rows. Rows are matched against a
frozen row spec (spec_*.json in this package): the exact sequence of English labels and whether
each row carries numbers. Any difference (a relabelled, added, dropped or moved row) raises, so a
changed statement fails loudly instead of ingesting shifted numbers.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from openpyxl.utils import column_index_from_string, get_column_letter

from pipeline.core.units import clean_label, normalize_fy, parse_number, slug

SPEC_DIR = Path(__file__).parent

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
# A row whose label (or column-A text) starts like this ends the data block.
_END = re.compile(r"^(note\b|notes\b|\(i\)|[*#@$]|dep:)", re.I)


def cols(spec: str) -> list[str]:
    """'C:E' -> ['C', 'D', 'E']; 'C,F,I' -> ['C', 'F', 'I']."""
    out: list[str] = []
    for part in spec.split(","):
        if ":" in part:
            a, b = part.split(":")
            out += [get_column_letter(i) for i in range(column_index_from_string(a), column_index_from_string(b) + 1)]
        else:
            out.append(part)
    return out


def text(ws: Any, cell: str) -> str:
    v = ws[cell].value
    return "" if v is None else clean_label(str(v))


def english(s: str) -> str:
    """The English part of a bilingual header cell ('प्रचलित भावों पर At Current Prices' -> 'At Current Prices')."""
    return clean_label(_DEVANAGARI.sub(" ", s).replace("‍", " "))


def expect(ws: Any, cell: str, needle: str) -> None:
    got = text(ws, cell)
    if needle.lower() not in got.lower():
        raise ValueError(f"sheet {ws.title!r} {cell}: expected text containing {needle!r}, found {got!r}")


def year_header(ws: Any, row: int, year_cols: list[str]) -> dict[str, str]:
    return {c: normalize_fy(text(ws, f"{c}{row}")) for c in year_cols}


@dataclass
class Row:
    row: int
    label: str
    values: dict[str, float | None] = field(default_factory=dict)
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def has_data(self) -> bool:
        return any(v is not None for v in self.values.values())


def read_rows(
    ws: Any,
    *,
    label_col: str,
    first: int,
    value_cols: list[str],
    extra_cols: tuple[str, ...] = (),
    last: int | None = None,
    dash_as_zero: bool = False,
) -> list[Row]:
    """Labelled rows from `first` until the notes/footnotes (or `last`). Rows without an English
    label are skipped only if they also carry no numbers (a number without a label raises)."""
    rows: list[Row] = []
    blank_run = 0
    r = first
    end = last if last is not None else ws.max_row
    while r <= end:
        raw_label = ws[f"{label_col}{r}"].value
        label = english(str(raw_label)) if isinstance(raw_label, str) else ""
        a_text = ws[f"A{r}"].value
        a_text = english(a_text) if isinstance(a_text, str) else ""
        cells = {c: ws[f"{c}{r}"].value for c in value_cols}
        note_cell = any(isinstance(v, str) and (_END.match(english(v)) or len(v) > 40) for v in cells.values())
        if last is None and (_END.match(label) or (not label and (_END.match(a_text) or note_cell))):
            break
        vals = {c: parse_number(v, dash_as_zero=dash_as_zero) for c, v in cells.items()}
        if not label:
            if any(v is not None for v in vals.values()):
                raise ValueError(f"sheet {ws.title!r} row {r}: numbers without an English label in {label_col}")
            blank_run += 1
            if last is None and blank_run >= 6:
                break
            r += 1
            continue
        blank_run = 0
        extra = {c: text(ws, f"{c}{r}") for c in extra_cols}
        rows.append(Row(r, label, vals, extra))
        r += 1
    if not rows:
        raise ValueError(f"sheet {ws.title!r}: no labelled rows from row {first}")
    return rows


# ---------------------------------------------------------------------------------------------
# frozen row specs
# ---------------------------------------------------------------------------------------------


@cache
def load_spec(name: str) -> dict[str, list[list[str]]]:
    return json.loads((SPEC_DIR / name).read_text(encoding="utf-8"))


def serial(ws: Any, r: int, cols: tuple[str, ...]) -> str:
    """The row's serial number ('1.2.6.1'), preferring a text cell over a numeric one (Excel
    stores some serials as numbers, so '1.10' can read as 1.1)."""
    vals = [ws[f"{c}{r}"].value for c in cols]
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v.strip().rstrip(".")
    for v in vals:
        if isinstance(v, (int, float)):
            return (str(int(v)) if float(v).is_integer() else repr(float(v))).rstrip(".")
    return ""


def derive_codes(
    labels: list[str],
    has_data: list[bool],
    serials: list[str] | None = None,
    overrides: dict[str, str] | None = None,
) -> list[str]:
    """Deterministic row codes (used by make_spec; the build only compares with the frozen spec).

    Code = slug of the label (or overrides[slug]). A label that repeats within the statement is
    qualified by its context, whichever is nearer above it: the nearest header row whose label is
    unique, or the row whose serial number is this row's parent ('1.2' for '1.2.3').
    Anything still repeated gets '_2', '_3'. Header rows (no numbers) get ''.
    """
    overrides = overrides or {}
    serials = serials or [""] * len(labels)
    slugs = [overrides.get(sl, sl) for sl in map(_short_slug, labels)]
    counts: dict[str, int] = {}
    for s in slugs:
        counts[s] = counts.get(s, 0) + 1
    codes: list[str] = []
    for i, s in enumerate(slugs):
        code = s
        if counts[s] > 1:
            ctx, hdr, par = "", -1, -1
            for j in range(i - 1, -1, -1):
                if not has_data[j] and counts[slugs[j]] == 1:
                    hdr = j
                    break
            if "." in serials[i]:
                parent = serials[i].rsplit(".", 1)[0]
                par = next((j for j in range(i - 1, -1, -1) if serials[j] == parent), -1)
            if par > hdr:  # the nearer context wins
                ctx = codes[par] or slugs[par]
            elif hdr >= 0:
                ctx = slugs[hdr]
            code = f"{ctx}.{s}" if ctx else s
        codes.append(code)
    out: list[str] = []
    seen: dict[str, int] = {}
    for code, data in zip(codes, has_data, strict=True):
        if not data:
            out.append("")
            continue
        seen[code] = seen.get(code, 0) + 1
        out.append(code if seen[code] == 1 else f"{code}_{seen[code]}")
    return out


def _short_slug(label: str) -> str:
    label = re.sub(r"^\d+(\.\d+)*\.?\s+", "", label)  # numbering printed inside the label ('1.1 Agriculture')
    s = slug(label.replace("&", " and ").replace("%", " pct ").replace("*", " ").replace("#", " "))
    return s[:60].rstrip("_")
