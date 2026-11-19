"""The block contract and validation (DESIGN_BRIEF s.3-4): every rule fails loudly with a clear message."""

from __future__ import annotations

import types

import polars as pl
import pytest

from pipeline.core.paths import Layout
from pipeline.sam.framework import (
    BlockContext,
    BlockResult,
    SamError,
    Satellite,
    block_order,
    build_block_module,
    check_contract,
    check_ref_ownership,
    constraint,
    entry,
    select_vintage,
)

pytestmark = pytest.mark.sam

NOTE = "test assumption: synthetic numbers for a framework unit test"


def _mod(build, block="closure", refs=("D1", "K4a"), depends=()):
    m = types.ModuleType(block)
    m.BLOCK, m.REFS, m.DEPENDS, m.build = block, list(refs), list(depends), build
    return m


def _est(ctx: BlockContext, ref="D1") -> str:
    return ctx.prov(ref=ref, status="estimated", method=f"synthetic {ref}", notes=NOTE, vintage="2026-08-31")


def _ok_entry(ctx, **kw):
    base = dict(prov_id=_est(ctx), status="estimated", role="free", confidence="low")
    base.update(kw)
    return entry(base.pop("row", "X_DISC"), base.pop("col", "H_R1"), base.pop("ref", "D1"), base.pop("value", 10.0),
                 **base)  # fmt: skip


def _run(build, tmp_layout, **kw):
    r, valid = build_block_module(_mod(build, **kw), tmp_layout, write=False)
    return r, valid


def test_a_valid_block_passes_and_writes_nothing_when_asked(tmp_layout):
    def build(ctx):
        pid = _est(ctx)
        pk = _est(ctx, "K4a")
        return BlockResult(
            entries=[
                entry("X_DISC", "H_R1", "D1", 5.0, prov_id=pid, status="estimated", role="fixed"),
                entry("K_HH", "H_R1", "K4a", -3.0, prov_id=pk, status="estimated", role="free", confidence="low"),
            ],
            constraints=[
                constraint(
                    "hh_saving",
                    "K4a",
                    ["K_HH"],
                    ["H_R1", "H_R2"],
                    -3.0,
                    prov_id=pk,
                    tol_abs=1.0,
                    description="synthetic",
                )
            ],  # fmt: skip
        )

    r, valid = _run(build, tmp_layout)
    assert r.ok, r.message
    assert valid.entries.height == 2 and valid.constraints["cols"].to_list() == ["H_R1,H_R2"]
    assert valid.provenance["ingest_unit"].to_list() == ["sam_closure"] * 2  # one record per ref
    assert not (tmp_layout.sam).exists()


@pytest.mark.parametrize(
    "kw,message",
    [
        (dict(row="X_NOPE"), "unknown account"),
        (dict(row="H_R1", col="X_DISC"), "structurally zero"),
        (dict(ref="P1"), "not in this block's REFS"),
        (dict(value=0.0), "zero value"),
        (dict(value=float("nan")), "not finite"),
        (dict(role="anchored", confidence=None), "anchored entry needs tol_rel"),
        (dict(role="free", confidence=None), "free entry needs confidence"),
        (dict(role="fixed"), "fixed entry has no tol_rel and no confidence"),
        (dict(status="official"), "differs from its provenance record"),
        (dict(prov_id="sam_closure:000000000000"), "was not registered"),
        (dict(component="Bad Slug"), "lower-case slug"),
        (dict(bop_function="FDI_equity"), "bop_function needs"),
        (dict(role="bogus"), "role 'bogus'"),
    ],
)
def test_bad_entries_are_rejected(tmp_layout, kw, message):
    def build(ctx):
        return BlockResult(entries=[_ok_entry(ctx, **kw)])

    r, _ = _run(build, tmp_layout)
    assert not r.ok and message in r.message, r.message


def test_bop_tags_of_wave_c_and_the_k7b_mirror_are_accepted(tmp_layout):
    """FR-row-1: the tags external_assistance, banking_capital, errors_omissions and portfolio_abroad exist (on a RoW
    entry). FR-cf-6: a bop tag may sit on the domestic mirror of a RoW line (ref K7b, no K_ROW/R_ROW in the cell);
    on any other ref without a RoW account it is still refused."""

    def build_row(ctx):
        pid = _est(ctx, "K8b")
        return BlockResult(entries=[
            entry("I_DEPO", "K_ROW", "K8b", 5.0, prov_id=pid, status="estimated", role="free", confidence="low",
                  component=tag, bop_function=tag)
            for tag in ("external_assistance", "banking_capital", "errors_omissions", "portfolio_abroad")
        ])  # fmt: skip

    r, _ = _run(build_row, tmp_layout, block="rest_of_world", refs=("K8b",))
    assert r.ok, r.message

    def build_mirror(ctx, ref="K7b"):
        pid = _est(ctx, ref)
        e = entry("I_EQTY", "K_NFPR", ref, 5.0, prov_id=pid, status="estimated", role="free", confidence="low",
                  component="row_cp_odi_equity", bop_function="ODI")  # fmt: skip
        return BlockResult(entries=[e])

    r, _ = _run(build_mirror, tmp_layout, block="capital_financial", refs=("K7b",))
    assert r.ok, r.message
    r, _ = _run(lambda ctx: build_mirror(ctx, "K7"), tmp_layout, block="capital_financial", refs=("K7",))
    assert not r.ok and "bop_function needs" in r.message, r.message


def test_duplicate_keys_are_rejected(tmp_layout):
    def build(ctx):
        return BlockResult(entries=[_ok_entry(ctx), _ok_entry(ctx, value=2.0)])

    r, _ = _run(build, tmp_layout)
    assert not r.ok and "duplicate key" in r.message


@pytest.mark.parametrize(
    "kw,message",
    [
        (dict(rows=["NOPE"]), "unknown accounts"),
        (dict(ref="ZZ9"), "not a gap-map ref"),
        (dict(tol_abs=-1.0), "tol_abs must be"),
        (dict(kind="range"), "kind must be"),
        (dict(refs=[]), "refs filter"),
        (dict(components=["Not A Slug"]), "components filter"),
        (dict(description=" "), "description is required"),
    ],
)
def test_bad_constraints_are_rejected(tmp_layout, kw, message):
    def build(ctx):
        args = dict(constraint_id="c1", ref="K4a", rows=["K_HH"], cols=["H_R1"], target=1.0, prov_id=_est(ctx),
                    description="synthetic")  # fmt: skip
        args.update(kw)
        return BlockResult(entries=[_ok_entry(ctx)], constraints=[constraint(**args)])

    r, _ = _run(build, tmp_layout)
    assert not r.ok and message in r.message, r.message


def test_provenance_rules(tmp_layout):
    ctx = BlockContext(block="closure", refs=("D1", "K4a"), depends=(), layout=tmp_layout)
    with pytest.raises(SamError, match="needs a method"):
        ctx.prov(ref="D1", status="estimated", method=" ", notes=NOTE, vintage="2026-08-31")
    with pytest.raises(SamError, match="needs inputs or notes"):
        ctx.prov(ref="D1", status="estimated", method="m", vintage="2026-08-31")
    with pytest.raises(SamError, match="does not resolve"):
        ctx.prov(ref="D1", status="derived", method="m", inputs=["io_tables:000000000000"])
    with pytest.raises(SamError, match="not in data/gap_map.csv"):
        ctx.prov(ref="ZZ9", status="estimated", method="m", notes=NOTE, vintage="2026-08-31")
    est = ctx.prov(ref="D1", status="estimated", method="m", notes=NOTE, vintage="2026-08-31")
    with pytest.raises(SamError, match="may only aggregate official inputs"):
        ctx.prov(ref="D1", status="official", method="m", inputs=[est])
    assert ctx.prov(ref="D1", status="estimated", method="m", notes=NOTE, vintage="2026-08-31") == est  # stable id
    assert est.startswith("sam_closure:")


def test_official_records_resolve_clean_inputs_and_take_their_vintage(repo_layout):
    ctx = BlockContext(block="production", refs=("P1",), depends=(), layout=repo_layout)
    v, pid = ctx.value("mospi_nas_2026_s1_1", "s1_1.gdp.current", vintage="latest")
    assert v > 2.9e7
    rec = ctx.provenance[ctx.prov(ref="P1", status="official", method="m", inputs=[pid])]
    # source_id is the source of the inputs (NAS 2026 here), not the gap map's primary source of the ref (the SUT)
    assert rec["vintage"] == ctx.clean_index.prov(pid)["vintage"]
    assert rec["source_id"] == ctx.clean_index.prov(pid)["source_id"] == "mospi_nas_2026_publication"


def test_satellite_rules(tmp_layout):
    def build(ctx, df=None):
        pid = _est(ctx)
        df = pl.DataFrame({"series_id": ["a", "a"], "value": [1.0, 2.0], "unit": ["INR_crore", "furlong"],
                           "status": ["estimated", "estimated"], "prov_id": [pid, pid]})  # fmt: skip
        return BlockResult(entries=[_ok_entry(ctx)], satellites={"keys": Satellite("D1", df, "synthetic")})

    r, _ = _run(build, tmp_layout)
    assert not r.ok and "series_id must be unique" in r.message and "furlong" in r.message


def test_contract_and_ownership(tmp_layout):
    def build(ctx):
        return BlockResult()

    with pytest.raises(SamError, match="owned by block 'production'"):
        check_contract(_mod(build, refs=("D1", "P1")), layout=tmp_layout)
    with pytest.raises(SamError, match="not a block of DESIGN_BRIEF"):
        check_contract(_mod(build, block="widgets", refs=("D1",)), layout=tmp_layout)
    with pytest.raises(SamError, match="not allowed for production"):
        check_contract(_mod(build, block="production", refs=("P1",), depends=("closure",)), layout=tmp_layout)
    with pytest.raises(SamError, match="claimed by both"):
        check_ref_ownership({"a": _mod(build, refs=("D1",)), "b": _mod(build, refs=("D1",))})
    with pytest.raises(SamError, match="cycle"):
        block_order(["a", "b"], {"a": ["b"], "b": ["a"]})
    r, _ = _run(build, tmp_layout)
    assert not r.ok and "returned nothing" in r.message


def test_dependencies_must_be_built(tmp_layout):
    def build(ctx):
        return BlockResult()

    r, _ = build_block_module(_mod(build, block="households", refs=("C1a",), depends=("production",)), tmp_layout)
    assert not r.ok and "dependency production has no output" in r.message


def test_vintage_handling():
    df = pl.DataFrame({"series_id": ["s", "s", "t", "s"], "period": ["2023-24", "2023-24", "2023-24", "2022-23"],
                       "vintage": ["2026-02-27", "2026-08-31", "2026-02-27", "2024-07-23"],
                       "value": [1.0, 2.0, 3.0, 4.0]})  # fmt: skip
    with pytest.raises(SamError, match="several vintages"):
        select_vintage(df, None, "x")
    # latest per (series, period): the 2022-23 row from an older release is kept
    assert select_vintage(df, "latest", "x")["value"].to_list() == [2.0, 3.0, 4.0]
    assert select_vintage(df, "2026-02-27", "x")["value"].to_list() == [1.0, 3.0]


def test_value_needs_exactly_one_row(repo_layout):
    ctx = BlockContext(block="production", refs=("P1",), depends=(), layout=repo_layout)
    with pytest.raises(SamError, match="not in the dataset"):
        ctx.value("mospi_nas_2026_s1_1", "s1_1.no_such_series.current")
    with pytest.raises(SamError, match="0 rows match"):  # the series exists, not for that period
        ctx.value("mospi_nas_2026_s1_1", "s1_1.gdp.current", period="1950-51", vintage="latest")
    with pytest.raises(SamError, match="not found"):
        ctx.frame("no_such_dataset")


def test_layout_paths_follow_the_clean_folder(tmp_path):
    lay = Layout.scratch(tmp_path)
    assert lay.sam == tmp_path / "sam" and lay.balancing_report == tmp_path / "BALANCING.md"
    assert Layout.default().balancing_report == Layout.default().root / "BALANCING.md"


# ---------------------------------------------------------------------------------------------
# Wave A review, integration lens (docs/phase2/verify/framework_integration.md)
# ---------------------------------------------------------------------------------------------


def test_a_broken_sibling_module_does_not_stop_another_blocks_build(tmp_layout, tmp_path, monkeypatch):
    """F1: a sibling with a syntax error fails only its own build; naming a block imports only it."""
    import sys

    import pipeline.sam.blocks as blocks_pkg
    from pipeline.sam import framework, run

    def build(ctx):
        return BlockResult(entries=[_ok_entry(ctx)])

    good = _mod(build)
    good.__name__ = "pipeline.sam.blocks.closure"
    monkeypatch.setitem(sys.modules, "pipeline.sam.blocks.closure", good)
    bad_dir = tmp_path / "blocks_extra"
    bad_dir.mkdir()
    (bad_dir / "factors.py").write_text('BLOCK = "factors"\ndef build(ctx:\n', encoding="utf-8")
    # the broken directory goes first so that it shadows the real block of that name (FR-factors-1: appended, the
    # real factors module was imported instead and the test failed for another reason)
    monkeypatch.setattr(blocks_pkg, "__path__", [str(bad_dir), *blocks_pkg.__path__])
    monkeypatch.setattr(framework, "block_names", lambda: ["closure", "factors"])
    monkeypatch.setattr(run, "block_names", lambda: ["closure", "factors"])
    monkeypatch.delitem(sys.modules, "pipeline.sam.blocks.factors", raising=False)
    runs, _ = run.build_blocks(tmp_layout, ["closure"], with_deps=False)
    assert [(r.block, r.ok) for r in runs] == [("closure", True)]
    runs, _ = run.build_blocks(tmp_layout, ["closure", "factors"], with_deps=True)
    by = {r.block: r for r in runs}
    assert by["closure"].ok and not by["factors"].ok and "SyntaxError" in by["factors"].message


def test_readers_check_unit_price_basis_and_fail_on_empty_results(repo_layout):
    """F2 and F4: a US$, percent or constant-price row is refused unless named; a typo raises."""
    ctx = BlockContext(block="production", refs=("P1",), depends=(), layout=repo_layout)
    sid = "bpm6.usd.bpm6_1.credit.current"
    with pytest.raises(SamError, match="USD_million"):
        ctx.value("external_sector_bop_bpm6_annual", sid, vintage="latest")
    v, _ = ctx.value("external_sector_bop_bpm6_annual", sid, vintage="latest", unit="USD_million")
    assert v > 0
    with pytest.raises(SamError, match="price_basis"):
        ctx.rows("mospi_nas_2026_s1_1", unit=None, vintage="latest")  # constant-price rows included
    with pytest.raises(SamError, match="item_code value"):
        ctx.rows("io_tables_sut_va", item_code="cee", vintage="latest")
    with pytest.raises(SamError, match="not in the dataset"):
        ctx.rows("mospi_nas_2026_s1_1", series_id="s1_1.gdp.curent", vintage="latest")
    with pytest.raises(SamError, match="no rows for period"):
        ctx.rows("mospi_nas_2026_s1_1", period="2023-2024", vintage="latest")
    with pytest.raises(SamError, match="vintage '2031-01-01' not found"):
        ctx.rows("mospi_nas_2026_s1_1", series_id="s1_1.gdp.current", vintage="2031-01-01")
    assert ctx.rows("io_tables_sut_va", item_code="ce", vintage="latest").height > 0


def test_official_record_over_a_dollar_input_needs_a_conversion(repo_layout):
    ctx = BlockContext(block="rest_of_world", refs=("R11",), depends=(), layout=repo_layout)
    sid = "bpm6.usd.bpm6_1.credit.current"
    _, pid = ctx.value("external_sector_bop_bpm6_annual", sid, vintage="latest", unit="USD_million")
    with pytest.raises(SamError, match="state the conversion"):
        ctx.prov(ref="R11", status="official", method="m", inputs=[pid])
    assert ctx.prov(ref="R11", status="official", method="m", inputs=[pid], conversion="USD million x INR/USD / 10")


def test_source_id_follows_the_inputs(repo_layout):
    """F3: the default source_id is the inputs' source; mixed sources need an explicit, matching one."""
    ctx = BlockContext(block="production", refs=("P1", "C1"), depends=(), layout=repo_layout)
    _, nas = ctx.value("mospi_nas_2026_s1_1", "s1_1.gdp.current", vintage="latest")
    sut = ctx.rows("io_tables_sut_va", item_code="ce", vintage="latest")["prov_id"][0]
    rec = ctx.provenance[ctx.prov(ref="P1", status="official", method="m", inputs=[sut])]
    assert rec["source_id"] == ctx.clean_index.prov(sut)["source_id"]
    with pytest.raises(SamError, match="several sources"):
        ctx.prov(ref="P1", status="official", method="m2", inputs=[sut, nas])
    with pytest.raises(SamError, match="not the source of any input"):
        ctx.prov(ref="P1", status="official", method="m3", inputs=[sut], source_id="mospi_nas_2026_publication")
    assert ctx.prov(ref="P1", status="official", method="m4", inputs=[sut, nas], source_id=rec["source_id"])


def test_entries_and_satellites_cite_records_of_their_own_ref(tmp_layout):
    """F5: an entry of ref K4a cannot cite a record made for D1; a record for another block's ref may back
    a constraint."""

    def build(ctx):
        return BlockResult(entries=[_ok_entry(ctx, ref="K4a", row="K_HH", col="H_R1", value=-3.0)])

    r, _ = _run(build, tmp_layout)
    assert not r.ok and "record made for ref D1" in r.message

    def build2(ctx):
        foreign = _est(ctx, "P1")  # production's ref: fine for a constraint
        c = constraint("c", "P1", ["A_CROP"], ["C_CROP"], 1.0, prov_id=foreign, tol_abs=1.0, description="x")
        return BlockResult(entries=[_ok_entry(ctx)], constraints=[c])

    r, _ = _run(build2, tmp_layout)
    assert r.ok, r.message


def test_a_nonzero_constraint_over_a_structurally_zero_selection_is_rejected(tmp_layout):
    """F7: HH <- DISC can hold no entry, so a target of 1e6 there can never be met."""

    def build(ctx, target):
        c = constraint("c", "D1", ["H_R1"], ["X_DISC"], target, prov_id=_est(ctx), description="x")
        return BlockResult(entries=[_ok_entry(ctx)], constraints=[c])

    r, _ = _run(lambda ctx: build(ctx, 1e6), tmp_layout)
    assert not r.ok and "structure.yaml" in r.message
    r, _ = _run(lambda ctx: build(ctx, 0.0), tmp_layout)  # a zero target documents that a use does not exist
    assert r.ok, r.message


def test_a_check_target_cannot_be_a_typed_in_number(tmp_layout):
    """F9: a check's target must come from data (a clean record, or an official/derived SAM record)."""

    def build(ctx):
        ctx.check("c", "typed in", 1.0, 123456.0, target_prov_id=_est(ctx), tol_abs=1.0)
        return BlockResult(entries=[_ok_entry(ctx)])

    r, _ = _run(build, tmp_layout)
    assert not r.ok and "never typed in" in r.message


def test_a_rebuilt_dependency_marks_its_dependents_stale(tmp_layout):
    """F8: households read production; rebuilding production afterwards makes households stale."""
    from pipeline.sam.framework import SamPaths, stale_dependents

    def prod(ctx, text):
        pid = ctx.prov(ref="P1", status="estimated", method=text, notes=NOTE, vintage="2026-08-31")
        e = entry("A_CROP", "C_CROP", "P1", 5.0, prov_id=pid, status="estimated", role="free", confidence="low")
        return BlockResult(entries=[e])

    def hh(ctx):
        ctx.block_entries("production")
        pid = ctx.prov(ref="C1a", status="estimated", method="m", notes=NOTE, vintage="2026-08-31")
        e = entry("C_CROP", "H_R1", "C1a", 5.0, prov_id=pid, status="estimated", role="free", confidence="low")
        return BlockResult(entries=[e])

    assert build_block_module(_mod(lambda c: prod(c, "v1"), "production", ("P1",)), tmp_layout)[0].ok
    assert build_block_module(_mod(hh, "households", ("C1a",), ("production",)), tmp_layout)[0].ok
    paths = SamPaths(tmp_layout)
    assert stale_dependents(paths) == []
    assert build_block_module(_mod(lambda c: prod(c, "v2"), "production", ("P1",)), tmp_layout)[0].ok
    assert stale_dependents(paths) == ["households (read production before it was rebuilt)"]


def test_latest_vintage_orders_partial_dates_like_prov():
    """F11: '2026' means up to 2026-12-31, later than '2026-02-27' (as ctx.prov orders vintages)."""
    df = pl.DataFrame(
        {"series_id": ["s", "s"], "period": ["2023-24"] * 2, "vintage": ["2026", "2026-02-27"], "value": [1.0, 2.0]}
    )
    assert select_vintage(df, "latest", "x")["value"].to_list() == [1.0]
