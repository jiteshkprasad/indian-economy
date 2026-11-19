"""ASI 2023-24 (factory sector, FY April 2023-March 2024; NSO, publications of 30 Sep 2025).

ASI reference years are fiscal years, so periods are plain `fy`. Latest available: ASI 2024-25
results were due on 29 Sep 2026 but had not appeared in the MoSPI release feed when this unit was
built (checked 29 Sep 2026). The keyless ASI API (api.mospi.gov.in, reachable since D1-6) serves
the same aggregates, so the published PDFs (with their printed captions) stay the source.

- Summary Results Statement 3A: principal characteristics, all-India, 2019-20..2023-24 (Rs lakh).
- Summary Results Statement 5A: principal characteristics by NIC-2008 2-digit division, 2023-24.
- Volume I Table 3: persons engaged by type, mandays and wages/emoluments by type, NIC-2008
  4-digit class, all-India, 2023-24.
Volume I Table 2b (2-digit, all-India) is not ingested: its pages print no unit caption (values
match Statement 5A / 100, i.e. Rs crore, but that is inference), and 5A carries the same items.
"""

from __future__ import annotations

import re
from typing import Any

from pipeline.core.unit import BuildContext, Dataset
from pipeline.core.units import conversion_note, to_inr_crore

from ._pdf import NUM, Pdf, ShapeError, expect_text, frame, numbers

SRC = "mospi_asi"
RAW_SUM = "asi_2023_24_summary_results.pdf"
RAW_V1 = "asi_2023_24_vol_i.pdf"
VINTAGE = "2025-09-30"
RELEASE = "Annual Survey of Industries 2023-24, Summary Results and Volume I (NSO, MoSPI; 30 Sep 2025)"
LAKH = "INR_lakh"


def _row(
    *,
    sid,
    table,
    item,
    label,
    period,
    value,
    unit,
    prov,
    industry="nic2008_all",
    stock_flow="flow",
    price_basis="current",
    dims=None,
) -> dict[str, Any]:
    return {
        "series_id": sid,
        "source_id": SRC,
        "table_id": table,
        "item_code": item,
        "item_label": label,
        "industry": industry,
        "institution": "asi_factory_sector",
        "geography": "IN",
        "dim_other": ";".join(f"{k}={v}" for k, v in sorted((dims or {}).items())) or None,
        "stock_flow": stock_flow,
        "period": period,
        "period_type": "fy",
        "value": value,
        "unit": unit,
        "price_basis": price_basis,
        "vintage": VINTAGE,
        "estimate_stage": "n.a.",
        "status": "official",
        "prov_id": prov,
    }


# Statement 3A: label -> (item code, kind) ; kind: count_stock | count | lakh_stock | lakh_flow
S3A = {
    "Factories in Operation": ("factories_in_operation", "count"),
    "Fixed Capital": ("fixed_capital", "lakh_stock"),
    "Invested Capital": ("invested_capital", "lakh_stock"),
    "Workers": ("workers", "count"),
    "Total Persons Engaged": ("persons_engaged", "count"),
    "Wages to Worker": ("wages_to_workers", "lakh_flow"),
    "Total Emoluments": ("total_emoluments", "lakh_flow"),
    "Input": ("total_input", "lakh_flow"),
    "Output": ("total_output", "lakh_flow"),
    "GVA": ("gva", "lakh_flow"),
    "Depreciation": ("depreciation", "lakh_flow"),
    "NVA": ("nva", "lakh_flow"),
    "Rent Paid for Fixed Assets": ("rent_paid", "lakh_flow"),
    "Interest Paid": ("interest_paid", "lakh_flow"),
    "Net Income": ("net_income", "lakh_flow"),
    "Net Profit": ("net_profit", "lakh_flow"),
}
YEARS_3A = ("2019-20", "2020-21", "2021-22", "2022-23", "2023-24")


def _statement3a(ctx: BuildContext, pdf: Pdf, raw: Any) -> list[dict[str, Any]]:
    (page,) = pdf.find_pages("Statement 3A: Value of Principal Characteristics", 34, window=4, count=1)
    expect_text(pdf, page, "Characteristics Unit ASI Year")
    expect_text(pdf, page, " ".join(YEARS_3A))
    pids = {
        "count": ctx.prov(
            raw=raw,
            table_id="Statement 3A",
            locator=f"p.{page} (printed S3-5), 'Number' rows, cols 2019-20..2023-24",
            unit_as_published="number",
            price_basis="n/a",
            vintage=VINTAGE,
            release=RELEASE,
        ),
        "lakh": ctx.prov(
            raw=raw,
            table_id="Statement 3A",
            locator=f"p.{page} (printed S3-5), '₹ Lakhs' rows, cols 2019-20..2023-24",
            unit_as_published="Rs lakh",
            conversion=conversion_note(LAKH),
            price_basis="current",
            vintage=VINTAGE,
            release=RELEASE,
        ),
    }
    lines = pdf.lines(page)
    i0 = next(i for i, ln in enumerate(lines) if ln.startswith("Statement 3A"))
    rows, seen = [], set()
    for ln in lines[i0 + 1 :]:
        if ln.startswith("Statement 3B"):
            break
        m = re.match(rf"^(.+?) (Number|₹ Lakhs)((?: {NUM}){{5}})$", ln)
        if not m:
            continue
        label = m.group(1)
        if label not in S3A:
            raise ShapeError(f"ASI Statement 3A: unmapped row {label!r}")
        item, kind = S3A[label]
        if (m.group(2) == "Number") != (kind == "count"):
            raise ShapeError(f"ASI Statement 3A: unit of {label!r} is {m.group(2)!r}")
        seen.add(label)
        for period, v in zip(YEARS_3A, numbers(m.group(3).split(), 5, f"3A {label}"), strict=True):
            assert v is not None
            if kind == "count":
                rows.append(
                    _row(
                        sid=f"s3a.{item}",
                        table="Statement 3A",
                        item=item,
                        label=label,
                        period=period,
                        value=v,
                        unit="count",
                        prov=pids["count"],
                        stock_flow="stock",
                        price_basis="n/a",
                    )
                )
            else:
                rows.append(
                    _row(
                        sid=f"s3a.{item}.current",
                        table="Statement 3A",
                        item=item,
                        label=label,
                        period=period,
                        value=to_inr_crore(v, LAKH),
                        unit="INR_crore",
                        prov=pids["lakh"],
                        stock_flow="stock" if kind == "lakh_stock" else "flow",
                    )
                )
    if seen != set(S3A):
        raise ShapeError(f"ASI Statement 3A: missing rows {sorted(set(S3A) - seen)}")
    return rows


S5A_COLS = (  # (item, kind) for the 11 numeric columns
    ("factories_in_operation", "count"),
    ("fixed_capital", "lakh_stock"),
    ("working_capital", "lakh_stock"),
    ("invested_capital", "lakh_stock"),
    ("gross_value_plant_machinery", "lakh_stock"),
    ("persons_engaged", "count"),
    ("total_input", "lakh_flow"),
    ("total_output", "lakh_flow"),
    ("gva", "lakh_flow"),
    ("nva", "lakh_flow"),
    ("gva_share", "pct"),
)
S5A_LABEL = {
    "factories_in_operation": "No. of operating factories",
    "fixed_capital": "Fixed capital",
    "working_capital": "Working capital",
    "invested_capital": "Invested capital",
    "gross_value_plant_machinery": "Gross value of plant and machinery",
    "persons_engaged": "Total persons engaged",
    "total_input": "Total input",
    "total_output": "Total output",
    "gva": "GVA",
    "nva": "NVA",
    "gva_share": "% share in aggregate GVA",
}


def _statement5a(ctx: BuildContext, pdf: Pdf, raw: Any) -> list[dict[str, Any]]:
    (page,) = pdf.find_pages(
        "Statement 5A: Estimate of Some Principal Characteristics by 2-digit Level of NIC", 39, window=4, count=1
    )
    expect_text(pdf, page, "(₹ Lakhs)")
    loc = f"p.{page} (printed S4-4), rows NIC-2008 2-digit division (arranged by GVA), cols 'No. of Operating Factories'..'% Share in Aggregate GVA'"
    pids = {
        "count": ctx.prov(
            raw=raw,
            table_id="Statement 5A",
            locator=loc + " (count columns)",
            unit_as_published="number",
            price_basis="n/a",
            vintage=VINTAGE,
            release=RELEASE,
        ),
        "lakh": ctx.prov(
            raw=raw,
            table_id="Statement 5A",
            locator=loc + " (₹ Lakhs columns)",
            unit_as_published="Rs lakh",
            conversion=conversion_note(LAKH),
            price_basis="current",
            vintage=VINTAGE,
            release=RELEASE,
        ),
        "pct": ctx.prov(
            raw=raw,
            table_id="Statement 5A",
            locator=loc + " (% share column)",
            unit_as_published="per cent",
            price_basis="n/a",
            vintage=VINTAGE,
            release=RELEASE,
        ),
    }
    rows, seen = [], set()
    for ln in pdf.lines(page):
        m = re.match(rf"^(\d\d|OT|All Industries)\b(.*?)((?: {NUM}){{11}})$", ln)
        if not m:
            continue
        code = {"All Industries": "all", "OT": "other"}.get(m.group(1), m.group(1))
        if code in seen:
            raise ShapeError(f"ASI Statement 5A: division {code} twice")
        seen.add(code)
        vals = numbers(m.group(3).split(), 11, f"5A {code}")
        for (item, kind), v in zip(S5A_COLS, vals, strict=True):
            assert v is not None
            base = dict(
                table="Statement 5A",
                item=item,
                label=f"{S5A_LABEL[item]}, NIC-2008 division {code}",
                period="2023-24",
                industry=f"nic2008_{code}",
            )
            if kind == "count":
                rows.append(
                    _row(
                        sid=f"s5a.{item}.{code}",
                        value=v,
                        unit="count",
                        prov=pids["count"],
                        stock_flow="stock",
                        price_basis="n/a",
                        **base,
                    )
                )
            elif kind == "pct":
                rows.append(
                    _row(
                        sid=f"s5a.{item}.{code}",
                        value=v,
                        unit="percent",
                        prov=pids["pct"],
                        stock_flow="n/a",
                        price_basis="n/a",
                        **base,
                    )
                )
            else:
                rows.append(
                    _row(
                        sid=f"s5a.{item}.{code}.current",
                        value=to_inr_crore(v, LAKH),
                        unit="INR_crore",
                        prov=pids["lakh"],
                        stock_flow="stock" if kind == "lakh_stock" else "flow",
                        **base,
                    )
                )
    if "all" not in seen or len(seen) < 30:
        raise ShapeError(f"ASI Statement 5A: only {len(seen)} rows parsed: {sorted(seen)}")
    return rows


# Volume I Table 3: rows in printed order -> (item code, label, kind)
T3_ROWS = (
    ("A. No. of Persons Engaged (no.)", "persons_engaged", "count"),
    ("1. Workers", "workers", "count"),
    ("1.1 Directly Employed", "workers_direct", "count"),
    ("Men", "workers_direct_men", "count"),
    ("Women", "workers_direct_women", "count"),
    ("1.2 Employed Through Contractors", "workers_contract", "count"),
    ("2. Employees Other Than Workers", "employees_other_than_workers", "count"),
    ("2.1 Supervisory and Managerial", "supervisory_managerial", "count"),
    ("2.2 Other Employees", "other_employees", "count"),
    ("3. Unpaid family members/proprietor etc", "unpaid_family_proprietor", "count"),
    ("B. Total Mandays Employed (in '000)", "mandays", "thousand"),
    ("Employers' Contribution ( lakhs)", "wages_salaries_incl_employer_contrib", "lakh"),
    ("1. Wages and Salary Including Bonus", "wages_salary_incl_bonus", "lakh"),
    ("1.1 Wages and Salary", "wages_salary", "lakh"),
    ("1.1.1 Workers", "wages_salary_workers", "lakh"),
    ("1.1.2 Supervisory & Managerial", "wages_salary_supervisory", "lakh"),
    ("1.1.3 Other Employees", "wages_salary_other_employees", "lakh"),
    ("1.2 Bonus to All Staff", "bonus", "lakh"),
    ("2. Employers' Contribution", "employers_contribution", "lakh"),
)
T3_DISPLAY = {
    "persons_engaged": "A. No. of Persons Engaged",
    "mandays": "B. Total Mandays Employed",
    "wages_salaries_incl_employer_contrib": "C. Wages and Salaries Including Employers' Contribution",
}
_T3_CODE = re.compile(r"^(All|Other|\d{4})$")


def _vol1_table3(ctx: BuildContext) -> list[dict[str, Any]]:
    raw = ctx.raw(SRC, RAW_V1)
    pdf = Pdf(raw.path)
    try:
        pages = pdf.find_pages(
            "Table 3: Estimate of (i) employment, (ii) mandays employed and (iii) emoluments paid in the factory sector by their type for each 4-digit industry class",
            327,
            window=10,
            count=15,
        )
        loc = f"pp.{pages[0]}-{pages[-1]} (printed T3-1..T3-15), rows in printed order, one column per NIC-2008 4-digit class ('All', 'Other')"
        pids = {
            "count": ctx.prov(
                raw=raw,
                table_id="Table 3",
                locator=loc + "; persons rows (no.)",
                unit_as_published="number",
                price_basis="n/a",
                vintage=VINTAGE,
                release=RELEASE,
            ),
            "thousand": ctx.prov(
                raw=raw,
                table_id="Table 3",
                locator=loc + "; row B mandays (in '000)",
                unit_as_published="thousand mandays",
                conversion="x 1,000 ('000 -> count)",
                price_basis="n/a",
                vintage=VINTAGE,
                release=RELEASE,
            ),
            "lakh": ctx.prov(
                raw=raw,
                table_id="Table 3",
                locator=loc + "; rows C (lakhs)",
                unit_as_published="Rs lakh",
                conversion=conversion_note(LAKH),
                price_basis="current",
                vintage=VINTAGE,
                release=RELEASE,
                notes="Row C.1 'Wages and Salary Including Bonus' is ASI 'total emoluments'; C = C.1 + employers' contribution.",
            ),
        }
        rows, codes_seen = [], set()
        for p in pages:
            lines = pdf.lines(p)
            ci = [i for i, ln in enumerate(lines) if ln == "Characteristics"]
            if len(ci) != 1:
                raise ShapeError(f"ASI Table 3 p.{p}: 'Characteristics' header not found once")
            codes = lines[ci[0] + 1].split(" ")
            if not all(_T3_CODE.match(c) for c in codes):
                raise ShapeError(f"ASI Table 3 p.{p}: bad code line {codes}")
            body = [ln for ln in lines[ci[0] + 2 :] if ln != "C. Wages and Salaries Including"]
            k = 0
            for label, item, kind in T3_ROWS:
                ln = body[k]
                k += 1
                if not ln.startswith(label + " "):
                    raise ShapeError(f"ASI Table 3 p.{p}: expected row {label!r}, found {ln!r}")
                vals = numbers(ln[len(label) + 1 :].split(" "), len(codes), f"ASI Table 3 p.{p} {label}")
                for code, v in zip(codes, vals, strict=True):
                    assert v is not None
                    ind = {"All": "all", "Other": "other"}.get(code, code)
                    base = dict(
                        table="Table 3 (Vol I)",
                        item=item,
                        label=f"{T3_DISPLAY.get(item, label)}, NIC-2008 class {ind}",
                        period="2023-24",
                        industry=f"nic2008_{ind}",
                    )
                    if kind == "count":
                        rows.append(
                            _row(
                                sid=f"v1t3.{item}.{ind}",
                                value=v,
                                unit="count",
                                prov=pids["count"],
                                stock_flow="stock",
                                price_basis="n/a",
                                **base,
                            )
                        )
                    elif kind == "thousand":
                        rows.append(
                            _row(
                                sid=f"v1t3.{item}.{ind}",
                                value=v * 1000,
                                unit="count",
                                prov=pids["thousand"],
                                stock_flow="flow",
                                price_basis="n/a",
                                **base,
                            )
                        )
                    else:
                        rows.append(
                            _row(
                                sid=f"v1t3.{item}.{ind}.current",
                                value=to_inr_crore(v, LAKH),
                                unit="INR_crore",
                                prov=pids["lakh"],
                                **base,
                            )
                        )
            for c in codes:
                if c in codes_seen:
                    raise ShapeError(f"ASI Table 3: class {c} printed twice")
                codes_seen.add(c)
        if "All" not in codes_seen or "Other" not in codes_seen:
            raise ShapeError("ASI Table 3: 'All' or 'Other' column missing")
    finally:
        pdf.close()
    return rows


def build(ctx: BuildContext, unit: str) -> list[Dataset]:
    raw = ctx.raw(SRC, RAW_SUM)
    pdf = Pdf(raw.path)
    try:
        hist = _statement3a(ctx, pdf, raw)
        ind = _statement5a(ctx, pdf, raw)
    finally:
        pdf.close()
    ind += _vol1_table3(ctx)
    return [
        Dataset(
            f"{unit}_asi_principal_characteristics",
            frame(hist),
            "ASI Summary Results Statement 3A: factory-sector principal characteristics, all-India, 2019-20..2023-24",
        ),
        Dataset(
            f"{unit}_asi_2324_industry",
            frame(ind),
            "ASI 2023-24 by industry: Statement 5A (NIC 2-digit) and Vol I Table 3 employment and emoluments (NIC 4-digit)",
        ),
    ]
