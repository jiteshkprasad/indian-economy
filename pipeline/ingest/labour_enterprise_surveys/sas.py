"""NSS 77th round, Report 587: Situation Assessment of Agricultural Households (SAS) 2019.

Agricultural year July 2018-June 2019: `sy` period '2018-07/2019-06' for every statement, the window
printed in each statement's title. Rural India, agricultural households only. Statements ingested:
- 1.1: estimated number of agricultural / non-agricultural / rural households (millions);
- 1.3 (social group: all): % distribution of households by size class of land possessed. The title
  prints "for the agricultural year July 2018 - June 2019"; the land classes are based on land
  possessed during July-December 2018 (visit 1; the table's footnote), which the provenance note says;
- 5.1A / 5.1B: average monthly income per agricultural household by source and size class of land
  possessed (net receipts with paid-out expenses only / with paid-out plus imputed expenses);
- 5.7: outstanding loans per agricultural household and incidence of indebtedness by size class.
"""

from __future__ import annotations

import re
from typing import Any

from pipeline.core.unit import BuildContext, Dataset

from ._pdf import NUM, Pdf, ShapeError, expect_text, frame, numbers

SRC = "mospi_sas_2019"
RAW = "sas_2019_report_587.pdf"
VINTAGE = "2021-09-10"  # Report 587 release (NSO press note / PIB, 10 Sep 2021)
RELEASE = "NSS Report No. 587: Situation Assessment of Agricultural Households and Land and Livestock Holdings of Households in Rural India, 2019 (NSO; 10 Sep 2021)"
PERIOD = "2018-19"

LAND = {  # printed size class of land possessed (ha.) -> household_group code
    "< 0.01": "agri_land_lt0.01",
    "0.01 - 0.40": "agri_land_0.01-0.40",
    "0.40 - 1.00": "agri_land_0.41-1.00",
    "1.01 - 2.00": "agri_land_1.01-2.00",
    "2.01 - 4.00": "agri_land_2.01-4.00",
    "4.01 - 10.00": "agri_land_4.01-10.00",
    "10.00 +": "agri_land_gt10.00",
    "all sizes": "agri_all",
}
INCOME_COLS = (
    ("wages", "income from wages"),
    ("leasing_out_land", "income from leasing out of land"),
    ("crop_production_net", "net receipt from crop production"),
    ("farming_animals_net", "net receipt from farming of animals"),
    ("nonfarm_business_net", "net receipt from non-farm business"),
    ("total", "total income"),
)


def _row(
    *,
    sid,
    table,
    item,
    label,
    hh,
    value,
    unit,
    prov,
    stock_flow="flow",
    price_basis="current",
    dims=None,
    window="jul_jun",
) -> dict[str, Any]:
    # survey_year is the internal window marker that _pdf.frame() turns into an `sy` period
    d = {"survey_year": window, **(dims or {})}
    return {
        "series_id": sid,
        "source_id": SRC,
        "table_id": table,
        "item_code": item,
        "item_label": label,
        "geography": "IN",
        "household_group": hh,
        "dim_other": ";".join(f"{k}={d[k]}" for k in sorted(d)),
        "stock_flow": stock_flow,
        "period": PERIOD,
        "period_type": "fy",
        "value": value,
        "unit": unit,
        "price_basis": price_basis,
        "vintage": VINTAGE,
        "estimate_stage": "n.a.",
        "status": "official",
        "prov_id": prov,
    }


def _land_rows(lines: list[str], start: int, n: int, where: str) -> dict[str, list[float | None]]:
    """The 8 size-class rows after line `start`, each ending in n numbers."""
    out: dict[str, list[float | None]] = {}
    for ln in lines[start:]:
        for lbl, code in LAND.items():
            m = re.fullmatch(rf"{re.escape(lbl)}((?: {NUM}){{{n}}})", ln)
            if m and code not in out:
                out[code] = numbers(m.group(1).split(), n, f"{where} {lbl}")
        if len(out) == len(LAND):
            return out
    raise ShapeError(f"{where}: size-class rows missing: {sorted(set(LAND.values()) - set(out))}")


def _statement_lines(pdf: Pdf, title: str, near: int) -> tuple[int, list[str], int]:
    (page,) = pdf.find_pages(title, near, window=4, count=1)
    lines = pdf.lines(page)
    head = title.split(":")[0] + ":"
    idx = [i for i, ln in enumerate(lines) if ln.replace(" ", "").startswith(head.replace(" ", ""))]
    if len(idx) != 1:
        raise ShapeError(f"SAS p.{page}: {head} found {len(idx)} times")
    return page, lines, idx[0]


def build(ctx: BuildContext, unit: str) -> list[Dataset]:
    raw = ctx.raw(SRC, RAW)
    pdf = Pdf(raw.path)
    rows: list[dict[str, Any]] = []
    try:
        # Statement 1.1
        page, lines, i = _statement_lines(
            pdf, "Statement 1.1: Estimates and percentage of agricultural households and non-", 75
        )
        body = " ".join(lines[i : i + 12])
        m = re.search(rf"Estimated number ({NUM}) ({NUM}) ({NUM}) \(in Millions\)", body)
        if not m:
            raise ShapeError(f"SAS Statement 1.1 p.{page}: 'Estimated number ... (in Millions)' row not found")
        pid = ctx.prov(
            raw=raw,
            table_id="Statement 1.1",
            locator=f"p.{page} (printed p.45), row 'Estimated number (in Millions)', cols (2)-(4)",
            unit_as_published="million households",
            conversion="x 1,000,000 (million -> count)",
            price_basis="n/a",
            vintage=VINTAGE,
            release=RELEASE,
            notes="Design-based estimates from visit-1 data; agricultural year July 2018-June 2019.",
        )
        for (hh, lbl), v in zip(
            (
                ("agri_all", "agricultural households"),
                ("rural_nonagri_all", "non-agricultural households"),
                ("rural_all", "rural households"),
            ),
            (m.group(1), m.group(2), m.group(3)),
            strict=True,
        ):
            rows.append(
                _row(
                    sid=f"s1_1.households.{hh}",
                    table="Statement 1.1",
                    item="households",
                    label=f"Estimated number of {lbl} (rural)",
                    hh=hh,
                    value=round(float(v) * 1e6, 6),
                    unit="count",
                    prov=pid,
                    stock_flow="stock",
                    price_basis="n/a",
                )
            )
        # Statement 1.3 (social group: all), agricultural households column
        pages13 = pdf.find_pages(
            "Statement 1.3: Percentage distribution of agricultural and non-agricultural households by size",
            76,
            window=4,
            count=2,
        )
        page = pages13[1]
        lines = pdf.lines(page)
        k = lines.index("Social Group: all")
        dist = _land_rows(lines, k + 1, 3, "SAS Statement 1.3 (all)")
        pid = ctx.prov(
            raw=raw,
            table_id="Statement 1.3",
            locator=f"p.{page} (printed p.47), block 'Social Group: all', col (2) agricultural households",
            unit_as_published="per cent",
            price_basis="n/a",
            vintage=VINTAGE,
            release=RELEASE,
            notes=(
                "Title: 'for the agricultural year July 2018 - June 2019' (the `sy` period). Footnote: 'Based on the "
                "land possessed by the household during July-December 2018', i.e. the size class of land possessed "
                "is measured from visit-1 data (para 3.1.2.2), as are the Statement 1.1 household counts. "
                "The class printed '0.40 - 1.00' is 0.41-1.00 ha."
            ),
        )
        for hh, vals in dist.items():
            assert vals[0] is not None
            rows.append(
                _row(
                    sid=f"s1_3.hh_share.{hh}",
                    table="Statement 1.3",
                    item="agri_hh_share_by_land_class",
                    label="Percentage distribution of agricultural households by size class of land possessed",
                    hh=hh,
                    value=vals[0],
                    unit="percent",
                    prov=pid,
                    stock_flow="n/a",
                    price_basis="n/a",
                )
            )
        # Statements 5.1A / 5.1B
        for st, near, basis, note in (
            ("5.1A", 114, "paid_out", "net receipts after out-of-pocket (paid-out) expenses only"),
            ("5.1B", 116, "paid_out_imputed", "net receipts after paid-out and imputed expenses"),
        ):
            page, lines, i = _statement_lines(
                pdf, f"Statement {st}: Average monthly income (Rs.) from different sources per agricultural", near
            )
            expect_text(pdf, page, "(1) (2) (3) (4) (5) (6) (7)")
            inc = _land_rows(lines, i, 6, f"SAS Statement {st}")
            pid = ctx.prov(
                raw=raw,
                table_id=f"Statement {st}",
                locator=f"p.{page} (printed p.{near - 30}), rows size class of land possessed, cols (2)-(7)",
                unit_as_published="Rs per month per agricultural household",
                price_basis="current",
                vintage=VINTAGE,
                release=RELEASE,
                notes=f"Agricultural year July 2018-June 2019; {note}. Excludes pensions, remittances and other non-economic receipts (para 3.5.1.4).",
            )
            for hh, vals in inc.items():
                for (code, lbl), v in zip(INCOME_COLS, vals, strict=True):
                    assert v is not None
                    rows.append(
                        _row(
                            sid=f"s{st.lower().replace('.', '_')}.income_{code}.{hh}.current",
                            table=f"Statement {st}",
                            item=f"income_{code}",
                            label=f"Average monthly {lbl} per agricultural household",
                            hh=hh,
                            value=v,
                            unit="INR",
                            prov=pid,
                            dims={"net_receipt_basis": basis},
                        )
                    )
        # Statement 5.7: outstanding loans
        page, lines, i = _statement_lines(
            pdf, "Statement 5.7: Percentage of indebted agricultural households and average amount (Rs.) of", 123
        )
        debt = _land_rows(lines, i, 3, "SAS Statement 5.7")
        pids = {
            "INR": ctx.prov(
                raw=raw,
                table_id="Statement 5.7",
                locator=f"p.{page} (printed p.93), col (2)",
                unit_as_published="Rs per agricultural household",
                price_basis="current",
                vintage=VINTAGE,
                release=RELEASE,
                notes="Outstanding loans per agricultural household (all agricultural households, indebted or not).",
            ),
            "percent": ctx.prov(
                raw=raw,
                table_id="Statement 5.7",
                locator=f"p.{page} (printed p.93), cols (3)-(4)",
                unit_as_published="per cent",
                price_basis="n/a",
                vintage=VINTAGE,
                release=RELEASE,
            ),
        }
        for hh, (amt, inc_pct, dist_pct) in debt.items():
            assert amt is not None and inc_pct is not None and dist_pct is not None
            rows.append(
                _row(
                    sid=f"s5_7.outstanding_loan_per_hh.{hh}.current",
                    table="Statement 5.7",
                    item="outstanding_loan_per_hh",
                    label="Average amount of outstanding loan per agricultural household",
                    hh=hh,
                    value=amt,
                    unit="INR",
                    prov=pids["INR"],
                    stock_flow="stock",
                )
            )
            rows.append(
                _row(
                    sid=f"s5_7.pct_indebted.{hh}",
                    table="Statement 5.7",
                    item="pct_indebted",
                    label="Percentage of indebted agricultural households",
                    hh=hh,
                    value=inc_pct,
                    unit="percent",
                    prov=pids["percent"],
                    stock_flow="n/a",
                    price_basis="n/a",
                )
            )
            rows.append(
                _row(
                    sid=f"s5_7.indebted_share.{hh}",
                    table="Statement 5.7",
                    item="indebted_hh_share",
                    label="Percentage distribution of indebted agricultural households",
                    hh=hh,
                    value=dist_pct,
                    unit="percent",
                    prov=pids["percent"],
                    stock_flow="n/a",
                    price_basis="n/a",
                )
            )
    finally:
        pdf.close()
    return [
        Dataset(
            f"{unit}_sas_2019_income_by_landclass",
            frame(rows),
            "SAS 2019 (Jul 2018-Jun 2019): agricultural households, income by source and land class, loans, household counts",
        )
    ]
