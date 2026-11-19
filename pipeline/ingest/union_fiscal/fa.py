"""Parsers for the Union Finance Accounts 2023-24 (CGA) statement PDFs.

The statements are bilingual: a Hindi column (legacy Kruti Dev font, garbled as ASCII) on the
left, the English head of account in the middle and the amounts right-aligned on the right. We
never read the Hindi column: words are split by their x-position, and each amount is taken from
the column its right edge falls in. Every page must carry the unit caption "(In thousands of
rupees)"; amounts are converted Rs thousand -> Rs crore (x 1e-4) by the caller.

Checks while parsing (a statement that changes shape fails loudly):
- every minor head of a sub-major head sums to the printed "(nn) TOTAL (nn)" line;
- every minor head (and sub-major total) of a major head sums to the printed "TOTAL" line;
- any line with an amount that is not a head of account, a TOTAL line or the tail of a wrapped
  label raises.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pdfplumber

from pipeline.core.units import clean_label

# An amount as printed: Indian digit grouping in Rs thousand, '—' (em dash) prefix = minus,
# footnote marks '#', '*', '@', '$' possibly before it. A bare dash means nil.
_AMOUNT = re.compile(r"^[#*@$^†‡]*(?P<neg>[—–\-]+)?\s*(?P<num>\d[\d,]*)[#*@$^†‡x]*$")  # trailing 'x': a stray mark in St 9 p89
_GROUPING = re.compile(r"^(?:\d{1,3}|\d{1,2}(?:,\d{2})+)$")
# nil markers; '–—' (en dash + em dash) is printed for MH 0032 minor head 901 (St 8 printed p105)
_DASHES = {"—", "–", "-", "--", "——", "–—", "—–"}
_MH = re.compile(r"^(?P<code>\d{4})\s*[–—\-'.]*\s*(?P<label>.*)$")
_SMH = re.compile(r"^(?P<code>\d{2})\s*[–—\-]*\s*(?P<label>\D.*)$")
_MINOR = re.compile(r"^(?P<code>\d{3})\s*[–—\-]?\s*(?P<label>.*)$")
_SM_TOTAL = re.compile(r"^(?:\(\s*(?P<a>\d{2})\s*\)\s*)?TOTAL\s*\(\s*(?P<code>\d{2})\s*\)\s*$")
_MH_TOTAL = re.compile(r"^(?:[+]\s*)?TOTAL\s*$")
_SECTION_TOTAL = re.compile(r"^(?:GRAND\s+)?TOTAL\s*[–—\-]?\s*(?P<label>\S.*)$")


def parse_amount(tok: str) -> float | None:
    """Rs thousand as printed -> float (thousand). '—' alone -> 0.0 (nil). Raises if not an amount."""
    t = tok.strip()
    if t in _DASHES:
        return 0.0
    m = _AMOUNT.match(t)
    if not m or not _GROUPING.match(m.group("num")):
        # _GROUPING: the statements print Rs thousand as 'crore,lakh,thousand' pairs, e.g.
        # 6,38,27,41,20: first group of 1-2 digits, then 2-digit groups (or a bare 1-3 digit number).
        # Anything else is two amounts glued together or a misread and must not be taken as one.
        raise ValueError(f"not an amount: {tok!r}")
    v = float(m.group("num").replace(",", ""))
    return -v if m.group("neg") else v


def split_glued(tok: str) -> tuple[float, float] | None:
    """'15,41,63,23,6015,42,56,27,64' (two amounts with no space) -> (15416323 60, 1542562764).
    Every group after the first has exactly two digits in these statements (Rs thousand), so a
    group of 3-4 digits marks the join. Returns None if the token is not two glued amounts."""
    parts = re.split(r"(?<=\d)(?=[#*@$^]*[—–\-])", tok)  # '—7,29,94,83,81—7,29,94,83,81'
    if len(parts) == 2 and all(is_amount(p) for p in parts):
        return parse_amount(parts[0]), parse_amount(parts[1])
    m = re.match(r"^([#*@$^]*[—–\-]*)((?:\d{1,2})(?:,\d{2})*),?(\d{2})(\d{1,2}(?:,\d{2})+)$", tok)
    if not m:
        return None
    left = m.group(1) + m.group(2) + "," + m.group(3) if "," in m.group(2) or m.group(2) else ""
    right = m.group(4)
    try:
        return parse_amount(left), parse_amount(right)
    except ValueError:
        return None


def is_amount(tok: str) -> bool:
    try:
        parse_amount(tok)
        return True
    except ValueError:
        return False


_SIGN_ONLY = re.compile(r"^[#*@$^†‡]*[—–\-]+$")
_DIGITS = re.compile(r"^\d[\d,]*[#*@$^†‡]*$")


def _merge_split_signs(row: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """'*—' '4,83,81' printed as two words (sign detached from the digits) -> one amount word."""
    out: list[dict[str, Any]] = []
    for w in row:
        if (
            out
            and _SIGN_ONLY.match(out[-1]["text"])
            and _DIGITS.match(w["text"])
            and 0 <= w["x0"] - out[-1]["x1"] < 8
        ):
            prev = out.pop()
            w = {**w, "text": prev["text"] + w["text"], "x0": prev["x0"]}
        out.append(w)
    return out


@dataclass
class Line:
    page: int  # 1-based page of the PDF file
    printed_page: str
    text: str  # English column text (amount tokens removed)
    amounts: list[float]  # amounts in the value column, left to right
    other_amounts: list[float] = field(default_factory=list)  # amounts in other columns (ignored)


def read_lines(
    path: Path,
    *,
    eng_min: float,
    eng_max: float,
    amount_min_x1: float,
    ignore_amount_x1: tuple[float, float] | None = None,
    unit_caption: str = "thousands of rupees",
    body_start: str = "thousands of rupees",
) -> list[Line]:
    """Group the words of every page into lines (by vertical position) keeping only the English
    column (x0 in [eng_min, eng_max)) and the amounts whose right edge is >= amount_min_x1.
    Amount tokens whose right edge falls in `ignore_amount_x1` (e.g. a 'voted' column) are kept
    aside. Everything above the unit caption on each page (the running header) is skipped."""
    out: list[Line] = []
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
            full = " ".join(w["text"] for w in words)
            if unit_caption.lower() not in full.lower():
                raise ValueError(f"{path.name} page {pno}: unit caption {unit_caption!r} not found")
            printed = next((w["text"] for w in words if re.fullmatch(r"\d{1,3}", w["text"]) and w["top"] < 60), "")
            # body starts below the caption line
            cap_top = max(
                w["top"]
                for i, w in enumerate(words)
                if w["text"].lower().startswith(body_start.split()[0][:8])
                and body_start.split()[-1].rstrip(")").lower()
                in " ".join(x["text"] for x in words[i : i + 4]).lower()
            )
            body = [w for w in words if w["top"] > cap_top + 3]
            rows: list[list[dict[str, Any]]] = []
            for w in sorted(body, key=lambda w: (round(w["top"]), w["x0"])):
                if rows and abs(rows[-1][0]["top"] - w["top"]) <= 3.0:
                    rows[-1].append(w)
                else:
                    rows.append([w])
            for r in rows:
                r.sort(key=lambda w: w["x0"])
                r = _merge_split_signs(r)
                eng, amts, other = [], [], []
                for w in r:
                    t = w["text"]
                    if w["x1"] >= amount_min_x1 and is_amount(t):
                        amts.append(parse_amount(t))
                    elif w["x1"] >= amount_min_x1 and (glued := split_glued(t)) is not None:
                        other.append(glued[0])  # two columns printed without a space
                        amts.append(glued[1])
                    elif w["x1"] >= amount_min_x1 and re.search(r"\d,\d", t):
                        raise ValueError(f"{path.name} page {pno}: unreadable amount {t!r} in the value column")
                    elif ignore_amount_x1 and ignore_amount_x1[0] <= w["x1"] <= ignore_amount_x1[1] and is_amount(t):
                        other.append(parse_amount(t))
                    elif eng_min <= w["x0"] < eng_max:
                        eng.append(t)
                    elif w["x0"] < eng_min < w["x1"] and (mcode := re.search(r"(?<!\d)(\d{2,4})[.\-–]?$", t)):
                        eng.append(mcode.group(1))  # a head code glued to the Hindi text ('...]207')
                text = clean_label(" ".join(eng)) if eng else ""
                if text or amts:
                    out.append(Line(pno, printed, text, amts, other))
    return out


@dataclass
class Head:
    kind: str  # 'minor' | 'sm_total' | 'mh_total' | 'section_total'
    major: str
    sub_major: str  # '00' when the major head has no sub-major heads
    minor: str  # '' for totals
    major_label: str
    sub_major_label: str
    label: str
    value: float  # Rs thousand
    page: int
    printed_page: str


_OCR_01 = re.compile(r"^[0O][lI](?=\s)")
_OCR_L = re.compile(r"^[lI](?=\d{2}(?:\s|$))")  # 'l08 Contributions ...' (letter l for digit 1) in St 9
_INTRUDED_CODE = re.compile(r"(?<![\d,.])(\d{3,4})\s*[–—\-]?\s*[A-Z]")
_DANGLING = re.compile(r"(\b(for|of|and|to|in|the|on|from|under|with|by)|[&,\-–—/])\s*$", re.I)
_SPLIT_TOTAL = re.compile(r"^T ?O ?T ?A ?L\b", re.I)
_CONTD = re.compile(r"\s*[-–—]*\s*(contd|concld)\.?\s*$", re.I)


def _strip_contd(s: str) -> str:
    return clean_label(_CONTD.sub("", s).rstrip("-–— "))


class HeadParser:
    """State machine over Lines for Statements 8 and 9 (one value column)."""

    def __init__(
        self,
        name: str,
        *,
        tol: float = 1.0,
        fixups: dict[tuple[int, str], str | None] | None = None,
        stray_pages: tuple[int, ...] = (),
    ) -> None:
        self.name = name
        self.stray_pages = stray_pages  # pages known to carry stray single-digit glyphs at the foot
        self.dropped: list[Line] = []
        self.fixups = dict(fixups or {})  # {(pdf page, English text as extracted): corrected text}
        self.fixups_used: set[tuple[int, str]] = set()
        self.tol = tol
        self.heads: list[Head] = []
        self.mh = ""
        self.mh_label = ""
        self.sm = "00"
        self.sm_label = ""
        self.pending: dict[str, Any] | None = None
        self.pending_total: tuple[str, Line] | None = None  # a minor head whose amount is on a later line
        self.problems: list[str] = []

    # -- helpers ---------------------------------------------------------------------------
    def _emit(self, kind: str, minor: str, label: str, value: float, line: Line) -> None:
        self.heads.append(
            Head(kind, self.mh, self.sm, minor, self.mh_label, self.sm_label, clean_label(label), value, line.page,
                 line.printed_page)
        )

    def _check(self, parts: list[Head], total: float, what: str, line: Line) -> None:
        s = sum(h.value for h in parts)
        if abs(s - total) > self.tol:
            self.problems.append(
                f"{self.name} p{line.page} ({line.printed_page}): {what}: parts sum {s:,.0f} != printed {total:,.0f}"
            )

    def _close(self, kind: str, amt: float, line: Line) -> None:
        if kind == "sm_total":
            parts = [h for h in self.heads if h.kind == "minor" and h.major == self.mh and h.sub_major == self.sm]
            self._check(parts, amt, f"MH {self.mh} sub-major {self.sm}", line)
            self._emit("sm_total", "", f"Total {self.sm_label}", amt, line)
        else:
            self.sm, self.sm_label = "00", ""
            parts = [h for h in self.heads if h.kind == "minor" and h.major == self.mh]
            self._check(parts, amt, f"MH {self.mh} total", line)
            self._emit("mh_total", "", f"Total {self.mh_label}", amt, line)

    # -- main ------------------------------------------------------------------------------
    def feed(self, line: Line) -> None:
        if (line.page, line.text) in self.fixups:
            self.fixups_used.add((line.page, line.text))
            if self.fixups[(line.page, line.text)] is None:
                return  # stray glyphs (e.g. '0 0 3' at the foot of a page), not a line of the statement
            line = Line(line.page, line.printed_page, self.fixups[(line.page, line.text)], line.amounts,
                        line.other_amounts)
        t = _OCR_L.sub("1", _OCR_01.sub("01", line.text))  # '0l Shareable Duties' (letter l for digit 1)
        t = _SPLIT_TOTAL.sub("TOTAL", t)  # 'TOTA L (05)'
        mi = _INTRUDED_CODE.search(t)
        if mi and not t[:1].isdigit() and not t.startswith(("TOTAL", "(")):
            t = t[mi.start(1) :]  # Hindi words that spill into the English column before the code
        amts = line.amounts
        if len(amts) > 1:
            raise ValueError(f"{self.name} p{line.page}: more than one value on a line: {line}")
        amt = amts[0] if amts else None
        if self.pending_total is not None:
            # a TOTAL whose amount is printed a little lower than its label (St 9): the next line
            # must be that amount alone
            kind, tline = self.pending_total
            self.pending_total = None
            if t or amt is None:
                raise ValueError(f"{self.name} p{tline.page}: TOTAL without amount: {tline} (next: {line})")
            self._close(kind, amt, tline)
            return
        msm_t = _SM_TOTAL.match(t)
        if msm_t:
            self.pending = None
            code = msm_t.group("code")
            if code != self.sm:
                raise ValueError(f"{self.name} p{line.page}: TOTAL ({code}) inside sub-major {self.sm}: {line}")
            if amt is None:
                self.pending_total = ("sm_total", line)
            else:
                self._close("sm_total", amt, line)
            return
        if _MH_TOTAL.match(t):
            self.pending = None
            if amt is None:
                self.pending_total = ("mh_total", line)
            else:
                self._close("mh_total", amt, line)
            return
        ms = _SECTION_TOTAL.match(t)
        if ms:
            self.pending = None
            if amt is None:  # the label wraps; the amount is on a later line
                self.pending = {"kind": "section_total", "minor": "", "label": ms.group("label"), "line": line}
            else:
                self._emit("section_total", "", ms.group("label"), amt, line)
            return
        mmh = _MH.match(t)
        if mmh:
            self.pending = None
            code, label = mmh.group("code"), _strip_contd(mmh.group("label"))
            if code != self.mh:
                self.mh, self.mh_label, self.sm, self.sm_label = code, label, "00", ""
            elif label and not self.mh_label:
                self.mh_label = label
            # Capital account of St 9 is by major head: the major head carries its own amount,
            # possibly on the last line of a wrapped label.
            if amt is not None:
                self._emit("major", "", label, amt, line)
            else:
                self.pending = {"kind": "major", "minor": "", "label": label, "line": line}
            return
        mm = _MINOR.match(t)
        if mm and not _MH.match(t):
            self.pending = None
            if amt is None:
                self.pending = {"kind": "minor", "minor": mm.group("code"), "label": mm.group("label"), "line": line}
            else:
                self._emit("minor", mm.group("code"), mm.group("label"), amt, line)
            return
        msm = _SMH.match(t)
        if msm:
            self.pending = None
            code, label = msm.group("code"), _strip_contd(msm.group("label"))
            if code != self.sm:
                open_minors = [h for h in self.heads if h.major == self.mh and h.sub_major == self.sm]
                closed = any(h.kind == "sm_total" for h in open_minors) or all(
                    h.minor == "000" for h in open_minors  # sub-major heads carrying their own amount
                )
                if open_minors and not closed:
                    # A new sub-major head while the previous block has minor heads and no printed
                    # total. Without an amount it is a footnote line that starts with a number
                    # (listed in `dropped`); with an amount it is almost surely a garbled minor head
                    # ('11 4Wireless' for '114 Wireless') and needs a fix-up.
                    if amt is None:
                        self.dropped.append(line)
                        return
                    raise ValueError(
                        f"{self.name} p{line.page}: sub-major {code!r} starts before MH {self.mh} block "
                        f"{self.sm} was closed by a TOTAL line: {line}"
                    )
                self.sm, self.sm_label = code, label
            # A sub-major head printed with its own amount and no minor heads (Railways MH 1002/1003
            # in St 8, 3002/3003 in St 9) is kept as minor head '000' so that it enters the
            # sub-major and major closures. Its amount may sit on the last line of a wrapped label.
            if amt is not None:
                self._emit("minor", "000", label, amt, line)
            else:
                self.pending = {"kind": "minor", "minor": "000", "label": label, "line": line}
            return
        if self.pending is not None:
            self.pending["label"] += " " + t
            if amt is None and self.pending["kind"] == "major":
                self.mh_label = _strip_contd(self.pending["label"])  # wrapped major-head title
            elif amt is None and self.pending["minor"] == "000":
                self.sm_label = _strip_contd(self.pending["label"])  # wrapped sub-major title
            if amt is not None:
                self._emit(self.pending["kind"], self.pending["minor"], self.pending["label"], amt, line)
                self.pending = None
            return
        if amt is None and t and self.heads and self.heads[-1].kind == "minor" and _DANGLING.search(self.heads[-1].label):
            # the rest of a label printed below its amount ('Externally Aided Projects-Grants for' /
            # 'Scheduled Castes'): label text only, the amount is already taken
            self.heads[-1].label = clean_label(self.heads[-1].label + " " + t)
            return
        if amt is not None and not t and abs(amt) < 10 and line.page in self.stray_pages:
            self.dropped.append(line)  # stray glyphs at the foot of a page (listed, reported by the unit)
            return
        if amt is not None:
            raise ValueError(f"{self.name} p{line.page} ({line.printed_page}): unexpected amount line: {line}")
        # anything else: a section heading, a footnote or a wrapped heading -> ignored

    def run(self, lines: list[Line]) -> list[Head]:
        for ln in lines:
            self.feed(ln)
        unused = set(self.fixups) - self.fixups_used
        if unused:
            raise ValueError(f"{self.name}: text fix-ups not applied (the PDF changed?): {sorted(unused)}")
        if self.problems:
            raise ValueError(f"{self.name}: {len(self.problems)} closure failures:\n" + "\n".join(self.problems[:40]))
        return self.heads
