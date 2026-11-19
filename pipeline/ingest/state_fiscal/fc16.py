"""Sixteenth Finance Commission 'relevant data' files of the state_fiscal unit: Key Fiscal
Indicators (KFI), the Centre-to-States transfers time series, sector-wise subsidies, the State
Finance Accounts minor-head dump, and the ULB (cityfinance) data dump."""

from __future__ import annotations

import re
from typing import Any

import openpyxl
import polars as pl

from pipeline.core.unit import BuildContext, Dataset
from pipeline.core.units import clean_label, conversion_note, fy, normalize_fy, parse_number, slug, to_inr_crore

from .common import (
    FC16_ABBR,
    UNDIVIDED_AP,
    Geo,
    expect,
    geo_for_period,
    norm,
    state_geo,
    territory_class,
)
from .sources import FC16, FC16_ULB

UNIT = "state_fiscal"
# FC16 publishes no release dates on its data page; the vintage is each file's Last-Modified.
KFI_VINTAGE = "2026-02-03"
ACCOUNTS_VINTAGE = "2026-02-03"
TRANSFERS_VINTAGE = "2026-02-03"
SUBSIDIES_VINTAGE = "2026-02-05"
ULB_VINTAGE = "2026-02-19"
RELEASE = "Sixteenth Finance Commission, relevant data files (fincomindia.nic.in, Feb 2026)"


def _kfi_year(y: Any) -> str:
    """KFI and the accounts dump label fiscal years by their ending year: 2024 = FY 2023-24.

    Checked against the files themselves: the accounts dump's 'Description' sheet says 'Year 2015
    means FY 2014-15', and KFI State GST is 0 through '2017' and first positive in '2018' (GST began
    in July 2017, i.e. FY 2017-18)."""
    return fy(int(y) - 1)


def _kfi_geo(block: str) -> Geo:
    if block == "All_States":
        return Geo("IN", "state_group=all_states_28")
    if block == "non-NEH_States":
        return Geo("IN", "state_group=non_neh_states")
    if block == "NEH_States":
        return Geo("IN", "state_group=neh_states")
    if block == "AP_un":
        return Geo(*UNDIVIDED_AP)
    return Geo(FC16_ABBR[block])


# KFI rows where a 0 can be 'not compiled' rather than a nil (sheet note: "Some of the 'nil' values
# may be missing values"; debt-flow and public-account rows are 0 for whole recent years). Each
# family has a head: when the head is non-zero for the same block and year, the family was compiled
# there and a 0 in it is a true nil (kept); otherwise the 0 is dropped. Evidence in the file:
# - A.4.x under A.4 (public debt receipts), B.6.x under B.6 (repayments);
# - A.4.2.a (GST loans) and A.4.2.b (SASCI loans) are filled for 2023-24 although A.4 is not, so
#   they count as compiled when A.4 or either of them is non-zero ('special_loans');
# - A.9/A.10 under A.10 (public account receipts), B.9/B.10 under B.10;
# - memo rows with no head (C.8.a maximum guaranteed, which cannot be 0 while C.8 > 0; C.3
#   contingency-fund corpus; C.4 off-budget borrowings; C.4-C.6/C.9 debt memo): every 0 is dropped.
KFI_FAMILY = (
    (re.compile(r"^a_4_2_[ab]-"), "special_loans"),
    (re.compile(r"^a_4[-_]"), "a_4"),
    (re.compile(r"^b_6[-_]"), "b_6"),
    (re.compile(r"^(a_9|a_10)-"), "a_10"),
    (re.compile(r"^(b_9|b_10)-"), "b_10"),
    (re.compile(r"^(c_8_a|c_4|c_5-total_debt|c_6|c_9|c_3-contingency)"), "self"),
)
KFI_HEAD_SN = {"a_4": "a_4-", "b_6": "b_6-", "a_10": "a_10-", "b_10": "b_10-", "a_4_2_a": "a_4_2_a-", "a_4_2_b": "a_4_2_b-"}
# Totals built on those families (heads that must be compiled for the total to be complete).
KFI_TOTAL_HEADS = {"a_5": ("a_4",), "a_8": ("a_4",), "b_8": ("b_6",), "a_11": ("a_4", "a_10"), "b_11": ("b_6", "b_10")}
# Year columns where a family is not compiled for (almost) every State: an incomplete cell of these
# totals is dropped, not flagged (the remaining States' cells, e.g. West Bengal 2022-23, are kept).
KFI_INCOMPLETE = {
    "a_5": {"2023-24"},  # A.5 = A.2 + A.4; A.4 not compiled for any State in 2023-24
    "a_8": {"2023-24"},
    "b_8": {"2023-24"},  # B.8 = B.5 + B.6 + B.7; B.6 not compiled for any State in 2023-24
    "a_10": {"2022-23"},  # public account compiled for West Bengal only in 2022-23
    "a_11": {"2022-23", "2023-24"},
    "b_10": {"2022-23"},
    "b_11": {"2022-23", "2023-24"},
}
# Special-category (north-eastern and hill) States: the constituents of the NEH_States block (asserted).
KFI_NEH = ("AR", "AS", "HP", "MN", "ML", "MZ", "NL", "SK", "TR", "UK")
KFI_HEAD_LABEL = {"a_4": "A.4", "b_6": "B.6", "a_10": "A.10", "b_10": "B.10", "special_loans": "A.4.2.a/b", "self": "the item itself"}
KFI_STOCKS = re.compile(r"^(c_1[-_]|c_2[-_]|c_3-outstanding|c_3_a-|c_3-contingency|c_4-off_budget|c_5-outstanding|c_8[-_])")
KFI_RATIOS = re.compile(r"^e_")


def build_kfi(ctx: BuildContext) -> Dataset:
    raw = ctx.raw(FC16, "fc16_kfi.xlsx")
    wb = openpyxl.load_workbook(raw.path, data_only=True, read_only=True)
    notes = " ".join(norm(c) for r in wb["Notes"].iter_rows(values_only=True) for c in r if c)
    for needle in ("values as percentage of gsdp", "some of the 'nil' values may be missing values", "ap_un"):
        if needle not in notes:
            raise ValueError(f"KFI Notes sheet changed: {needle!r} not found")
    ws = wb["State-wise"]
    rows = list(ws.iter_rows(values_only=True))
    head = rows[0]
    if head[1] != "S.N" or head[2] != "Description":
        raise ValueError(f"KFI header changed: {head[:5]}")
    blocks = [(j, c) for j, c in enumerate(head) if isinstance(c, str) and j >= 4]
    if len(blocks) != 32 or blocks[0][1] != "All_States" or blocks[-1][1] != "AP_un":
        raise ValueError(f"KFI blocks changed: {[b for _, b in blocks]}")
    for j, name in blocks:
        if list(head[j + 1 : j + 14]) != list(range(2012, 2025)):
            raise ValueError(f"KFI block {name}: year header {head[j + 1 : j + 14]}")
    periods = [_kfi_year(y) for y in range(2012, 2025)]

    # items: rows with a description (the unlabelled row under an item is its % of GSDP: skipped)
    items: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    part = ""
    for i, r in enumerate(rows[1:], start=2):
        sn, desc = r[1], r[2]
        if isinstance(sn, str) and sn.startswith("Part"):
            part = sn
            continue
        if desc is None:
            continue
        vals = [r[j + 1] for j, _ in blocks]
        if all(v is None for v in vals):
            continue  # a sub-heading such as 'Objects of Revenue Expenditure:'
        label = clean_label(desc)
        code = (slug(sn) + "-" if sn else "") + slug(label)[:40].rstrip("_")
        if code in seen:
            raise ValueError(f"KFI duplicate item code {code}")
        seen.add(code)
        items.append((i, code, label))
    if len(items) != 92:
        raise ValueError(f"KFI item count changed: {len(items)}")

    # the years each block exists (undivided AP to 2014-15, AP and Telangana from 2014-15)
    rr = next(i for i, c, _ in items if c.startswith("a_1-revenue_receipts"))
    alive = {
        name: {p for p, v in zip(periods, rows[rr - 1][j + 1 : j + 14], strict=True) if v not in (None, 0)}
        for j, name in blocks
    }

    cells_by_code: dict[str, dict[tuple[str, str], Any]] = {
        code: {(name, p): x for j, name in blocks for p, x in zip(periods, rows[i - 1][j + 1 : j + 14], strict=True)}
        for i, code, _ in items
    }

    def cells(prefix: str) -> dict[tuple[str, str], Any]:
        return next(c for code, c in cells_by_code.items() if code.startswith(prefix))

    heads = {h: cells(sn) for h, sn in KFI_HEAD_SN.items()}

    def nonzero(x: Any) -> bool:
        return isinstance(x, (int, float)) and x != 0

    def compiled(head: str, name: str, p: str, own: Any) -> bool:
        """Whether the family `head` was compiled for block `name` in year `p` (own = the cell itself)."""
        if head == "self":
            return nonzero(own)
        if head == "special_loans":
            return any(nonzero(heads[h][(name, p)]) for h in ("a_4", "a_4_2_a", "a_4_2_b"))
        return nonzero(heads[head][(name, p)])

    # constituents of the three aggregate blocks, checked on revenue receipts
    states = [name for _, name in blocks if name not in ("All_States", "non-NEH_States", "NEH_States")]
    members = {
        "All_States": states,
        "NEH_States": list(KFI_NEH),
        "non-NEH_States": [s for s in states if s not in KFI_NEH],
    }
    rrc = cells("a_1-revenue_receipts")
    for agg, mem in members.items():
        for p in periods:
            tot = sum(rrc[(s, p)] or 0 for s in mem)
            if abs(tot - rrc[(agg, p)]) > max(1.0, 1e-6 * abs(tot)):
                raise ValueError(f"KFI {agg} {p}: revenue receipts {rrc[(agg, p)]} != sum of members {tot}")

    def exists(s: str, p: str, stock: bool) -> bool:
        """Block s has a figure for year p: its flows exist that year; its end-March stocks exist only if
        it still existed a year later (undivided AP has no balance sheet at end-March 2015)."""
        if p not in alive[s]:
            return False
        k = periods.index(p)
        return not (stock and k + 1 < len(periods) and periods[k + 1] not in alive[s])

    def not_compiled(code: str, name: str, p: str, own: Any) -> dict[str, list[str]]:
        """Heads not compiled under this cell: for a State, only totals are affected (a published non-zero
        family item is itself complete); for an aggregate, any alive member without the head."""
        head_code = code.split("-", 1)[0]
        fam = next((h for rx, h in KFI_FAMILY if rx.match(code)), None)
        hs = KFI_TOTAL_HEADS.get(head_code, (fam,) if fam and name in members else ())
        if not hs:
            return {}
        out: dict[str, list[str]] = {}
        for h in hs:
            if name in members:
                row = cells_by_code[code]
                stock = bool(KFI_STOCKS.match(code))
                miss = [s for s in members[name] if exists(s, p, stock) and not compiled(h, s, p, row[(s, p)])]
            else:
                miss = [] if compiled(h, name, p, own) else [name]
            if miss:
                out[h] = miss
        return out

    def stale_member(code: str, name: str, p: str) -> str | None:
        """verify-10: a group's end-March stock that still counts a block which had ceased (undivided AP's
        end-March 2015 C.8.a repeats end-March 2014 while AP and Telangana report their own). Returns
        the note, after checking that the published total is the live members plus the stale cell."""
        if name not in members or not KFI_STOCKS.match(code):
            return None
        row = cells_by_code[code]
        stale = [s for s in members[name] if p in alive[s] and not exists(s, p, True) and nonzero(row[(s, p)])]
        if not stale:
            return None
        live = sum(row[(s, p)] or 0 for s in members[name] if exists(s, p, True))
        extra = sum(row[(s, p)] for s in stale)
        if abs(row[(name, p)] - live - extra) > 0.05:
            raise ValueError(f"KFI {code} {name} {p}: total {row[(name, p)]} != live members {live} + stale {extra}")
        k = periods.index(p)
        end = f"end-March {int(p[:4]) + 1}"
        prev = "; ".join(f"{s} {row[(s, periods[k - 1])]:,.2f}" for s in stale)
        return (
            f"INCLUDES A STALE UNDIVIDED-AP FIGURE: the published {name} total ({row[(name, p)]:,.2f}) equals its "
            f"member States that exist at {end} ({live:,.2f}) plus the {end} cell of undivided AP ({', '.join(stale)}: "
            f"{extra:,.2f}; a year earlier: {prev}). Undivided AP ceased on 2 June 2014 and Andhra Pradesh and "
            "Telangana report their own figures, so Andhra Pradesh is counted twice. The undivided-AP row itself "
            "is not ingested (verifier finding verify-10)."
        )

    partial_pids: dict[str, str] = {}

    def partial_pid(miss: dict[str, list[str]], is_agg: bool, extra: str | None = None) -> str:
        what = "; ".join(f"{KFI_HEAD_LABEL[h]} not compiled for {', '.join(ms)}" for h, ms in sorted(miss.items()))
        key = f"{is_agg}|{what}|{extra}"
        if key not in partial_pids:
            partial_pids[key] = ctx.prov(
                raw=raw,
                table_id="Key Fiscal Indicators",
                locator="sheet 'State-wise', same cells as the main KFI record (item rows x block x year column)",
                unit_as_published="Rs crore (no caption in the sheet; values are the Finance Accounts totals in Rs crore)",
                price_basis="current",
                vintage=KFI_VINTAGE,
                release=RELEASE,
                notes=(
                    (
                        ("INCOMPLETE AGGREGATE, as published: the group total includes States whose figure is printed "
                         if is_agg else "INCOMPLETE TOTAL, as published: a component of this total is printed ")
                        + f"as 0 = not compiled ({what}). "
                        if miss
                        else ""
                    )
                    + (f"{extra} " if extra else "")
                    + "Year label '2024' = FY 2023-24. Do not use as a complete total; see "
                    "docs/phase1/issues/state_fiscal.md (state_fiscal-3, state_fiscal-23)."
                ),
            )
        return partial_pids[key]

    pid = ctx.prov(
        raw=raw,
        table_id="Key Fiscal Indicators",
        locator=f"sheet 'State-wise', item rows {items[0][0]}-{items[-1][0]} (S.N col B, Description col C); 32 "
        "side-by-side blocks (All_States, non-NEH, NEH, 28 States, AP_un), each 13 year columns headed 2012..2024 "
        "(= FY 2011-12..2023-24); the unlabelled %-of-GSDP rows are not ingested",
        unit_as_published="Rs crore (no caption in the sheet; values are the Finance Accounts totals in Rs crore)",
        price_basis="current",
        vintage=KFI_VINTAGE,
        release=RELEASE,
        notes="Year label '2024' = FY 2023-24. Zeros are kept as nils except: years outside a block's existence; "
        "zeros in a debt-flow/public-account family whose head row (A.4, B.6, A.10, B.10) is 0 for that block-year "
        "(not compiled); all zeros in C.8.a and the C.3-C.9 memo rows; undivided-AP stocks after bifurcation. "
        "Incomplete totals/aggregates carry their own provenance record (see docs/phase1/issues/state_fiscal.md, "
        "state_fiscal-3). GST compensation loans are treated as central grants in the deficits (sheet note). "
        "Label errors as printed: D.2 '(A.3-B.5)' also nets A.6/B.7; C.3.a '(C.3+C.1.2.a)' is in fact C.3 - C.1.2.a. "
        "C.1.2.a '(cum)' is cumulative GST back-to-back loans received, not the outstanding balance. "
        "Block 'AP_un' is undivided Andhra Pradesh, IN-XAP (DECISIONS D1-9): its FY 2014-15 flows are 1 April-1 June "
        "2014, and the AP and Telangana flows for 2014-15 are 2 June 2014-31 March 2015. GSDP rows for AP/TS before "
        "2015-16 and for undivided AP after 2013-14 carry their own records.",
    )
    pid_gsdp = ctx.prov(
        raw=raw,
        table_id="Key Fiscal Indicators",
        locator="sheet 'State-wise', row 'C.10 Gross State Domestic Product (GSDP)', all blocks",
        unit_as_published="Rs crore (no caption)",
        price_basis="current",
        base_year="2011-12",
        vintage=KFI_VINTAGE,
        release=RELEASE,
        notes="Sheet notes: GSDP from MoSPI; for All_States the India GDP figure is used (old 2011-12 base).",
    )
    pid_gsdp_successor = ctx.prov(
        raw=raw,
        table_id="Key Fiscal Indicators",
        locator="sheet 'State-wise', row 'C.10 Gross State Domestic Product (GSDP)', blocks AP and TS, year columns "
        "2012-2015 (FY 2011-12 to 2014-15)",
        unit_as_published="Rs crore (no caption)",
        price_basis="current",
        base_year="2011-12",
        vintage=KFI_VINTAGE,
        release=RELEASE,
        notes="SUCCESSOR-TERRITORY FIGURE: GSDP of the territory that became Andhra Pradesh (IN-AP) or Telangana "
        "(IN-TS) on 2 June 2014, for years that begin before either State existed (FY 2011-12 to 2014-15). AP + TS "
        "equals the undivided-AP block (IN-XAP) exactly in every year. Sheet notes: GSDP from MoSPI, 2011-12 base.",
    )
    pid_gsdp_territorial = ctx.prov(
        raw=raw,
        table_id="Key Fiscal Indicators",
        locator="sheet 'State-wise', row 'C.10 Gross State Domestic Product (GSDP)', block AP_un, year columns "
        "2015-2024 (FY 2014-15 to 2023-24)",
        unit_as_published="Rs crore (no caption)",
        price_basis="current",
        base_year="2011-12",
        vintage=KFI_VINTAGE,
        release=RELEASE,
        notes="TERRITORIAL AGGREGATE, NOT ADDITIVE: GSDP of the former undivided-AP territory (IN-XAP) for years "
        "after it was divided on 2 June 2014; it equals Andhra Pradesh (IN-AP) + Telangana (IN-TS) exactly, so "
        "never add it to them. Sheet notes: GSDP from MoSPI, 2011-12 base.",
    )
    pid_ratio = ctx.prov(
        raw=raw,
        table_id="Key Fiscal Indicators",
        locator="sheet 'State-wise', rows E.1-E.3 (Other Indicators), all blocks",
        unit_as_published="ratio",
        price_basis="n/a",
        vintage=KFI_VINTAGE,
        release=RELEASE,
        notes="Ratios as printed; each is a ratio of two flows of the same block and year (E.1 = B.1.a / A.1 "
        "exactly for AP, TS and AP_un in FY 2014-15, tested). Block 'AP_un' is undivided Andhra Pradesh, IN-XAP "
        "(DECISIONS D1-9): its FY 2014-15 ratios cover 1 April-1 June 2014, and the AP and Telangana ratios for "
        "2014-15 cover 2 June 2014-31 March 2015 (verify-13, state_fiscal-25).",
    )
    def gsdp_pid(geography: str, p: str) -> str:
        c = territory_class(geography, p, "fy")
        if c is None:
            return pid_gsdp
        if geography in ("IN-AP", "IN-TS") and c in ("before", "straddle"):
            return pid_gsdp_successor
        if geography == UNDIVIDED_AP[0] and c in ("after", "straddle"):
            return pid_gsdp_territorial
        raise ValueError(f"KFI GSDP {geography} {p}: territory {c}")

    out: list[dict[str, Any]] = []
    for i, code, label in items:
        r = rows[i - 1]
        is_ratio = bool(KFI_RATIOS.match(code))
        is_gsdp = code.startswith("c_10-")
        stock = bool(KFI_STOCKS.match(code))
        head_code = code.split("-", 1)[0]
        for j, name in blocks:
            geo = _kfi_geo(name)
            for p, cell in zip(periods, r[j + 1 : j + 14], strict=True):
                if isinstance(cell, str):
                    if cell.strip() in ("#DIV/0!",):
                        continue
                    raise ValueError(f"KFI {code} {name} {p}: text cell {cell!r}")
                v = parse_number(cell)
                if v is None:
                    continue
                if v == 0:
                    if p not in alive[name]:
                        continue  # the block does not exist that year (undivided AP, AP, Telangana)
                    fam = next((h for rx, h in KFI_FAMILY if rx.match(code)), None)
                    if fam and not compiled(fam, name, p, v):
                        continue  # 'not compiled', not a nil
                k = periods.index(p)
                if stock and k + 1 < len(periods) and periods[k + 1] not in alive[name]:
                    # no balance sheet at end-March after the block ceased: undivided AP ended on 2 June
                    # 2014, so its '2015' stocks are 0, except C.8.a which repeats end-March 2014 (55,536)
                    continue
                miss = not_compiled(code, name, p, v)
                if miss and p in KFI_INCOMPLETE.get(head_code, set()):
                    continue  # year-wide not-compiled column: dropped (declared)
                stale = stale_member(code, name, p)
                out.append(
                    {
                        "series_id": f"kfi.{code}.{geo.key}",
                        "source_id": FC16,
                        "table_id": "Key Fiscal Indicators",
                        "item_code": code,
                        "item_label": label,
                        "institution": "gg_state",
                        "geography": geo.geography,
                        "dim_other": geo.dim_other,
                        "stock_flow": "n/a" if is_ratio else "stock" if stock else "flow",
                        "period": f"{int(p[:4]) + 1}-03-31" if stock else p,
                        "period_type": "date" if stock else "fy",
                        "value": v,
                        "unit": "ratio" if is_ratio else "INR_crore",
                        "price_basis": "n/a" if is_ratio else "current",
                        "base_year": "2011-12" if is_gsdp else None,
                        "vintage": KFI_VINTAGE,
                        "estimate_stage": "Audited",
                        "status": "official",
                        "prov_id": pid_ratio if is_ratio else gsdp_pid(geo.geography, p) if is_gsdp
                        else partial_pid(miss, name in members, stale) if (miss or stale) else pid,
                    }
                )
    return Dataset(
        f"{UNIT}_fc16_kfi",
        pl.DataFrame(out, infer_schema_length=None),
        "FC16 Key Fiscal Indicators: 28 States (+groups, undivided AP), ~90 items, FY 2011-12 to 2023-24 (Finance Accounts)",
    )


# ---------------------------------------------------------------------------------------------
# Transfers time series
# ---------------------------------------------------------------------------------------------

TRANSFER_COLS = {  # master sheet column (1-based) -> (code, label as printed in row 2)
    3: ("states_share", "States' share"),
    4: ("fc_grants", "FC grants"),
    5: ("total_fc_transfers", "Total transfers through FC"),
    6: ("non_fc_grants", "Non-FC grants"),
    7: ("total_grants", "Total grants"),
    8: ("total_transfers", "Total transfers"),
    10: ("gtr", "GTR"),
}
GRANT_DETAIL_COLS = {  # 'Grants - details RBI' sheet
    2: ("share_in_central_taxes", "Share in Central Taxes"),
    3: ("total_grants", "Total grants from Centre"),
    4: ("state_plan_spl_plan_nec", "State Plan, Spl Plan and NEC Schemes"),
    5: ("central_plan_and_css", "Central Plan and Centrally Sponsored Schemes"),
    6: ("statutory_grants", "Statutory grants (incl natural calamity grant)"),
    7: ("non_plan_non_statutory", "Non-plan non-statutory grants"),
    8: ("fc_grants", "Finance Commission grants"),
    9: ("art_275_1_grants", "Grants under proviso to Art 275(1)"),
    10: ("other_grants", "Other Grants"),
}


def _period_stage(text: Any) -> tuple[str, str]:
    t = norm(text)
    stage = "RE" if t.endswith("re") else "BE" if t.endswith("be") else "Actuals"
    return normalize_fy(re.sub(r"(re|be)$", "", t).strip()), stage


def build_transfers(ctx: BuildContext) -> Dataset:
    raw = ctx.raw(FC16, "fc16_transfers.xlsx")
    wb = openpyxl.load_workbook(raw.path, data_only=True)
    ws = wb["Time series of transfers - mast"]
    for col, (_, lab) in TRANSFER_COLS.items():
        if norm(ws.cell(2, col).value) != norm(lab):
            raise ValueError(f"transfers master: column {col} header {ws.cell(2, col).value!r}, expected {lab!r}")
    expect(ws, "B2", "Year")
    out: list[dict[str, Any]] = []
    years = [
        r
        for r in range(3, ws.max_row + 1)
        if isinstance(ws.cell(r, 2).value, str) and re.fullmatch(r"\d{4}-\d{2}\s*(RE|BE)?", ws.cell(r, 2).value.strip())
    ]
    pid = ctx.prov(
        raw=raw,
        table_id="Time series of transfers (master)",
        locator=f"sheet 'Time series of transfers - mast', year rows {years[0]}-{years[-1]} (col B), cols C:H and J; "
        "'Average %' rows and ratio columns I, K:N not ingested",
        unit_as_published="Rs crore (no caption; Union Budget / RBI figures in Rs crore)",
        price_basis="current",
        vintage=TRANSFERS_VINTAGE,
        release=RELEASE,
        notes="Sources per sheet: RBI Bulletins/DBIE to 2022-23, Union Budget Statement 18 from 2023-24; FC grants "
        "1982-83..2001-02 are FC-XII ratios x RBI gross revenue (derived by FC16); non-FC grants = total - FC grants.",
    )
    for r in years:
        period, stage = _period_stage(ws.cell(r, 2).value)
        for col, (code, lab) in TRANSFER_COLS.items():
            v = parse_number(ws.cell(r, col).value)
            if v is None:
                continue
            out.append(_tr_row(f"tsm.{code}.{stage.lower()}", "Time series of transfers (master)", code, lab, period, stage, v, pid, stage != "Actuals"))
    ws = wb["Grants - details RBI"]
    for col, (_, lab) in GRANT_DETAIL_COLS.items():
        if norm(ws.cell(2, col).value) != norm(lab):
            raise ValueError(f"grant details: column {col} header {ws.cell(2, col).value!r}, expected {lab!r}")
    years = [r for r in range(3, ws.max_row + 1) if isinstance(ws.cell(r, 1).value, str) and re.match(r"\d{4}-\d{2}$", ws.cell(r, 1).value.strip())]
    pid = ctx.prov(
        raw=raw,
        table_id="Grants - details RBI",
        locator=f"sheet 'Grants - details RBI', year rows {years[0]}-{years[-1]} (col A), cols B:J",
        unit_as_published="Rs crore (no caption)",
        price_basis="current",
        vintage=TRANSFERS_VINTAGE,
        release=RELEASE,
        notes="RBI data to 2022-23; 2023-24 from Union Budget Statement 18 (sheet note). '-' = not available.",
    )
    for r in years:
        period, stage = _period_stage(ws.cell(r, 1).value)
        for col, (code, lab) in GRANT_DETAIL_COLS.items():
            v = parse_number(ws.cell(r, col).value)
            if v is None:
                continue
            out.append(_tr_row(f"gd.{code}", "Grants - details RBI", code, lab, period, stage, v, pid, False))
    return Dataset(
        f"{UNIT}_fc16_transfers",
        pl.DataFrame(out, infer_schema_length=None),
        "FC16 time series of Centre-to-State transfers (States' share, FC and non-FC grants, GTR), 1952-53 to 2025-26 BE",
    )


def _tr_row(sid, table, code, label, period, stage, v, pid, _est) -> dict[str, Any]:
    union = code == "gtr"  # the Union's gross tax revenue (the devolution base), not a State series
    return {
        "series_id": sid,
        "source_id": FC16,
        "table_id": table,
        "item_code": code,
        "item_label": clean_label(label),
        "institution": "gg_centre" if union else "gg_state",
        "geography": "IN",
        "counterparty": None if union else "gg_centre",
        "dim_other": None if union else "state_group=all_states",
        "stock_flow": "flow",
        "period": period,
        "period_type": "fy",
        "value": v,
        "unit": "INR_crore",
        "price_basis": "current",
        "vintage": TRANSFERS_VINTAGE,
        "estimate_stage": stage,
        "status": "official",
        "prov_id": pid,
    }


# ---------------------------------------------------------------------------------------------
# Sector-wise subsidies
# ---------------------------------------------------------------------------------------------


def build_subsidies(ctx: BuildContext) -> Dataset:
    raw = ctx.raw(FC16, "fc16_subsidies.xlsx")
    ws = openpyxl.load_workbook(raw.path, data_only=True).worksheets[0]
    expect(ws, "A1", "Sector wise Subsidies and Transfers (Union and States)")
    expect(ws, "J1", "Rs. Crore")
    expect(ws, "A2", "State")
    expect(ws, "B2", "Sector")
    heads = {c: ws.cell(2, c).value for c in range(3, 11)}
    periods = {}
    for c, h in heads.items():
        t = clean_label(h)
        m = re.fullmatch(r"(\d{4}-\d{2})\s*(\((RE|BE)\))?", t)
        if not m:
            raise ValueError(f"subsidies: header {h!r}")
        periods[c] = (m.group(1), m.group(3) or "Actuals")
    body = [r for r in range(3, ws.max_row + 1) if ws.cell(r, 1).value]
    pid = ctx.prov(
        raw=raw,
        table_id="Sector wise Subsidies and Transfers",
        locator=f"sheet '{ws.title}', rows {body[0]}-{body[-1]} (State col A x Sector col B), cols C:J "
        "(2018-19 to 2025-26 BE)",
        unit_as_published="Rs. Crore",
        price_basis="current",
        vintage=SUBSIDIES_VINTAGE,
        release=RELEASE,
        notes="21 States and the Union only. Blank cells are not available (no row); zeros kept as published.",
    )
    out = []
    for r in body:
        state = clean_label(ws.cell(r, 1).value)
        sector = clean_label(ws.cell(r, 2).value)
        geo = Geo("IN", None, "gg_centre") if state == "Union" else state_geo(state)
        for c, (period, stage) in periods.items():
            v = parse_number(ws.cell(r, c).value)
            if v is None:
                continue
            out.append(
                {
                    "series_id": f"sub.{slug(sector)}.{geo.key}.{geo.institution}",
                    "source_id": FC16,
                    "table_id": "Sector wise Subsidies and Transfers",
                    "item_code": f"subsidy_{slug(sector)}",
                    "item_label": f"Subsidies and transfers: {sector}",
                    "institution": geo.institution,
                    "geography": geo.geography,
                    "stock_flow": "flow",
                    "period": period,
                    "period_type": "fy",
                    "value": v,
                    "unit": "INR_crore",
                    "price_basis": "current",
                    "vintage": SUBSIDIES_VINTAGE,
                    "estimate_stage": stage,
                    "status": "official",
                    "prov_id": pid,
                }
            )
    df = pl.DataFrame(out, infer_schema_length=None)
    return Dataset(
        f"{UNIT}_fc16_subsidies",
        df,
        "FC16 sector-wise subsidies and transfers, 21 States and the Union, 2018-19 to 2025-26 BE",
    )


# ---------------------------------------------------------------------------------------------
# State Finance Accounts (minor-head dump) -> major-head totals and local-body assistance
# ---------------------------------------------------------------------------------------------

LOCAL_BODY_MINOR = {  # CGA List of Major and Minor Heads: assistance to local bodies
    "191": "urban",
    "192": "urban",
    "193": "urban",
    "196": "rural",
    "197": "rural",
    "198": "rural",
}
CLASSES = {"Revenue Rec": "revenue_receipts", "Revenue Exp": "revenue_expenditure", "Capital Exp": "capital_expenditure", "Capital Rec": "capital_receipts"}


def _accounts_frame(path) -> pl.DataFrame:
    df = pl.read_excel(path, sheet_name="ServiceHeads", engine="calamine", infer_schema_length=0)
    want = [
        "State Abb", "Year", "Classification", "Category", "Sub Category", "Major Head", "Major Head Desc",
        "Sub Major Head", "Sub Major Head Desc", "Minor Head", "Minor Head Desc", "Amount_State", "Amount_Centre", "Amount",
    ]  # fmt: skip
    if df.columns != want:
        raise ValueError(f"ServiceHeads columns changed: {df.columns}")
    return df


def build_state_accounts(ctx: BuildContext) -> list[Dataset]:
    raw = ctx.raw(FC16, "fc16_state_accounts.xlsx")
    desc = openpyxl.load_workbook(raw.path, read_only=True)["Description"]
    text = " ".join(norm(c) for r in desc.iter_rows(values_only=True) for c in r if c)
    for needle in ("year 2015 means fy 2014-15", "amount in in lakh", "#bh means union government"):
        if needle not in text:
            raise ValueError(f"accounts 'Description' sheet changed: {needle!r} not found")
    df = _accounts_frame(raw.path)
    unknown = set(df["Classification"].unique().to_list()) - set(CLASSES)
    if unknown:
        raise ValueError(f"accounts: unknown classifications {unknown}")
    bad = df.filter(pl.col("Amount").is_not_null() & pl.col("Amount").cast(pl.Float64, strict=False).is_null())
    if bad.height:
        raise ValueError(f"accounts: non-numeric amounts {bad.head(3)}")
    df = df.filter(pl.col("Amount").is_not_null()).with_columns(
        pl.col("Amount").cast(pl.Float64),
        (pl.col("Year").cast(pl.Int64) - 1).alias("y0"),
    )
    states = sorted(set(df["State Abb"].unique().to_list()) - {"#BH", "AP_un"})
    if set(states) - set(FC16_ABBR):
        raise ValueError(f"accounts: unknown State codes {set(states) - set(FC16_ABBR)}")
    common = {
        "raw": raw,
        "price_basis": "current",
        "vintage": ACCOUNTS_VINTAGE,
        "release": RELEASE,
        "status": "derived",
    }
    pid_mh = ctx.prov(
        table_id="State Finance Accounts - ServiceHeads",
        locator="sheet 'ServiceHeads' (550,775 minor-head rows: State Abb, Year, Classification, Major Head, ..., "
        "Amount); summed by State x Year x Classification x Major Head",
        unit_as_published="Rs lakh",
        conversion=conversion_note("INR_lakh"),
        method="Sum of column 'Amount' over all minor-head rows of the same State, Year, Classification and Major "
        "Head (blank amounts skipped), then Rs lakh / 100. Year label 2024 = FY 2023-24 (sheet 'Description').",
        notes="Minor-head data of the CAG Finance Accounts compiled by FC16. Some State-years are missing (sheet "
        "'Missing data'); #BH = Union Government. Duplicate minor-head keys in the dump are summed." + ACC_TERRITORY,
        **common,
    )
    pid_lb = ctx.prov(
        table_id="State Finance Accounts - ServiceHeads",
        locator="sheet 'ServiceHeads', rows with Minor Head 191, 192, 193 (urban local bodies) and 196, 197, 198 "
        "(panchayats), Classification 'Revenue Exp' and 'Capital Exp'",
        unit_as_published="Rs lakh",
        conversion=conversion_note("INR_lakh"),
        method="Sum of 'Amount' over all major heads for each assistance-to-local-bodies minor head (CGA list: 191 "
        "municipal corporations, 192 municipalities, 193 nagar panchayats, 196 zila parishads, 197 block "
        "panchayats, 198 gram panchayats), by State, Year and Classification; Rs lakh / 100.",
        notes="Minor heads 191-198 only. Major head 3604 (Compensation and Assignments to Local Bodies and "
        "Panchayati Raj Institutions; KFI B.1.4, 1,14,381 crore for 28 States in 2023-24) is not included, and "
        "neither are local-body transfers booked under other minor heads, so this is not total State transfers "
        "to local bodies." + ACC_TERRITORY,
        **common,
    )
    g = (
        df.group_by("State Abb", "y0", "Classification", "Major Head", maintain_order=True)
        .agg(pl.col("Amount").sum(), pl.col("Major Head Desc").min(), pl.len().alias("n"))
        .sort("State Abb", "y0", "Classification", "Major Head")
    )
    out = []
    for st, y0, cl, mh, amt, mdesc, _ in g.iter_rows():
        geo = _acc_geo(st, y0)
        out.append(
            _acc_row(
                f"fa.{CLASSES[cl]}.mh{mh}.{geo.key}",
                f"mh_{mh}",
                f"{mh} {clean_label(mdesc)}",
                geo,
                CLASSES[cl],
                fy(y0),
                to_inr_crore(amt, "INR_lakh"),
                pid_mh,
            )
        )
    lb = (
        df.filter(pl.col("Minor Head").is_in(list(LOCAL_BODY_MINOR)) & pl.col("Classification").is_in(["Revenue Exp", "Capital Exp"]))
        .group_by("State Abb", "y0", "Classification", "Minor Head", maintain_order=True)
        .agg(pl.col("Amount").sum())
        .sort("State Abb", "y0", "Classification", "Minor Head")
    )
    labels = {
        "191": "Assistance to Municipal Corporations",
        "192": "Assistance to Municipalities/Municipal Councils",
        "193": "Assistance to Nagar Panchayats/Notified Area Committees",
        "196": "Assistance to Zila Parishads/District Level Panchayats",
        "197": "Assistance to Block Panchayats/Intermediate Level Panchayats",
        "198": "Assistance to Gram Panchayats",
    }
    lb_rows = []
    for st, y0, cl, mn, amt in lb.iter_rows():
        geo = _acc_geo(st, y0)
        lb_rows.append(
            _acc_row(
                f"falb.{CLASSES[cl]}.minor{mn}.{geo.key}",
                f"minor_{mn}",
                f"All major heads, minor head {mn}: {labels[mn]}",
                geo,
                CLASSES[cl],
                fy(y0),
                to_inr_crore(amt, "INR_lakh"),
                pid_lb,
                counterparty=f"gg_local_{LOCAL_BODY_MINOR[mn]}",
            )
        )
    return [
        Dataset(
            f"{UNIT}_fc16_state_accounts",
            pl.DataFrame(out, infer_schema_length=None),
            "FC16 State Finance Accounts dump summed to major heads: States, UTs with legislature and Union, FY 1995-96 to 2023-24",
        ),
        Dataset(
            f"{UNIT}_fc16_local_body_assistance",
            pl.DataFrame(lb_rows, infer_schema_length=None),
            "FC16 State Finance Accounts: assistance to urban and rural local bodies under minor heads 191-198 only, by "
            "State and year; excludes MH 3604 (compensation and assignments to local bodies), so not total transfers",
        ),
    ]


ACC_TERRITORY = (
    " Territories (DECISIONS D1-9): 'AP_un' is undivided Andhra Pradesh, IN-XAP (to 1 June 2014; its FY "
    '2014-15 rows are 1 April-1 June 2014, and the AP and Telangana rows for 2014-15 are 2 June 2014-31 '
    "March 2015); 'JK' for FY 2013-14 to 2018-19 is the former State of Jammu and Kashmir incl. Ladakh, "
    'IN-XJK, and for 2020-21 the UT, IN-JK (the dump has no J&K 2019-20). FY 2000-01 straddles the '
    'creation of Uttarakhand (9 Nov 2000) and Jharkhand (15 Nov 2000): by magnitude, the UK and JH rows '
    'cover only the months after creation, and the UP row the whole year (undivided to 8 Nov 2000).'
)


def _acc_geo(st: str, y0: int) -> Geo:
    """FC16 'State Abb' -> Geo for FY y0-(y0+1). The accounts of the former State of Jammu and Kashmir
    (FY 2013-14 to 2018-19, before the UTs of 31 Oct 2019) are IN-XJK; the UT's accounts are IN-JK."""
    if st == "#BH":
        return Geo("IN", None, "gg_centre")
    if st == "AP_un":
        return Geo(*UNDIVIDED_AP)
    return geo_for_period(Geo(FC16_ABBR[st]), fy(y0), "fy")


def _acc_row(sid, code, label, geo, account, period, v, pid, counterparty=None) -> dict[str, Any]:
    dims = [d for d in (geo.dim_other, f"account={account}") if d]
    return {
        "series_id": sid,
        "source_id": FC16,
        "table_id": "State Finance Accounts - ServiceHeads",
        "item_code": code,
        "item_label": clean_label(label),
        "institution": geo.institution,
        "counterparty": counterparty,
        "geography": geo.geography,
        "side": "receipts" if "receipts" in account else "payments",
        "dim_other": ";".join(sorted(dims)),
        "stock_flow": "flow",
        "period": period,
        "period_type": "fy",
        "value": float(v),
        "unit": "INR_crore",
        "price_basis": "current",
        "vintage": ACCOUNTS_VINTAGE,
        "estimate_stage": "Audited",
        "status": "derived",
        "prov_id": pid,
    }


# ---------------------------------------------------------------------------------------------
# ULB data dump (cityfinance)
# ---------------------------------------------------------------------------------------------

ULB_FIRST, ULB_LAST = 8, 48  # 1-based columns 'Property Tax' .. 'Total Cash and Bank Balance'
ULB_STOCK_PREFIXES = (
    "central_and_state_government", "bonds", "banks_and_financial", "borrowings_others", "gross_borrowings",
    "receivables", "other_receivables", "total_receivables", "total_cash",
)  # fmt: skip
ULB_SECTIONS = {  # 1-based column -> section prefix, so the two 'Others' columns stay distinct
    30: "revenue_expenditure",
    42: "borrowings",
}


def build_ulb(ctx: BuildContext) -> Dataset:
    raw = ctx.raw(FC16_ULB, "fc16_ulb_cityfinance.xlsx")
    df = pl.read_excel(
        raw.path,
        sheet_name="Financial & Docs_All_ULBs clean",
        engine="calamine",
        infer_schema_length=0,
        read_options={"header_row": None},
    )
    head = [clean_label(h) if h else "" for h in df.row(0)]
    if head[1] != "State" or head[5] != "Year" or head[ULB_FIRST - 1] != "Property Tax" or head[ULB_LAST - 1] != "Total Cash and Bank Balance":
        raise ValueError(f"ULB header changed: {head}")
    body = df.slice(1)
    items = []
    for c in range(ULB_FIRST, ULB_LAST + 1):
        lab = head[c - 1]
        code = slug(lab)[:50].rstrip("_")
        if c in ULB_SECTIONS:
            code = f"{ULB_SECTIONS[c]}_{code}"
        items.append((f"column_{c}", code, lab))
    if len({c for _, c, _ in items}) != len(items):
        raise ValueError("ULB item codes are not unique")
    cols = [pl.col("column_2").alias("state"), pl.col("column_6").alias("year")]
    for col, code, _ in items:
        cols.append(pl.col(col).cast(pl.Float64, strict=True).alias(code))
    d = body.select(cols)
    long = d.unpivot(index=["state", "year"], variable_name="code", value_name="v").filter(pl.col("v").is_not_null())
    g = (
        long.group_by("state", "year", "code", maintain_order=True)
        .agg(pl.col("v").sum().alias("sum"), pl.len().alias("n"))
        .sort("state", "year", "code")
    )
    tot = long.group_by("year", "code", maintain_order=True).agg(pl.col("v").sum().alias("sum"), pl.len().alias("n")).sort("year", "code")
    labels = {code: lab for _, code, lab in items}
    pid = ctx.prov(
        raw=raw,
        table_id="FC16 ULB Data Dump (Financial & Docs_All_ULBs clean)",
        locator="sheet 'Financial & Docs_All_ULBs clean', 37,866 ULB-year rows, cols H:AV ('Property Tax' .. 'Total "
        "Cash and Bank Balance'); grouped by State (col B) and Year (col F)",
        unit_as_published="rupees (the sheet has no unit caption; magnitudes are rupees per ULB)",
        conversion=conversion_note("INR"),
        price_basis="current",
        vintage=ULB_VINTAGE,
        release=RELEASE,
        status="derived",
        method="For each State, Year and item: sum over ULB rows with a non-blank value (rupees x 1e-7 = Rs crore); "
        "the all-India row sums all ULB rows. A companion '..._n_ulbs' series counts the ULB rows summed. "
        "'Number of registered properties' is a count and is summed as a count.",
        notes="Coverage grows from 3,725 ULBs (2015-16) to 4,620 (2023-24); blank cells are not zeros. Known "
        "data-quality jumps (registry quirks: e.g. Khategaon tax revenue 11x in one year).",
    )
    pid_n = ctx.prov(
        raw=raw,
        table_id="FC16 ULB Data Dump (Financial & Docs_All_ULBs clean)",
        locator="sheet 'Financial & Docs_All_ULBs clean', cols H:AV, grouped by State (col B) and Year (col F)",
        unit_as_published="count",
        price_basis="n/a",
        vintage=ULB_VINTAGE,
        release=RELEASE,
        status="derived",
        method="'_n_ulbs' series: number of ULB rows with a non-blank value for the item in that State and Year "
        "(all-India: all rows). 'Number of registered properties': sum over ULB rows of the published count.",
    )
    out = []

    def emit(geo: Geo, year: str, code: str, s: float, n: int) -> None:
        is_count = code == "number_of_registered_properties"
        # balance-sheet items (the dump's URL column points to cityfinance 'balanceSheet' data sets)
        stock = code.startswith(ULB_STOCK_PREFIXES)
        p = normalize_fy(year)
        base = {
            "source_id": FC16_ULB,
            "table_id": "FC16 ULB Data Dump",
            "institution": "gg_local_ulb",
            "geography": geo.geography,
            "dim_other": geo.dim_other,
            "period": p,
            "period_type": "fy",
            "price_basis": "n/a" if is_count else "current",
            "vintage": ULB_VINTAGE,
            "estimate_stage": "n.a.",  # ULB annual accounts, audited for some ULBs and not for others
            "status": "derived",
        }
        out.append(
            base
            | {
                "prov_id": pid_n if is_count else pid,
                "series_id": f"ulb.{code}.{geo.key}",
                "item_code": code,
                "item_label": labels[code],
                "stock_flow": "stock" if stock else "flow",
                "period": f"{int(p[:4]) + 1}-03-31" if stock else p,
                "period_type": "date" if stock else "fy",
                "value": s if is_count else to_inr_crore(s, "INR"),
                "unit": "count" if is_count else "INR_crore",
            }
        )
        out.append(
            base
            | {
                "prov_id": pid_n,
                "series_id": f"ulb.{code}_n_ulbs.{geo.key}",
                "item_code": f"{code}_n_ulbs",
                "item_label": f"Number of ULBs reporting: {labels[code]}",
                "stock_flow": "n/a",
                "price_basis": "n/a",
                "value": float(n),
                "unit": "count",
            }
        )

    for st, year, code, s, n in g.iter_rows():
        emit(state_geo(st), year, code, s, n)
    for year, code, s, n in tot.iter_rows():
        emit(Geo("IN", "state_group=all_ulbs_in_dump"), year, code, s, n)
    return Dataset(
        f"{UNIT}_ulb_cityfinance",
        pl.DataFrame(out, infer_schema_length=None),
        "FC16 ULB (cityfinance) dump summed by State: ULB revenue, grants, expenditure, borrowing, 2015-16 to 2023-24",
    )
