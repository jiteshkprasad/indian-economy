"""Stated parameters of the capital_financial block (FR-cf-4: one place a verifier can audit).

Every entry here is a rule or an assumption, never a data value: data come from clean Parquet (read in
the other modules with ctx.value / ctx.rows) or from the DEPENDS blocks. Each assumption is repeated in
the method text of the provenance record that uses it and logged in docs/phase2/issues/capital_financial.md.
"""

from __future__ import annotations

# --- clean datasets read ---------------------------------------------------------------------------------
FSF = "rbi_financial_accounts_fsf_balance_sheets"  # RBI FSF 2023-24 (Jan 2026 release), single vintage
FSF7 = "rbi_financial_accounts_fsf_instrument_sector"  # FSF Statement 7 (instrument x sector totals)
FSF6 = "rbi_financial_accounts_fsf_fwtw"  # FSF Statements 6.13.a/b (from-whom-to-whom)
HH52 = "rbi_financial_accounts_hh_finsav_52ab"  # RBI T52(a)/(b), household financial saving and stocks
NAS19, NAS111, NAS114, NAS53 = (
    "mospi_nas_2026_s1_9",
    "mospi_nas_2026_s1_11",
    "mospi_nas_2026_s1_14",
    "mospi_nas_2026_s5_3",
)
NAS72A, NAS72B = "mospi_nas_2026_s7_2a", "mospi_nas_2026_s7_2b"
NAS_RESID = "mospi_nas_2026_derived_residuals"
SUT_USE = "io_tables_sut_use"
PRODUCT_MAP = "io_tables_sut_product_to_sam34"  # the committed SUT product -> commodity concordance
NSSF = "union_fiscal_nssf"
FA_EXP, FA_GIA, AFS = "union_fiscal_fa_expenditure", "union_fiscal_fa_gia", "union_fiscal_afs"
SF_APP = "state_fiscal_rbi_sf_appendices"
RBI_AC, RBI_K9B, RTP = (
    "rbi_banking_corporate_rbi_accounts",
    "rbi_banking_corporate_rbi_surplus_timing",
    "rbi_banking_corporate_rtp_banks",
)
# registry source ids, for records whose inputs come from several sources (the one the numbers mainly rest on)
SRC_NAS, SRC_SUT, SRC_FSF = "mospi_nas_2026_publication", "mospi_sut_2022base", "rbi_fsf_fof"
SRC_FA, SRC_BUDGET, SRC_RBI_AR, SRC_RTP, SRC_T52 = (
    "cga_finance_accounts_aag",
    "mof_union_budget_2026_27",
    "rbi_annual_report",
    "rbi_trend_progress",
    "rbi_hh_fin_savings",
)
LATEST = "latest"  # an explicit choice: NAS 2026 (31 Aug 2026), SUT and FSF carry one vintage each today
RBI_AC_VINTAGE = "2024-05-30"  # RBI Annual Report 2023-24 (the accounts of the reference year)
RTP_VINTAGE = "2024-12-26"  # RTP 2023-24: the only vintage with both the with- and without-merger lines
T52_VINTAGE = "latest"

# --- the SAM accounts this block works with ----------------------------------------------------------
K_DOMESTIC = ("K_HH", "K_NFPU", "K_NFPR", "K_RBI", "K_BANK", "K_NBFC", "K_INSP", "K_MUTF", "K_GCEN", "K_GSTA")
K_FC_GFCF = ("K_BANK", "K_NBFC", "K_INSP")  # FC sub-sectors that share the FC GFCF other than RBI's
E_TO_K = {
    "E_NFPU": "K_NFPU",
    "E_NFPR": "K_NFPR",
    "E_RBI": "K_RBI",
    "E_BANK": "K_BANK",
    "E_NBFC": "K_NBFC",
    "E_INSP": "K_INSP",
    "G_CEN": "K_GCEN",
    "G_STA": "K_GSTA",
}

# --- FSF leaf institutions (plan s.2.0) --------------------------------------------------------------
# leaf statement -> SAM capital account. FSF rows are not additive: only these statements are read.
# HDFC Ltd sat in fc_odc_hfc_dt, so the merger is internal to K_BANK (XR-6: E_BANK = K_BANK = FSF ODC).
SUB_ACCOUNT = {
    "fc_rbi": "K_RBI",
    "fc_odc_scb": "K_BANK",
    "fc_odc_coop": "K_BANK",
    "fc_odc_nbfc_dt": "K_BANK",
    "fc_odc_hfc_dt": "K_BANK",
    "fc_ofc_aifi": "K_NBFC",
    "fc_ofc_nbfc_ndt": "K_NBFC",
    "fc_ofc_hfc_ndt": "K_NBFC",
    "fc_ofc_sfc": "K_NBFC",
    "fc_ofc_sidc": "K_NBFC",
    "fc_ofc_mf": "K_MUTF",  # St 1.3.6 (the MF aggregate; its MMF/other sub-statements are not read)
    "fc_ofc_icpf_ins": "K_INSP",
    "fc_ofc_icpf_pf": "K_INSP",
    "gg_cen": "K_GCEN",
    "gg_sta": "K_GSTA",
    "nfc_pub": "K_NFPU",
    "nfc_pvt": "K_NFPR",
    "hh": "K_HH",
}
# FSF counterparty code of each leaf statement (the codes other statements use to name it)
SUB_CODE = {s: ("fc_odc" if s.startswith("fc_odc") else "fc_ofc" if s.startswith("fc_ofc") else s) for s in SUB_ACCOUNT}
# counterparty code -> SAM account; fc_ofc is split across its sub-sectors (OFC_KEY rule); hh, row dropped
CP_ACCOUNT = {
    "fc_rbi": "K_RBI",
    "fc_odc": "K_BANK",
    "gg_cen": "K_GCEN",
    "gg_sta": "K_GSTA",
    "nfc_pub": "K_NFPU",
    "nfc_pvt": "K_NFPR",
}
OFC_SUBS = tuple(s for s in SUB_ACCOUNT if s.startswith("fc_ofc"))
LEAF_CPS = ("fc_rbi", "fc_odc", "fc_ofc", "gg_cen", "gg_sta", "hh", "nfc_pub", "nfc_pvt", "other_resident", "row")
UNALLOCATED = "unallocated"  # 'all' minus the leaf counterparties of a statement line
OFC_DEFAULT = "K_NBFC"  # when the OFC sub-sector key is all zero (logged at each use)

# FSF instruments read at leaf level. f52 and the f6 components are published without counterparties.
PAIR_INSTRUMENTS = ("f21", "f22_f29", "f3", "f4", "f51", "f52")
OWN_INSTRUMENTS = ("f81", "f89")  # I_OTHR: each sector's own report, no pairing (plan s.2.7 Step A)
INPE_INSTRUMENTS = ("f61", "f62", "f63", "f64", "f66", "f6_pf")  # holder control; no non-HH counterparty
READ_INSTRUMENTS = PAIR_INSTRUMENTS + OWN_INSTRUMENTS + INPE_INSTRUMENTS
GG_CODES = ("gg_cen", "gg_sta")
FSF_TOP_INSTRUMENTS = ("f1", "f2", "f3", "f4", "f5", "f6", "f8", "other", "nec")  # add up to a statement's total

# which side's report is the control for each SAM instrument (plan s.2.7 Step A, with the reason there)
CONTROL = {
    "I_CURR": "issuer",  # RBI balance sheet
    "I_DEPO": "issuer",  # deposit-takers' returns (RBI's reserve liabilities beat banks' own report)
    "I_SSAV": "issuer",  # Finance Accounts / NSSF
    "I_GSEC": "issuer",  # debt management knows its holders
    "I_CBND": "holder",  # portfolio returns; issuer side distorted by the HDFC reclassification
    "I_LOAN": "holder",  # lenders' loan returns (BSR)
    "I_EQTY": "holder",  # issuer side is book-value paid-up capital
    "I_MFUN": "issuer",  # AMFI/SEBI-consistent MF sector total (holders key its split)
    "I_INPE": "holder",  # NAS households; issuer side includes revaluation
}
# a control-side counterparty that is `other_resident` or unallocated goes to this account, else it is not
# written and falls into K9 (plan s.2.7 Step B): currency and deposits of unnamed residents are private NFCs'
UNNAMED_DEFAULT = {"I_CURR": "K_NFPR", "I_DEPO": "K_NFPR"}
MF_HOLDER_EXCLUDED = ("fc_ofc_sfc", "fc_ofc_sidc")  # implausible MF-unit holdings (plan s.2.7 Step C3)
# FSF insurance/pension liabilities (published without counterparties) that NAS 5.3 household lines replace
# (K7b hh_cp: life insurance -> K_INSP; PF & pension -> Centre/States by their f6_pf, rest K_INSP). Every other
# non-household I_INPE cell and every F52 liability outside the MF sector is not written and falls into K9
# (logged at build; verification V-CF-4).
INPE_NAS_REPLACED = (
    ("fc_ofc_icpf_ins", "f62"),
    ("fc_ofc_icpf_pf", "f63"),
    ("fc_ofc_icpf_pf", "f6_pf"),
    ("gg_cen", "f6_pf"),
    ("gg_sta", "f6_pf"),
)

# roles of the reconciled FSF entries (plan s.2.1 K7/K8)
CONTROL_TOL = 0.10  # anchored tolerance of a control-side cell that is a pure sum of published reports
K9B_TOL = 0.02  # RBI surplus payable/receivable (RBI Annual Report figure, cash vs accrual timing)
CIS_TOL = 0.001  # I3a NAS-sector values (rounding only)

# --- I1a GFCF by commodity x investor (plan s.2.2) -----------------------------------------------------
# asset group of each commodity with SUT GFCF (NAS 1.11 asset classes); used in the RAS prior only
ASSET_OF = {
    "C_CNST": "dwellings_other_buildings_and_structures",
    "C_TREQ": "machinery_and_equipment",
    "C_ELEQ": "machinery_and_equipment",
    "C_MACH": "machinery_and_equipment",
    "C_WOOD": "machinery_and_equipment",
    "C_GJOM": "machinery_and_equipment",
    "C_PHRM": "machinery_and_equipment",
    "C_ITSV": "intellectual_property_products",
    "C_EDUC": "intellectual_property_products",
    "C_OSRV": "intellectual_property_products",
    "C_CROP": "cultivated_biological_resources",
    "C_LVST": "cultivated_biological_resources",
}
NAS_SECTORS = {  # NAS 1.11 / 1.14 sector series stems
    "nfc_pub": ("public_non_financial_corporations", "nfc_public"),
    "nfc_pvt": ("private_non_financial_corporations", "nfc_private"),
    "fc_pub": ("public_financial_corporations", "fc_public"),
    "fc_pvt": ("private_financial_corporations", "fc_private"),
    "gg": ("general_government", "gg"),
    "hh": ("household_sector", "households_npish"),
}
RAS_TOL = 1e-9  # relative
RAS_MAX_ITER = 10000
# Union capital outlay heads that are not general government GFCF in NAS (departmental commercial
# enterprises and financial investments): Railways 5002/5003, Posts 5201, Telecom 5225/5275, investment heads
UNION_NON_GG_HEADS = ("5002", "5003", "5201", "5225", "5275", "4416", "5465", "5466", "5467")

# --- D3 (plan s.2.3) --------------------------------------------------------------------------------
D3_CORPORATE = ("K_NFPU", "K_NFPR", "K_RBI", "K_BANK", "K_NBFC", "K_INSP")  # remainder pro rata to GCF

# --- K9 (plan s.2.10, XR-17) ------------------------------------------------------------------------
K9_MIN = 1.0  # |K9_s| below Rs 1 crore: no entry (logged)

# --- RoW counterparts (plan s.2.9) --------------------------------------------------------------------
# a RoW counterpart named only "FC" is split by FSF RoW-held equity stocks of FC issuers at 2023-03-31
FC_ROW_KEY_PERIOD = "2023-03-31"
FC_ROW_KEY_SUBS = {
    "fc_odc_scb": "K_BANK",
    "fc_odc_coop": "K_BANK",
    "fc_odc_nbfc_dt": "K_BANK",
    "fc_odc_hfc_dt": "K_BANK",
    "fc_ofc_nbfc_ndt": "K_NBFC",
    "fc_ofc_hfc_ndt": "K_NBFC",
    "fc_ofc_sidc": "K_NBFC",
    "fc_ofc_aifi": "K_NBFC",
    "fc_ofc_sfc": "K_NBFC",
    "fc_ofc_icpf_ins": "K_INSP",
}
