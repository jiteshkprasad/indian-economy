"""The capital_financial block (plan docs/phase2/plans/capital_financial.md s.7, tests T1-T25).

Three layers:
- pure functions on small fixtures (the allocation rule, RAS, the K9 pair, the RoW posting reader);
- a build on synthetic stand-ins for government and fincorp (when those are not built) and the real
  rest_of_world and households outputs: every official total the block must reproduce, recomputed here
  from data/clean with polars (never typed in);
- the built outputs (fresh build equals the files, checks pass, K accounts close), once every DEPENDS block
  is built.
"""

from __future__ import annotations

import polars as pl
import pytest

from pipeline.core.io import canonical_floats
from pipeline.core.paths import Layout
from pipeline.sam import spec
from pipeline.sam.blocks import capital_financial as CF
from pipeline.sam.blocks.capital_financial import fsf as F
from pipeline.sam.blocks.capital_financial import params as P
from pipeline.sam.blocks.capital_financial import physical as X
from pipeline.sam.blocks.capital_financial import residuals as R
from pipeline.sam.blocks.capital_financial import row as W
from pipeline.sam.framework import BlockContext, SamError, SamPaths, build_block_module, validate_result

pytestmark = pytest.mark.sam

LAYOUT = Layout.default()
PATHS = SamPaths(LAYOUT)
YEAR = spec.YEAR
ALL_DEPS_BUILT = all(PATHS.built(b) for b in CF.DEPENDS)


# ---------------------------------------------------------------------------------------------------
# clean-data readers for expected values
# ---------------------------------------------------------------------------------------------------


def _clean(unit: str, dataset: str) -> pl.DataFrame:
    """A clean dataset, latest vintage of each (series, period) (the datasets used here carry dated vintages)."""
    df = pl.read_parquet(LAYOUT.clean / unit / f"{dataset}.parquet")
    last = df.group_by("series_id", "period", maintain_order=True).agg(pl.col("vintage").max().alias("_v"))
    return df.join(last, on=["series_id", "period"], maintain_order="left").filter(pl.col("vintage") == pl.col("_v"))


def _v(unit: str, dataset: str, sid: str, period: str = YEAR) -> float:
    df = _clean(unit, dataset).filter((pl.col("series_id") == sid) & (pl.col("period") == period))
    assert df.height == 1, (dataset, sid, period, df.height)
    return float(df["value"][0])


def _nas(ds: str, sid: str) -> float:
    return _v("mospi_nas_2026", f"mospi_nas_2026_{ds}", sid)


def _fsf(sid: str, period: str = YEAR) -> float:
    return _v("rbi_financial_accounts", "rbi_financial_accounts_fsf_balance_sheets", sid, period)


# ---------------------------------------------------------------------------------------------------
# pure functions
# ---------------------------------------------------------------------------------------------------


def test_abs_share_keeps_signs_and_hits_the_total():
    out = F.abs_share(100.0, {"a": 80.0, "b": -20.0, "c": 60.0})
    assert out is not None
    assert sum(out.values()) == pytest.approx(100.0)
    # the adjustment (100 - 120) is spread by |r|: a gets 80 - 20*80/160
    assert out["a"] == pytest.approx(70.0) and out["b"] == pytest.approx(-22.5) and out["c"] == pytest.approx(52.5)
    assert F.abs_share(5.0, {"a": 0.0}) is None


def test_ras_fits_rows_and_columns_and_keeps_zeros():
    prior = {("r1", "c1"): 1.0, ("r1", "c2"): 1.0, ("r2", "c1"): 1.0}
    cells, _ = X.ras(prior, {"r1": 4.0, "r2": 6.0}, {"c1": 7.0, "c2": 3.0})
    assert ("r2", "c2") not in cells
    assert cells[("r1", "c1")] + cells[("r1", "c2")] == pytest.approx(4.0)
    assert cells[("r1", "c1")] + cells[("r2", "c1")] == pytest.approx(7.0)
    with pytest.raises(SamError):
        X.ras(prior, {"r1": 4.0, "r2": 6.0}, {"c1": 7.0, "c2": 4.0})


def test_largest_remainder_split_adds_up_exactly():
    parts = X.largest_remainder_split(154528.496164, {"a": 3.0, "b": 7.0, "c": 0.0})
    assert "c" not in parts
    assert sum(parts.values()) == 154528.496164


def test_residual_pair_nets_to_k9_and_skips_tiny_residuals():
    assert R.residual_pair({"k9": 0.4, "pos": 5.0, "neg": -4.6}) == {}
    pair = R.residual_pair({"k9": 10.0, "pos": 30.0, "neg": -20.0})
    assert pair["residual_pos"] + pair["residual_neg"] == pytest.approx(10.0)
    assert R.residual_pair({"k9": -7.0, "pos": 0.0, "neg": -7.0}) == {"residual_neg": -7.0}


def test_sam_instrument_map():
    assert F.sam_instrument("f22_f29", "gg_cen") == "I_SSAV"
    assert F.sam_instrument("f22_f29", "fc_odc") == "I_DEPO"
    assert F.sam_instrument("f3", "gg_sta") == "I_GSEC"
    assert F.sam_instrument("f3", "nfc_pvt") == "I_CBND"
    assert F.sam_instrument("f52", "fc_ofc") == "I_MFUN"
    assert F.sam_instrument("f6_pf", "gg_cen") == "I_INPE"
    with pytest.raises(SamError):
        F.sam_instrument("other", "gg_cen")


def test_row_postings_reader():
    sat = pl.DataFrame(
        {
            "line": ["nri", "eo", "res", "rei", "fdi"],
            "instrument": ["I_DEPO", "I_OTHR", "I_RESV", "I_EQTY", "I_EQTY"],
            "bop_function": ["NRI_deposits", "other", "reserves", "FDI_reinvested_earnings", "FDI_equity"],
            "direction": ["row_acquires", "row_acquires", "row_incurs", "row_acquires", "row_acquires"],
            "counterpart": ["K_BANK", "unallocated_k9", "K_RBI", "K_NFPR", "FC"],
            "value": [10.0, 3.0, 50.0, 9.0, 4.0],
        }
    )
    sat = sat.with_columns(pl.col("line").replace({"rei": W.REINVESTED}))
    r14a = pl.DataFrame({"row": ["R_ROW", "R_ROW"], "col": ["E_NFPR", "E_BANK"], "value": [6.0, 3.0]})
    posts, log = W.postings(sat, r14a, {"K_BANK": 1.0, "K_NBFC": 3.0})
    got = {(p.account, p.instrument, p.side, p.line): p.value for p in posts}
    assert got[("K_BANK", "I_DEPO", "liability", "nri")] == 10.0
    assert got[("K_NFPR", "I_EQTY", "liability", W.REINVESTED)] == 6.0  # R14a payer split, not the satellite's
    assert got[("K_BANK", "I_EQTY", "liability", W.REINVESTED)] == 3.0
    assert got[("K_NBFC", "I_EQTY", "liability", "fdi")] == pytest.approx(3.0)
    assert not any(p.instrument == "I_RESV" for p in posts)  # rest_of_world's K8c is the domestic side
    assert not any(p.line == "eo" for p in posts) and any("eo" in m for m in log)
    with pytest.raises(SamError):
        W.postings(sat.drop("direction"), r14a, {})


# ---------------------------------------------------------------------------------------------------
# a build on synthetic stand-ins for government and fincorp
# ---------------------------------------------------------------------------------------------------


def _stand_in_deps(ctx: BlockContext) -> CF.Deps:
    """rest_of_world and households as built; government and fincorp as they are built, else stand-ins from
    clean NAS 1.9 (all FC saving on K_BANK, GG saving on K_GCEN, no K6/K8e, uniform FC GOS key)."""
    if PATHS.built("government") and PATHS.built("fincorp"):
        return CF.read_deps(ctx)
    v = lambda sid: ctx.value("mospi_nas_2026_s1_9", sid, vintage="latest")  # noqa: E731
    pub, pid = v("s1_9.public_financial_corporations.current")
    prv, _ = v("s1_9.private_financial_corporations.current")
    gg, _ = v("s1_9.general_government.current")
    fake = pl.DataFrame(
        [
            {"row": "K_BANK", "col": "E_BANK", "ref": "K2a", "component": "public", "value": pub, "block": "fincorp"},
            {"row": "K_BANK", "col": "E_BANK", "ref": "K2a", "component": "private", "value": prv, "block": "fincorp"},
            {"row": "K_GCEN", "col": "G_CEN", "ref": "K3a", "component": "total", "value": gg, "block": "government"},
        ]
    ).with_columns(pl.lit(pid).alias("prov_id"))
    row_e = pl.read_parquet(PATHS.entries("rest_of_world")).with_columns(pl.col("component").fill_null("total"))
    capfin = ctx.accounts.in_group("CAP") + ctx.accounts.in_group("INST")
    rowk = row_e.filter(pl.col("row").is_in(capfin) | pl.col("col").is_in(capfin)).select(CF.ENTRY_COLS)
    sat = pl.read_parquet(PATHS.satellites("rest_of_world") / f"{W.SATELLITE}.parquet")
    r14a = row_e.filter(pl.col("ref") == "R14a").select("row", "col", "value", "prov_id")
    hk = pl.read_parquet(PATHS.satellites("households") / "hh_keys.parquet")
    return CF.Deps(
        k8e=0.0,
        k8e_pids=[],
        fc_gos={(a, p): 1.0 for a in P.K_FC_GFCF for p in ("public", "private")},
        fc_pids=[pid],
        row_sat=sat,
        r14a=r14a,
        row_pids=sorted(set(sat["prov_id"]) | set(r14a["prov_id"])),
        entries=pl.concat([fake.select(CF.ENTRY_COLS), rowk], how="vertical"),
        hh_keys=hk,
        hh_pids=sorted(set(hk["prov_id"])),
    )


@pytest.fixture(scope="module")
def syn():
    if not (PATHS.built("rest_of_world") and PATHS.built("households")):
        pytest.skip(
            "rest_of_world / households not built: run `uv run python -m pipeline sam rest_of_world households`"
        )
    depends = tuple(b for b in CF.DEPENDS if PATHS.built(b))
    ctx = BlockContext(block=CF.BLOCK, refs=tuple(CF.REFS), depends=depends, layout=LAYOUT)
    deps = _stand_in_deps(ctx)
    res = CF.compute(ctx, deps)
    valid = validate_result(ctx, res)
    return ctx, deps, valid


def _e(valid, **kw) -> pl.DataFrame:
    df = valid.entries
    for k, v in kw.items():
        df = df.filter(pl.col(k).is_in(v) if isinstance(v, (list, tuple)) else pl.col(k) == v)
    return df


def _sum(valid, **kw) -> float:
    return float(_e(valid, **kw)["value"].sum())


def test_checks_pass_on_the_synthetic_build(syn):
    _, _, valid = syn
    failed = valid.checks.filter(~pl.col("ok"))
    assert failed.height == 0, failed
    assert valid.checks.height >= 20


def test_t1_t2_gfcf_by_sector_and_commodity(syn):
    _, _, valid = syn
    i1a = _e(valid, ref="I1a")
    sectors = {
        "public_non_financial_corporations": ["K_NFPU"],
        "private_non_financial_corporations": ["K_NFPR"],
        "general_government": ["K_GCEN", "K_GSTA"],
        "household_sector": ["K_HH"],
    }
    for stem, cols in sectors.items():
        got = float(i1a.filter(pl.col("col").is_in(cols))["value"].sum())
        assert got == pytest.approx(_nas("s1_11", f"s1_11.{stem}.current"), abs=1.0), stem
    for part, stem in (("public", "public_financial_corporations"), ("private", "private_financial_corporations")):
        got = float(i1a.filter(pl.col("component") == part)["value"].sum())
        assert got == pytest.approx(_nas("s1_11", f"s1_11.{stem}.current"), abs=1.0), part
    use = _clean("io_tables", "io_tables_sut_use").filter(pl.col("period") == YEAR)
    total = float(use.filter(pl.col("series_id") == "use.gfcf.total.current")["value"][0])
    assert float(i1a["value"].sum()) == pytest.approx(total, abs=0.01)
    # rows = production's I1 targets by commodity (SUT via the committed concordance)
    cons = pl.read_parquet(PATHS.constraints("production")).filter(pl.col("constraint_id").str.starts_with("gfcf."))
    by_c = dict(i1a.group_by("row", maintain_order=True).agg(pl.col("value").sum()).iter_rows())
    for r in cons.iter_rows(named=True):
        c = r["rows"]
        assert by_c.get(c, 0.0) == pytest.approx(r["target"], abs=0.01), c
    assert (i1a["role"] == "free").all() and set(i1a["status"]) == {"estimated"}


def test_t3_t17_valuables_and_saving_investment_errors(syn):
    _, _, valid = syn
    gold = _nas("s1_9", "s1_9.saving_in_the_form_of_gold_and_silver_ornaments.current")
    assert gold == _nas("s5_3", "s5_3.saving_in_form_of_gold_and_silver_ornaments.current")
    valu = _v("io_tables", "io_tables_sut_use", "use.valuables.total.current")
    assert _sum(valid, ref="I2") == pytest.approx(gold, abs=1e-6)
    assert _sum(valid, ref="I2") + _sum(valid, ref="I2a") == pytest.approx(valu, abs=1e-6)
    assert set(_e(valid, ref=["I2", "I2a"])["row"]) == {"C_GJOM"} and set(_e(valid, ref=["I2", "I2a"])["col"]) == {
        "K_HH"
    }
    d3 = _v("mospi_nas_2026", "mospi_nas_2026_derived_residuals", "derived.si_errors_omissions.current")
    assert _sum(valid, ref="D3") == pytest.approx(d3, abs=1e-6)
    assert _sum(valid, ref="D3", row="K_HH") == pytest.approx(_sum(valid, ref="I2a"), abs=1e-6)
    # remainder pro rata to corporate GCF: the NFC ratio is the NAS 1.14 GCF ratio
    pu = _nas("s1_14", "s1_14.nfc_public.gross_capital_formation.current")
    pv = _nas("s1_14", "s1_14.nfc_private.gross_capital_formation.current")
    assert _sum(valid, ref="D3", row="K_NFPU") / _sum(valid, ref="D3", row="K_NFPR") == pytest.approx(pu / pv, rel=1e-9)
    assert set(_e(valid, ref="D3")["col"]) == {"X_DISC"} and (_e(valid, ref="D3")["role"] == "fixed").all()


def test_t4_inventories(syn):
    _, _, valid = syn
    i3a = _e(valid, ref="I3a")
    cii = _v("io_tables", "io_tables_sut_use", "use.cii.total.current")
    assert float(i3a["value"].sum()) == pytest.approx(cii, abs=0.01)
    for stem114, stem111, cols in (
        ("nfc_public", "public_non_financial_corporations", ["K_NFPU"]),
        ("nfc_private", "private_non_financial_corporations", ["K_NFPR"]),
        ("gg", "general_government", ["K_GCEN", "K_GSTA"]),
        ("households_npish", "household_sector", ["K_HH"]),
    ):
        want = _nas("s1_14", f"s1_14.{stem114}.gross_capital_formation.current") - _nas(
            "s1_11", f"s1_11.{stem111}.current"
        )
        assert float(i3a.filter(pl.col("col").is_in(cols))["value"].sum()) == pytest.approx(want, abs=0.1), stem114
    pub = float(i3a.filter(pl.col("col").is_in(["K_NFPU", "K_GCEN"]))["value"].sum())
    assert pub == pytest.approx(_nas("s7_2a", "s7_2a.total.cis.current"), abs=0.1)
    assert set(i3a["row"]) == {"K_DSTK"} and _sum(valid, ref="I3a", col="K_GSTA") == 0.0


def test_t5_t6_saving(syn):
    _, _, valid = syn
    for a, stem in (("K_NFPU", "public"), ("K_NFPR", "private")):
        assert _sum(valid, ref="K1", row=a) == _nas("s1_9", f"s1_9.{stem}_non_financial_corporations.current")
    k4 = valid.constraints.filter(pl.col("ref") == "K4")
    assert k4.height == 1
    t = k4["target"][0]
    assert t == _nas("s1_9", "s1_9.household_sector.current")
    assert t == pytest.approx(_nas("s1_14", "s1_14.households_npish.gross_savings.current"), abs=0.5)
    assert t == pytest.approx(_nas("s5_3", "s5_3.household_saving_1_2_3_4.current"), abs=0.5)
    closure_like = k4.row(0, named=True)
    assert closure_like["rows"] == "K_HH" and closure_like["refs"] == "K4a" and closure_like["tol_abs"] == 0.5


def test_t7_t8_household_financial_saving(syn):
    _, _, valid = syn
    assert _sum(valid, ref="K7a") == pytest.approx(_nas("s5_3", "s5_3.gross_financial_saving.current"), abs=0.01)
    assert _sum(valid, ref="K8a") == pytest.approx(_nas("s5_3", "s5_3.financial_liabilities.current"), abs=0.01)
    net = _nas("s5_3", "s5_3.net_financial_saving_of_household_sector_1_4.current")
    assert _sum(valid, ref="K7a") - _sum(valid, ref="K8a") == pytest.approx(net, abs=0.01)
    nssf = _v("union_fiscal", "union_fiscal_nssf", "nssf.net_collection")
    assert _sum(valid, ref="K7a", row="I_SSAV") == pytest.approx(nssf, abs=0.01)
    inpe = _nas("s5_3", "s5_3.insurance_funds.current") + _nas("s5_3", "s5_3.provident_and_pension_funds.current")
    ppf = _v("union_fiscal", "union_fiscal_nssf", "nssf.ppf.additions")
    assert _sum(valid, ref="K7a", row="I_INPE") == pytest.approx(inpe - ppf, abs=0.01)
    k7a = _e(valid, ref="K7a")
    assert k7a.filter(pl.col("component") == "ppf")["row"].to_list() == ["I_SSAV"]  # PPF in I_SSAV only (D5)
    # census: every NAS 5.3 line maps to exactly one instrument, components frozen by XR-19
    assert sorted(k7a["component"]) == sorted(c for c, _, _ in CF.H.ASSET_LINES)
    assert k7a["component"].n_unique() == k7a.height
    assert sorted(_e(valid, ref="K8a")["component"]) == sorted(c for c, _ in CF.H.LIABILITY_LINES)
    assert (_e(valid, ref=["K7a", "K8a"])["role"] == "fixed").all()


def test_t9_ppf_is_inside_nas_pf_and_equals_the_t52b_stock_change():
    t52 = _clean("rbi_financial_accounts", "rbi_financial_accounts_hh_finsav_52ab")

    def stock(p: str) -> float:
        return float(t52.filter((pl.col("series_id") == "t52b.fa_ppf.current") & (pl.col("period") == p))["value"][0])

    ppf = _v("union_fiscal", "union_fiscal_nssf", "nssf.ppf.additions")
    assert stock("2024-03-31") - stock("2023-03-31") == pytest.approx(ppf, abs=0.1)
    small = _nas("s5_3", "s5_3.investment_in_small_savings_etc.current")
    assert small + ppf == pytest.approx(_v("union_fiscal", "union_fiscal_nssf", "nssf.net_collection"), abs=0.01)


def test_t10_fsf_extraction_reproduces_statement_7():
    bs = _clean("rbi_financial_accounts", "rbi_financial_accounts_fsf_balance_sheets").filter(
        (pl.col("period") == YEAR) & (pl.col("dim_other") == "measure=transaction") & (pl.col("counterparty") == "all")
    )
    for side in ("assets", "liabilities"):
        leaf = bs.filter(
            pl.col("institution").is_in([*P.SUB_ACCOUNT, "row"])
            & (pl.col("side") == side)
            & pl.col("instrument").is_in(list(P.FSF_TOP_INSTRUMENTS))
        )
        st7 = _v(
            "rbi_financial_accounts",
            "rbi_financial_accounts_fsf_instrument_sector",
            f"fsf7.all.{side}.transaction.total.current",
        )
        assert float(leaf["value"].sum()) == pytest.approx(st7, abs=1.0), side
    # the report table keeps every leaf cell of the instruments it reads: per statement line, cells = 'all'
    rep = F.reports(
        _clean("rbi_financial_accounts", "rbi_financial_accounts_fsf_balance_sheets").filter(pl.col("period") == YEAR)
    )
    for (sub, side, fi), g in rep.group_by("sub", "side", "fsf_instr", maintain_order=True):
        allv = bs.filter((pl.col("institution") == sub) & (pl.col("side") == side) & (pl.col("instrument") == fi))
        assert float(g["value"].sum()) == pytest.approx(float(allv["value"][0]), abs=1e-5), (sub, side, fi)


def test_fsf_markets_do_not_clear_as_published(syn):
    """The reason for the reconciliation (plan s.2.6): equity holders report far more than issuers."""
    _, _, valid = syn
    sat = valid.satellites["fsf_instrument_closure"][1]
    d = {(r["fsf_instrument"], r["side"]): r["value"] for r in sat.iter_rows(named=True)}
    assert d[("f51", "assets")] - d[("f51", "liabilities")] > 1.0e6


def test_t11_reconciled_pairs_clear_and_follow_the_control_side(syn):
    _, _, valid = syn
    dom = valid.entries.filter(pl.col("component").str.starts_with("dom"))
    for inst in ("I_CURR", "I_DEPO", "I_SSAV", "I_GSEC", "I_CBND", "I_LOAN", "I_EQTY", "I_MFUN"):
        held = float(dom.filter(pl.col("row") == inst)["value"].sum())
        issued = float(dom.filter(pl.col("col") == inst)["value"].sum())
        assert held == pytest.approx(issued, abs=1e-6), inst
    assert (
        dom.filter(
            pl.col("row").is_in(["I_OTHR", "I_RESV", "I_INPE"]) | pl.col("col").is_in(["I_OTHR", "I_RESV", "I_INPE"])
        ).height
        == 0
    )
    dual = valid.satellites["s4_fsf_dual_reports"][1]
    wide = {(r["instrument"], r["holder"], r["issuer"], r["measure"]): r["value"] for r in dual.iter_rows(named=True)}
    # issuer control: the Centre's G-sec liability to banks as printed; holder control: banks' loans to private NFCs
    assert wide[("I_GSEC", "fc_odc", "gg_cen", "chosen")] == pytest.approx(
        _fsf("fsf.gg_cen.liabilities.transaction.f3.fc_odc.current"), abs=1e-6
    )
    odc_loans = sum(
        _fsf(f"fsf.{s}.assets.transaction.f4.nfc_pvt.current")
        for s in ("fc_odc_scb", "fc_odc_coop", "fc_odc_nbfc_dt", "fc_odc_hfc_dt")
    )
    assert wide[("I_LOAN", "fc_odc", "nfc_pvt", "chosen")] == pytest.approx(odc_loans, abs=1e-6)
    # an anchored (control-side, published) cell is a pure sum of printed reports: the Centre's small savings
    # liability to public NFCs
    cell = valid.entries.filter((pl.col("row") == "K_GCEN") & (pl.col("col") == "I_SSAV") & (pl.col("ref") == "K8"))
    assert cell["role"].to_list() == ["anchored"]
    assert float(cell["value"][0]) == pytest.approx(
        _fsf("fsf.gg_cen.liabilities.transaction.f22_f29.nfc_pub.current"), abs=1e-6
    )


def test_t12_household_counterparts_mirror_nas(syn):
    _, _, valid = syn
    hh = valid.entries.filter(pl.col("component") == "hh_cp")
    for inst in ("I_CURR", "I_DEPO", "I_EQTY", "I_MFUN", "I_GSEC", "I_SSAV", "I_INPE", "I_OTHR"):
        assert float(hh.filter(pl.col("col") == inst)["value"].sum()) == pytest.approx(
            _sum(valid, ref="K7a", row=inst), abs=1e-6
        ), inst
    assert float(hh.filter(pl.col("row") == "I_LOAN")["value"].sum()) == pytest.approx(_sum(valid, ref="K8a"), abs=1e-6)
    assert (hh["role"] == "free").all() and set(hh["confidence"]) == {"high"}
    # States' FSF deposits from households disappear (NAS has no such line); currency follows NAS
    assert hh.filter((pl.col("row") == "K_GSTA") & (pl.col("col") == "I_SSAV")).height == 0
    assert float(hh.filter(pl.col("row") == "K_RBI")["value"].sum()) == _nas("s5_3", "s5_3.currency.current")


def test_t13_row_counterparts_mirror_the_bop_lines(syn):
    _, deps, valid = syn
    k8b = pl.read_parquet(PATHS.entries("rest_of_world")).filter(pl.col("ref") == "K8b")
    row_cp = valid.entries.filter(pl.col("component").str.starts_with("row_cp_"))
    sat = deps.row_sat
    unalloc = set(sat.filter(pl.col("counterpart") == W.UNALLOCATED)["line"].to_list())
    for r in k8b.iter_rows(named=True):
        inst = r["row"] if r["col"] == "K_ROW" else r["col"]
        if inst == "I_RESV" or r["component"] in unalloc:
            assert row_cp.filter(pl.col("component") == f"row_cp_{r['component']}").height == 0
            continue
        got = float(row_cp.filter(pl.col("component") == f"row_cp_{r['component']}")["value"].sum())
        assert got == pytest.approx(r["value"], abs=1e-4), r["component"]  # satellite parts stored to 6 decimals
    r14a = pl.read_parquet(PATHS.entries("rest_of_world")).filter(pl.col("ref") == "R14a")
    for r in r14a.iter_rows(named=True):
        acct = P.E_TO_K[r["col"]]
        got = _sum(valid, component=f"row_cp_{W.REINVESTED}", row=acct)
        assert got == pytest.approx(r["value"], abs=1e-6), acct


def test_t14_every_instrument_but_i_othr_clears_with_the_rest_of_world(syn):
    _, deps, valid = syn
    bal = CF._instrument_balance(valid.entries.to_dicts(), deps.entries)
    for inst, gap in bal.items():
        if inst != "I_OTHR":
            assert abs(gap) <= 0.01, (inst, gap)


def test_t16_k9_closes_every_domestic_capital_account(syn):
    ctx, deps, valid = syn
    own = valid.entries.select("row", "col", "value")
    allk = pl.concat([own, deps.entries.select("row", "col", "value")], how="vertical")
    k4 = _nas("s1_9", "s1_9.household_sector.current")
    for s in P.K_DOMESTIC:
        row = float(allk.filter((pl.col("row") == s) & (pl.col("col") != s))["value"].sum())
        col = float(allk.filter((pl.col("col") == s) & (pl.col("row") != s))["value"].sum())
        gap = row + (k4 if s == "K_HH" else 0.0) - col
        assert abs(gap) <= max(P.K9_MIN, 0.01), (s, gap)
    dec = valid.satellites["k9_decomposition"][1]
    for s in P.K_DOMESTIC:
        d = {r["item"]: r["value"] for r in dec.filter(pl.col("account") == s).iter_rows(named=True)}
        terms = sum(v for k, v in d.items() if k.startswith("term:"))
        assert terms == pytest.approx(d["k9"], abs=1e-3), s
        assert d["pos"] + d["neg"] == pytest.approx(d["k9"], abs=1e-3), s
    k9 = _e(valid, ref="K9")
    assert set(k9["row"]) == {"I_OTHR"} and set(k9["component"]) <= {"residual_pos", "residual_neg"}
    assert (k9.filter(pl.col("component") == "residual_pos")["value"] > 0).all()
    assert (k9.filter(pl.col("component") == "residual_neg")["value"] < 0).all()


def _inputs(rec: dict) -> set[str]:
    ins = rec["inputs"]
    return set(ins.split(",")) if isinstance(ins, str) else set(ins or [])


def test_k9_pair_is_the_sum_of_the_published_pair_terms(syn):
    """Verification V-CF-2: residual_pos / residual_neg are the sums of the positive / negative `pair:*` rows of
    k9_decomposition, which regroup the exact `term:*` decomposition (RoW as one term; household and domestic
    layers combined per instrument); the K9 record states the grouping and that it is a weight choice."""
    _, _, valid = syn
    dec = valid.satellites["k9_decomposition"][1]
    k9 = _e(valid, ref="K9")
    for s in P.K_DOMESTIC:
        d = {r["item"]: r["value"] for r in dec.filter(pl.col("account") == s).iter_rows(named=True)}
        pair = {k: v for k, v in d.items() if k.startswith("pair:")}
        assert sum(pair.values()) == pytest.approx(d["k9"], abs=1e-3), s
        assert sum(v for v in pair.values() if v > 0) == pytest.approx(d["pos"], abs=1e-6), s
        assert sum(v for v in pair.values() if v < 0) == pytest.approx(d["neg"], abs=1e-6), s
        for t in ("nas_vs_fsf", "row_counterparty", "fsf_unwritten"):
            assert pair[f"pair:{t}"] == pytest.approx(d[f"term:{t}"], abs=1e-9), (s, t)
        hh_dom = sum(v for k, v in pair.items() if k.startswith("pair:hh_dom:"))
        dom = sum(v for k, v in d.items() if k.startswith("term:fsf_reconciliation:"))
        assert hh_dom == pytest.approx(dom + d["term:hh_counterparty"], abs=1e-3), s
        got = {r["component"]: r["value"] for r in k9.filter(pl.col("col") == s).iter_rows(named=True)}
        if len(got) == 2:
            assert got["residual_pos"] == pytest.approx(d["pos"], abs=1e-3), s
            assert got["residual_neg"] == pytest.approx(d["neg"], abs=1e-3), s
    rec = valid.provenance.filter(pl.col("prov_id") == k9["prov_id"][0]).row(0, named=True)
    assert "pair:*" in rec["method"] and "weight choice" in rec["method"]


def test_gg_gfcf_key_puts_statutory_bodies_in_the_centre(syn):
    """Verification V-CF-1 follow-up (government V-GOV-7, its A-K6-4: statutory bodies and development
    authorities are inside G_CEN): their IGAS-2 capital grants join the Centre's GG GFCF key, like central
    autonomous bodies' (D2-8). Key recomputed from clean Finance Accounts, IGAS-2 and RBI State Finances."""
    _, _, valid = syn

    def fa(sid: str) -> float:
        return _v("union_fiscal", "union_fiscal_fa_expenditure", sid)

    def gia(sid: str) -> float:
        return _v("union_fiscal", "union_fiscal_fa_gia", f"gia.cash.{sid}.capital_assets")

    centre = (
        fa("fa9.section.expenditure_heads_capital_account")
        - sum(fa(f"fa9.{h}.total") for h in P.UNION_NON_GG_HEADS)
        + gia("autonomous_bodies")
        + gia("statutory_bodies_and_development_authorities")
    )
    states = _v(
        "state_fiscal",
        "state_fiscal_rbi_sf_appendices",
        "app4.total_capital_disbursements.i-total_capital_outlay.in.all_states_uts.actuals",
    ) + gia("urban_local_bodies")
    key = {r["item"]: r["value"] for r in valid.satellites["gg_gfcf_key"][1].iter_rows(named=True)}
    assert key["centre_key"] == pytest.approx(centre, abs=1e-3)
    assert key["states_key"] == pytest.approx(states, abs=1e-3)
    assert key["centre_statutory"] == pytest.approx(gia("statutory_bodies_and_development_authorities"), abs=1e-6)
    i1a = _e(valid, ref="I1a")
    cen = float(i1a.filter(pl.col("col") == "K_GCEN")["value"].sum())
    sta = float(i1a.filter(pl.col("col") == "K_GSTA")["value"].sum())
    assert cen / (cen + sta) == pytest.approx(centre / (centre + states), abs=1e-9)


def test_gsec_issuance_targets_cite_every_input(syn):
    """Verification V-CF-3: cf.k8.gsec_centre / gsec_states replace FSF's household and RoW holders with this
    block's NAS 5.3 and rest_of_world postings, so their records are estimated and cite the NAS 5.3 G-sec
    series, the FSF F3 statements used (the Centre's also uses the States' F3 to households), the household
    posting record and rest_of_world's FPI G-sec line."""
    _, deps, valid = syn
    prov = {r["prov_id"]: r for r in valid.provenance.iter_rows(named=True)}
    nas = _clean("mospi_nas_2026", "mospi_nas_2026_s5_3").filter(
        (pl.col("series_id") == "s5_3.investment_in_government_securities.current") & (pl.col("period") == YEAR)
    )
    fsf = _clean("rbi_financial_accounts", "rbi_financial_accounts_fsf_balance_sheets").filter(
        (pl.col("period") == YEAR)
        & (pl.col("dim_other") == "measure=transaction")
        & (pl.col("instrument") == "f3")
        & (pl.col("side") == "liabilities")
    )
    f3 = {g: set(fsf.filter(pl.col("institution") == g)["prov_id"].to_list()) for g in P.GG_CODES}
    for gov, sub, acct in (("centre", "gg_cen", "K_GCEN"), ("states", "gg_sta", "K_GSTA")):
        c = valid.constraints.filter(pl.col("constraint_id") == f"cf.k8.gsec_{gov}")
        rec = prov[c["prov_id"][0]]
        ins = _inputs(rec)
        assert rec["status"] == "estimated", gov
        assert nas["prov_id"][0] in ins and f3[sub] <= ins and f3["gg_sta"] <= ins, gov
        assert set(_e(valid, ref="K7b", component="hh_cp", row=acct, col="I_GSEC")["prov_id"].to_list()) <= ins
        row = deps.row_sat.filter((pl.col("instrument") == "I_GSEC") & (pl.col("counterpart") == acct))
        assert set(row["prov_id"].to_list()) <= ins, gov


def test_fsf_cells_no_reconciliation_step_reads_are_listed(syn):
    """Verification V-CF-4: every non-household FSF insurance/pension cell (f6x) and every F52 liability outside
    the MF sector is listed by fsf.unread_cells (logged at build) with its fate. Only the insurers', PF and
    government pension liabilities are replaced by NAS 5.3 household lines; the rest (insurers' non-life
    technical reserves f61 first) are not written and fall into K9. Listing recomputed from clean FSF."""
    ctx, _, _ = syn
    cells = F.unread_cells(F.reports(ctx.rows(P.FSF, vintage=P.LATEST)))
    liab = pl.col("side") == "liabilities"
    mf_liab = (pl.col("instrument") == "f52") & liab & (pl.col("institution") != "fc_ofc_mf")
    df = _clean("rbi_financial_accounts", "rbi_financial_accounts_fsf_balance_sheets").filter(
        (pl.col("period") == YEAR)
        & (pl.col("dim_other") == "measure=transaction")
        & (pl.col("counterparty") == "all")
        & pl.col("institution").is_in([s for s in P.SUB_ACCOUNT if s != "hh"])
        & (pl.col("instrument").is_in(list(P.INPE_INSTRUMENTS)) | mf_liab)
        & (pl.col("value") != 0)
    )
    want = {(r["institution"], r["side"], r["instrument"]): r["value"] for r in df.iter_rows(named=True)}
    got: dict[tuple[str, str, str], float] = {}
    for c in cells:
        k = (c["sub"], c["side"], c["fsf_instr"])
        got[k] = got.get(k, 0.0) + c["value"]
    assert set(got) == set(want)
    for k, v in want.items():
        assert got[k] == pytest.approx(v, abs=1e-6), k
    fate = {(c["sub"], c["side"], c["fsf_instr"]): c["fate"] for c in cells}
    assert fate[("fc_ofc_icpf_ins", "liabilities", "f61")] == "k9"
    assert {k for k, f in fate.items() if f != "k9"} == {(s, "liabilities", i) for s, i in P.INPE_NAS_REPLACED}


def test_t18_rbi_surplus_timing(syn):
    _, _, valid = syn
    k9b = _v(
        "rbi_banking_corporate", "rbi_banking_corporate_rbi_surplus_timing", "k9b.change_in_surplus_payable.current"
    )
    assert _sum(valid, ref="K9b", row="K_RBI") == pytest.approx(k9b, abs=0.01)
    assert _sum(valid, ref="K9b", col="K_GCEN") == pytest.approx(k9b, abs=0.01)
    pair = _fsf("fsf.fc_rbi.liabilities.transaction.f89.gg_cen.current")
    # RBI's other payables are only the pair: K9b + the fsf_f89 remainder = FSF
    rbi_f89 = _sum(valid, ref="K8", row="K_RBI", col="I_OTHR", component="fsf_f89")
    assert k9b + rbi_f89 == pytest.approx(pair, abs=0.01)
    assert set(_e(valid, ref="K9b")["role"]) == {"anchored"}


def test_t19_centre_state_loans(syn):
    _, deps, valid = syn
    fsf = _fsf("fsf.gg_cen.assets.transaction.f4.gg_sta.current")
    afs = (
        _v("union_fiscal", "union_fiscal_afs", "afs.cfi_cap_disbursements.7601")
        - _v("union_fiscal", "union_fiscal_afs", "afs.cfi_cap_receipts.state_governments")
        - _v("union_fiscal", "union_fiscal_afs", "afs.cfi_cap_receipts.union_territories_with_legislature")
    )
    assert fsf == pytest.approx(afs, abs=0.1)
    fw = valid.satellites["s4_fwtw_sam"][1]
    pair = float(fw.filter(pl.col("series_id") == "fwtw.i_loan.k_gcen.k_gsta")["value"][0])
    k8e = float(deps.entries.filter((pl.col("ref") == "K8e") & (pl.col("row") == "I_LOAN"))["value"].sum())
    assert pair + k8e == pytest.approx(fsf, abs=1e-6)


def test_t20_currency(syn):
    _, _, valid = syn
    got = float(valid.entries.filter((pl.col("row") == "K_RBI") & (pl.col("col") == "I_CURR"))["value"].sum())
    want = (
        _fsf("fsf.fc_rbi.liabilities.transaction.f21.all.current")
        - _fsf("fsf.fc_rbi.liabilities.transaction.f21.hh.current")
        + _nas("s5_3", "s5_3.currency.current")
    )
    assert got == pytest.approx(want, abs=0.01)


def test_t21_hdfc_merger_memo(syn):
    _, _, valid = syn
    memo = {r["series_id"]: r["value"] for r in valid.satellites["s4_hdfc_merger_memo"][1].iter_rows(named=True)}
    rtp = pl.read_parquet(LAYOUT.clean / "rbi_banking_corporate" / "rbi_banking_corporate_rtp_banks.parquet").filter(
        (pl.col("vintage") == P.RTP_VINTAGE) & (pl.col("period") == "2024-03-31")
    )

    def r(s: str) -> float:
        return float(rtp.filter(pl.col("series_id") == f"rtp.scb_bs.{s}.scb.current")["value"][0])

    assert memo["rtp.scb.merger_effect.loans"] == r("loans_advances") - r("loans_advances_excl_merger")
    assert memo["rtp.scb.merger_effect.deposits"] == r("deposits") - r("deposits_excl_merger")


def test_t22_structural_guards(syn):
    _, _, valid = syn
    e = valid.entries
    assert (
        e.filter(
            pl.col("row").is_in(["K_ROW", "R_ROW", "I_RESV"]) | pl.col("col").is_in(["K_ROW", "R_ROW", "I_RESV"])
        ).height
        == 0
    )
    assert e.filter(pl.col("value") == 0).height == 0
    fsf_items = e.filter(~pl.col("component").str.starts_with("row_cp_"))  # BoP line names may say "other"
    assert fsf_items.filter(pl.col("component").str.contains("other|nec")).height == 0  # FSF VIII/IX not written
    assert e.filter((pl.col("row") == "K_RBI") & (pl.col("col") == "I_INPE")).height == 0  # RBI F6 not written
    assert e["bop_function"].null_count() == e.height


def test_t23_roles_and_statuses(syn):
    _, _, valid = syn
    e = valid.entries
    for ref in ("K7a", "K8a", "K1", "I2", "I2a", "D3"):
        assert set(_e(valid, ref=ref)["role"]) == {"fixed"}, ref
    k9 = _e(valid, ref="K9")
    assert set(k9["role"]) == {"free"} and set(k9["confidence"]) == {"low"}
    cp = e.filter(pl.col("component").str.starts_with("row_cp_") | (pl.col("component") == "hh_cp"))
    assert set(cp["role"]) == {"free"} and set(cp["confidence"]) == {"high"}
    anchored = e.filter(pl.col("role") == "anchored")
    assert set(anchored["status"]) == {"derived"}
    prov = valid.provenance
    est = prov.filter(pl.col("status") == "estimated")
    assert est.height > 0 and est["method"].str.len_chars().min() > 40


def test_t24_k9_sensitivity_table(syn):
    """Plan T24 (report): each variant changes one rule; the household layer and the sum over sectors do not move."""
    _, _, valid = syn
    sens = valid.satellites["k9_sensitivity"][1]
    k9 = sens.filter(pl.col("item") == "k9")
    assert set(k9["variant"]) == {"base", "equity_issuer_control", "insurer_strip_off", "d3_all_k_nfpu"}
    dec = valid.satellites["k9_decomposition"][1].filter(pl.col("item") == "k9")
    base = dict(zip(dec["account"], dec["value"], strict=True))
    by = {
        v: dict(zip(g["account"], g["value"], strict=True))
        for v, g in ((v, k9.filter(pl.col("variant") == v)) for v in sorted(set(k9["variant"])))
    }
    assert by["base"] == pytest.approx(base, abs=1e-6)
    for v, d in by.items():
        assert set(d) == set(P.K_DOMESTIC), v
        assert sum(d.values()) == pytest.approx(sum(base.values()), abs=1e-3), v
        assert d["K_HH"] == pytest.approx(base["K_HH"], abs=1e-6), v  # NAS 5.3 layer is untouched
    # D3 variant: the remainder D3 - I2a (from clean data) leaves the other corporate accounts for K_NFPU
    rem = _v("mospi_nas_2026", "mospi_nas_2026_derived_residuals", "derived.si_errors_omissions.current") - (
        _v("io_tables", "io_tables_sut_use", "use.valuables.total.current")
        - _nas("s1_9", "s1_9.saving_in_the_form_of_gold_and_silver_ornaments.current")
    )
    d3v = by["d3_all_k_nfpu"]
    for s in P.K_DOMESTIC:
        d3_s = _sum(valid, ref="D3", row=s) if s != "K_HH" else 0.0
        expect = base[s] - d3_s + (rem if s == "K_NFPU" else 0.0)
        assert d3v[s] == pytest.approx(expect, abs=1e-3), s
    # the insurer strip moves insurers' equity purchases only: the change lands on K_INSP (holder) and issuers
    strip = by["insurer_strip_off"]
    assert strip["K_INSP"] < base["K_INSP"]
    assert strip["K_GSTA"] == pytest.approx(base["K_GSTA"], abs=1e-6)
    assert strip["K_RBI"] == pytest.approx(base["K_RBI"], abs=1e-6)
    ch = sens.filter(pl.col("item") == "change_from_base")
    for r in ch.iter_rows(named=True):
        assert r["value"] == pytest.approx(by[r["variant"]][r["account"]] - base[r["account"]], abs=1e-6)


def test_t25_household_wealth(syn):
    _, _, valid = syn
    if "s5_hh_wealth" not in valid.satellites:
        pytest.skip("households hh_keys without AIDIS keys")
    s5 = valid.satellites["s5_hh_wealth"][1]
    t52 = _clean("rbi_financial_accounts", "rbi_financial_accounts_hh_finsav_52ab")

    def stock(s: str) -> float:
        return float(t52.filter((pl.col("series_id") == s) & (pl.col("period") == "2024-03-31"))["value"][0])

    fa = s5.filter(pl.col("measure") == "financial_assets")
    assert float(fa["value"].sum()) == pytest.approx(stock("t52b.fa.current"), abs=1.0)
    debt = s5.filter(pl.col("measure") == "institutional_debt")
    assert float(debt["value"].sum()) == pytest.approx(stock("t52b.fl.current"), abs=1.0)
    keys = pl.read_parquet(PATHS.satellites("households") / "hh_keys.parquet").filter(
        (pl.col("key") == "aidis_fin_assets") & (pl.col("measure") == "share")
    )
    share = dict(zip(keys["household_group"], keys["value"], strict=True))
    for r in fa.iter_rows(named=True):
        assert r["value"] / stock("t52b.fa.current") == pytest.approx(share[r["household_group"]], abs=1e-5)


def test_constraints_do_not_redeclare_production_targets(syn):
    """XR-15: production's gfcf.* / valuables.* are not re-declared (their tolerance is Rs 1 per SUT cell)."""
    _, _, valid = syn
    ids = set(valid.constraints["constraint_id"].to_list())
    assert "cf.i1a.gfcf.total" not in ids and "cf.valuables.total" not in ids
    assert {"cf.i1a.gfcf.fc_public", "cf.i1a.gfcf.fc_private", "cf.k4.hh_saving", "cf.i3a.cis.total"} <= ids


# ---------------------------------------------------------------------------------------------------
# the built block (once every DEPENDS block is built)
# ---------------------------------------------------------------------------------------------------

needs_build = pytest.mark.skipif(
    not (ALL_DEPS_BUILT and PATHS.built(CF.BLOCK)),
    reason="capital_financial or a DEPENDS block is not built (run `uv run python -m pipeline sam capital_financial`)",
)


@pytest.fixture(scope="module")
def fresh():
    r, valid = build_block_module(CF, LAYOUT, write=False)
    assert r.ok, r.message
    return valid


@needs_build
def test_built_outputs_equal_a_fresh_build(fresh):
    built = pl.read_parquet(PATHS.entries(CF.BLOCK))
    want = canonical_floats(fresh.entries, {"value": 6, "tol_rel": None}).sort(list(spec.ENTRY_KEY))
    assert built.drop("block").equals(want)
    cons = pl.read_parquet(PATHS.constraints(CF.BLOCK))
    assert cons.drop("block").equals(canonical_floats(fresh.constraints).sort("constraint_id"))
    assert pl.read_parquet(PATHS.provenance(CF.BLOCK)).equals(fresh.provenance.sort("prov_id"))


@needs_build
def test_built_checks_pass(fresh):
    failed = fresh.checks.filter(~pl.col("ok"))
    assert failed.height == 0, failed


@needs_build
def test_built_k_accounts_close_and_markets_clear():
    own = pl.read_parquet(PATHS.entries(CF.BLOCK)).select("row", "col", "value")
    dep = pl.concat([pl.read_parquet(PATHS.entries(b)).select("row", "col", "value") for b in CF.DEPENDS])
    allk = pl.concat([own, dep], how="vertical")
    k4 = _nas("s1_9", "s1_9.household_sector.current")
    for s in P.K_DOMESTIC:
        row = float(allk.filter((pl.col("row") == s) & (pl.col("col") != s))["value"].sum())
        col = float(allk.filter((pl.col("col") == s) & (pl.col("row") != s))["value"].sum())
        assert abs(row + (k4 if s == "K_HH" else 0.0) - col) <= max(P.K9_MIN, 0.01), s
    for inst in ("I_CURR", "I_DEPO", "I_LOAN", "I_GSEC", "I_SSAV", "I_CBND", "I_EQTY", "I_MFUN", "I_INPE", "I_RESV"):
        gap = float(allk.filter(pl.col("row") == inst)["value"].sum()) - float(
            allk.filter(pl.col("col") == inst)["value"].sum()
        )
        assert abs(gap) <= 0.01, (inst, gap)
