"""Memo satellites: S7 (the IGST settlement route; IGST is already inside CGST/SGST, so these are not SAM
cells) and `tax_classification` (where each contested head went, so government books none of them twice)."""

from __future__ import annotations

from pipeline.sam.framework import BlockContext

from .common import FA, PIB

FA_VINTAGE = "latest"  # Finance Accounts 2023-24 (audited, 2024-12-10): one vintage

S7_FA = [
    ("fa8.0008.01.total", "igst_imports", "IGST collected on imports"),
    ("fa8.0008.02.101", "igst_domestic_tax", "IGST domestic: tax"),
    ("fa8.0008.02.102", "igst_domestic_interest", "IGST domestic: interest"),
    ("fa8.0008.02.103", "igst_domestic_penalty", "IGST domestic: penalty"),
    ("fa8.0008.02.104", "igst_domestic_fees", "IGST domestic: fees"),
    ("fa8.0008.02.800", "igst_domestic_other", "IGST domestic: other receipts"),
    ("fa8.0008.02.105", "itc_to_cgst", "IGST input tax credit cross-utilised for CGST"),
    ("fa8.0008.02.106", "itc_to_sgst", "IGST input tax credit cross-utilised for SGST"),
    ("fa8.0008.02.107", "itc_to_utgst", "IGST input tax credit cross-utilised for UTGST"),
    ("fa8.0008.02.950", "apportioned_to_cgst_tax", "IGST apportioned to CGST (tax)"),
    ("fa8.0008.02.951", "apportioned_to_cgst_interest", "IGST apportioned to CGST (interest)"),
    ("fa8.0008.02.953", "apportioned_to_sgst_tax", "IGST apportioned to SGST (tax)"),
    ("fa8.0008.02.954", "apportioned_to_sgst_interest", "IGST apportioned to SGST (interest)"),
    ("fa8.0008.02.956", "apportioned_to_utgst_tax", "IGST apportioned to UTGST (tax)"),
    ("fa8.0008.02.957", "apportioned_to_utgst_interest", "IGST apportioned to UTGST (interest)"),
    ("fa8.0008.02.959", "advance_apportionment_cgst", "advance apportionment, CGST"),
    ("fa8.0008.02.960", "advance_apportionment_sgst", "advance apportionment, SGST"),
    ("fa8.0008.02.961", "advance_apportionment_utgst", "advance apportionment, UTGST"),
    ("fa8.0008.02.total", "igst_domestic_net", "IGST domestic, net of settlement"),
    ("fa8.0008.total", "igst_residual", "IGST residual (MH 0008 total; inside T_CGST)"),
    ("fa8.0005.00.105", "cgst_from_igst_itc", "CGST side: IGST ITC cross-utilised"),
    ("fa8.0005.00.106", "cgst_from_igst_apportionment", "CGST side: apportionment of IGST"),
    ("fa8.0005.00.107", "cgst_from_igst_apportionment_interest", "CGST side: apportionment of IGST (interest)"),
    ("fa8.0005.00.110", "cgst_advance_apportionment", "CGST side: advance apportionment"),
    ("fa8.0007.total", "utgst_total", "UTGST (MH 0007) total"),
    ("fa8.0009.01.total", "cess_imports", "compensation cess on imports"),
    ("fa8.0009.02.total", "cess_domestic", "compensation cess, domestic"),
]


def s7_rows(ctx: BlockContext) -> tuple[list[dict], list[str]]:
    rows, ins = [], []
    for sid, key, label in S7_FA:
        v, p = ctx.value(FA, sid, vintage=FA_VINTAGE)
        rows.append({"series_id": f"s7.annual.{key}", "item": key, "label": label, "period": ctx.year,
                     "source_series": sid, "value": v})  # fmt: skip
        ins.append(p)
    pib_ids = sorted(
        s for s in ctx.frame(PIB)["series_id"].unique().to_list()
        if s.startswith("pib.gst.")
    )  # fmt: skip
    for month in ("2023-04", "2023-05"):
        m = ctx.rows(PIB, series_id=pib_ids, period=month, vintage="latest", allow_empty=True)
        for r in m.sort("series_id").iter_rows(named=True):
            key = r["series_id"].removeprefix("pib.gst.")
            rows.append({"series_id": f"s7.monthly.{month}.{key}", "item": key, "label": f"PIB GST release: {key}",
                         "period": month, "source_series": r["series_id"], "value": r["value"]})  # fmt: skip
            ins.append(r["prov_id"])
    return rows, sorted(set(ins))


def classification_rows(cash, t3, p9a, p10a, lpg_p9: float, stat7: dict[str, float]) -> list[dict]:
    """Every contested head, its amount and the one place it is booked (government must not book it again)."""

    def r(item, amount, ref, cell, gov, treatment):
        return {"item": item, "value": amount, "ref": ref, "sam_cell": cell, "government": gov,
                "treatment": treatment}  # fmt: skip

    ci = {i.key: i.value for i in cash.items}
    rows = [
        r("vehicle_tax_states", ci["vehicle_tax"], "P7a/T2x", "T_OPRT <- C_TREQ; G_STA <- T_OPRT", "G_STA",
          "product tax (DECISIONS D2-4); government R16 has no vehicle_tax"),
        r("vehicle_tax_uts", ci.get("ut_vehicle_tax", 0.0), "P7a/T1a", "T_OPRT <- C_TREQ; G_CEN <- T_OPRT", "G_CEN",
          "product tax (DECISIONS D2-4)"),
        r("professions_tax", cash.x("professions_tax"), "T3a/T2x", "T_PIT <- H_* {professions_tax}; G_STA <- T_PIT",
          "G_STA", "current tax on income (D5), not a production tax (plan C4)"),
        r("agricultural_income_tax", cash.x("agricultural_income_tax"), "T3a/T2x",
          "T_PIT <- H_* {professions_tax}; G_STA <- T_PIT", "G_STA", "current tax on income (D5)"),
        r("stt", cash.x("stt"), "T3a/T1a", "T_PIT <- H_* {income_tax}; G_CEN <- T_PIT", "G_CEN",
          "tax on income (DECISIONS D2-12; NAD question)"),
        r("ctt", ci.get("ctt", 0.0), "P7a/T1a", "T_OPRT <- C_FINS; G_CEN <- T_OPRT", "G_CEN",
          "product tax (DECISIONS D2-12)"),
        r("equalisation_levy_mh0045", ci.get("equalisation_levy", 0.0), "P7a/T1a",
          "T_OPRT <- C_BSRE, C_COMM; G_CEN <- T_OPRT", "G_CEN", "product tax on digital services (D2-12)"),
        r("export_duty", ci.get("export_duty", 0.0), "P7a/T1a", "T_OPRT <- goods; G_CEN <- T_OPRT", "G_CEN",
          "product tax on exports, not import duty (D2-12; TAX-2)"),
        r("utgst", ci.get("utgst", 0.0), "T1a", "G_CEN <- T_CGST {utgst}", "G_CEN",
          "UTs without legislature are Union: in T_CGST, component utgst (plan C6)"),
        r("union_excise_gross_incl_nccd", ci.get("union_excise", 0.0), "P7a/T1a",
          "T_UEXC <- C_*; G_CEN <- T_UEXC", "G_CEN",
          "Union excise gross (incl. NCCD); the NDRF transfer is internal to G_CEN"),
        r("miss_interest_subvention", stat7["miss"], "P9a", "G_CEN <- T_PSUB (SUT P9 on C_FINS)", "G_CEN",
          "product subsidy on financial services; not R18, not P10a"),
        r("lpg_subsidy_in_p9", -lpg_p9, "P9a", "G_CEN <- T_PSUB (SUT P9 on C_RPET)", "G_CEN", "product subsidy"),
        r("lpg_dbt_not_product_subsidy", stat7["lpg"] + lpg_p9, "none", "government R10", "G_CEN",
          "St 7 LPG less the SUT P9 on C_RPET: a social benefit (government), not a subsidy"),
        r("fertiliser_subsidy", stat7["fertiliser"], "P9a", "G_CEN <- T_PSUB (SUT P9 on C_CHEM)", "G_CEN",
          "product subsidy (SUT cell 2,07,569 is the control)"),
        r("pm_aasha", stat7["aasha"], "P9a", "G_CEN <- T_PSUB (SUT P9 on C_CROP)", "G_CEN", "product subsidy"),
        r("state_food_subsidies_fc16", p9a.food, "P9a", "G_STA <- T_PSUB (SUT P9 on C_TRAD)", "G_STA",
          "product subsidy (XR-23); government keeps them out of C2a and R10"),
        r("union_food_subsidy", stat7["food"], "none", "government C2a", "G_CEN",
          "GFCE (free/subsidised grain), never P9a"),
        r("state_power_subsidies", p9a.util, "P9a", "G_STA <- T_PSUB (SUT P9 on C_UTIL)", "G_STA", "product subsidy"),
        r("lic_pension_subsidy", stat7["lic"], "none", "government R18", "G_CEN",
          "current transfer to insurers; excluded from P10a interest subsidies"),
    ]  # fmt: skip
    rows.append(r("pm_kisan", p10a.pm_kisan[0], "none", "government R10 H_* <- G_CEN {pm_kisan}", "G_CEN",
                  "current transfer to farm households (inferred: NAS 4.2 does not itemise it; COFOG 04.agri current "
                  "transfers can hold it; government-30, DECISIONS D2-24), "
                  "not a production subsidy: outside P10a"))  # fmt: skip
    for key, v, _ in p10a.centre_subsidy_items:
        rows.append(r(key, v, "P10a", "G_CEN <- T_PROD {gross_subsidies}", "G_CEN",
                      "other subsidy on production (D39); not R18/R10"))  # fmt: skip
    return [x for x in rows if x["value"] != 0]
