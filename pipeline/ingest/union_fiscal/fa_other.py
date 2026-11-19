"""Parsers for two further Union Finance Accounts 2023-24 (CGA) documents.

- Statement No. 14 "Statement of debts and other interest bearing obligations of Government",
  section I "Small Savings, Provident Funds etc.": the blocks for major heads 8009 (State
  Provident Funds: GPF of civil, defence and railway employees), 8011 (Insurance and Pension
  Funds) and 8014 (Postal Life Insurance Schemes). Four amount columns: amount on 1 April 2023,
  additions during the year, discharges during the year, amount on 31 March 2024, in Rs thousand.
- Appendix to Statement No. 9 (IGAS-2) "Disclosure statement: accounting and classification of
  grants-in-aid": grants-in-aid released in 2023-24 by category of grantee, and the part of it
  allocated for the creation of capital assets (cash, and in kind), in Rs lakh.

Both are bilingual. The Hindi text (legacy Kruti Dev font, garbled) is never read: words are
split by x-position (Statement 14) or by the English label pattern (the Appendix).

Checks while parsing (a statement that changes shape fails loudly):
- Statement 14: every line satisfies opening + additions - discharges = closing; the minor heads
  of a sub-major head add up to its printed 'Total (nn)' line and the sub-major totals (or the
  minor heads, where there is no sub-major level) add up to the printed major-head TOTAL, in all
  four columns, to the thousand rupees.
- Appendix: both tables list exactly the ten printed grantee categories, with two amounts each.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pdfplumber

from pipeline.core.units import clean_label

from .fa import _merge_split_signs, is_amount, parse_amount

# ---------------------------------------------------------------------------------------------
# Statement 14
# ---------------------------------------------------------------------------------------------

ST14_COLUMNS = ("opening", "additions", "discharges", "closing")
_ST14_ENG = (240.0, 490.0)

# major head -> (printed first line, printed closing TOTAL line)
ST14_BLOCKS: dict[str, tuple[str, str]] = {
    "8009": ("8009— State Provident Funds", "TOTAL-STATE PROVIDENT FUNDS"),
    "8011": ("8011— Insurance and Pension Funds", "TOTAL—INSURANCE AND PENSION FUNDS"),
    "8014": ("8014—Postal Life Insurance Schemes", "Total—POSTAL LIFE INSURANCE SCHEMES"),
}


@dataclass
class St14Line:
    page: int
    printed_page: str
    text: str
    amounts: dict[int, float]  # column index (0-3) -> Rs thousand
    error: str | None = None  # an unreadable amount; fatal only inside a parsed block


@dataclass
class St14Row:
    kind: str  # 'minor' | 'sm_total' | 'mh_total'
    major: str
    sub_major: str  # '00' when the block has no sub-major level
    minor: str  # '' for totals
    label: str
    sub_major_label: str
    values: tuple[float, float, float, float]  # opening, additions, discharges, closing (Rs thousand)
    page: int
    printed_page: str


def _norm(s: str) -> str:
    return re.sub(r"[\s—–\-]+", "", s).upper()


def _column_edges(words: list[dict[str, Any]]) -> list[float]:
    """The right edges of the four amount columns on one page. Odd and even pages are offset
    (e.g. 545/610/680/759 vs 532/616/690/762), so they are found per page: the four most
    common right edges of amount-looking tokens right of the English column, merged within 4pt."""
    xs = sorted(w["x1"] for w in words if w["x0"] >= _ST14_ENG[1] - 20 and w["x0"] < 770 and is_amount(w["text"]))
    clusters: list[list[float]] = []
    for x in xs:
        if clusters and x - clusters[-1][-1] <= 4.0:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    top = sorted(sorted(clusters, key=len, reverse=True)[:4], key=lambda c: c[0])
    return [max(c) for c in top]


def st14_lines(path: Path) -> list[St14Line]:
    """Lines of every page. Pages with the caption '(In thousands of rupees)' carry the running
    header above it (skipped); continuation pages have no header."""
    out: list[St14Line] = []
    seen_title = False
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
            full = " ".join(w["text"] for w in words)
            if "thousands of rupees" in full.lower():
                if "No. 14" not in full or "STATEMENT OF DEBTS AND OTHER INTEREST BEARING OBLIGATIONS" not in full:
                    raise ValueError(f"{path.name} page {pno}: not a Statement 14 page")
                seen_title = True
                cap_top = min(w["top"] for w in words if w["text"] == "thousands")
                body = [w for w in words if w["top"] >= cap_top - 2]
            elif seen_title:
                body = words
            else:
                continue  # the cover page
            printed = next((w["text"] for w in words if re.fullmatch(r"\d{3}", w["text"]) and w["x0"] > 770), "")
            edges = _column_edges(body)
            rows: list[list[dict[str, Any]]] = []
            for w in sorted(body, key=lambda w: (round(w["top"]), w["x0"])):
                if rows and abs(rows[-1][0]["top"] - w["top"]) <= 3.0:
                    rows[-1].append(w)
                else:
                    rows.append([w])
            for r in rows:
                r.sort(key=lambda w: w["x0"])
                r = _merge_split_signs(r)
                eng: list[str] = []
                amts: dict[int, float] = {}
                err: str | None = None
                for w in r:
                    t = w["text"]
                    if w["x0"] > 770:
                        continue  # printed page number
                    if w["x0"] >= _ST14_ENG[1] - 20 and is_amount(t):
                        col = min(range(len(edges)), key=lambda k: abs(edges[k] - w["x1"])) if edges else None
                        if len(edges) != 4 or col is None or abs(edges[col] - w["x1"]) > 6.0:
                            err = f"amount {t!r} at x1={w['x1']:.0f} outside the columns {edges}"
                        elif col in amts:
                            err = f"two amounts in column {col}: {t!r}"
                        else:
                            amts[col] = parse_amount(t)
                    elif w["x0"] >= _ST14_ENG[1] and re.search(r"\d", t):
                        err = f"unreadable amount {t!r}"
                    elif _ST14_ENG[0] <= w["x0"] < _ST14_ENG[1]:
                        eng.append(t)
                text = clean_label(" ".join(eng)) if eng else ""
                if text or amts:
                    out.append(St14Line(pno, printed, text, amts, err))
    return out


_ST14_MINOR = re.compile(r"^(?P<code>\d{3})\s*[—–\-]\s*(?P<label>.+)$")
_ST14_SMH = re.compile(r"^(?P<code>\d{2})\s*[—–\-]\s*(?P<label>.+)$")
_ST14_SM_TOTAL = re.compile(r"^Total\s*\(\s*(?P<code>\d{2})\s*\)$")


def st14_rows(path: Path) -> list[St14Row]:
    """The minor heads, sub-major totals and major-head total of every block in ST14_BLOCKS."""
    lines = st14_lines(path)
    out: list[St14Row] = []
    for major, (first, last) in ST14_BLOCKS.items():
        start = [i for i, ln in enumerate(lines) if _norm(ln.text).startswith(_norm(first))]
        if len(start) != 1:
            raise ValueError(f"{path.name}: block {first!r} found {len(start)} times")
        sm, sm_label = "00", ""
        label: list[str] = []
        closed = False
        for ln in lines[start[0] + 1 :]:
            t = ln.text
            if ln.error:
                raise ValueError(f"{path.name} p{ln.page}: {ln.error} in block {major}")
            if not ln.amounts:
                if not t:
                    continue
                if re.match(r"^[IVX]+\.\s*[—–\-]", t):
                    continue  # the section line repeated at the top of a page ('I.— Small Savings, ...—contd.')
                m = _ST14_SMH.match(t)
                if m and re.search(r"(contd|concld)\.?$", t):
                    if m.group("code") != sm:  # '02— Rural Postal Life Insurance Schemes—concld.'
                        raise ValueError(
                            f"{path.name} p{ln.page}: {t!r} continues sub-major {m.group('code')}, not {sm}"
                        )
                    continue
                if m and not label:
                    sm, sm_label = m.group("code"), clean_label(m.group("label").rstrip("—– "))
                    continue
                label.append(t)  # a head whose label wraps (its amounts are on a later line)
                continue
            if len(ln.amounts) != 4:
                # e.g. a prior-period adjustment printed below a TOTAL: not handled, so fail loudly
                raise ValueError(f"{path.name} p{ln.page}: expected 4 amounts, got {ln.amounts} for {t!r}")
            vals = tuple(ln.amounts[k] for k in range(4))
            starts_head = bool(_ST14_MINOR.match(t) or _ST14_SM_TOTAL.match(t) or _norm(t) == _norm(last))
            if label and starts_head:
                # text lines printed after the previous head's amounts ('101— Net RPLI Corpus as on'
                # + amounts, then '31st October, 2009') are the tail of that head's label
                if not out or out[-1].major != major:
                    raise ValueError(f"{path.name} p{ln.page}: orphan text {label!r}")
                out[-1].label = clean_label(" ".join([out[-1].label, *label]))
                label = []
            text = clean_label(" ".join([*label, t]))
            label = []
            if _norm(text) == _norm(last):
                out.append(St14Row("mh_total", major, "", "", text, "", vals, ln.page, ln.printed_page))
                closed = True
                break
            if (m := _ST14_SM_TOTAL.match(text)) is not None:
                if m.group("code") != sm:
                    raise ValueError(f"{path.name} p{ln.page}: {text!r} closes sub-major {sm}")
                out.append(St14Row("sm_total", major, sm, "", text, sm_label, vals, ln.page, ln.printed_page))
                continue
            m = _ST14_MINOR.match(text)
            if not m:
                raise ValueError(f"{path.name} p{ln.page}: unexpected line {text!r} {vals}")
            out.append(
                St14Row("minor", major, sm, m.group("code"), clean_label(m.group("label")), sm_label, vals,
                        ln.page, ln.printed_page)
            )
        if not closed:
            raise ValueError(f"{path.name}: block {major} has no closing line {last!r}")
    _st14_check(out, path.name)
    return out


def _st14_check(rows: list[St14Row], name: str) -> None:
    def close(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
        return all(abs(x - y) < 0.5 for x, y in zip(a, b, strict=True))

    for r in rows:
        o, a, d, c = r.values
        if abs(o + a - d - c) >= 0.5:
            raise ValueError(f"{name}: {r.major} {r.sub_major} {r.minor} {r.label!r}: {o} + {a} - {d} != {c}")
    for major in {r.major for r in rows}:
        blk = [r for r in rows if r.major == major]
        tot = [r for r in blk if r.kind == "mh_total"]
        sms = [r for r in blk if r.kind == "sm_total"]
        minors = [r for r in blk if r.kind == "minor"]
        for s in sms:
            parts = [r.values for r in minors if r.sub_major == s.sub_major]
            if not close(tuple(sum(p[k] for p in parts) for k in range(4)), s.values):
                raise ValueError(f"{name}: {major}-{s.sub_major} minor heads do not add up to {s.label!r}")
        if sms and {r.sub_major for r in minors} != {s.sub_major for s in sms}:
            raise ValueError(f"{name}: {major}: sub-major heads without a Total line")
        parts = [s.values for s in sms] if sms else [r.values for r in minors]
        if len(tot) != 1 or not close(tuple(sum(p[k] for p in parts) for k in range(4)), tot[0].values):
            raise ValueError(f"{name}: {major}: parts do not add up to the major-head total")


# ---------------------------------------------------------------------------------------------
# Appendix to Statement 9 (IGAS-2): grants-in-aid by category of grantee
# ---------------------------------------------------------------------------------------------

GIA_CATEGORIES = {
    "State Government": "state_governments",
    "Union Territories Government": "ut_governments",
    "Urban Local Bodies": "urban_local_bodies",
    "Panchayati Raj Institutions": "panchayati_raj_institutions",
    "Public Sector Undertakings": "public_sector_undertakings",
    "Non-Governmental Organisations (NGOs)": "ngos",
    "Autonomous Bodies": "autonomous_bodies",
    "Co-operative Societies and Co-operative Institutions": "cooperatives",
    "Statutory Bodies and Development Authorities": "statutory_bodies_and_development_authorities",
    "Others": "others",
}
GIA_TABLES = {
    "cash": "Total Funds released during the Year 2023-24 as Grants-in-aid and Funds allocated for Creation of Assets",
    "in_kind": "Total value of grants-in-aid in kind released during the Year 2023-24",
}
_GIA_LINE = re.compile(r"^(?P<label>[A-Z][A-Za-z()\-,. ]+?)\s+(?P<a>\d[\d,]*\.\d{2})\s+(?P<b>\d[\d,]*\.\d{2})$")


@dataclass
class GiaRow:
    table: str  # 'cash' | 'in_kind'
    category: str  # code from GIA_CATEGORIES
    label: str
    total: float  # Rs lakh: total grants-in-aid released (cash) / total value in kind
    capital: float  # Rs lakh: of which for creation of capital assets / capital assets in nature
    page: int


def gia_rows(path: Path, *, year: str) -> list[GiaRow]:
    out: list[GiaRow] = []
    seen: set[str] = set()
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            flat = re.sub(r"\s+", " ", text)
            table = next((k for k, t in GIA_TABLES.items() if t.replace("2023-24", year) in flat), None)
            if table is None:
                continue
            if "(Rupees in lakhs)" not in flat:
                raise ValueError(f"{path.name} p{pno}: unit caption '(Rupees in lakhs)' not found")
            if table in seen:
                raise ValueError(f"{path.name} p{pno}: table {table!r} printed twice")
            seen.add(table)
            got: dict[str, GiaRow] = {}
            for ln in text.splitlines():
                m = _GIA_LINE.match(clean_label(ln))
                if not m:
                    continue
                lab = m.group("label")
                if lab not in GIA_CATEGORIES:
                    raise ValueError(f"{path.name} p{pno}: unknown grantee category {lab!r}")
                if lab in got:
                    raise ValueError(f"{path.name} p{pno}: {lab!r} printed twice")
                got[lab] = GiaRow(table, GIA_CATEGORIES[lab], lab, float(m.group("a").replace(",", "")),
                                  float(m.group("b").replace(",", "")), pno)
            if set(got) != set(GIA_CATEGORIES):
                raise ValueError(f"{path.name} p{pno}: categories {sorted(got)} != {sorted(GIA_CATEGORIES)}")
            out.extend(got[k] for k in GIA_CATEGORIES)
    if seen != set(GIA_TABLES):
        raise ValueError(f"{path.name}: tables found {sorted(seen)}, expected {sorted(GIA_TABLES)}")
    return out
