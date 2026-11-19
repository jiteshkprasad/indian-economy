"""NSS 77th round AIDIS 2019 (Report 588): the press note of 10 Sep 2021 only.

The quintile-level report tables (assets and debt by expenditure quintile) come from the eSankhyiki
NSS-77 AIDIS API instead (esankhyiki.py, dataset aidis_2019_quintile); the Report 588 PDF was not
located on the MoSPI site. This dataset holds the press note's rural/urban x household-type figures. The press note is prose, so each figure
is read with a sentence-level pattern that must match exactly once.

Periods: stocks (assets, debt, incidence) are as on 30.06.2018 (`date`); fixed capital
expenditure is for 01.07.2018-30.06.2019 (`sy` '2018-07/2019-06'); bank-account
coverage refers to the survey year January-December 2019 (`cy`).
"""

from __future__ import annotations

import re
from typing import Any

from pipeline.core.unit import BuildContext, Dataset
from pipeline.core.units import parse_number

from ._pdf import Pdf, ShapeError, frame

SRC = "mospi_aidis_2019"
RAW = "aidis_2019_press_note.pdf"
VINTAGE = "2021-09-10"  # date printed on the press note, p.2
RELEASE = "Press Note on NSS Report No. 588: All India Debt & Investment Survey 2019 (NSO, MoSPI; 10 Sep 2021)"
N = r"([\d,]+(?:\.\d+)?)"
STOCK_DATE = "2018-06-30"

# (pattern, [(item, sector, hh_type, unit, period kind)...]) -- one capture group per target, in order.
# hh_type: all | cultivator | non_cultivator (rural) | self_employed | other (urban).
P: list[tuple[str, list[tuple[str, str, str, str, str]]]] = [
    (
        rf"About {N}% of the households in Rural India \({N}% cultivator households and {N}% non-cultivator households\) reported owning any asset",
        [("pct_hh_owning_any_asset", "rural", h, "percent", "date") for h in ("all", "cultivator", "non_cultivator")],
    ),
    (
        rf"About {N}% of the households in Urban India \({N}% self-employed households and {N}% other households\) reported owning any asset",
        [("pct_hh_owning_any_asset", "urban", h, "percent", "date") for h in ("all", "self_employed", "other")],
    ),
    (
        rf"In Rural India, {N}% households owned physical assets & {N}% households owned financial assets",
        [
            ("pct_hh_owning_physical_asset", "rural", "all", "percent", "date"),
            ("pct_hh_owning_financial_asset", "rural", "all", "percent", "date"),
        ],
    ),
    (
        rf"In Urban India, {N}% households owned physical assets & {N}% households owned financial assets",
        [
            ("pct_hh_owning_physical_asset", "urban", "all", "percent", "date"),
            ("pct_hh_owning_financial_asset", "urban", "all", "percent", "date"),
        ],
    ),
    (
        rf"Average value of asset per household was Rs\. {N} in Rural India \(Rs\. {N} for cultivator households, Rs\. {N} for non-cultivator households\)",
        [("ava_per_hh", "rural", h, "INR", "date") for h in ("all", "cultivator", "non_cultivator")],
    ),
    (
        rf"Average value of asset per household was Rs\. {N} in Urban India \(Rs\. {N} for self-employed households, Rs\. {N} for other households\)",
        [("ava_per_hh", "urban", h, "INR", "date") for h in ("all", "self_employed", "other")],
    ),
    (
        rf"Average value of physical asset per household was Rs\. {N} and average value for financial asset was Rs\. {N} in Rural India",
        [
            ("ava_physical_per_hh", "rural", "all", "INR", "date"),
            ("ava_financial_per_hh", "rural", "all", "INR", "date"),
        ],
    ),
    (
        rf"Average value of physical asset per household was Rs\. {N} and Average value of financial asset per household was Rs\. {N} in Urban India",
        [
            ("ava_physical_per_hh", "urban", "all", "INR", "date"),
            ("ava_financial_per_hh", "urban", "all", "INR", "date"),
        ],
    ),
    (
        rf"in Rural India, jointly holding {N}% share in the total value of asset, with land having {N}% share and buildings {N}% share followed by deposits \({N}%\) and other assets \({N}%\)",
        [
            (f"asset_share_{a}", "rural", "all", "percent", "date")
            for a in ("land_building", "land", "building", "deposits", "other")
        ],
    ),
    (
        rf"Share of land in total value of assets is around {N}% in Urban India followed by building \({N} ?%\), deposits \({N}%\) and other assets \({N}%\)",
        [(f"asset_share_{a}", "urban", "all", "percent", "date") for a in ("land", "building", "deposits", "other")],
    ),
    (
        rf"Incidence of Indebtedness was about {N}% in Rural India \({N}% cultivator households, {N}% non-cultivator households\) compared to {N}% in Urban India \({N}% self-employed households, {N}% other households\)",
        [("incidence_of_indebtedness", "rural", h, "percent", "date") for h in ("all", "cultivator", "non_cultivator")]
        + [("incidence_of_indebtedness", "urban", h, "percent", "date") for h in ("all", "self_employed", "other")],
    ),
    (
        rf"In Rural India, ?{N}% households were indebted to institutional credit agencies only \({N}% cultivator households, {N}% non-cultivator households\) against {N}% households in Urban India \({N}% self-employed households, {N}% other households\)",
        [
            ("pct_hh_indebted_institutional_only", "rural", h, "percent", "date")
            for h in ("all", "cultivator", "non_cultivator")
        ]
        + [
            ("pct_hh_indebted_institutional_only", "urban", h, "percent", "date")
            for h in ("all", "self_employed", "other")
        ],
    ),
    (
        rf"About {N}% of the households were indebted to non-institutional credit agencies only in Rural India \({N}% cultivator households, {N}% non-cultivator households\) compared to {N}% households in Urban India \({N}% self-employed households, {N}% other households\)",
        [
            ("pct_hh_indebted_noninstitutional_only", "rural", h, "percent", "date")
            for h in ("all", "cultivator", "non_cultivator")
        ]
        + [
            ("pct_hh_indebted_noninstitutional_only", "urban", h, "percent", "date")
            for h in ("all", "self_employed", "other")
        ],
    ),
    (
        rf"About {N}% of the households were indebted to both institutional credit agencies & non-institutional credit agencies in Rural India \({N}% cultivator households, {N}% non-cultivator households\) against {N}% households in Urban India \({N}% self-employed households, {N}% other households\)",
        [("pct_hh_indebted_both", "rural", h, "percent", "date") for h in ("all", "cultivator", "non_cultivator")]
        + [("pct_hh_indebted_both", "urban", h, "percent", "date") for h in ("all", "self_employed", "other")],
    ),
    (
        rf"Average amount of debt was Rs\. {N} among rural households \(Rs\. {N} for cultivator households, Rs\. {N} for non-cultivator households\)",
        [("aod_per_hh", "rural", h, "INR", "date") for h in ("all", "cultivator", "non_cultivator")],
    ),
    (
        rf"Average amount of debt was Rs\. {N} among urban households \(Rs\. {N} for self-employed households, Rs\. {N} for other households\)",
        [("aod_per_hh", "urban", h, "INR", "date") for h in ("all", "self_employed", "other")],
    ),
    (
        rf"In Rural India, the share of outstanding cash debt from institutional credit agencies was {N}% against {N}% from non-institutional credit agencies\. In Urban India, the share of outstanding cash debt from institutional credit agencies was {N}% compared to {N}% from non-institutional credit agencies",
        [
            ("debt_share_institutional", "rural", "all", "percent", "date"),
            ("debt_share_noninstitutional", "rural", "all", "percent", "date"),
            ("debt_share_institutional", "urban", "all", "percent", "date"),
            ("debt_share_noninstitutional", "urban", "all", "percent", "date"),
        ],
    ),
    (
        rf"Average amount of debt was Rs\. {N} among indebted households in Rural India \(Rs\. {N} for cultivator households, Rs\. {N} for non-cultivator households\)",
        [("aod_per_indebted_hh", "rural", h, "INR", "date") for h in ("all", "cultivator", "non_cultivator")],
    ),
    (
        rf"Average amount of debt was Rs\. {N} among indebted households in Urban India \(Rs\. {N} for self-employed households, Rs\. {N} for other households\)",
        [("aod_per_indebted_hh", "urban", h, "INR", "date") for h in ("all", "self_employed", "other")],
    ),
    (
        rf"About {N}% of the rural households reported incurring expenditure towards formation of fixed capital \({N}% cultivator households, {N}% non-cultivator households\)",
        [("pct_hh_reporting_fce", "rural", h, "percent", "fy") for h in ("all", "cultivator", "non_cultivator")],
    ),
    (
        rf"About {N}% of the urban households reported incurring expenditure towards formation of fixed capital \({N}% self-employed households, {N}% other households\)",
        [("pct_hh_reporting_fce", "urban", h, "percent", "fy") for h in ("all", "self_employed", "other")],
    ),
    (
        rf"The average fixed capital expenditure incurred per household was Rs\. {N} in Rural India \(Rs\. {N} for cultivator households, Rs\. {N} for non-cultivator households\)",
        [("fce_per_hh", "rural", h, "INR", "fy") for h in ("all", "cultivator", "non_cultivator")],
    ),
    (
        rf"The average fixed capital expenditure incurred per household was Rs\. {N} in Urban India \(Rs\. {N} for self-employed households, Rs\. {N} for other households\)",
        [("fce_per_hh", "urban", h, "INR", "fy") for h in ("all", "self_employed", "other")],
    ),
    (
        rf"About {N} ?% of the population of age 18 years and above had deposit account in Banks in Rural India \({N}% male and {N}% female\)",
        [("pct_adults_with_bank_deposit_account", "rural", s, "percent", "cy") for s in ("all", "male", "female")],
    ),
    (
        rf"About {N} ?% of the population of age 18 years and above had deposit account in Banks in Urban India \({N}% male and {N}% female\)",
        [("pct_adults_with_bank_deposit_account", "urban", s, "percent", "cy") for s in ("all", "male", "female")],
    ),
]
LABELS = {
    "pct_hh_owning_any_asset": "Percentage of households owning any asset (physical or financial)",
    "pct_hh_owning_physical_asset": "Percentage of households owning physical assets",
    "pct_hh_owning_financial_asset": "Percentage of households owning financial assets",
    "ava_per_hh": "Average value of assets (physical and financial) per household",
    "ava_physical_per_hh": "Average value of physical assets per household",
    "ava_financial_per_hh": "Average value of financial assets per household",
    "asset_share_land_building": "Share of land and building in total value of assets",
    "asset_share_land": "Share of land in total value of assets",
    "asset_share_building": "Share of buildings in total value of assets",
    "asset_share_deposits": "Share of deposits in total value of assets",
    "asset_share_other": "Share of other assets (livestock, transport, machinery, business equipment, shares) in total value of assets",
    "incidence_of_indebtedness": "Incidence of indebtedness (percentage of indebted households)",
    "pct_hh_indebted_institutional_only": "Percentage of households indebted to institutional credit agencies only",
    "pct_hh_indebted_noninstitutional_only": "Percentage of households indebted to non-institutional credit agencies only",
    "pct_hh_indebted_both": "Percentage of households indebted to both institutional and non-institutional agencies",
    "aod_per_hh": "Average amount of cash debt per household",
    "debt_share_institutional": "Share of outstanding cash debt from institutional credit agencies",
    "debt_share_noninstitutional": "Share of outstanding cash debt from non-institutional credit agencies",
    "aod_per_indebted_hh": "Average amount of debt per indebted household",
    "pct_hh_reporting_fce": "Percentage of households reporting fixed capital expenditure",
    "fce_per_hh": "Average fixed capital expenditure per household (01.07.2018-30.06.2019)",
    "pct_adults_with_bank_deposit_account": "Percentage of persons aged 18+ with a deposit account in banks",
}


def build(ctx: BuildContext, unit: str) -> list[Dataset]:
    raw = ctx.raw(SRC, RAW)
    pdf = Pdf(raw.path)
    try:
        text = " ".join(" ".join(pdf.lines(p)) for p in range(2, pdf.n_pages + 1))
    finally:
        pdf.close()
    text = re.sub(r"\d+ \| Page", " ", text)  # page footers inside sentences
    text = re.sub(r"\s+", " ", text)
    if "10 September, 2021" not in text:
        raise ShapeError("AIDIS press note: date '10 September, 2021' not found")
    pids: dict[tuple[str, tuple[str, ...]], str] = {}

    base_note = "Assets/debt as on 30.06.2018; fixed capital expenditure 01.07.2018-30.06.2019; survey Jan-Dec 2019. Rural/urban x household type only; the expenditure-quintile tables of Report 588 are in the dataset aidis_2019_quintile (from the eSankhyiki NSS-77 API)."

    def prov(unit_pub: str, pb: str, whole: tuple[str, ...] = ()) -> str:
        key = (unit_pub, whole)
        if key not in pids:
            notes = base_note
            if whole:
                notes += (
                    " ROUNDED: these values are printed in the prose as whole-number percentages (precision is assured"
                    " only to +-0.5 percentage point; a printed 18 may be 18.0 or a rounded 17.6; those marked * are introduced by 'about' or 'around'), while"
                    " most other press-note percentages carry one decimal: " + ", ".join(whole) + "."
                )
            pids[key] = ctx.prov(
                raw=raw,
                table_id="Press note, sections A-D",
                locator="pp.3-6, sentences under 'A. Asset Holdings', 'B. Household Indebtedness', 'C. Capital Expenditure', 'D. Deposit accounts in Bank'",
                unit_as_published=unit_pub,
                price_basis=pb,
                vintage=VINTAGE,
                release=RELEASE,
                notes=notes,
            )
        return pids[key]

    rows: list[dict[str, Any]] = []
    for pat, targets in P:
        found = re.findall(pat, text)
        if len(found) != 1:
            raise ShapeError(f"AIDIS press note: pattern matched {len(found)} times: {pat[:80]!r}")
        vals = found[0] if isinstance(found[0], tuple) else (found[0],)
        if len(vals) != len(targets):
            raise ShapeError(f"AIDIS press note: {len(vals)} values for {len(targets)} targets")
        # the text just before each captured number, to spot figures introduced by 'about'/'around'
        lead = [part[-8:].lower() for part in pat.split(N)[:-1]]
        for v, lead_txt, (item, sector, who, unit_, kind) in zip(vals, lead, targets, strict=True):
            x = parse_number(v)
            assert x is not None
            period, ptype = {"date": (STOCK_DATE, "date"), "fy": ("2018-19", "fy"), "cy": ("2019", "cy")}[kind]
            dims = {"hh_type": who} if item != "pct_adults_with_bank_deposit_account" else {"sex": who}
            if kind == "fy":
                dims["survey_year"] = "jul_jun"
            pb = "current" if unit_ == "INR" else "n/a"
            rows.append(
                {
                    "series_id": f"pn.{item}.{sector}.{who}" + (".current" if pb == "current" else ""),
                    "source_id": SRC,
                    "table_id": "Press note",
                    "item_code": item,
                    "item_label": LABELS[item],
                    "geography": "IN",
                    "household_group": sector,
                    "dim_other": ";".join(f"{k}={dims[k]}" for k in sorted(dims)),
                    "stock_flow": "stock"
                    if (unit_ == "INR" and kind == "date")
                    else ("flow" if unit_ == "INR" else "n/a"),
                    "period": period,
                    "period_type": ptype,
                    "value": x,
                    "unit": unit_,
                    "price_basis": pb,
                    "vintage": VINTAGE,
                    "estimate_stage": "n.a.",
                    "status": "official",
                    "prov_id": None,  # assigned below, once the whole-number items are known
                    "_unit_pub": "Rs per household" if unit_ == "INR" else "per cent",
                    "_whole": unit_ == "percent" and "." not in v,
                    "_about": bool(re.search(r"(about|around) ?$", lead_txt)),
                }
            )
    whole = tuple(sorted(r["series_id"] + ("*" if r["_about"] else "") for r in rows if r["_whole"]))
    for r in rows:
        r["prov_id"] = prov(r.pop("_unit_pub"), r["price_basis"], whole if r.pop("_whole") else ())
        r.pop("_about")
    return [
        Dataset(
            f"{unit}_aidis_2019_press_note",
            frame(rows),
            "AIDIS 2019 press note: assets, debt, capital expenditure, bank accounts by rural/urban x household type",
        )
    ]
