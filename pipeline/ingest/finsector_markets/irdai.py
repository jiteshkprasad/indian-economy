"""IRDAI Handbook on Indian Insurance Statistics 2024-25 (released 3 Feb 2026): parsers.

Read from the pinned zip (seven workbooks). Every table is matched by its title and by the exact
row labels in the published order; a relabelled or reshuffled table fails the build.
Growth-rate rows (printed under each value row, with unreliable signs: registry quirk) are never
read; share rows are skipped (they are arithmetic on the levels).
"""

from __future__ import annotations

from typing import Any

from pipeline.core.unit import BuildContext, Dataset
from pipeline.core.units import clean_label, conversion_note, to_inr_crore

from .common import Rows, cell_text, expect, frame, fy_end, fy_label, load_zip_member, num

SRC = "irdai_handbook_insurance"
RAW = "irdai_handbook_2024_25.zip"
VINTAGE = "2026-02-03"
RELEASE = "Handbook on Indian Insurance Statistics 2024-25 (IRDAI, listed 03-02-2026)"

# --------------------------------------------------------------------------------------------
# Summary sheets A (all insurers), B (life), C (general incl. health and reinsurers)
# --------------------------------------------------------------------------------------------
# (published label, item code, kind). kind: flow (FY), stock (as on 31 March), pct (FY ratio),
# skip (Swiss Re sigma figures marked '#', which are not IRDAI's own; and grievance counts).
F, S, P, X = "flow", "stock", "pct", "skip"
SUMMARY: dict[str, tuple[str, list[tuple[str, str, str]]]] = {
    "A": (
        "insurers_all",
        [
            ("Number of Companies (including Stand-alone Health Insurers & Reinsurers)", "companies", S),
            ("Number of Foreign Reinsurers' Branches", "foreign_reinsurer_branches", S),
            ("Number of Offices of Insurers", "offices", S),
            ("Insurance Penetration#", "penetration_swiss_re", X),
            ("Insurance Density#", "density_swiss_re", X),
            ("Number of New Policies Issued", "new_policies", F),
            ("Total Premium", "total_premium", F),
            ("Market Share of PSUs (including Specialized)", "psu_market_share", P),
            ("Commission expenses", "commission", F),
            ("Operating expenses", "operating_expenses", F),
            (
                "Claims (benefit paid of Life Insurers and net incurred claims (within India) of non-life insurers)",
                "claims_benefits",
                F,
            ),
            ("Assets Under Management (including Reinsurers & FRBs)", "aum", S),
            ("Profit after tax", "profit_after_tax", F),
            ("Paid-up Capital (including Reinsurers)", "paid_up_capital", S),
            ("Assigned Capital of Branches of Foreign Reinsurers", "frb_assigned_capital", S),
            ("No of grievances reported during the year", "grievances_reported", X),
            ("No. of grievances resolved during the year", "grievances_resolved", X),
            ("Resolution rate", "grievance_resolution_rate", X),
            ("No. of complaints reported with the Ombudsmen at different centres", "ombudsman_complaints", X),
            ("No. of Complaints disposed by Ombudsmen", "ombudsman_disposed", X),
            ("Disposal rate", "ombudsman_disposal_rate", X),
        ],
    ),
    "B": (
        "insurers_life",
        [
            ("Number of Companies", "companies", S),
            ("Number of Life Offices", "offices", S),
            ("Insurance Penetration#", "penetration_swiss_re", X),
            ("Insurance Density#", "density_swiss_re", X),
            ("Number of New Policies Issued", "new_policies", F),
            ("New Business Premium", "new_business_premium", F),
            ("Total Premium", "total_premium", F),
            ("Market share of LIC (based on Total Premium)", "lic_market_share", P),
            ("Individual Business in Force - Number of policies", "individual_in_force_policies", S),
            ("Individual Business in Force - Sum Assured", "individual_in_force_sum_assured", S),
            ("Number of Insurance Agents", "agents", S),
            ("Commission Expenses*", "commission", F),
            ("Operating Expenses", "operating_expenses", F),
            ("No. of claims submitted/intimated (Individual-death)", "death_claims_intimated_individual", F),
            ("No of claims submitted/intimated (Group-death)", "death_claims_intimated_group", F),
            ("Amount Claimed/intimated (Individual)", "death_claims_amount_individual", F),
            ("Amount Claimed/intimated (Group)", "death_claims_amount_group", F),
            ("Total Benefits Paid", "total_benefits_paid", F),
            *[
                (lab, f"nb_premium_channel.{code}", F)
                for lab, code in (
                    ("Individual agents", "individual_agents"),
                    ("Corporate agents-Banks", "corporate_agents_banks"),
                    ("Corporate agents-Others", "corporate_agents_others"),
                    ("Brokers", "brokers"),
                    ("Direct selling", "direct_selling"),
                    ("MI Agents", "mi_agents"),
                    ("Common Service Centres(CSCs)", "csc"),
                    ("Web-aggregators", "web_aggregators"),
                    ("IMF", "imf"),
                    ("On-line", "online"),
                    ("Point of sale", "point_of_sale"),
                    ("Others if any", "others"),
                    ("Total", "total"),
                    ("Referrals", "referrals"),
                )
            ],
            *[
                (lab, f"nb_lives_channel.{code}", F)
                for lab, code in (
                    ("Individual agents", "individual_agents"),
                    ("Corporate agents-Banks", "corporate_agents_banks"),
                    ("Corporate agents-Others", "corporate_agents_others"),
                    ("Brokers", "brokers"),
                    ("Direct selling", "direct_selling"),
                    ("MI Agents", "mi_agents"),
                    ("Common Service Centres(CSCs)", "csc"),
                    ("Web Aggregators", "web_aggregators"),
                    ("IMF", "imf"),
                    ("Online", "online"),
                    ("Point of sale", "point_of_sale"),
                    ("Others if any", "others"),
                    ("Total", "total"),
                    ("Referrals", "referrals"),
                )
            ],
            *[
                (lab, f"offices_region.{code}", S)
                for lab, code in (
                    ("Metro", "metro"),
                    ("Urban", "urban"),
                    ("Semi-urban", "semi_urban"),
                    ("Rural", "rural"),
                    ("Unclassified", "unclassified"),
                    ("Total", "total"),
                )
            ],
            ("Life Fund", "aum.life_fund", S),
            ("Pension & General Annuity & Group fund", "aum.pension_annuity_group_fund", S),
            ("Unit ULIP Fund", "aum.ulip_fund", S),
            ("Total Fund", "aum.total", S),
            ("Profit /Loss after tax", "profit_after_tax", F),
            ("No of companies made profit", "companies_profit", X),
            ("No of companies made loss", "companies_loss", X),
            ("Paid up Capital", "paid_up_capital", S),
            ("No. of grievances reported during the year", "grievances_reported", X),
            ("No. of grievances resolved during the year", "grievances_resolved", X),
            ("Resolution rate$", "grievance_resolution_rate", X),
            ("No. of complaints reported with the Ombudsmen at different centres", "ombudsman_complaints", X),
            ("No. of Complaints disposed by Ombudsmen", "ombudsman_disposed", X),
            ("Disposal rate$", "ombudsman_disposal_rate", X),
        ],
    ),
    "C": (
        "insurers_general",
        [
            ("Number of Companies (including Stand-alone Health Insurers & Reinsurers)", "companies", S),
            ("Number of Foreign Reinsurers' Branches", "foreign_reinsurer_branches", S),
            ("Number of Offices of Insurers", "offices", S),
            ("Insurance Penetration#", "penetration_swiss_re", X),
            ("Insurance Density#", "density_swiss_re", X),
            ("Number of New Policies Issued", "new_policies", F),
            ("Gross Direct Premium (Within & Outside India)", "gross_direct_premium", F),
            ("Market Share of PSUs (including Specialized) (Basis GDP within India)", "psu_market_share", P),
            *[
                (lab, f"gdp_segment.{code}", F)
                for lab, code in (
                    ("Fire", "fire"),
                    ("Marine", "marine"),
                    ("Motor", "motor"),
                    ("Health", "health"),
                    ("Others", "others"),
                    ("Total", "total"),
                )
            ],
            *[
                (lab, f"net_retention.{code}", P)
                for lab, code in (
                    ("Fire", "fire"),
                    ("Marine Cargo", "marine_cargo"),
                    ("Marine Hull", "marine_hull"),
                    ("Motor", "motor"),
                    ("Engineering", "engineering"),
                    ("Aviation", "aviation"),
                    ("Miscellaneous", "miscellaneous"),
                    ("Total", "total"),
                )
            ],
            *[
                (lab, f"incurred_claims_ratio.{code}", P)
                for lab, code in (
                    ("Fire", "fire"),
                    ("Marine", "marine"),
                    ("Motor", "motor"),
                    ("Health", "health"),
                    ("Others", "others"),
                    ("Total", "total"),
                )
            ],
            ("Underwriting Experience", "underwriting_experience", F),
            ("Assets Under Management", "aum", S),
            # remark says 'As on 31st March', but these are annual flows (income, profit): read as FY
            ("Income from investments", "investment_income", F),
            ("Profit after tax", "profit_after_tax", F),
            ("Paid-up Capital of General, Health and Reinsurers", "paid_up_capital", S),
            ("Assigned Capital of Branches of Foreign Reinsurers", "frb_assigned_capital", S),
            ("Commission expenses", "commission", F),
            ("Operating expenses related to Insurance business", "operating_expenses", F),
            ("No of grievances reported during the year", "grievances_reported", X),
            ("No. of grievances resolved during the year", "grievances_resolved", X),
            ("Resolution rate", "grievance_resolution_rate", X),
            ("No. of complaints reported with the Ombudsmen at different centres", "ombudsman_complaints", X),
            ("No. of Complaints disposed by Ombudsmen", "ombudsman_disposed", X),
            ("Disposal rate", "ombudsman_disposal_rate", X),
        ],
    ),
}
SUMMARY_TITLES = {
    "A": "SUMMARY OF INDIAN INSURANCE SECTOR",
    "B": "SUMMARY OF INDIAN LIFE INSURANCE SECTOR",
    "C": "SUMMARY OF INDIAN GENERAL INSURANCE SECTOR",
}
# published unit caption -> (clean unit, factor to that unit, unit_as_published, conversion)
SUMMARY_UNITS = {
    "₹Crore": ("INR_crore", 1.0, "Rs crore", "none"),
    "Nos.": ("count", 1.0, "number", "none"),
    "Lakhs": ("count", 1e5, "lakh (number)", "x 100,000 (lakh -> count)"),
    "Per cent": ("percent", 1.0, "per cent", "none"),
}


def _summary(ctx: BuildContext, rows: Rows, raw: Any) -> None:
    wb, member = load_zip_member(raw, "Summary.xlsx")
    for sheet, (inst, items) in SUMMARY.items():
        ws = wb[sheet]
        expect(ws, "A1", SUMMARY_TITLES[sheet])
        for cell, text in (("A2", "Particular"), ("B2", "Remarks"), ("C2", "Unit")):
            expect(ws, cell, text)
        years: dict[int, str] = {}
        c = 4
        while ws.cell(2, c).value is not None:
            years[c] = fy_label(ws.cell(2, c).value)
            c += 1
        item_rows = []
        for r in range(3, ws.max_row + 1):
            label = cell_text(ws, r, 1)
            if not label:
                continue
            vals = [ws.cell(r, k).value for k in years]
            if ws.cell(r, 3).value is None and all(v is None for v in vals):
                continue  # section header or footnote
            item_rows.append(r)
        if len(item_rows) != len(items):
            raise ValueError(f"IRDAI Summary {sheet}: {len(item_rows)} item rows, expected {len(items)}")
        provs: dict[tuple[str, str], str] = {}
        for r, (label, code, kind) in zip(item_rows, items, strict=True):
            got = cell_text(ws, r, 1)
            if got != label:
                raise ValueError(f"IRDAI Summary {sheet} row {r}: expected {label!r}, found {got!r}")
            if kind == X:
                continue
            cap = cell_text(ws, r, 3)
            if cap not in SUMMARY_UNITS:
                raise ValueError(f"IRDAI Summary {sheet} row {r}: unknown unit caption {cap!r}")
            unit, factor, pub, conv = SUMMARY_UNITS[cap]
            if kind == P and unit != "percent" or kind != P and unit == "percent":
                raise ValueError(f"IRDAI Summary {sheet} row {r}: kind {kind} does not fit unit {cap!r}")
            key = (cap, kind)
            if key not in provs:
                prow = [rr for rr, (_, _, kk) in zip(item_rows, items, strict=True) if kk == kind]
                provs[key] = rows.prov(
                    raw,
                    table_id=f"Summary Table {sheet}",
                    locator=f"zip member '{member}', sheet '{sheet}', rows {prow[0]}-{prow[-1]} with unit "
                    f"'{cap}', year columns D:{ws.cell(2, max(years)).column_letter} "
                    f"({years[min(years)]}..{years[max(years)]}); rows matched by label",
                    unit_as_published=pub,
                    conversion=conv,
                    release=RELEASE,
                    money=unit == "INR_crore",
                )
            for col, fy in years.items():
                v = num(ws.cell(r, col).value)
                if v is None:
                    continue
                stock = kind == S
                rows.add(
                    prov_id=provs[key],
                    series_id=f"sum_{sheet.lower()}.{code}" + (".current" if unit == "INR_crore" else ""),
                    table_id=f"Summary Table {sheet}",
                    item_code=code,
                    item_label=label,
                    value=v * factor,
                    unit=unit,
                    stock_flow={F: "flow", S: "stock", P: "n/a"}[kind],
                    period=fy_end(fy) if stock else fy,
                    period_type="date" if stock else "fy",
                    institution=inst,
                )


# --------------------------------------------------------------------------------------------
# Part I: life
# --------------------------------------------------------------------------------------------

T2_ROWS = {  # label in col B -> (item code, institution)
    "Life Insurance Corporation of India": ("total_premium", "lic"),
    "Private Sector Total": ("total_premium", "life_private"),
    "Grand Total": ("total_premium", "insurers_life"),
}

T20_FUNDS = {
    "Life Fund": "life_fund",
    "Pension & General Annuity Fund": "pension_annuity_group_fund",
    "ULIP Funds": "ulip_fund",
}
T20_CATEGORIES = {
    "Central Govt - Securities": "central_govt_securities",
    "State Govt & Other Approved Securities": "state_govt_other_approved_securities",
    "Infrastructure Investments": "infrastructure",
    "Approved Investments": "approved_investments",
    "Other than Approved Investments (OTAI)": "other_than_approved",
    "Total (Life Fund)": "total",
    "Total (Pension & General Annuity & Group Fund) Investments": "total",
    "Total (ULIP Funds)": "total",
}

# Tables 24 and 25: row labels in published order -> item code (None = heading row, not read)
T24_ITEMS: list[tuple[str, str | None]] = [
    ("Premiums earned – net", None),
    ("(a) Premium", "premium"),
    ("(b) Reinsurance ceded", "reinsurance_ceded"),
    ("(c) Reinsurance accepted", "reinsurance_accepted"),
    ("Income from Investments", None),
    ("(a) Interest, Dividends & Rent – Gross", "inv_interest_dividends_rent_gross"),
    ("(b) Profit on sale/redemption of investments", "inv_profit_on_sale"),
    ("(c) (Loss on sale/ redemption of investments)", "inv_loss_on_sale"),
    ("(d) Transfer/Gain on revaluation/change in fair value", "inv_fair_value_change"),
    ("(e) Amortization of Premium/Discount on Investments", "inv_amortisation"),
    ("(f) Appropriation/Expropriation Adjustment Account", "inv_appropriation_adjustment"),
    ("Unrealised Gains/Loss", "unrealised_gains"),
    ("Other Income", "other_income"),
    ("Transfer from Shareholders' Account", "transfer_from_shareholders"),
    ("TOTAL (A)", "total_a_income"),
    ("Commission", "commission"),
    ("Operating Expenses related to Insurance Business", "operating_expenses"),
    ("Provision for doubtful debts", "provision_doubtful_debts"),
    ("Adjustment related to previous year", "prior_year_adjustment"),
    ("Bad debts written off", "bad_debts_written_off"),
    ("Provision for Tax", "provision_for_tax"),
    ("Provisions (other than taxation)", None),
    ("(a) For diminution in the value of investments (Net)", "provision_diminution_investments"),
    ("(b) Others", "provision_others"),
    ("Service Tax on Unit Linked Charges", "service_tax_ulip_charges"),
    ("TOTAL (B)", "total_b_expenses"),
    ("Benefits Paid (Net)", "benefits_paid_net"),
    ("Interim Bonuses Paid", "interim_bonuses_paid"),
    ("Change in valuation of liability in respect of life policies", None),
    ("(a) Gross*", "change_liability_gross"),
    ("(b) Amount ceded in Reinsurance", "change_liability_ceded"),
    ("(c) Amount accepted in Reinsurance", "change_liability_accepted"),
    ("(d) Transfer to Linked Fund (Fund Reserve)", "transfer_to_linked_fund"),
    ("(e) Fund for discontinued policies", "fund_discontinued_policies"),
    ("TOTAL (C)", "total_c_benefits_reserves"),
    ("SURPLUS/ (DEFICIT) (D) =(A)-(B)- (C )", "surplus"),
    ("Amount transferred from Shareholder's A/c", "transfer_from_shareholders_after_surplus"),
    ("Prior Period Items", "prior_period_items"),
    ("Balance at the beginning of the year", "balance_beginning"),
    ("Transfer from Linked Fund (Lapsed Policies)", "transfer_from_linked_fund_lapsed"),
    ("Surplus available for appropriations", "surplus_available"),
    ("APPROPRIATIONS", None),
    ("Transfer to Shareholders’ Account", "appr_transfer_to_shareholders"),
    ("Transfer from shareholders’ Account(Non Technical Accounts)", "appr_transfer_from_shareholders"),
    ("Funds for future appropriations (Reserve for lapsed unit linked policies unlikely to be revived)", "appr_ffa_lapsed_ulip"),
    ("Balance being funds for future appropriations-Policyholders", "appr_ffa_policyholders"),
    ("Balance being funds for future appropriations-Previous year", "appr_ffa_previous_year"),
    ("Balance transferred to Balance Sheet", "appr_to_balance_sheet"),
    ("TOTAL (D)", "total_d_appropriations"),
]
T25_ITEMS: list[tuple[str, str | None]] = [
    ("Amounts transferred from the Policyholders Account (Technical Account)", "transfer_from_policyholders"),
    ("Income From Investments:", None),
    ("(a) Interest, Dividends & Rent – Gross", "inv_interest_dividends_rent_gross"),
    ("(b) Profit on sale/redemption of investments", "inv_profit_on_sale"),
    ("(c) (Loss on sale/ redemption of investments)", "inv_loss_on_sale"),
    ("(d) Transfer/gain on revaluation/Change in Fair value", "inv_fair_value_change"),
    ("(e) Amortization of Premium/Discount on Investments", "inv_amortisation"),
    ("Other Income", "other_income"),
    ("TOTAL (A)", "total_a_income"),
    ("Expenses other than those directly related to the insurance business", "expenses_non_insurance"),
    ("Bad debts written off", "bad_debts_written_off"),
    ("Provisions (Other than taxation)", None),
    ("(a) For diminution in the value of investments (Net)", "provision_diminution_investments"),
    ("(b) Provision for doubtful debts", "provision_doubtful_debts"),
    ("(c) Others", "provision_others"),
    ("Prior Period Expenses", "prior_period_expenses"),
    ("Contribution to Policyholders Account", "contribution_to_policyholders"),
    ("TOTAL (B)", "total_b_expenses"),
    ("Profit/ (Loss) before tax", "profit_before_tax"),
    ("Prior period expenses", "prior_period_expenses_after_pbt"),
    ("Provision for Taxation", "provision_for_tax"),
    ("Profit / (Loss) after tax", "profit_after_tax"),
    ("APPROPRIATIONS", None),
    ("(a) Balance at the beginning of the year", "appr_balance_beginning"),
    ("(b) Interim dividends paid during the year", "appr_interim_dividends"),
    ("(c) Proposed final dividend", "appr_proposed_final_dividend"),
    ("(d) Dividend distribution tax", "appr_dividend_distribution_tax"),
    ("(e) Transfer to reserves/ other accounts", "appr_transfer_to_reserves"),
    ("(f) Adjustment on account of depreciation in PY", "appr_depreciation_adjustment"),
    ("(g) Adjustment done due to scheme approved by High Court", "appr_court_scheme_adjustment"),
    ("(h) Debenture redemption reserve", "appr_debenture_redemption_reserve"),
    ("Profit carried to the Balance Sheet", "profit_carried_to_balance_sheet"),
]
LIFE_BLOCKS = {"LIC": "lic", "TOTAL": "insurers_life"}  # column-block header -> institution code


def _year_row(ws: Any, row: int, first: int, n: int) -> list[str]:
    return [fy_label(ws.cell(row, first + i).value) for i in range(n)]


def _labelled_rows(ws: Any, items: list[tuple[str, str | None]], first: int) -> list[tuple[int, str, str | None]]:
    """Match the col-A labels from `first` onwards against `items` (in order)."""
    out = []
    r = first
    for label, code in items:
        while not cell_text(ws, r, 1):
            r += 1
            if r > ws.max_row:
                raise ValueError(f"sheet {ws.title!r}: ran out of rows looking for {label!r}")
        got = cell_text(ws, r, 1)
        if got != clean_label(label):
            raise ValueError(f"sheet {ws.title!r} row {r}: expected {label!r}, found {got!r}")
        out.append((r, label, code))
        r += 1
    return out


def _accounts(rows: Rows, raw: Any, member: str, ws: Any, table: str, prefix: str, items, blocks, note: str) -> None:
    """Policyholders'/shareholders' account tables: label rows x (insurer block x 10 years), Rs lakh."""
    hdr = {cell_text(ws, 3, c): c for c in range(2, ws.max_column + 1) if cell_text(ws, 3, c)}
    labelled = _labelled_rows(ws, items, 5)
    last = labelled[-1][0]
    for block, inst in blocks.items():
        if block not in hdr:
            raise ValueError(f"{table}: insurer block {block!r} not in the header row")
        c0 = hdr[block]
        years = _year_row(ws, 4, c0, 10)
        if years[0] != "2015-16" or years[-1] != "2024-25":
            raise ValueError(f"{table} block {block}: unexpected years {years}")
        pid = rows.prov(
            raw,
            table_id=table,
            locator=f"zip member '{member}', sheet '{ws.title}', rows 5-{last}, block '{block}' cols "
            f"{ws.cell(4, c0).column_letter}:{ws.cell(4, c0 + 9).column_letter} (2015-16..2024-25); rows matched "
            "by label in published order",
            unit_as_published="Rs lakh",
            conversion=conversion_note("INR_lakh"),
            release=RELEASE,
            money=True,
            notes=note,
        )
        for r, label, code in labelled:
            if code is None:
                continue
            for i, fy in enumerate(years):
                v = num(ws.cell(r, c0 + i).value)
                if v is None:
                    continue
                rows.add(
                    prov_id=pid,
                    series_id=f"{prefix}.{code}.{inst}.current",
                    table_id=table,
                    item_code=code,
                    item_label=label,
                    value=to_inr_crore(v, "INR_lakh"),
                    unit="INR_crore",
                    stock_flow="flow",
                    period=fy,
                    period_type="fy",
                    institution=inst,
                )


def _life(ctx: BuildContext, rows: Rows, raw: Any) -> None:
    wb, member = load_zip_member(raw, "Part I.xlsx")

    ws = wb["2"]
    expect(ws, "A1", "TABLE 2: TOTAL PREMIUM OF LIFE INSURERS")
    expect(ws, "L2", "Crore")
    years = _year_row(ws, 3, 3, 10)
    if years[0] != "2015-16" or years[-1] != "2024-25":
        raise ValueError(f"Table 2: unexpected years {years}")
    found = {cell_text(ws, r, 2): r for r in range(4, ws.max_row + 1) if cell_text(ws, r, 2) in T2_ROWS}
    if set(found) != set(T2_ROWS):
        raise ValueError(f"Table 2: rows missing: {set(T2_ROWS) - set(found)}")
    pid = rows.prov(
        raw,
        table_id="Table 2",
        locator=f"zip member '{member}', sheet '2', rows {sorted(found.values())} (LIC, Private Sector Total, "
        "Grand Total), cols C:L (2015-16..2024-25); growth rows in brackets not read",
        unit_as_published="Rs crore",
        release=RELEASE,
        money=True,
        notes="Table note 2: 'The total premium figures include premiums from overseas business. At present, the Life "
        "Insurance Corporation of India (LIC) is the only life insurer undertaking insurance business outside India.' "
        "(LIC out-of-India premium: 398.15 cr in 2024-25, 476.25 cr in 2023-24, per Table 24 note 3.)",
    )
    for label, r in found.items():
        code, inst = T2_ROWS[label]
        for i, fy in enumerate(years):
            v = num(ws.cell(r, 3 + i).value)
            if v is None:
                continue
            rows.add(
                prov_id=pid,
                series_id=f"t2.{code}.{inst}.current",
                table_id="Table 2",
                item_code=code,
                item_label=f"Total premium: {label}",
                value=v,
                unit="INR_crore",
                stock_flow="flow",
                period=fy,
                period_type="fy",
                institution=inst,
            )

    ws = wb["20"]
    expect(ws, "A1", "TABLE 20: ASSETS UNDER MANAGEMENT (INVESTMENTS) OF LIFE INSURERS")
    expect(ws, "A2", "As on 31st March")
    expect(ws, "L3", "Crore")
    dates = [int(ws.cell(4, 3 + i).value) for i in range(10)]
    if dates != list(range(2016, 2026)):
        raise ValueError(f"Table 20: unexpected year header {dates}")
    fund = None
    value_rows = []
    for r in range(5, ws.max_row + 1):
        a, b = cell_text(ws, r, 1), cell_text(ws, r, 2)
        if a.startswith("Note"):
            break
        if a.upper().startswith("GRAND TOTAL"):
            value_rows.append((r, "all_funds", "total", "Grand total"))
            continue
        if a:
            if a not in T20_FUNDS:
                raise ValueError(f"Table 20 row {r}: unknown fund {a!r}")
            fund = T20_FUNDS[a]
        if not b:
            continue  # growth-rate row (never read)
        if b not in T20_CATEGORIES or fund is None:
            raise ValueError(f"Table 20 row {r}: unknown category {b!r}")
        value_rows.append((r, fund, T20_CATEGORIES[b], b))
    if len(value_rows) != 14:
        raise ValueError(f"Table 20: {len(value_rows)} value rows, expected 14")
    pid = rows.prov(
        raw,
        table_id="Table 20",
        locator=f"zip member '{member}', sheet '20', value rows {value_rows[0][0]}-{value_rows[-1][0]} (fund x "
        "category and GRAND TOTAL), cols C:L (31 March 2016..2025); interleaved growth rows not read",
        unit_as_published="Rs crore",
        release=RELEASE,
        money=True,
    )
    for r, fnd, cat, label in value_rows:
        for i, year in enumerate(dates):
            v = num(ws.cell(r, 3 + i).value)
            if v is None:
                continue
            rows.add(
                prov_id=pid,
                series_id=f"t20.aum.{fnd}.{cat}.current",
                table_id="Table 20",
                item_code=f"aum.{cat}",
                item_label=f"AUM (investments) of life insurers: {label}",
                value=v,
                unit="INR_crore",
                stock_flow="stock",
                period=f"{year}-03-31",
                period_type="date",
                institution="insurers_life",
                product=fnd,
            )

    ws = wb["24"]
    expect(ws, "A1", "TABLE 24: POLICYHOLDERS ACCOUNT OF LIFE INSURERS")
    expect(ws, "A2", "Lakh")
    expect(ws, "A62", "from out of India business")
    _accounts(rows, raw, member, ws, "Table 24", "t24", T24_ITEMS, LIFE_BLOCKS,
              "Policyholders' (technical) account. Table note 3: 'In respect of LIC, the premium figure include "
              "₹398.15 crore (PY ₹476.25 crore) from out of India business' (i.e. 2024-25 and 2023-24): LIC and "
              "industry premium include LIC's foreign-branch business (a RoW flow for S9/R17).")
    ws = wb["25"]
    expect(ws, "A1", "TABLE 25: SHAREHOLDERS ACCOUNT OF LIFE INSURERS")
    expect(ws, "A2", "Lakh")
    _accounts(rows, raw, member, ws, "Table 25", "t25", T25_ITEMS, LIFE_BLOCKS, "Shareholders' (non-technical) account")


# --------------------------------------------------------------------------------------------
# Part II: general and health insurers
# --------------------------------------------------------------------------------------------

GROUPS = {  # row label (col B) -> institution code
    "Public Sector Insurers Total": "general_public",
    "Private Sector Insurers Total": "general_private",
    "Specialized Insurers Total": "general_specialized",
    "Stand-alone Health Insurers Total": "health_standalone",
    "Grand Total": "insurers_general_direct",
}
SEGMENTS_41 = {"Fire": "fire", "Marine": "marine", "Motor": "motor", "Health + PA+ TRAVEL": "health_pa_travel",
               "Others": "others", "Total": "total"}
SEGMENTS_44 = {"FIRE INSURANCE": "fire", "MARINE INSURANCE": "marine", "MOTOR INSURANCE": "motor",
               "HEALTH INSURANCE": "health", "OTHER SEGMENTS": "others", "ALL SEGMENTS": "total"}
T46_CATEGORIES = {
    "Central Govt. Securities": "central_govt_securities",
    "State Govt & Other Approved Securities": "state_govt_other_approved_securities",
    "Housing & Loans to State Govt. for Housing and Fire Fighting Equipments": "housing_state_govt_loans",
    "Infrastructure Investments": "infrastructure",
    "Approved Investments": "approved_investments",
    "Other Investments": "other_investments",
    "TOTAL": "total",
}
T51_ITEMS: list[tuple[str, str | None]] = [
    ("OPERATING PROFIT/(LOSS)", "operating_profit"),
    ("(a) Fire Insurance", "operating_profit_fire"),
    ("(b) Marine Insurance", "operating_profit_marine"),
    ("(c ) Miscellaneous Insurance", "operating_profit_miscellaneous"),
    ("INCOME FROM INVESTMENTS", None),
    ("(a) Interest, Dividend & Rent – Gross", "inv_interest_dividend_rent_gross"),
    ("(b) Profit on sale of investments", "inv_profit_on_sale"),
    ("Less: Loss on sale of investments", "inv_loss_on_sale"),
    ("OTHER INCOME", "other_income"),
    ("TOTAL (A)", "total_a_income"),
    ("PROVISIONS (Other than taxation)", None),
    ("(a) For diminution in the value of investments", "provision_diminution_investments"),
    ("(b) For doubtful debts", "provision_doubtful_debts"),
    ("(c) Others", "provision_others"),
    ("OTHER EXPENSES", None),
    ("(a) Expenses other than those related to Insurance Business", "expenses_non_insurance"),
    ("(b) Bad debts written off", "bad_debts_written_off"),
    ("(c) Others", "other_expenses_others"),
    ("TOTAL (B)", "total_b_expenses"),
    ("Profit Before Tax", "profit_before_tax"),
    ("Prior Period Adjustments", "prior_period_adjustments"),
    ("Provision for Taxation", "provision_for_tax"),
    ("Profit after Tax", "profit_after_tax"),
    ("APPROPRIATIONS", None),
    ("(a) Interim dividends paid during the year", "appr_interim_dividends"),
    ("(b) Proposed final dividend", "appr_proposed_final_dividend"),
    ("(c) Dividend distribution tax", "appr_dividend_distribution_tax"),
    ("(d) Transfer to any Reserves or Other Accounts", "appr_transfer_to_reserves"),
    ("(e) Others", "appr_others"),
    ("Balance of profit/ loss brought forward from last year", "balance_brought_forward"),
    ("Balance carried forward to Balance Sheet", "balance_carried_forward"),
]
T51_BLOCKS = {k: v for k, v in GROUPS.items() if k != "Grand Total"}


def _group_rows(ws: Any, first: int) -> dict[str, int]:
    found = {cell_text(ws, r, 2): r for r in range(first, ws.max_row + 1) if cell_text(ws, r, 2) in GROUPS}
    if set(found) != set(GROUPS):
        raise ValueError(f"sheet {ws.title!r}: group total rows missing: {set(GROUPS) - set(found)}")
    return found


def _nonlife(ctx: BuildContext, rows: Rows, raw: Any) -> None:
    wb, member = load_zip_member(raw, "Part II.xlsx")

    ws = wb["40"]
    expect(ws, "A1", "TABLE 40 GROSS DIRECT PREMIUM OF GENERAL AND HEALTH INSURERS")
    expect(ws, "L2", "Crore")
    years = _year_row(ws, 3, 3, 10)
    if years[0] != "2015-16" or years[-1] != "2024-25":
        raise ValueError(f"Table 40: unexpected years {years}")
    grp = _group_rows(ws, 4)
    pid = rows.prov(
        raw,
        table_id="Table 40",
        locator=f"zip member '{member}', sheet '40', group total rows {sorted(grp.values())}, cols C:L "
        "(2015-16..2024-25); insurer rows and growth rows not read",
        unit_as_published="Rs crore",
        release=RELEASE,
        money=True,
        notes="Gross direct premium within and outside India",
    )
    for label, r in grp.items():
        inst = GROUPS[label]
        for i, fy in enumerate(years):
            v = num(ws.cell(r, 3 + i).value)
            if v is None:
                continue
            rows.add(prov_id=pid, series_id=f"t40.gross_direct_premium.{inst}.current", table_id="Table 40",
                     item_code="gross_direct_premium", item_label=f"Gross direct premium (within and outside India): {label}",
                     value=v, unit="INR_crore", stock_flow="flow", period=fy, period_type="fy", institution=inst)

    ws = wb["41"]
    expect(ws, "A1", "TABLE 41: SEGMENT-WISE GROSS DIRECT PREMIUM")
    expect(ws, "A2", "Crore")
    seg_cols = {cell_text(ws, 3, c): c for c in range(3, ws.max_column + 1) if cell_text(ws, 3, c)}
    if set(seg_cols) != set(SEGMENTS_41):
        raise ValueError(f"Table 41: unexpected segment header {sorted(seg_cols)}")
    grp = _group_rows(ws, 5)
    pid = rows.prov(
        raw,
        table_id="Table 41",
        locator=f"zip member '{member}', sheet '41', group total rows {sorted(grp.values())}, segment blocks "
        f"{ {k: ws.cell(3, c).column_letter for k, c in seg_cols.items()} } x 10 years (2015-16..2024-25)",
        unit_as_published="Rs crore",
        release=RELEASE,
        money=True,
        notes="Segment-wise gross direct premium within India",
    )
    for seg, c0 in seg_cols.items():
        yrs = _year_row(ws, 4, c0, 10)
        if yrs != years:
            raise ValueError(f"Table 41 segment {seg}: unexpected years {yrs}")
        for label, r in grp.items():
            inst = GROUPS[label]
            for i, fy in enumerate(yrs):
                v = num(ws.cell(r, c0 + i).value)
                if v is None:
                    continue
                rows.add(prov_id=pid, series_id=f"t41.gross_direct_premium.{SEGMENTS_41[seg]}.{inst}.current",
                         table_id="Table 41", item_code="gross_direct_premium_in_india",
                         item_label=f"Gross direct premium within India, {seg}: {label}", value=v, unit="INR_crore",
                         stock_flow="flow", period=fy, period_type="fy", institution=inst, product=SEGMENTS_41[seg])

    ws = wb["44"]
    expect(ws, "A1", "TABLE 44: NET PREMIUM EARNED, INCURRED CLAIMS")
    seg_cols = {cell_text(ws, 2, c): c for c in range(3, ws.max_column + 1) if cell_text(ws, 2, c)}
    if set(seg_cols) != set(SEGMENTS_44):
        raise ValueError(f"Table 44: unexpected segment header {sorted(seg_cols)}")
    grp = _group_rows(ws, 5)
    pid = rows.prov(
        raw,
        table_id="Table 44",
        locator=f"zip member '{member}', sheet '44', group total rows {sorted(grp.values())}, per segment block "
        f"{ {k: ws.cell(2, c).column_letter for k, c in seg_cols.items()} }: net premium earned (11 cols) and claims "
        "incurred net (next 11 cols), 2014-15..2024-25; the ratio columns are not read",
        unit_as_published="Rs crore",
        release=RELEASE,
        money=True,
    )
    for seg, c0 in seg_cols.items():
        for measure, off, needle in (("net_premium_earned", 0, "NET PREMIUM EARNED"),
                                     ("claims_incurred_net", 11, "CLAIMS INCURRED (NET)")):
            if needle not in cell_text(ws, 3, c0 + off).upper() or "CRORE" not in cell_text(ws, 3, c0 + off).upper():
                raise ValueError(f"Table 44 {seg}: expected {needle!r} (Rs crore) at col {c0 + off}")
            yrs = _year_row(ws, 4, c0 + off, 11)
            if yrs[0] != "2014-15" or yrs[-1] != "2024-25":
                raise ValueError(f"Table 44 {seg} {measure}: unexpected years {yrs}")
            for label, r in grp.items():
                inst = GROUPS[label]
                for i, fy in enumerate(yrs):
                    v = num(ws.cell(r, c0 + off + i).value)
                    if v is None:
                        continue
                    rows.add(prov_id=pid, series_id=f"t44.{measure}.{SEGMENTS_44[seg]}.{inst}.current",
                             table_id="Table 44", item_code=measure,
                             item_label=f"{'Net premium earned' if off == 0 else 'Claims incurred (net)'}, "
                             f"{seg.title()}: {label}", value=v, unit="INR_crore", stock_flow="flow", period=fy,
                             period_type="fy", institution=inst, product=SEGMENTS_44[seg])

    ws = wb["46"]
    expect(ws, "A1", "TABLE 46: ASSETS UNDER MANAGEMENT (INVESTMENTS) OF GENERAL")
    expect(ws, "A2", "As on 31st March")
    dates = [int(ws.cell(3, 3 + i).value) for i in range(10)]
    if dates != list(range(2016, 2026)):
        raise ValueError(f"Table 46: unexpected year header {dates}")
    amount_rows = []
    for r in range(4, ws.max_row + 1):
        a, b = cell_text(ws, r, 1), cell_text(ws, r, 2)
        if a:
            if a not in T46_CATEGORIES:
                raise ValueError(f"Table 46 row {r}: unknown category {a!r}")
            if b != "Amount (₹Crore)":
                raise ValueError(f"Table 46 row {r}: expected 'Amount (₹Crore)', found {b!r}")
            amount_rows.append((r, a))
    if [a for _, a in amount_rows] != list(T46_CATEGORIES):
        raise ValueError(f"Table 46: categories changed: {[a for _, a in amount_rows]}")
    pid = rows.prov(
        raw,
        table_id="Table 46",
        locator=f"zip member '{member}', sheet '46', 'Amount' rows {[r for r, _ in amount_rows]}, cols C:L "
        "(31 March 2016..2025); growth and share rows not read",
        unit_as_published="Rs crore",
        release=RELEASE,
        money=True,
        notes="General, health and reinsurance companies",
    )
    for r, label in amount_rows:
        for i, year in enumerate(dates):
            v = num(ws.cell(r, 3 + i).value)
            if v is None:
                continue
            rows.add(prov_id=pid, series_id=f"t46.aum.{T46_CATEGORIES[label]}.current", table_id="Table 46",
                     item_code=f"aum.{T46_CATEGORIES[label]}",
                     item_label=f"AUM (investments) of general, health and reinsurance companies: {label}", value=v,
                     unit="INR_crore", stock_flow="stock", period=f"{year}-03-31", period_type="date",
                     institution="insurers_general")

    ws = wb["51"]
    expect(ws, "A1", "TABLE 51: SHAREHOLDERS ACCOUNT OF GENERAL AND HEALTH INSURERS")
    hdr = {cell_text(ws, 3, c): c for c in range(2, ws.max_column + 1) if cell_text(ws, 3, c)}
    labelled = _labelled_rows(ws, T51_ITEMS, 5)
    unit_note = "Rs crore (Table 50, the companion policyholders' account, is captioned Rs crore; Table 51 has no caption)"
    for block, inst in T51_BLOCKS.items():
        if block not in hdr:
            raise ValueError(f"Table 51: block {block!r} missing")
        c0 = hdr[block]
        yrs = _year_row(ws, 4, c0, 10)
        if yrs[0] != "2015-16" or yrs[-1] != "2024-25":
            raise ValueError(f"Table 51 block {block}: unexpected years {yrs}")
        pid = rows.prov(
            raw,
            table_id="Table 51",
            locator=f"zip member '{member}', sheet '51', rows 5-{labelled[-1][0]}, block '{block}' cols "
            f"{ws.cell(4, c0).column_letter}:{ws.cell(4, c0 + 9).column_letter} (2015-16..2024-25)",
            unit_as_published="Rs crore",
            release=RELEASE,
            money=True,
            notes=unit_note,
        )
        for r, label, code in labelled:
            if code is None:
                continue
            for i, fy in enumerate(yrs):
                v = num(ws.cell(r, c0 + i).value)
                if v is None:
                    continue
                rows.add(prov_id=pid, series_id=f"t51.{code}.{inst}.current", table_id="Table 51", item_code=code,
                         item_label=label, value=v, unit="INR_crore", stock_flow="flow", period=fy, period_type="fy",
                         institution=inst)


def build(ctx: BuildContext, unit: str) -> list[Dataset]:
    raw = ctx.raw(SRC, RAW)
    out = []
    for name, fn, desc in (
        ("irdai_summary", _summary, "IRDAI Handbook 2024-25 Summary tables A-C (all/life/general insurers), 2013-14 to 2024-25"),
        ("irdai_life", _life, "IRDAI Handbook 2024-25 life: premium (T2), AUM by fund x asset (T20), policyholders'/shareholders' accounts (T24-T25)"),
        ("irdai_nonlife", _nonlife, "IRDAI Handbook 2024-25 general/health: premium (T40-T41), net premium and claims (T44), AUM (T46), shareholders' account (T51)"),
    ):
        rows = Rows(ctx, SRC, VINTAGE)
        fn(ctx, rows, raw)
        out.append(Dataset(f"{unit}_{name}", frame(rows.rows), desc))
    return out
