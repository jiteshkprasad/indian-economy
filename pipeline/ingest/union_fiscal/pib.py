"""Parsers for the PIB (Ministry of Finance) monthly GST collection press releases.

The releases are located through PIB's public release archive (allRel.aspx): the pinned archive
page gives the ASP.NET hidden fields, the unit posts the form back for one day and ministry
(DECISIONS D1-7), and `gst_prid` picks the one GST-collection release listed. `release` parses the
pinned release page (PressReleasePage.aspx, the page PIB shows inside its release frame).
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup

from pipeline.core.units import clean_label, parse_number

_HIDDEN = ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION")


def _soup(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_bytes().decode("utf-8"), "lxml")


def archive_form(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Hidden ASP.NET fields of the archive page and its ministry options {value: name}."""
    s = _soup(path)
    hidden: dict[str, str] = {}
    for name in _HIDDEN:
        el = s.find("input", attrs={"name": name})
        if el is None or not el.get("value"):
            raise ValueError(f"{path.name}: hidden field {name} not found")
        hidden[name] = str(el["value"])
    sel = s.find("select", attrs={"name": "ctl00$ContentPlaceHolder1$ddlMinistry"})
    if sel is None:
        raise ValueError(f"{path.name}: ministry list not found")
    ministries = {str(o.get("value")): clean_label(o.get_text()) for o in sel.find_all("option")}
    return hidden, ministries


def _selected(s: BeautifulSoup, name: str) -> str:
    sel = s.find("select", attrs={"name": name})
    opt = sel.find("option", selected=True) if sel is not None else None
    return clean_label(opt.get_text()) if opt is not None else ""


def gst_prid(path: Path, *, year: int, month: int) -> str:
    """The PRID of the GST-collection release for collection month (year, month) in an archive
    listing posted for the release day. The listing must show the filters it was asked for
    (Ministry of Finance, day 1 of the following month), and exactly one release title must name
    GST collections/revenue and the collection month."""
    s = _soup(path)
    ry, rm = (year + 1, 1) if month == 12 else (year, month + 1)
    want = {
        "ctl00$ContentPlaceHolder1$ddlMinistry": "Ministry of Finance",
        "ctl00$ContentPlaceHolder1$ddlday": "1",
        "ctl00$ContentPlaceHolder1$ddlMonth": calendar.month_name[rm],
        "ctl00$ContentPlaceHolder1$ddlYear": str(ry),
    }
    got = {k: _selected(s, k) for k in want}
    if got != want:
        raise ValueError(f"{path.name}: archive listing shows filters {got}, expected {want}")
    mname = calendar.month_name[month]
    hits = []
    for a in s.select("a[href*=PRID]"):
        title = clean_label(a.get_text(" "))
        if (
            re.search(r"\bGST\b", title)
            and re.search(r"collect|revenue", title, re.I)
            and re.search(rf"\b{mname}[,]?\s+{year}\b", title)
        ):
            m = re.search(r"PRID=(\d+)", a["href"])
            if m:
                hits.append((m.group(1), title))
    prids = sorted({h[0] for h in hits})
    if len(prids) != 1:
        raise ValueError(f"{path.name}: expected one GST-collection release for {mname} {year}, found {hits}")
    return prids[0]


# ---------------------------------------------------------------------------------------------
# release page
# ---------------------------------------------------------------------------------------------

_MONTHS = {m: i for i, m in enumerate(calendar.month_abbr) if m}


@dataclass
class GstRelease:
    prid: str
    posted: str  # YYYY-MM-DD
    month: str  # collection month YYYY-MM
    title: str
    headline: dict[str, float]  # Rs crore, from the release text (keys in HEADLINE)
    headline_text: str  # the sentences the headline figures were read from
    state_month: list[tuple[str, str, float, str]] = field(default_factory=list)  # (state, 'YYYY-MM', Rs crore, where)
    state_cum: list[tuple[str, str, str, float]] = field(default_factory=list)  # (state, fy, 'pre'|'post', Rs crore)
    cum_window: str = ""  # 'April-March' etc. as printed in the Table-2 title


def _amt(s: str) -> float:
    v = parse_number(s.replace("₹", "").replace("Rs.", "").replace("Rs", "").strip())
    if v is None:
        raise ValueError(f"not an amount: {s!r}")
    return float(v)


# headline figures (Rs crore) read from the release text; keys -> series item codes
HEADLINE = (
    "gross_gst",
    "cgst",
    "sgst",
    "igst",
    "igst_on_imports",
    "cess",
    "cess_on_imports",
    "igst_settled_to_cgst",
    "igst_settled_to_sgst",
    "cgst_post_settlement",
    "sgst_post_settlement",
)


def _rs(name: str) -> str:
    """'₹1,62,712 crore' / 'Rs 1,87,035 crore' with the number captured as group `name`."""
    return r"(?:₹|Rs\.?)\s*(?P<" + name + r">\d[\d,]*)\s*crore"


_HEADLINE_RE = re.compile(
    r"The gross (?:GST|Goods? (?:&|and) Services Tax \(GST\)) revenue collected in the month of "
    r"(?P<mon>[A-Z][a-z]+),?\s+(?P<yr>\d{4}) is\s*" + _rs("gross_gst") + r"\s*"
    r"(?:out )?of which CGST is\s*" + _rs("cgst") + r"\s*,\s*"
    r"SGST is\s*" + _rs("sgst") + r"\s*,\s*"
    r"IGST is\s*" + _rs("igst") + r"\s*\(including\s*" + _rs("igst_on_imports")
    + r" collected on import of goods\)\s*and cess is\s*" + _rs("cess")
    + r"\s*\(including\s*" + _rs("cess_on_imports") + r" collected on import of goods\)\.\s*"
    r"The government has settled\s*" + _rs("igst_settled_to_cgst") + r" to CGST and\s*"
    + _rs("igst_settled_to_sgst") + r" to SGST from IGST\.\s*"
    r"The total revenue of Centre and the States in the month of (?P<mon2>[A-Z][a-z]+),?\s+(?P<yr2>\d{4}) after "
    r"regular settlement is\s*" + _rs("cgst_post_settlement") + r" for CGST and\s*"
    + _rs("sgst_post_settlement") + r" for the SGST\."
)
_POSTED = re.compile(r"Posted On:\s*(\d{2}) ([A-Z]{3}) (\d{4})")
_RELEASE_ID = re.compile(r"\(Release ID:\s*(\d+)\)")
_TABLE1_HDR = re.compile(r"^([A-Z][a-z]{2})-(\d{2})$")
GST_TOTAL_ROWS = {"Grand Total": "grand_total", "Other Territory": "other_territory",
                  "Center Jurisdiction": "centre_jurisdiction"}


def release(path: Path, *, year: int, month: int) -> GstRelease:
    """Parse one pinned release page. Checks: release id and posting date are printed; the headline
    names the expected collection month; CGST + SGST + IGST + cess = gross (to 2 crore of rounding);
    post-settlement CGST/SGST = collections + IGST settled to each (to 2 crore). Table 1 (State-wise
    GST collected during the month, excluding GST on imports of goods) has the expected two month
    columns, and its rows add up to its printed Grand Total."""
    s = _soup(path)
    text = re.sub(r"\s+", " ", s.get_text(" ", strip=True))
    rid = sorted(set(_RELEASE_ID.findall(text)))
    if len(rid) != 1:
        raise ValueError(f"{path.name}: release id {rid}")
    mp = _POSTED.search(text)
    if not mp:
        raise ValueError(f"{path.name}: 'Posted On' date not found")
    posted = f"{mp.group(3)}-{_MONTHS[mp.group(2).title()]:02d}-{int(mp.group(1)):02d}"
    mh = _HEADLINE_RE.search(text)
    if not mh:
        raise ValueError(f"{path.name}: headline sentence not recognised")
    for mk, yk in (("mon", "yr"), ("mon2", "yr2")):
        if (mh.group(mk), int(mh.group(yk))) != (calendar.month_name[month], year):
            raise ValueError(f"{path.name}: headline month {mh.group(mk)} {mh.group(yk)}, expected {month}/{year}")
    hl = {k: _amt(mh.group(k)) for k in HEADLINE}
    checks = {
        "gross = CGST + SGST + IGST + cess": (hl["gross_gst"], hl["cgst"] + hl["sgst"] + hl["igst"] + hl["cess"]),
        "post-settlement CGST": (hl["cgst_post_settlement"], hl["cgst"] + hl["igst_settled_to_cgst"]),
        "post-settlement SGST": (hl["sgst_post_settlement"], hl["sgst"] + hl["igst_settled_to_sgst"]),
    }
    for what, (a, b) in checks.items():
        if abs(a - b) > 2.0:
            raise ValueError(f"{path.name}: {what}: {a} vs {b}")
    head = text[: mp.start()]
    title = clean_label(head[head.rfind("Ministry of Finance") + len("Ministry of Finance"):])
    rel = GstRelease(rid[0], posted, f"{year}-{month:02d}", title, hl, mh.group(0))
    # Table 1: 'State/UT | Apr-22 | Apr-23 | Growth (%)'. The page repeats it (a copy inside the
    # release block, and the table itself); take the innermost tables with that header.
    tables = [t for t in s.find_all("table") if not t.find("table")]
    t1 = []
    for t in tables:
        rows = [
            [clean_label(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"])] for tr in t.find_all("tr")
        ]
        rows = [r for r in rows if any(r)]
        if rows and rows[0][:1] == ["State/UT"] and len(rows[0]) == 4 and rows[0][3].startswith("Growth"):
            t1.append(rows)
    if not t1 or any(r != t1[0] for r in t1):
        raise ValueError(f"{path.name}: Table 1 not found once ({len(t1)} copies differ)")
    rows = t1[0]
    cols = []
    for h in rows[0][1:3]:
        m = _TABLE1_HDR.match(h)
        if not m:
            raise ValueError(f"{path.name}: Table 1 header {rows[0]}")
        cols.append(f"20{m.group(2)}-{_MONTHS[m.group(1)]:02d}")
    if cols != [f"{year - 1}-{month:02d}", f"{year}-{month:02d}"]:
        raise ValueError(f"{path.name}: Table 1 columns {cols}, expected {month}/{year - 1} and {month}/{year}")
    grand: dict[str, float] = {}
    parts: dict[str, float] = {c: 0.0 for c in cols}
    for r in rows[1:]:
        if len(r) != 4:
            raise ValueError(f"{path.name}: Table 1 row {r}")
        name = r[0]
        for c, cell in zip(cols, r[1:3], strict=True):
            v = _amt(cell)
            rel.state_month.append((name, c, v, "Table 1"))
            if name == "Grand Total":
                grand[c] = v
            else:
                parts[c] += v
    for c in cols:
        if c not in grand or abs(grand[c] - parts[c]) > 25:  # 38 rows each rounded to the crore
            raise ValueError(f"{path.name}: Table 1 rows add up to {parts[c]}, Grand Total {grand.get(c)} ({c})")
    return rel
