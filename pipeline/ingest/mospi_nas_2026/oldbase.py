"""Old-base (2011-12) National Accounts: ratios and history only, never mixed with the new base.

- NAS 2024 (published 5 Jun 2024), the last edition with full sequences of accounts:
  1.15 total economy, 2.0 NFC (2.1 public, 2.1A departmental, 2.1B non-departmental, 2.2 private),
  3.0 FC (3.1 public, 3.2 private), 4.0 general government, 5.0 households, 6.0 rest of the
  world; 2011-12 to 2022-23, current prices. Dataset mospi_nas_2026_oldbase_soa_<stmt>.
- NAS 2025 (published 26 Jun 2025), key statements 1.1, 1.9, 1.14, 5.3; 2011-12 to 2023-24.
  Dataset mospi_nas_2026_oldbase_nas2025_<stmt>.

Every row carries base_year 2011-12 and the edition's vintage; price bases are `current` or
`constant_2011_12`. Estimate stages are the revision rounds the MoSPI NAS API gives for exactly these
values (see STAGES; checked by test_oldbase_stages_match_api_revision_rounds). The NAS 2024
methodology note (pinned) also states that 2022-23 is the FRE in NAS 2024. Rows are checked against
the frozen spec_oldbase.json.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import openpyxl
import polars as pl

from pipeline.core.unit import BuildContext, Dataset, RawFile
from pipeline.core.units import normalize_fy, parse_number, slug
from pipeline.ingest.mospi_nas_2026 import grid
from pipeline.ingest.mospi_nas_2026.codes import institution_code, is_institution

UNIT = "mospi_nas_2026"
SRC = "mospi_nas_old_base_2011_12"
SPEC_FILE = "spec_oldbase.json"
BASE_YEAR = "2011-12"
CUR, CON = "current", "constant_2011_12"

# Vintages are the MoSPI CMS listing dates of the editions (Phase 0 recon); they cannot be verified from
# the pinned files: every old-base file's server Last-Modified is 16 May 2025, which for NAS 2025 is
# before the listed 26 Jun 2025 (issue mospi_nas_2026-9, verifier finding verify-6). Values unaffected.
EDITIONS = {
    "nas2024": ("2024-06-05", "National Accounts Statistics 2024 (NSO, MoSPI; old base 2011-12; published 5 Jun 2024)"),
    "nas2025": ("2025-06-26", "National Accounts Statistics 2025 (NSO, MoSPI; old base 2011-12; published 26 Jun 2025)"),
}
# Estimate stage of each year's figure in each edition. The files print none. Until 2026-09-29 the unit assumed
# the textbook cycle (latest FRE, then SRE, then TRE). The MoSPI NAS API (base 2011-12, series Current) labels
# every revision round, and matching the editions' values to it (issue mospi_nas_2026-9) gives: 2011-12 to
# 2013-14 are the API's 'Additional Revision' round (-> 'Revised') in both editions, and in NAS 2025, 2022-23
# is the API's 'Final Estimates' and 2021-22 its 'Second Revised Estimates'. Other years as the cycle says.
STAGES = {
    "nas2024": {2022: "FRE", 2021: "SRE"},
    "nas2025": {2023: "FRE", 2022: "Final", 2021: "SRE"},
}


def stage(edition: str, period: str) -> str:
    y = int(period[:4])
    if y <= 2013:
        return "Revised"
    return STAGES[edition].get(y, "TRE")


@dataclass(frozen=True)
class OldCfg:
    edition: str
    stmt: str
    kind: str  # soa | grid
    title_cell: str
    title: str
    unit_cell: str
    label: str = "O"
    code_col: str = "P"
    year_row: int = 8
    first: int = 10
    panels: tuple[tuple[str, str, str | None], ...] = (("C:N", CUR, None),)
    section: str | None = None
    sheet: str | None = None

    @property
    def file(self) -> str:
        return f"{self.edition}_{self.stmt}.xlsx"

    @property
    def key(self) -> str:
        return f"{self.edition}/{self.stmt}"

    @property
    def dataset(self) -> str:
        tag = "soa" if self.kind == "soa" else self.edition
        return f"{UNIT}_oldbase_{tag}_s{self.stmt.lower().replace('.', '_')}"


_SOA = {
    "1.15": ("A4", "Sequence of Accounts-Total Economy", "P7", 8),
    "2.0": ("A3", "Sequence of Accounts - Non-financial corporations", "P6", 7),
    "2.1": ("A3", "Sequence of Accounts - Public non-Financial Corporations", "P7", 8),
    "2.1A": ("A3", "Departmental En", "P6", 7),
    "2.1B": ("A3", "Non-departmental", "P7", 8),
    "2.2": ("A3", "Sequence of Accounts - Private non-financial corporations", "P7", 8),
    "3.0": ("A3", "Sequence of Accounts - Financial corporations", "P7", 8),
    "3.1": ("A3", "Sequence of Accounts - Public Financial Corporations", "P7", 8),
    "3.2": ("A3", "Sequence of Accounts - Private Financial Corporations", "P7", 8),
    "4.0": ("A3", "Sequence of Accounts- General Government", "P6", 7),
    "5.0": ("A3", "Sequence of Accounts - Households", "P7", 8),
    "6.0": ("A3", "Sequence of Accounts- Rest of the World", "I7", 8),
}
SOA_INSTITUTION = {
    "1.15": "total_economy", "2.0": "nfc", "2.1": "nfc_public", "2.1A": "nfc_public_de", "2.1B": "nfc_public_nde",
    "2.2": "nfc_private", "3.0": "fc", "3.1": "fc_public", "3.2": "fc_private", "4.0": "gg",
    "5.0": "households_npish", "6.0": "rest_of_world",
}

CFGS: tuple[OldCfg, ...] = (
    *(OldCfg("nas2024", s, "soa", t, title, u, year_row=yr, first=yr + 2) for s, (t, title, u, yr) in _SOA.items()),
    OldCfg("nas2025", "1.1", "grid", "P1", "Statement 1.1: Key aggregates of National Accounts", "V3", label="AC",
           code_col="AD", year_row=5, first=7, panels=(("C:O", CUR, "C2"), ("P:AB", CON, "P2"))),
    OldCfg("nas2025", "1.9", "grid", "C2", "Statement 1.9: Finances for Gross Capital Formation", "I4", label="P",
           code_col="Q", year_row=6, first=8, panels=(("C:O", CUR, "C3"),)),
    OldCfg("nas2025", "1.14", "grid", "C3", "Statement 1.14: Institutional Sectoral Accounts", "I6", label="P",
           code_col="Q", year_row=8, first=10, panels=(("C:O", CUR, "D4"),), section="institution"),
    OldCfg("nas2025", "5.3", "grid", "A3", "FINANCIAL ASSESTS AND LIABILITIES OF HOUSEHOLD SECTOR", "I5", label="P",
           code_col="Q", year_row=7, first=9, panels=(("C:O", CUR, "E4"),)),
)

# The sequence-of-accounts sheets print the SNA code twice: column A (Hindi side) and column P (English
# side). Wherever both hold an ASCII code they must agree, or the build fails. The one publisher error
# found (verifier finding verify-1, issue mospi_nas_2026-24): in NAS 2024 Statement 3.0, column P is
# shifted one row down on the financial-account liabilities block (P92 'F1' beside 'Net incurrence of
# liabilities' ... P100 'B9' beside 'Other accounts payable', P101 blank beside NET LENDING). There, the
# code is taken from column A, and the build checks the exact shift (P[r] == A[r+1] on every row), so a
# corrected re-issue of the file fails loudly instead of being silently re-coded.
CODE_SHIFTED_P = {"nas2024/3.0": (92, 101)}
# A code printed in only one of the two columns counts as a disagreement too (verifier note s2-1: a re-issue
# that blanks one column while shifting the other must not slip through). The one known one-sided row outside
# the shifted block: NAS 2024 1.15 row 11, where column A holds a corrupted formula string instead of 'P1'
# (column P 'P1' beside 'Output, in basic prices' is right). It is accepted only with exactly these contents.
ONE_SIDED_OK = {("nas2024/1.15", 11): ("P1+34:3411:153", "P1")}
_SNA_CODE = re.compile(r"[A-Z][A-Za-z0-9+/]{0,7}")


def _ascii_code(v: Any) -> str:
    """An SNA code printed in a code column ('F3', 'D9r', 'B2n+B3n'), or '' for Hindi text, headings, blanks."""
    s = v.strip() if isinstance(v, str) else ""
    return s if _SNA_CODE.fullmatch(s) and s.upper() not in ("CODE", "USES") else ""


def _row_code(ws: Any, cfg: OldCfg, r: int) -> str:
    code_p = grid.text(ws, f"{cfg.code_col}{r}")
    code_a = _ascii_code(ws[f"A{r}"].value)
    lo_hi = CODE_SHIFTED_P.get(cfg.key)
    if lo_hi and lo_hi[0] <= r <= lo_hi[1]:
        below = _ascii_code(ws[f"A{r + 1}"].value)
        if _ascii_code(code_p) != below:
            raise ValueError(f"{cfg.key} row {r}: expected the known one-row shift of column {cfg.code_col} "
                             f"({cfg.code_col}{r}={code_p!r} == A{r + 1}={below!r}); the file changed")
        return code_a
    p_code = _ascii_code(code_p)
    if code_a == p_code:
        return code_p
    known = ONE_SIDED_OK.get((cfg.key, r))
    if known and (grid.text(ws, f"A{r}"), code_p) == known:
        return code_p
    raise ValueError(f"{cfg.key} row {r}: SNA code columns disagree or only one holds a code "
                     f"(A={ws[f'A{r}'].value!r}, {cfg.code_col}={code_p!r})")


SIDES = {
    "resources": "resources",
    "uses": "uses",
    "changes in liabilities and net worth": "liabilities",
    "changes in assets": "assets",
}


@dataclass
class OldRow:
    row: int
    label: str
    code: str  # the SNA code as printed ('' if none)
    account: str
    side: str
    values: dict[str, float | None]

    @property
    def has_data(self) -> bool:
        return any(v is not None for v in self.values.values())


@dataclass
class OldParsed:
    cfg: OldCfg
    ws: Any
    years: dict[str, tuple[str, str]]  # col -> (period, basis)
    rows: list[Any]
    sections: list[str]
    serials: list[str] | None = None


def _sheet(raw: RawFile, cfg: OldCfg) -> Any:
    wb = openpyxl.load_workbook(raw.path, data_only=True)
    if len(wb.worksheets) != 1:
        raise ValueError(f"{cfg.key}: expected one sheet, found {wb.sheetnames}")
    return wb.worksheets[0]


def _years(ws: Any, cfg: OldCfg) -> dict[str, tuple[str, str]]:
    grid.expect(ws, cfg.title_cell, cfg.title)
    grid.expect(ws, cfg.unit_cell, "crore")
    out: dict[str, tuple[str, str]] = {}
    for cols, basis, check in cfg.panels:
        if check:
            grid.expect(ws, check, "current" if basis == CUR else "constant (2011-12)")
        for c in grid.cols(cols):
            out[c] = (normalize_fy(grid.text(ws, f"{c}{cfg.year_row}")), basis)
    return out


def _soa_rows(ws: Any, cfg: OldCfg, years: dict[str, tuple[str, str]]) -> list[OldRow]:
    first_years = [p for p, _ in years.values()]
    rows: list[OldRow] = []
    account, side, blank = "", "", 0
    r = cfg.year_row - 3  # the first account title sits just above the first year header
    while r <= ws.max_row and blank < 12:
        row_text = {c: grid.english(v) for c in grid.cols("A:Q") if isinstance((v := ws[f"{c}{r}"].value), str)}
        if any(re.match(r"^notes?\s*:", t, re.I) for t in row_text.values()):
            break
        if not grid.text(ws, f"{cfg.label}{r}") and any(re.match(r"^[*#@$]", t) for t in row_text.values()):
            break  # footnotes
        label = grid.english(grid.text(ws, f"{cfg.label}{r}"))
        code = grid.text(ws, f"{cfg.code_col}{r}")
        raw_vals = {c: ws[f"{c}{r}"].value for c in years}
        if not row_text and all(v is None for v in raw_vals.values()):
            blank += 1
            r += 1
            continue
        blank = 0
        if isinstance(ws[f"C{r}"].value, str) and grid.english(ws[f"C{r}"].value) == first_years[0]:
            got = [normalize_fy(grid.text(ws, f"{c}{r}")) for c in years]  # repeated year header
            if got != first_years:
                raise ValueError(f"{cfg.key} row {r}: year header {got} differs from {first_years}")
            r += 1
            continue
        if ws[f"{cfg.label}{r}"].value is not None and not isinstance(ws[f"{cfg.label}{r}"].value, str):
            r += 1  # the column-number row (1, 2, 3 ...)
            continue
        if code.lower() in SIDES:
            side = SIDES[code.lower()]
            r += 1
            continue
        titles = [t for t in row_text.values() if re.search(r"\baccount\b|external account", t, re.I)]
        if not code and titles and not any(isinstance(v, (int, float)) for v in raw_vals.values()):
            account = slug(titles[0].lower().replace(" account", "").replace("account of ", ""))
            side = ""
            r += 1
            continue
        if not label and not any(isinstance(v, (int, float)) for v in raw_vals.values()) and (
            any("crore" in t.lower() for t in row_text.values()) or not any(row_text.values())
        ):
            r += 1
            continue
        if not label:
            raise ValueError(f"{cfg.key} row {r}: unrecognised row {row_text}")
        if not account or not side:
            raise ValueError(f"{cfg.key} row {r}: item {label!r} outside an account/side block")
        vals = {c: parse_number(v) for c, v in raw_vals.items()}
        rows.append(OldRow(r, label, _row_code(ws, cfg, r), account, side, vals))
        r += 1
    return rows


def parse(raw: RawFile, cfg: OldCfg) -> OldParsed:
    ws = _sheet(raw, cfg)
    years = _years(ws, cfg)
    if cfg.kind == "soa":
        rows: list[Any] = _soa_rows(ws, cfg, years)
        return OldParsed(cfg, ws, years, rows, ["" for _ in rows])
    rows = grid.read_rows(ws, label_col=cfg.label, first=cfg.first, value_cols=list(years))
    sections, cur = [], ""
    for r in rows:
        if not r.has_data and (cfg.section != "institution" or is_institution(r.label)):
            cur = r.label
        sections.append(cur)
    serials = [grid.serial(ws, r.row, (cfg.code_col, "A")) for r in rows]
    return OldParsed(cfg, ws, years, rows, sections, serials)


def _mask(row: Any, years: dict) -> str:
    return "".join("0" if row.values[c] is None else "1" for c in years)


def _item_code(r: OldRow) -> str:
    base = slug(r.code.replace("+", "_plus_").replace("/", "_")) if r.code else grid._short_slug(r.label)
    return f"{r.account}.{r.side}.{base}"


def spec_rows(p: OldParsed) -> list[list[str]]:
    if p.cfg.kind == "soa":
        codes = [_item_code(r) for r in p.rows]
        seen: dict[str, int] = {}
        out = []
        for r, c in zip(p.rows, codes, strict=True):
            seen[c] = seen.get(c, 0) + 1
            out.append([r.label, "d" if r.has_data else "h", c if seen[c] == 1 else f"{c}_{seen[c]}",
                        _mask(r, p.years)])
        return out
    labels = [r.label for r in p.rows]
    data = [r.has_data for r in p.rows]
    if p.cfg.stmt == "1.1":
        codes = _s1_1_codes(p)
    elif p.cfg.section:
        codes = [grid._short_slug(lab) if d else "" for lab, d in zip(labels, data, strict=True)]
    else:
        codes = grid.derive_codes(labels, data, p.serials)
    return [[r.label, "d" if r.has_data else "h", c, _mask(r, p.years)] for r, c in zip(p.rows, codes, strict=True)]


def _s1_1_codes(p: OldParsed) -> list[str]:
    """NAS 2025 Statement 1.1 uses the same item codes as the new-base Statement 1.1 (template map in
    __init__.S1_1_ITEMS), matched by (section, label) ignoring case, so the two bases line up by code."""
    from pipeline.ingest.mospi_nas_2026 import S1_1_ITEMS

    table = {(sec, lab.lower()): it.code for (sec, lab), it in S1_1_ITEMS.items()}
    out = []
    for r, section in zip(p.rows, p.sections, strict=True):
        if not r.has_data:
            out.append("")
            continue
        key = (slug(section), r.label.lower())
        if key not in table:
            raise ValueError(f"{p.cfg.key}: row {r.row} {key} is not in the Statement 1.1 item map")
        out.append(table[key])
    return out


def build_one(ctx: BuildContext, cfg: OldCfg) -> Dataset:
    raw = ctx.raw(SRC, cfg.file)
    p = parse(raw, cfg)
    spec = grid.load_spec(SPEC_FILE).get(cfg.key)
    if spec is None:
        raise ValueError(f"{cfg.key}: no row spec in {SPEC_FILE}")
    got = spec_rows(p)
    if got != spec:
        diff = [f"row {r.row}: {g} vs {w}" for r, g, w in zip(p.rows, got, spec, strict=False) if g != w]
        raise ValueError(f"{cfg.key}: rows differ from the frozen spec (statement changed?): {diff[:6] or len(got)}")
    vintage, release = EDITIONS[cfg.edition]
    tbl = cfg.dataset.removeprefix(f"{UNIT}_")
    out: list[dict[str, Any]] = []
    prov: dict[str, str] = {}
    rws = [r.row for r in p.rows]
    for row, s, section in zip(p.rows, spec, p.sections, strict=True):
        code = s[2]
        if not row.has_data:
            continue
        pct = bool(re.search(r"ratio|rate|percentage|share|to gdp|to gndi|to nni", f"{row.label} {section}", re.I)) \
            and cfg.kind == "grid" and cfg.stmt == "1.1" and bool(re.search(r"rate|percentage", section, re.I))
        for c, (period, basis) in p.years.items():
            v = row.values[c]
            if v is None:
                continue
            pk = f"{basis}/{pct}"
            if pk not in prov:
                cl = [k for k, (_, b) in p.years.items() if b == basis]
                prov[pk] = ctx.prov(
                    raw=raw,
                    table_id=f"Statement {cfg.stmt} ({cfg.edition.upper()})",
                    locator=f"sheet '{p.ws.title}', rows {rws[0]}-{rws[-1]}, cols {cl[0]}:{cl[-1]} ({basis}); "
                    f"rows matched by English label in column {cfg.label} against spec_oldbase.json",
                    unit_as_published="percent" if pct else "Rs crore",
                    conversion="none",
                    price_basis=basis,
                    base_year=BASE_YEAR,
                    vintage=vintage,
                    release=release,
                )
            dims: dict[str, Any] = {"geography": "IN"}
            if cfg.kind == "soa":
                dims["institution"] = SOA_INSTITUTION[cfg.stmt]
                dims["side"] = row.side
                dims["dim_other"] = f"account={row.account}"
                item = code.split(".", 2)[2]
                sid = f"{tbl}.{code}.{basis}"
            elif cfg.section == "institution":
                dims["institution"] = institution_code(section)
                item = code
                sid = f"{tbl}.{dims['institution']}.{code}.{basis}"
            else:
                item = code
                sid = f"{tbl}.{code}.{basis}"
            if cfg.stmt == "5.3" and cfg.kind == "grid":
                dims["institution"] = "households_npish"
            out.append(
                {
                    "series_id": sid,
                    "source_id": SRC,
                    "table_id": f"Statement {cfg.stmt} ({cfg.edition.upper()})",
                    "item_code": item,
                    "item_label": row.label if cfg.kind == "grid" else f"{row.label} [{row.code or '-'}]",
                    **dims,
                    "stock_flow": "n/a" if pct else "flow",
                    "period": period,
                    "period_type": "fy",
                    "value": v,
                    "unit": "percent" if pct else "INR_crore",
                    "price_basis": basis,
                    "base_year": BASE_YEAR,
                    "vintage": vintage,
                    "estimate_stage": stage(cfg.edition, period),
                    "status": "official",
                    "prov_id": prov[pk],
                }
            )
    title = grid.english(grid.text(p.ws, cfg.title_cell))
    return Dataset(cfg.dataset, pl.DataFrame(out), f"Old base 2011-12, {cfg.edition.upper()}: {title[:140]}")


def build(ctx: BuildContext) -> list[Dataset]:
    return [build_one(ctx, c) for c in CFGS]
