"""Independent verification of the top-flows time series (Phase 2 verifier, 2026-09-30; SPEC s.3 rule 3).

This file does NOT import pipeline.timeseries (no builder code) and does not use polars. Every expected
number is recomputed here with DuckDB SQL straight from data/clean/<unit>/<dataset>.parquet, using a flow
specification written from docs/phase2/plans/timeseries.md s.2.1-2.3 (dataset, series ids, coefficients,
year ranges and base years), not from pipeline/timeseries/flows.yaml. It is compared with the written
outputs in data/timeseries/ (top_flows, definitions, coverage, _provenance).

Rules applied independently (plan s.2.0): FY rows only; budget BE/RE rows never used; the latest vintage per
(series, period); NAS API old-base revision rounds taken chronologically latest; status `official` only for
a published value or a +1 sum of official lines of one table, otherwise `derived` (sign flips,
differences, F10's net OS/MI + CFC, the back-series current-account derivation, links); the linked variant
linked(t) = old(t) x new(2022-23) / old(2022-23) for t <= 2021-22.

Scope of the checks:
- a stratified sample (every (flow, variant, base_year, segment) stratum: first, middle, last and every
  4th FY; >= 20% of all rows, every flow, both NAS bases and the base-less series, early/middle/late years)
  checked in depth: value, status, vintage, estimate stage, series ids and the provenance inputs;
- a full census of the row keys and of every non-linked value, and every linked value;
- the joins that justify the no-splice precedence, the revision-round rule, coverage by year (plan s.2.6);
- the SAM definitions evaluated with plain SQL on the built blocks' entries (pre-balancing), with the
  guards (unlisted refs, missing selectors, entries matched twice);
- manifest coverage, the CLI command and determinism (the CLI run twice into scratch layouts under
  PYTHONHASHSEED 0/1 and 1/4 threads, byte-identical to the committed files).

Defects are recorded as strict xfails (docs/phase2/verify/timeseries.md): TSV-1 the old-base segment code
'NO' is written as 'False' (YAML 1.1 boolean); TSV-2 RBI HBS Table 12 rows before 2011-12 are labelled base
2011-12 although the clean records carry no base (earlier-base figures); TSV-3 F27/F28 pensions are class B
on a different concept from the government block's R9 controls; TSV-4 the F26 bridge contradicts fincorp's
State-interest concept; TSV-5 the M13 link refusal reason contradicts the plan's own 0.02 rule. When a
defect is fixed the xfail turns into XPASS (strict) and the marker must be removed.

Builder's fix pass (2026-09-30, recorded in docs/phase2/issues/timeseries.md; to be re-verified): TSV-1,
TSV-2, TSV-4 and TSV-5 are fixed and their markers removed. For TSV-2 the plan spec below gives the T12
segments base_year None (the verifier's stated fix), so F37's linked rows start in 2011-12 (2,504 rows). TSV-3
was fixed by the verifier's first option (F27/F28 class C with clean-series bridges), so its test now checks
TS + bridge against the SAM cells instead of a class-B band.

Re-verification (wave C, 2026-10-01; docs/phase2/verify/timeseries.md): every wave-B change above was
recomputed from clean data with DuckDB and confirmed. Two changes in this pass: (1) closure-18: F35 (household
saving) and M13 (household GDI) contain closure's K4a, which equals NAS 1.9 only after balancing (the K4
constraint; closure plan C7 option A). On the pre-balancing block entries they must miss by the same K4 gap and
by nothing else; every class-A flow, F35 and M13 included, is then checked on the balanced SAM
(data/sam/2023-24/sam_entries_balanced.parquet). (2) The TSV-3 test takes its bridge series from the
government block's R9 control methods, written here, instead of trusting pipeline/timeseries/explanations.yaml,
and requires the builder's file to list the same series.
"""

# ruff: noqa: E501  (the plan's flow table and the join pairs are kept one entry per line so each reads as one rule)

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from functools import cache
from pathlib import Path

import duckdb
import pytest
import yaml

pytestmark = [pytest.mark.quality, pytest.mark.sam]

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean"
TSD = ROOT / "data" / "timeseries"
BLOCKS = ROOT / "data" / "sam" / "2023-24" / "blocks"
OLD, NEW, YEAR = "2011-12", "2022-23", "2023-24"
PUB, LINK = "published", "linked_2022_23"
OUT_FILES = (
    "top_flows.parquet",
    "top_flows_definitions.parquet",
    "top_flows_coverage.parquet",
    "top_flows_sam_check.parquet",
    "_provenance.parquet",
)

# ------------------------------------------------------------------------------------------------
# the plan's flow specification (docs/phase2/plans/timeseries.md s.2.1-2.3; s.8 cross-plan review)
# ------------------------------------------------------------------------------------------------
S11, S19, S53 = (f"mospi_nas_2026_oldbase_nas2025_{s}" for s in ("s1_1", "s1_9", "s5_3"))
N11, N19, N53 = (f"mospi_nas_2026_{s}" for s in ("s1_1", "s1_9", "s5_3"))
BACK, API22, API11 = (
    "mospi_nas_2026_api_b2011_back",
    "mospi_nas_2026_api_b2022_annual",
    "mospi_nas_2026_api_b2011_annual",
)
SOA15, SOA40 = "mospi_nas_2026_oldbase_soa_s1_15", "mospi_nas_2026_oldbase_soa_s4_0"
T12 = "rbi_financial_accounts_hbs_saving"
RB, KF, AT, FT = (
    "union_fiscal_rb_receipts",
    "state_fiscal_fc16_kfi",
    "state_fiscal_rbi_sf_app_tables",
    "state_fiscal_fc16_transfers",
)
BI, BO, FI = (
    "external_sector_invisibles_annual",
    "external_sector_bop_overall_annual",
    "external_sector_foreign_investment",
)
FF, AF, EP, FS = (
    "rbi_financial_accounts_fsf_instrument_sector",
    "union_fiscal_afs",
    "union_fiscal_exp_profile",
    "state_fiscal_fc16_subsidies",
)
ROUNDS = "ROUNDS"  # a term (ROUNDS, stem): the NAS API old-base annual series, latest revision round per FY
ROUND_ORDER = (  # chronological, latest last
    "first_advance_estimates",
    "second_advance_estimates",
    "provisional_estimates",
    "first_revised_estimates",
    "second_revised_estimates",
    "third_revised_estimates",
    "final_estimates",
    "additional_revision",
)
PLAN_CODES = {
    "NB",
    "NO",
    "NN",
    "NP",
    "NS",
    "NA",
    "T12",
    "RB",
    "KF",
    "AT",
    "FT",
    "AF",
    "EP",
    "FS",
    "RS",
    "FF",
    "BI",
    "BO",
    "FI",
    "NR",
}
LINK_WHITELIST = {"M01", "M02", "F01", "F03", "M03", "F05", "F06", "F07", "M06", "F37"}  # plan s.2.5


def seg(code, ds, base, lo, hi, terms, variant=PUB, derived=False):
    return {
        "code": code,
        "ds": ds,
        "base": base,
        "lo": lo,
        "hi": hi,
        "terms": terms,
        "variant": variant,
        "derived": derived,
    }


def t(sid, coef=1.0, hi=None):
    return (sid, coef, hi)


def nas(item, nb_lo="1950-51", no_item=None, np_id=None, nb=True, np_=True):
    out = [seg("NB", BACK, OLD, nb_lo, "2010-11", [t(f"api.{item}.current")])] if nb else []
    out.append(seg("NO", S11, OLD, "2011-12", "2023-24", [t(f"oldbase_nas2025_s1_1.{no_item or item}.current")]))
    out.append(seg("NN", N11, NEW, "2022-23", "2024-25", [t(f"s1_1.{no_item or item}.current")]))
    if np_:
        out.append(
            seg("NP", API22, NEW, "2025-26", "2025-26", [t(np_id or f"api.{item}.rev_provisional_estimates.current")])
        )
    return out


def on(ds_old, ds_new, pre_old, pre_new, items):
    return [
        seg("NO", ds_old, OLD, "2011-12", "2023-24", [t(f"{pre_old}.{i}.current") for i in items]),
        seg("NN", ds_new, NEW, "2022-23", "2024-25", [t(f"{pre_new}.{i}.current") for i in items]),
    ]


def s19(*items):
    return on(S19, N19, "oldbase_nas2025_s1_9", "s1_9", items)


def s53(*items):
    return on(S53, N53, "oldbase_nas2025_s5_3", "s5_3", items)


def s11(*items):
    return on(S11, N11, "oldbase_nas2025_s1_1", "s1_1", items)


R0021 = ("collections", "health_and_education_cess", "interest_recoveries", "miscellaneous_receipts", "penalties", "surcharge",
         "tax_under_black_money")  # fmt: skip
PIT = [t(f"rb.tr.0021.{x}") for x in R0021] + [t("rb.tr.0034.security_transaction_tax")]  # STT in T_PIT (D2-12)

SPEC: dict[str, list[dict]] = {
    "F01": nas("pfce"),
    "F02": nas("gfce"),
    "F03": nas("gfcf"),
    "F04": nas("valuables", nb_lo="1999-00"),
    "F05": s11("exports_goods"),
    "F06": s11("exports_services"),
    "F07": s11("imports_goods"),
    "F08": [seg("NN", N11, NEW, "2022-23", "2024-25", [t("s1_1.imports_services.current")])],
    "F09": [seg("NS", SOA15, OLD, "2011-12", "2022-23", [t("oldbase_soa_s1_15.generation_of_income.uses.d1.current")]),
            seg("NN", "mospi_nas_2026_s7_1", NEW, "2022-23", "2024-25", [t("s7_1.total.ce.current")])],
    "F10": [seg("NS", SOA15, OLD, "2011-12", "2022-23", [t("oldbase_soa_s1_15.generation_of_income.uses.b2n_b3n.current"),
                                                          t("oldbase_soa_s1_15.production.uses.p51c.current")], derived=True),
            seg("NN", "mospi_nas_2026_s7_1", NEW, "2022-23", "2024-25", [t("s7_1.total.os_mi.current"), t("s7_1.total.cfc.current")],
                derived=True)],
    "F11": nas("primary_income_row_net", np_=False),
    "F12": s11("taxes_on_products"),
    "F13": [seg("NO", S11, OLD, "2011-12", "2023-24", [t("oldbase_nas2025_s1_1.subsidies_on_products.current", -1)]),
            seg("NN", N11, NEW, "2022-23", "2024-25", [t("s1_1.subsidies_on_products.current", -1)])],
    "F14": [seg("RB", RB, None, "2022-23", "2024-25", [t("rb.tr.0005.central_goods_and_services_tax_cgst"),
            t("rb.tr.0008.integrated_goods_and_services_tax_igst"), t("rb.tr.0009.gst_compensation_cess")])],
    "F15": [seg("KF", KF, None, "2017-18", "2023-24", [t("kfi.a_1_1_2-state_goods_and_service_tax.in.all_states_28")])],
    "F16": [seg("RB", RB, None, "2022-23", "2024-25", [t("rb.tr.total.total_union_excise_duties")])],
    "F17": [seg("RB", RB, None, "2022-23", "2024-25", [t("rb.tr.total.total_customs")])],
    "F18": [seg("KF", KF, None, "2011-12", "2023-24", [t("kfi.a_1_1_1-taxes_on_sales_trade_etc.in.all_states_28")])],
    "F19": [seg("KF", KF, None, "2011-12", "2023-24", [t("kfi.a_1_1_3-state_excise.in.all_states_28")])],
    "F20": [seg("KF", KF, None, "2011-12", "2023-24", [t("kfi.a_1_1_5-stamps_and_registration_fees.in.all_states_28")])],
    "F21": [seg("RB", RB, None, "2022-23", "2024-25", [t("rb.tr.total.total_corporation_tax")])],
    "F22": [seg("RB", RB, None, "2022-23", "2024-25", PIT)],
    "F23": [seg("FT", FT, None, "1952-53", "2006-07", [t("tsm.states_share.actuals")]),
            seg("AT", AT, None, "2007-08", "2023-24", [t("at2.i-states_share_in_central_taxes.actuals")])],
    "F24": [seg("FT", FT, None, "1952-53", "2006-07", [t("tsm.total_grants.actuals")]),
            seg("AT", AT, None, "2007-08", "2023-24", [t("at2.ii-grants_from_the_centre.actuals")])],
    "F25": [seg("AF", AF, None, "2022-23", "2023-24", [t("afs.cfi_rev_disbursements.2049")])],
    "F26": [seg("KF", KF, None, "2011-12", "2023-24", [t("kfi.b_1_a-interest_payments.in.all_states_28")])],
    "F27": [seg("AF", AF, None, "2022-23", "2023-24", [t("afs.cfi_rev_disbursements.2071")])],
    "F28": [seg("KF", KF, None, "2011-12", "2023-24", [t("kfi.b_1_b-pension_and_other_retirement_benefits.in.all_states_28")])],
    "F29": [seg("EP", EP, None, "2022-23", "2024-25", [t("stat7.food")]),
            seg("FS", FS, None, "2018-19", "2023-24", [t("sub.food.in.gg_centre")], variant="fc16_definition")],
    "F30": [seg("FS", FS, None, "2018-19", "2021-22", [t("sub.fertilizer.in.gg_centre", -1)]),
            seg("EP", EP, None, "2022-23", "2024-25", [t("stat7.fertiliser", -1)])],
    "F31": [seg("RS", "rbi_banking_corporate_rbi_surplus_timing", None, "2022-23", "2025-26",
                [t("r6.surplus_received_by_centre_cash.current")])],
    "F32": s19("general_government"),
    "F33": [seg("NA", API11, OLD, "2011-12", "2023-24", [t((ROUNDS, "api.gfcf.sec_gg"))]),
            seg("NN", "mospi_nas_2026_s1_11", NEW, "2022-23", "2024-25", [t("s1_11.general_government.current")])],
    "F34": [seg("FF", FF, None, "2012-13", "2023-24", [t("fsf7.gg.liabilities.transaction.f3.current")])],
    "F35": s19("household_sector"),
    "F36": [seg("T12", T12, None, "1983-84", "2010-11", [t("t12.assets.financial_assets.current")])] + s53("gross_financial_saving"),
    "F37": [seg("T12", T12, None, "1983-84", "2010-11", [t("t12.liabilities.financial_liabilities.current")])]
           + s53("financial_liabilities"),
    "F38": s19("saving_in_physical_assets"),
    "F39": [seg("T12", T12, None, "1983-84", "2010-11", [t("t12.assets.bank_deposits.current")])]
           + s53("with_banks", "with_co_operative_banks_and_societies"),
    "F40": [seg("T12", T12, None, "1983-84", "2010-11", [t("t12.assets.shares_debentures.current"),
                                                         t("t12.assets.units_of_uti.current", hi="2008-09")])]
           + s53("shares_and_debentures"),
    "F41": [seg("T12", T12, None, "1983-84", "2010-11", [t("t12.assets.life_insurance_fund.current"), t("t12.assets.pf_pension_fund.current")])]
           + s53("insurance_funds", "provident_and_pension_funds"),
    "F42": [seg("T12", T12, None, "1983-84", "2010-11", [t("t12.liabilities.bank_advances.current")])]
           + s53("bank_advances", "loans_and_advances_by_co_operative_banks_and_societies"),
    "F43": [seg("BI", BI, None, "2006-07", "2025-26", [t("invis.inr.private_transfers.receipts.current")])],
    "F44": [seg("BI", BI, None, "2006-07", "2025-26", [t("invis.inr.private_transfers.payments.current")])],
    "F45": s19("private_non_financial_corporations"),
    "F46": [seg("NA", API11, OLD, "2011-12", "2023-24", [t((ROUNDS, "api.gfcf.sec_nfc_private"))]),
            seg("NN", "mospi_nas_2026_s1_11", NEW, "2022-23", "2024-25", [t("s1_11.private_non_financial_corporations.current")])],
    "F47": s19("financial_corporations"),
    "F48": [seg("FF", FF, None, "2012-13", "2023-24", [t("fsf7.nfc_pub.liabilities.transaction.total.current"),
                                                        t("fsf7.nfc_pvt.liabilities.transaction.total.current")])],
    "F49": [seg("NB", BACK, OLD, "1950-51", "2010-11", [t("api.gcf_incl_errors_omissions.current"), t("api.gross_saving.current", -1)])]
           + s19("net_capital_inflow_from_row"),
    "F50": [seg("BI", BI, None, "2006-07", "2025-26", [t("invis.inr.income.investment.payments.current")])],
    "F51": [seg("FI", FI, None, "2004-05", "2025-26", [t("t143.inr.fdi_to_india_net.current")])],
    "F52": [seg("BO", BO, None, "2020-21", "2025-26", [t("bop_old.inr.ka.portfolio.in_india.net.current")]),
            seg("FI", FI, None, "2004-05", "2019-20", [t("t143.inr.portfolio_net.current")], variant="proxy_total_portfolio")],
    "F53": [seg("NR", "external_sector_nri_deposits", None, "2007-08", "2019-20", [t("nri.flow.inr.total.current")]),
            seg("BO", BO, None, "2020-21", "2025-26", [t("bop_old.inr.ka.banking_capital.commercial_banks.nri_deposits.net.current")])],
    "F54": [seg("BO", BO, None, "2020-21", "2025-26", [t("bop_old.inr.monetary_movements.reserves.net.current", -1)])],
    "M01": nas("gdp"),
    "M02": nas("gva", no_item="gva_basic", np_id="api.gva.ind_total.rev_provisional_estimates.current"),
    "M03": nas("exports"),
    "M04": [seg("NN", N11, NEW, "2022-23", "2024-25", [t("s1_1.imports.current")]),
            seg("NP", API22, NEW, "2025-26", "2025-26", [t("api.imports.rev_provisional_estimates.current")])],
    "M05": [seg("NN", "mospi_nas_2026_s6_1", NEW, "2022-23", "2024-25", [t("s6_1.adjustment_for_cif_in_import_of_services.current")])],
    "M06": [seg("NB", BACK, OLD, "1950-51", "2010-11", [t("api.imports.current")]),
            seg("NO", S11, OLD, "2011-12", "2023-24", [t("oldbase_nas2025_s1_1.imports.current")]),
            seg("NN", "mospi_nas_2026_s6_1", NEW, "2022-23", "2024-25", [t("s6_1.imports.current")])],
    "M07": [seg("NB", BACK, OLD, "1950-51", "2010-11", [t("api.net_taxes_on_products.current")]),
            seg("NO", S11, OLD, "2011-12", "2023-24", [t("oldbase_nas2025_s1_1.taxes_on_products.current"),
                                                       t("oldbase_nas2025_s1_1.subsidies_on_products.current", -1)]),
            seg("NN", N11, NEW, "2022-23", "2024-25", [t("s1_1.taxes_on_products.current"), t("s1_1.subsidies_on_products.current", -1)]),
            seg("NP", API22, NEW, "2025-26", "2025-26", [t("api.net_taxes_on_products.rev_provisional_estimates.current")])],
    "M08": [seg("NS", SOA40, OLD, "2011-12", "2022-23", [t("oldbase_soa_s4_0.secondary_distribution_of_income.resources.d5.current")]),
            seg("RB", RB, None, "2022-23", "2024-25", [t("rb.tr.total.total_corporation_tax")] + PIT)],
    "M09": [seg("T12", T12, None, "1983-84", "2010-11", [t("t12.assets.financial_assets.current"),
                                                         t("t12.liabilities.financial_liabilities.current", -1)])]
           + s53("net_financial_saving_of_household_sector_1_4"),
    "M10": nas("cis"),
    "M11": nas("other_current_transfers_row_net", np_=False),
    "M12": [seg("NN", "mospi_nas_2026_derived_residuals", NEW, "2022-23", "2024-25", [t("derived.household_residual.current")])],
    "M13": [seg("NO", "mospi_nas_2026_oldbase_nas2025_s1_14", OLD, "2011-12", "2023-24",
                [t("oldbase_nas2025_s1_14.households_npish.gross_disposable_income.current")]),
            seg("NN", "mospi_nas_2026_s1_14", NEW, "2022-23", "2024-25", [t("s1_14.households_npish.gross_disposable_income.current")])],
    "M14": [seg("FT", FT, None, "1952-53", "2023-24", [t("tsm.gtr.actuals")]),
            seg("RB", RB, None, "2024-25", "2024-25", [t("rb.tr.total.total_tax_revenue"), t("rb.tr.0710.less_states_share", -1),
                t("rb.tr.total.net_less_nccd_transferred_to_the_national_disaster_response_fund", -1)])],
    "M15": [seg("NS", SOA40, OLD, "2011-12", "2022-23", [t("oldbase_soa_s4_0.allocation_of_primary_income.uses.d4.current")])],
}  # fmt: skip


# ------------------------------------------------------------------------------------------------
# readers (DuckDB only)
# ------------------------------------------------------------------------------------------------


@cache
def con() -> duckdb.DuckDBPyConnection:
    for f in OUT_FILES:
        if not (TSD / f).exists():
            pytest.fail(f"data/timeseries/{f} missing: run `uv run python -m pipeline timeseries`")
    return duckdb.connect()


def q(sql: str) -> list[tuple]:
    return con().sql(sql).fetchall()


def records(path: Path, where: str = "true") -> list[dict]:
    rel = con().sql(f"select * from '{path.as_posix()}' where {where}")
    cols = rel.columns
    return [dict(zip(cols, r, strict=True)) for r in rel.fetchall()]


@cache
def paths() -> dict[str, str]:
    out = {}
    for cat in sorted(CLEAN.glob("*/_datasets.json")):
        for ds in json.loads(cat.read_text(encoding="utf-8")):
            out[ds] = (cat.parent / f"{ds}.parquet").as_posix()
    return out


def fy(y: int) -> str:
    return f"{y}-{(y + 1) % 100:02d}"


def fys(lo: str, hi: str) -> list[str]:
    return [fy(y) for y in range(int(lo[:4]), int(hi[:4]) + 1)]


def vkey(v: str) -> tuple[dt.date, str]:
    p = [int(x) for x in v.split("-")]
    if len(p) == 1:
        return dt.date(p[0], 12, 31), v
    if len(p) == 2:
        return dt.date(p[0] + (p[1] == 12), p[1] % 12 + 1, 1) - dt.timedelta(days=1), v
    return dt.date(*p), v


COLS = "series_id, period, period_type, value, unit, price_basis, vintage, estimate_stage, status, prov_id, base_year"


@cache
def latest(ds: str, sid: str) -> dict[str, dict]:
    """{FY: clean row}: FY rows, BE/RE excluded, the latest vintage of each period."""
    out: dict[str, dict] = {}
    for r in records(Path(paths()[ds]), f"series_id = '{sid}'"):
        if r["period_type"] != "fy" or r["estimate_stage"] in ("BE", "RE"):
            continue
        if r["period"] not in out or vkey(r["vintage"]) > vkey(out[r["period"]]["vintage"]):
            out[r["period"]] = r
    return out


@cache
def latest_round(ds: str, stem: str) -> dict[str, dict]:
    """{FY: clean row} of stem.rev_<round>.current, the chronologically latest round of each FY."""
    by: dict[str, list] = defaultdict(list)
    for r in records(Path(paths()[ds]), f"series_id like '{stem}.rev_%.current'"):
        rnd = r["series_id"][len(stem) + 5 : -len(".current")]
        assert rnd in ROUND_ORDER, f"unknown NAS API revision round {rnd!r}"
        by[r["period"]].append((ROUND_ORDER.index(rnd), r))
    return {p: max(v, key=lambda x: x[0])[1] for p, v in by.items()}


@cache
def expected() -> dict[tuple, dict]:
    """{(flow, variant, base_year, FY): {value, parts: [(coef, clean row)], code, derived}} from the plan spec."""
    exp = {}
    for flow, segs in SPEC.items():
        for s in segs:
            data = [(c, hi, latest_round(s["ds"], sid[1]) if isinstance(sid, tuple) else latest(s["ds"], sid))
                    for sid, c, hi in s["terms"]]  # fmt: skip
            for p in fys(s["lo"], s["hi"]):
                parts = [(c, d[p]) for c, hi, d in data if not (hi and p > hi)]
                assert all(p in d for c, hi, d in data if not (hi and p > hi)), (flow, s["code"], p, "missing input")
                exp[(flow, s["variant"], s["base"], p)] = {
                    "value": sum(c * r["value"] for c, r in parts),
                    "parts": parts,
                    "code": s["code"],
                    "derived": s["derived"] or any(c != 1 for c, _ in parts),
                }
    return exp


def key(r: dict) -> tuple:
    return (r["flow_id"], r["variant"], r["base_year"], r["period"])


@cache
def rows() -> dict[tuple, dict]:
    return {key(r): r for r in records(TSD / "top_flows.parquet")}


@cache
def prov() -> dict[str, dict]:
    return {r["prov_id"]: r for r in records(TSD / "_provenance.parquet")}


@cache
def defs() -> dict[str, dict]:
    return {r["flow_id"]: r for r in records(TSD / "top_flows_definitions.parquet")}


@cache
def sample() -> list[tuple]:
    """Stratified sample: per (flow, variant, base_year, segment) the first, middle and last FY and every 4th."""
    strata: dict[tuple, list] = defaultdict(list)
    for k, r in rows().items():
        strata[(r["flow_id"], r["variant"], str(r["base_year"]), r["segment"])].append(k)
    out = set()
    for ks in strata.values():
        ks = sorted(ks, key=lambda k: k[3])
        n = len(ks)
        out |= {ks[i] for i in {0, n // 2, n - 1} | set(range(0, n, 4))}
    return sorted(out, key=str)


def rel_eq(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6 * max(1.0, abs(b))


def ratios(flow: str) -> tuple[float | None, float | None]:
    e = expected()
    out = []
    for p in ("2022-23", "2023-24"):
        o, n = e.get((flow, PUB, OLD, p)), e.get((flow, PUB, NEW, p))
        out.append(n["value"] / o["value"] if o and n and o["value"] else None)
    return out[0], out[1]


# ------------------------------------------------------------------------------------------------
# rows: census of keys and values, stratified deep sample
# ------------------------------------------------------------------------------------------------


def test_row_keys_equal_the_plan_spec():
    """Every (flow, variant, base_year, FY) of the plan exists once, and nothing else (linked rows aside)."""
    got = {k for k in rows() if k[1] != LINK}
    exp = set(expected())
    assert got == exp, (sorted(exp - got, key=str)[:10], sorted(got - exp, key=str)[:10])
    assert len(got) == 2028 and len(rows()) == 2504  # 476 linked rows: F37's link now starts in 2011-12 (TSV-2)
    assert {k[0] for k in rows()} == set(SPEC) and len(SPEC) == 69


def test_stratified_sample_covers_at_least_20_percent_and_every_stratum():
    s = sample()
    assert len(s) >= 0.20 * len(rows()), (len(s), len(rows()))
    assert {k[0] for k in s} == set(SPEC), "every flow is sampled"
    assert {k[1] for k in s} == {PUB, LINK, "fc16_definition", "proxy_total_portfolio"}
    assert {k[2] for k in s} == {OLD, NEW, None}, "both NAS bases and the base-less series"
    years = [int(k[3][:4]) for k in s]
    assert min(years) <= 1955 and any(1990 <= y <= 2010 for y in years) and max(years) >= 2025


def test_sampled_rows_recompute_from_clean_data():
    """Value, status, vintage, estimate stage and series ids of every sampled non-linked row."""
    e = expected()
    bad = []
    for k in sample():
        if k[1] == LINK:
            continue
        r, x = rows()[k], e[k]
        sts = {p["status"] for _, p in x["parts"]}
        status = "derived" if x["derived"] or sts != {"official"} else "official"
        stages = {p["estimate_stage"] for _, p in x["parts"]}
        checks = {
            "value": rel_eq(r["value"], x["value"]),
            "status": r["status"] == status,
            "vintage": r["vintage"] == max((p["vintage"] for _, p in x["parts"]), key=vkey),
            "stage": r["estimate_stage"] in stages,  # every sampled row's inputs share one stage today
            "series": set(r["series_ids"].split(",")) == {p["series_id"] for _, p in x["parts"]},
            "unit": (r["unit"], r["price_basis"], r["period_type"]) == ("INR_crore", "current", "fy")
            and all((p["unit"], p["price_basis"]) == ("INR_crore", "current") for _, p in x["parts"]),
        }
        bad += [(k, c) for c, ok in checks.items() if not ok]
    assert not bad, bad[:20]


def test_every_non_linked_value_recomputes_from_clean_data():
    e = expected()
    bad = [
        (k, r["value"], e[k]["value"])
        for k, r in rows().items()
        if k[1] != LINK and not rel_eq(r["value"], e[k]["value"])
    ]
    assert not bad, bad[:10]


def test_sampled_provenance_traces_to_the_clean_records():
    """Each sampled row cites a time-series record (Phase 1 schema, ingest_unit timeseries) whose status and
    base_year are the row's, whose source is registered and is the inputs' source, and whose inputs include
    every clean record the row is computed from. Every record is used; linked records resolve."""
    reg = yaml.safe_load((ROOT / "data" / "registry.yaml").read_text(encoding="utf-8"))
    sources = {s["id"] for s in reg["sources"]}
    for f in sorted((ROOT / "data" / "registry_additions").glob("*.yaml")):
        sources |= {s["id"] for s in (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("sources") or []}
    clean_prov = {}
    for f in sorted(CLEAN.glob("*/_provenance.parquet")):
        for pid, src in q(f"select prov_id, source_id from '{f.as_posix()}'"):
            clean_prov[pid] = src
    e, pv = expected(), prov()
    assert {r["prov_id"] for r in rows().values()} == set(pv), "every row cites a record and every record is used"
    bad = []
    for k in sample():
        r = rows()[k]
        p = pv[r["prov_id"]]
        ins = set(p["inputs"].split(","))
        if p["ingest_unit"] != "timeseries" or p["status"] != r["status"] or p["base_year"] != r["base_year"]:
            bad.append((k, "record metadata"))
        if p["source_id"] not in sources or not (p["method"] or "").strip():
            bad.append((k, "source or method"))
        if k[1] == LINK:
            if not all(i in pv or i in clean_prov for i in ins):
                bad.append((k, "link inputs unresolved"))
            continue
        need = {x["prov_id"] for _, x in e[k]["parts"]}
        if not need <= ins or not ins <= set(clean_prov):
            bad.append((k, "inputs"))
        if p["source_id"] not in {clean_prov[i] for i in ins if i in clean_prov}:
            bad.append((k, "source is not the inputs' source"))
    assert not bad, bad[:20]
    assert "estimated" not in {p["status"] for p in pv.values()}, "nothing is estimated"


# ------------------------------------------------------------------------------------------------
# base years, splices and the linked variant
# ------------------------------------------------------------------------------------------------


def test_linked_variant_recomputes_from_clean_data():
    """plan s.2.5: only the whitelisted flows are linked; for them the rules hold in clean data; every linked
    value = old(t) x new(2022-23)/old(2022-23), t <= 2021-22, status derived, base 2022-23; the ratios in the
    definitions table are the clean ratios."""
    e = expected()
    linked = {f for f, d in defs().items() if d["link_policy"] == "linked"}
    assert linked == LINK_WHITELIST
    for f in SPEC:
        r22, r23 = ratios(f)
        d = defs()[f]
        for mine, theirs in ((r22, d["link_ratio_2022_23"]), (r23, d["link_ratio_2023_24"])):
            assert (mine is None) == (theirs is None) and (mine is None or abs(mine - theirs) < 1e-9), f
        if f in LINK_WHITELIST:
            vals = [v["value"] for k, v in e.items() if k[0] == f and k[1] == PUB and k[2] in (OLD, NEW) and v["value"]]
            assert abs(r22 - r23) <= 0.02 and len({v > 0 for v in vals}) == 1, f
    want = {
        (k[0], LINK, NEW, k[3])
        for k in e
        if k[0] in LINK_WHITELIST and k[1] == PUB and k[2] == OLD and k[3] <= "2021-22"
    }
    have = {k for k in rows() if k[1] == LINK}
    assert have == want
    for k in have:
        r = rows()[k]
        r22, _ = ratios(k[0])
        assert rel_eq(r["value"], e[(k[0], PUB, OLD, k[3])]["value"] * r22), k
        assert r["status"] == "derived" and r["base_year"] == NEW, k


def test_both_bases_stay_visible_at_the_break():
    """Every flow with old- and new-base NAS segments has both rows in 2022-23 (and 2023-24 where the old
    segment reaches it), flagged base_overlap; no other published row carries that flag."""
    want = set()
    for f, segs in SPEC.items():
        old = {p for s in segs if s["base"] == OLD and s["variant"] == PUB for p in fys(s["lo"], s["hi"])}
        new = {p for s in segs if s["base"] == NEW and s["variant"] == PUB for p in fys(s["lo"], s["hi"])}
        want |= {(f, p) for p in old & new}
    flagged = {(k[0], k[3]) for k, r in rows().items() if "base_overlap" in (r["flags"] or "")}
    assert flagged == want
    assert all(p in ("2022-23", "2023-24") for _, p in want)
    assert all(rows()[(f, PUB, b, p)] for f, p in want for b in (OLD, NEW))


def test_coverage_counts_match_plan_2_6():
    cov = dict(
        q(f"""select period, count(distinct flow_id) from '{(TSD / "top_flows.parquet").as_posix()}'
                     where variant = 'published' and flow_id like 'F%' group by 1""")
    )
    plan = {"1950-51": 5, "1952-53": 7, "1983-84": 13, "1999-00": 14, "2004-05": 15, "2006-07": 18, "2007-08": 19,
            "2011-12": 38, "2012-13": 40, "2017-18": 41, "2018-19": 42, "2020-21": 44, "2022-23": 54, "2023-24": 54,
            "2024-25": 42, "2025-26": 12}  # fmt: skip
    for p, n in plan.items():
        assert cov[p] == n, (p, cov[p], n)
    covfile = q(f"""select count(*), sum(n_rows) from '{(TSD / "top_flows_coverage.parquet").as_posix()}'""")[0]
    pub = [k for k in rows() if k[1] == PUB]
    assert covfile == (len({(k[0], k[3]) for k in pub}), len(pub))


def test_joins_without_a_splice_are_equalities_in_clean_data():
    """The precedence joins of plan s.2.1 / s.7 T2, recomputed."""
    yrs = fys("2011-12", "2023-24")
    for t12, items in (("t12.assets.financial_assets.current", ["gross_financial_saving"]),
                       ("t12.liabilities.financial_liabilities.current", ["financial_liabilities"]),
                       ("t12.assets.bank_deposits.current", ["with_banks", "with_co_operative_banks_and_societies"]),
                       ("t12.assets.shares_debentures.current", ["shares_and_debentures"]),
                       ("t12.assets.life_insurance_fund.current", ["insurance_funds"]),
                       ("t12.assets.pf_pension_fund.current", ["provident_and_pension_funds"]),
                       ("t12.liabilities.bank_advances.current",
                        ["bank_advances", "loans_and_advances_by_co_operative_banks_and_societies"])):  # fmt: skip
        a = latest(T12, t12)
        parts = [latest(S53, f"oldbase_nas2025_s5_3.{i}.current") for i in items]
        assert max(abs(a[p]["value"] - sum(x[p]["value"] for x in parts)) for p in yrs) <= 0.5, t12
    for a_, b_ in (("tsm.states_share.actuals", "at2.i-states_share_in_central_taxes.actuals"),
                   ("tsm.total_grants.actuals", "at2.ii-grants_from_the_centre.actuals")):  # fmt: skip
        a, b = latest(FT, a_), latest(AT, b_)
        assert max(abs(a[p]["value"] - b[p]["value"]) for p in fys("2007-08", "2022-23")) <= 0.5, a_
        assert abs(a[YEAR]["value"] - b[YEAR]["value"]) > 100, f"{a_}: the 2023-24 basis switch (timeseries-1)"
    for x, y in (("gdp", "gdp"), ("pfce", "pfce"), ("gfce", "gfce"), ("gfcf", "gfcf"), ("exports", "exports"),
                 ("imports", "imports"), ("gva", "gva_basic")):  # fmt: skip
        assert (
            abs(
                latest(BACK, f"api.{x}.current")[OLD]["value"]
                - latest(S11, f"oldbase_nas2025_s1_1.{y}.current")[OLD]["value"]
            )
            <= 2.5
        )
    gcf, sav = latest(S11, "oldbase_nas2025_s1_1.gcf.current"), latest(S11, "oldbase_nas2025_s1_1.gross_saving.current")
    nci = latest(S19, "oldbase_nas2025_s1_9.net_capital_inflow_from_row.current")
    assert max(abs(gcf[p]["value"] - sav[p]["value"] - nci[p]["value"]) for p in yrs) < 1e-3
    nb = (
        latest(BACK, "api.gcf_incl_errors_omissions.current")[OLD]["value"]
        - latest(BACK, "api.gross_saving.current")[OLD]["value"]
    )
    assert abs(nb - nci[OLD]["value"]) <= 1
    gtr = latest(FT, "tsm.gtr.actuals")
    for p in ("2022-23", "2023-24"):
        d = (latest(RB, "rb.tr.total.total_tax_revenue")[p]["value"] - latest(RB, "rb.tr.0710.less_states_share")[p]["value"]
             - latest(RB, "rb.tr.total.net_less_nccd_transferred_to_the_national_disaster_response_fund")[p]["value"])  # fmt: skip
        assert abs(d - gtr[p]["value"]) <= 0.5, p
    fi, bo = latest(FI, "t143.inr.fdi_to_india_net.current"), latest(BO, "bop_old.inr.ka.fdi.in_india.net.current")
    assert all(fi[p]["value"] == bo[p]["value"] for p in bo)
    for a_, b_ in (("invis.inr.private_transfers.receipts.current", "s6_1.other_current_transfers_to_resident_sectors_other_than_gener.current"),
                   ("invis.inr.private_transfers.payments.current", "s6_1.other_current_transfers_by_resident_sectors_other_than_gener.current"),
                   ("invis.inr.income.investment.payments.current", "s6_1.property_and_entrepreneurial_income_to_the_rest_of_the_world.current")):  # fmt: skip
        a, b = latest(BI, a_), latest("mospi_nas_2026_s6_1", b_)
        assert max(abs(a[p]["value"] - b[p]["value"]) for p in b) <= 0.5, a_
    fs, ep = latest(FS, "sub.fertilizer.in.gg_centre"), latest(EP, "stat7.fertiliser")
    assert max(abs(fs[p]["value"] - ep[p]["value"]) for p in ("2022-23", "2023-24")) <= 0.5


def test_latest_revision_round_is_the_nas_2025_level():
    """The NAS API old-base 'latest round' rule: for every FY 2011-12..2023-24 the chronologically latest
    round of api.gdp equals NAS 2025 1.1 GDP, and the latest rounds of the six sector GFCF series add up to
    NAS 2025 1.1 GFCF (within the API's integer rounding), which validates the rule for F33 and F46."""
    gdp, no = latest_round(API11, "api.gdp"), latest(S11, "oldbase_nas2025_s1_1.gdp.current")
    gfcf = latest(S11, "oldbase_nas2025_s1_1.gfcf.current")
    secs = ["gg", "nfc_private", "nfc_public", "fc_private", "fc_public", "households_npish"]
    lr = {s: latest_round(API11, f"api.gfcf.sec_{s}") for s in secs}
    for p in fys("2011-12", "2023-24"):
        assert abs(gdp[p]["value"] - no[p]["value"]) <= 1, p
        assert abs(sum(lr[s][p]["value"] for s in secs) - gfcf[p]["value"]) <= 6, p


# ------------------------------------------------------------------------------------------------
# the SAM definitions on the built blocks' entries (pre-balancing), plain SQL
# ------------------------------------------------------------------------------------------------


@cache
def entries() -> duckdb.DuckDBPyRelation | None:
    files = sorted(BLOCKS.glob("*_entries.parquet")) if BLOCKS.exists() else []
    if not files:
        return None
    sql = " union all ".join(
        f"select row, col, ref, component, value, role, tol_rel, bop_function, value as allow_base from '{f.as_posix()}'"
        for f in files
    )
    con().sql(f"create or replace table sam_entries as {sql}")
    return con().table("sam_entries")


BALANCED = ROOT / "data" / "sam" / "2023-24" / "sam_entries_balanced.parquet"


@cache
def balanced() -> duckdb.DuckDBPyRelation | None:
    """The balanced SAM's entries; the anchored allowance is taken on the prior, as for the block entries."""
    if not BALANCED.exists():
        return None
    con().sql(
        "create or replace table sam_balanced as select row, col, ref, component, value, role, tol_rel, bop_function, "
        f"prior as allow_base from '{BALANCED.as_posix()}'"
    )
    return con().table("sam_balanced")


@cache
def groups() -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for a in yaml.safe_load((ROOT / "pipeline" / "sam" / "accounts.yaml").read_text(encoding="utf-8"))["accounts"]:
        out[a["group"]].append(a["code"])
    return out


@cache
def flows_yaml() -> dict:
    return yaml.safe_load((ROOT / "pipeline" / "timeseries" / "flows.yaml").read_text(encoding="utf-8"))


def expand(tokens: list[str]) -> list[str]:
    sets = flows_yaml()["account_sets"]
    out: list[str] = []
    for tok in tokens:
        out += groups()[tok[1:]] if tok.startswith("@") else sets[tok[1:]] if tok.startswith("$") else [tok]
    return out


def inlist(xs) -> str:
    return "(" + ",".join(f"'{x}'" for x in xs) + ")"


def sam_eval(terms: list[dict], excluded: list[str], table: str = "sam_entries") -> dict:
    named = {r for tm in terms for r in tm["refs"]}
    total = allowance = 0.0
    missing, unlisted, keys = [], set(), []
    for i, tm in enumerate(terms):
        blk = f"select * from {table} where row in {inlist(expand(tm['rows']))} and col in {inlist(expand(tm['cols']))}"
        unlisted |= {r for (r,) in q(f"select distinct ref from ({blk})")} - named - set(excluded)
        sel = f"select * from ({blk}) where ref in {inlist(tm['refs'])}"
        missing += [f"t{i + 1}:{r}" for r in tm["refs"] if r not in (tm.get("optional_refs") or [])
                    and not q(f"select count(*) from ({sel}) where ref = '{r}'")[0][0]]  # fmt: skip
        for col, vals in (("component", tm.get("components")), ("bop_function", tm.get("bop_functions"))):
            if vals is not None:
                missing += [
                    f"t{i + 1}:{v}" for v in vals if not q(f"select count(*) from ({sel}) where {col} = '{v}'")[0][0]
                ]
                sel = f"select * from ({sel}) where {col} in {inlist(vals)}"
        s, a = q(f"""select coalesce(sum(value), 0), coalesce(sum(case when role = 'anchored'
                     then tol_rel * abs(allow_base) end), 0) from ({sel})""")[0]
        total += float(tm.get("coef", 1)) * s
        allowance += a
        keys += q(f"select row, col, ref, component, bop_function from ({sel})")
    return {
        "value": total,
        "allowance": allowance,
        "missing": missing,
        "unlisted": sorted(unlisted),
        "dup": len(keys) - len(set(keys)),
    }


def ts_2023_24(flow: str) -> float:
    ks = [k for k in rows() if k[0] == flow and k[1] == PUB and k[3] == YEAR and k[2] in (None, NEW)]
    assert len(ks) == 1, flow
    return rows()[ks[0]]["value"]


K4_GAP_FLOWS = ("F35", "M13")  # contain closure's K4a (household saving): = NAS 1.9 only after balancing


def test_class_a_flows_equal_their_sam_definition_on_the_built_blocks():
    """Pre-balancing: every class-A flow whose cells are written equals its SAM definition (flows.yaml terms,
    evaluated here with plain SQL) within max(Rs 5 crore, the anchored allowance); no unlisted ref sits in
    its cell blocks, every named ref/component/bop tag exists, no entry is matched twice. Flows whose
    owning block is not built yet (closure: K4a, D1) are skipped and listed.

    closure-18 (wave C): F35 and M13 contain closure's K4a, which the K4 constraint pulls onto NAS 1.9 household
    saving only in balancing (closure plan C7, option A). Before balancing F35 misses NAS by the K4 gap Z, and
    M13 must miss by the same Z and by nothing else (its other terms, PFCE and D1, are held to NAS here). Both
    are checked against NAS on the balanced SAM in the next test."""
    if entries() is None:
        pytest.skip("no SAM block entries yet")
    bad, skipped, n, gap = [], [], 0, {}
    for f in flows_yaml()["flows"]:
        if not f["sam"]["terms"]:
            continue
        ev = sam_eval(f["sam"]["terms"], f["sam"].get("excluded_refs") or [])
        if ev["unlisted"] or ev["dup"]:
            bad.append((f["id"], "guard", ev["unlisted"], ev["dup"]))
        if ev["missing"]:
            skipped.append((f["id"], ev["missing"]))
            continue
        if f["check_class"] == "A":
            n += 1
            diff = ev["value"] - ts_2023_24(f["id"])
            if f["id"] in K4_GAP_FLOWS:
                gap[f["id"]] = (diff, ev["allowance"])
            elif abs(diff) > max(5.0, ev["allowance"]):
                bad.append((f["id"], ev["value"], ts_2023_24(f["id"])))
    if len(gap) == 2:  # closure built: M13's pre-balancing gap is F35's K4 gap
        (z, _), (d13, a13) = gap["F35"], gap["M13"]
        if abs(d13 - z) > max(5.0, a13):
            bad.append(("M13", "gap is not the K4 gap", round(d13, 2), round(z, 2)))
    assert not bad, bad
    assert {s[0] for s in skipped} <= {"F35", "M12", "M13"}, skipped  # only closure's K4a / D1 may be missing
    assert n >= 40


def test_class_a_flows_equal_their_sam_definition_on_the_balanced_sam():
    """closure-18 (wave C): on the balanced SAM every class-A flow, F35 (household saving) and M13 (household
    GDI) included, equals its SAM definition within max(Rs 5 crore, the anchored allowance on the prior), with
    the same guards; nothing is missing once closure is built."""
    if balanced() is None:
        pytest.skip("no balanced SAM yet: data/sam/2023-24/sam_entries_balanced.parquet")
    bad, checked = [], set()
    for f in flows_yaml()["flows"]:
        if not f["sam"]["terms"]:
            continue
        ev = sam_eval(f["sam"]["terms"], f["sam"].get("excluded_refs") or [], table="sam_balanced")
        if ev["unlisted"] or ev["dup"] or ev["missing"]:
            bad.append((f["id"], "guard", ev["unlisted"], ev["dup"], ev["missing"]))
        if f["check_class"] == "A":
            checked.add(f["id"])
            if abs(ev["value"] - ts_2023_24(f["id"])) > max(5.0, ev["allowance"]):
                bad.append((f["id"], round(ev["value"], 2), ts_2023_24(f["id"])))
    assert not bad, bad
    assert len(checked) >= 47 and set(K4_GAP_FLOWS) <= checked, sorted(checked)


# ------------------------------------------------------------------------------------------------
# manifest, CLI, determinism
# ------------------------------------------------------------------------------------------------


def test_manifest_hashes_every_time_series_file():
    m = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))["files"]
    for f in OUT_FILES:
        k = f"data/timeseries/{f}"
        assert k in m, k
        assert m[k]["sha256"] == hashlib.sha256((TSD / f).read_bytes()).hexdigest(), f"{k}: manifest is stale"
        assert m[k]["rows"] == q(f"select count(*) from '{(TSD / f).as_posix()}'")[0][0]
    assert not [p.name for p in TSD.iterdir() if p.is_file() and p.name not in OUT_FILES], "orphaned outputs"


def test_cli_exposes_the_step_and_repro_covers_it():
    out = subprocess.run(
        [sys.executable, "-m", "pipeline", "--help"], cwd=ROOT, capture_output=True, text=True, timeout=300
    )
    assert out.returncode == 0 and "timeseries [--out DIR]" in out.stdout
    from pipeline.cli import REPRO_OUTPUT_DIRS  # the shared constant the tolerance and orphan checks use

    assert REPRO_OUTPUT_DIRS == ("data/clean/", "data/sam/", "data/timeseries/")


def test_cli_run_is_deterministic_and_reproduces_the_committed_files(tmp_path):
    """`timeseries --out` into two scratch layouts (a copy of data/clean, no SAM): PYTHONHASHSEED 0 / 1 thread
    and PYTHONHASHSEED 1 / 4 threads. The four files that do not depend on the SAM are byte-identical to each
    other and to the committed ones; the check tables of the two runs are identical to each other."""
    runs = {"a": {"PYTHONHASHSEED": "0"}, "b": {"PYTHONHASHSEED": "1", "INDIA_SAM_ALLOW_ANY_THREADS": "1",
            "POLARS_MAX_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "MKL_NUM_THREADS": "4"}}  # fmt: skip
    for name, extra in runs.items():
        shutil.copytree(CLEAN, tmp_path / name / "clean")
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "INDIA_SAM_ALLOW_ANY_HASHSEED": "1", **extra}
        out = subprocess.run([sys.executable, "-m", "pipeline", "timeseries", "--out", str(tmp_path / name)], cwd=ROOT,
                             env=env, capture_output=True, text=True, timeout=900)  # fmt: skip
        assert out.returncode == 0, out.stdout + out.stderr
    for f in OUT_FILES:
        a, b = (tmp_path / "a" / "timeseries" / f).read_bytes(), (tmp_path / "b" / "timeseries" / f).read_bytes()
        assert a == b, f"{f}: differs between hash seeds / thread counts"
        if f != "top_flows_sam_check.parquet":
            assert a == (TSD / f).read_bytes(), f"{f}: the committed file is not what the current code builds"


# ------------------------------------------------------------------------------------------------
# defects TSV-1..TSV-5 (docs/phase2/verify/timeseries.md): fixed 2026-09-30, kept as regression tests
# ------------------------------------------------------------------------------------------------


def test_segment_codes_are_the_plan_codes():
    codes = {r["segment"].removeprefix("LINK:") for r in rows().values()}
    assert codes <= PLAN_CODES, sorted(codes - PLAN_CODES)
    for k, r in rows().items():
        if k[1] != LINK:
            assert r["segment"] == expected()[k]["code"], k


def test_row_base_year_is_the_base_year_of_its_clean_inputs():
    bad = sorted({(k[0], rows()[k]["segment"], k[2], p["base_year"]) for k, x in expected().items()
                  for _, p in x["parts"] if p["base_year"] != k[2]}, key=str)  # fmt: skip
    assert not bad, bad


# TSV-3 bridges written from the government block's R9 control methods (gov.r9.centre: Union Finance Accounts
# MH 2071 less the NPS employer contribution 2071.01.117/.902 and CGHS pensioners 2071.01.118; gov.r9.states:
# RBI SF App. II ii.e pensions, all States + UTs, less the PFRDA State employer NPS contribution m7d) and the
# plan's TS series (F27 AFS MH 2071; F28 FC16 KFI, 28 States): (dataset, series, coef) so that TS + bridge is
# on government's concept.
TSV3_BRIDGES = {
    "F27": {
        ("union_fiscal_fa_expenditure", "fa9.2071.01.117", -1.0),
        ("union_fiscal_fa_expenditure", "fa9.2071.01.902", -1.0),
        ("union_fiscal_fa_expenditure", "fa9.2071.01.118", -1.0),
    },
    "F28": {
        ("state_fiscal_rbi_sf_appendices", "app2.total_expenditure.ii.e-pensions.in.all_states_uts.actuals", 1.0),
        ("state_fiscal_fc16_kfi", "kfi.b_1_b-pension_and_other_retirement_benefits.in.all_states_28", -1.0),
        ("finsector_markets_pfrda_sg", "m7d.annual_contribution_employer.state_govt.current", -1.0),
    },
}


def test_pension_flows_bridge_onto_the_sam_concept_on_the_built_blocks():
    """TSV-3 (fixed by its first option): F27/F28 are class C; the builder registers exactly the verifier's
    bridge series; TS + bridge equals the SAM cells H_* <- G [R9, R9a] (plan s.2.2) on the block entries within
    the class-C tolerance. The AFS and Finance Accounts MH 2071 totals agree (F27's TS is AFS, government's
    control starts from the Finance Accounts)."""
    if entries() is None or not (BLOCKS / "government_entries.parquet").exists():
        pytest.skip("government block not built")
    afs = latest(AF, "afs.cfi_rev_disbursements.2071")[YEAR]["value"]
    fa = latest("union_fiscal_fa_expenditure", "fa9.2071.total")[YEAR]["value"]
    assert abs(afs - fa) <= 0.01, (afs, fa)
    hh = inlist(groups()["HH"])
    expl = {
        e["flow_id"]: e
        for e in yaml.safe_load((ROOT / "pipeline" / "timeseries" / "explanations.yaml").read_text(encoding="utf-8"))[
            "explanations"
        ]
    }
    bad = []
    for flow, gov in (("F27", "G_CEN"), ("F28", "G_STA")):  # plan s.2.2: H_* <- G [R9, R9a]
        theirs = {(b["dataset"], b["id"], float(b.get("coef", 1))) for b in expl[flow]["bridge_series"]}
        if theirs != TSV3_BRIDGES[flow]:
            bad.append((flow, "bridge series differ", sorted(theirs ^ TSV3_BRIDGES[flow])))
        sam = q(
            f"select coalesce(sum(value), 0) from sam_entries where row in {hh} and col = '{gov}' and ref in ('R9', 'R9a')"
        )[0][0]
        tsv = ts_2023_24(flow)
        bridge = sum(c * latest(ds, sid)[YEAR]["value"] for ds, sid, c in TSV3_BRIDGES[flow])
        resid = sam - tsv - bridge
        if defs()[flow]["check_class"] != "C" or abs(resid) > max(500.0, 0.01 * abs(tsv)):
            bad.append((flow, round(sam, 2), tsv, round(bridge, 2), round(resid, 2)))
    assert not bad, bad


def test_f26_bridge_brings_the_time_series_onto_the_sam_concept():
    if entries() is None or not (BLOCKS / "fincorp_entries.parquet").exists():
        pytest.skip("fincorp block not built")
    rows_ = inlist(groups()["HH"] + groups()["NFC"] + groups()["FC"] + ["R_ROW", "G_CEN"])
    # plan s.2.2 F26 + s.8 XR-9: every interest cell paid by G_STA
    sam = q(f"""select coalesce(sum(value), 0) from sam_entries where col = 'G_STA' and row in {rows_}
                and ref in ('R3', 'R3a', 'R3b', 'R5', 'R14', 'R8a', 'R9c')""")[0][0]
    expl = {
        e["flow_id"]: e
        for e in yaml.safe_load((ROOT / "pipeline" / "timeseries" / "explanations.yaml").read_text(encoding="utf-8"))[
            "explanations"
        ]
    }
    bridge = sum(
        float(b.get("coef", 1)) * latest(b["dataset"], b["id"])[YEAR]["value"] for b in expl["F26"]["bridge_series"]
    )
    tsv = ts_2023_24("F26")
    resid = sam - tsv - bridge
    assert abs(resid) <= max(500.0, 0.01 * abs(tsv)), (round(sam, 2), tsv, round(bridge, 2), round(resid, 2))


def test_refusals_citing_unstable_ratios_are_true():
    bad = []
    for f, d in defs().items():
        if d["link_policy"] != "linked" and "unstable" in (d["link_reason"] or ""):
            r22, r23 = ratios(f)
            if r22 is not None and r23 is not None and abs(r22 - r23) <= 0.02:
                bad.append((f, round(r22, 5), round(r23, 5)))
    assert not bad, bad
