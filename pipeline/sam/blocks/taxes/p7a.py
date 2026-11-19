"""P7a (product taxes by type within commodity) and the P7b valuation satellite.

Method (plan docs/phase2/plans/taxes.md s.2.1-2.2, DECISIONS D2-4, D2-12):
1. Row targets = Union + State cash receipts by tax account (receipts.py), scaled by one factor s so that
   they add up to the SUT product-tax total (the SUT margin wins; the TAX-1 gap is spread pro rata).
2. Column targets = production's P7 constraint targets (SUT product taxes by commodity, the same floats).
3. Prior at SUT-product level (155 products): commodity-specific heads first (petroleum from PPAC, State
   excise on alcohol, electricity duty, vehicle tax, ...), then GST and compensation cess on each product's
   remaining SUT tax ("GST residual"); aggregated to the 34 commodities with the committed concordance.
4. Feasibility pre-check (a transportation LP on the prior's zero pattern): if the scaled row targets
   cannot all be met, the LP moves them as little as possible (sum of relative deviations); the moves
   are published in the p7a_precheck satellite and logged.
5. RAS of the prior to the column targets (exact) and the (pre-checked) row targets.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl
from scipy.optimize import linprog

from pipeline.sam.framework import BlockContext, SamError

from .common import GST_ACCOUNTS, PPAC, PRODUCT_MAP, PRODUCT_TAX_ACCOUNTS, SUPPLY, USE, pids
from .receipts import Cash

SUT_VINTAGE = "latest"  # the SUT 2023-24 has one vintage (31 Aug 2026) today; an explicit choice
PPAC_VINTAGE = "latest"  # PPAC 2023-24 (2026-07-17)

# --- stated assumption parameters (each also in the provenance method text) ----------------------------
P_CRUDE, P_GAS, P_POL, P_ALCO, P_ELEC = "sut_p044", "sut_p043", "sut_p085", "sut_p065", "sut_p128"
P_TOBACCO, P_LAND_TRANSPORT, P_RECREATION, P_FIN = "sut_p069", "sut_p136", "sut_p155", "sut_p142"
P_HOTEL, P_TRADE, P_COAL = "sut_p134", "sut_p132", "sut_p042"
VEHICLES = ("sut_p120", "sut_p121", "sut_p122")  # motor vehicles, motor cycles/scooters, bicycles
DIGITAL = ("sut_p149", "sut_p141")  # other business services, communication (equalisation levy base)
CESS_BASE = ("sut_p064", "sut_p066", "sut_p069", "sut_p120")  # pan masala (misc food), aerated waters, tobacco, cars
CESS_FACTOR = 0.5  # legal-base products carry compensation cess = 0.5 x their GST residual (prior shape only)
NON_GST = (P_GAS, P_CRUDE, P_ALCO, P_POL, P_ELEC)  # outside GST (petroleum crude/gas/fuels, alcohol, power)
VAT_RESIDUAL = (P_ALCO, P_GAS, P_POL)  # non-petroleum VAT (liquor, natural gas, ATF/other POL)
LICENCE = (P_HOTEL, P_TRADE)  # State excise in excess of the SUT alcohol tax (licence fees)
NON_POL_VAT = "non_pol_vat"  # component of the State VAT other than PPAC's VAT on POL (a residual; low confidence)
GOODS_MAX = 126  # SUT products 1..126 are goods (export duty base: those of them that carry SUT product tax)
MIN_CELL = 1e-3  # Rs crore: prior cells below this are dropped (logged)
RAS_TOL = 1e-10  # relative
RAS_MAXIT = 200_000


@dataclass
class Load:
    account: str
    component: str
    item: str  # what the load is (for P7b and the method text)
    product: str
    value: float


@dataclass
class SutProducts:
    tax: dict[str, float]  # SUT product taxes by product
    commodity: dict[str, str]  # product -> SAM commodity
    pfce: dict[str, float]
    gfcf: dict[str, float]
    exports: dict[str, float]
    imports: dict[str, float]
    output: dict[str, float]
    prov_ids: list[str]


def read_sut(ctx: BlockContext) -> SutProducts:
    conc = ctx.concordance(PRODUCT_MAP)
    com = {"sut_p" + r["sut_product"].zfill(3): r["commodity"] for r in conc.iter_rows(named=True)}
    sup = ctx.rows(SUPPLY, vintage=SUT_VINTAGE, item_code=["product_taxes", "imports", "output"])
    use = ctx.rows(USE, vintage=SUT_VINTAGE, item_code=["pfce", "gfcf", "exports"])

    def vec(df: pl.DataFrame, item: str) -> dict[str, float]:
        d = df.filter((pl.col("item_code") == item) & pl.col("product").str.starts_with("sut_p"))
        out = (
            d.group_by("product", maintain_order=True).agg(pl.col("value").sum()).sort("product")
        )  # output is by product x industry
        return dict(zip(out["product"].to_list(), out["value"].to_list(), strict=True))

    tax = vec(sup, "product_taxes")
    missing = sorted(set(tax) - set(com))
    if missing:
        raise SamError(f"SUT products with product taxes missing from the concordance: {missing}")
    neg = {p: v for p, v in tax.items() if v < 0}
    if neg:
        raise SamError(f"negative SUT product taxes (the P7a split assumes none): {neg}")
    used = sup.filter(pl.col("item_code") == "product_taxes")["prov_id"].to_list() + use["prov_id"].to_list()
    return SutProducts(
        tax={p: v for p, v in tax.items() if v != 0},
        commodity=com,
        pfce=vec(use, "pfce"),
        gfcf=vec(use, "gfcf"),
        exports=vec(use, "exports"),
        imports=vec(sup, "imports"),
        output=vec(sup, "output"),
        prov_ids=pids(used, sup["prov_id"].to_list()),
    )


def read_ppac(ctx: BlockContext) -> tuple[dict[str, float], list[str]]:
    keys = {
        "excise": "ppac.centre.a.excise_duty",
        "crude_cess": "ppac.centre.a.cess_on_crude_oil",
        "crude_nccd": "ppac.centre.a.nccd_on_crude_oil",
        "cgst": "ppac.centre.a.cgst",
        "igst": "ppac.centre.a.igst",
        "sgst": "ppac.states.a.sgst_utgst",
        "vat": "ppac.states.a.sales_tax_vat_on_pol_products",
        "entry_tax": "ppac.states.a.entry_tax_others",
        "octroi": "ppac.states.a.octroi_duties_incl_electricity_duty",
    }
    out, ps = {}, []
    for k, s in keys.items():
        out[k], p = ctx.value(PPAC, s, vintage=PPAC_VINTAGE)
        ps.append(p)
    return out, sorted(set(ps))


# ---------------------------------------------------------------------------------------------------
# the prior (pure: plain dicts in, loads out; unit-tested on small fixtures)
# ---------------------------------------------------------------------------------------------------


def _pro_rata(total: float, weights: dict[str, float]) -> dict[str, float]:
    w = {k: v for k, v in sorted(weights.items()) if v > 0}
    s = sum(w.values())
    if total == 0:
        return {}
    if s <= 0:
        raise SamError(f"no positive weight to place {total:,.2f} on (keys {sorted(weights)})")
    return {k: total * v / s for k, v in w.items()}


def build_prior(sut: SutProducts, rows: dict[str, float], oprt: dict[str, float], ppac: dict[str, float]) -> list[Load]:
    """Product-level prior loads. `rows`: cash row targets by account (unscaled; T_SEXC, T_SVAT and T_OPRT
    include the UT heads). `oprt`: T_OPRT cash by item (keys of receipts.CENTRE/STATE). `ppac`: read_ppac."""
    tax = sut.tax
    loads: list[Load] = []
    placed: dict[str, float] = {p: 0.0 for p in tax}

    def put(acct: str, item: str, amounts: dict[str, float], component: str = "total") -> None:
        for p, v in amounts.items():
            if p not in tax:
                raise SamError(f"P7a prior: {item} placed on {p}, which has no SUT product tax")
            if v > 0:
                loads.append(Load(acct, component, item, p, v))
                placed[p] += v

    def room(p: str) -> float:
        return max(0.0, tax.get(p, 0.0) - placed.get(p, 0.0))

    # 1. petroleum (PPAC), royalties and customs excluded (royalty is D45 rent; customs is P8)
    put("T_UEXC", "ppac_excise_pol", {P_POL: ppac["excise"]})
    # the SUT's C_OILG product tax equals PPAC cess + NCCD on crude to the rupee (20,771.31): the SUT books the
    # crude cess on crude oil and natural gas (pro rata to their SUT tax), and no VAT there
    put(
        "T_UEXC",
        "crude_cess_nccd",
        _pro_rata(ppac["crude_cess"] + ppac["crude_nccd"], {p: tax.get(p, 0.0) for p in (P_CRUDE, P_GAS)}),
    )
    put("T_SVAT", "ppac_vat_pol", {P_POL: ppac["vat"]})
    put("T_OPRT", "ppac_entry_octroi_pol", {P_POL: ppac["entry_tax"] + ppac["octroi"]})
    r_c, r_s = rows["T_CGST"], rows["T_SGST"]
    put("T_CGST", "ppac_gst_pol", {P_POL: ppac["cgst"] + ppac["igst"] * r_c / (r_c + r_s)})
    put("T_SGST", "ppac_gst_pol", {P_POL: ppac["sgst"] + ppac["igst"] * r_s / (r_c + r_s)})
    # 2. Union excise other than petroleum: NCCD / BED on tobacco products
    rest = rows["T_UEXC"] - ppac["excise"] - ppac["crude_cess"] - ppac["crude_nccd"]
    if rest < 0:
        raise SamError(f"PPAC petroleum excise exceeds total Union excise by {-rest:,.2f}")
    put("T_UEXC", "non_pol_excise_tobacco", {P_TOBACCO: rest})
    # 3. State excise on alcoholic beverages, up to the SUT alcohol tax; the excess = licence fees on hotels
    #    and trade (gap-map P7a fallback), pro rata to their SUT product tax
    sexc = rows["T_SEXC"]
    on_alco = min(sexc, room(P_ALCO))
    put("T_SEXC", "state_excise_alcohol", {P_ALCO: on_alco})
    put("T_SEXC", "licence_fee_excess", _pro_rata(sexc - on_alco, {p: tax.get(p, 0.0) for p in LICENCE}),
        component="licence_fee_excess")  # fmt: skip
    # 4. T_OPRT heads with an identified base
    put(
        "T_OPRT", "electricity_duty", {P_ELEC: oprt.get("electricity_duty", 0.0) + oprt.get("ut_electricity_duty", 0.0)}
    )
    put(
        "T_OPRT",
        "vehicle_tax",
        _pro_rata(
            oprt.get("vehicle_tax", 0.0) + oprt.get("ut_vehicle_tax", 0.0),
            {p: sut.pfce.get(p, 0.0) + sut.gfcf.get(p, 0.0) for p in VEHICLES},
        ),
    )
    put(
        "T_OPRT",
        "goods_passengers",
        {P_LAND_TRANSPORT: oprt.get("goods_passengers", 0.0) + oprt.get("ut_goods_passengers", 0.0)},
    )
    put("T_OPRT", "entertainment_tax", {P_RECREATION: oprt.get("entertainment_tax", 0.0)})
    put(
        "T_OPRT",
        "equalisation_levy",
        _pro_rata(oprt.get("equalisation_levy", 0.0), {p: sut.imports.get(p, 0.0) for p in DIGITAL}),
    )
    goods = {p: sut.exports.get(p, 0.0) for p in tax if int(p[5:]) <= GOODS_MAX}
    put("T_OPRT", "export_duty", _pro_rata(oprt.get("export_duty", 0.0), goods))
    put("T_OPRT", "ctt", {P_FIN: oprt.get("ctt", 0.0)})  # fmt: skip
    # 5. non-petroleum State VAT (liquor, natural gas, ATF/other POL): pro rata to the room left. Its own
    #    component (low confidence), apart from PPAC's VAT on POL (high): with no room on p065/p043 it lands on
    #    p085 by plan fallback (b), so balancing may move it more cheaply (verification V-TX-3)
    vat_rest = rows["T_SVAT"] - ppac["vat"]
    if vat_rest < 0:
        raise SamError(f"PPAC VAT on POL exceeds State + UT sales tax by {-vat_rest:,.2f}")
    put("T_SVAT", "non_pol_vat", _pro_rata(vat_rest, {p: room(p) for p in VAT_RESIDUAL}), component=NON_POL_VAT)
    # 6. GST residual of GST products: other T_OPRT heads, then compensation cess, then CGST : SGST
    gst_res = {p: room(p) for p in tax if p not in NON_GST}
    other = (
        oprt.get("service_tax_arrears", 0.0)
        + oprt.get("other_taxes_duties", 0.0)
        - (ppac["entry_tax"] + ppac["octroi"])
    )
    put("T_OPRT", "other_commodity_taxes", _pro_rata(max(0.0, other), gst_res))
    gst_res = {p: room(p) for p in tax if p not in NON_GST}
    base = {p: CESS_FACTOR * gst_res.get(p, 0.0) for p in CESS_BASE}
    cess = rows["T_GCES"]
    if sum(base.values()) >= cess:
        put("T_GCES", "cess_legal_base", _pro_rata(cess, base))
    else:
        put("T_GCES", "cess_legal_base", base)
        spread = {p: v for p, v in gst_res.items() if p not in CESS_BASE and p != P_COAL}
        put("T_GCES", "cess_spread", _pro_rata(cess - sum(base.values()), spread))
    for p in sorted(gst_res):
        g = room(p)
        if g > 0:
            put("T_CGST", "gst", {p: g * r_c / (r_c + r_s)})
            put("T_SGST", "gst", {p: g * r_s / (r_c + r_s)})
    return loads


def cells_from_loads(loads: list[Load], commodity: dict[str, str]) -> pl.DataFrame:
    """Aggregate loads to (account, component, item, commodity)."""
    df = pl.DataFrame(
        [(ld.account, ld.component, ld.item, commodity[ld.product], ld.value) for ld in loads],
        schema={"account": pl.String, "component": pl.String, "item": pl.String, "commodity": pl.String,
                "value": pl.Float64},
        orient="row",
    )  # fmt: skip
    return df.group_by(["account", "component", "item", "commodity"], maintain_order=True).agg(pl.col("value").sum())


# ---------------------------------------------------------------------------------------------------
# pre-check (transportation LP) and RAS
# ---------------------------------------------------------------------------------------------------


@dataclass
class Fit:
    cells: pl.DataFrame  # account, component, commodity, prior, value
    row_target: dict[str, float]  # scaled cash targets
    row_final: dict[str, float]  # after the pre-check
    iterations: int
    max_rel_err: float


def precheck(cells: pl.DataFrame, rows: dict[str, float], cols: dict[str, float]) -> dict[str, float]:
    """Row targets that the prior's zero pattern can meet with the column targets, moving `rows` as little as
    possible (min sum |r' - r| / r). Returns r' (== rows when feasible)."""
    keys = cells.select("account", "commodity").rows()
    racc = sorted(rows)
    ccom = sorted(cols)
    n, m, k = len(keys), len(racc), len(ccom)
    # variables: x (n), d_plus (m), d_minus (m)
    c = np.concatenate([np.zeros(n), [1 / rows[a] for a in racc], [1 / rows[a] for a in racc]])
    a_eq, b_eq = [], []
    for i, a in enumerate(racc):
        row = np.zeros(n + 2 * m)
        row[[j for j, (acc, _) in enumerate(keys) if acc == a]] = 1.0
        row[n + i], row[n + m + i] = -1.0, 1.0
        a_eq.append(row)
        b_eq.append(rows[a])
    for com in ccom:
        row = np.zeros(n + 2 * m)
        row[[j for j, (_, cc) in enumerate(keys) if cc == com]] = 1.0
        a_eq.append(row)
        b_eq.append(cols[com])
    res = linprog(c, A_eq=np.array(a_eq), b_eq=np.array(b_eq), bounds=[(0, None)] * (n + 2 * m), method="highs")
    if res.status != 0:
        raise SamError(f"P7a pre-check LP failed: {res.message} ({k} columns, {m} rows, {n} cells)")
    dp, dm = res.x[n : n + m], res.x[n + m :]
    out = {}
    for i, a in enumerate(racc):
        d = dp[i] - dm[i]
        out[a] = rows[a] + (d if abs(d) > 1e-6 * rows[a] else 0.0)
    return out


def ras(cells: pl.DataFrame, rows: dict[str, float], cols: dict[str, float]) -> tuple[np.ndarray, int, float]:
    x = cells["value"].to_numpy().astype(float).copy()
    acc = cells["account"].to_list()
    com = cells["commodity"].to_list()
    ra = sorted(rows)
    cc = sorted(cols)
    ri = np.array([ra.index(a) for a in acc])
    ci = np.array([cc.index(c) for c in com])
    rt = np.array([rows[a] for a in ra])
    ct = np.array([cols[c] for c in cc])
    err = np.inf
    for it in range(1, RAS_MAXIT + 1):
        rs = np.bincount(ri, weights=x, minlength=len(ra))
        x *= (rt / rs)[ri]
        cs = np.bincount(ci, weights=x, minlength=len(cc))
        x *= (ct / cs)[ci]
        rs = np.bincount(ri, weights=x, minlength=len(ra))
        err = float(np.max(np.abs(rs - rt) / rt))
        if err < RAS_TOL:
            return x, it, err
    raise SamError(f"P7a RAS did not converge in {RAS_MAXIT} iterations (max relative row error {err:.3g})")


def fit(cells_items: pl.DataFrame, cash_rows: dict[str, float], cols: dict[str, float], ctx: BlockContext) -> Fit:
    cells = (
        cells_items.group_by(["account", "component", "commodity"], maintain_order=True)
        .agg(pl.col("value").sum())
        .sort("account", "component", "commodity")
    )
    small = cells.filter(pl.col("value") < MIN_CELL)
    if small.height:
        ctx.log(f"P7a: {small.height} prior cell(s) below Rs {MIN_CELL} crore dropped: {small.rows()[:5]}")
        cells = cells.filter(pl.col("value") >= MIN_CELL)
    bad_cols = sorted(set(cells["commodity"].to_list()) - {c for c, v in cols.items() if v > 0})
    if bad_cols:
        raise SamError(f"P7a prior puts tax on commodities with no SUT product tax: {bad_cols}")
    no_prior = sorted(c for c, v in cols.items() if v > 0 and c not in set(cells["commodity"].to_list()))
    if no_prior:
        raise SamError(f"P7a: SUT product tax on {no_prior} but no prior cell")
    cols = {c: v for c, v in cols.items() if v > 0}
    s = sum(cols.values()) / sum(cash_rows.values())
    scaled = {a: v * s for a, v in cash_rows.items()}
    final = precheck(cells, scaled, cols)
    x, it, err = ras(cells, final, cols)
    return Fit(cells.rename({"value": "prior"}).with_columns(pl.Series("value", x)), scaled, final, it, err)


def item_values(cells_items: pl.DataFrame, f: Fit) -> pl.DataFrame:
    """Final value of every prior item: its cell's RAS factor times its prior (for P7b and the satellites)."""
    z = f.cells.with_columns((pl.col("value") / pl.col("prior")).alias("z")).select(
        "account", "component", "commodity", "z"
    )
    return (
        cells_items.join(z, on=["account", "component", "commodity"], how="inner", maintain_order="left")
        .with_columns((pl.col("value") * pl.col("z")).alias("final"))
        .rename({"value": "prior"})
    )


def rows_and_items(cash: Cash) -> tuple[dict[str, float], dict[str, float]]:
    rows = {a: cash.by_account(a) for a in PRODUCT_TAX_ACCOUNTS}
    oprt = {i.key: i.value for i in cash.items if i.account == "T_OPRT"}
    return rows, oprt


def confidence(account: str, component: str, commodity: str) -> str:
    """Balancing confidence of a P7a entry (plan s.2 table)."""
    if component in ("licence_fee_excess", NON_POL_VAT) or account == "T_GCES":
        return "low"
    if (account in ("T_UEXC", "T_SVAT") and commodity in ("C_RPET", "C_OILG")) or (
        account == "T_SEXC" and commodity == "C_BVTB"
    ):
        return "high"
    if account == "T_OPRT":
        return "medium" if commodity in ("C_UTIL", "C_TREQ") else "low"
    return "medium"


# ---------------------------------------------------------------------------------------------------
# P7b: tax by commodity x type x use (satellite)
# ---------------------------------------------------------------------------------------------------

# non-ITC activities for GST (their GST on intermediate inputs is a cost, not a credit): stated list
NON_ITC = {"A_CROP": 1.0, "A_LVST": 1.0, "A_FOFI": 1.0, "A_UTIL": 1.0, "A_RPET": 1.0, "A_DWEL": 1.0,
           "A_EDUC": 1.0, "A_HLTH": 1.0, "A_PADM": 1.0, "A_OSRV": 1.0, "A_FINS": 0.5, "A_INSR": 0.5}  # fmt: skip
GFCF_GST = ("C_CNST", "C_TREQ")  # blocked credit: immovable property; passenger vehicles


def uses_by_commodity(prod_entries: pl.DataFrame, prod_cons: pl.DataFrame) -> pl.DataFrame:
    """Use values at purchasers' prices by commodity: IC by activity (P2), exports (P5), CII (I3) from
    production's entries; PFCE, GFCE, GFCF, valuables from its constraint targets (C1, C2, I1, I2)."""
    e = prod_entries
    parts = [
        e.filter(pl.col("ref") == "P2").select(pl.col("row").alias("commodity"), pl.col("col").alias("use"),
                                               pl.lit("ic").alias("use_type"), "value"),
        e.filter(pl.col("ref") == "P5").select(pl.col("row").alias("commodity"), pl.lit("exports").alias("use"),
                                               pl.lit("exports").alias("use_type"), "value"),
        e.filter(pl.col("ref") == "I3").select(pl.col("row").alias("commodity"), pl.lit("cii").alias("use"),
                                               pl.lit("cii").alias("use_type"), "value"),
    ]  # fmt: skip
    for stem in ("pfce", "gfce", "gfcf", "valuables"):
        c = prod_cons.filter(pl.col("constraint_id").str.starts_with(f"{stem}.") & (pl.col("target") != 0))
        parts.append(
            c.select(
                pl.col("constraint_id").str.split(".").list.get(1).str.to_uppercase().alias("commodity"),
                pl.lit(stem).alias("use"),
                pl.lit(stem).alias("use_type"),
                pl.col("target").alias("value"),
            )
        )
    return pl.concat(parts).filter(pl.col("value") != 0)


def eligible(account: str, item: str, commodity: str, use: str, use_type: str, bvtb_alco: float) -> float:
    """Weight multiplier (0..1) for placing tax `item` of `account` on a use (plan s.2.2 rules)."""
    if item == "export_duty":
        return 1.0 if use_type == "exports" else 0.0
    if use_type == "exports":
        return 0.0
    if use_type == "cii":
        return 0.0 if account in GST_ACCOUNTS else 1.0  # held by registered businesses (credit) / cost otherwise
    if item == "electricity_duty":
        return 1.0 if use_type in ("ic", "pfce") else 0.0
    if item == "vehicle_tax":
        return 1.0 if use_type in ("pfce", "gfcf") else 0.0
    if item == "state_excise_alcohol":
        return 1.0 if use_type == "pfce" or use == "A_HOTL" else 0.0
    if account in GST_ACCOUNTS:
        if use_type == "ic":
            if use == "A_BVTB":
                return bvtb_alco  # alcohol producers are outside GST on output: their input GST is a cost
            return NON_ITC.get(use, 0.0)
        if use_type == "gfcf":
            return 1.0 if commodity in GFCF_GST else 0.0
        return 1.0  # pfce, gfce, valuables
    return 1.0  # excise, VAT, other product taxes: every domestic use pays


def p7b(items: pl.DataFrame, uses: pl.DataFrame, bvtb_alco: float) -> tuple[pl.DataFrame, int]:
    """Distribute each item's final value over its commodity's uses. Returns rows (account, component,
    commodity, use, use_type, value) and the number of items that had no eligible use (spread over all
    domestic uses instead; logged)."""
    by_com = {c: g for (c,), g in uses.group_by(["commodity"], maintain_order=True)}
    out: list[tuple] = []
    fallback = 0
    for r in items.iter_rows(named=True):
        u = by_com.get(r["commodity"])
        if u is None:
            raise SamError(f"P7b: commodity {r['commodity']} carries tax but has no use in production's entries")
        w = [
            (x["use"], x["use_type"], x["value"] * eligible(r["account"], r["item"], r["commodity"], x["use"],
                                                            x["use_type"], bvtb_alco))
            for x in u.iter_rows(named=True)
        ]  # fmt: skip
        w = [t for t in w if t[2] > 0]
        if not w:
            fallback += 1
            w = [(x["use"], x["use_type"], x["value"]) for x in u.iter_rows(named=True)
                 if x["use_type"] != "exports" and x["value"] > 0]  # fmt: skip
        s = sum(t[2] for t in w)
        for use, ut, v in w:
            out.append((r["account"], r["component"], r["commodity"], use, ut, r["final"] * v / s))
    df = pl.DataFrame(
        out,
        schema={"account": pl.String, "component": pl.String, "commodity": pl.String, "use": pl.String,
                "use_type": pl.String, "value": pl.Float64},
        orient="row",
    )  # fmt: skip
    df = df.group_by(["account", "component", "commodity", "use", "use_type"], maintain_order=True).agg(
        pl.col("value").sum()
    )
    return df.sort("account", "component", "commodity", "use"), fallback
