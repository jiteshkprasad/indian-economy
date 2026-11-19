"""Value tests for the NAS 2026 statements of the mospi_nas_2026 unit (new base 2022-23).

Three kinds of evidence:
- DOC_VALUES: numbers quoted by the Phase 0 recon/verify notes (docs/phase0/recon/mospi_nas.md,
  docs/phase0/verify/mospi_nas.md) and the gap map (data/gap_map.csv), i.e. read off the published
  statements by other agents, independent of this parser.
- ANCHORS: at least three values per dataset with the cell they were read from in the pinned XLSX
  (sheet!cell). They pin the label -> cell mapping; a verifier can open the file at that cell.
- identities inside and across statements, ranges, signs, continuity, base/vintage separation.
"""

from __future__ import annotations

import polars as pl
import pytest

from pipeline.core import checks

pytestmark = pytest.mark.quality
U = "mospi_nas_2026"
NEW_DATASETS = [
    "s1_2", "s1_4", "s1_5", "s1_6", "s1_6a", "s1_6b", "s1_7", "s1_8", "s1_9", "s1_10", "s1_11", "s1_12", "s1_13",
    "s1_14", "s4_1", "s4_2", "s5_1", "s5_2", "s5_3", "s6_1", "s6_2", "s7_1", "s7_1a", "s7_1b", "s7_1c", "s7_2",
    "s7_2a", "s7_2b", "s7_2c", "s7_3", "s7_3a", "s7_3b", "s7_3c", "s7_4", "s7_4a", "s7_4b", "s7_4c", "s8_1_1",
    "s8_1_2", "s8_2", "s8_3", "s8_4", "s8_5", "s8_6_1a", "s8_6_1b", "s8_6_2a", "s8_6_2b", "s8_7", "s8_8", "s8_9",
    "s8_10", "s8_11", "s8_12", "s8_13", "s8_14", "s8_15_1", "s8_15_2", "s8_15_3", "s8_16", "s8_17_2", "s8_18_1",
    "s8_18_2",
]
_cache: dict[str, pl.DataFrame] = {}


def ds(name: str) -> pl.DataFrame:
    if name not in _cache:
        _cache[name] = checks.load_dataset(U, f"{U}_{name}")
    return _cache[name]


def cat(*names: str) -> pl.DataFrame:
    return pl.concat([ds(n) for n in names], how="diagonal_relaxed")


def v(name: str, sid: str, period: str = "2023-24") -> float:
    return checks.value(ds(name), sid, period)


def ident(df: pl.DataFrame, total: str, parts: dict[str, float], what: str, tol: float = 2.0) -> None:
    checks.assert_no_rows(checks.check_identity(df, total, parts, by=("period",), abs_tol=tol), what)


# ---------------------------------------------------------------------------------------------
# 1. values quoted in the Phase 0 notes / gap map (independent reading of the statements)
# ---------------------------------------------------------------------------------------------

DOC_VALUES = [
    # verify/mospi_nas.md: 1.9 household rows 2023-24
    ("s1_9", "s1_9.household_sector.current", "2023-24", 5890330),
    ("s1_9", "s1_9.gross_financial_saving.current", "2023-24", 3602199),
    ("s1_9", "s1_9.less_financial_liabilities.current", "2023-24", 1909287),
    ("s1_9", "s1_9.saving_in_physical_assets.current", "2023-24", 4025292),
    ("s1_9", "s1_9.saving_in_the_form_of_gold_and_silver_ornaments.current", "2023-24", 172127),
    # gap map K1/K2/K3/K5/R14a (NAS 1.9, 2023-24)
    ("s1_9", "s1_9.public_non_financial_corporations.current", "2023-24", 462996),
    ("s1_9", "s1_9.private_non_financial_corporations.current", "2023-24", 2410409),
    ("s1_9", "s1_9.public_financial_corporations.current", "2023-24", 535510),
    ("s1_9", "s1_9.private_financial_corporations.current", "2023-24", 455938),
    ("s1_9", "s1_9.general_government.current", "2023-24", -318384),
    ("s1_9", "s1_9.net_capital_inflow_from_row.current", "2023-24", 208891),
    ("s1_9", "s1_9.reinvested_earnings_of_foreign_companies_in_private_corporat.current", "2023-24", 163704),
    # recon 1.9: GG saving 2022-23 and 2024-25
    ("s1_9", "s1_9.general_government.current", "2022-23", -591900),
    ("s1_9", "s1_9.general_government.current", "2024-25", -99729),
    # recon/verify + gap map D1/C2: 1.14
    ("s1_14", "s1_14.households_npish.gross_disposable_income.current", "2022-23", 21019932),
    ("s1_14", "s1_14.households_npish.gross_disposable_income.current", "2023-24", 22877010),
    ("s1_14", "s1_14.households_npish.gross_disposable_income.current", "2024-25", 24796706),
    ("s1_14", "s1_14.gg.gross_disposable_income.current", "2023-24", 2802643),
    ("s1_14", "s1_14.gg.final_consumption_expenditure.current", "2023-24", 3121027),
    ("s1_14", "s1_14.households_npish.final_consumption_expenditure.current", "2023-24", 16415547),
    # gap map 6.1 items (2023-24) and verify notes (2022-23)
    ("s6_1", "s6_1.compensation_of_employees_from_rest_of_the_world.current", "2023-24", 62344),
    ("s6_1", "s6_1.property_and_entrepreneurial_income_from_rest_of_the_world.current", "2023-24", 280907),
    ("s6_1", "s6_1.other_current_transfers_to_resident_sectors_other_than_gener.current", "2023-24", 983128),
    ("s6_1", "s6_1.compensation_of_employees_to_the_rest_of_the_world.current", "2023-24", 30636),
    ("s6_1", "s6_1.property_and_entrepreneurial_income_to_the_rest_of_the_world.current", "2023-24", 724612),
    ("s6_1", "s6_1.other_current_transfers_by_resident_sectors_other_than_gener.current", "2023-24", 99913),
    ("s6_1", "s6_1.capital_transfers_to_general_government_from_the_rest_of_the.current", "2023-24", -7000),
    ("s6_1", "s6_1.capital_transfers_to_corporations_households_and_npishs_net.current", "2023-24", 1556),
    ("s6_1", "s6_1.acquisitions_less_disposal_of_non_produced_non_financial_ass.current", "2023-24", 1666),
    ("s6_1", "s6_1.net_acquisition_of_foreign_financial_assets.current", "2023-24", 670569),
    ("s6_1", "s6_1.net_incurrence_of_foreign_liabilities.current", "2023-24", 886570),
    ("s6_1", "s6_1.adjustment_for_cif_in_import_of_services.current", "2023-24", 212499),
    ("s6_1", "s6_1.imports.current", "2023-24", 7159405),
    ("s6_1", "s6_1.surplus_on_current_transactions.current", "2023-24", -208891),
    ("s6_1", "s6_1.surplus_on_current_transactions.current", "2022-23", -527525),
    ("s6_1", "s6_1.adjustment_for_cif_in_import_of_services.current", "2022-23", 292776),
    ("s6_1", "s6_1.services_without_adjustment_for_cif.current", "2022-23", 1461480),
    # gap map K7a / K8a: 5.3 (2023-24)
    ("s5_3", "s5_3.currency.current", "2023-24", 118248),
    ("s5_3", "s5_3.deposits.current", "2023-24", 1417816),
    ("s5_3", "s5_3.with_banks.current", "2023-24", 1409652),
    ("s5_3", "s5_3.with_non_banking_companies.current", "2023-24", -59126),
    ("s5_3", "s5_3.with_co_operative_banks_and_societies.current", "2023-24", 59063),
    ("s5_3", "s5_3.trade_debt_net.current", "2023-24", 8228),
    ("s5_3", "s5_3.shares_and_debentures.current", "2023-24", 358719),
    ("s5_3", "s5_3.mutual_funds.current", "2023-24", 285052),
    ("s5_3", "s5_3.claims_on_government.current", "2023-24", 335303),
    ("s5_3", "s5_3.investment_in_government_securities.current", "2023-24", 25552),
    ("s5_3", "s5_3.investment_in_small_savings_etc.current", "2023-24", 309751),
    ("s5_3", "s5_3.insurance_funds.current", "2023-24", 649086),
    ("s5_3", "s5_3.provident_and_pension_funds.current", "2023-24", 723027),
    ("s5_3", "s5_3.financial_liabilities.current", "2023-24", 1909287),
    ("s5_3", "s5_3.bank_advances.current", "2023-24", 1856521),
    ("s5_3", "s5_3.loans_and_advances_by_co_operative_banks_and_societies.current", "2023-24", 50664),
    ("s5_3", "s5_3.loans_by_financial_corporations_and_non_banking_companies.current", "2023-24", -6423),
    ("s5_3", "s5_3.loans_and_advances_from_government.current", "2023-24", 334),
    ("s5_3", "s5_3.loans_from_insurance_corporations.current", "2023-24", 8191),
    ("s5_3", "s5_3.net_financial_saving_of_household_sector_1_4.current", "2023-24", 1692912),
    ("s5_3", "s5_3.net_financial_saving_of_household_sector_1_4.current", "2024-25", 2257602),
    # gap map F4b: 4.1 NVA 2023-24
    ("s4_1", "s4_1.central_government.current", "2023-24", 577519),
    ("s4_1", "s4_1.state_government.current", "2023-24", 1178217),
    ("s4_1", "s4_1.local_bodies.current", "2023-24", 218133),
    ("s4_1", "s4_1.autonomous_institutions.current", "2023-24", 153164),
    # gap map R4: 1.13 FISIM by user 2023-24
    ("s1_13", "s1_13.allocation_of_fisim_as_ic_to_user_industry.current", "2023-24", 627885),
    ("s1_13", "s1_13.private_final_consumption_expenditure.current", "2023-24", 602897),
    ("s1_13", "s1_13.rest_of_world_row.current", "2023-24", 29794),
    # gap map V2a: 7.1C households OS/MI and CFC 2023-24; P2/P10/V1/V2 totals (7.1)
    ("s7_1c", "s7_1c.total.os_mi.current", "2023-24", 8590352),
    ("s7_1c", "s7_1c.total.cfc.current", "2023-24", 1181079),
    ("s7_1", "s7_1.total.ic.current", "2023-24", 31158879),
    ("s7_1", "s7_1.total.net_production_taxes.current", "2023-24", -57442),
    ("s7_1", "s7_1.total.ce.current", "2023-24", 9442897),
    ("s7_1", "s7_1.total.os_mi.current", "2023-24", 13183820),
    ("s7_1", "s7_1.total.cfc.current", "2023-24", 3836206),
    # verify notes: 7.1 2022-23 totals (CE, OS/MI, CFC, PT closing to GVA 23823136); recon 7.1 totals
    ("s7_1", "s7_1.total.ce.current", "2022-23", 8653669),
    ("s7_1", "s7_1.total.os_mi.current", "2022-23", 11654812),
    ("s7_1", "s7_1.total.cfc.current", "2022-23", 3584380),
    ("s7_1", "s7_1.total.net_production_taxes.current", "2022-23", -69725),
    ("s7_1", "s7_1.total.output.current", "2022-23", 53484479),
    ("s7_1", "s7_1.total.ic.current", "2022-23", 29661344),
    # recon 1.6: GVA 2022-23 .. 2024-25; recon 8.17.1/8.17.2 via 1.1
    ("s1_6", "s1_6.total.gva.current", "2022-23", 23823136),
    ("s1_6", "s1_6.total.gva.current", "2023-24", 26405480),
    ("s1_6", "s1_6.total.gva.current", "2024-25", 28845683),
    # verify notes: 1.14 sector GCF sum 2022-23 = 8627076 (GCF excl. valuables); 1.10 total
    ("s1_10", "s1_10.total.gcf.current", "2022-23", 8627076),
    # recon: PFCE 1.12 = 1.1 PFCE
    ("s1_12", "s1_12.private_final_consumption_expenditure_3_4_1_4_2.current", "2023-24", 16415547),
    # 8.18.2 Q1 2022-23 discrepancy (recon: 'Q1 -41,323')
    ("s8_18_2", "s8_18_2.discrepancies.current", "Q1 2022-23", -41323),
]


@pytest.mark.parametrize("name, sid, period, crore", DOC_VALUES, ids=[f"{d[1]}@{d[2]}" for d in DOC_VALUES])
def test_values_quoted_in_phase0_notes(name, sid, period, crore):
    assert round(v(name, sid, period)) == crore


# ---------------------------------------------------------------------------------------------
# 2. anchors: several values per dataset, with the cell they were read from
# ---------------------------------------------------------------------------------------------

ANCHORS = [
    ("s1_10", "s1_10.total.gcf.constant_2022_23", "2023-24", 9610133.3, "1.10!G32"),
    ("s1_10", "s1_10.agri.gcf.constant_2022_23", "2023-24", 551675.2, "1.10!G8"),
    ("s1_10", "s1_10.other_services.gcf.current", "2023-24", 666047.7, "1.10!D31"),
    ("s1_10", "s1_10.water_transport.gcf.current", "2023-24", 5357.4, "1.10!D23"),
    ("s1_11", "s1_11.general_government.constant_2022_23", "2023-24", 1222898.1, "1.11!G33"),
    ("s1_11", "s1_11.pct_share.public_non_financial_corporations.current", "2023-24", 10.8, "1.11!D44"),
    ("s1_11", "s1_11.public_non_financial_corporations.machinery_and_equipment.current", "2023-24", 355616.9, "1.11!D15"),
    ("s1_12", "s1_12.alcoholic_beverages_tobacco_and_narcotics.constant_2022_23", "2023-24", 216672.7, "1.12!G10"),
    ("s1_12", "s1_12.information_and_communication.current", "2023-24", 290578.7, "1.12!D16"),
    ("s1_12", "s1_12.transport.current", "2023-24", 2882319.1, "1.12!D15"),
    ("s1_13", "s1_13.agriculture_livestock_forestry_and_fishing.current", "2023-24", 139985.6, "1.13!D8"),
    ("s1_13", "s1_13.other_services.current", "2023-24", 31672.3, "1.13!D17"),
    ("s1_13", "s1_13.transport_storage_communication_and_services_related_to_broa.current", "2023-24", 28476.2, "1.13!D14"),
    ("s1_14", "s1_14.fc_private.gross_savings.current", "2023-24", 455937.9, "1.14!D25"),
    ("s1_14", "s1_14.fc_private.consumption_of_fixed_capital.current", "2023-24", 62431.0, "1.14!D27"),
    ("s1_14", "s1_14.households_npish.consumption_of_fixed_capital.current", "2023-24", 1181078.8, "1.14!D41"),
    ("s1_14", "s1_14.nfc_public.gross_value_added_at_basic_prices.current", "2023-24", 1519220.0, "1.14!D9"),
    ("s1_2", "s1_2.constant.per_capita_gdp.constant_2022_23", "2023-24", 201324.3, "1.2!D16"),
    ("s1_2", "s1_2.current.per_capita_nni.current", "2023-24", 177896.6, "1.2!D12"),
    ("s1_2", "s1_2.per_capita_gndi.current", "2023-24", 211716.0, "1.2!D13"),
    ("s1_4", "s1_4.cpi_combined", "2023-24", 105.4, "1.4!D31"),
    ("s1_4", "s1_4.price.gva_at_basic_prices.transport_storage_communication_and_services_related_to_broa", "2023-24", 102.9, "1.4!D15"),
    ("s1_4", "s1_4.quantum.private_final_consumption_expenditure", "2023-24", 106.2, "1.4!D49"),
    ("s1_5", "s1_5.total.compensation_of_employees_ce.current", "2023-24", 9442896.6, "1.5!D146"),
    ("s1_5", "s1_5.agri.compensation_of_employees_ce.current", "2023-24", 727434.7, "1.5!D14"),
    ("s1_5", "s1_5.other_services.production_taxes_less_production_subsidies.current", "2023-24", 9627.5, "1.5!D136"),
    ("s1_5", "s1_5.utilities.production_taxes_less_production_subsidies.current", "2023-24", -11267.1, "1.5!D52"),
    ("s1_6", "s1_6.total.gva.constant_2022_23", "2023-24", 25592651.2, "1.6!G37"),
    ("s1_6", "s1_6.agri.gva.constant_2022_23", "2023-24", 4872239.2, "1.6!G8"),
    ("s1_6", "s1_6.mfg_textiles.gva.constant_2022_23", "2023-24", 391791.1, "1.6!G16"),
    ("s1_6", "s1_6.water_transport.gva.current", "2023-24", 20676.6, "1.6!D28"),
    ("s1_6a", "s1_6a.total.gva_share.constant_2022_23", "2023-24", 100.0, "1.6A!C36"),
    ("s1_6a", "s1_6a.agri.gva_share.constant_2022_23", "2023-24", 19.0, "1.6A!G7"),
    ("s1_6a", "s1_6a.mfg_textiles.gva_share.constant_2022_23", "2023-24", 1.5, "1.6A!G15"),
    ("s1_6a", "s1_6a.water_transport.gva_share.current", "2023-24", 0.1, "1.6A!D27"),
    ("s1_6b", "s1_6b.total.gva_growth.constant_2022_23", "2023-24", 7.4, "1.6B!E36"),
    ("s1_6b", "s1_6b.agri.gva_growth.constant_2022_23", "2023-24", 2.7, "1.6B!E7"),
    ("s1_6b", "s1_6b.mfg_textiles.gva_growth.constant_2022_23", "2023-24", -1.3, "1.6B!E15"),
    ("s1_6b", "s1_6b.water_transport.gva_growth.current", "2023-24", 8.3, "1.6B!C27"),
    ("s1_7", "s1_7.total.nva.constant_2022_23", "2023-24", 21795163.2, "1.7!G32"),
    ("s1_7", "s1_7.agri.nva.constant_2022_23", "2023-24", 4631337.3, "1.7!G8"),
    ("s1_7", "s1_7.other_services.nva.current", "2023-24", 1670702.1, "1.7!D31"),
    ("s1_7", "s1_7.water_transport.nva.current", "2023-24", 15555.8, "1.7!D23"),
    ("s1_8", "s1_8.total.cfc.constant_2022_23", "2023-24", 3797488.0, "1.8!G32"),
    ("s1_8", "s1_8.agri.cfc.constant_2022_23", "2023-24", 240901.9, "1.8!G8"),
    ("s1_8", "s1_8.other_services.cfc.current", "2023-24", 241148.5, "1.8!D31"),
    ("s1_8", "s1_8.water_transport.cfc.current", "2023-24", 5120.7, "1.8!D23"),
    ("s1_9", "s1_9.gross_savings.current", "2023-24", 9436798.6, "1.9!D8"),
    ("s1_9", "s1_9.finances_for_gross_capital_formation_1_2.current", "2023-24", 9645689.3, "1.9!D26"),
    ("s1_9", "s1_9.private_non_financial_corporations.current", "2023-24", 2410408.5, "1.9!D13"),
    ("s1_9", "s1_9.savings_of_co_operatives_banks_and_societies.current", "2023-24", 32958.0, "1.9!D29"),
    ("s4_1", "s4_1.andhra_pradesh.constant_2022_23", "2023-24", 62159.0, "4.1!G13"),
    ("s4_1", "s4_1.madhya_pradesh.constant_2022_23", "2023-24", 63873.0, "4.1!G27"),
    ("s4_1", "s4_1.west_bengal.current", "2023-24", 50244.8, "4.1!D43"),
    ("s4_2", "s4_2.capital_expenditure.total.current", "2023-24", 1358637.7, "4.2(2023-24)!X15"),
    ("s4_2", "s4_2.capital_expenditure.01.current", "2023-24", 297704.5, "4.2(2023-24)!C15"),
    ("s4_2", "s4_2.gfcf.04.water_supply.current", "2023-24", 87244.9, "4.2(2023-24)!K17"),
    ("s4_2", "s4_2.total_expenditure.total.current", "2023-24", 6650592.2, "4.2(2023-24)!X25"),
    ("s5_1", "s5_1.total.constant_2022_23", "2023-24", 15903693.1, "5.1!G72"),
    ("s5_1", "s5_1.alcoholic_beverages.constant_2022_23", "2023-24", 101334.1, "5.1!G25"),
    ("s5_1", "s5_1.insurance_and_financial_services.current", "2023-24", 1092903.5, "5.1!D64"),
    ("s5_1", "s5_1.water_supply_and_miscellaneous_services_relating_to_the_dwel.current", "2023-24", 98082.3, "5.1!D33"),
    ("s5_2", "s5_2.total.aic.constant_2022_23", "2023-24", 16995236.2, "5.2!Q22"),
    ("s5_2", "s5_2.alcoholic_beverages_tobacco_and_narcotics.aic.constant_2022_23", "2023-24", 216672.7, "5.2!O10"),
    ("s5_2", "s5_2.information_and_communication.aic.current", "2023-24", 290578.7, "5.2!F16"),
    ("s5_2", "s5_2.transport.hh_ice.current", "2023-24", 2882319.1, "5.2!F15"),
    ("s5_3", "s5_3.bank_advances.current", "2023-24", 1856520.6, "5.3!D32"),
    ("s5_3", "s5_3.loans_by_financial_corporations_and_non_banking_companies.current", "2023-24", -6423.0, "5.3!D34"),
    ("s5_3", "s5_3.with_non_banking_companies.current", "2023-24", -59126.5, "5.3!D13"),
    ("s6_1", "s6_1.acquisitions_less_disposal_of_non_produced_non_financial_ass.current", "2023-24", 1666.3, "6.1!D62"),
    ("s6_1", "s6_1.miscellaneous_services.construction.current", "2023-24", 37941.1, "6.1!D28"),
    ("s6_1", "s6_1.transport_respect_of_imports_other_than_merchandise.current", "2023-24", 237488.5, "6.1!D41"),
    ("s6_2", "s6_2.adjustment_for_cif_in_import_of_services.constant_2022_23", "2023-24", 202461.8, "6.2!D20"),
    ("s6_2", "s6_2.goods_including_net_exports_of_goods_under_merchanting_and_m.constant_2022_23", "2023-24", 3665677.3, "6.2!D10"),
    ("s6_2", "s6_2.property_and_entrepreneurial_income_to_rest_of_the_world.constant_2022_23", "2023-24", 674426.8, "6.2!D18"),
    ("s7_1", "s7_1.total.ce.current", "2023-24", 9442896.6, "7.1!O31"),
    ("s7_1", "s7_1.agri.ce.current", "2023-24", 727434.7, "7.1!O7"),
    ("s7_1", "s7_1.other_services.ic.current", "2023-24", 930425.3, "7.1!K30"),
    ("s7_1", "s7_1.water_transport.output.current", "2023-24", 53555.6, "7.1!J22"),
    ("s7_1a", "s7_1a.total.ce.current", "2023-24", 2894267.5, "7.1A!O31"),
    ("s7_1a", "s7_1a.agri.ce.current", "2023-24", 37319.7, "7.1A!O7"),
    ("s7_1a", "s7_1a.other_services.ic.current", "2023-24", 182542.2, "7.1A!K30"),
    ("s7_1a", "s7_1a.water_transport.output.current", "2023-24", 7015.4, "7.1A!J22"),
    ("s7_1b", "s7_1b.total.ce.current", "2023-24", 4247821.7, "7.1B!O31"),
    ("s7_1b", "s7_1b.agri.ce.current", "2023-24", 83539.7, "7.1B!O7"),
    ("s7_1b", "s7_1b.other_services.ic.current", "2023-24", 448825.5, "7.1B!K30"),
    ("s7_1b", "s7_1b.water_transport.output.current", "2023-24", 42903.6, "7.1B!J22"),
    ("s7_1c", "s7_1c.total.ce.current", "2023-24", 2300807.4, "7.1C!O31"),
    ("s7_1c", "s7_1c.agri.ce.current", "2023-24", 606575.4, "7.1C!O7"),
    ("s7_1c", "s7_1c.other_services.ic.current", "2023-24", 299057.6, "7.1C!K30"),
    ("s7_1c", "s7_1c.water_transport.output.current", "2023-24", 3636.5, "7.1C!J22"),
    ("s7_2", "s7_2.total.cfc.constant_2022_23", "2023-24", 3797488.0, "7.2!V32"),
    ("s7_2", "s7_2.agri.cfc.constant_2022_23", "2023-24", 240901.9, "7.2!V8"),
    ("s7_2", "s7_2.other_services.gcf_excl_valuables.constant_2022_23", "2023-24", 662463.4, "7.2!U31"),
    ("s7_2", "s7_2.water_transport.gfcf.current", "2023-24", 5164.3, "7.2!G23"),
    ("s7_2a", "s7_2a.total.cfc.constant_2022_23", "2023-24", 836858.5, "7.2A!V32"),
    ("s7_2a", "s7_2a.agri.cfc.constant_2022_23", "2023-24", 41546.8, "7.2A!V8"),
    ("s7_2a", "s7_2a.other_services.gcf_excl_valuables.constant_2022_23", "2023-24", 128020.5, "7.2A!U31"),
    ("s7_2a", "s7_2a.water_transport.gfcf.current", "2023-24", 728.4, "7.2A!G23"),
    ("s7_2b", "s7_2b.total.cfc.constant_2022_23", "2023-24", 1781053.1, "7.2B!V32"),
    ("s7_2b", "s7_2b.agri.cfc.constant_2022_23", "2023-24", 6072.1, "7.2B!V8"),
    ("s7_2b", "s7_2b.other_services.gcf_excl_valuables.constant_2022_23", "2023-24", 336949.1, "7.2B!U31"),
    ("s7_2b", "s7_2b.water_transport.gfcf.current", "2023-24", 4408.9, "7.2B!G23"),
    ("s7_2c", "s7_2c.total.cfc.constant_2022_23", "2023-24", 1179576.4, "7.2C!V32"),
    ("s7_2c", "s7_2c.agri.cfc.constant_2022_23", "2023-24", 193283.0, "7.2C!V8"),
    ("s7_2c", "s7_2c.other_services.gcf_excl_valuables.constant_2022_23", "2023-24", 197493.8, "7.2C!U31"),
    ("s7_2c", "s7_2c.water_transport.gfcf.current", "2023-24", 27.1, "7.2C!G23"),
    ("s7_3", "s7_3.total.gfcf.current", "2023-24", 9245762.5, "7.3!H31"),
    ("s7_3", "s7_3.agri.gfcf.current", "2023-24", 526886.5, "7.3!H7"),
    ("s7_3", "s7_3.other_services.gfcf_dwellings_structures.current", "2023-24", 334959.1, "7.3!I30"),
    ("s7_3", "s7_3.water_transport.gfcf_machinery_equipment.current", "2023-24", 3401.6, "7.3!J22"),
    ("s7_3a", "s7_3a.total.gfcf.current", "2023-24", 2248592.7, "7.3A!H31"),
    ("s7_3a", "s7_3a.agri.gfcf.current", "2023-24", 97412.1, "7.3A!H7"),
    ("s7_3a", "s7_3a.other_services.gfcf_dwellings_structures.current", "2023-24", 78032.2, "7.3A!I30"),
    ("s7_3a", "s7_3a.water_transport.gfcf_machinery_equipment.current", "2023-24", 479.6, "7.3A!J22"),
    ("s7_3b", "s7_3b.total.gfcf.current", "2023-24", 2972809.5, "7.3B!H31"),
    ("s7_3b", "s7_3b.agri.gfcf.current", "2023-24", 11940.4, "7.3B!H7"),
    ("s7_3b", "s7_3b.other_services.gfcf.current", "2023-24", 342546.0, "7.3B!H30"),
    ("s7_3b", "s7_3b.water_transport.gfcf_machinery_equipment.current", "2023-24", 2895.0, "7.3B!J22"),
    ("s7_3c", "s7_3c.total.gfcf.current", "2023-24", 4024360.3, "7.3C!H31"),
    ("s7_3c", "s7_3c.agri.gfcf.current", "2023-24", 417534.0, "7.3C!H7"),
    ("s7_3c", "s7_3c.other_services.gfcf_dwellings_structures.current", "2023-24", 109353.8, "7.3C!I30"),
    ("s7_3c", "s7_3c.water_transport.gfcf_machinery_equipment.current", "2023-24", 27.1, "7.3C!H22"),
    ("s7_4", "s7_4.total.inventories.current", "2024-03-31", 6961886.4, "7.4!G31"),
    ("s7_4", "s7_4.agri.inventories.current", "2024-03-31", 303759.9, "7.4!G7"),
    ("s7_4", "s7_4.other_services.net_capital_stock.current", "2024-03-31", 6033904.0, "7.4!H30"),
    ("s7_4", "s7_4.water_transport.net_fixed_capital_stock.current", "2024-03-31", 133483.9, "7.4!F22"),
    ("s7_4a", "s7_4a.total.inventories.current", "2024-03-31", 799508.4, "7.4A!G31"),
    ("s7_4a", "s7_4a.agri.inventories.current", "2024-03-31", 21513.9, "7.4A!G7"),
    ("s7_4a", "s7_4a.other_services.net_capital_stock.current", "2024-03-31", 1185214.0, "7.4A!H30"),
    ("s7_4a", "s7_4a.water_transport.net_fixed_capital_stock.current", "2024-03-31", 10590.4, "7.4A!F22"),
    ("s7_4b", "s7_4b.total.inventories.current", "2024-03-31", 5365132.6, "7.4B!G31"),
    ("s7_4b", "s7_4b.agri.inventories.current", "2024-03-31", 41236.4, "7.4B!G7"),
    ("s7_4b", "s7_4b.other_services.net_capital_stock.current", "2024-03-31", 3080081.1, "7.4B!H30"),
    ("s7_4b", "s7_4b.water_transport.net_fixed_capital_stock.current", "2024-03-31", 114695.3, "7.4B!F22"),
    ("s7_4c", "s7_4c.total.inventories.current", "2024-03-31", 797245.4, "7.4C!G31"),
    ("s7_4c", "s7_4c.agri.inventories.current", "2024-03-31", 241009.7, "7.4C!G7"),
    ("s7_4c", "s7_4c.other_services.net_capital_stock.current", "2024-03-31", 1768608.9, "7.4C!H30"),
    ("s7_4c", "s7_4c.water_transport.net_fixed_capital_stock.current", "2024-03-31", 8198.2, "7.4C!F22"),
    ("s8_10", "s8_10.air_transport.cfc.constant_2022_23", "2023-24", 10610.4, "8.10!G37"),
    ("s8_10", "s8_10.road_transport.net_value_added.current", "2023-24", 593305.2, "8.10!D24"),
    ("s8_10", "s8_10.water_transport.output.current", "2023-24", 53555.6, "8.10!D26"),
    ("s8_11", "s8_11.cable_operators_recording_publishing_and_broadcasting_servic.gross_value_added_unadjusted_for_fisim.constant_2022_23", "2023-24", 97469.5, "8.11!G27"),
    ("s8_11", "s8_11.telecommunication.input.current", "2023-24", 244251.4, "8.11!D22"),
    ("s8_11", "s8_11.total_storage_communication_and_services_related_to_broadcas.output.current", "2023-24", 938255.1, "8.11!D36"),
    ("s8_12", "s8_12.captive_financial_institutions_s_127.constant_2022_23", "2023-24", 88453.8, "8.12!G15"),
    ("s8_12", "s8_12.life_insurance_s_128.constant_2022_23", "2023-24", 85323.6, "8.12!G17"),
    ("s8_12", "s8_12.pension_funds_s_129.current", "2023-24", 0.0, "8.12!C19"),
    ("s8_13", "s8_13.administrative_and_support_service_activities_and_other_prof.gross_value_added_unadjusted_for_fisim.constant_2022_23", "2023-24", 1022884.3, "8.13!G27"),
    ("s8_13", "s8_13.ownership_of_dwellings.gross_value_added_unadjusted_for_fisim.current", "2023-24", 2027324.8, "8.13!D15"),
    ("s8_13", "s8_13.real_estate_ownership_of_dwellings_and_other_professional_se.output.current", "2023-24", 7043423.3, "8.13!D29"),
    ("s8_14", "s8_14.arts_entertainment_and_recreation.fisim.constant_2022_23", "2023-24", 1444.0, "8.14!G27"),
    ("s8_14", "s8_14.personal_services_including_washing_hair_dressing_custom_tai.gross_value_added.constant_2022_23", "2023-24", 327181.2, "8.14!G33"),
    ("s8_14", "s8_14.total_other_services.output.current", "2023-24", 2842275.9, "8.14!D40"),
    ("s8_15_1", "s8_15_1.total.ce.current", "2023-24", 2127241.6, "8.15.1!O31"),
    ("s8_15_1", "s8_15_1.construction.ce.current", "2023-24", 45850.1, "8.15.1!O15"),
    ("s8_15_1", "s8_15_1.public_admin.net_production_taxes.current", "2023-24", 0.0, "8.15.1!F14"),
    ("s8_15_1", "s8_15_1.utilities.output.current", "2023-24", 95080.8, "8.15.1!J14"),
    ("s8_15_2", "s8_15_2.total.ce.current", "2023-24", 248602.0, "8.15.2!O31"),
    ("s8_15_2", "s8_15_2.agri.ce.current", "2023-24", 34501.2, "8.15.2!O7"),
    ("s8_15_2", "s8_15_2.road_transport.ce.current", "2023-24", 4538.3, "8.15.2!O21"),
    ("s8_15_2", "s8_15_2.water_transport.output.current", "2023-24", 1680.0, "8.15.2!J22"),
    ("s8_15_3", "s8_15_3.total.ce.current", "2023-24", 518424.0, "8.15.3!O31"),
    ("s8_15_3", "s8_15_3.agri.ce.current", "2023-24", 2818.4, "8.15.3!O7"),
    ("s8_15_3", "s8_15_3.other_services.ce.current", "2023-24", 3180.0, "8.15.3!O30"),
    ("s8_15_3", "s8_15_3.water_transport.output.current", "2023-24", 5335.4, "8.15.3!J22"),
    ("s8_16", "s8_16.administrative_departments.cfc.current", "2023-24", 375679.2, "8.16!F7"),
    ("s8_16", "s8_16.non_financial.book_depreciation.current", "2023-24", 244111.0, "8.16!E13"),
    ("s8_16", "s8_16.railways.cfc.current", "2023-24", 33147.5, "8.16!F9"),
    ("s8_17_2", "s8_17_2.total.gva.constant_2022_23", "2023-24", 25592651.2, "8.17.2!C19"),
    ("s8_17_2", "s8_17_2.agri.gva.constant_2022_23", "2023-24", 4872239.2, "8.17.2!C9"),
    ("s8_17_2", "s8_17_2.public_admin_other.gva.constant_2022_23", "2023-24", 3289389.8, "8.17.2!C18"),
    ("s8_17_2", "s8_17_2.utilities.gva.current", "2023-24", 732148.4, "8.17.2!L13"),
    ("s8_18_1", "s8_18_1.agriculture_livestock_forestry_and_fishing.constant_2022_23", "Q2 2023-24", 917119.7, "8.18.1!G9"),
    ("s8_18_1", "s8_18_1.gva_at_basic_prices.constant_2022_23", "Q2 2023-24", 5925094.4, "8.18.1!G19"),
    ("s8_18_1", "s8_18_1.valuables.constant_2022_23", "Q2 2023-24", 82568.6, "8.18.1!G27"),
    ("s8_18_2", "s8_18_2.agriculture_livestock_forestry_and_fishing.current", "Q2 2023-24", 961983.1, "8.18.2!G9"),
    ("s8_18_2", "s8_18_2.gva_at_basic_prices.current", "Q2 2023-24", 6133318.4, "8.18.2!G19"),
    ("s8_18_2", "s8_18_2.valuables.current", "Q2 2023-24", 92782.9, "8.18.2!G27"),
    ("s8_1_1", "s8_1_1.chemical_fertilisers.constant_2022_23", "2023-24", 58141.7, "8.1.1!G13"),
    ("s8_1_1", "s8_1_1.fisim.current", "2023-24", 51777.6, "8.1.1!D21"),
    ("s8_1_1", "s8_1_1.seed.current", "2023-24", 86090.2, "8.1.1!D11"),
    ("s8_1_2", "s8_1_2.ajwain.constant_2022_23", "2023-24", 489.7, "8.1.2!G66"),
    ("s8_1_2", "s8_1_2.linseed.current", "2023-24", 596.1, "8.1.2!D36"),
    ("s8_1_2", "s8_1_2.wheat.current", "2023-24", 281831.3, "8.1.2!D10"),
    ("s8_2", "s8_2.beef.constant_2022_23", "2023-24", 42296.4, "8.2!G12"),
    ("s8_2", "s8_2.market_charges.constant_2022_23", "2023-24", 799.5, "8.2!G33"),
    ("s8_2", "s8_2.wool_and_hair.current", "2023-24", 612.4, "8.2!D22"),
    ("s8_3", "s8_3.cfc.constant_2022_23", "2023-24", 4854.0, "8.3!G16"),
    ("s8_3", "s8_3.input.constant_2022_23", "2023-24", 65364.8, "8.3!G12"),
    ("s8_3", "s8_3.value_of_output.current", "2023-24", 462432.8, "8.3!D8"),
    ("s8_4", "s8_4.cfc.constant_2022_23", "2023-24", 16196.6, "8.4!G15"),
    ("s8_4", "s8_4.input.current", "2023-24", 160075.5, "8.4!D12"),
    ("s8_4", "s8_4.value_of_output.current", "2023-24", 430060.2, "8.4!D8"),
    ("s8_5", "s8_5.bauxite.constant_2022_23", "2023-24", 6232.1, "8.5!G18"),
    ("s8_5", "s8_5.metallic_minerals.input.constant_2022_23", "2023-24", 101666.6, "8.5!G22"),
    ("s8_5", "s8_5.total_minerals.value_of_output.current", "2023-24", 884053.5, "8.5!D32"),
    ("s8_6_1a", "s8_6_1a.manufacture_of_basic_iron_and_steel_casting_of_iron_and_stee.constant_2022_23", "2023-24", 1736822.0, "8.6.1 PART I!H20"),
    ("s8_6_1a", "s8_6_1a.manufacture_of_metal_and_metal_products.constant_2022_23", "2023-24", 3124062.2, "8.6.1 PART I!H19"),
    ("s8_6_1a", "s8_6_1a.total_value_of_output.current", "2023-24", 17719548.0, "8.6.1 PART I!E45"),
    ("s8_6_1b", "s8_6_1b.cfc.constant_2022_23", "2023-24", 737235.3, "8.6.1 PART II!H48"),
    ("s8_6_1b", "s8_6_1b.manufacture_of_machinery_and_equipment.constant_2022_23", "2023-24", 819612.0, "8.6.1 PART II!H23"),
    ("s8_6_1b", "s8_6_1b.repair_and_installation_of_machinery_and_equipment.current", "2023-24", 8693.9, "8.6.1 PART II!E44"),
    ("s8_6_2a", "s8_6_2a.manufacture_of_basic_iron_and_steel_casting_of_iron_and_stee.constant_2022_23", "2023-24", 66593.5, "8.6.2 PART I!H20"),
    ("s8_6_2a", "s8_6_2a.manufacture_of_metal_and_metal_products.constant_2022_23", "2023-24", 315282.9, "8.6.2 PART I!H19"),
    ("s8_6_2a", "s8_6_2a.total_output.current", "2023-24", 2201779.2, "8.6.2 PART I!E45"),
    ("s8_6_2b", "s8_6_2b.cfc.constant_2022_23", "2023-24", 87404.1, "8.6.2 PART II!H48"),
    ("s8_6_2b", "s8_6_2b.manufacture_of_machinery_and_equipment.constant_2022_23", "2023-24", 25844.2, "8.6.2 PART II!H23"),
    ("s8_6_2b", "s8_6_2b.repair_and_installation_of_machinery_and_equipment.current", "2023-24", 33733.6, "8.6.2 PART II!E44"),
    ("s8_7", "s8_7.total.cfc.constant_2022_23", "2023-24", 253039.0, "8.7!G41"),
    ("s8_7", "s8_7.electricity.cfc.constant_2022_23", "2023-24", 199964.4, "8.7!G13"),
    ("s8_7", "s8_7.remediation_and_other_utility_services.input.constant_2022_23", "2023-24", 93321.2, "8.7!G31"),
    ("s8_7", "s8_7.water_supply.output.current", "2023-24", 132494.7, "8.7!D23"),
    ("s8_8", "s8_8.bitumen_and_bitumen_mixtures.constant_2022_23", "2023-24", 76734.1, "8.8!G23"),
    ("s8_8", "s8_8.mineral_exploration.constant_2022_23", "2023-24", 63799.6, "8.8!G17"),
    ("s8_8", "s8_8.timber_and_roundwood.current", "2023-24", 228527.0, "8.8!D22"),
    ("s8_9", "s8_9.hotels_and_restaurants.cfc.constant_2022_23", "2023-24", 62111.5, "8.9!G20"),
    ("s8_9", "s8_9.trade_and_repair_services.input.constant_2022_23", "2023-24", 1053163.7, "8.9!G10"),
    ("s8_9", "s8_9.trade_repair_hotels_and_restaurants.output.current", "2023-24", 3971195.6, "8.9!D23"),
]


@pytest.mark.parametrize("name, sid, period, value, cell", ANCHORS, ids=[f"{a[1]}@{a[2]}" for a in ANCHORS])
def test_anchor_values(name, sid, period, value, cell):
    assert abs(v(name, sid, period) - value) < 0.051, f"{sid} {period}: expected {value} (pinned file cell {cell})"


def test_every_dataset_has_anchors():
    assert {a[0] for a in ANCHORS} == set(NEW_DATASETS)
    for name in NEW_DATASETS:
        assert sum(a[0] == name for a in ANCHORS) >= 3, name


# ---------------------------------------------------------------------------------------------
# 3. identities inside statements
# ---------------------------------------------------------------------------------------------

INDUSTRY_TREE = {
    "total": ["agri", "mining", "manufacturing", "utilities", "construction", "trade_hotels", "transport_comm",
              "financial", "real_estate_prof", "public_admin", "other_services"],
    "agri": ["crops", "livestock", "forestry", "fishing"],
    "trade_hotels": ["trade_repair", "hotels"],
    "transport_comm": ["railways", "road_transport", "water_transport", "air_transport", "transport_services",
                       "storage", "communication"],
}


def _wide(df: pl.DataFrame, key: str) -> pl.DataFrame:
    """One column per `key` value (industry or item), one row per (other dims, period)."""
    idx = [c for c in ("industry", "item_code", "price_basis", "period") if c != key]
    return df.pivot(on=key, index=idx, values="value", aggregate_function=None)


def _check_sum(df: pl.DataFrame, key: str, total: str, parts: list[str], tol: float, what: str,
               coef: dict[str, float] | None = None) -> None:
    w = _wide(df, key)
    cols = [total, *parts]
    missing = [c for c in cols if c not in w.columns]
    assert not missing, f"{what}: no column(s) {missing}"
    w = w.drop_nulls(cols)
    assert w.height, f"{what}: no complete rows"
    coef = coef or {}
    s = sum(pl.col(p) * coef.get(p, 1.0) for p in parts)
    bad = w.with_columns((pl.col(total) - s).alias("diff")).filter(pl.col("diff").abs() > tol)
    checks.assert_no_rows(bad, what)


@pytest.mark.parametrize("name", ["s1_6", "s1_7", "s1_8", "s1_10", "s7_1", "s7_2", "s7_3", "s7_4"])
def test_industry_aggregation(name):
    df = ds(name).filter(pl.col("unit") == "INR_crore")
    for total, parts in INDUSTRY_TREE.items():
        _check_sum(df, "industry", total, parts, tol=5.0, what=f"{name}: {total} = sum of {parts}")
    if name == "s1_6":
        _check_sum(df, "industry", "manufacturing", ["mfg_food", "mfg_textiles", "mfg_metal", "mfg_machinery",
                                                     "mfg_other"], 2.0, "1.6 manufacturing sub-groups")


@pytest.mark.parametrize("name", ["s7_1", "s7_1a", "s7_1b", "s7_1c", "s8_15_1", "s8_15_2", "s8_15_3"])
def test_production_account_by_industry(name):
    df = ds(name)
    os_code = "os_mi" if "os_mi" in set(df["item_code"]) else "os"
    _check_sum(df, "item_code", "output", ["ic", "gva"], 2.0, f"{name}: output = IC + GVA")
    _check_sum(df, "item_code", "gva", ["ce", os_code, "cfc", "net_production_taxes"], 2.0,
               f"{name}: GVA = CE + OS/MI + CFC + net production taxes")


def test_capital_formation_by_industry_identities():
    for n in ("s7_2", "s7_2a", "s7_2b", "s7_2c"):
        _check_sum(ds(n), "item_code", "gcf_excl_valuables", ["gfcf", "cis"], 2.0, f"{n}: GCF = GFCF + CIS")
    for n in ("s7_3", "s7_3a", "s7_3b", "s7_3c"):
        _check_sum(ds(n), "item_code", "gfcf", ["gfcf_dwellings_structures", "gfcf_machinery_equipment",
                                                  "gfcf_cultivated_biological", "gfcf_ipp"], 2.0, f"{n}: GFCF by asset")
    for n in ("s7_4", "s7_4a", "s7_4b", "s7_4c"):
        _check_sum(ds(n), "item_code", "net_capital_stock", ["net_fixed_capital_stock", "inventories"], 2.0,
                   f"{n}: NCS = NFCS + inventories")


@pytest.mark.parametrize("fam", ["7.1", "7.2", "7.3", "7.4"])
def test_sector_split_adds_to_total(fam):
    """7.x = 7.xA (public sector) + 7.xB (private corporations) + 7.xC (households), current prices."""
    t = fam.replace(".", "_")
    frames = []
    for suffix in ("", "a", "b", "c"):
        d = ds(f"s{t}{suffix}").filter(pl.col("price_basis") == "current")
        d = d.with_columns(pl.col("item_code").replace({"os": "os_mi"}), pl.lit(suffix or "all").alias("part"))
        frames.append(d.select("industry", "item_code", "period", "part", "value"))
    w = pl.concat(frames).pivot(on="part", index=["industry", "item_code", "period"], values="value")
    w = w.fill_null(0.0).with_columns((pl.col("all") - pl.col("a") - pl.col("b") - pl.col("c")).alias("diff"))
    checks.assert_no_rows(w.filter(pl.col("diff").abs() > 5.0), f"{fam} = {fam}A + {fam}B + {fam}C")


def test_public_sector_is_gg_plus_departmental_plus_non_departmental():
    frames = []
    for n, part in (("s7_1a", "pub"), ("s8_15_1", "gg"), ("s8_15_2", "de"), ("s8_15_3", "nde")):
        frames.append(ds(n).filter(pl.col("industry") == "total").with_columns(pl.lit(part).alias("part"))
                      .select("item_code", "period", "part", "value"))
    w = pl.concat(frames).pivot(on="part", index=["item_code", "period"], values="value").fill_null(0.0)
    w = w.with_columns((pl.col("pub") - pl.col("gg") - pl.col("de") - pl.col("nde")).alias("diff"))
    checks.assert_no_rows(w.filter(pl.col("diff").abs() > 5.0), "7.1A = 8.15.1 + 8.15.2 + 8.15.3 (totals)")


def test_statement_1_5_matches_7_1_and_1_10():
    s15 = ds("s1_5").filter(pl.col("price_basis") == "current")
    for item5, (other, item) in {
        "output": ("s7_1", "output"), "intermediate_consumption": ("s7_1", "ic"),
        "gva_at_basic_prices": ("s7_1", "gva"), "compensation_of_employees_ce": ("s7_1", "ce"),
        "gross_capital_formation": ("s1_10", "gcf"),
    }.items():
        a = s15.filter(pl.col("item_code") == item5).select("industry", "period", "value")
        b = ds(other).filter((pl.col("item_code") == item) & (pl.col("price_basis") == "current"))
        j = a.join(b.select("industry", "period", pl.col("value").alias("v2")), on=["industry", "period"])
        assert j.height >= 30, (item5, j.height)
        checks.assert_no_rows(j.filter((pl.col("value") - pl.col("v2")).abs() > 1.0), f"1.5 {item5} vs {other}")


def test_statement_1_9_identities():
    d = ds("s1_9")
    p = "s1_9.{}.current".format
    ident(d, p("gross_savings"), {p("non_financial_corporations"): 1, p("financial_corporations"): 1,
                                  p("general_government"): 1, p("household_sector"): 1}, "1.9 gross saving by sector")
    ident(d, p("non_financial_corporations"), {p("public_non_financial_corporations"): 1,
                                               p("private_non_financial_corporations"): 1}, "1.9 NFC")
    ident(d, p("financial_corporations"), {p("public_financial_corporations"): 1,
                                           p("private_financial_corporations"): 1}, "1.9 FC")
    ident(d, p("public_non_financial_corporations"), {p("public_non_financial_corporations.departmental_enterprises"): 1,
          p("public_non_financial_corporations.non_departmental_enterprises"): 1}, "1.9 public NFC")
    ident(d, p("household_sector"), {p("gross_financial_saving"): 1, p("less_financial_liabilities"): -1,
                                     p("saving_in_physical_assets"): 1,
                                     p("saving_in_the_form_of_gold_and_silver_ornaments"): 1}, "1.9 household saving")
    ident(d, p("finances_for_gross_capital_formation_1_2"), {p("gross_savings"): 1, p("net_capital_inflow_from_row"): 1},
          "1.9 finances for GCF")


def test_statement_1_11_identities():
    d = ds("s1_11").filter(pl.col("unit") == "INR_crore")
    sectors = ["public_non_financial_corporations", "private_non_financial_corporations", "public_financial_corporations",
               "private_financial_corporations", "general_government", "household_sector"]
    assets = ["dwellings_other_buildings_and_structures", "machinery_and_equipment", "cultivated_biological_resources",
              "intellectual_property_products"]
    for b in ("current", "constant_2022_23"):
        ident(d, f"s1_11.gross_fixed_capital_formation.{b}", {f"s1_11.{s}.{b}": 1 for s in sectors}, f"1.11 sectors {b}")
        for s in ["gross_fixed_capital_formation", *sectors]:
            ident(d, f"s1_11.{s}.{b}", {f"s1_11.{s}.{a}.{b}": 1 for a in assets}, f"1.11 {s} by asset {b}")


def test_statement_1_12_and_5_1_identities():
    d = ds("s1_12")
    purposes = ["food_and_non_alcoholic_beverages", "alcoholic_beverages_tobacco_and_narcotics", "clothing_and_footwear",
                "housing_water_electricity_gas_and_other_fuels",
                "furnishings_household_equipment_and_routine_household_mainte", "health", "transport",
                "information_and_communication", "recreation_sport_and_culture", "education",
                "restaurants_and_accommodation_services", "insurance_and_financial_services",
                "personal_care_social_protection_and_miscellaneous_goods_and"]
    for b in ("current", "constant_2022_23"):
        dom = f"s1_12.private_final_consumption_expenditure_in_domestic_market.{b}"
        ident(d, dom, {f"s1_12.{x}.{b}": 1 for x in purposes}, f"1.12 by purpose {b}")
        ident(d, dom, {f"s1_12.{x}.{b}": 1 for x in ("durable_goods", "semi_durable_goods", "non_durable_goods",
                                                      "services")}, f"1.12 by durability {b}")
        ident(d, f"s1_12.private_final_consumption_expenditure_3_4_1_4_2.{b}",
              {dom: 1, f"s1_12.final_consumption_expenditure_of_resident_households_in_the.{b}": 1,
               f"s1_12.final_consumption_expenditure_of_non_resident_households_in.{b}": -1}, f"1.12 national PFCE {b}")
        ident(ds("s5_1"), f"s5_1.total.{b}", {f"s5_1.{x}.{b}": 1 for x in purposes}, f"5.1 divisions {b}")
    both = cat("s1_12", "s5_1", "s5_2")
    ident(both, "s5_1.total.current", {"s1_12.private_final_consumption_expenditure_in_domestic_market.current": 1},
          "5.1 total = 1.12 domestic PFCE")
    ident(both, "s5_2.total.hh_ice.current", {"s5_1.total.current": 1}, "5.2 household ICE = 5.1 total")
    ident(ds("s5_1"), "s5_1.food_and_non_alcoholic_beverages.current",
          {"s5_1.food.current": 1, "s5_1.non_alcoholic_beverages.current": 1}, "5.1 food + non-alcoholic")


def test_statement_5_2_actual_individual_consumption():
    d = ds("s5_2").with_columns(
        pl.col("series_id").str.split(".").list.get(1).alias("row"),
        pl.col("series_id").str.split(".").list.get(2).alias("var"),
    )
    w = d.pivot(on="var", index=["row", "price_basis", "period"], values="value").fill_null(0.0)
    assert w.height == 14 * 2 * 3
    bad = w.filter((pl.col("aic") - pl.col("hh_ice") - pl.col("gg_ice")).abs() > 1.0)
    checks.assert_no_rows(bad, "5.2 AIC = household ICE + government ICE")


def test_statement_1_13_identities():
    d = ds("s1_13")
    inds = ["agriculture_livestock_forestry_and_fishing", "mining_and_quarrying", "manufacturing",
            "electricity_gas_water_supply_and_other_utility_services", "construction",
            "trade_repair_hotels_and_restaurants", "transport_storage_communication_and_services_related_to_broa",
            "real_estate_ownership_of_dwelling_and_professional_services", "public_administration_and_defence",
            "other_services"]
    ident(d, "s1_13.allocation_of_fisim_as_ic_to_user_industry.current", {f"s1_13.{i}.current": 1 for i in inds},
          "1.13 FISIM IC by industry")
    ident(d, "s1_13.allocation_of_fisim_to_expenditure.current",
          {"s1_13.private_final_consumption_expenditure.current": 1, "s1_13.rest_of_world_row.current": 1},
          "1.13 FISIM final uses")
    ident(cat("s1_13", "s5_1"), "s5_1.financial_intermediation_services_indirectly_measured.current",
          {"s1_13.private_final_consumption_expenditure.current": 1}, "FISIM in PFCE: 5.1 = 1.13")


def test_statement_4_1_identities():
    d = ds("s4_1")
    states = [s for s in d["series_id"].unique().to_list() if s.endswith(".current") and s.split(".")[1] not in {
        "gross_value_added", "consumption_of_fixed_capital", "net_value_added", "central_government",
        "state_government", "local_bodies", "autonomous_institutions"}]
    assert len(states) == 31, states
    for b in ("current", "constant_2022_23"):
        ident(d, f"s4_1.net_value_added.{b}", {f"s4_1.gross_value_added.{b}": 1, f"s4_1.consumption_of_fixed_capital.{b}": -1},
              f"4.1 NVA = GVA - CFC {b}")
        ident(d, f"s4_1.net_value_added.{b}", {f"s4_1.{x}.{b}": 1 for x in ("central_government", "state_government",
              "local_bodies", "autonomous_institutions")}, f"4.1 NVA by level {b}", tol=5.0)
    ident(d, "s4_1.state_government.current", {s: 1 for s in states}, "4.1 States sum", tol=10.0)


def test_statement_4_2_identities():
    d = ds("s4_2")
    divisions = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"]
    rows = sorted({s.split(".")[1] for s in d["series_id"].to_list()})
    for r in rows:
        ident(d, f"s4_2.{r}.total.current", {f"s4_2.{r}.{c}.current": 1 for c in divisions}, f"4.2 {r}: total = divisions",
              tol=5.0)
    ident(d, "s4_2.consumption_expenditure.total.current", {"s4_2.compensation_of_employees.total.current": 1,
          "s4_2.net_purchase_of_commodities_and_services.total.current": 1}, "4.2 consumption = CE + purchases")
    ident(d, "s4_2.current_expenditure.total.current", {"s4_2.consumption_expenditure.total.current": 1,
          "s4_2.subsidy.total.current": 1, "s4_2.current_transfer.total.current": 1}, "4.2 current expenditure")
    ident(d, "s4_2.total_expenditure.total.current", {"s4_2.current_expenditure.total.current": 1,
          "s4_2.capital_expenditure.total.current": 1, "s4_2.net_investment_in_stock.total.current": 1,
          "s4_2.loans_and_advances.total.current": 1}, "4.2 total expenditure", tol=5.0)
    ident(d, "s4_2.final_consumption_expenditure.total.current", {"s4_2.individual_consumption_expenditure.total.current": 1,
          "s4_2.collective_consumption_expenditure.total.current": 1}, "4.2 FCE = individual + collective")
    # 4.2 excludes CFC (its note); adding GG CFC (8.16 administrative departments) gives 1.14 GG FCE
    ident(cat("s4_2", "s8_16", "s1_14"), "s1_14.gg.final_consumption_expenditure.current",
          {"s4_2.final_consumption_expenditure.total.current": 1, "s8_16.administrative_departments.cfc.current": 1},
          "1.14 GG FCE = 4.2 FCE + GG CFC", tol=5.0)
    ident(cat("s4_2", "s5_2"), "s5_2.total.gg_ice.current", {"s4_2.individual_consumption_expenditure.total.current": 1},
          "5.2 GG individual consumption = 4.2")


def test_statement_5_3_identities():
    d = ds("s5_3")
    p = "s5_3.{}.current".format
    ident(d, p("gross_financial_saving"), {p(x): 1 for x in ("currency", "deposits", "shares_and_debentures",
          "claims_on_government", "insurance_funds", "provident_and_pension_funds")}, "5.3 financial assets")
    ident(d, p("deposits"), {p(x): 1 for x in ("with_banks", "with_non_banking_companies",
          "with_co_operative_banks_and_societies", "trade_debt_net")}, "5.3 deposits")
    ident(d, p("shares_and_debentures"), {p(x): 1 for x in ("corporate_companies_shares_debentures_hybrid_instruments_in",
          "co_operative_banks_and_societies", "mutual_funds", "secondary_markets_net_investments")}, "5.3 shares")
    ident(d, p("claims_on_government"), {p("investment_in_government_securities"): 1,
          p("investment_in_small_savings_etc"): 1}, "5.3 claims on government")
    ident(d, p("insurance_funds"), {p(x): 1 for x in ("life_insurance_funds", "postal_insurance", "state_insurance")},
          "5.3 insurance")
    ident(d, p("financial_liabilities"), {p(x): 1 for x in ("bank_advances",
          "loans_and_advances_by_co_operative_banks_and_societies",
          "loans_by_financial_corporations_and_non_banking_companies", "loans_and_advances_from_government",
          "loans_from_insurance_corporations")}, "5.3 liabilities")
    ident(d, p("household_saving_1_2_3_4"), {p("gross_financial_saving"): 1, p("saving_in_physical_assets"): 1,
          p("saving_in_form_of_gold_and_silver_ornaments"): 1, p("financial_liabilities"): -1}, "5.3 household saving")
    ident(d, p("net_financial_saving_of_household_sector_1_4"), {p("gross_financial_saving"): 1,
          p("financial_liabilities"): -1}, "5.3 net financial saving")
    ident(cat("s5_3", "s1_9"), p("household_saving_1_2_3_4"), {"s1_9.household_sector.current": 1}, "5.3 = 1.9 households")


def test_statement_6_1_identities():
    d = ds("s6_1")
    p = "s6_1.{}.current".format
    ident(d, p("exports"), {p("exports.goods"): 1, p("services"): 1}, "6.1 exports")
    ident(d, p("exports.goods"), {p("merchandise_f_o_b"): 1, p("net_exports_of_goods_under_merchanting"): 1,
          p("exports.goods.goods_for_processing_in_reporting_economy"): 1}, "6.1 goods exports")
    ident(d, p("net_exports_of_goods_under_merchanting"), {p("goods_acquired_under_merchanting"): 1,
          p("goods_sold_under_merchanting"): 1}, "6.1 merchanting")
    ident(d, p("imports"), {p("imports.goods"): 1, p("services_without_adjustment_for_cif"): 1}, "6.1 imports")
    ident(d, p("current_receipts"), {p("exports"): 1, p("compensation_of_employees_from_rest_of_the_world"): 1,
          p("property_and_entrepreneurial_income_from_rest_of_the_world"): 1,
          p("other_current_transfers_to_resident_sectors_other_than_gener"): 1}, "6.1 current receipts")
    ident(d, p("current_disbursements"), {p("imports"): 1, p("compensation_of_employees_to_the_rest_of_the_world"): 1,
          p("property_and_entrepreneurial_income_to_the_rest_of_the_world"): 1,
          p("other_current_transfers_by_resident_sectors_other_than_gener"): 1}, "6.1 current disbursements")
    ident(d, p("surplus_on_current_transactions"), {p("current_receipts"): 1, p("current_disbursements"): -1},
          "6.1 current-account surplus")
    ident(d, p("import_of_services_adjusted_for_cost_insurance_and_freight_c"),
          {p("services_without_adjustment_for_cif"): 1, p("adjustment_for_cif_in_import_of_services"): -1},
          "6.1 CIF-adjusted services imports")
    ident(d, p("net_lending_to_the_rest_of_the_world_13_14_15_16_or_18_19"),
          {p("surplus_on_current_transactions"): 1,
           p("capital_transfers_to_general_government_from_the_rest_of_the"): 1,
           p("capital_transfers_to_corporations_households_and_npishs_net"): 1,
           p("acquisitions_less_disposal_of_non_produced_non_financial_ass"): -1}, "6.1 net lending (capital account)")
    ident(d, p("net_lending_to_the_rest_of_the_world_13_14_15_16_or_18_19"),
          {p("net_acquisition_of_foreign_financial_assets"): 1, p("net_incurrence_of_foreign_liabilities"): -1},
          "6.1 net lending (financial account, incl. errors and omissions)")
    both = cat("s6_1", "s1_1", "s1_9")
    ident(both, "s1_1.exports.current", {p("exports"): 1}, "6.1 exports = 1.1")
    ident(both, "s1_1.imports.current", {p("imports"): 1, p("adjustment_for_cif_in_import_of_services"): -1},
          "1.1 imports = 6.1 imports - CIF adjustment")
    ident(both, "s1_1.imports_services.current", {p("import_of_services_adjusted_for_cost_insurance_and_freight_c"): 1},
          "1.1 services imports = 6.1 item 19")
    ident(both, "s1_9.net_capital_inflow_from_row.current", {p("surplus_on_current_transactions"): -1},
          "1.9 net capital inflow = -(6.1 surplus)")


def test_statement_6_2_identities():
    d = ds("s6_2")
    p = "s6_2.{}.constant_2022_23".format
    ident(d, p("exports"), {p("goods_including_net_exports_of_goods_under_merchanting_and_m"): 1, p("exports.services"): 1},
          "6.2 exports")
    ident(d, p("imports"), {p("goods_including_manufacturing_services_on_physical_inputs_ow"): 1, p("imports.services"): 1},
          "6.2 imports")
    ident(d, p("net_primary_income_from_rest_of_the_world_2_3_5_6"), {
          p("compensation_of_employees_from_rest_of_the_world"): 1,
          p("property_and_entrepreneurial_income_from_rest_of_the_world"): 1,
          p("compensation_of_employees_to_rest_of_the_world"): -1,
          p("property_and_entrepreneurial_income_to_rest_of_the_world"): -1}, "6.2 net primary income")
    ident(d, p("import_of_services_adjusted_for_cost_insurance_and_freight_c"), {p("imports.services"): 1,
          p("adjustment_for_cif_in_import_of_services"): -1}, "6.2 CIF-adjusted services")
    ident(cat("s6_2", "s1_1"), "s1_1.exports.constant_2022_23", {p("exports"): 1}, "6.2 exports = 1.1 (constant)")


# ---------------------------------------------------------------------------------------------
# 4. identities across statements (the SAM's control totals must agree)
# ---------------------------------------------------------------------------------------------


def test_industry_statements_agree_with_1_1():
    both = cat("s1_1", "s1_6", "s1_7", "s1_8", "s1_10", "s7_1", "s7_2", "s7_3")
    for b in ("current", "constant_2022_23"):
        ident(both, f"s1_1.gva_basic.{b}", {f"s1_6.total.gva.{b}": 1}, f"1.6 total = 1.1 GVA {b}")
        ident(both, f"s1_1.cfc.{b}", {f"s1_8.total.cfc.{b}": 1}, f"1.8 total = 1.1 CFC {b}")
        ident(both, f"s1_1.gcf.{b}", {f"s1_10.total.gcf.{b}": 1, f"s1_1.valuables.{b}": 1},
              f"1.10 total + valuables = 1.1 GCF {b}", tol=5.0)
        ident(both, f"s1_6.total.gva.{b}", {f"s1_7.total.nva.{b}": 1, f"s1_8.total.cfc.{b}": 1}, f"GVA = NVA + CFC {b}")
    ident(both, "s1_1.gva_basic.current", {"s7_1.total.gva.current": 1}, "7.1 total GVA = 1.1")
    ident(both, "s1_10.total.gcf.current", {"s7_2.total.gcf_excl_valuables.current": 1}, "7.2 GCF = 1.10")
    ident(both, "s1_8.total.cfc.current", {"s7_2.total.cfc.current": 1}, "7.2 CFC = 1.8")
    ident(both, "s1_1.gfcf.current", {"s7_3.total.gfcf.current": 1}, "7.3 GFCF = 1.1")


def test_nva_equals_gva_minus_cfc_by_industry():
    frames = [ds(n).select("industry", "item_code", "price_basis", "period", "value") for n in ("s1_6", "s1_7", "s1_8")]
    w = pl.concat(frames).pivot(on="item_code", index=["industry", "price_basis", "period"], values="value").drop_nulls()
    assert w.height >= 140
    checks.assert_no_rows(w.filter((pl.col("gva") - pl.col("nva") - pl.col("cfc")).abs() > 1.0), "1.7 = 1.6 - 1.8")


def test_institutional_sector_accounts_agree():
    d = cat("s1_1", "s1_9", "s1_11", "s1_14")
    sec = ["nfc_public", "nfc_private", "fc_public", "fc_private", "gg", "households_npish"]
    g = "s1_14.{}.{}.current".format
    ident(d, "s1_1.gva_basic.current", {g(s, "gross_value_added_at_basic_prices"): 1 for s in sec}, "1.14 GVA = 1.1")
    ident(d, "s1_1.cfc.current", {g(s, "consumption_of_fixed_capital"): 1 for s in sec}, "1.14 CFC = 1.1", tol=5.0)
    ident(d, "s1_1.gcf.current", {**{g(s, "gross_capital_formation"): 1 for s in sec}, "s1_1.valuables.current": 1},
          "1.14 GCF + valuables = 1.1 GCF", tol=5.0)
    ident(d, "s1_1.gross_saving.current", {g(s, "gross_savings"): 1 for s in sec}, "1.14 saving = 1.1", tol=5.0)
    ident(d, "s1_1.pfce.current", {g("households_npish", "final_consumption_expenditure"): 1}, "1.14 HH FCE = PFCE")
    ident(d, "s1_1.gfce.current", {g("gg", "final_consumption_expenditure"): 1}, "1.14 GG FCE = GFCE")
    ident(d, "s1_1.gross_saving.current", {"s1_9.gross_savings.current": 1}, "1.9 = 1.1 gross saving")
    for s19, s14 in (("public_non_financial_corporations", "nfc_public"), ("private_non_financial_corporations",
                     "nfc_private"), ("public_financial_corporations", "fc_public"),
                     ("private_financial_corporations", "fc_private"), ("general_government", "gg"),
                     ("household_sector", "households_npish")):
        ident(d, f"s1_9.{s19}.current", {g(s14, "gross_savings"): 1}, f"1.9 = 1.14 saving ({s14})")
    ident(d, "s1_1.gfcf.current", {"s1_11.gross_fixed_capital_formation.current": 1}, "1.11 GFCF = 1.1")
    ident(d, g("households_npish", "gross_capital_formation"), {"s1_9.saving_in_physical_assets.current": 1},
          "household GCF (1.14) = saving in physical assets (1.9)")


def test_sector_gva_1_14_matches_production_statements():
    d = cat("s1_14", "s7_1a", "s7_1b", "s7_1c", "s8_15_1")
    ident(d, "s7_1c.total.gva.current", {"s1_14.households_npish.gross_value_added_at_basic_prices.current": 1},
          "7.1C = 1.14 households GVA")
    ident(d, "s7_1a.total.gva.current", {f"s1_14.{s}.gross_value_added_at_basic_prices.current": 1
          for s in ("nfc_public", "fc_public", "gg")}, "7.1A = 1.14 public NFC + public FC + GG GVA")
    ident(d, "s7_1b.total.gva.current", {f"s1_14.{s}.gross_value_added_at_basic_prices.current": 1
          for s in ("nfc_private", "fc_private")}, "7.1B = 1.14 private NFC + FC GVA")
    ident(d, "s8_15_1.total.gva.current", {"s1_14.gg.gross_value_added_at_basic_prices.current": 1}, "8.15.1 = 1.14 GG")
    ident(cat("s8_16", "s1_14"), "s8_16.administrative_departments.cfc.current",
          {"s1_14.gg.consumption_of_fixed_capital.current": 1}, "8.16 admin CFC = 1.14 GG CFC")


@pytest.mark.parametrize("stmt_sid, industry", [
    ("s8_1_1.crop_sector.gross_value_added", None), ("s8_2.gross_value_added", "livestock"),
    ("s8_3.gross_value_added", "forestry"), ("s8_4.gross_value_added", "fishing"),
    ("s8_5.gross_value_added", "mining"), ("s8_7.total.gross_value_added", "utilities"),
    ("s8_8.gross_value_added", "construction"), ("s8_9.trade_repair_hotels_and_restaurants.gross_value_added",
                                                 "trade_hotels"), ("s8_12.gross_value_added_s_12", "financial"),
    ("s8_13.gross_value_added", "real_estate_prof"), ("s8_14.total_other_services.gross_value_added", "other_services"),
])
def test_sector_detail_statements_match_1_6(stmt_sid, industry):
    name = stmt_sid.split(".")[0]
    d = cat(name, "s1_6", "s8_1_1")
    for b in ("current", "constant_2022_23"):
        if industry is None:  # crops in 1.6 = crop sector + irrigation (8.1.1)
            ident(d, f"s1_6.crops.gva.{b}", {f"{stmt_sid}.{b}": 1, f"s8_1_1.irrigation.gross_value_added.{b}": 1},
                  f"1.6 crops = 8.1.1 crops + irrigation {b}")
        else:
            ident(d, f"s1_6.{industry}.gva.{b}", {f"{stmt_sid}.{b}": 1}, f"1.6 {industry} = {name} {b}")


def test_transport_and_communication_detail():
    d = cat("s1_6", "s8_10", "s8_11")
    ident(d, "s1_6.transport_comm.gva.current", {"s8_10.total_transport_services.gross_value_added.current": 1,
          "s8_11.total_storage_communication_and_services_related_to_broadcas.gross_value_added.current": 1},
          "1.6 transport & communication = 8.10 + 8.11")
    ident(d, "s1_6.storage.gva.current", {"s8_11.storage.gross_value_added.current": 1}, "1.6 storage = 8.11")


def test_gross_value_added_in_detail_statements():
    for name, blocks in {
        "s8_7": ["electricity", "gas", "water_supply", "remediation_and_other_utility_services", "total"],
        "s8_9": ["trade_and_repair_services", "hotels_and_restaurants", "trade_repair_hotels_and_restaurants"],
        "s8_10": ["road_transport", "water_transport", "air_transport", "services_incidental_to_transport",
                  "total_transport_services"],
    }.items():
        for blk in blocks:
            for b in ("current", "constant_2022_23"):
                ident(ds(name), f"{name}.{blk}.gross_value_added.{b}", {f"{name}.{blk}.output.{b}": 1,
                      f"{name}.{blk}.input.{b}": -1, f"{name}.{blk}.fisim.{b}": -1}, f"{name} {blk}: GVA = output - input - FISIM")
                ident(ds(name), f"{name}.{blk}.net_value_added.{b}", {f"{name}.{blk}.gross_value_added.{b}": 1,
                      f"{name}.{blk}.cfc.{b}": -1}, f"{name} {blk}: NVA = GVA - CFC")
    for name in ("s8_6_1b", "s8_6_2b"):
        for b in ("current", "constant_2022_23"):
            ident(ds(name), f"{name}.gva.{b}", {f"{name}.gva_unadjusted_for_fisim.{b}": 1, f"{name}.fisim.{b}": -1},
                  f"{name}: GVA = unadjusted GVA - FISIM")
            ident(ds(name), f"{name}.nva.{b}", {f"{name}.gva.{b}": 1, f"{name}.cfc.{b}": -1}, f"{name}: NVA")


def test_pe_gva_8_17_2_agrees_with_1_6_and_adds_up():
    d = ds("s8_17_2")
    for b in ("current", "constant_2022_23"):
        for per_total, parts in (("primary", ["agri", "mining"]), ("secondary", ["manufacturing", "utilities",
                                  "construction"]), ("tertiary", ["trade_transport_comm", "financial_real_estate_prof",
                                  "public_admin_other"]), ("total", ["primary", "secondary", "tertiary"])):
            ident(d, f"s8_17_2.{per_total}.gva.{b}", {f"s8_17_2.{p}.gva.{b}": 1 for p in parts}, f"8.17.2 {per_total} {b}",
                  tol=5.0)
    j = d.join(ds("s1_6"), on=["industry", "item_code", "price_basis", "period"], suffix="_16")
    assert j.height == 2 * 3 * 6, j.height  # agri, mining, manufacturing, utilities, construction, total
    checks.assert_no_rows(j.filter((pl.col("value") - pl.col("value_16")).abs() > 1.0), "8.17.2 = 1.6 (2022-23..2024-25)")
    stages = dict(d.select("period", "estimate_stage").unique().iter_rows())
    assert stages == {"2022-23": "Final", "2023-24": "Final", "2024-25": "FRE", "2025-26": "PE"}


@pytest.mark.parametrize("name, basis", [("s8_18_2", "current"), ("s8_18_1", "constant_2022_23")])
def test_quarters_add_up_to_the_year(name, basis):
    q = ds(name).with_columns(pl.col("period").str.slice(3).alias("fy"))
    annual = q.group_by(["series_id", "item_code", "fy"]).agg(pl.col("value").sum(), pl.len().alias("n"))
    assert set(annual["n"]) == {4}
    ref = cat("s1_1", "s8_17_1")
    for item_q, item_a in (("gdp", "gdp"), ("pfce", "pfce"), ("gfce", "gfce"), ("gfcf", "gfcf"),
                           ("exports", "exports"), ("imports", "imports"), ("gva_at_basic_prices", "gva_basic")):
        code_q = {"pfce": "private_final_consumption_expenditure_pfce",
                  "gfce": "government_final_consumption_expenditure_gfce",
                  "gfcf": "gross_fixed_capital_formation_gfcf"}.get(item_q, item_q)
        a = annual.filter(pl.col("item_code") == code_q)
        for fy, total in zip(a["fy"], a["value"], strict=True):
            src = "s8_17_1" if fy == "2025-26" else "s1_1"
            code_a = {"gva_basic": "gva_basic" if src == "s1_1" else "gva_basic"}.get(item_a, item_a)
            want = checks.value(ref, f"{src}.{code_a}.{basis}", fy)
            assert abs(total - want) <= 5.0, (name, item_q, fy, total, want)
    ident(ds(name), f"{name}.gdp.{basis}", {f"{name}.exp.gdp.{basis}": 1}, f"{name}: GDP production = expenditure side")


# ---------------------------------------------------------------------------------------------
# 5. ranges, signs, continuity, bases and vintages
# ---------------------------------------------------------------------------------------------

# Level items that are legitimately negative somewhere in NAS 2026 (net or balancing items).
MAY_BE_NEGATIVE = (
    r"net_production_taxes|cis|changes_in_stocks|inventor|os$|os_mi|operating_surplus|discrepanc|surplus|general_government"
    r"|gg\.gross_savings|capital_transfer|net_lending|net_acquisition|net_incurrence|acquired_under_merchanting"
    r"|non_banking|loans_by_financial|postal_insurance|secondary_markets|government_securities|currency|loans"
    r"|other_financial_assets|other_liabilities|corporate_equity|acquisitions_less|net_investment_in_stock"
    r"|subsid|production_taxes|increment_in_livestock|valuables|cultivated_biological|net_value_added|nva"
    r"|gross_value_added|gva|consumption_expenditure|net_purchase|input|mixed|trade_debt|with_banks|deposits"
    r"|shares|mutual|claims|finances|gross_savings|less_financial|household_saving|net_financial_saving|primary_income"
    r"|net_primary|net_exports|goods_sold|merchanting|others|other_services|miscellaneous|fisim|allocation"
    # 4.2 capital expenditure on environment protection (COFOG 05) is published negative in 2022-23
    # and 2023-24 (-34.87, -345.28): capital transfers/CIS net of disposals. Kept as published.
    r"|capital_expenditure\.05"
    # 7.2A/7.3A public-sector GFCF in storage is published negative for 2022-23 (-184.17: disposals
    # exceed acquisitions). Kept as published and logged in docs/phase1/issues/mospi_nas_2026.md.
    r"|^s7_[23]a\.storage\.gfcf"
    # 7.3/7.3A/7.3B GFCF by asset: five small published negatives (-4 to -526 crore; storage IPP,
    # water-transport IPP/machinery, forestry structures), i.e. disposals > acquisitions.
    r"|^s7_3[ab]?\.(storage|water_transport|forestry)\.gfcf_"
)


def test_levels_are_non_negative_except_net_items():
    import re

    rx = re.compile(MAY_BE_NEGATIVE)
    for name in NEW_DATASETS:
        d = ds(name).filter((pl.col("unit") == "INR_crore") & (pl.col("value") < 0))
        bad = d.filter(~pl.col("item_code").map_elements(lambda s: bool(rx.search(s)), return_dtype=pl.Boolean)
                       & ~pl.col("series_id").map_elements(lambda s: bool(rx.search(s)), return_dtype=pl.Boolean))
        checks.assert_no_rows(bad.select("series_id", "period", "value"), f"{name}: unexpected negative level")


def test_percentages_indices_and_counts_in_range():
    for name in NEW_DATASETS:
        d = ds(name)
        checks.assert_no_rows(checks.check_range(d.filter(pl.col("unit") == "percent"), lo=-100, hi=200), f"{name} %")
        checks.assert_no_rows(checks.check_range(d.filter(pl.col("unit") == "index"), lo=50, hi=200), f"{name} index")
        checks.assert_no_rows(checks.check_range(d.filter(pl.col("unit") == "INR"), lo=50_000, hi=500_000),
                              f"{name} per-capita rupees")
    pop = ds("s1_2").filter(pl.col("unit") == "count")
    checks.assert_no_rows(checks.check_range(pop, lo=1.35e9, hi=1.45e9), "population")


def test_big_aggregates_move_smoothly():
    """Year-on-year change of the headline totals stays within 25% (the new series has no break)."""
    heads = [("s7_1", r"\.total\.(output|ic|gva|ce|cfc|os_mi)\."), ("s1_6", r"\.total\."), ("s1_14", r"gross_value_added"),
             ("s5_1", r"^s5_1\.total\."), ("s1_12", r"private_final_consumption"), ("s6_1", r"^s6_1\.(exports|imports)\.")]
    for name, rx in heads:
        d = ds(name).filter(pl.col("series_id").str.contains(rx) & (pl.col("unit") == "INR_crore"))
        assert d.height, name
        checks.assert_no_rows(checks.check_continuity(d, max_rel_change=0.25, min_abs_level=100_000),
                              f"{name}: break > 25%")


def test_new_base_labels():
    for name in NEW_DATASETS:
        d = ds(name)
        assert set(d["base_year"]) == {"2022-23"}, name
        assert set(d["vintage"]) == {"2026-08-31"}, name
        assert set(d["source_id"]) == {"mospi_nas_2026_publication"}, name
        assert set(d["price_basis"]) <= {"current", "constant_2022_23", "n/a"}, name
        assert set(d["status"]) == {"official"}, name
        for per, ptype, stage in d.select("period", "period_type", "estimate_stage").unique().iter_rows():
            fy = per if ptype == "fy" else per[3:] if ptype == "fq" else f"{int(per[:4]) - 1}-{per[2:4]}"
            assert stage == {"2022-23": "Final", "2023-24": "Final", "2024-25": "FRE", "2025-26": "PE"}[fy], (name, per)


def test_net_capital_stock_is_a_stock_at_end_march():
    for n in ("s7_4", "s7_4a", "s7_4b", "s7_4c"):
        d = ds(n)
        assert set(d["period_type"]) == {"date"} and set(d["stock_flow"]) == {"stock"}
        assert set(d["period"]) == {"2023-03-31", "2024-03-31", "2025-03-31"}


def test_all_statements_ingested():
    """Every statement file in the NAS 2026 listing (64; 'Abbreviation' is a glossary) has a dataset."""
    from pipeline.core.fetch import pinned_raw
    from pipeline.core.paths import Layout
    from pipeline.ingest import mospi_nas_2026 as M

    listing = pinned_raw(Layout.default(), U, M.SRC, "chapters_2861.json").read_json()
    stems = set(M._statement_urls(listing)) - {"Abbreviation"}
    assert len(stems) == 64
    built = {"s1_1", "s8_17_1", *NEW_DATASETS}
    assert {"s" + s.lower().replace(".", "_") for s in stems} == built


def test_derived_residuals_match_published_gaps():
    d = checks.load_dataset(U, f"{U}_derived_residuals")
    assert set(d["status"]) == {"derived"}
    # verify/mospi_nas.md 'Critical findings' 1 and 2 (read off 1.1, 1.9, 1.14)
    for sid, per, want in (("derived.household_residual.current", "2022-23", 812858),
                           ("derived.household_residual.current", "2023-24", 571133),
                           ("derived.household_residual.current", "2024-25", -128403),
                           ("derived.si_errors_omissions.current", "2022-23", 520083),
                           ("derived.si_errors_omissions.current", "2023-24", 358634),
                           ("derived.si_errors_omissions.current", "2024-25", -279181)):
        assert abs(checks.value(d, sid, per) - want) <= 1.0, (sid, per)
    prov = checks.load_provenance(U)
    rec = prov.filter(pl.col("prov_id").is_in(d["prov_id"].unique().to_list()))
    assert rec["inputs"].is_not_null().all() and rec["method"].is_not_null().all()
