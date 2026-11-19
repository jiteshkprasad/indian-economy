"""Small tables typed out of PDF reports (text layer, parsed by label with regexes).

- HCES 2023-24 Report No. 592: Table 3.17 (MPCE with/without imputation, major States),
  Table 3.18 (MPCE 1999-2000 to 2023-24, nominal and at 2011-12 prices), Table 3.19 (MPCE by item
  group with/without imputation, All-India).
- NSS Report No. 596 (Health, Jan-Dec 2025): Table 2.21 (out-of-pocket medical expenditure per
  hospitalisation case by household-consumption quintile, R/U) and Table 2.24 (out-patient care).
- NSS Report No. 595 (CMS: Education 2025, Apr-Jun 2025): Statement 2.3 (average expenditure per
  student on school education by level, gender and sector).

Every table is found on a pinned page whose title is asserted; each row is matched by its label and
must carry exactly the expected count of numbers, so a re-typeset report fails instead of shifting.
"""

from __future__ import annotations

import re
from typing import Any

import pdfplumber
import polars as pl

from pipeline.core.unit import BuildContext, Dataset
from pipeline.core.units import agricultural_year, parse_number

from ._common import ROUNDS, UNIT, state_geo, survey_note, sy_period

NUM = r"-?[\d,]+(?:\.\d+)?"


def _page_text(path: Any, page: int) -> str:
    with pdfplumber.open(path) as pdf:
        return pdf.pages[page - 1].extract_text() or ""


def _nums(s: str) -> list[float]:
    out = []
    for tok in re.findall(NUM, s):
        v = parse_number(tok)
        if v is None:
            raise ValueError(f"unparseable number {tok!r}")
        out.append(v)
    return out


def _line(text: str, label_re: str, n: int, where: str) -> list[float]:
    """The n numbers that follow `label_re` at the start of a line (exactly one such line)."""
    pat = re.compile(rf"^{label_re}\s+((?:{NUM}\s*){{{n}}})$", re.M)
    hits = pat.findall(text)
    if len(hits) != 1:
        raise ValueError(f"{where}: expected one line matching {label_re!r} with {n} numbers, found {len(hits)}")
    vals = _nums(hits[0])
    if len(vals) != n:
        raise ValueError(f"{where}: {label_re!r}: {len(vals)} numbers, expected {n}")
    return vals


def _require(text: str, needle: str, where: str) -> None:
    if needle not in text:
        raise ValueError(f"{where}: expected text {needle!r} on the pinned page")


# =============================================================================================
# HCES Report No. 592
# =============================================================================================

R592_FILE = "hces2324_report592.pdf"
R592_URL = "https://www.mospi.gov.in/sites/default/files/publication_reports/Final_Report_HCES_2023-24L.pdf"
P_T317, P_T318, P_T319 = 69, 70, 71

# Rounds in Table 3.18, as printed in the column heads -> survey window (period_type 'sy').
# The table prints only the round ('1999-'00 NSS (55th round)'); the July-June windows of NSS rounds
# 55, 61, 66 and 68 were checked on 2026-09-29 against the IHSN survey catalogue (dates of data
# collection: catalog.ihsn.org/catalog/2606 1999-07-01..2000-06-30, /1910 2004-07..2005-06,
# /1903 2009-07..2010-06, /3281 2011-07..2012-06). The HCES windows are printed in Report 592 (pp.3, 20).
T318_ROUNDS = [
    ("1999-00", agricultural_year(1999), "NSS 55th round, July 1999-June 2000, MRP"),
    ("2004-05", agricultural_year(2004), "NSS 61st round, July 2004-June 2005, MRP"),
    ("2009-10", agricultural_year(2009), "NSS 66th round, July 2009-June 2010, MMRP"),
    ("2011-12", agricultural_year(2011), "NSS 68th round, July 2011-June 2012, MMRP"),
    ("2022-23", sy_period("2022-23"), "HCES 2022-23, August 2022-July 2023, MMRP (new design)"),
    ("2023-24", sy_period("2023-24"), "HCES 2023-24, August 2023-July 2024, MMRP (new design)"),
]
T318_SY = {label: sy for label, sy, _ in T318_ROUNDS}

T319_ITEMS: list[tuple[str, str, str]] = [  # (code, regex for the label as typeset, published label)
    ("cereals", r"cereals & cereal substitutes", "cereals & cereal substitutes"),
    ("pulses", r"pulses & pulse products\*", "pulses & pulse products (includes gram)"),
    ("sugar_salt", r"sugar & salt", "sugar & salt"),
    ("milk", r"milk & milk products", "milk & milk products"),
    ("vegetables", r"vegetables", "vegetables"),
    ("fruits", r"fruits", "fruits"),
    ("egg_fish_meat", r"egg, fish & meat", "egg, fish & meat"),
    ("edible_oil", r"edible oil", "edible oil"),
    ("spices", r"spices", "spices"),
    ("beverages_processed", r"beverages, refreshments,\n", "beverages, refreshments, processed food (includes purchased cooked meals)"),
    ("food_total", r"food total", "food total"),
    ("pan_tobacco", r"pan, tobacco & intoxicants", "pan, tobacco & intoxicants"),
    ("fuel_light", r"fuel and light", "fuel and light"),
    ("education", r"education", "education"),
    ("medical", r"medical", "medical"),
    ("conveyance", r"conveyance", "conveyance"),
    ("consumer_services", r"consumer services excl\.\n", "consumer services excl. conveyance (includes tailoring charges)"),
    ("misc_goods_entertainment", r"misc\. goods, entertainment", "misc. goods, entertainment"),
    ("rent", r"rent", "rent"),
    ("taxes_cesses", r"taxes and cesses", "taxes and cesses"),
    ("clothing_bedding_footwear", r"clothing, bedding & footwear\$", "clothing, bedding & footwear (excludes tailoring charges)"),
    ("durables", r"durable goods", "durable goods"),
    ("nonfood_total", r"non-food total", "non-food total"),
    ("all_items", r"all items", "all items"),
]
T319_FOOD = ["cereals", "pulses", "sugar_salt", "milk", "vegetables", "fruits", "egg_fish_meat", "edible_oil", "spices",
             "beverages_processed"]
T319_NONFOOD = ["pan_tobacco", "fuel_light", "education", "medical", "conveyance", "consumer_services",
                "misc_goods_entertainment", "rent", "taxes_cesses", "clothing_bedding_footwear", "durables"]

T317_STATES = ["Andhra Pradesh", "Assam", "Bihar", "Chhattisgarh", "Gujarat", "Haryana", "Jharkhand", "Karnataka",
               "Kerala", "Madhya Pradesh", "Maharashtra", "Odisha", "Punjab", "Rajasthan", "Tamil Nadu", "Telangana",
               "Uttar Pradesh", "West Bengal", "All-India"]


def build_report592(ctx: BuildContext) -> Dataset:
    rd = ROUNDS["2023-24"]
    src = rd["src"]
    raw = ctx.raw(src, R592_FILE)
    base = {"source_id": src, "vintage": rd["vintage"], "estimate_stage": "n.a.", "status": "official",
            "stock_flow": "flow", "unit": "INR", "period_type": "sy"}
    sy2324 = sy_period("2023-24")
    rows: list[dict[str, Any]] = []
    release = "HCES 2023-24, NSS Report No. 592 (NSO, MoSPI, 30 Jan 2025)"

    # ---- Table 3.18 --------------------------------------------------------------------------
    where = "Report 592 Table 3.18"
    t = _page_text(raw.path, P_T318)
    _require(t, "Table 3.18: Trend in MPCE since 1999", where)
    _require(t, "At nominal price", where)
    _require(t, "At real price (2011-12 price)", where)
    nominal, real = t.split("At real price (2011-12 price)", 1)
    nominal = nominal.split("At nominal price", 1)[1]
    notes318 = (
        "Columns: 1999-00 (NSS 55th, Jul 1999-Jun 2000, MRP), 2004-05 (61st, Jul-Jun, MRP), 2009-10 (66th, "
        "Jul-Jun, MMRP), 2011-12 (68th, Jul-Jun, MMRP), 2022-23 (HCES, Aug 2022-Jul 2023), 2023-24 (HCES, Aug "
        "2023-Jul 2024). Rows carry the survey window as period_type 'sy' (e.g. 1999-07/2000-06, 2023-08/2024-07); "
        "the NSS July-June windows are not printed in the table and were checked against the IHSN survey catalogue "
        "(catalog.ihsn.org 2606, 1910, 1903, 3281). MRP->MMRP (2009-10) and the "
        "2022-23 survey redesign are level breaks (table note i). 'With imputation' adds imputed values of free "
        "items from social-welfare schemes (2022-23 and 2023-24 only). Real values: 1999-00 to 2009-10 inflated with "
        "CPI(AL)/CPI(IW), 2022-23 onward deflated with CPI(R)/CPI(U) to 2011-12 prices (table note ii)."
    )
    for basis, block, base_year in (("current", nominal, None), ("constant_2011_12", real, "2011-12")):
        pid = ctx.prov(raw=raw, table_id="Table 3.18", locator=f"PDF page {P_T318} (report page 52), Table 3.18, "
                       f"'{'At nominal price' if basis == 'current' else 'At real price (2011-12 price)'}' rows Rural/Urban, "
                       "cols 2-9", unit_as_published="Rs. per person per 30 days", conversion="none",
                       price_basis=basis, base_year=base_year, vintage=rd["vintage"], release=release, notes=notes318)
        for sector in ("Rural", "Urban"):
            v = _line(block, sector, 8, where)
            cols = [("mpce", p) for p, _, _ in T318_ROUNDS[:5]] + [("mpce_with_imputation", "2022-23"),
                                                                    ("mpce", "2023-24"), ("mpce_with_imputation", "2023-24")]
            for (code, period), val in zip(cols, v, strict=True):
                rows.append({**base, "series_id": f"t3_18.{code}.{sector.lower()}.{basis}", "table_id": "Table 3.18",
                             "item_code": code, "item_label": "Average MPCE (Rs.)" + (" with imputation" if "imput" in code else ""),
                             "geography": "IN", "household_group": f"{sector.lower()}_all", "period": T318_SY[period],
                             "value": val, "price_basis": basis, "base_year": base_year, "prov_id": pid})

    # ---- Table 3.19 --------------------------------------------------------------------------
    where = "Report 592 Table 3.19"
    t = _page_text(raw.path, P_T319)
    _require(t, "Table 3.19: Absolute and percentage break-up of MPCE by item groups in 2023-24: All-India", where)
    body = t.split("(1) (2) (3) (4) (5) (6) (7) (8) (9)", 1)[1]
    pid_v = ctx.prov(raw=raw, table_id="Table 3.19", locator=f"PDF page {P_T319} (report page 53), Table 3.19, cols 2-5",
                     unit_as_published="Rs. per person per 30 days", conversion="none", price_basis="current",
                     vintage=rd["vintage"], release=release, notes=survey_note("2023-24"))
    pid_s = ctx.prov(raw=raw, table_id="Table 3.19", locator=f"PDF page {P_T319} (report page 53), Table 3.19, cols 6-9",
                     unit_as_published="percent of total MPCE", conversion="none", price_basis="n/a",
                     vintage=rd["vintage"], release=release, notes=survey_note("2023-24"))
    for code, rx, label in T319_ITEMS:
        if rx.endswith(r"\n"):
            m = re.search(rf"^{rx}({NUM}(?: {NUM}){{7}})$", body, re.M)
            vals = _nums(m.group(1)) if m else []
            if len(vals) != 8:
                raise ValueError(f"{where}: split label {rx!r} not followed by 8 numbers")
        else:
            vals = _line(body, rx, 8, where)
        for i, (metric, sector) in enumerate([("mpce", "rural"), ("mpce", "urban"), ("mpce_with_imputation", "rural"),
                                              ("mpce_with_imputation", "urban"), ("share", "rural"), ("share", "urban"),
                                              ("share_with_imputation", "rural"), ("share_with_imputation", "urban")]):
            is_share = metric.startswith("share")
            rows.append({**base, "series_id": f"t3_19.{code}.{metric}.{sector}" + ("" if is_share else ".current"),
                         "table_id": "Table 3.19", "item_code": metric, "item_label": label,
                         "product": f"hces_group:{code}", "geography": "IN", "household_group": f"{sector}_all",
                         "period": sy2324, "value": vals[i], "unit": "percent" if is_share else "INR",
                         "stock_flow": "n/a" if is_share else "flow", "price_basis": "n/a" if is_share else "current",
                         "prov_id": pid_s if is_share else pid_v})

    # ---- Table 3.17 --------------------------------------------------------------------------
    where = "Report 592 Table 3.17"
    t = _page_text(raw.path, P_T317)
    _require(t, "Table 3.17: Average MPCE and urban-rural differences in MPCE in 2023-24, major States", where)
    body = t.split("(1) (2) (3) (4) (5) (6) (7)", 1)[1]
    pid17 = ctx.prov(raw=raw, table_id="Table 3.17", locator=f"PDF page {P_T317} (report page 51), Table 3.17, cols 2,3,5,6",
                     unit_as_published="Rs. per person per 30 days", conversion="none", price_basis="current",
                     vintage=rd["vintage"], release=release, notes=survey_note("2023-24"))
    for st in T317_STATES:
        v = _line(body, re.escape(st), 6, where)
        geo = state_geo(st)
        for (metric, sector), val in (
            (("mpce", "rural"), v[0]), (("mpce", "urban"), v[1]),
            (("mpce_with_imputation", "rural"), v[3]), (("mpce_with_imputation", "urban"), v[4]),
        ):
            rows.append({**base, "series_id": f"t3_17.{metric}.{geo.lower()}.{sector}.current", "table_id": "Table 3.17",
                         "item_code": metric, "item_label": "Average MPCE (Rs.)" + (" with imputation" if "imput" in metric else ""),
                         "geography": geo, "household_group": f"{sector}_all", "period": sy2324, "value": val,
                         "price_basis": "current", "prov_id": pid17})
    return Dataset(f"{UNIT}_report592_mpce", pl.DataFrame(rows),
                   "HCES 2023-24 Report 592 Tables 3.17-3.19: MPCE with/without imputation by State and item group; "
                   "MPCE trend 1999-00 to 2023-24 (nominal and 2011-12 prices)")


# =============================================================================================
# NSS Report No. 596: Health (Jan-Dec 2025)
# =============================================================================================

H596_FILE = "nss596_health_report.pdf"
H596_URL = ("https://www.mospi.gov.in/uploads/publications_reports/publications_reports1776676412084_2b4f2b5c-2f1c-"
            "446b-8fa3-ec8f125b2b66_Final_Report_no_596_Health_(2).pdf")
H596_VINTAGE = "2026-04"
H596_RELEASE = "NSS Report No. 596: Household Social Consumption: Health, NSS 80th round (NSO, MoSPI, April 2026)"
P_T221, P_T224 = 55, 58
H596_NOTE = (
    "Survey period January-December 2025 (NSS 80th round). Quintile classes here are quintiles of HOUSEHOLDS by "
    "the round's own usual monthly per capita expenditure (UMPCE), not HCES 2023-24 person fractiles; use as a "
    "distribution check only (gap map C4d). Out-of-pocket = total medical expenditure minus reimbursement."
)


def build_health596(ctx: BuildContext) -> Dataset:
    src = "nss_health_2025_report"
    raw = ctx.raw(src, H596_FILE)
    base = {"source_id": src, "vintage": H596_VINTAGE, "estimate_stage": "n.a.", "status": "official",
            "stock_flow": "flow", "unit": "INR", "period": "2025", "period_type": "cy", "price_basis": "current",
            "geography": "IN"}
    rows: list[dict[str, Any]] = []
    where = "Report 596 Table 2.21"
    t = _page_text(raw.path, P_T221)
    _require(t, "Table 2.21: Average out-pocket medical expenditure (₹) per case of hospitalization", where)
    pid = ctx.prov(raw=raw, table_id="Table 2.21", locator=f"PDF page {P_T221} (report page 29), Table 2.21, rows "
                   "1st-5th quintile and All, cols average (R, U) and median (R, U)",
                   unit_as_published="Rs. per hospitalisation case (last 365 days)", conversion="none",
                   price_basis="current", vintage=H596_VINTAGE, release=H596_RELEASE, notes=H596_NOTE)
    labels = [("1st quintile", "hh_q1"), ("2nd quintile", "hh_q2"), ("3rd quintile", "hh_q3"),
              ("4th quintile", "hh_q4"), ("5th quintile", "hh_q5"), ("All", "all")]
    for lab, q in labels:
        v = _line(t, lab, 4, where)
        for (metric, sector), val in zip([("oop_per_hosp_case_avg", "rural"), ("oop_per_hosp_case_avg", "urban"),
                                          ("oop_per_hosp_case_median", "rural"), ("oop_per_hosp_case_median", "urban")],
                                         v, strict=True):
            rows.append({**base, "series_id": f"t2_21.{metric}.{sector}_{q}", "table_id": "Table 2.21",
                         "item_code": metric,
                         "item_label": ("Average" if metric.endswith("avg") else "Median")
                         + " out-of-pocket medical expenditure (Rs.) per hospitalization case (excluding childbirth), last 365 days",
                         "household_group": f"{sector}_{q}", "value": val, "prov_id": pid})
    where = "Report 596 Table 2.24"
    t = _page_text(raw.path, P_T224)
    _require(t, "Table 2.24: Average and Median out-of-pocket medical expenditure for out-", where)
    seg = t.split("Table 2.24", 1)[1].split("Table 2.25", 1)[0]
    pid = ctx.prov(raw=raw, table_id="Table 2.24", locator=f"PDF page {P_T224} (report page 32), Table 2.24, rows "
                   "Rural, Urban, Rural+ Urban", unit_as_published="Rs. per treated spell of ailment (last 15 days)",
                   conversion="none", price_basis="current", vintage=H596_VINTAGE, release=H596_RELEASE, notes=H596_NOTE)
    for lab, hg in (("Rural", "rural_all"), ("Urban", "urban_all"), (r"Rural\+ Urban", "all")):
        v = _line(seg, lab, 2, where)
        for metric, val in zip(("oop_per_opd_spell_avg", "oop_per_opd_spell_median"), v, strict=True):
            rows.append({**base, "series_id": f"t2_24.{metric}.{hg}", "table_id": "Table 2.24", "item_code": metric,
                         "item_label": ("Average" if metric.endswith("avg") else "Median")
                         + " out-of-pocket medical expenditure (Rs.) per treated spell of ailment (out-patient care), last 15 days",
                         "household_group": hg, "value": val, "prov_id": pid})
    return Dataset(f"{UNIT}_health596", pl.DataFrame(rows),
                   "NSS Report 596 (Health, Jan-Dec 2025) Tables 2.21 and 2.24: out-of-pocket medical expenditure per "
                   "hospitalisation case by household quintile (R/U) and per out-patient spell")


# =============================================================================================
# NSS Report No. 595: CMS Education 2025 (Apr-Jun 2025)
# =============================================================================================

E595_FILE = "cms_education_2025_report.pdf"
E595_URL = ("https://www.mospi.gov.in/uploads/publications_reports/publications_reports1757588642898_9ba30fe0-3677-"
            "478c-8d53-9a0d2ba107f0_CMS_E_2025L.pdf")
E595_VINTAGE = "2025-08"
E595_RELEASE = "NSS Report No. 595: Comprehensive Modular Survey: Education, 2025 (NSO, MoSPI, August 2025)"
P_S23 = (26, 27)
E595_NOTE = (
    "Survey period April-June 2025 (NSS 80th round CMS); expenditure during the current academic year on school "
    "education, all components (course fee, books, uniform, transport, coaching, etc.), per student currently "
    "enrolled. No consumption-class split is published; used as a check only (gap map C4d)."
)
E595_LEVELS = [("Pre-primary", "pre_primary"), ("Primary", "primary"), ("Middle", "middle"),
               ("Secondary", "secondary"), ("Higher secondary", "higher_secondary"), ("All", "all")]


def build_cms_education(ctx: BuildContext) -> Dataset:
    src = "nss_cms_education_2025_report"
    raw = ctx.raw(src, E595_FILE)
    where = "Report 595 Statement 2.3"
    text = ""
    for p in P_S23:
        t = _page_text(raw.path, p)
        _require(t, "Statement 2.3: Average expenditure (₹) per student on school education by", where)
        text += t.split("Level of current enrolment male female person", 1)[1].split("Statement 2.4", 1)[0].split(
            "NSS Report No. 595", 1)[0]
        text += "\n"
    # blocks: rural, urban, rural + urban (the third continues on the next page)
    parts = re.split(r"^(rural \+ urban|rural|urban)$", text, flags=re.M)
    blocks: dict[str, str] = {}
    cur = None
    for piece in parts:
        if piece in ("rural", "urban", "rural + urban"):
            cur = piece
            blocks.setdefault(cur, "")
        elif cur:
            blocks[cur] += piece
    if set(blocks) != {"rural", "urban", "rural + urban"}:
        raise ValueError(f"{where}: sector blocks found {sorted(blocks)}")
    pid = ctx.prov(raw=raw, table_id="Statement 2.3", locator=f"PDF pages {P_S23[0]}-{P_S23[1]} (report pages 13-14), "
                   "Statement 2.3, blocks rural / urban / rural + urban, cols male, female, person",
                   unit_as_published="Rs. per student (current academic year)", conversion="none",
                   price_basis="current", vintage=E595_VINTAGE, release=E595_RELEASE, notes=E595_NOTE)
    rows = []
    for sec, hg in (("rural", "rural_all"), ("urban", "urban_all"), ("rural + urban", "all")):
        for lab, lvl in E595_LEVELS:
            v = _line(blocks[sec], lab, 3, f"{where} {sec}")
            for sex, val in zip(("male", "female", "person"), v, strict=True):
                rows.append({"source_id": src, "vintage": E595_VINTAGE, "estimate_stage": "n.a.", "status": "official",
                             "stock_flow": "flow", "unit": "INR", "period": "2025-Q2", "period_type": "cq",
                             "price_basis": "current", "geography": "IN",
                             "series_id": f"s2_3.exp_per_student.{lvl}.{sex}.{hg}", "table_id": "Statement 2.3",
                             "item_code": f"exp_per_student_{lvl}",
                             "item_label": f"Average expenditure (Rs.) per student on school education: {lab}",
                             "household_group": hg, "dim_other": f"ref_period=current_academic_year;sex={sex}",
                             "value": val, "prov_id": pid})
    return Dataset(f"{UNIT}_cms_education_2025", pl.DataFrame(rows),
                   "NSS Report 595 (CMS Education, Apr-Jun 2025) Statement 2.3: average expenditure per student on "
                   "school education by level, sex and sector. Values are spending over the CURRENT ACADEMIC YEAR "
                   "(ref_period in dim_other); period 2025-Q2 is only the survey quarter, not a quarterly flow")
