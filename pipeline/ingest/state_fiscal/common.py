"""Shared helpers for the state_fiscal unit: geography codes, sheet checks, and the parser for
RBI's numbered item tables (Appendices I-IV and similar), which builds each row's place in the
table's hierarchy from its printed numbering ('I.', 'A.', '1.', 'i)', '(a)', 'of which')."""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from pipeline.core import geo
from pipeline.core.units import clean_label, parse_number, period_end, period_start, slug

# ---------------------------------------------------------------------------------------------
# geography
# ---------------------------------------------------------------------------------------------

# State/UT codes come from the project code set, pipeline/core/geo.py (DECISIONS D1-9): printed names are
# resolved with geo.state_code(), which never guesses. The few printed variants geo does not list are
# mapped here to a name geo does know, so every code still comes from the shared map.
_NAME_VARIANTS: dict[str, str] = {
    "nct delhi": "Delhi",  # RBI State Finances and Municipal Finances print 'NCT Delhi'
}

# FC16 two-letter abbreviations (KFI block headers, ServiceHeads 'State Abb') -> the State's name, resolved
# through geo.state_code(). FC16 writes Chhattisgarh as 'CH' (ISO's IN-CH is Chandigarh), and OD, TS, UK.
_FC16_NAMES: dict[str, str] = {
    "AP": "Andhra Pradesh", "AR": "Arunachal Pradesh", "AS": "Assam", "BR": "Bihar", "CH": "Chhattisgarh",
    "GA": "Goa", "GJ": "Gujarat", "HP": "Himachal Pradesh", "HR": "Haryana", "JH": "Jharkhand",
    "KA": "Karnataka", "KL": "Kerala", "MH": "Maharashtra", "ML": "Meghalaya", "MN": "Manipur",
    "MP": "Madhya Pradesh", "MZ": "Mizoram", "NL": "Nagaland", "OD": "Odisha", "PB": "Punjab",
    "RJ": "Rajasthan", "SK": "Sikkim", "TN": "Tamil Nadu", "TR": "Tripura", "TS": "Telangana",
    "UK": "Uttarakhand", "UP": "Uttar Pradesh", "WB": "West Bengal", "JK": "Jammu and Kashmir",
    "DL": "Delhi", "PY": "Puducherry",
}  # fmt: skip
FC16_ABBR: dict[str, str] = {abbr: geo.state_code(name) for abbr, name in _FC16_NAMES.items()}

# Undivided Andhra Pradesh (FC16 block 'AP_un'): the project historical code IN-XAP (geo.HISTORICAL). The
# dim 'boundary=undivided' is kept as an explicit marker as well, so filters written before D1-9 was
# adopted (including the verifier's spot-check) still find these rows; the geography alone is sufficient.
UNDIVIDED_AP = ("IN-XAP", "boundary=undivided")


@dataclass(frozen=True)
class Geo:
    """A geography as clean-table dims: project State/UT code, plus dim_other for groups/undivided AP."""

    geography: str
    dim_other: str | None = None
    institution: str = "gg_state"

    @property
    def key(self) -> str:
        """Short lower-case id for series ids ('in-mh', 'in.all_states_uts', 'in-xap.undivided')."""
        k = self.geography.lower()
        if self.dim_other:
            k += "." + self.dim_other.split("=", 1)[1]
        return k


def state_geo(name: str) -> Geo:
    """Geo for a printed State/UT name ('1. Andhra Pradesh', 'NCT Delhi', 'WEST BENGAL ')."""
    n = re.sub(r"^\d+\.\s*", "", clean_label(name)).lower()
    n = n.replace("&", "and")
    if re.fullmatch(r"all states? (and|&) uts?\*?", n) or n in ("all states/uts*", "all states/uts"):
        return Geo("IN", "state_group=all_states_uts")
    try:
        return Geo(geo.state_code(_NAME_VARIANTS.get(n, n)))
    except KeyError as e:
        raise ValueError(f"unknown State/UT name {name!r}") from e


# ---------------------------------------------------------------------------------------------
# territory calendar (D1-9: a row's geography must mean one fixed territory)
# ---------------------------------------------------------------------------------------------


def _calendar() -> tuple[dict[str, dt.date], dict[str, dt.date], dict[str, str]]:
    """From geo.HISTORICAL: the first day each successor code exists, the last day each historical code
    exists, and the historical code of a continuing government (the successor that keeps the name)."""
    first: dict[str, dt.date] = {}
    last: dict[str, dt.date] = {}
    predecessor: dict[str, str] = {}
    for h, (_, end, repl) in geo.HISTORICAL.items():
        last[h] = dt.date.fromisoformat(end)
        # e.g. 'IN-AP + IN-TS from 2014-06-02', 'IN-JK + IN-LA (UTs) from 2019-10-31'
        m = re.fullmatch(r"((?:IN-[A-Z]{2})(?: \+ IN-[A-Z]{2})*)(?: \([^)]*\))? from (\d{4}-\d{2}-\d{2})", repl)
        if not m:
            raise ValueError(f"geo.HISTORICAL[{h!r}]: unexpected successor text {repl!r}")
        start = dt.date.fromisoformat(m.group(2))
        succ = re.findall(r"IN-[A-Z]{2}", m.group(1))
        if any(c not in geo.STATES_UTS for c in succ) or start != last[h] + dt.timedelta(days=1):
            raise ValueError(f"geo.HISTORICAL[{h!r}]: successors {succ} / start {start} inconsistent")
        for c in succ:
            first[c] = max(first.get(c, start), start)
        if f"IN-{h[4:]}" in succ:  # IN-XJK -> IN-JK: the government that continues under the same name
            predecessor[f"IN-{h[4:]}"] = h
    # Not Andhra Pradesh: FC16 files carry undivided AP as its own block ('AP_un' -> IN-XAP), so an 'AP'
    # row dated before June 2014 is a figure for the successor territory (KFI GSDP), never undivided AP.
    predecessor.pop("IN-AP", None)
    return first, last, predecessor


TERRITORY_FROM, TERRITORY_TO, PREDECESSOR = _calendar()


def geo_for_period(g: Geo, period: str, period_type: str) -> Geo:
    """Re-code a continuing government's row to its historical code when the whole period lies before
    the reorganisation (e.g. the State of Jammu and Kashmir's FY 2018-19 accounts are IN-XJK, not the UT
    IN-JK). Straddling periods keep the current code; `territory_problems` makes each unit declare them."""
    h = PREDECESSOR.get(g.geography)
    if h and period_end(period, period_type) < TERRITORY_FROM[g.geography]:
        return Geo(h, g.dim_other, g.institution)
    return g


def territory_class(geography: str, period: str, period_type: str) -> str | None:
    """None when the territory existed for the whole period; otherwise 'before' (the period ends before
    the code's territory existed), 'after' (a historical territory, period starts after it ceased), or
    'straddle' (the reorganisation falls inside the period)."""
    p0, p1 = period_start(period, period_type), period_end(period, period_type)
    if geography in TERRITORY_FROM:
        s = TERRITORY_FROM[geography]
        if p1 < s:
            return "before"
        if p0 < s:
            return "straddle"
    if geography in TERRITORY_TO:
        e = TERRITORY_TO[geography]
        if p0 > e:
            return "after"
        if p1 > e:
            return "straddle"
    return None


# A provenance record carrying rows outside their territory's existence must say why (verify-13): its notes
# cite DECISIONS D1-9 next to the territory sentence, or carry one of the GSDP record headings.
TERRITORY_NOTE_MARKERS = ("DECISIONS D1-9", "SUCCESSOR-TERRITORY FIGURE", "TERRITORIAL AGGREGATE, NOT ADDITIVE")


def territory_problems(
    df: Any, declared: dict[tuple[str, str, str], str], notes: dict[str, str | None] | None = None
) -> list[str]:
    """Rows whose period does not sit inside their territory's existence and are not declared.
    `declared` maps (geography, period, class) to the reason, which the provenance notes must state.
    With `notes` (prov_id -> provenance notes), each such row's record must also state the reason: its notes
    must contain one of TERRITORY_NOTE_MARKERS."""
    out = []
    seen = set()
    cols = ["geography", "period", "period_type"] + (["prov_id"] if notes is not None else [])
    for g, p, pt, *pid in df.select(cols).unique(maintain_order=True).iter_rows():
        c = territory_class(g, p, pt)
        if c is None:
            continue
        if (g, p, c) not in declared and (g, p, c) not in seen:
            out.append(f"{g} {p}: {c} its territory's existence ({geo.state_name(g)}), not declared")
        seen.add((g, p, c))
        if pid and not any(m in (notes.get(pid[0]) or "") for m in TERRITORY_NOTE_MARKERS):
            out.append(f"{g} {p}: {c} its territory's existence, but record {pid[0]} does not state why")
    out += [f"declared {k} not found in the data" for k in declared if k not in seen]
    return out


# ---------------------------------------------------------------------------------------------
# sheet helpers
# ---------------------------------------------------------------------------------------------


def norm(text: Any) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip().lower()


def expect(ws: Any, cell: str, needle: str) -> None:
    got = norm(ws[cell].value)
    if norm(needle) not in got:
        raise ValueError(f"sheet {ws.title!r} {cell}: expected text containing {needle!r}, found {got!r}")


def rbi_period(text: Any) -> tuple[str, str]:
    """('2023-24', 'Actuals') from RBI column headers such as '2023-24 (Accounts)',
    '2024-25 (Revised Estimates)', '2025-26(BE)', '2021-2022 (Accounts)', '2024-25 (BE)$'."""
    t = norm(text).replace("$", "").strip()
    m = re.fullmatch(r"(\d{4})\s*[-–]\s*(\d{2}|\d{4})\s*(\((.*)\))?", t)
    if not m:
        raise ValueError(f"unrecognised RBI period header {text!r}")
    y0 = int(m.group(1))
    y1 = m.group(2)
    if len(y1) == 4:
        if int(y1) != y0 + 1:
            raise ValueError(f"bad fiscal year header {text!r}")
    elif int(y1) != (y0 + 1) % 100:
        raise ValueError(f"bad fiscal year header {text!r}")
    tag = (m.group(4) or "").strip()
    stage = {
        "": "Actuals",
        "accounts": "Actuals",
        "revised estimates": "RE",
        "re": "RE",
        "budget estimates": "BE",
        "be": "BE",
    }.get(tag)
    if stage is None:
        raise ValueError(f"unrecognised estimate tag in {text!r}")
    return f"{y0}-{(y0 + 1) % 100:02d}", stage


# ---------------------------------------------------------------------------------------------
# RBI numbered item tables
# ---------------------------------------------------------------------------------------------

# (kind, regex). The number token is group 1. Order matters.
_TOKENS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("roman_paren", re.compile(r"^\(([ivx]+)\)\s*")),
    ("alpha_paren", re.compile(r"^\(([a-h])\)\s*")),
    ("roman_up", re.compile(r"^l?([IVX]+)\.\s*")),  # 'lIV.' is a typo in one sheet
    ("alpha_up", re.compile(r"^([A-H])\.\s*")),
    ("digit", re.compile(r"^(\d+)[.\s]\s*")),  # PRI prints '1 Interest Receipts'
    ("roman_low", re.compile(r"^([ivx]+)[.)]\s*")),
    ("alpha_low", re.compile(r"^([a-h])\)\s*")),
)
_FAMILY = {
    "roman_paren": "roman_low",
    "alpha_paren": "alpha_low",
    "roman_low": "roman_low",
    "alpha_low": "alpha_low",
    "roman_up": "roman_up",
    "alpha_up": "alpha_up",
    "digit": "digit",
}
# '(A+B)', '(1 to 3)', '(i to viii)', '(a + b)', '(C = i to iii)', '(1 - 8)', '(I to XII)'
_FORMULA = re.compile(r"\(\s*(?:[A-Z]\s*=\s*)?([A-Za-z0-9]+)\s*(?:\+|to|-)\s*([A-Za-z0-9]+)(?:\s*\+\s*[A-Za-z0-9]+)*\s*\)")
_OF_WHICH = re.compile(r"^of\s*which\s*:?\s*", re.I)


def _kind_of_token(tok: str) -> str | None:
    if re.fullmatch(r"\d+", tok):
        return "digit"
    if re.fullmatch(r"[IVX]+", tok):
        return "roman_up"
    if re.fullmatch(r"[A-H]", tok):
        return "alpha_up"
    if re.fullmatch(r"[ivx]+", tok):
        return "roman_low"
    if re.fullmatch(r"[a-h]", tok):
        return "alpha_low"
    return None


@dataclass
class Node:
    kind: str | None  # token kind, None for unnumbered rows
    token: str
    path: str
    child_family: str | None = None
    expects_children: bool = False
    formula: tuple[str, str] | None = None
    child_first: str | None = None  # the first token the formula names (children start with it)
    n_children: int = 0


@dataclass
class ItemRow:
    """One line item of a numbered RBI table."""

    row: int
    label: str  # as published (continuations joined)
    code: str  # '<dotted path>-<slug>', unique within the table
    path: str  # dotted numbering path, e.g. 'i.a.3.vii'
    parent: str | None  # parent's path
    formula: tuple[str, str] | None  # the '(x to y)' the row prints, if any
    cells: dict[str, Any] = field(default_factory=dict)  # column letter -> raw cell value


def _strip_number(label: str) -> tuple[str | None, str | None, str]:
    for kind, rx in _TOKENS:
        m = rx.match(label)
        if m:
            tok = m.group(1)
            if kind == "roman_up" and label.startswith("l"):
                tok = tok  # 'lIV.' -> 'IV'
            return kind, tok, label[m.end() :]
    return None, None, label


def _slug(text: str, n: int = 48) -> str:
    t = _FORMULA.sub("", text)
    t = re.sub(r"[*#@$+]+", " ", t)
    s = slug(t) or "item"
    return s[:n].rstrip("_")


def parse_item_rows(
    rows: list[tuple[int, str, dict[str, Any]]], *, continuations: set[str], where: str
) -> list[ItemRow]:
    """rows: (sheet row, label text, {column: cell}) in sheet order, label non-empty.

    Builds the numbering path of each row. A row whose (normalised) label is in `continuations`
    is the second line of the previous label. Raises on an unplaceable or duplicate path."""
    # 1. join continuation lines
    merged: list[tuple[int, str, dict[str, Any]]] = []
    for r, label, cells in rows:
        lab = clean_label(label)
        if norm(lab) in continuations:
            if not merged:
                raise ValueError(f"{where}: continuation line {lab!r} at row {r} has no previous line")
            pr, plab, pcells = merged[-1]
            joined = dict(pcells)
            for col, v in cells.items():
                if parse_number(v) is not None:
                    if parse_number(pcells.get(col)) is not None:
                        raise ValueError(f"{where}: both lines of {plab!r} (rows {pr}-{r}) have a number in {col}")
                    joined[col] = v
                elif col not in joined or joined[col] is None:
                    joined[col] = v
            merged[-1] = (pr, clean_label(f"{plab} {lab}"), joined)
            continue
        merged.append((r, lab, cells))

    out: list[ItemRow] = []
    stack: list[Node] = []
    seen: set[str] = set()
    last_unnumbered_parent: str | None = None
    for r, lab, cells in merged:
        text = lab
        if _OF_WHICH.match(text):
            rest = _OF_WHICH.sub("", text)
            if not stack:
                raise ValueError(f"{where}: 'of which' at row {r} with no parent")
            if not rest:  # a bare 'of which:' marker: what follows are children of the top
                stack[-1].expects_children = True
                continue
            parent = stack[-1]
            tok = "of_" + _slug(rest, 30)
            node = Node(None, tok, f"{parent.path}.{tok}")
            item = _emit(out, seen, r, lab, node, parent.path, cells, where)
            last_unnumbered_parent = parent.path
            continue
        kind, tok, rest = _strip_number(text)
        fm = _FORMULA.search(rest)
        formula = (fm.group(1), fm.group(2)) if fm else None
        if kind is None:
            if norm(text).startswith("total") or (formula and not stack) or not out:
                # a table total: the root of the tree if it prints a formula, else a memo line
                node = Node(None, _slug(text, 40), _slug(text, 40), formula=formula)
                if formula:
                    _declare(node, formula)
                    stack = [node]
                _emit(out, seen, r, lab, node, None, cells, where)
                last_unnumbered_parent = None
                continue
            # an unnumbered line under an 'of which' marker or next to an 'of which' child
            if stack and stack[-1].expects_children:
                parent_path = stack[-1].path
                stack[-1].expects_children = False  # the marker is used up by this line
            elif last_unnumbered_parent is not None:
                parent_path = last_unnumbered_parent
            else:
                raise ValueError(f"{where}: cannot place unnumbered row {r} {lab!r} (add it to continuations?)")
            t = _slug(text, 30)
            node = Node(None, t, f"{parent_path}.{t}")
            _emit(out, seen, r, lab, node, parent_path, cells, where)
            last_unnumbered_parent = parent_path
            continue
        last_unnumbered_parent = None
        fam = _FAMILY[kind]
        tok_norm = tok.lower()
        parent_path = _place(stack, fam, tok_norm, seen)
        path = f"{parent_path}.{tok_norm}" if parent_path else tok_norm
        node = Node(kind, tok_norm, path, formula=formula)
        if formula:
            _declare(node, formula)
        _emit(out, seen, r, lab, node, parent_path, cells, where)
        stack.append(node)
    return out


def _declare(node: Node, formula: tuple[str, str]) -> None:
    node.child_family = _FAMILY.get(_kind_of_token(formula[0]) or "", None)
    node.child_first = formula[0].lower()


def _place(stack: list[Node], fam: str, tok: str, seen: set[str]) -> str | None:
    """Pop the stack to the parent of a new numbered row of family `fam`; return its path.

    Rules, in order: (1) the top declares this family for its children (by its printed formula
    or an 'of which' marker) and the child path is new: child of the top. (2) no node in the
    stack has or expects this family: child of the top (e.g. 'a) Opening Balance' under 'i.').
    (3) the top has this family: its sibling. Otherwise pop and retry. A path already used means
    the row belongs higher up (numbering restarts: '2. Non-Development' after '(b) ... 2.')."""

    def free(parent: str | None) -> bool:
        return (f"{parent}.{tok}" if parent else tok) not in seen

    while stack:
        top = stack[-1]
        declared = top.child_family == fam or (top.expects_children and top.child_family is None)
        # a formula may name earlier siblings ('C. Overall (A+B)'): it declares children only if
        # the first child carries the formula's first token
        if declared and top.n_children == 0 and top.child_first and tok != top.child_first:
            declared = False
        if declared and free(top.path):
            top.child_family = fam
            top.expects_children = False
            top.n_children += 1
            return top.path
        known = any((n.kind and _FAMILY[n.kind] == fam) or n.child_family == fam for n in stack)
        lower = fam in ("roman_low", "alpha_low", "digit")
        if lower and not known and top.child_family is None and free(top.path):
            top.child_family = fam
            top.n_children += 1
            return top.path
        stack.pop()
        if top.kind is not None and _FAMILY[top.kind] == fam:
            parent = stack[-1].path if stack else None
            if free(parent):
                if stack:
                    stack[-1].n_children += 1
                return parent
    if not free(None):
        raise ValueError(f"cannot place numbered row {tok!r}: path already used at the root")
    return None


def _emit(
    out: list[ItemRow], seen: set[str], r: int, lab: str, node: Node, parent: str | None, cells: dict[str, Any], where: str
) -> ItemRow:
    if node.path in seen:
        raise ValueError(f"{where}: duplicate item path {node.path!r} at row {r} ({lab!r})")
    seen.add(node.path)
    _, _, rest = _strip_number(_OF_WHICH.sub("", lab))
    item = ItemRow(r, lab, f"{node.path}-{_slug(rest)}", node.path, parent, node.formula, cells)
    out.append(item)
    return item
