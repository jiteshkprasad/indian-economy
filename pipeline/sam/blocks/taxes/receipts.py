"""Union and State tax receipts (cash, as published), mapped to the SAM tax accounts (T1, T2 and the
direct-tax heads used by T3/T4). Every value is read from clean data; nothing is typed in."""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.sam.framework import BlockContext, SamError

from .common import RB, SF, pids, prefixed, sf_series, total

VINTAGE = "latest"  # an explicit choice: RB 2023-24 actuals carry one vintage (2025-02-01); RBI SF one (2026-01-23)


@dataclass(frozen=True)
class Item:
    key: str  # slug, e.g. "vehicle_tax"
    account: str  # SAM tax account
    gov: str  # G_CEN or G_STA
    value: float
    prov_ids: tuple[str, ...]
    series: tuple[str, ...]
    label: str


# Union heads (Receipt Budget 2025-26, actuals 2023-24), gross of devolution (R1 moves the States' share).
CENTRE = [
    ("cgst", "T_CGST", ["rb.tr.0005.central_goods_and_services_tax_cgst"], "CGST (MH 0005)"),
    ("igst", "T_CGST", ["rb.tr.0008.integrated_goods_and_services_tax_igst"],
     "IGST unsettled residual (MH 0008; settled IGST is already inside CGST/SGST)"),
    ("utgst", "T_CGST", ["rb.tr.0007.union_territories_goods_and_services_tax_utgst"],
     "UTGST (MH 0007), received by the Union (UTs without legislature)"),
    ("gst_compensation_cess", "T_GCES", ["rb.tr.0009.gst_compensation_cess"], "GST compensation cess (MH 0009)"),
    ("union_excise", "T_UEXC", ["rb.tr.total.total_union_excise_duties"],
     "Union excise duties (MH 0038) gross, incl. NCCD, RIC, AIDC, SAED and cess on crude oil"),
    ("ut_sales_tax", "T_SVAT", ["rb.tr.0710.sales_tax"], "Sales tax of UTs without legislature (MH 0710)"),
    ("ut_state_excise", "T_SEXC", ["rb.tr.0710.state_excise_duties"], "State excise of UTs without legislature"),
    ("ut_vehicle_tax", "T_OPRT", ["rb.tr.0710.taxes_on_vehicles"], "Motor-vehicle tax of UTs without legislature"),
    ("ut_goods_passengers", "T_OPRT", ["rb.tr.0710.taxes_on_goods_and_passengers"],
     "Taxes on goods and passengers, UTs without legislature"),
    ("ut_electricity_duty", "T_OPRT", ["rb.tr.0710.taxes_and_duties_on_electricity"],
     "Electricity duty, UTs without legislature"),
    ("service_tax_arrears", "T_OPRT", ["rb.tr.total.total_service_tax"], "Service tax arrears (MH 0044)"),
    ("equalisation_levy", "T_OPRT", ["rb.tr.total.total_other_taxes_and_duties_on_commodities_and_services"],
     "MH 0045 other taxes and duties on commodities and services (equalisation levy)"),
    ("export_duty", "T_OPRT", ["rb.tr.0037.export_duty", "rb.tr.0037.cesses_on_exports"],
     "Export duty and cesses on exports (inside MH 0037 customs; not import duty)"),
    ("ctt", "T_OPRT", ["rb.tr.total.total_commodity_transaction_tax"], "Commodity transaction tax (MH 0036)"),
]  # fmt: skip
# State heads (RBI State Finances 2025-26, Appendix I, accounts 2023-24, all States + UTs with legislature).
STATE = [
    ("sgst", "T_SGST", ["i.a.3.vii-state_goods_and_services_tax"], "SGST"),
    ("sales_tax", "T_SVAT", ["i.a.3.i-sales_tax"], "Sales tax / VAT (incl. CST)"),
    ("state_excise", "T_SEXC", ["i.a.3.ii-state_excise"], "State excise"),
    ("vehicle_tax", "T_OPRT", ["i.a.3.iii-taxes_on_vehicles"], "Taxes on vehicles (product tax, DECISIONS D2-4)"),
    ("goods_passengers", "T_OPRT", ["i.a.3.iv-taxes_on_goods_and_passengers"], "Taxes on goods and passengers"),
    ("electricity_duty", "T_OPRT", ["i.a.3.v-taxes_and_duties_on_electricity"], "Taxes and duties on electricity"),
    ("entertainment_tax", "T_OPRT", ["i.a.3.vi-entertainment_tax"], "Entertainment tax"),
    ("other_taxes_duties", "T_OPRT", ["i.a.3.viii-other_taxes_and_duties"], "Other taxes and duties on commodities"),
]  # fmt: skip


@dataclass
class Cash:
    items: list[Item] = field(default_factory=list)
    extra: dict[str, tuple[float, list[str]]] = field(default_factory=dict)  # direct taxes, customs, P10a heads

    def get(self, key: str) -> Item:
        for i in self.items:
            if i.key == key:
                return i
        raise SamError(f"taxes: no cash item {key!r}")

    def by_account(self, account: str, gov: str | None = None) -> float:
        return sum(i.value for i in self.items if i.account == account and (gov is None or i.gov == gov))

    def pids(self, account: str | None = None, gov: str | None = None) -> list[str]:
        return pids(*(i.prov_ids for i in self.items
                      if (account is None or i.account == account) and (gov is None or i.gov == gov)))  # fmt: skip

    def x(self, key: str) -> float:
        return self.extra[key][0]

    def xp(self, key: str) -> list[str]:
        return self.extra[key][1]


def read_cash(ctx: BlockContext) -> Cash:
    c = Cash()
    for key, acct, series, label in CENTRE:
        v, p = total(ctx, RB, series, vintage=VINTAGE)
        if v != 0:
            c.items.append(Item(key, acct, "G_CEN", v, tuple(p), tuple(series), label))
        else:
            ctx.log(f"cash item {key} is 0 in 2023-24: no entry")
    for key, acct, codes, label in STATE:
        series = [sf_series(x) for x in codes]
        v, p = total(ctx, SF, series, vintage=VINTAGE)
        c.items.append(Item(key, acct, "G_STA", v, tuple(p), tuple(series), label))

    # --- direct taxes (Union RB; State RBI SF) --------------------------------------------------------
    mh21 = prefixed(ctx, RB, "rb.tr.0021.", ctx.year, vintage=VINTAGE)
    c.extra["mh0021"] = (float(mh21["value"].sum()), sorted(set(mh21["prov_id"].to_list())))
    for key, series in (
        ("stt", ["rb.tr.0034.security_transaction_tax"]),
        ("taxes_on_income", ["rb.tr.total.total_taxes_on_income"]),
        ("wealth_tax", ["rb.tr.total.total_wealth_tax"]),  # MH 0031 estate duty + MH 0032 wealth tax (arrears)
        ("mh0028", ["rb.tr.total.total_other_taxes_on_income_and_expenditure"]),  # expenditure tax etc. (arrears)
        ("firm_heads", ["rb.tr.0023.hotel_receipts_tax", "rb.tr.0024.interest_tax", "rb.tr.0026.fringe_benefit_tax"]),
        ("cit", ["rb.tr.total.total_corporation_tax"]),
        ("customs", ["rb.tr.total.total_customs"]),
        ("export_duty", ["rb.tr.0037.export_duty", "rb.tr.0037.cesses_on_exports"]),
        ("gst_total", ["rb.tr.total.total_goods_and_services_tax_gst"]),
        ("centre_stamps", ["rb.tr.0030.stamps_duty_judicial_court_fees_released_in_stamps",
                           "rb.tr.0710.stamps_and_registration"]),
        ("centre_land_revenue", ["rb.tr.0710.land_revenue"]),
    ):  # fmt: skip
        c.extra[key] = total(ctx, RB, series, vintage=VINTAGE)
    for key, codes in (
        ("state_income_taxes", ["i.a.1-taxes_on_income"]),
        ("professions_tax", ["i.a.1.ii-taxes_on_professions_trades_callings_and_employm"]),
        ("agricultural_income_tax", ["i.a.1.i-agricultural_income_tax"]),
        ("stamps", ["i.a.2.ii-stamps_and_registration_fees"]),
        ("land_revenue", ["i.a.2.i-land_revenue"]),
        ("urban_property_tax", ["i.a.2.iii-urban_immovable_property_tax"]),
    ):
        c.extra[key] = total(ctx, SF, [sf_series(x) for x in codes], vintage=VINTAGE)

    # identities the mapping relies on (fail loudly if the published totals do not add up)
    inc = c.x("mh0021") + c.x("stt") + c.x("firm_heads") + c.x("mh0028")
    if abs(inc - c.x("taxes_on_income")) > 0.02:
        raise SamError(f"RB taxes on income {c.x('taxes_on_income')} != MH 0021 + STT + 0023/24/26 + 0028 = {inc}")
    st = c.x("professions_tax") + c.x("agricultural_income_tax")
    if abs(st - c.x("state_income_taxes")) > 0.02:
        raise SamError(f"RBI SF State taxes on income {c.x('state_income_taxes')} != professions + agricultural {st}")
    return c
