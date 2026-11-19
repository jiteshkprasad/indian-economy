"""The closure block (K4a, D1, pre-balancing diagnostics): plan docs/phase2/plans/closure.md s.7.

Three kinds of test:
- pure data tests on clean NAS 2026 (the published D1 identities, the required-flow identity T8): run now;
- the block on a synthetic set of the eight dependency blocks written into a scratch SAM folder, with real
  clean data (every official number the block reads, and every D2/D3 value the fakes write, is read from
  data/clean in the test): the residual identity, the D1 key and total, the whitelist and the diagnostics;
- the real built outputs (T1, T3, T4, T5, T11, T12, T13, T14): skip until `sam closure` has run.
Post-balancing tests (T2, T6, T7, T9, T10) are in test_sam_identities.py.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import polars as pl
import pytest

from pipeline.core import io
from pipeline.core.io import canonical_floats
from pipeline.core.paths import Layout
from pipeline.sam import spec
from pipeline.sam.accounts import Accounts
from pipeline.sam.assemble import diagnostics
from pipeline.sam.blocks import closure
from pipeline.sam.framework import (
    BlockContext,
    SamError,
    SamPaths,
    Satellite,
    build_block_module,
    constraint,
    entry,
    referenced_provenance,
    validate_constraints,
    validate_entries,
    validate_satellite,
)

pytestmark = pytest.mark.sam

LAYOUT = Layout.default()
PATHS = SamPaths(LAYOUT)
YEAR = spec.YEAR
ACC = Accounts.load()
HH = ACC.in_group("HH")


def _clean(dataset: str, sid: str, unit: str = "mospi_nas_2026", period: str = YEAR) -> float:
    df = pl.read_parquet(LAYOUT.clean / unit / f"{dataset}.parquet")
    df = df.filter((pl.col("series_id") == sid) & (pl.col("period") == period))
    df = df.filter(pl.col("vintage") == df["vintage"].max())
    assert df.height == 1, (dataset, sid, df)
    return float(df["value"][0])


def _nas(ds: str, sid: str) -> float:
    return _clean(f"mospi_nas_2026_{ds}", sid)


# =============================================================================================
# pure data tests (no SAM needed)
# =============================================================================================


def test_published_d1_identities():
    """T4 (data part): the published household residual = 1.14 GDI - FCE - saving = 1.1 GNDI - PFCE - GFCE - saving."""
    d1 = _nas("derived_residuals", "derived.household_residual.current")
    a = (
        _nas("s1_14", "s1_14.households_npish.gross_disposable_income.current")
        - _nas("s1_14", "s1_14.households_npish.final_consumption_expenditure.current")
        - _nas("s1_14", "s1_14.households_npish.gross_savings.current")
    )
    b = (
        _nas("s1_1", "s1_1.gndi.current")
        - _nas("s1_1", "s1_1.pfce.current")
        - _nas("s1_1", "s1_1.gfce.current")
        - _nas("s1_1", "s1_1.gross_saving.current")
    )
    assert a == pytest.approx(d1, abs=0.01) and b == pytest.approx(d1, abs=0.01)


def test_household_saving_sources_agree():
    """T2 (data part): NAS 1.9 = 1.14 = 5.3 household saving (the K4 target)."""
    k = _nas("s1_9", "s1_9.household_sector.current")
    assert _nas("s1_14", "s1_14.households_npish.gross_savings.current") == pytest.approx(k, abs=K4_TOL)
    assert _nas("s5_3", "s5_3.household_saving_1_2_3_4.current") == pytest.approx(k, abs=K4_TOL)


K4_TOL = closure.K4_TOL


class _Ctx:
    """A stand-in for BlockContext.value over the real clean data (for closure.required_flows)."""

    def __init__(self) -> None:
        self.ctx = BlockContext(block="closure", refs=("K4a", "D1"), depends=(), layout=LAYOUT)

    def value(self, *a, **k):
        return self.ctx.value(*a, **k)


def test_required_flows_add_up_to_the_row_net():
    """T8: the six institutional requirements (table 2.4-C) add up to NAS 6.1's net property income and current
    transfers from the RoW (a pure identity of the published accounts)."""
    req, pids = closure.required_flows(_Ctx())
    assert req["DOMESTIC"]["required_net"] == pytest.approx(req["ROW_NET"]["required_net"], abs=0.01)
    row = (
        _nas("s6_1", "s6_1.property_and_entrepreneurial_income_from_rest_of_the_world.current")
        - _nas("s6_1", "s6_1.property_and_entrepreneurial_income_to_the_rest_of_the_world.current")
        + _nas("s6_1", "s6_1.other_current_transfers_to_resident_sectors_other_than_gener.current")
        - _nas("s6_1", "s6_1.other_current_transfers_by_resident_sectors_other_than_gener.current")
    )
    assert req["ROW_NET"]["required_net"] == pytest.approx(row, abs=1e-6)
    # households: GDI - CE receivable - gross OS/MI (7.1C OS/MI + CFC)
    hh = (
        _nas("s1_14", "s1_14.households_npish.gross_disposable_income.current")
        - _nas("derived_residuals", "derived.ce_receivable_by_residents.current")
        - _nas("s7_1c", "s7_1c.total.os_mi.current")
        - _nas("s7_1c", "s7_1c.total.cfc.current")
    )
    assert req["HH"]["required_net"] == pytest.approx(hh, abs=1e-6)
    # FC gross OS = public + private financial OS and CFC (= factors' FC GOS constraint)
    fc_gos = sum(
        _nas(s, f"{s}.financial.{m}.current") for s in ("s7_1a", "s7_1b") for m in ("os", "cfc")
    )  # fmt: skip
    assert req["FC"]["primary_income"] == pytest.approx(fc_gos, abs=1e-6)
    assert len(pids) >= 8


# =============================================================================================
# pure functions on small fixtures
# =============================================================================================


def _frame(rows: list[tuple]) -> pl.DataFrame:
    """rows: (row, col, ref, value[, role])"""
    recs = []
    for r in rows:
        role = r[4] if len(r) > 4 else "free"
        recs.append(dict(row=r[0], col=r[1], ref=r[2], component="total", value=float(r[3]), status="estimated",
                         role=role, tol_rel=None, confidence=None if role == "fixed" else "low", bop_function=None,
                         prov_id="sam_x:000000000000", note=None, block="x"))  # fmt: skip
    return pl.DataFrame(recs, schema={**spec.ENTRY_DTYPES, "block": pl.String()}, orient="row")


def test_split_pro_rata_is_exact_and_puts_the_remainder_on_the_largest():
    key = {"a": 1.0, "b": 2.0, "c": 7.0}
    out = closure.split_pro_rata(100.0 / 3.0, key)
    assert sum(out.values()) == pytest.approx(100.0 / 3.0, abs=1e-12)
    assert out["a"] == round(100.0 / 30.0, 6) and out["b"] == round(200.0 / 30.0, 6)
    with pytest.raises(SamError):
        closure.split_pro_rata(1.0, {"a": 0.0, "b": 0.0})


def test_whitelist_rejects_misfiled_and_intra_household_refs():
    ok = _frame([("H_R1", "F_LREG", "F1a", 10), ("C_FOOD", "H_R1", "C1a", 5)])
    assert closure.check_household_entries(ok, ["H_R1"]) == ([], [])
    bad = _frame([("H_R1", "G_CEN", "R9", 10), ("H_R1", "E_BANK", "R3a", 1), ("T_PIT", "H_R1", "T3", 2),
                  ("H_R1", "H_R2", "R10", 3)])  # fmt: skip
    problems, _ = closure.check_household_entries(bad, ["H_R1", "H_R2"])
    text = "\n".join(problems)
    assert "R9a" in text and "R8a" in text and "T3a" in text and "intra-household" in text
    assert len(problems) == 4


def test_partial_group_coverage_warns_except_r12a():
    df = _frame([("H_R1", "F_LREG", "F1a", 10), ("R_ROW", "H_R2", "R12a", 1)])
    problems, warnings = closure.check_household_entries(df, ["H_R1", "H_R2"])
    assert problems == [] and len(warnings) == 1 and "F1a" in warnings[0]


def test_account_imbalances_and_constraint_gaps():
    acc = ACC
    df = _frame([("C_FOOD", "H_R1", "C1a", 70), ("H_R1", "F_LREG", "F1a", 100), ("K_HH", "H_R1", "K4a", 20),
                 ("X_DISC", "H_R1", "D1", 10, "fixed")])  # fmt: skip
    imb = closure.account_imbalances(df, acc)
    assert imb.height == len(acc.codes) and imb["account"].to_list() == acc.codes
    r = imb.filter(pl.col("account") == "H_R1").row(0, named=True)
    assert r["row_total"] == 100 and r["col_total"] == 100 and r["imbalance"] == 0 and r["n_var_col"] == 2
    assert imb["imbalance"].sum() == pytest.approx(0.0)
    # same numbers as the framework's own diagnostics (one computation, checked twice: T12)
    fw = diagnostics(df, acc).select("account", "imbalance", "rank").sort("account")
    mine = imb.select("account", "imbalance", "rank").sort("account")
    assert mine.equals(fw)
    cons = pl.DataFrame(
        [dict(constraint_id="c", ref="C1", rows="C_FOOD", cols="H_R1,H_R2", refs=None, components=None, target=75.0,
              tol_abs=1.0, tol_rel=0.0, kind="equal", prov_id="p", description="d", block="b"),
         dict(constraint_id="m", ref="C1", rows="C_FOOD", cols="H_R1", refs="C1a", components=None, target=60.0,
              tol_abs=0.0, tol_rel=0.0, kind="min", prov_id="p", description="d", block="b")],
        schema={**spec.CONSTRAINT_DTYPES, "block": pl.String()}, orient="row",
    )  # fmt: skip
    g = closure.constraint_gaps(df, cons).sort("constraint_id")
    assert g["prior_sum"].to_list() == [70.0, 70.0]
    assert g["outside"].to_list() == [True, False] and g["hi"][1] == float("inf")


def test_institution_flows_classify_and_net():
    df = _frame([("H_R1", "F_LREG", "F1a", 100), ("H_R1", "G_CEN", "R9a", 10), ("T_PIT", "H_R1", "T3a", 5),
                 ("C_FOOD", "H_R1", "C1a", 80), ("K_HH", "H_R1", "K4a", 20), ("X_DISC", "H_R1", "D1", 5, "fixed"),
                 ("G_CEN", "T_PIT", "T1a", 5), ("G_CEN", "T_CGST", "T1a", 7), ("G_STA", "G_CEN", "R1", 3)])  # fmt: skip
    f = closure.institution_flows(df, ACC)

    def net(inst, cls):
        return f.filter((pl.col("institution") == inst) & (pl.col("flow_class") == cls))["net"].item()

    assert net("H_R1", "factor_income") == 100 and net("H_R1", "social") == 10
    assert net("H_R1", "current_taxes") == -5 and net("H_R1", "final_consumption") == -80
    assert net("H_R1", "saving") == -20 and net("H_R1", "discrepancy") == -5
    assert net("GG", "current_taxes") == 5 and net("GG", "taxes_on_production_imports") == 7
    assert net("GG", "other_transfers") == 0  # devolution is internal to GG
    assert net("G_CEN", "other_transfers") == -3


# =============================================================================================
# the block on synthetic dependencies (scratch SAM folder, real clean data)
# =============================================================================================


@dataclass(frozen=True)
class _ScratchSam(Layout):
    """The real clean data; SAM outputs under a scratch folder."""

    sam_dir: Path = Path(".")

    @property
    def sam(self) -> Path:  # type: ignore[override]
        return self.sam_dir


def _layout(tmp: Path) -> _ScratchSam:
    base = Layout.default()
    return _ScratchSam(**{f.name: getattr(base, f.name) for f in fields(Layout)}, sam_dir=tmp / "sam")


def _val(ds, sid, unit="mospi_nas_2026"):
    return _clean(ds, sid, unit)


def _fake_specs(extra: dict | None = None) -> dict:
    """block -> (refs, [(row, col, ref, value, role)]). Household flows are synthetic; D2/D3 are read from clean."""
    cif = _val("io_tables_sut_supply", "supply.cif_adj.cif.current", "io_tables")
    d3 = _val("mospi_nas_2026_derived_residuals", "derived.si_errors_omissions.current")
    i2a = _val("io_tables_sut_use", "use.valuables.total.current", "io_tables") - _val(
        "mospi_nas_2026_s1_9", "s1_9.saving_in_the_form_of_gold_and_silver_ornaments.current"
    )
    n = {g: i + 1 for i, g in enumerate(HH)}
    specs = {
        "production": (["D4"], [(c, "X_DISC", "D4", 0.0, "fixed") for c in ACC.in_group("COM")]),
        "households": (["C1a"], [("C_FOOD", g, "C1a", 120_000.0 * n[g], "free") for g in HH]),
        "factors": (["F1a", "F2"], [(g, "F_LREG", "F1a", 100_000.0 * n[g], "free") for g in HH]
                    + [(g, "F_MIXD", "F2", 50_000.0 * n[g], "free") for g in HH]),
        "taxes": (["T3a"], [("T_PIT", g, "T3a", 2_000.0 * n[g], "free") for g in HH]),
        "government": (["R9a", "R9b", "R10"], [(g, "G_CEN", "R9a", 5_000.0, "free") for g in HH]
                       + [("G_CEN", g, "R9b", 500.0, "free") for g in HH]),
        "fincorp": (["R8a", "R5"], [(g, "E_BANK", "R8a", 20_000.0 * n[g], "free") for g in HH]
                    + [("E_BANK", g, "R5", 1_000.0 * n[g], "free") for g in HH]),
        "rest_of_world": (["R11a", "R12a", "D2"], [(g, "R_ROW", "R11a", 3_000.0, "free") for g in HH]
                          + [("R_ROW", g, "R12a", 400.0, "free") for g in ("H_U4", "H_U5")]
                          + [("R_ROW", "X_DISC", "D2", cif, "fixed")]),
        "capital_financial": (["D3", "I2a"], [("K_HH", "X_DISC", "D3", i2a, "fixed"),
                                              ("K_NFPR", "X_DISC", "D3", d3 - i2a, "fixed")]),
    }  # fmt: skip
    for b, rows in (extra or {}).items():
        refs, ents = specs[b]
        specs[b] = (refs, ents + rows)
    return specs


def _write_fake(layout: Layout, block: str, refs: list[str], rows: list[tuple]) -> None:
    ctx = BlockContext(block=block, refs=tuple(refs), depends=(), layout=layout)
    pids = {r: ctx.prov(ref=r, status="estimated", method=f"synthetic {r} for the closure unit test",
                        notes="test fixture", vintage="2026-08-31") for r in refs}  # fmt: skip
    ents = []
    for row, col, ref, v, role in rows:
        kw = {"confidence": "low"} if role == "free" else {}
        ents.append(entry(row, col, ref, v, prov_id=pids[ref], status="estimated", role=role, **kw))
    cons = []
    sats: dict[str, Satellite] = {}
    if block == "capital_financial":
        k4 = _val("mospi_nas_2026_s1_9", "s1_9.household_sector.current")
        cons.append(constraint("cf.k4.hh_saving", "D3", ["K_HH"], HH, k4, prov_id=pids["D3"], tol_abs=0.5,
                               refs=["K4a"], description="duplicate of closure's K4 constraint"))  # fmt: skip
    if block == "households":
        persons = {g: 1.0e7 * (i + 1) for i, g in enumerate(HH)}
        sats["hh_keys"] = Satellite("C1a", pl.DataFrame(
            [{"series_id": f"pop_persons.level.{g.lower()}", "household_group": g, "key": "pop_persons",
              "measure": "level", "value": v, "unit": "count", "status": "estimated", "prov_id": pids["C1a"]}
             for g, v in persons.items()]), "test keys")  # fmt: skip
    paths = SamPaths(layout)
    paths.blocks.mkdir(parents=True, exist_ok=True)
    ent = validate_entries(ctx, ents).with_columns(pl.lit(block).alias("block"))
    con = validate_constraints(ctx, cons).with_columns(pl.lit(block).alias("block"))
    used = set(ent["prov_id"]) | set(con["prov_id"])
    for name, s in sats.items():
        df = validate_satellite(ctx, name, s)
        used |= set(df["prov_id"])
        paths.satellites(block).mkdir(parents=True, exist_ok=True)
        io.write_parquet(df, paths.satellites(block) / f"{name}.parquet", sort_by=("series_id",))
    io.write_parquet(ent, paths.entries(block), sort_by=spec.ENTRY_KEY, decimals={"value": 6, "tol_rel": None})
    io.write_parquet(con, paths.constraints(block), sort_by=("constraint_id",))
    io.write_parquet(referenced_provenance(ctx, used), paths.provenance(block), sort_by=("prov_id",))
    paths.catalog(block).write_text("{}", encoding="utf-8", newline="\n")


def _synthetic(tmp: Path, extra: dict | None = None):
    layout = _layout(tmp)
    for b, (refs, rows) in _fake_specs(extra).items():
        _write_fake(layout, b, refs, rows)
    r, valid = build_block_module(closure, layout, write=False)
    return layout, r, valid


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    layout, r, valid = _synthetic(tmp_path_factory.mktemp("closure_synth"))
    assert r.ok, r.message
    return layout, r, valid


def _dep_entries(layout: Layout) -> pl.DataFrame:
    p = SamPaths(layout)
    return pl.concat([pl.read_parquet(p.entries(b)) for b in closure.DEPENDS])


def test_synthetic_entries_shape(synthetic):
    """T1 / T4 shape: 10 K4a (free, low, estimated) and 10 D1 (fixed, estimated, > 0) entries."""
    _, _, valid = synthetic
    e = valid.entries
    k = e.filter(pl.col("ref") == "K4a")
    d = e.filter(pl.col("ref") == "D1")
    assert sorted(k["col"]) == sorted(HH) and set(k["row"]) == {"K_HH"}
    assert set(k["role"]) == {"free"} and set(k["confidence"]) == {"low"} and set(k["status"]) == {"estimated"}
    assert (k["value"].abs() >= closure.MIN_ABS_SAVING).all()
    assert sorted(d["col"]) == sorted(HH) and set(d["row"]) == {"X_DISC"} and set(d["role"]) == {"fixed"}
    assert set(d["status"]) == {"estimated"} and (d["value"] > 0).all()
    prov = valid.provenance
    assert prov.filter(pl.col("prov_id").is_in(k["prov_id"].to_list()))["method"].str.len_chars().min() > 50


def test_synthetic_residual_identity_and_d1(synthetic):
    """T3, T4, T5: each group's prior account balances; D1 = D2 + D3 + D4 as written, within Rs 1 crore of the
    published residual; D1 shares = gross-income shares."""
    layout, _, valid = synthetic
    dep = _dep_entries(layout)
    allp = pl.concat([dep.drop("block"), valid.entries])
    for g in HH:
        row = allp.filter(pl.col("row") == g)["value"].sum()
        col = allp.filter(pl.col("col") == g)["value"].sum()
        assert row - col == pytest.approx(0.0, abs=1e-5), g
    d1 = valid.entries.filter(pl.col("ref") == "D1")
    xcol = dep.filter(pl.col("col") == "X_DISC")["value"].sum()
    assert d1["value"].sum() == pytest.approx(xcol, abs=1e-6)
    pub = _nas("derived_residuals", "derived.household_residual.current")
    assert abs(d1["value"].sum() - pub) <= closure.D1_BAND
    inc = {g: dep.filter(pl.col("row") == g)["value"].sum() for g in HH}
    tot = sum(inc.values())
    for g, v in d1.select("col", "value").rows():
        assert v / d1["value"].sum() == pytest.approx(inc[g] / tot, abs=1e-9)


def test_synthetic_constraints(synthetic):
    _, _, valid = synthetic
    c = {r["constraint_id"]: r for r in valid.constraints.iter_rows(named=True)}
    k4 = c["k4.hh_saving_total"]
    assert k4["target"] == _nas("s1_9", "s1_9.household_sector.current") and k4["refs"] == "K4a"
    assert k4["rows"] == "K_HH" and k4["cols"] == ",".join(HH) and k4["tol_abs"] == closure.K4_TOL
    d1 = c["d1.published_total"]
    assert d1["target"] == _nas("derived_residuals", "derived.household_residual.current") and d1["kind"] == "band"


def test_synthetic_k4_duplicate_merges_with_capital_financial(synthetic, tmp_path):
    """closure's K4 constraint and capital_financial's (same selection, same target) are duplicates, not a conflict."""
    from pipeline.sam.assemble import merge_constraints

    layout, _, valid = synthetic
    p = SamPaths(layout)
    io.write_parquet(valid.constraints.with_columns(pl.lit("closure").alias("block")), p.constraints("closure"),
                     sort_by=("constraint_id",))  # fmt: skip
    try:
        m = merge_constraints(p, ["capital_financial", "closure"])
        k = m.filter(pl.col("declared_by").str.contains("cf.k4"))
        assert k.height == 1 and "closure:k4.hh_saving_total" in k["declared_by"][0]
    finally:
        p.constraints("closure").unlink()


def test_synthetic_diagnostics(synthetic):
    """T12 and T13: prior_imbalance has 128 accounts that sum to 0 and equal the framework's diagnostics; X_DISC is
    flagged with no variable entry; constraint_gaps covers every declared constraint; the X_DISC residual is
    D1_published - D2 - D3 - D4 as written."""
    layout, _, valid = synthetic
    allp = pl.concat([_dep_entries(layout), valid.entries.with_columns(pl.lit("closure").alias("block"))])
    _, pi = valid.satellites["prior_imbalance"]
    imb = pi.filter(pl.col("measure") == "imbalance")
    assert imb.height == len(ACC.codes)
    assert imb["value"].sum() == pytest.approx(0.0, abs=1e-6)
    fw = dict(diagnostics(allp, ACC).select("account", "imbalance").rows())
    for a, v in imb.select("account", "value").rows():
        assert v == pytest.approx(fw[a], abs=1e-6), a
    xd = pi.filter((pl.col("account") == "X_DISC") & pl.col("measure").is_in(["n_var_row", "n_var_col"]))
    assert xd["value"].sum() == 0
    _, cg = valid.satellites["constraint_gaps"]
    assert set(cg["constraint_id"]) == {"capital_financial:cf.k4.hh_saving", "closure:k4.hh_saving_total",
                                        "closure:d1.published_total"}  # fmt: skip
    _, xs = valid.satellites["xdisc_identity"]
    x = dict(xs.select("item", "value").rows())
    assert x["residual_published_minus_written"] == pytest.approx(
        x["d1_published"] - x["d2_written"] - x["d3_written"] - x["d4_written"], abs=1e-6
    )
    assert x["d2_written"] in (x["ref_d2_sut_cif"], x["ref_d2_nas61_cif"])


def test_synthetic_hh_saving_and_z(synthetic):
    _, _, valid = synthetic
    _, hs = valid.satellites["hh_saving"]
    v = {(g, m): x for g, m, x in hs.select("household_group", "measure", "value").rows()}
    k4a = {r["col"]: r["value"] for r in valid.entries.filter(pl.col("ref") == "K4a").iter_rows(named=True)}
    nas = _nas("s1_9", "s1_9.household_sector.current")
    assert v[("ALL", "z")] == pytest.approx(sum(k4a.values()) - nas, abs=1e-5)
    assert sum(v[(g, "k4a_option_b")] for g in HH) == pytest.approx(nas, abs=1e-4)
    assert sum(v[(g, "d1_key")] for g in HH) == pytest.approx(1.0, abs=1e-9)
    assert sum(v[(g, "d1_by_population")] for g in HH) == pytest.approx(v[("ALL", "d1")], abs=1e-5)
    assert v[("RURAL", "ifpri_saving_rate_2022_23")] == _clean(
        "io_tables_ifpri_2223_datapaper", "ifpri.t11.savings_rate.rural", "io_tables", "2022-23"
    )
    _, ig = valid.satellites["institution_gaps"]
    h = {m: x for i, m, x in ig.select("institution", "measure", "value").rows() if i == "HH"}
    assert h["imbalance"] == pytest.approx(0.0, abs=1e-5)  # option A: every group closes


def _inputs(prov: pl.DataFrame, pid: str) -> set[str]:
    rec = prov.filter(pl.col("prov_id") == pid)
    assert rec.height == 1, pid
    return {i for i in (rec["inputs"][0] or "").split(",") if i}


def _d1_total_pid(prov: pl.DataFrame) -> str:
    tot = prov.filter((pl.col("status") == "derived") & pl.col("method").str.starts_with("Gap map D1, DECISIONS D2-3"))
    assert tot.height == 1
    return tot["prov_id"][0]


def test_synthetic_d1_split_record_cites_the_income_key(synthetic):
    """Verification V-CLO-4: the D1 split record cites the entries of its key (prior gross income: every entry with
    row = H_g) and the D1 total record, not the household outlays."""
    layout, _, valid = synthetic
    dep = _dep_entries(layout)
    pids = set(valid.entries.filter(pl.col("ref") == "D1")["prov_id"])
    assert len(pids) == 1
    income = set(dep.filter(pl.col("row").is_in(HH))["prov_id"])
    assert _inputs(valid.provenance, pids.pop()) == income | {_d1_total_pid(valid.provenance)}


def test_synthetic_satellite_statuses(synthetic):
    """Verification V-CLO-3 (STATUS_RULE): a diagnostic row is 'estimated' where an estimated entry enters it (all
    synthetic entries are estimated), 'derived' for counts and for the NAS requirements, 'official' only for a copy
    of one published figure; hh_saving copies keep the status of what they copy."""
    _, _, valid = synthetic
    _, pi = valid.satellites["prior_imbalance"]
    for m in ("row_total", "col_total", "imbalance", "rank"):
        assert set(pi.filter((pl.col("measure") == m) & (pl.col("account") == "H_R1"))["status"]) == {"estimated"}, m
    assert set(pi.filter(pl.col("measure").is_in(["n_var_row", "n_var_col"]))["status"]) == {"derived"}
    _, ig = valid.satellites["institution_gaps"]
    st = {(i, m): s for i, m, s in ig.select("institution", "measure", "status").rows()}
    assert st[("HH", "nas_total")] == "official" and st[("HH", "required_net")] == "derived"
    assert st[("HH", "delivered_net")] == "estimated" and st[("HH", "gap")] == "estimated"
    assert st[("ROW_NET", "required_net")] == "derived"
    _, cg = valid.satellites["constraint_gaps"]
    k4 = dict(cg.filter(pl.col("constraint_id") == "closure:k4.hh_saving_total").select("measure", "status").rows())
    assert k4 == {"prior_sum": "estimated", "target": "official", "lo": "derived", "hi": "derived",
                  "gap": "estimated", "n_members": "derived"}  # fmt: skip
    _, hs = valid.satellites["hh_saving"]
    s = dict(hs.select("series_id", "status").rows())
    assert s["all.k4_nas"] == "official" and s["all.d1"] == "derived" and s["all.z"] == "estimated"
    assert s["h_r1.persons"] == "estimated"  # the synthetic hh_keys rows are estimated
    k4_rec = hs.filter(pl.col("series_id") == "all.k4_nas")["prov_id"][0]
    cons = {r["constraint_id"]: r["prov_id"] for r in valid.constraints.iter_rows(named=True)}
    assert _inputs(valid.provenance, k4_rec) == _inputs(valid.provenance, cons["k4.hh_saving_total"])


def test_synthetic_checks(synthetic):
    _, _, valid = synthetic
    ch = {r["check_id"]: r for r in valid.checks.iter_rows(named=True)}
    for cid in ("d1.written_vs_published", "d1.published_identity_s1_14", "d1.published_identity_s1_1",
                "d2.written_vs_sut_cif", "d3.written_vs_nas", "d3.k_hh_vs_unsectored_valuables",
                "x_disc.prior_closure", "required_flows.identity"):  # fmt: skip
        assert ch[cid]["ok"], ch[cid]
    assert "k4.prior_sum_vs_nas" in ch  # fails by Z (a finding, not an error)


@pytest.mark.parametrize(
    "extra,message",
    [
        ({"government": [("H_R1", "G_CEN", "R10", 1.0, "free"), ("H_R2", "H_R1", "R10", 1.0, "free")]},
         "intra-household"),
        ({"government": [("H_R1", "G_CEN", "R9b", 1.0, "free")]}, "not an allowed household resource ref"),
    ],
)  # fmt: skip
def test_synthetic_loud_failures(tmp_path, extra, message):
    _, r, _ = _synthetic(tmp_path, extra)
    assert not r.ok and message in r.message, r.message


def test_synthetic_tiny_residual_fails(tmp_path):
    """Plan s.6 R6: a group whose residual saving is below Rs 1 crore in absolute value fails the build."""
    layout = _layout(tmp_path)
    specs = _fake_specs()
    for b, (refs, rows) in specs.items():
        _write_fake(layout, b, refs, rows)
    dep = _dep_entries(layout)
    inc = closure.group_sums(dep, HH, side="row")
    out = closure.group_sums(dep, HH, side="col")
    d1 = closure.split_pro_rata(float(dep.filter(pl.col("col") == "X_DISC")["value"].sum()), inc)
    gap = inc["H_R1"] - out["H_R1"] - d1["H_R1"] - 0.5  # leaves a residual of Rs 0.5 crore on H_R1
    refs, rows = specs["taxes"]
    _write_fake(layout, "taxes", refs, [(r, c, f, v + gap if c == "H_R1" else v, ro) for r, c, f, v, ro in rows])
    r, _ = build_block_module(closure, layout, write=False)
    assert not r.ok and "smaller than Rs 1" in r.message, r.message


def test_synthetic_d1_band_is_enforced(tmp_path):
    layout = _layout(tmp_path)
    for b, (refs, rows) in _fake_specs().items():
        if b == "rest_of_world":
            rows = [(r, c, f, v + 5.0 if f == "D2" else v, ro) for r, c, f, v, ro in rows]
        _write_fake(layout, b, refs, rows)
    r, _ = build_block_module(closure, layout, write=False)
    assert not r.ok and "X_DISC identity" in r.message


# =============================================================================================
# the real built outputs (skip until `sam closure` has run)
# =============================================================================================


@pytest.fixture(scope="module")
def built():
    if not PATHS.built("closure"):
        missing = [b for b in closure.DEPENDS if not PATHS.built(b)]
        pytest.skip(f"closure not built (dependencies not built: {', '.join(missing) or 'none'}; run `sam closure`)")
    return pl.read_parquet(PATHS.entries("closure"))


@pytest.fixture(scope="module")
def fresh(built):
    r, valid = build_block_module(closure, LAYOUT, write=False)
    assert r.ok, r.message
    return valid


def test_built_outputs_equal_a_fresh_build(built, fresh):
    want = canonical_floats(fresh.entries, {"value": 6, "tol_rel": None}).sort(list(spec.ENTRY_KEY))
    assert built.drop("block").equals(want)
    cons = pl.read_parquet(PATHS.constraints("closure"))
    assert cons.drop("block").equals(canonical_floats(fresh.constraints).sort("constraint_id"))


def test_built_checks_that_must_hold(fresh):
    ch = {r["check_id"]: r for r in fresh.checks.iter_rows(named=True)}
    for cid in ("d1.written_vs_published", "d1.published_identity_s1_14", "d1.published_identity_s1_1",
                "x_disc.prior_closure", "required_flows.identity", "d3.written_vs_nas"):  # fmt: skip
        assert ch[cid]["ok"], ch[cid]


def test_built_residual_identity_and_d1(built):
    """T3, T4, T5 on the real prior."""
    dep = pl.concat([pl.read_parquet(PATHS.entries(b)) for b in closure.DEPENDS])
    allp = pl.concat([dep, built])
    for g in HH:
        d = allp.filter(pl.col("row") == g)["value"].sum() - allp.filter(pl.col("col") == g)["value"].sum()
        assert d == pytest.approx(0.0, abs=1e-5), g
    d1 = built.filter(pl.col("ref") == "D1")
    assert d1.height == 10 and set(d1["role"]) == {"fixed"} and (d1["value"] > 0).all()
    assert d1["value"].sum() == pytest.approx(dep.filter(pl.col("col") == "X_DISC")["value"].sum(), abs=1e-5)
    pub = _nas("derived_residuals", "derived.household_residual.current")
    assert abs(d1["value"].sum() - pub) <= closure.D1_BAND
    inc = {g: dep.filter(pl.col("row") == g)["value"].sum() for g in HH}
    for g, v in d1.select("col", "value").rows():
        assert v / d1["value"].sum() == pytest.approx(inc[g] / sum(inc.values()), abs=1e-9)
    k = built.filter(pl.col("ref") == "K4a")
    assert k.height == 10 and set(k["role"]) == {"free"} and (k["value"].abs() >= 1).all()


def test_built_whitelist_holds(built):
    """T11: every household-touching entry of every block uses an allowed ref (the build enforces it)."""
    dep = pl.concat([pl.read_parquet(PATHS.entries(b)) for b in closure.DEPENDS])
    problems, _ = closure.check_household_entries(dep, HH)
    assert problems == []


def test_built_diagnostics_match_the_framework(built):
    """T12 on the real prior."""
    dep = pl.concat([pl.read_parquet(PATHS.entries(b)) for b in closure.DEPENDS])
    allp = pl.concat([dep, built])
    pi = pl.read_parquet(PATHS.satellites("closure") / "prior_imbalance.parquet")
    imb = pi.filter(pl.col("measure") == "imbalance")
    assert imb.height == len(ACC.codes) and abs(imb["value"].sum()) < 1e-4
    fw = dict(diagnostics(allp, ACC).select("account", "imbalance").rows())
    for a, v in imb.select("account", "value").rows():
        assert v == pytest.approx(fw[a], abs=1e-5), a


def test_built_d1_split_record_cites_the_income_key(built):
    """Verification V-CLO-4 on the real prior."""
    prov = pl.read_parquet(PATHS.provenance("closure"))
    dep = pl.concat([pl.read_parquet(PATHS.entries(b)) for b in closure.DEPENDS])
    pids = set(built.filter(pl.col("ref") == "D1")["prov_id"])
    assert len(pids) == 1
    income = set(dep.filter(pl.col("row").is_in(HH))["prov_id"])
    assert _inputs(prov, pids.pop()) == income | {_d1_total_pid(prov)}


def test_built_satellite_statuses(built):
    """Verification V-CLO-3 on the real prior: prior_imbalance row / column totals are 'estimated' exactly where an
    estimated entry is in that row / column; constraint targets keep their record's status; the hh_saving copies
    keep the status of the NAS K4 total (official), hh_keys persons and the IFPRI rates."""
    dep = pl.concat([pl.read_parquet(PATHS.entries(b)) for b in closure.DEPENDS])
    allp = pl.concat([dep, built])
    pi = pl.read_parquet(PATHS.satellites("closure") / "prior_imbalance.parquet")
    for side, m in (("row", "row_total"), ("col", "col_total")):
        est = set(allp.filter(pl.col("status") == "estimated")[side])
        for a, st in pi.filter(pl.col("measure") == m).select("account", "status").rows():
            assert st == ("estimated" if a in est else "derived"), (a, m, st)
    assert set(pi.filter(pl.col("measure").is_in(["n_var_row", "n_var_col"]))["status"]) == {"derived"}
    prov = pl.read_parquet(PATHS.provenance("closure"))
    status_of = dict(prov.select("prov_id", "status").rows())
    for sat in ("prior_imbalance", "constraint_gaps", "institution_gaps", "hh_saving", "xdisc_identity"):
        df = pl.read_parquet(PATHS.satellites("closure") / f"{sat}.parquet")
        for pid, st in df.select("prov_id", "status").unique().rows():
            assert status_of[pid] == st, (sat, pid)
    cg = pl.read_parquet(PATHS.satellites("closure") / "constraint_gaps.parquet").filter(pl.col("measure") == "target")
    cons = pl.concat([pl.read_parquet(PATHS.constraints(b)) for b in [*closure.DEPENDS, "closure"]])
    recs = pl.concat(
        [pl.read_parquet(PATHS.provenance(b)).select("prov_id", "status") for b in [*closure.DEPENDS, "closure"]]
    )
    rec_status = dict(recs.rows())
    want = {f"{b}:{c}": rec_status[p] for b, c, p in cons.select("block", "constraint_id", "prov_id").rows()}
    for cid, st in cg.select("constraint_id", "status").rows():
        assert st == want[cid], cid
    hs = dict(pl.read_parquet(PATHS.satellites("closure") / "hh_saving.parquet").select("series_id", "status").rows())
    keys = pl.read_parquet(PATHS.satellites("households") / "hh_keys.parquet")
    persons = set(keys.filter((pl.col("key") == "pop_persons") & (pl.col("measure") == "level"))["status"])
    assert len(persons) == 1 and {hs[f"{g.lower()}.persons"] for g in HH} == persons
    ifpri = pl.read_parquet(LAYOUT.clean / "io_tables" / "io_tables_ifpri_2223_datapaper.parquet")
    ifpri = set(ifpri.filter(pl.col("series_id").is_in(["ifpri.t11.savings_rate.rural", "ifpri.t11.savings_rate.urban"])
                             & (pl.col("period") == "2022-23"))["status"])  # fmt: skip
    assert {hs["rural.ifpri_saving_rate_2022_23"], hs["urban.ifpri_saving_rate_2022_23"]} == ifpri
    assert hs["all.k4_nas"] == "official" and hs["all.z"] == "estimated"


def test_built_xdisc_identity(built):
    """T13."""
    xs = pl.read_parquet(PATHS.satellites("closure") / "xdisc_identity.parquet")
    x = dict(xs.select("item", "value").rows())
    assert x["d1_published"] == _nas("derived_residuals", "derived.household_residual.current")
    assert x["d2_written"] == pytest.approx(
        _clean("io_tables_sut_supply", "supply.cif_adj.cif.current", "io_tables"), abs=1e-6
    )
    assert abs(x["residual_published_minus_written"]) <= closure.D1_BAND
