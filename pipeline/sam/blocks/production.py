"""Production block (the template block): the SUT 2023-24 aggregated to 34 activities x 34 commodities.

Reads (all latest vintage, 31 Aug 2026, period 2023-24):
- io_tables_sut_supply / io_tables_sut_use / io_tables_sut_va: MoSPI Supply and Use Tables 2023-24,
  155 products x 67 industries, Rs crore (unit io_tables).
- data/concordance/io_tables_sut_product_to_sam34.csv and io_tables_sut_industry_to_sam34.csv
  (ACCOUNT_STRUCTURE s.2): every SUT product -> one commodity, every SUT industry -> one activity.
- mospi_nas_2026_s1_1 and mospi_nas_2026_s7_1 (NAS 2026 Statements 1.1 and 7.1) and the SUT note
  totals: control totals only (checks), plus the D4 discrepancy.

Writes entries (gap-map refs): ACT<-COM make (P1), COM<-ACT intermediate use (P2), COM<-M_TTM margin
services supplied (P3), M_TTM<-COM margins paid (P4), COM<-R_ROW exports (P5), R_ROW<-COM imports
after the CIF adjustment (P6), T_CUST<-COM import duty (P8), T_PSUB<-COM product subsidies (P9,
negative), T_PROD<-ACT net production taxes (P10), COM<-K_DSTK change in inventories (I3, official
by commodity) and COM<-X_DISC (D4, zero in 2023-24).
Declares constraints (the official totals whose split other blocks estimate): product taxes by
commodity over the 7 product-tax accounts (P7), CE by activity (V1), OS/mixed income + CFC by
activity (V2), PFCE / GFCE / GFCF / valuables by commodity (C1, C2, I1, I2).
Satellite `sut_memo` (P6): the SUT memo rows (CIF adjustment by commodity, purchases of residents
abroad and of non-residents in India) that are not SAM cells.
Not implemented: P6a (optional import-use matrix; needs ICIO work, not cheap) and S6 (energy PSUT by
34 activities needs an ISIC-group concordance): docs/phase2/issues/production.md.

Roles. The published SUT is not exactly additive: supply - use misses by up to Rs 0.50 crore per
product, output - inputs by up to Rs 0.86 crore per industry, and the TTM column sums to +Rs 0.33 crore
(many cells are published with decimals, so this is not a whole-crore rounding bound). An all-`fixed`
production block therefore could not balance to Rs 0.01 crore (e.g. the margin account M_TTM, all of
whose entries are SUT cells). Entries built from SUT cells (P1-P6, I3) are `anchored`, each allowed to
move by Rs 1 crore per SUT cell aggregated into it (tol_rel = n_cells / |value|): an ASSUMED
allowance, chosen to cover the observed non-additivity with a margin; the tax vectors P8, P9, P10 and
D4 are `fixed`. Constraint targets get the same allowance (tol_abs = n_cells crore). See
FRAMEWORK_REQUESTS.md (deviation 1 and the Wave A review).
"""

from __future__ import annotations

import polars as pl

from pipeline.sam.framework import BlockContext, BlockResult, SamError, Satellite, constraint, entry

BLOCK = "production"
REFS = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "V1", "V2", "C1", "C2", "I1", "I3", "D4"]
DEPENDS: list[str] = []

SUPPLY, USE, VA = "io_tables_sut_supply", "io_tables_sut_use", "io_tables_sut_va"
NOTE = "io_tables_sut_note_totals"
NAS11, NAS71 = "mospi_nas_2026_s1_1", "mospi_nas_2026_s7_1"
PRODUCT_MAP, INDUSTRY_MAP = "io_tables_sut_product_to_sam34", "io_tables_sut_industry_to_sam34"
VINTAGE = "latest"  # an explicit choice: the SUT and NAS 2026 carry one vintage each (31 Aug 2026) today
ROUNDING = 1.0  # Rs crore per published SUT cell: an assumed allowance for the SUT's non-additivity (docstring)
CHECK_TOL = 5.0  # Rs crore: SAM aggregate vs published total (RECONCILIATION.md finds <= 3 crore)
PRODUCT_TAX_ACCOUNTS = ["T_CGST", "T_SGST", "T_GCES", "T_UEXC", "T_SVAT", "T_SEXC", "T_OPRT"]  # P7a's split
# NAS broad group (concordance `nas_group`, SUT note Table 5.1) -> NAS 2026 Statement 7.1 industry code
NAS_GROUPS = {
    "1": "agri", "2": "mining", "3": "manufacturing", "4": "utilities", "5": "construction", "6": "trade_hotels",
    "7": "transport_comm", "8": "financial", "9": "real_estate_prof", "10": "public_admin", "11": "other_services",
}  # fmt: skip


def build(ctx: BlockContext) -> BlockResult:
    prod, ind, conc = _concordances(ctx)
    supply = _tag(ctx.rows(SUPPLY, vintage=VINTAGE), prod, ind)
    use = _tag(ctx.rows(USE, vintage=VINTAGE), prod, ind)
    va = _tag(ctx.rows(VA, vintage=VINTAGE), prod, ind)
    vintages = sorted(set(supply["vintage"]) | set(use["vintage"]) | set(va["vintage"]))
    ctx.log(f"SUT {ctx.year}, vintage(s) {vintages}; concordances {conc}")

    entries: list[dict] = []
    cons: list[dict] = []

    # --- P1 make matrix (ACT <- COM) and P2 intermediate use (COM <- ACT) -------------------------------
    p1 = _cells(supply.filter(pl.col("item_code") == "output"), ["activity", "commodity"])
    pid = _prov(ctx, "P1", p1, "Supply table, domestic output at basic prices (product x industry)", conc)
    entries += _sut_entries(p1, "activity", "commodity", "P1", pid, ctx)
    p2 = _cells(use.filter(pl.col("item_code") == "ic"), ["commodity", "activity"])
    pid = _prov(ctx, "P2", p2, "Use table, intermediate consumption at purchasers' prices (product x industry)", conc)
    entries += _sut_entries(p2, "commodity", "activity", "P2", pid, ctx)

    # --- P3/P4 margins: negative TTM entries are margin services supplied, positive ones margins paid ----
    ttm = supply.filter(pl.col("item_code") == "ttm")
    p3 = _cells(ttm.filter(pl.col("value") < 0).with_columns(-pl.col("value")), ["commodity"])
    pid = _prov(ctx, "P3", p3, "negated negative entries of the Supply-table TTM column (trade, transport)", conc)
    entries += _sut_entries(p3.with_columns(pl.lit("M_TTM").alias("m")), "commodity", "m", "P3", pid, ctx)
    p4 = _cells(ttm.filter(pl.col("value") > 0), ["commodity"])
    pid = _prov(ctx, "P4", p4, "positive entries of the Supply-table TTM column", conc)
    entries += _sut_entries(p4.with_columns(pl.lit("M_TTM").alias("m")), "m", "commodity", "P4", pid, ctx)

    # --- P5 exports, P6 imports after the CIF adjustment ------------------------------------------------
    rest = pl.lit("R_ROW").alias("r")
    p5 = _cells(use.filter(pl.col("item_code") == "exports"), ["commodity"]).with_columns(rest)
    pid = _prov(ctx, "P5", p5, "Use-table Export column (product rows; memo rows excluded)", conc)
    entries += _sut_entries(p5, "commodity", "r", "P5", pid, ctx)
    p6 = _cells(supply.filter(pl.col("item_code") == "imports_after_cif"), ["commodity"]).with_columns(rest)
    pid = _prov(ctx, "P6", p6, "Supply-table 'Imports after cif adjustment' column (product rows)", conc)
    entries += _sut_entries(p6, "r", "commodity", "P6", pid, ctx)

    # --- P8 import duty, P9 product subsidies (negative), P10 net production taxes: fixed ----------------
    for ref, item, acct, what in (
        ("P8", "import_duty", "T_CUST", "Supply-table Import Duty column"),
        ("P9", "product_subsidies", "T_PSUB", "Supply-table Subsidy on Products column (negative, as published)"),
    ):
        df = _cells(supply.filter(pl.col("item_code") == item), ["commodity"]).with_columns(pl.lit(acct).alias("t"))
        pid = _prov(ctx, ref, df, what, conc)
        entries += _fixed_entries(df, "t", "commodity", ref, pid, ctx)
    p10 = _cells(va.filter(pl.col("item_code") == "net_production_taxes"), ["activity"]).with_columns(
        pl.lit("T_PROD").alias("t")
    )
    pid = _prov(ctx, "P10", p10, "Use-table value-added block, 'Production Taxes less Subsidies' row", conc)
    entries += _fixed_entries(p10, "t", "activity", "P10", pid, ctx)

    # --- I3 change in inventories by commodity (official by commodity, so written here) ------------------
    i3 = _cells(use.filter(pl.col("item_code") == "cii"), ["commodity"]).with_columns(pl.lit("K_DSTK").alias("k"))
    pid = _prov(ctx, "I3", i3, "Use-table CII column (change in inventories; product rows)", conc)
    entries += _sut_entries(i3, "commodity", "k", "I3", pid, ctx)

    # --- D4 GDP expenditure discrepancy (NAS 1.1): zero in 2023-24 ------------------------------------
    disc, disc_pid = ctx.value(NAS11, "s1_1.discrepancies.current", vintage=VINTAGE)
    if disc != 0.0:
        raise SamError(f"NAS 1.1 discrepancy is {disc} (not 0): D4 needs an allocation rule by commodity first")
    pid = ctx.prov(
        ref="D4",
        status="official",
        inputs=[disc_pid],
        method="NAS 2026 Statement 1.1 'Discrepancies' (current prices) is 0 for 2023-24, so every "
        "C_* <- X_DISC cell is written as 0 (the cell exists so later years plug in; gap map D4).",
        locator=f"{NAS11}: s1_1.discrepancies.current, {ctx.year}",
    )
    entries += [
        entry(c, "X_DISC", "D4", 0.0, prov_id=pid, status="official", role="fixed")
        for c in ctx.accounts.in_group("COM")
    ]

    # --- constraints: official totals whose split other blocks write ---------------------------------
    commodities, activities = ctx.accounts.in_group("COM"), ctx.accounts.in_group("ACT")
    hh, gov, cap = ctx.accounts.in_group("HH"), ctx.accounts.in_group("GOV"), ctx.accounts.in_group("CAP")
    specs = [
        # (ref, frame, key, item label, rows(code), cols(code), refs filter, constraint-id stem)
        ("P7", supply.filter(pl.col("item_code") == "product_taxes"), "commodity",
         "Supply-table Product taxes column (excl. import duty)", lambda c: PRODUCT_TAX_ACCOUNTS, lambda c: [c], None,
         "product_taxes"),
        ("C1", use.filter(pl.col("item_code") == "pfce"), "commodity", "Use-table PFCE column",
         lambda c: [c], lambda c: hh, None, "pfce"),
        ("C2", use.filter(pl.col("item_code") == "gfce"), "commodity", "Use-table GFCE column",
         lambda c: [c], lambda c: gov, None, "gfce"),
        ("I1", use.filter(pl.col("item_code") == "gfcf"), "commodity", "Use-table GFCF column",
         lambda c: [c], lambda c: cap, ["I1", "I1a"], "gfcf"),
        ("I2", use.filter(pl.col("item_code") == "valuables"), "commodity",
         "Use-table Net Acquisition of Valuables column (all acquirers: valuables by commodity = I2 + I2a)",
         lambda c: [c], lambda c: cap, ["I2", "I2a"], "valuables"),
        ("V1", va.filter(pl.col("item_code") == "ce"), "activity", "value-added block, Compensation of Employees",
         lambda a: ["F_LREG", "F_LCAS"], lambda a: [a], None, "ce"),
        ("V2", va.filter(pl.col("item_code").is_in(["os_mi", "cfc"])), "activity",
         "value-added block, Operating Surplus (incl. mixed income) + Consumption of Fixed Capital",
         lambda a: ["F_MIXD", "F_GOSC"], lambda a: [a], None, "os_mi_cfc"),
    ]  # fmt: skip
    totals: dict[str, pl.DataFrame] = {}
    for ref, frame, key, what, rows_of, cols_of, refs, stem in specs:
        agg = _cells(frame, [key])
        totals[stem] = agg
        pid = _prov(ctx, ref, agg, what, conc, constraint_note=True)
        by = {r[key]: r for r in agg.iter_rows(named=True)}
        for code in commodities if key == "commodity" else activities:
            r = by.get(code)
            t, n = (r["value"], r["n_cells"]) if r else (0.0, 0)
            cons.append(
                constraint(
                    f"{stem}.{code.lower()}",
                    ref,
                    rows_of(code),
                    cols_of(code),
                    t,
                    prov_id=pid,
                    tol_abs=ROUNDING * n,
                    refs=refs,
                    description=f"SUT {ctx.year} {what} for {code} ({n} SUT cell(s); 0 = no such use)",
                )
            )

    _checks(ctx, entries, totals, supply, use, ind)
    return BlockResult(entries=entries, constraints=cons, satellites={"sut_memo": _memo(ctx, supply, use)})


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------


def _concordances(ctx: BlockContext) -> tuple[pl.DataFrame, pl.DataFrame, str]:
    """SUT product -> commodity and SUT industry -> activity, as the codes used in the clean data."""
    p = ctx.concordance(PRODUCT_MAP).select(
        ("sut_p" + pl.col("sut_product").str.zfill(3)).alias("product"), "commodity", "nas_group"
    )
    i = ctx.concordance(INDUSTRY_MAP).select(
        ("sut_i" + pl.col("sut_industry").str.zfill(2)).alias("industry"), "activity", "nas_group"
    )
    for what, df, col, group in (("product", p, "commodity", "COM"), ("industry", i, "activity", "ACT")):
        if df[what].n_unique() != df.height:
            raise SamError(f"{what} concordance maps a SUT code twice")
        bad = sorted(set(df[col].to_list()) - set(ctx.accounts.in_group(group)))
        if bad:
            raise SamError(f"{what} concordance uses codes that are not {group} accounts: {bad}")
    sha = ", ".join(f"{k}.csv sha256 {v[:12]}" for k, v in sorted(ctx.concordances_read.items()))
    return p, i, sha


def _tag(df: pl.DataFrame, prod: pl.DataFrame, ind: pl.DataFrame) -> pl.DataFrame:
    """Attach commodity/activity codes to real product/industry rows; memo and total rows keep nulls.
    Fails if a real SUT product or industry is missing from the concordance."""
    df = df.join(prod.select("product", "commodity"), on="product", how="left", maintain_order="left").join(
        ind.select("industry", "activity"), on="industry", how="left", maintain_order="left"
    )
    unmapped_p = df.filter(pl.col("product").str.starts_with("sut_p") & pl.col("commodity").is_null())
    unmapped_i = df.filter(pl.col("industry").str.starts_with("sut_i") & pl.col("activity").is_null())
    if unmapped_p.height or unmapped_i.height:
        raise SamError(
            f"SUT codes missing from the concordance: products {sorted(set(unmapped_p['product']))}, "
            f"industries {sorted(set(unmapped_i['industry']))}"
        )
    return df


def _cells(df: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    """Sum real SUT cells (every key column mapped; memo and 'total' rows have null codes and drop out)
    by the SAM keys. Columns: keys, value, n_cells, prov_ids (sorted, comma-joined clean prov_ids)."""
    df = df.filter(pl.all_horizontal(pl.col(k).is_not_null() for k in keys))
    return (
        df.group_by(keys, maintain_order=True)
        .agg(
            pl.col("value").sum(),
            pl.len().cast(pl.Int64).alias("n_cells"),
            pl.col("prov_id").unique().sort().str.join(",").alias("prov_ids"),
        )
        .sort(keys)
    )


def _prov(
    ctx: BlockContext, ref: str, agg: pl.DataFrame, what: str, conc: str, *, constraint_note: bool = False
) -> str:
    inputs = sorted({p for s in agg["prov_ids"].to_list() for p in s.split(",")})
    use = "constraint targets" if constraint_note else "entries"
    return ctx.prov(
        ref=ref,
        status="official",
        inputs=inputs,
        method=f"Gap map {ref}: {use} = sums of SUT {ctx.year} {what} over the 34-sector concordance ({conc}); "
        f"{agg['n_cells'].sum()} published cells, no value changed (pure aggregation). Allowance (assumed, for "
        f"the SUT's non-additivity): Rs {ROUNDING:g} crore per SUT cell aggregated.",
        locator=f"{', '.join(sorted(ctx.datasets_read & {SUPPLY, USE, VA}))}, period {ctx.year}",
        table_id=f"SUT {ctx.year} (Supply and Use Tables, 155 products x 67 industries)",
    )


def _sut_entries(agg: pl.DataFrame, row_col: str, col_col: str, ref: str, pid: str, ctx: BlockContext) -> list[dict]:
    """Anchored entries from aggregated SUT cells (zero sums dropped: a structural zero is absent)."""
    out, zeros = [], 0
    for r in agg.iter_rows(named=True):
        v = r["value"]
        if v == 0:
            zeros += 1
            continue
        out.append(
            entry(
                r[row_col],
                r[col_col],
                ref,
                v,
                prov_id=pid,
                status="official",
                role="anchored",
                tol_rel=ROUNDING * r["n_cells"] / abs(v),
            )  # fmt: skip
        )
    if zeros:
        ctx.log(f"{ref}: {zeros} aggregated cell(s) sum to exactly 0 and are left out")
    return out


def _fixed_entries(agg: pl.DataFrame, row_col: str, col_col: str, ref: str, pid: str, ctx: BlockContext) -> list[dict]:
    """Fixed entries (the tax vectors). Zero sums are dropped and logged, as in _sut_entries."""
    zero = agg.filter(pl.col("value") == 0)
    if zero.height:
        ctx.log(f"{ref}: {zero.height} aggregated cell(s) sum to exactly 0 and are left out")
    return [
        entry(r[row_col], r[col_col], ref, r["value"], prov_id=pid, status="official", role="fixed")
        for r in agg.iter_rows(named=True)
        if r["value"] != 0
    ]


def _memo(ctx: BlockContext, supply: pl.DataFrame, use: pl.DataFrame) -> Satellite:
    """SUT memo items that are not SAM cells (gap map P5/P6 notes): CIF adjustment by commodity and the
    purchases of residents abroad / non-residents in India, as published."""
    cif = _cells(supply.filter(pl.col("item_code") == "cif_adj"), ["commodity"])
    memo = pl.concat(
        [
            supply.filter(pl.col("product").is_in(["cif", "purchases_residents_abroad"])),
            use.filter(pl.col("product").is_in(["purchases_nonresidents_domestic", "purchases_residents_abroad"])),
        ]
    ).sort("series_id")
    inputs = sorted(set(memo["prov_id"].to_list()) | {p for s in cif["prov_ids"].to_list() for p in s.split(",")})
    pid = ctx.prov(
        ref="P6",
        status="official",
        inputs=inputs,
        method=f"SUT {ctx.year} memo items as published: the CIF adjustment column summed by commodity over the "
        "34-sector concordance, and the memo rows 'CIF', 'Purchases of Residents abroad' and 'Purchases of "
        "Non-Residents in domestic market' (already inside the product rows; not SAM cells).",
        locator=f"{SUPPLY} item cif_adj and memo rows; {USE} memo rows; period {ctx.year}",
    )
    rows = [
        {"series_id": f"cif_adj.{r['commodity'].lower()}", "item": "cif_adjustment", "commodity": r["commodity"],
         "value": r["value"], "unit": "INR_crore", "status": "official", "prov_id": pid}
        for r in cif.iter_rows(named=True)
    ] + [
        {"series_id": f"memo.{r['item_code']}.{r['product']}", "item": f"{r['item_code']}:{r['product']}",
         "commodity": None, "value": r["value"], "unit": "INR_crore", "status": "official", "prov_id": pid}
        for r in memo.iter_rows(named=True)
    ]  # fmt: skip
    df = pl.DataFrame(
        rows,
        schema={
            "series_id": pl.String(),
            "item": pl.String(),
            "commodity": pl.String(),
            "value": pl.Float64(),
            "unit": pl.String(),
            "status": pl.String(),
            "prov_id": pl.String(),
        },  # fmt: skip
        orient="row",
    )
    return Satellite("P6", df, f"SUT {ctx.year} memo items: CIF adjustment by commodity; purchases abroad/in India")


def _checks(
    ctx: BlockContext,
    entries: list[dict],
    totals: dict[str, pl.DataFrame],
    supply: pl.DataFrame,
    use: pl.DataFrame,
    ind: pl.DataFrame,
) -> None:
    """Every production total against NAS 2026 (and the SUT's own total rows), read from clean data."""

    def s(ref: str) -> float:
        return sum(e["value"] for e in entries if e["ref"] == ref)

    def t(stem: str) -> float:
        return float(totals[stem]["value"].sum())

    def nas(sid: str, ds: str = NAS11) -> tuple[float, str]:
        return ctx.value(ds, sid, vintage=VINTAGE)

    gva = s("P1") - s("P2")
    net_product_taxes = t("product_taxes") + s("P8") + s("P9")
    checks = [
        ("gdp_production", "GDP = output - IC + product taxes + import duty + product subsidies (NAS 1.1 GDP)",
         gva + net_product_taxes, nas("s1_1.gdp.current")),
        ("gdp_expenditure", "GDP = PFCE + GFCE + GFCF + CIS + valuables + exports - imports (NAS 1.1 GDP)",
         t("pfce") + t("gfce") + t("gfcf") + s("I3") + t("valuables") + s("P5") - s("P6"),
         nas("s1_1.gdp_expenditure.current")),
        ("gva", "GVA at basic prices = output - IC (NAS 1.1)", gva, nas("s1_1.gva_basic.current")),
        ("output", "Output (P1) vs NAS 7.1 total gross output", s("P1"), nas("s7_1.total.output.current", NAS71)),
        ("ic_nas71", "Intermediate consumption (P2) vs NAS 7.1 total", s("P2"), nas("s7_1.total.ic.current", NAS71)),
        ("ic_sut_note", "Intermediate consumption (P2) vs SUT note Table 9 IC", s("P2"), _note(ctx, "ic")),
        ("pfce", "PFCE by commodity (C1 targets) vs NAS 1.1", t("pfce"), nas("s1_1.pfce.current")),
        ("gfce", "GFCE by commodity (C2 targets) vs NAS 1.1", t("gfce"), nas("s1_1.gfce.current")),
        ("gfcf", "GFCF by commodity (I1 targets) vs NAS 1.1", t("gfcf"), nas("s1_1.gfcf.current")),
        ("cis", "Change in inventories (I3) vs NAS 1.1", s("I3"), nas("s1_1.cis.current")),
        ("valuables", "Valuables by commodity (I2 targets) vs NAS 1.1", t("valuables"), nas("s1_1.valuables.current")),
        ("exports", "Exports (P5) vs NAS 1.1", s("P5"), nas("s1_1.exports.current")),
        ("imports", "Imports after CIF adjustment (P6) vs NAS 1.1", s("P6"), nas("s1_1.imports.current")),
        ("product_taxes", "Product taxes (P7 targets) + import duty (P8) vs NAS 1.1 taxes on products",
         t("product_taxes") + s("P8"), nas("s1_1.taxes_on_products.current")),
        ("product_subsidies", "Product subsidies (P9, negative) vs minus NAS 1.1 subsidies on products",
         -s("P9"), nas("s1_1.subsidies_on_products.current")),
        ("ce", "CE by activity (V1 targets) vs NAS 7.1 total", t("ce"), nas("s7_1.total.ce.current", NAS71)),
        ("os_mi_cfc", "OS/MI + CFC (V2 targets) vs NAS 7.1 OS/MI + CFC", t("os_mi_cfc"),
         _sum2(ctx, "s7_1.total.os_mi.current", "s7_1.total.cfc.current")),
        ("net_production_taxes", "Net production taxes (P10) vs NAS 7.1 total", s("P10"),
         nas("s7_1.total.net_production_taxes.current", NAS71)),
    ]  # fmt: skip
    for cid, desc, v, (target, tpid) in checks:
        ctx.check(cid, desc, v, target, target_prov_id=tpid, tol_abs=CHECK_TOL)

    # the SUT's own published total rows (rounding inside the SUT)
    for cid, frame, item, ref_sum in (
        ("sut_total.imports_after_cif", supply, "imports_after_cif", s("P6")),
        ("sut_total.import_duty", supply, "import_duty", s("P8")),
        ("sut_total.product_subsidies", supply, "product_subsidies", s("P9")),
        ("sut_total.product_taxes", supply, "product_taxes", t("product_taxes")),
        ("sut_total.exports", use, "exports", s("P5")),
        ("sut_total.pfce", use, "pfce", t("pfce")),
        ("sut_total.ic", use, "ic_total", s("P2")),
    ):
        row = frame.filter((pl.col("item_code") == item) & (pl.col("product") == "total"))
        if row.height != 1:
            raise SamError(f"SUT total row for {item} not found exactly once")
        ctx.check(cid, f"Sum of SAM {item} vs the SUT's own 'total' row", ref_sum, row["value"][0],
                  target_prov_id=row["prov_id"][0], tol_abs=CHECK_TOL)  # fmt: skip

    # output by NAS broad group vs NAS 7.1 (groups 9 and 11 compared together: SUT industry 58 holds R&D,
    # which NAS files under professional services, group 9; RECONCILIATION.md IND-re-output)
    groups = dict(zip(ind["activity"].to_list(), ind["nas_group"].to_list()))
    by_group: dict[str, float] = {}
    for e in entries:
        if e["ref"] == "P1":
            g = groups[e["row"]]
            by_group[g] = by_group.get(g, 0.0) + e["value"]
    for g, code in NAS_GROUPS.items():
        if g in ("9", "11"):
            continue
        tv, tp = nas(f"s7_1.{code}.output.current", NAS71)
        ctx.check(f"output_group.{code}", f"Output of NAS group {g} ({code}) vs NAS 7.1", by_group[g], tv,
                  target_prov_id=tp, tol_abs=CHECK_TOL)  # fmt: skip
    v9, p9 = nas("s7_1.real_estate_prof.output.current", NAS71)
    v11, _ = nas("s7_1.other_services.output.current", NAS71)
    ctx.check("output_group.9_plus_11", "Output of NAS groups 9 + 11 vs NAS 7.1 (R&D sits in 11 in the SUT, 9 in NAS)",
              by_group["9"] + by_group["11"], v9 + v11, target_prov_id=p9, tol_abs=CHECK_TOL)  # fmt: skip


def _note(ctx: BlockContext, item: str) -> tuple[float, str]:
    df = ctx.rows(NOTE, item_code=item, vintage=VINTAGE)
    if df.height != 1:
        raise SamError(f"SUT note total {item!r}: {df.height} rows for {ctx.year}")
    return float(df["value"][0]), str(df["prov_id"][0])


def _sum2(ctx: BlockContext, a: str, b: str) -> tuple[float, str]:
    va, pa = ctx.value(NAS71, a, vintage=VINTAGE)
    vb, _ = ctx.value(NAS71, b, vintage=VINTAGE)
    return va + vb, pa
