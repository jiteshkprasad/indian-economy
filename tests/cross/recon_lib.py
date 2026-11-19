# ruff: noqa: E501  (check definitions carry long, sourced notes and series ids)
"""Cross-source reconciliation checks for Phase 1 (read-only over data/clean).

Owned by the reconciliation checker, not by any ingest unit. Every number here is read from a clean
Parquet file (plus the committed SUT -> SAM concordance in data/concordance, used only to group the
SUT's 67 industries into the 11 NAS groups). Nothing is estimated or typed in.

A check compares side A with side B for one period:

    raw difference  = A - B                 (Rs crore, and % of |B|)
    bridged residual = A - (B + bridge)     (bridge = named, sourced reconciling items)

and carries a tolerance (percent of |B|, with an absolute floor in Rs crore) and a verdict:

- ``agree``: no bridge needed; |A - B| is within tolerance.
- ``explained``: the difference has a stated cause. Either a sourced bridge closes it to within
  tolerance ("bridged"), or it is a documented conceptual/coverage/vintage difference that stays
  inside a stated tolerance ("conceptual": the bridge items are not in the clean data).
- ``UNEXPLAINED``: no verified cause. The test asserts the tolerance we would expect and is marked
  xfail (non-strict), so the disagreement stays visible in every test run and an XPASS shows when a
  fix lands.

Ratio checks (``ratio_range``) test A/B instead of A - B (used for HCES vs NAS PFCE).

Run ``uv run python tests/cross/recon_lib.py`` to print the markdown tables used in
docs/phase1/RECONCILIATION.md.
"""

from __future__ import annotations

import csv
import functools
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

REPO = Path(__file__).resolve().parents[2]
CLEAN = REPO / "data" / "clean"
CONCORDANCE = REPO / "data" / "concordance" / "io_tables_sut_industry_to_sam34.csv"

AGREE, EXPLAINED, UNEXPLAINED = "agree", "explained", "UNEXPLAINED"


class MissingData(Exception):
    """A clean dataset needed by a check does not exist (unit not built)."""


# --------------------------------------------------------------------------------------------------
# data access
# --------------------------------------------------------------------------------------------------


@functools.cache
def load(unit: str, dataset: str) -> pl.DataFrame:
    p = CLEAN / unit / f"{dataset}.parquet"
    if not p.exists():
        raise MissingData(f"data/clean/{unit}/{dataset}.parquet is missing (build unit {unit})")
    return pl.read_parquet(p)


def _pick(df: pl.DataFrame, what: str, vintage: str | None) -> pl.DataFrame:
    """One row per series: the requested vintage, else the latest vintage present."""
    if vintage is not None:
        df = df.filter(pl.col("vintage") == vintage)
    elif df.height > 1:
        df = df.filter(pl.col("vintage") == df["vintage"].max())
    if df.height != 1:
        raise LookupError(f"{what}: expected 1 row, found {df.height}")
    return df


def value(unit: str, dataset: str, series_id: str, period: str, vintage: str | None = None) -> float:
    df = load(unit, dataset).filter((pl.col("series_id") == series_id) & (pl.col("period") == period))
    return float(_pick(df, f"{dataset}:{series_id}@{period}", vintage)["value"][0])


def value_sum(unit: str, dataset: str, pattern: str, period: str, *, min_rows: int = 1) -> float:
    """Sum of every series whose id matches the regex (latest vintage of each)."""
    df = load(unit, dataset).filter(pl.col("series_id").str.contains(pattern) & (pl.col("period") == period))
    df = df.filter(pl.col("vintage") == pl.col("vintage").max().over("series_id"))
    if df.height < min_rows:
        raise LookupError(f"{dataset}:/{pattern}/@{period}: {df.height} rows, need >= {min_rows}")
    return float(df["value"].sum())


@dataclass(frozen=True)
class Term:
    label: str
    src: str  # "unit/dataset: series_id (or rule)"
    fn: Callable[[], float]
    coef: float = 1.0

    def get(self) -> float:
        return self.coef * self.fn()


def s(
    label: str, unit: str, dataset: str, series_id: str, period: str, coef: float = 1.0, vintage: str | None = None
) -> Term:
    tag = f" [vintage {vintage}]" if vintage else ""
    return Term(
        label,
        f"`{dataset}`: `{series_id}` ({period}){tag}",
        lambda: value(unit, dataset, series_id, period, vintage),
        coef,
    )


def ssum(label: str, unit: str, dataset: str, pattern: str, period: str, coef: float = 1.0, min_rows: int = 1) -> Term:
    return Term(
        label,
        f"`{dataset}`: sum of series matching `{pattern}` ({period})",
        lambda: value_sum(unit, dataset, pattern, period, min_rows=min_rows),
        coef,
    )


# --- derived helpers (all from clean data) --------------------------------------------------------

NAS_GROUPS = {
    1: "agri",
    2: "mining",
    3: "manufacturing",
    4: "utilities",
    5: "construction",
    6: "trade_hotels",
    7: "transport_comm",
    8: "financial",
    9: "real_estate_prof",
    10: "public_admin",
    11: "other_services",
}


@functools.cache
def sut_industry_group() -> dict[str, int]:
    with open(CONCORDANCE, encoding="utf-8", newline="") as f:
        return {f"sut_i{int(r['sut_industry']):02d}": int(r["nas_group"]) for r in csv.DictReader(f)}


SUT_ITEM = {  # item -> (dataset, series pattern with {ind})
    "output": ("io_tables_sut_supply", r"^supply\.output\.total\.{ind}\.current$"),
    "ic": ("io_tables_sut_use", r"^use\.ic\.total\.{ind}\.current$"),
    "gva": ("io_tables_sut_va", r"^va\.gva_production\.{ind}\.current$"),
    "ce": ("io_tables_sut_va", r"^va\.ce\.{ind}\.current$"),
}


def sut_group_value(item: str, groups: tuple[int, ...], period: str) -> float:
    ds, pat = SUT_ITEM[item]
    inds = [i for i, g in sut_industry_group().items() if g in groups]
    rx = pat.replace("{ind}", "(" + "|".join(inds) + ")")
    return value_sum("io_tables", ds, rx, period, min_rows=len(inds))


def sut_group(item: str, groups: tuple[int, ...], period: str) -> Term:
    names = "+".join(NAS_GROUPS[g] for g in groups)
    return Term(
        f"SUT {item}, industries in NAS group {names}",
        f"`{SUT_ITEM[item][0]}` summed over SUT industries with `nas_group` in {groups} "
        f"(`data/concordance/io_tables_sut_industry_to_sam34.csv`) ({period})",
        lambda: sut_group_value(item, groups, period),
    )


# HCES rows carry their survey window (period_type 'sy', Aug-Jul; hces_consumption-1/-26), not the FY.
# A check for FY X-Y reads the HCES round whose survey window starts in August of year X.
HCES_WINDOW = {"2022-23": "2022-08/2023-07", "2023-24": "2023-08/2024-07"}


def hces_aggregate(period: str, imputed: bool = False) -> Term:
    """HCES annual aggregate (Rs crore) = 12 x sum over rural/urban of persons x average MPCE."""
    tag = "hces2223" if period == "2022-23" else "hces2324"
    window = HCES_WINDOW[period]

    def fn() -> float:
        tot = 0.0
        for sector in ("rural", "urban"):
            persons = value(
                "hces_consumption", "hces_consumption_a2_fractile_persons", f"a2.{tag}.persons.in.{sector}_all", window
            )
            if imputed:
                mpce = value(
                    "hces_consumption",
                    "hces_consumption_report592_mpce",
                    f"t3_18.mpce_with_imputation.{sector}.current",
                    window,
                )
            else:
                mpce = value(
                    "hces_consumption",
                    "hces_consumption_a2_fractile_persons",
                    f"a2.{tag}.avg_mpce.in.{sector}_all.current",
                    window,
                )
            tot += persons * mpce * 12 / 1e7
        return tot

    what = "MPCE with imputation (Report 592 T3.18)" if imputed else "average MPCE (A2)"
    return Term(
        f"HCES aggregate ({'with' if imputed else 'without'} imputation)",
        f"`hces_consumption_a2_fractile_persons`: persons (rural_all, urban_all) x {what} x 12 / 1e7 "
        f"(survey window {window}, compared with FY {period})",
        fn,
    )


def fsf_nft(inst: str, period: str, coef: float = 1.0) -> Term:
    """FSF net financial transactions of a sector: transactions in assets less in liabilities."""
    ds = "rbi_financial_accounts_fsf_instrument_sector"

    def fn() -> float:
        a = value("rbi_financial_accounts", ds, f"fsf7.{inst}.assets.transaction.total.current", period)
        li = value("rbi_financial_accounts", ds, f"fsf7.{inst}.liabilities.transaction.total.current", period)
        return a - li

    return Term(
        f"FSF net financial transactions, {inst}",
        f"`{ds}`: `fsf7.{inst}.assets.transaction.total.current` less "
        f"`...liabilities.transaction.total.current` ({period})",
        fn,
        coef,
    )


# --------------------------------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------------------------------


@dataclass
class Check:
    id: str
    area: str
    period: str
    title: str
    a: list[Term]
    b: list[Term]
    verdict: str
    tol_pct: float
    note: str
    bridge: list[Term] = field(default_factory=list)
    tol_abs: float = 5.0  # Rs crore floor (rounding of published figures)
    ratio_range: tuple[float, float] | None = None

    def evaluate(self) -> dict:
        a = sum(t.get() for t in self.a)
        b = sum(t.get() for t in self.b)
        br = sum(t.get() for t in self.bridge)
        diff = a - b
        pct = 100 * diff / abs(b) if b else float("nan")
        resid = a - (b + br)
        tol = max(self.tol_abs, self.tol_pct / 100 * abs(b))
        if self.ratio_range:
            ratio = a / b
            ok = self.ratio_range[0] <= ratio <= self.ratio_range[1]
        else:
            ratio = None
            ok = abs(resid) <= tol
        return {
            "a": a,
            "b": b,
            "bridge": br,
            "diff": diff,
            "pct": pct,
            "resid": resid,
            "resid_pct": 100 * resid / abs(b) if b else float("nan"),
            "tol": tol,
            "ratio": ratio,
            "ok": ok,
        }


CHECKS: list[Check] = []


def add(*checks: Check) -> None:
    CHECKS.extend(checks)


NAS = "mospi_nas_2026"
IO = "io_tables"
UF = "union_fiscal"
SF = "state_fiscal"
EXT = "external_sector"
RFA = "rbi_financial_accounts"
RBC = "rbi_banking_corporate"
FM = "finsector_markets"


def nas11(sid: str, per: str, label: str, coef: float = 1.0) -> Term:
    return s(label, NAS, f"{NAS}_s1_1", f"s1_1.{sid}.current", per, coef)


def sutv(item: str, per: str, label: str, coef: float = 1.0, ds: str = "io_tables_sut_supply") -> Term:
    return s(label, IO, ds, item, per, coef)


# ---- GDP: NAS 1.1 vs SUT ---------------------------------------------------------------------------
for per in ("2022-23", "2023-24"):
    add(
        Check(
            f"GDP-1-{per}",
            "GDP",
            per,
            "GDP: NAS 1.1 vs SUT (GVA + product taxes + import duty - product subsidies)",
            [nas11("gdp", per, "NAS GDP")],
            [
                ssum(
                    "SUT GVA (67 industries)",
                    IO,
                    "io_tables_sut_va",
                    r"^va\.gva_production\.sut_i\d+\.current$",
                    per,
                    min_rows=67,
                ),
                sutv("supply.product_taxes.total.current", per, "SUT product taxes"),
                sutv("supply.import_duty.total.current", per, "SUT import duty"),
                sutv("supply.product_subsidies.total.current", per, "SUT product subsidies (stored negative)"),
            ],
            AGREE,
            0.001,
            "The SUT is the new-base benchmark from which NAS 2026 GDP is built.",
        ),
        Check(
            f"GDP-2-{per}",
            "GDP",
            per,
            "GVA at basic prices: NAS 1.1 vs SUT sum of 67 industries",
            [nas11("gva_basic", per, "NAS GVA")],
            [ssum("SUT GVA", IO, "io_tables_sut_va", r"^va\.gva_production\.sut_i\d+\.current$", per, min_rows=67)],
            AGREE,
            0.001,
            "",
        ),
        Check(
            f"GDP-3-{per}",
            "GDP",
            per,
            "Net product taxes: NAS 1.1 (taxes - subsidies) vs SUT valuation columns",
            [
                nas11("taxes_on_products", per, "NAS taxes on products incl. import duties"),
                nas11("subsidies_on_products", per, "NAS subsidies on products", -1),
            ],
            [
                sutv("supply.product_taxes.total.current", per, "SUT product taxes"),
                sutv("supply.import_duty.total.current", per, "SUT import duty"),
                sutv("supply.product_subsidies.total.current", per, "SUT product subsidies (negative)"),
            ],
            AGREE,
            0.001,
            "",
        ),
        Check(
            f"GDP-4-{per}",
            "GDP",
            per,
            "GDP by expenditure: NAS 1.1 vs SUT final-use columns",
            [nas11("gdp", per, "NAS GDP")],
            [
                sutv("use.pfce.total.current", per, "SUT PFCE", ds="io_tables_sut_use"),
                sutv("use.gfce.total.current", per, "SUT GFCE", ds="io_tables_sut_use"),
                sutv("use.gfcf.total.current", per, "SUT GFCF", ds="io_tables_sut_use"),
                sutv("use.cii.total.current", per, "SUT change in inventories", ds="io_tables_sut_use"),
                sutv("use.valuables.total.current", per, "SUT valuables", ds="io_tables_sut_use"),
                sutv("use.exports.total.current", per, "SUT exports", ds="io_tables_sut_use"),
                sutv("supply.imports_after_cif.total.current", per, "SUT imports after CIF adjustment", -1),
            ],
            AGREE,
            0.001,
            "NAS 2026 shows a zero discrepancy for 2022-23 and 2023-24, so the SUT final uses close GDP exactly.",
        ),
        Check(
            f"GDP-5-{per}",
            "GDP",
            per,
            "Output: NAS 7.1 total vs SUT total output",
            [s("NAS output", NAS, f"{NAS}_s7_1", "s7_1.total.output.current", per)],
            [
                ssum(
                    "SUT output",
                    IO,
                    "io_tables_sut_supply",
                    r"^supply\.output\.total\.sut_i\d+\.current$",
                    per,
                    min_rows=67,
                )
            ],
            AGREE,
            0.001,
            "",
        ),
        Check(
            f"GDP-6-{per}",
            "GDP",
            per,
            "Intermediate consumption: NAS 7.1 total vs SUT",
            [s("NAS IC", NAS, f"{NAS}_s7_1", "s7_1.total.ic.current", per)],
            [sutv("use.ic_total.total.current", per, "SUT IC", ds="io_tables_sut_use")],
            AGREE,
            0.001,
            "",
        ),
    )

# ---- Industry: NAS 7.1 by group vs SUT via the concordance's nas_group -----------------------------
for per in ("2022-23", "2023-24"):
    for item in ("output", "ic", "gva", "ce"):
        for g in (1, 2, 3, 4, 5, 6, 7, 8, 10):
            add(
                Check(
                    f"IND-{NAS_GROUPS[g]}-{item}-{per}",
                    "Industry",
                    per,
                    f"{item.upper()} of {NAS_GROUPS[g]}: NAS 7.1 vs SUT",
                    [s(f"NAS {item}", NAS, f"{NAS}_s7_1", f"s7_1.{NAS_GROUPS[g]}.{item}.current", per)],
                    [sut_group(item, (g,), per)],
                    AGREE,
                    0.001,
                    "",
                )
            )
        add(
            Check(
                f"IND-re+os-{item}-{per}",
                "Industry",
                per,
                f"{item.upper()} of real estate & prof. + other services: NAS 7.1 vs SUT",
                [
                    s(f"NAS {item}", NAS, f"{NAS}_s7_1", f"s7_1.real_estate_prof.{item}.current", per),
                    s(f"NAS {item}", NAS, f"{NAS}_s7_1", f"s7_1.other_services.{item}.current", per),
                ],
                [sut_group(item, (9, 11), per)],
                AGREE,
                0.001,
                "The two groups together agree exactly; see IND-re-output for the split.",
            )
        )
    rnd = "s8_13.professional_scientific_and_technical_services_including_r_a.output.current"
    add(
        Check(
            f"IND-re-output-{per}",
            "Industry",
            per,
            "Output of real estate, dwellings & professional services: NAS 7.1 vs SUT (concordance group 9)",
            [s("NAS output", NAS, f"{NAS}_s7_1", "s7_1.real_estate_prof.output.current", per)],
            [sut_group("output", (9,), per)],
            EXPLAINED,
            0.001,
            "SUT industry 58 'Education & Research' holds research & development (NIC 72), which NAS "
            "classifies under professional services. The gap equals NAS 8.13 'professional, scientific "
            "and technical services incl. R&D' output exactly. Finding for io_tables: the concordance "
            "puts all of SUT 58 in NAS group 11.",
            bridge=[s("NAS 8.13 prof./scientific/technical incl. R&D output", NAS, f"{NAS}_s8_13", rnd, per)],
        ),
        Check(
            f"IND-os-output-{per}",
            "Industry",
            per,
            "Output of other services: NAS 7.1 vs SUT (concordance group 11)",
            [s("NAS output", NAS, f"{NAS}_s7_1", "s7_1.other_services.output.current", per)],
            [sut_group("output", (11,), per)],
            EXPLAINED,
            0.001,
            "Mirror of IND-re-output: the R&D output sits in SUT 58 (group 11) but in NAS professional services.",
            bridge=[s("NAS 8.13 R&D output (moved out)", NAS, f"{NAS}_s8_13", rnd, per, -1)],
        ),
    )

# ---- Government -----------------------------------------------------------------------------------
P = "2023-24"
FA_R = "union_fiscal_fa_receipts"
SFA = "state_fiscal_rbi_sf_appendices"
KFI = "state_fiscal_fc16_kfi"


def fa(sid: str, label: str, coef: float = 1.0) -> Term:
    return s(label, UF, FA_R, sid, P, coef)


def sfa(sid: str, label: str, coef: float = 1.0) -> Term:
    return s(label, SF, SFA, f"{sid}.in.all_states_uts.actuals", P, coef)


def kfi(sid: str, label: str, per: str = P, coef: float = 1.0) -> Term:
    return s(label, SF, KFI, f"kfi.{sid}.in.all_states_28", per, coef)


def st(table: str, sid: str, geo: str, label: str, coef: float = 1.0) -> Term:
    return s(label, SF, "state_fiscal_rbi_sf_statements", f"st{table}.{sid}.{geo}.actuals", P, coef)


def ut_share_of(total_sid: str, share_table: str, share_item: str, label: str) -> Term:
    """Delhi + J&K + Puducherry part of an all-States-and-UTs total, from their published % shares."""

    def fn() -> float:
        tot = value(SF, SFA, f"{total_sid}.in.all_states_uts.actuals", P)
        sh = sum(
            value(SF, "state_fiscal_rbi_sf_statements", f"st{share_table}.{share_item}.{g}.actuals", P)
            for g in ("in-dl", "in-jk", "in-py")
        )
        return tot * sh / 100

    return Term(
        label,
        f"`{SFA}`: `{total_sid}` x (Delhi + J&K + Puducherry % shares in "
        f"`state_fiscal_rbi_sf_statements` St {share_table} `{share_item}`) ({P})",
        fn,
        -1,
    )


FA901 = r"^fa8\.00\d\d(\.\d\d)?\.901$"
add(
    Check(
        "GOV-1-2023-24",
        "Government",
        P,
        "Devolution: Union 'share of net proceeds assigned to States' (FA) vs States' share in central taxes (RBI SF, all States & UTs)",
        [ssum("Union FA minor head 901, all taxes", UF, FA_R, FA901, P, coef=-1, min_rows=5)],
        [sfa("app1.total_revenue.i.b-share_in_central_taxes", "RBI SF: share in central taxes")],
        AGREE,
        0.05,
        "Union outflow equals State-side receipt.",
    ),
    Check(
        "GOV-2-2023-24",
        "Government",
        P,
        "Devolution: Union FA vs FC16 KFI States' share (28 States)",
        [ssum("Union FA minor head 901", UF, FA_R, FA901, P, coef=-1, min_rows=5)],
        [kfi("a_1_3-state_s_share_in_union_taxes_and_duties", "FC16 KFI A.1.3")],
        AGREE,
        0.05,
        "UTs with legislature get no tax devolution, so 28 States = all.",
    ),
    Check(
        "GOV-3-2023-24",
        "Government",
        P,
        "Devolution: Receipt Budget 'Less States' share' vs Finance Accounts minor head 901",
        [s("Receipt Budget", UF, "union_fiscal_rb_receipts", "rb.tr.0710.less_states_share", P, -1)],
        [ssum("FA minor head 901", UF, FA_R, FA901, P, coef=-1, min_rows=5)],
        AGREE,
        0.001,
        "",
    ),
)
for fa_sid, sf_sid, name in (
    ("fa8.0005.00.901", "app1.total_revenue.i.b.i-central_goods_and_services_tax_cgst", "CGST"),
    ("fa8.0020.00.901", "app1.total_revenue.i.b.ii-corporation_tax", "corporation tax"),
    ("fa8.0021.00.901", "app1.total_revenue.i.b.iii-income_tax", "income tax"),
    ("fa8.0037.00.901", "app1.total_revenue.i.b.vii-customs", "customs"),
    ("fa8.0038.01.901", "app1.total_revenue.i.b.viii-union_excise_duties", "Union excise"),
):
    add(
        Check(
            f"GOV-4-{name.replace(' ', '_')}-2023-24",
            "Government",
            P,
            f"Devolution of {name}: Union FA (minor head 901) vs RBI SF States' receipt",
            [fa(fa_sid, f"FA {name} assigned to States", -1)],
            [sfa(sf_sid, f"SF share: {name}")],
            AGREE,
            0.1,
            "",
        )
    )

INT_SF = "app2.total_expenditure.ii.c.2-interest_payments"
add(
    Check(
        "GOV-5-2023-24",
        "Government",
        P,
        "State interest payments: RBI SF (all States & UTs, less Delhi, J&K, Puducherry) vs FC16 KFI (28 States)",
        [kfi("b_1_a-interest_payments", "FC16 KFI B.1.a interest")],
        [sfa(INT_SF, "RBI SF interest payments, all States & UTs")],
        EXPLAINED,
        0.5,
        "Coverage: RBI SF includes the three UTs with legislature; their interest (SF Statement 13) bridges the gap.",
        bridge=[
            st("13", "interest_payments_gross", g, f"St 13 interest, {g}", -1) for g in ("in-dl", "in-jk", "in-py")
        ],
    ),
    Check(
        "GOV-6-2023-24",
        "Government",
        P,
        "Union interest payments: Finance Accounts vs Annual Financial Statement (MH 2049)",
        [s("FA 2049", UF, "union_fiscal_fa_expenditure", "fa9.2049.total", P)],
        [s("AFS 2049", UF, "union_fiscal_afs", "afs.cfi_rev_disbursements.2049", P)],
        AGREE,
        0.001,
        "",
    ),
    Check(
        "GOV-7-2023-24",
        "Government",
        P,
        "Interest on Central loans: Union receipt (FA 0049-01 + 0049-02) vs States' payment (RBI SF)",
        [
            fa("fa8.0049.01.total", "FA interest from State govts"),
            fa("fa8.0049.02.total", "FA interest from UTs with legislature"),
        ],
        [
            sfa(
                "app2.total_expenditure.ii.c.2.i-interest_on_loans_from_the_centre",
                "RBI SF interest on loans from the Centre",
            )
        ],
        UNEXPLAINED,
        1.0,
        "States report paying 1,431 crore (10%) more interest to the Centre than the Union books as received. Not bridged by UT coverage (UT receipts are only 86 crore). Possible causes to confirm: interest on back-to-back GST-compensation loans or 50-year capex loans booked differently on each side.",
    ),
    Check(
        "GOV-8-2023-24",
        "Government",
        P,
        "Grants from the Centre: RBI SF (less UTs via St 15 shares) vs FC16 KFI (28 States)",
        [kfi("a_1_4-grants_in_aid_from_goi", "FC16 KFI A.1.4 grants")],
        [sfa("app1.total_revenue.ii.d-grants_from_the_centre", "RBI SF grants from the Centre")],
        EXPLAINED,
        0.5,
        "Coverage: Delhi, J&K and Puducherry hold 10.5% of grants (St 15 shares, rounded to 0.1 pp).",
        bridge=[
            ut_share_of(
                "app1.total_revenue.ii.d-grants_from_the_centre", "15", "grants_share", "UTs' grants (share-based)"
            )
        ],
    ),
    Check(
        "GOV-9-2023-24",
        "Government",
        P,
        "Grants to States: Union (AFS MH 3601 + St 18 transfers to Delhi/J&K/Puducherry) vs RBI SF grants received",
        [
            s("AFS 3601 grants to State govts", UF, "union_fiscal_afs", "afs.cfi_rev_disbursements.3601", P),
            s(
                "Exp. Profile St 18 IV: Delhi, Puducherry, J&K",
                UF,
                "union_fiscal_exp_profile",
                "stat18.transfers_to_delhi_puducherry_and_jammu_kashmir",
                P,
            ),
        ],
        [sfa("app1.total_revenue.ii.d-grants_from_the_centre", "RBI SF grants from the Centre")],
        UNEXPLAINED,
        2.0,
        "Union-side grants exceed State-side receipts by ~67,000 crore (12.7%). Known issue H9 (GAP_MAP): Union grant heads include releases outside State treasuries and loan-like items; not bridged with ingested data.",
    ),
    Check(
        "GOV-10-2023-24",
        "Government",
        P,
        "Finance Commission grants: Union Exp. Profile St 18 vs RBI SF",
        [s("St 18 II FC grants", UF, "union_fiscal_exp_profile", "stat18.finance_commission_grants", P)],
        [sfa("app1.total_revenue.ii.d.5-finance_commission_grants", "RBI SF FC grants")],
        UNEXPLAINED,
        1.0,
        "Union shows 4,605 crore (3.2%) more FC grants than States record; largest item-level gaps are post-devolution revenue deficit grants (51,673 vs 48,110) and rural local-body grants (47,260 vs 44,268). Timing of March releases is the usual suspect; not verified.",
    ),
    Check(
        "GOV-11-2023-24",
        "Government",
        P,
        "RBI surplus: Union Finance Accounts receipt (FY 2023-24) vs RBI Annual Report surplus transferred for RBI year 2022-23",
        [fa("fa8.0050.00.106", "FA share of surplus profits from RBI")],
        [
            s(
                "RBI AR Table XII.1 surplus transferred (RBI year 2022-23)",
                RBC,
                "rbi_banking_corporate_rbi_accounts",
                "xii_1.surplus_transferred.current",
                "2022-23",
            )
        ],
        AGREE,
        0.001,
        "Cash basis (DECISIONS D0-7): the Centre receives RBI's year-t surplus in fiscal year t+1.",
    ),
    Check(
        "GOV-12-2023-24",
        "Government",
        P,
        "State government value added (= compensation of employees): NAS 4.1 vs FC16 KFI salaries (28 States)",
        [s("NAS 4.1 State government", NAS, f"{NAS}_s4_1", "s4_1.state_government.current", P)],
        [kfi("b_1_c-salaries", "FC16 KFI B.1.c salaries")],
        UNEXPLAINED,
        5.0,
        "NAS CE is 8.4% above budget salaries. Expected direction (NAS CE adds employer social contributions, incl. NPS and imputed pensions, and covers the UTs with legislature), but no ingested source quantifies those items, so the size is not verified.",
    ),
    Check(
        "GOV-13-2023-24",
        "Government",
        P,
        "General government gross saving: NAS 1.14 vs RBI HBS T11 (base 2022-23)",
        [s("NAS 1.14 GG gross saving", NAS, f"{NAS}_s1_14", "s1_14.gg.gross_savings.current", P)],
        [s("HBS T11 GG", RFA, "rbi_financial_accounts_hbs_saving", "t11.gross_saving_gg.base2022.current", P)],
        EXPLAINED,
        1.0,
        "Vintage: HBS 2025-26 (Jul 2026) reproduces the Feb 2026 first release of the new series; NAS 2026 (31 Aug 2026) revised it.",
    ),
)

# ---- Taxes ----------------------------------------------------------------------------------------
RB = "union_fiscal_rb_receipts"


def rb(sid: str, label: str, per: str = P, coef: float = 1.0) -> Term:
    return s(label, UF, RB, sid, per, coef)


UNION_PRODUCT_TAXES = [  # gross (before States' share), Receipt Budget Actuals
    ("rb.tr.0005.central_goods_and_services_tax_cgst", "CGST"),
    ("rb.tr.0007.union_territories_goods_and_services_tax_utgst", "UTGST"),
    ("rb.tr.0008.integrated_goods_and_services_tax_igst", "IGST (net of settlement)"),
    ("rb.tr.0009.gst_compensation_cess", "GST compensation cess"),
    ("rb.tr.total.total_customs", "customs (incl. export duty)"),
    ("rb.tr.total.total_union_excise_duties", "Union excise"),
    ("rb.tr.total.total_service_tax", "service tax (arrears)"),
    ("rb.tr.total.total_other_taxes_and_duties_on_commodities_and_services", "other commodity taxes"),
]
STATE_PRODUCT_TAXES = [  # RBI SF Appendix I, all States & UTs
    ("app1.total_revenue.i.a.3.vii-state_goods_and_services_tax", "SGST"),
    ("app1.total_revenue.i.a.3.i-sales_tax", "sales tax/VAT"),
    ("app1.total_revenue.i.a.3.ii-state_excise", "State excise"),
    ("app1.total_revenue.i.a.3.v-taxes_and_duties_on_electricity", "electricity duty"),
    ("app1.total_revenue.i.a.3.iv-taxes_on_goods_and_passengers", "goods & passengers"),
    ("app1.total_revenue.i.a.3.vi-entertainment_tax", "entertainment tax"),
    ("app1.total_revenue.i.a.3.viii-other_taxes_and_duties", "other taxes & duties"),
]
add(
    Check(
        "TAX-1-2023-24",
        "Taxes",
        P,
        "Product taxes: SUT (product taxes + import duty) vs Union gross + State product-tax receipts",
        [
            sutv("supply.product_taxes.total.current", P, "SUT product taxes"),
            sutv("supply.import_duty.total.current", P, "SUT import duty"),
        ],
        [rb(sid, f"Union {n}") for sid, n in UNION_PRODUCT_TAXES]
        + [sfa(sid, f"States {n}") for sid, n in STATE_PRODUCT_TAXES],
        UNEXPLAINED,
        2.0,
        "SUT exceeds budget receipts by ~1.6 lakh crore (5.2%). Candidates, none verified: State taxes on vehicles (1.10 lakh cr, excluded here as they are partly D59/D29; including them leaves 50,243 crore, 1.6%), local-body taxes, accrual vs cash timing of GST, and refunds. Phase 2 must allocate this gap in P7a (two-margin GRAS).",
    ),
    Check(
        "TAX-2-2023-24",
        "Taxes",
        P,
        "Import duty: SUT vs Union customs less export duty and export cesses",
        [sutv("supply.import_duty.total.current", P, "SUT import duty")],
        [rb("rb.tr.total.total_customs", "Receipt Budget total customs")],
        EXPLAINED,
        0.5,
        "Customs receipts include export duty (a product tax on exports, not an import duty). Remaining gap 885 crore (0.4%) is within tolerance (cash vs accrual).",
        bridge=[
            rb("rb.tr.0037.export_duty", "export duty", coef=-1),
            rb("rb.tr.0037.cesses_on_exports", "cesses on exports", coef=-1),
        ],
    ),
    Check(
        "TAX-3-2023-24",
        "Taxes",
        P,
        "Gross CGST: Receipt Budget vs Finance Accounts (net + States' share)",
        [rb("rb.tr.0005.central_goods_and_services_tax_cgst", "RB CGST")],
        [fa("fa8.0005.total", "FA CGST net"), fa("fa8.0005.00.901", "FA CGST assigned to States", -1)],
        AGREE,
        0.001,
        "",
    ),
    Check(
        "TAX-4-2023-24",
        "Taxes",
        P,
        "Union GST total (Receipt Budget) = CGST + IGST + compensation cess",
        [rb("rb.tr.total.total_goods_and_services_tax_gst", "RB total GST")],
        [
            rb("rb.tr.0005.central_goods_and_services_tax_cgst", "CGST"),
            rb("rb.tr.0008.integrated_goods_and_services_tax_igst", "IGST"),
            rb("rb.tr.0009.gst_compensation_cess", "cess"),
        ],
        AGREE,
        0.001,
        "UTGST sits under 'Taxes of Union Territories', not in the GST total.",
    ),
    Check(
        "TAX-5-2023-24",
        "Taxes",
        P,
        "SGST: RBI SF (all States & UTs) vs FC16 KFI (28 States)",
        [sfa("app1.total_revenue.i.a.3.vii-state_goods_and_services_tax", "RBI SF SGST")],
        [kfi("a_1_1_2-state_goods_and_service_tax", "FC16 KFI SGST")],
        EXPLAINED,
        6.0,
        "Coverage: RBI SF adds Delhi, J&K and Puducherry (3.7% of all own-tax revenue per St 14); SGST gap 41,009 crore (5.1%). No per-UT SGST in the clean data, so conceptual.",
    ),
    Check(
        "TAX-6-2023-24",
        "Taxes",
        P,
        "SGST: FC16 KFI vs FC16 State Finance Accounts major head 0006 (28 States)",
        [kfi("a_1_1_2-state_goods_and_service_tax", "FC16 KFI SGST")],
        [
            ssum(
                "FC16 state accounts MH 0006",
                SF,
                "state_fiscal_fc16_state_accounts",
                r"^fa\.revenue_receipts\.mh0006\.in-[a-z]{2}$",
                P,
                min_rows=28,
            )
        ],
        AGREE,
        0.01,
        "",
    ),
    Check(
        "TAX-7-2023-24",
        "Taxes",
        P,
        "GST symmetry: Union gross CGST + UTGST vs States' SGST (post-settlement)",
        [
            rb("rb.tr.0005.central_goods_and_services_tax_cgst", "CGST"),
            rb("rb.tr.0007.union_territories_goods_and_services_tax_utgst", "UTGST"),
        ],
        [sfa("app1.total_revenue.i.a.3.vii-state_goods_and_services_tax", "SGST, all States & UTs")],
        EXPLAINED,
        2.5,
        "After IGST settlement the central and state legs should be near-equal. CGST includes an advance-apportionment reversal of -9,000 crore (FA 0005-110) and settlement timing differs; not bridged.",
    ),
    Check(
        "TAX-8-2022-23",
        "Taxes",
        "2022-23",
        "Taxes on products 2022-23: NAS new base (1.1) vs NAS old base (SOA 4.0 D21, GG receivable)",
        [nas11("taxes_on_products", "2022-23", "NAS 2026 taxes on products")],
        [
            s(
                "Old-base D21",
                NAS,
                f"{NAS}_oldbase_soa_s4_0",
                "oldbase_soa_s4_0.allocation_of_primary_income.resources.d21.current",
                "2022-23",
            )
        ],
        UNEXPLAINED,
        1.0,
        "The new base records 1.17 lakh crore (3.8%) less product tax for the same year. Taxes are cash data, so this is a treatment change (e.g. GST refunds, cess, or reclassification to D29/D5) that S&M 2026 would have to confirm. Matters for splicing the Phase 2 time series.",
    ),
    Check(
        "TAX-9-2023-24",
        "Taxes",
        P,
        "Product subsidies: SUT vs Union (fertiliser + petroleum + other) + States (RBI SF St 36)",
        [sutv("supply.product_subsidies.total.current", P, "SUT product subsidies", coef=-1)],
        [
            s("Union fertiliser", UF, "union_fiscal_exp_profile", "stat7.fertiliser", P),
            s("Union petroleum", UF, "union_fiscal_exp_profile", "stat7.petroleum", P),
            s("Union other subsidies", UF, "union_fiscal_exp_profile", "stat7.other_subsidies", P),
            st("36", "subsidies", "in.all_states_uts", "States' subsidies (St 36)"),
        ],
        UNEXPLAINED,
        3.0,
        "Food subsidy excluded (GFCE in NAS 2026, D0-5) and interest subsidies excluded (D39). SUT is 43,000 crore (8%) higher; States' St 36 mixes product and production subsidies and local bodies are missing, so the split is not verified.",
    ),
    Check(
        "TAX-10-2023-24",
        "Taxes",
        P,
        "Union fertiliser subsidy: Exp. Profile St 7 vs FC16 subsidy table",
        [s("St 7 fertiliser", UF, "union_fiscal_exp_profile", "stat7.fertiliser", P)],
        [s("FC16 Union fertiliser", SF, "state_fiscal_fc16_subsidies", "sub.fertilizer.in.gg_centre", P)],
        AGREE,
        0.01,
        "",
    ),
    Check(
        "TAX-11-2023-24",
        "Taxes",
        P,
        "Union food subsidy: Exp. Profile St 7 vs FC16 subsidy table",
        [s("St 7 food", UF, "union_fiscal_exp_profile", "stat7.food", P)],
        [s("FC16 Union food", SF, "state_fiscal_fc16_subsidies", "sub.food.in.gg_centre", P)],
        UNEXPLAINED,
        1.0,
        "FC16 is 18,942 crore (8%) higher; FC16's 'subsidies and transfers' definition likely adds food-related transfers outside St 7; not verified.",
    ),
    Check(
        "TAX-12-2023-24",
        "Taxes",
        P,
        "Union petroleum subsidy: Exp. Profile St 7 vs FC16 'fuel'",
        [s("St 7 petroleum", UF, "union_fiscal_exp_profile", "stat7.petroleum", P)],
        [s("FC16 Union fuel", SF, "state_fiscal_fc16_subsidies", "sub.fuel.in.gg_centre", P)],
        UNEXPLAINED,
        1.0,
        "St 7 LPG subsidy 12,240 vs FC16 fuel 8,500; classification unknown.",
    ),
)
for sid, fa_net, fa_share, name in (
    ("rb.tr.total.total_corporation_tax", "fa8.0020.total", "fa8.0020.00.901", "corporation tax"),
    ("rb.tr.total.total_customs", "fa8.0037.total", "fa8.0037.00.901", "customs"),
):
    add(
        Check(
            f"TAX-13-{name.replace(' ', '_')}-2023-24",
            "Taxes",
            P,
            f"Gross {name}: Receipt Budget vs Finance Accounts (net + States' share)",
            [rb(sid, f"RB {name}")],
            [fa(fa_net, "FA net"), fa(fa_share, "FA assigned to States", -1)],
            AGREE,
            0.01,
            "",
        )
    )
add(
    Check(
        "TAX-13-income_tax-2023-24",
        "Taxes",
        P,
        "Gross income tax: Receipt Budget (0021 items) vs Finance Accounts (net + States' share)",
        [ssum("RB 0021 items", UF, RB, r"^rb\.tr\.0021\.", P, min_rows=5)],
        [fa("fa8.0021.total", "FA net"), fa("fa8.0021.00.901", "FA assigned to States", -1)],
        AGREE,
        0.01,
        "",
    )
)

add(
    Check(
        "TAX-14-2022-23",
        "Taxes",
        "2022-23",
        "Current taxes on income: NAS old base (SOA 4.0 D5) vs Union gross corporation tax + income tax (Receipt Budget)",
        [
            s(
                "Old-base D5",
                NAS,
                f"{NAS}_oldbase_soa_s4_0",
                "oldbase_soa_s4_0.secondary_distribution_of_income.resources.d5.current",
                "2022-23",
            )
        ],
        [
            rb("rb.tr.total.total_corporation_tax", "RB corporation tax", per="2022-23"),
            ssum("RB 0021 items (income tax)", UF, RB, r"^rb\.tr\.0021\.", "2022-23", min_rows=5),
        ],
        EXPLAINED,
        1.0,
        "D5 also holds small State taxes on income (professions tax, agricultural income tax). The 0.3% gap leaves no room for State motor-vehicle taxes in D5, which suggests NAS books them elsewhere (relevant to TAX-1); not confirmed.",
    )
)

# ---- External ------------------------------------------------------------------------------------
BOP = "external_sector_bop_bpm6_annual"


def bop(code: str, side: str, per: str, label: str, coef: float = 1.0) -> Term:
    return s(label, EXT, BOP, f"bpm6.inr.{code}.{side}.current", per, coef)


def n61(sid: str, per: str, label: str, coef: float = 1.0) -> Term:
    return s(label, NAS, f"{NAS}_s6_1", f"s6_1.{sid}.current", per, coef)


for per in ("2022-23", "2023-24"):
    add(
        Check(
            f"EXT-1-{per}",
            "External",
            per,
            "Exports of goods & services: NAS 1.1 vs BoP (BPM6) credit",
            [nas11("exports", per, "NAS exports")],
            [bop("bpm6_1_a", "credit", per, "BoP G&S credit")],
            AGREE,
            0.001,
            "",
        ),
        Check(
            f"EXT-2-{per}",
            "External",
            per,
            "Imports: NAS 6.1 (unadjusted) vs BoP G&S debit",
            [n61("imports", per, "NAS 6.1 imports")],
            [bop("bpm6_1_a", "debit", per, "BoP G&S debit")],
            AGREE,
            0.001,
            "",
        ),
        Check(
            f"EXT-3-{per}",
            "External",
            per,
            "Imports: NAS 1.1 (CIF-adjusted) vs BoP G&S debit",
            [nas11("imports", per, "NAS 1.1 imports")],
            [bop("bpm6_1_a", "debit", per, "BoP G&S debit")],
            EXPLAINED,
            0.001,
            "NAS 1.1 deducts the CIF adjustment on imports of services (NAS 6.1 memo; the X_DISC cell D2).",
            bridge=[n61("adjustment_for_cif_in_import_of_services", per, "CIF adjustment", -1)],
        ),
        Check(
            f"EXT-4-{per}",
            "External",
            per,
            "Current receipts: NAS 6.1 vs BoP current-account credit",
            [n61("current_receipts", per, "NAS 6.1 current receipts")],
            [bop("bpm6_1", "credit", per, "BoP CA credit")],
            EXPLAINED,
            0.001,
            "NAS books general-government transfers with RoW in the capital account (6.1 'capital transfers to GG'), BoP in secondary income.",
            bridge=[bop("bpm6_1_c_2", "credit", per, "BoP GG secondary income credit", -1)],
        ),
        Check(
            f"EXT-5-{per}",
            "External",
            per,
            "Current disbursements: NAS 6.1 vs BoP current-account debit",
            [n61("current_disbursements", per, "NAS 6.1")],
            [bop("bpm6_1", "debit", per, "BoP CA debit")],
            EXPLAINED,
            0.001,
            "As EXT-4.",
            bridge=[bop("bpm6_1_c_2", "debit", per, "BoP GG secondary income debit", -1)],
        ),
        Check(
            f"EXT-6-{per}",
            "External",
            per,
            "Current balance: NAS 6.1 surplus on current transactions vs BoP current account",
            [n61("surplus_on_current_transactions", per, "NAS 6.1")],
            [bop("bpm6_1", "net", per, "BoP CA net")],
            EXPLAINED,
            0.001,
            "As EXT-4.",
            bridge=[bop("bpm6_1_c_2", "net", per, "BoP GG secondary income net", -1)],
        ),
        Check(
            f"EXT-7-{per}",
            "External",
            per,
            "Net lending to RoW: NAS 6.1 vs BoP current + capital account",
            [n61("net_lending_to_the_rest_of_the_world_13_14_15_16_or_18_19", per, "NAS 6.1 net lending")],
            [bop("bpm6_1", "net", per, "BoP CA"), bop("bpm6_2", "net", per, "BoP capital account")],
            AGREE,
            0.001,
            "",
        ),
        Check(
            f"EXT-8-{per}",
            "External",
            per,
            "Primary income (net): NAS 1.1 vs BoP",
            [nas11("primary_income_row_net", per, "NAS 1.1")],
            [bop("bpm6_1_b", "net", per, "BoP primary income")],
            AGREE,
            0.001,
            "",
        ),
        Check(
            f"EXT-9-{per}",
            "External",
            per,
            "Private transfers (remittances) received: NAS 6.1 vs BoP invisibles (private transfers receipts)",
            [n61("other_current_transfers_to_resident_sectors_other_than_gener", per, "NAS 6.1")],
            [
                s(
                    "BoP private transfers receipts",
                    EXT,
                    "external_sector_invisibles_annual",
                    "invis.inr.private_transfers.receipts.current",
                    per,
                )
            ],
            AGREE,
            0.001,
            "",
        ),
        Check(
            f"EXT-10-{per}",
            "External",
            per,
            "Net private transfers: NAS 1.1 vs BoP secondary income (non-GG) net",
            [nas11("other_current_transfers_row_net", per, "NAS 1.1")],
            [bop("bpm6_1_c_1", "net", per, "BoP")],
            AGREE,
            0.001,
            "",
        ),
        Check(
            f"EXT-11-{per}",
            "External",
            per,
            "Goods exports: NAS 6.1 vs BoP goods credit",
            [n61("exports.goods", per, "NAS 6.1 goods")],
            [bop("bpm6_1_a_a", "credit", per, "BoP goods credit")],
            EXPLAINED,
            0.001,
            "NAS counts goods sent for processing with goods; BoP shows them as manufacturing services.",
            bridge=[bop("bpm6_1_a_b_1", "credit", per, "BoP manufacturing services on inputs owned by others")],
        ),
        Check(
            f"EXT-12-{per}",
            "External",
            per,
            "FDI to India (net): RBI HBS T143 vs BoP BPM6 3.1.A",
            [s("HBS T143", EXT, "external_sector_foreign_investment", "t143.inr.fdi_to_india_net.current", per)],
            [bop("bpm6_3_1_a", "net", per, "BoP DI in India")],
            AGREE,
            0.001,
            "Same RBI compilation; a consistency check, not an independent one.",
        ),
        Check(
            f"EXT-13-{per}",
            "External",
            per,
            "Financial account: FSF RoW net financial transactions vs BoP financial account (net)",
            [fsf_nft("row", per)],
            [bop("bpm6_3", "net", per, "BoP financial account net")],
            AGREE,
            0.2,
            "",
        ),
    )
add(
    Check(
        "EXT-14-2023-24",
        "External",
        P,
        "NAS 6.1 capital transfers to GG vs BoP (old format) official transfers, net",
        [n61("capital_transfers_to_general_government_from_the_rest_of_the", P, "NAS 6.1")],
        [
            s(
                "BoP official transfers net",
                EXT,
                "external_sector_invisibles_annual",
                "invis.inr.official_transfers.net.current",
                P,
            )
        ],
        AGREE,
        0.1,
        "Confirms NAS puts official transfers in the capital account (see EXT-4).",
    ),
    Check(
        "EXT-15-2023-24",
        "External",
        P,
        "FPI: BoP portfolio investment in India (FIIs, net) vs SEBI/NSDL FPI net investment",
        [bop("bpm6_3_2_a", "net", P, "BoP portfolio investment in India")],
        [s("SEBI T59 FPI net investment", FM, "finsector_markets_sebi_foreign", "t59.net_investment.current", P)],
        UNEXPLAINED,
        3.0,
        "BoP is 30,208 crore (8.9%) above NSDL. ADR/GDR issues were nil (BoP old format), so they do not explain it. Candidates: BoP settlement vs NSDL trade date, and portfolio flows outside the FPI route; not verified.",
    ),
    Check(
        "EXT-16-2023-24",
        "External",
        P,
        "FDI: SEBI Handbook T58 vs RBI HBS T143 (direct investment to India)",
        [s("SEBI T58", FM, "finsector_markets_sebi_foreign", "t58.fdi_direct_investment_to_india.current", P)],
        [s("HBS T143", EXT, "external_sector_foreign_investment", "t143.inr.fdi_to_india_net.current", P)],
        AGREE,
        0.001,
        "SEBI republishes RBI data.",
    ),
)

# ---- Households -----------------------------------------------------------------------------------
H52 = "rbi_financial_accounts_hh_finsav_52ab"
for per in ("2022-23", "2023-24"):
    add(
        Check(
            f"HH-1-{per}",
            "Households",
            per,
            "HCES aggregate consumption vs NAS PFCE (ratio)",
            [hces_aggregate(per)],
            [nas11("pfce", per, "NAS PFCE")],
            EXPLAINED,
            0.0,
            "Known NSS-NAS gap (GAP_MAP H1: ~44%). HCES survey years run Aug-Jul, not Apr-Mar; HCES excludes NPISH, imputed rent and FISIM, and under-covers the rich.",
            ratio_range=(0.40, 0.48),
        ),
        Check(
            f"HH-2-{per}",
            "Households",
            per,
            "Household gross financial saving: NAS 5.3 vs RBI Bulletin T52(a) financial assets",
            [s("NAS 5.3", NAS, f"{NAS}_s5_3", "s5_3.gross_financial_saving.current", per)],
            [s("RBI T52(a)", RFA, H52, "t52a.fa.current.fy", per)],
            AGREE,
            0.1,
            "NAS takes this block from RBI.",
        ),
        Check(
            f"HH-3-{per}",
            "Households",
            per,
            "Household financial liabilities: NAS 5.3 vs RBI T52(a)",
            [s("NAS 5.3", NAS, f"{NAS}_s5_3", "s5_3.financial_liabilities.current", per)],
            [s("RBI T52(a)", RFA, H52, "t52a.fl.current.fy", per)],
            AGREE,
            0.1,
            "",
        ),
        Check(
            f"HH-4-{per}",
            "Households",
            per,
            "Household net financial saving: NAS 5.3 vs RBI T52(a)",
            [s("NAS 5.3", NAS, f"{NAS}_s5_3", "s5_3.net_financial_saving_of_household_sector_1_4.current", per)],
            [s("RBI T52(a)", RFA, H52, "t52a.nfa.current.fy", per)],
            AGREE,
            0.1,
            "",
        ),
        Check(
            f"HH-5-{per}",
            "Households",
            per,
            "Household saving: NAS 5.3 vs NAS 1.14 (households incl. NPISH)",
            [s("NAS 5.3", NAS, f"{NAS}_s5_3", "s5_3.household_saving_1_2_3_4.current", per)],
            [s("NAS 1.14", NAS, f"{NAS}_s1_14", "s1_14.households_npish.gross_savings.current", per)],
            AGREE,
            0.001,
            "",
        ),
        Check(
            f"HH-6-{per}",
            "Households",
            per,
            "Household gross saving: NAS 5.3 vs RBI HBS T11 (base 2022-23)",
            [s("NAS 5.3", NAS, f"{NAS}_s5_3", "s5_3.household_saving_1_2_3_4.current", per)],
            [s("HBS T11", RFA, "rbi_financial_accounts_hbs_saving", "t11.gross_saving_hh.base2022.current", per)],
            EXPLAINED,
            1.5,
            "Vintage: HBS T11 (Jul 2026) carries the Feb 2026 first release; NAS 2026 (Aug 2026) and RBI T52 (Sep 2026) revised physical and financial saving.",
        ),
    )
add(
    Check(
        "HH-7-2023-24",
        "Households",
        P,
        "Household HCES aggregate with imputation (free/PDS items) vs NAS PFCE (ratio)",
        [hces_aggregate(P, imputed=True)],
        [nas11("pfce", P, "NAS PFCE")],
        EXPLAINED,
        0.0,
        "As HH-1; imputing free items adds ~2 points.",
        ratio_range=(0.40, 0.50),
    ),
    Check(
        "HH-8-2023-24",
        "Households",
        P,
        "Household financial assets: FSF (Jan 2026) vs RBI HBS T12 (Jul 2026), both pre-revision",
        [
            s(
                "FSF hh assets",
                RFA,
                "rbi_financial_accounts_fsf_instrument_sector",
                "fsf7.hh.assets.transaction.total.current",
                P,
            )
        ],
        [s("HBS T12", RFA, "rbi_financial_accounts_hbs_saving", "t12.assets.financial_assets.current", P)],
        EXPLAINED,
        1.0,
        "Same pre-revision RBI estimate family; small instrument-coverage differences.",
    ),
    Check(
        "HH-9-2023-24",
        "Households",
        P,
        "Household net financial saving: FSF household row vs NAS 5.3",
        [s("NAS 5.3 NFS", NAS, f"{NAS}_s5_3", "s5_3.net_financial_saving_of_household_sector_1_4.current", P)],
        [fsf_nft("hh", P)],
        EXPLAINED,
        1.5,
        "Vintage: FSF 2023-24 (Jan 2026) predates RBI's Sep 2026 revision of household financial saving. Bridge = RBI's own revision (T52(a) Sep 2026 less HBS T12 Jul 2026, assets less liabilities).",
        bridge=[
            s("revision in assets: T52(a) FA", RFA, H52, "t52a.fa.current.fy", P),
            s(
                "less HBS T12 FA",
                RFA,
                "rbi_financial_accounts_hbs_saving",
                "t12.assets.financial_assets.current",
                P,
                -1,
            ),
            s("less revision in liabilities: T52(a) FL", RFA, H52, "t52a.fl.current.fy", P, -1),
            s(
                "plus HBS T12 FL",
                RFA,
                "rbi_financial_accounts_hbs_saving",
                "t12.liabilities.financial_liabilities.current",
                P,
            ),
        ],
    ),
)

# ---- Financial: FSF sector totals vs NAS saving/investment; RBI surplus ----------------------------


def nas_si(inst: str, per: str, coef: float = 1.0) -> list[Term]:
    return [
        s(f"NAS 1.14 {inst} gross saving", NAS, f"{NAS}_s1_14", f"s1_14.{inst}.gross_savings.current", per, coef),
        s(f"NAS 1.14 {inst} GCF", NAS, f"{NAS}_s1_14", f"s1_14.{inst}.gross_capital_formation.current", per, -coef),
    ]


def oldb9(stmt: str, label: str, coef: float = 1.0) -> Term:
    return s(label, NAS, f"{NAS}_oldbase_soa_{stmt}", f"oldbase_soa_{stmt}.capital.assets.b9.current", "2022-23", coef)


for per in ("2022-23", "2023-24"):
    add(
        Check(
            f"FIN-1-hh-{per}",
            "Financial",
            per,
            "Households: NAS 1.14 (saving - GCF) vs FSF net financial transactions",
            nas_si("households_npish", per),
            [fsf_nft("hh", per)],
            UNEXPLAINED,
            5.0,
            "NAS household S-I exceeds FSF net lending by 1.6 lakh crore (2022-23) and 3.0 lakh crore (2023-24); the 2023-24 gap is 1.2 lakh crore larger than NAS 5.3 vs FSF (HH-9). Candidates, not verified: household capital transfers (not published in the new base), the S-I errors & omissions that NAS leaves unsectored, and FSF vintage. Phase 2 K9 residual.",
        ),
        Check(
            f"FIN-1-gg-{per}",
            "Financial",
            per,
            "General government: NAS 1.14 (saving - GCF) vs FSF",
            nas_si("gg", per),
            [fsf_nft("gg", per)],
            AGREE if per == "2022-23" else UNEXPLAINED,
            1.0 if per == "2022-23" else 5.0,
            "2022-23 agrees within 0.1% even without capital transfers (the new-base NAS publishes no GG D9). "
            "2023-24 NAS net borrowing is 1.2 lakh crore (7%) smaller than FSF; not bridged."
            if per == "2023-24"
            else "Agrees within 0.1%; see the 2023-24 row for the gap.",
        ),
        Check(
            f"FIN-1-nfc-{per}",
            "Financial",
            per,
            "Non-financial corporations (public + private): NAS 1.14 (saving - GCF) vs FSF",
            nas_si("nfc_public", per) + nas_si("nfc_private", per),
            [fsf_nft("nfc_pub", per), fsf_nft("nfc_pvt", per)],
            UNEXPLAINED,
            5.0,
            "Largest sector gap: new-base NAS NFC net borrowing exceeds FSF by 1.9 lakh crore (2022-23) and 5.7 lakh crore (2023-24); the old base (FIN-2-nfc) went the other way. Not bridged; Phase 2 K9.",
        ),
        Check(
            f"FIN-1-fc-{per}",
            "Financial",
            per,
            "Financial corporations (incl. RBI): NAS 1.14 (saving - GCF) vs FSF (ODC + OFC + RBI)",
            nas_si("fc_public", per) + nas_si("fc_private", per),
            [fsf_nft("fc_odc", per), fsf_nft("fc_ofc", per), fsf_nft("fc_rbi", per)],
            UNEXPLAINED,
            5.0,
            "NAS FC net lending is below FSF in 2022-23 (-0.5 lakh crore) and above it in 2023-24 (+2.3 lakh crore); the sign flip rules out a single timing item such as the RBI surplus (K9b). Not bridged.",
        ),
    )
add(
    Check(
        "FIN-2-hh-2022-23",
        "Financial",
        "2022-23",
        "Households: NAS old base (SOA 5.0 B9) vs FSF",
        [oldb9("s5_0", "old-base household B9")],
        [fsf_nft("hh", "2022-23")],
        EXPLAINED,
        2.0,
        "Old-base NAS took household financial flows from RBI; vintage differences only.",
    ),
    Check(
        "FIN-2-gg-2022-23",
        "Financial",
        "2022-23",
        "General government: NAS old base (SOA 4.0 B9) vs FSF",
        [oldb9("s4_0", "old-base GG B9")],
        [fsf_nft("gg", "2022-23")],
        UNEXPLAINED,
        5.0,
        "NAS GG net borrowing (budget-based) is 3.0 lakh crore larger than FSF's financial-account measure.",
    ),
    Check(
        "FIN-2-nfc-2022-23",
        "Financial",
        "2022-23",
        "NFCs: NAS old base (SOA 2.0 B9) vs FSF (public + private)",
        [oldb9("s2_0", "old-base NFC B9")],
        [fsf_nft("nfc_pub", "2022-23"), fsf_nft("nfc_pvt", "2022-23")],
        UNEXPLAINED,
        5.0,
        "FSF shows 3.0 lakh crore more NFC net borrowing than old-base NAS.",
    ),
    Check(
        "FIN-2-fc-2022-23",
        "Financial",
        "2022-23",
        "FCs: NAS old base (SOA 3.0 B9) vs FSF (ODC + OFC + RBI)",
        [oldb9("s3_0", "old-base FC B9")],
        [fsf_nft("fc_odc", "2022-23"), fsf_nft("fc_ofc", "2022-23"), fsf_nft("fc_rbi", "2022-23")],
        UNEXPLAINED,
        5.0,
        "11% gap; not bridged.",
    ),
    Check(
        "FIN-2-row-2022-23",
        "Financial",
        "2022-23",
        "RoW: NAS old base (SOA 6.0 B9) vs FSF",
        [oldb9("s6_0", "old-base RoW B9")],
        [fsf_nft("row", "2022-23")],
        EXPLAINED,
        2.0,
        "Both from the BoP; old-base NAS used the older BoP vintage and the current account (FSF uses the financial account).",
    ),
    Check(
        "FIN-3-2023-24",
        "Financial",
        P,
        "FSF closure: all-sector transactions in assets vs in liabilities",
        [
            s(
                "FSF all assets",
                RFA,
                "rbi_financial_accounts_fsf_instrument_sector",
                "fsf7.all.assets.transaction.total.current",
                P,
            )
        ],
        [
            s(
                "FSF all liabilities",
                RFA,
                "rbi_financial_accounts_fsf_instrument_sector",
                "fsf7.all.liabilities.transaction.total.current",
                P,
            )
        ],
        EXPLAINED,
        0.5,
        "FSF does not close by 49,902 crore (0.36%): instrument-level asset/liability gaps (e.g. monetary gold, unallocated 'other n.e.c.') net to this; RBI publishes it as is.",
    ),
    Check(
        "FIN-4-2023-24",
        "Financial",
        P,
        "RBI surplus timing: FSF RBI other-payable (F89) to the Centre, 2023-24 flow vs change in RBI surplus payable (AR)",
        [
            s(
                "FSF RBI F89 liabilities to gg_cen, transaction",
                RFA,
                "rbi_financial_accounts_fsf_balance_sheets",
                "fsf.fc_rbi.liabilities.transaction.f89.gg_cen.current",
                P,
            )
        ],
        [
            s(
                "K9b change in surplus payable",
                RBC,
                "rbi_banking_corporate_rbi_surplus_timing",
                "k9b.change_in_surplus_payable.current",
                P,
            )
        ],
        EXPLAINED,
        2.0,
        "FSF accrues the surplus (DECISIONS D0-7/K9b); the 1,810 crore gap is the change in RBI's other (non-surplus) payables to the Centre, which FSF includes in F89.",
    ),
    Check(
        "FIN-5-2024-03-31",
        "Financial",
        "2024-03-31",
        "RBI payable to the Centre, end-March 2024: FSF F89 stock vs RBI AR 'surplus payable'",
        [
            s(
                "FSF RBI F89 to gg_cen, outstanding",
                RFA,
                "rbi_financial_accounts_fsf_balance_sheets",
                "fsf.fc_rbi.liabilities.outstanding.f89.gg_cen.current",
                "2024-03-31",
            )
        ],
        [
            s(
                "RBI AR Schedule 4 surplus payable",
                RBC,
                "rbi_banking_corporate_rbi_accounts",
                "sch4.x.surplus_payable_to_the_central_government.current",
                "2024-03-31",
            )
        ],
        UNEXPLAINED,
        1.0,
        "FSF shows 11,498 crore (5.5%) more RBI payables to the Centre than the surplus line (13,309 at end-March 2023). Other payables to GoI not identified in the AR schedules ingested.",
    ),
)
for inst, t11 in (
    ("nfc_public", "gross_saving_nfc_pub"),
    ("nfc_private", "gross_saving_nfc_pvt"),
    ("fc_public", "gross_saving_fc_pub"),
    ("fc_private", "gross_saving_fc_pvt"),
):
    add(
        Check(
            f"FIN-6-{inst}-2023-24",
            "Financial",
            P,
            f"Gross saving of {inst}: NAS 1.14 vs RBI HBS T11 (base 2022-23)",
            [s("NAS 1.14", NAS, f"{NAS}_s1_14", f"s1_14.{inst}.gross_savings.current", P)],
            [s("HBS T11", RFA, "rbi_financial_accounts_hbs_saving", f"t11.{t11}.base2022.current", P)],
            EXPLAINED,
            1.0,
            "Vintage (as GOV-13).",
        )
    )
add(
    Check(
        "FIN-6-total-2023-24",
        "Financial",
        P,
        "Gross saving, total economy: NAS 1.1 vs RBI HBS T11 (base 2022-23)",
        [nas11("gross_saving", P, "NAS 1.1")],
        [s("HBS T11", RFA, "rbi_financial_accounts_hbs_saving", "t11.gross_saving.base2022.current", P)],
        EXPLAINED,
        1.0,
        "Vintage (as GOV-13); 0.85%, mostly household physical saving.",
    )
)

# ---- Added at the Phase 1 close-out (2026-09-29) for data ingested after the first reconciliation ----
# NAS 2026 through the eSankhyiki API (mospi_nas_2026_api_b2022_annual) vs the published statements.
for per in ("2022-23", "2023-24"):
    for n, (item, label) in enumerate((("gdp", "GDP"), ("pfce", "PFCE"), ("gfce", "GFCE")), start=7):
        add(
            Check(
                f"GDP-{n}-{per}",
                "GDP",
                per,
                f"{label}: NAS 2026 via the eSankhyiki API (base 2022-23) vs NAS 2026 Statement 1.1",
                [
                    s(
                        f"API {label}",
                        NAS,
                        f"{NAS}_api_b2022_annual",
                        f"api.{item}.rev_final_estimates.current",
                        per,
                    )
                ],
                [nas11(item, per, f"NAS 1.1 {label}")],
                AGREE,
                0.001,
                "",
            )
        )

# Union grants: Expenditure Budget Statement 6 (GCCA) and Finance Accounts Appendix to Statement 9 (IGAS-2).
GIA = "union_fiscal_fa_gia"
add(
    Check(
        "GOV-14-2023-24",
        "Government",
        P,
        "Grants for creation of capital assets: Expenditure Budget St 6 Actuals (Budget 2025-26) vs Finance Accounts App. to St 9 (IGAS-2) capital column, all grantees",
        [
            ssum(
                "FA IGAS-2 capital assets, cash + in kind, 10 grantee categories",
                UF,
                GIA,
                r"^gia\.(cash|in_kind)\.[a-z_]+\.capital_assets$",
                P,
                min_rows=20,
            )
        ],
        [s("St 6 Grand Total (Actuals)", UF, "union_fiscal_gcca", "stat6.grand_total", P)],
        AGREE,
        0.001,
        "",
    ),
    Check(
        "GOV-15-2023-24",
        "Government",
        P,
        "Grants to State Governments: Finance Accounts IGAS-2 grantee 'State Government' (cash + in kind) vs Finance Accounts St 9 MH 3601",
        [ssum("FA IGAS-2 State Government", UF, GIA, r"^gia\.(cash|in_kind)\.state_governments\.total$", P, min_rows=2)],
        [s("FA St 9 MH 3601 total", UF, "union_fiscal_fa_expenditure", "fa9.3601.total", P)],
        UNEXPLAINED,
        1.0,
        "The same audited Finance Accounts give 1.41 lakh crore (26%) less to 'State Government' by grantee than under MH 3601. MH 3601 releases to State implementing agencies, societies or local bodies are probably classed under other grantees (autonomous bodies, others), but the appendix does not say so (union_fiscal-23). Bears on H9 and on the capital share of R2 (R2k).",
    ),
    Check(
        "GOV-16-2023-24",
        "Government",
        P,
        "Grants to States and UTs with legislature: Finance Accounts IGAS-2 (State + UT Governments, cash + in kind) vs RBI SF grants received from the Centre",
        [
            ssum("FA IGAS-2 State Government", UF, GIA, r"^gia\.(cash|in_kind)\.state_governments\.total$", P, min_rows=2),
            ssum("FA IGAS-2 UT Governments", UF, GIA, r"^gia\.(cash|in_kind)\.ut_governments\.total$", P, min_rows=2),
        ],
        [sfa("app1.total_revenue.ii.d-grants_from_the_centre", "RBI SF grants from the Centre")],
        UNEXPLAINED,
        2.0,
        "IGAS-2's grantee view is 71,500 crore (13.6%) below what States and the three UTs record, while the Union MH 3601 view is 67,000 crore above it (GOV-9). The State-side receipt lies between the Union's two measures; neither Union measure is bridged to it with ingested data (H9).",
    ),
)

# Union GPF (MH 8009): Finance Accounts Statement 14 vs Annual Financial Statement public account.
for n, (col, afs_side, label) in enumerate(
    (("additions", "pa_receipts", "gross additions"), ("discharges", "pa_disbursements", "discharges")), start=17
):
    add(
        Check(
            f"GOV-{n}-2023-24",
            "Government",
            P,
            f"Union State Provident Funds (GPF, MH 8009) {label}: Finance Accounts St 14 vs AFS public account",
            [s(f"FA St 14 MH 8009 {label}", UF, "union_fiscal_fa_provident_funds", f"fa14.8009.total.{col}", P)],
            [s(f"AFS {afs_side} (i) State Provident Fund", UF, "union_fiscal_afs", f"afs.{afs_side}.i_state_provident_fund", P)],
            AGREE,
            0.001,
            "",
        )
    )

_ids = [c.id for c in CHECKS]
assert len(_ids) == len(set(_ids)), "duplicate check ids"


# --------------------------------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------------------------------


def _fmt(x: float) -> str:
    return f"{x:,.0f}"


def _status(c: Check, r: dict) -> str:
    if c.verdict == UNEXPLAINED:
        return "**UNEXPLAINED**" + ("" if not r["ok"] else " (now within tol.)")
    kind = "bridged" if c.bridge else ("ratio" if c.ratio_range else "")
    base = c.verdict + (f" ({kind})" if kind and c.verdict == EXPLAINED else "")
    return base if r["ok"] else f"{base} - FAILS"


def markdown(area: str | None = None, detail: bool = False) -> str:
    rows = [
        "| id | check | A (Rs cr) | B (Rs cr) | A-B | % of B | bridge | residual | tol | verdict |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    out = []
    for c in CHECKS:
        if area and c.area != area:
            continue
        try:
            r = c.evaluate()
        except MissingData as e:
            rows.append(f"| {c.id} | {c.title} | | | | | | | | MISSING DATA: {e} |")
            continue
        tol = f"{c.ratio_range[0]:.2f}-{c.ratio_range[1]:.2f} ratio" if c.ratio_range else f"{c.tol_pct:g}%"
        pct = f"ratio {r['ratio']:.3f}" if c.ratio_range else f"{r['pct']:+.2f}%"
        rows.append(
            f"| {c.id} | {c.title} | {_fmt(r['a'])} | {_fmt(r['b'])} | {_fmt(r['diff'])} | {pct} | "
            f"{_fmt(r['bridge']) if c.bridge else ''} | {_fmt(r['resid']) if c.bridge else ''} | {tol} | {_status(c, r)} |"
        )
        if detail:
            out.append(
                f"- **{c.id}** A = "
                + " + ".join(f"{t.coef:+g} x {t.label} [{t.src}]" for t in c.a)
                + "; B = "
                + " + ".join(f"{t.coef:+g} x {t.label} [{t.src}]" for t in c.b)
                + (
                    "; bridge = " + " + ".join(f"{t.coef:+g} x {t.label} [{t.src}]" for t in c.bridge)
                    if c.bridge
                    else ""
                )
                + (f". {c.note}" if c.note else "")
            )
    return "\n".join(rows) + ("\n\n" + "\n".join(out) if detail else "")


if __name__ == "__main__":
    detail = "--detail" in sys.argv
    areas = [a for a in sys.argv[1:] if not a.startswith("--")] or sorted(
        {c.area for c in CHECKS}, key=[c.area for c in CHECKS].index
    )
    for a in areas:
        print(f"\n### {a}\n")
        print(markdown(a, detail))
