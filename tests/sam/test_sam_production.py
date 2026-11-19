"""The production block: its built outputs validate, match a fresh rebuild, and add up to the SUT and
NAS 2026 totals. Every expected value is recomputed here from data/clean (polars), never typed in."""

from __future__ import annotations

import polars as pl
import pytest

from pipeline.core.io import canonical_floats
from pipeline.core.paths import Layout
from pipeline.sam import spec
from pipeline.sam.accounts import Accounts
from pipeline.sam.blocks import production
from pipeline.sam.framework import SamPaths, build_block_module

pytestmark = pytest.mark.sam

LAYOUT = Layout.default()
PATHS = SamPaths(LAYOUT)
YEAR = spec.YEAR


def _clean(unit: str, dataset: str) -> pl.DataFrame:
    df = pl.read_parquet(LAYOUT.clean / unit / f"{dataset}.parquet").filter(pl.col("period") == YEAR)
    latest = df["vintage"].max()
    return df.filter(pl.col("vintage") == latest)


@pytest.fixture(scope="module")
def built() -> pl.DataFrame:
    if not PATHS.built("production"):
        pytest.fail("production block not built: run `uv run python -m pipeline sam production`")
    return pl.read_parquet(PATHS.entries("production"))


@pytest.fixture(scope="module")
def cons() -> pl.DataFrame:
    return pl.read_parquet(PATHS.constraints("production"))


@pytest.fixture(scope="module")
def fresh():
    r, valid = build_block_module(production, LAYOUT, write=False)
    assert r.ok, r.message
    return valid


def test_built_outputs_equal_a_fresh_build(built, cons, fresh):
    """The files on disk are what the current code builds (no stale outputs)."""
    # tol_rel is written unrounded (12 significant digits; Wave A review F4), value to 6 decimals
    want = canonical_floats(fresh.entries, {"value": 6, "tol_rel": None}).sort(list(spec.ENTRY_KEY))
    assert built.drop("block").equals(want)
    assert cons.drop("block").equals(canonical_floats(fresh.constraints).sort("constraint_id"))
    prov = pl.read_parquet(PATHS.provenance("production"))
    assert prov.equals(fresh.provenance.sort("prov_id"))


def test_every_control_total_check_passes(fresh):
    failed = fresh.checks.filter(~pl.col("ok"))
    assert failed.height == 0, failed
    assert fresh.checks.height >= 30


def test_roles_statuses_and_refs(built):
    assert set(built["status"]) == {"official"}
    roles = dict(built.group_by("ref", maintain_order=True).agg(pl.col("role").unique().sort()).iter_rows())
    for ref in ("P1", "P2", "P3", "P4", "P5", "P6", "I3"):
        assert roles[ref] == ["anchored"], ref
    for ref in ("P8", "P9", "P10", "D4"):
        assert roles[ref] == ["fixed"], ref
    assert built.filter((pl.col("value") == 0) & (pl.col("ref") != "D4")).height == 0
    d4 = built.filter(pl.col("ref") == "D4")
    assert d4.height == 34 and (d4["value"] == 0).all() and set(d4["col"]) == {"X_DISC"}
    # margins: only trade and transport supply margin services
    assert set(built.filter(pl.col("ref") == "P3")["row"]) == {"C_TRAD", "C_TRNS"}


def _sut(dataset: str, item: str) -> pl.DataFrame:
    df = _clean("io_tables", dataset).filter(pl.col("item_code") == item)
    return df.filter(pl.col("product").str.starts_with("sut_p") | pl.col("industry").str.starts_with("sut_i"))


@pytest.mark.parametrize(
    "ref,dataset,item,sign",
    [
        ("P1", "io_tables_sut_supply", "output", 1),
        ("P2", "io_tables_sut_use", "ic", 1),
        ("P5", "io_tables_sut_use", "exports", 1),
        ("P6", "io_tables_sut_supply", "imports_after_cif", 1),
        ("P8", "io_tables_sut_supply", "import_duty", 1),
        ("P9", "io_tables_sut_supply", "product_subsidies", 1),
        ("P10", "io_tables_sut_va", "net_production_taxes", 1),
        ("I3", "io_tables_sut_use", "cii", 1),
    ],
)
def test_entry_totals_equal_the_sut_cells(built, ref, dataset, item, sign):
    sut = _sut(dataset, item)
    if item in ("output", "ic"):
        sut = sut.filter(pl.col("product").str.starts_with("sut_p") & pl.col("industry").str.starts_with("sut_i"))
    got = built.filter(pl.col("ref") == ref)["value"].sum()
    assert got == pytest.approx(sign * sut["value"].sum(), abs=1e-4)


def test_margins_net_to_the_ttm_column(built):
    ttm = _sut("io_tables_sut_supply", "ttm")["value"]
    p3 = built.filter(pl.col("ref") == "P3")["value"].sum()
    p4 = built.filter(pl.col("ref") == "P4")["value"].sum()
    assert p3 == pytest.approx(-ttm.filter(ttm < 0).sum(), abs=1e-4)
    assert p4 == pytest.approx(ttm.filter(ttm > 0).sum(), abs=1e-4)
    assert abs(p4 - p3) < 1.0  # the TTM column sums to ~0 (SUT rounding)


@pytest.mark.parametrize(
    "stem,dataset,item",
    [
        ("pfce", "io_tables_sut_use", "pfce"),
        ("gfce", "io_tables_sut_use", "gfce"),
        ("gfcf", "io_tables_sut_use", "gfcf"),
        ("valuables", "io_tables_sut_use", "valuables"),
        ("product_taxes", "io_tables_sut_supply", "product_taxes"),
        ("ce", "io_tables_sut_va", "ce"),
    ],
)
def test_constraint_targets_equal_the_sut_vectors(cons, stem, dataset, item):
    c = cons.filter(pl.col("constraint_id").str.starts_with(stem + "."))
    assert c.height == 34
    assert c["target"].sum() == pytest.approx(_sut(dataset, item)["value"].sum(), abs=1e-4)


def test_nas_totals(built, cons):
    """GDP, PFCE, IC, exports, imports, product taxes and subsidies against NAS 2026 (read from clean)."""
    nas = _clean("mospi_nas_2026", "mospi_nas_2026_s1_1")
    n71 = _clean("mospi_nas_2026", "mospi_nas_2026_s7_1")

    def v(df, sid):
        return df.filter(pl.col("series_id") == sid)["value"].item()

    def s(ref):
        return built.filter(pl.col("ref") == ref)["value"].sum()

    def t(stem):
        return cons.filter(pl.col("constraint_id").str.starts_with(stem + "."))["target"].sum()

    tol = 5.0  # Rs crore (SUT rounding; RECONCILIATION.md finds <= 3)
    gdp = s("P1") - s("P2") + t("product_taxes") + s("P8") + s("P9")
    assert gdp == pytest.approx(v(nas, "s1_1.gdp.current"), abs=tol)
    assert t("pfce") == pytest.approx(v(nas, "s1_1.pfce.current"), abs=tol)
    assert s("P2") == pytest.approx(v(n71, "s7_1.total.ic.current"), abs=tol)
    assert s("P5") == pytest.approx(v(nas, "s1_1.exports.current"), abs=tol)
    assert s("P6") == pytest.approx(v(nas, "s1_1.imports.current"), abs=tol)
    assert t("product_taxes") + s("P8") == pytest.approx(v(nas, "s1_1.taxes_on_products.current"), abs=tol)
    assert -s("P9") == pytest.approx(v(nas, "s1_1.subsidies_on_products.current"), abs=tol)


def test_production_accounts_close_up_to_sut_rounding(built, cons):
    """With the constraint targets standing in for the other blocks' entries, every commodity, activity and
    the margin account balances within the rounding allowance the block declares."""
    acc = Accounts.load()
    e = built.select("row", "col", "value")
    targets = []
    for r in cons.iter_rows(named=True):
        if r["target"] == 0:
            continue
        rows, cols = r["rows"].split(","), r["cols"].split(",")
        targets.append({"row": rows[0], "col": cols[0], "value": r["target"]})  # the total on one representative cell
    allc = pl.concat([e, pl.DataFrame(targets, schema=e.schema)])
    rt = allc.group_by("row", maintain_order=True).agg(pl.col("value").sum().alias("r")).rename({"row": "a"})
    ct = allc.group_by("col", maintain_order=True).agg(pl.col("value").sum().alias("c")).rename({"col": "a"})
    j = (
        rt.join(ct, on="a", how="full", coalesce=True)
        .fill_null(0.0)
        .with_columns((pl.col("r") - pl.col("c")).alias("d"))
    )
    for grp in ("ACT", "COM", "MRG"):
        sub = j.filter(pl.col("a").is_in(acc.in_group(grp)))
        assert sub["d"].abs().max() < 5.0, sub.sort(pl.col("d").abs(), descending=True).head(5)


def test_satellite_memo(fresh):
    _, df = fresh.satellites["sut_memo"]
    cif = df.filter(pl.col("item") == "cif_adjustment")["value"].sum()
    memo = df.filter(pl.col("series_id") == "memo.cif_adj.cif")["value"].item()
    assert cif == pytest.approx(-memo, abs=1e-4)  # the CIF adjustment by commodity offsets the memo row


def test_production_prior_closed_with_pseudo_entries_balances(built, cons):
    """Wave A review V-2 smoke test: production's 1,064 entries (962 anchored at Rs 1 crore per SUT cell) with
    all 238 constraints, closed by one free pseudo-entry per non-zero constraint target and free closing
    entries through I_OTHR (what the other blocks will supply), must balance to a certified optimum with
    no slack (the interior-point solve returned optimal_inaccurate on exactly this).

    The duality gap is tested here in exact form, not with the certificate's f - q (Phase 3 review V4-01). This
    synthetic prior is closed by construction, so its optimum sits at the prior: f = sum c (z ln z - z + 1) is
    about 2e-5 while sum c is about 1.8e9. The certificate's relative gap |f - q| / max(1, |f|) is then an
    absolute test at 1e-8 on two sums whose rounding floor is about eps * sum c = 4e-7, and it reports 2e-8 to
    4e-8 of pure cancellation noise. Through the identity f - q = -lambda.res - sum_k mu_k (s_k - bound_k), which
    involves no large terms, the same iterate's gap is about 1e-12 (a log1p form summed with math.fsum gives the
    same). The certified run is unaffected: its f is about 1.1e5 and its recorded gap 3.15e-13. Every other
    certificate criterion is required exactly as kkt_certificate states it. The closing entries are summed with
    math.fsum, so the input does not depend on the order of polars' parallel group sums (it did, in the last
    bits, and the solver then took 5 or 18 steps)."""
    import math

    import numpy as np

    from pipeline.sam import balance as B
    from pipeline.sam.balance import cross_entropy, problem_from_frames

    acc = Accounts.load()
    cols = ["row", "col", "ref", "component", "value", "role", "tol_rel", "confidence"]
    ent = built.select(cols)
    pseudo = []
    for c in cons.filter(pl.col("target") != 0).iter_rows(named=True):
        rows, cs = c["rows"].split(","), c["cols"].split(",")
        # the target's counterpart: a free entry on the first cell of the selection that the block leaves open
        r, k = (rows[0], cs[0]) if c["ref"] not in ("I1", "I2") else (rows[0], "K_NFPR" if c["ref"] == "I1" else "K_HH")
        ref = {"I1": "I1a", "I2": "I2a"}.get(c["ref"], c["ref"] + "_pseudo")
        pseudo.append({"row": r, "col": k, "ref": ref, "component": "pseudo", "value": c["target"], "role": "free",
                       "tol_rel": None, "confidence": "medium"})  # fmt: skip
    base = pl.concat([ent, pl.DataFrame(pseudo, schema=ent.schema)])
    flows: dict[str, list[float]] = {}  # account -> row values and negated column values (exactly rounded sum)
    for r, k, v in base.select("row", "col", "value").iter_rows():
        flows.setdefault(r, []).append(v)
        flows.setdefault(k, []).append(-v)
    close = [
        {"row": "I_OTHR", "col": a, "ref": "CLOSE", "component": "pseudo", "value": d, "role": "free",
         "tol_rel": None, "confidence": "low"}
        for a in sorted(flows)
        if acc.group(a) not in ("ACT", "COM", "MRG") and a != "I_OTHR" and abs(d := math.fsum(flows[a])) > 1e-9
    ]  # fmt: skip
    df = pl.concat([base, pl.DataFrame(close, schema=ent.schema)])
    p = problem_from_frames(df, cons, acc.codes)
    s = cross_entropy(p)
    assert s.status == "optimal" and s.solver == "NEWTON", s.messages
    assert not s.balance_slack and not s.polish.get("failed"), s.messages
    assert s.phase1["total_slack"] == 0 and not s.band_violation and not s.anchor_violation
    assert s.max_imbalance <= spec.BALANCE_TOL

    # the certificate, criterion by criterion, at the iterate cross_entropy certified (same deterministic path)
    core = B._core(p)
    B._widen(core, B._phase1(core))
    d = B._dual_newton_path(core)
    assert d.converged and d.iterations == s.iterations
    cert = B.kkt_certificate(core, d.z, d.y)
    assert {k: v for k, v in cert.items() if k not in ("duality_gap_rel", "ok")} == {
        k: v for k, v in s.certificate.items() if k not in ("duality_gap_rel", "ok")
    }
    kt = cert["tolerance"]
    assert cert["stationarity"] <= kt and cert["sign_at_upper_bounds"] <= kt and cert["sign_at_lower_bounds"] <= kt
    assert cert["non_complementary_bands"] == 0 and cert["entries_forced_to_zero"] == 0
    m = core.m
    gz = core.G @ d.z
    res = gz[:m] + core.b[np.flatnonzero(core.eq_of >= 0)]
    tb, tk = B._tolerances(core, d.z)
    bs = gz[m:]
    assert np.all(np.abs(res) <= tb) and np.all(np.maximum(bs - core.band_hi, core.band_lo - bs) <= tk)
    assert cert["max_box_violation"] <= float(np.max(tb, initial=spec.NEWTON_TOL_ABS))
    # the duality gap without cancellation: f - q = -lambda.res - sum_k mu_k (s_k - bound_k)
    nu = d.y[m:].copy()
    nu[~(((nu > 0) & (np.abs(bs - core.band_hi) <= tk)) | ((nu < 0) & (np.abs(bs - core.band_lo) <= tk)))] = 0.0
    bound = np.where(nu > 0, core.band_hi, np.where(nu < 0, core.band_lo, 0.0))
    gap = -math.fsum(d.y[:m] * res) - math.fsum(np.where(nu != 0, nu * (bs - bound), 0.0))
    f = math.fsum(core.w * np.abs(core.a) * (d.z * np.log1p(d.z - 1.0) - (d.z - 1.0)))
    assert abs(gap) / max(1.0, abs(f)) <= B.CERT_GAP
    # and the certificate's own figure is within its rounding floor (so if it fails, it fails on noise only)
    floor = 64 * np.finfo(np.float64).eps * float(np.sum(core.w * np.abs(core.a)))
    assert cert["duality_gap_rel"] <= B.CERT_GAP or cert["duality_gap_rel"] * max(1.0, abs(f)) <= floor
