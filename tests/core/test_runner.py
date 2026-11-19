"""End-to-end runner behaviour with an in-memory fake unit (no network, tmp data tree)."""

import json
import os
import sys
import types
from pathlib import Path

import polars as pl
import pytest

from pipeline.core import fetch as F
from pipeline.core.manifest import read_manifest
from pipeline.core.runner import build_module, fetch_module
from pipeline.core.unit import BuildContext, Dataset, UnitError, check_contract

pytestmark = pytest.mark.unit
SRC = "mospi_nas_2026_publication"
CSV = b"period,value\n2022-23,1.5\n2023-24,-0.0000001\n"


@pytest.fixture(autouse=True)
def fake_http(monkeypatch):
    def fake(layout, url, **kw):
        return F.Response(200, url, "text/csv", CSV, {"content-type": "text/csv"}, {"User-Agent": "x"}, 1)

    monkeypatch.setattr(F, "http_request", fake)


def rows(ctx: BuildContext, *, status="official", method=None, source=SRC):
    raw = ctx.raw(SRC, "demo.csv")
    pid = ctx.prov(
        raw=raw,
        table_id="Demo table",
        locator="demo.csv, all rows",
        unit_as_published="Rs lakh crore",
        conversion="INR_lakh_crore -> INR_crore: x 100000",
        price_basis="current",
        vintage="2026-08-31",
        release="Demo release",
        status=status,
        method=method,
    )
    src = pl.read_csv(raw.path)
    return pl.DataFrame(
        {
            "series_id": "t.x.current",
            "source_id": source,
            "table_id": "Demo table",
            "item_code": "x",
            "item_label": "Demo item",
            "stock_flow": "flow",
            "period": src["period"],
            "period_type": "fy",
            "value": src["value"] * 1e5,
            "unit": "INR_crore",
            "price_basis": "current",
            "vintage": "2026-08-31",
            "estimate_stage": "Final",
            "status": status,
            "prov_id": pid,
        }
    )


def make_unit(build, name="demo_unit"):
    mod = types.ModuleType(name)
    mod.UNIT = name
    mod.SOURCES = [SRC]
    mod.fetch = lambda ctx: ctx.fetch(SRC, "https://example.org/demo.csv", name="demo.csv")
    mod.build = build
    return mod


def ok_build(ctx):
    return [Dataset("demo_unit_t", rows(ctx), "demo")]


def D(name, df):  # noqa: N802 - a described Dataset, for brevity
    return Dataset(name, df, "demo")


def test_fetch_then_build_writes_clean_provenance_catalog_and_manifest(tmp_layout):
    mod = make_unit(ok_build)
    assert fetch_module(mod, tmp_layout).ok
    r = build_module(mod, tmp_layout)
    assert r.ok, r.message
    out = tmp_layout.clean / "demo_unit"
    df = pl.read_parquet(out / "demo_unit_t.parquet")
    assert df["dataset"].unique().to_list() == ["demo_unit_t"]
    assert df["value"].to_list() == [150000.0, -0.01]
    prov = pl.read_parquet(out / "_provenance.parquet")
    assert prov.height == 1 and prov["raw_sha256"][0] == F.io.sha256_bytes(CSV)
    catalog = json.loads((out / "_datasets.json").read_text(encoding="utf-8"))
    assert catalog == {"demo_unit_t": {"description": "demo", "rows": 2, "source_ids": [SRC]}}
    m = read_manifest(tmp_layout.manifest)
    assert set(m["files"]) == {
        "data/clean/demo_unit/demo_unit_t.parquet",
        "data/clean/demo_unit/_provenance.parquet",
        "data/clean/demo_unit/_datasets.json",
    }
    assert m["raw_pins"]["demo_unit"][f"{SRC}/demo.csv"] == F.io.sha256_bytes(CSV)
    first = tmp_layout.manifest.read_bytes()
    assert build_module(mod, tmp_layout).ok
    assert tmp_layout.manifest.read_bytes() == first  # rebuild is byte-identical


def test_build_without_fetch_fails_loudly(tmp_layout):
    r = build_module(make_unit(ok_build), tmp_layout)
    assert not r.ok and "OfflineMissing" in r.message


@pytest.mark.parametrize(
    "build, needle",
    [
        (lambda ctx: [D("other_name", rows(ctx))], "must be snake_case and equal"),
        (lambda ctx: [Dataset("demo_unit_t", rows(ctx))], "description is required"),
        (
            lambda ctx: [D("demo_unit_t", rows(ctx).with_columns(pl.lit("demo_unit:0123456789ab").alias("prov_id")))],
            "not registered",
        ),
        (
            lambda ctx: [D("demo_unit_t", rows(ctx).with_columns(pl.lit("estimated").alias("status")))],
            "differs from their provenance",
        ),
        (lambda ctx: [D("demo_unit_t", rows(ctx, source="rbi_hbs"))], "not in the unit's SOURCES"),
        (lambda ctx: [D("demo_unit_t", rows(ctx).head(0))], "empty dataset"),
        (lambda ctx: [D("demo_unit_t", rows(ctx)), D("demo_unit_t", rows(ctx))], "returned twice"),
        (lambda ctx: [], "non-empty list"),
        (lambda ctx: [D("demo_unit_t", rows(ctx).with_columns(pl.lit("lakh").alias("unit")))], "isin"),
        (lambda ctx: [D("demo_unit_t", rows(ctx).with_columns(pl.lit(1).alias("extra")))], "not in the clean schema"),
    ],
)
def test_contract_violations_fail_and_write_nothing(tmp_layout, build, needle):
    assert fetch_module(make_unit(build), tmp_layout).ok
    r = build_module(make_unit(build), tmp_layout)
    assert not r.ok
    assert needle in r.message, r.message
    assert not (tmp_layout.clean / "demo_unit").exists()


def test_estimated_rows_need_a_method(tmp_layout):
    fetch_module(make_unit(ok_build), tmp_layout)
    r = build_module(make_unit(lambda ctx: [D("demo_unit_t", rows(ctx, status="estimated"))]), tmp_layout)
    assert not r.ok and "needs a method" in r.message
    good = make_unit(lambda ctx: [D("demo_unit_t", rows(ctx, status="estimated", method="Scaled by a share"))])
    assert build_module(good, tmp_layout).ok


def test_failed_rebuild_keeps_previous_output_and_stale_datasets_disappear(tmp_layout):
    mod = make_unit(lambda ctx: [D("demo_unit_t", rows(ctx)), D("demo_unit_u", rows(ctx))])
    fetch_module(mod, tmp_layout)
    assert build_module(mod, tmp_layout).ok
    assert (tmp_layout.clean / "demo_unit" / "demo_unit_u.parquet").exists()
    bad = make_unit(lambda ctx: [D("bad", rows(ctx))])
    assert not build_module(bad, tmp_layout).ok
    assert (tmp_layout.clean / "demo_unit" / "demo_unit_u.parquet").exists()  # untouched
    assert build_module(make_unit(ok_build), tmp_layout).ok
    assert not (tmp_layout.clean / "demo_unit" / "demo_unit_u.parquet").exists()  # full rebuild


def _consumer(ctx):
    """A unit that derives its numbers from another unit's clean data and cites its provenance."""
    dep = ctx.clean("demo_dep", "demo_dep_t")
    pid = ctx.prov(
        raw=None,
        source_id=SRC,
        table_id="Derived table",
        locator="computed from demo_dep_t",
        unit_as_published="n/a",
        price_basis="current",
        vintage="2026-08-31",
        release="Demo release",
        status="derived",
        method="Twice the demo_dep value",
        inputs=dep["prov_id"].unique().to_list(),
    )
    df = rows(ctx).with_columns(
        pl.lit(pid).alias("prov_id"), pl.lit("derived").alias("status"), (dep["value"] * 2).alias("value")
    )
    return [D("demo_unit_t", df)]


def test_depends_and_foreign_provenance_inputs(tmp_layout):
    dep = make_unit(lambda ctx: [D("demo_dep_t", rows(ctx))], name="demo_dep")
    consumer = make_unit(_consumer)
    for m in (dep, consumer):
        assert fetch_module(m, tmp_layout).ok
    r = build_module(consumer, tmp_layout)
    assert not r.ok and "requires DEPENDS" in r.message
    consumer.DEPENDS = ["demo_dep"]
    r = build_module(consumer, tmp_layout)
    assert not r.ok and "build demo_dep first" in r.message
    assert build_module(dep, tmp_layout).ok
    r = build_module(consumer, tmp_layout)
    assert r.ok, r.message
    prov = pl.read_parquet(tmp_layout.clean / "demo_unit" / "_provenance.parquet")
    assert prov["prov_id"].str.starts_with("demo_unit:").all()  # foreign records checked, not copied
    assert prov["inputs"][0].startswith("demo_dep:")


def test_swap_failure_keeps_previous_output_and_leaves_no_debris(tmp_layout, monkeypatch):
    from pipeline.core import runner

    mod = make_unit(lambda ctx: [D("demo_unit_t", rows(ctx)), D("demo_unit_u", rows(ctx))])
    fetch_module(mod, tmp_layout)
    assert build_module(mod, tmp_layout).ok
    out = tmp_layout.clean / "demo_unit"
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    real = os.replace

    def refuse_first(src, dst):  # what Windows does when a file inside `out` is open elsewhere
        if Path(src) == out:
            raise PermissionError(32, "The process cannot access the file because it is being used")
        return real(src, dst)

    monkeypatch.setattr(runner.os, "replace", refuse_first)
    r = build_module(make_unit(ok_build), tmp_layout)
    assert not r.ok and "previous output is unchanged" in r.message
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before
    assert not [p for p in tmp_layout.clean.iterdir() if p.name.startswith(".demo_unit.")]


@pytest.mark.skipif(sys.platform != "win32", reason="POSIX allows renaming a folder with open files")
def test_open_file_in_output_on_windows(tmp_layout):
    mod = make_unit(ok_build)
    fetch_module(mod, tmp_layout)
    assert build_module(mod, tmp_layout).ok
    out = tmp_layout.clean / "demo_unit"
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    with open(out / "demo_unit_t.parquet", "rb"):
        two = make_unit(lambda ctx: [D("demo_unit_t", rows(ctx)), D("demo_unit_u", rows(ctx))])
        r = build_module(two, tmp_layout)
    if not r.ok:  # the usual outcome: the swap is refused and nothing changes
        assert "previous output is unchanged" in r.message
        assert {p.name: p.read_bytes() for p in out.iterdir()} == before
    else:  # the rename went through: the new output is complete
        assert (out / "demo_unit_u.parquet").exists()
    assert build_module(make_unit(ok_build), tmp_layout).ok  # a later build sweeps any debris
    assert not [p for p in tmp_layout.clean.iterdir() if p.name.startswith(".demo_unit.")]


def _prov_rows(ctx, *, unit="INR_crore", status="official", **prov_kw):
    raw = ctx.raw(SRC, "demo.csv")
    kw = dict(
        raw=raw,
        table_id="Demo table",
        locator="demo.csv",
        price_basis="current",
        vintage="2026-08-31",
        release="Demo release",
        status=status,
    )
    kw.update(prov_kw)
    pid = ctx.prov(**kw)
    return rows(ctx).with_columns(
        pl.lit(pid).alias("prov_id"), pl.lit(unit).alias("unit"), pl.lit(status).alias("status")
    )


@pytest.mark.parametrize(
    "prov_kw, needle",
    [
        (dict(unit_as_published="Rs lakh", conversion="none"), "conversion must be 'INR_lakh -> INR_crore: x 0.01'"),
        (dict(unit_as_published="Rs '000 crore", conversion="none"), "INR_thousand_crore"),
        (dict(unit_as_published="US$ million", conversion="none"), "INR_per_USD"),
        (dict(unit_as_published="per cent", conversion="none"), "rupee unit_as_published"),
        (dict(unit="USD_million", unit_as_published="Rs crore", conversion="none"), "rupee unit_as_published on"),
    ],
)
def test_row_units_must_agree_with_provenance(tmp_layout, prov_kw, needle):
    fetch_module(make_unit(ok_build), tmp_layout)
    unit = prov_kw.pop("unit", "INR_crore")
    r = build_module(make_unit(lambda ctx: [D("demo_unit_t", _prov_rows(ctx, unit=unit, **prov_kw))]), tmp_layout)
    assert not r.ok and needle in r.message, r.message


def test_consistent_units_pass(tmp_layout):
    fetch_module(make_unit(ok_build), tmp_layout)
    for uap, conv in (("Rs crore", "none"), ("(Rs. crore)", "none"), ("Rs lakh", "INR_lakh -> INR_crore: x 0.01")):
        r = build_module(
            make_unit(
                lambda ctx, u=uap, c=conv: [D("demo_unit_t", _prov_rows(ctx, unit_as_published=u, conversion=c))]
            ),
            tmp_layout,
        )
        assert r.ok, r.message


def test_dollar_rows_in_rupees_need_a_rate_series(tmp_layout):
    fetch_module(make_unit(ok_build), tmp_layout)

    def build(ctx):
        rate = _prov_rows(ctx, unit="INR_per_USD", unit_as_published="Rs per US$", conversion="none")
        rate = rate.with_columns(pl.lit("t.rate").alias("series_id"), pl.lit("rate").alias("item_code"))
        usd = _prov_rows(ctx, unit="USD_million", unit_as_published="US$ million", conversion="none")
        usd = usd.with_columns(pl.lit("t.usd").alias("series_id"), pl.lit("usd").alias("item_code"))
        pid = ctx.prov(
            raw=None,
            source_id=SRC,
            table_id="Demo table",
            locator="t.usd x t.rate",
            unit_as_published="US$ million",
            conversion="USD_million -> INR_crore: x rate / 10",
            price_basis="current",
            vintage="2026-08-31",
            release="Demo release",
            status="derived",
            method="usd_million_to_inr_crore",
            inputs=[usd["prov_id"][0], rate["prov_id"][0]],
        )
        inr = usd.with_columns(
            pl.lit("t.inr").alias("series_id"),
            pl.lit("inr").alias("item_code"),
            pl.lit("INR_crore").alias("unit"),
            pl.lit("derived").alias("status"),
            pl.lit(pid).alias("prov_id"),
        )
        return [D("demo_unit_t", pl.concat([rate, usd, inr]))]

    r = build_module(make_unit(build), tmp_layout)
    assert r.ok, r.message


def test_derived_and_estimated_records_must_be_traceable(tmp_layout):
    fetch_module(make_unit(ok_build), tmp_layout)
    common = dict(
        raw=None,
        source_id=SRC,
        table_id="Demo",
        locator="n/a",
        unit_as_published="Rs crore",
        price_basis="current",
        vintage="2026-08-31",
        release="none",
    )

    def derived(ctx):
        ctx.prov(**common, status="derived", method="I made it up")

    def estimated(ctx):
        ctx.prov(**common, status="estimated", method="x")

    for build, needle in ((derived, "derived provenance record needs `inputs`"), (estimated, "`notes` citing")):
        r = build_module(make_unit(build), tmp_layout)
        assert not r.ok and needle in r.message, r.message


def test_build_does_not_rebuild_dependencies_unless_asked(tmp_layout, monkeypatch):
    from pipeline.core import runner

    dep = make_unit(lambda ctx: [D("demo_dep_t", rows(ctx))], name="demo_dep")
    consumer = make_unit(_consumer)
    consumer.DEPENDS = ["demo_dep"]
    mods = {"demo_dep": dep, "demo_unit": consumer}
    monkeypatch.setattr(runner, "load_unit", lambda n, layout=None: mods[n])
    for m in mods.values():
        assert fetch_module(m, tmp_layout).ok
    res = {r.unit: r for r in runner.run("build", ["demo_unit"], tmp_layout)}
    assert set(res) == {"demo_unit"} and "has no clean output" in res["demo_unit"].message
    assert not (tmp_layout.clean / "demo_dep").exists()  # the other unit's folder was not written
    res = {r.unit: r for r in runner.run("build", ["demo_unit"], tmp_layout, with_deps=True)}
    assert res["demo_dep"].ok and res["demo_unit"].ok
    stamp = (tmp_layout.clean / "demo_dep" / "demo_dep_t.parquet").stat().st_mtime_ns
    res = {r.unit: r for r in runner.run("build", ["demo_unit"], tmp_layout)}
    assert set(res) == {"demo_unit"} and res["demo_unit"].ok
    assert (tmp_layout.clean / "demo_dep" / "demo_dep_t.parquet").stat().st_mtime_ns == stamp


def test_contract_checks():
    mod = make_unit(ok_build)
    check_contract(mod)
    mod.DEPENDS = ["demo_unit"]
    with pytest.raises(UnitError, match="itself"):
        check_contract(mod)
    mod.DEPENDS = []
    mod.SOURCES = ["not_a_registered_source"]
    with pytest.raises(KeyError):
        check_contract(mod)
    del mod.build
    mod.SOURCES = [SRC]
    with pytest.raises(UnitError, match="build"):
        check_contract(mod)


# ---------------------------------------------------------------------------------------------
# Phase 1 close-out (docs/phase1/FRAMEWORK_REQUESTS.md)
# ---------------------------------------------------------------------------------------------


def _share_rows(ctx, unit="percent", uap="per cent", price_basis="n/a"):
    raw = ctx.raw(SRC, "demo.csv")
    pid = ctx.prov(
        raw=raw,
        table_id="Demo table",
        locator="demo.csv",
        unit_as_published=uap,
        price_basis=price_basis,
        vintage="2026-08-31",
        release="Demo release",
    )
    base = rows(ctx).drop("value", "unit", "price_basis", "prov_id", "series_id")
    return base.with_columns(
        pl.lit("t.share").alias("series_id"),
        pl.Series("value", [0.000123456789123, 12.3456789123]),
        pl.lit(unit).alias("unit"),
        pl.lit(price_basis).alias("price_basis"),
        pl.lit(pid).alias("prov_id"),
    )


def test_ratio_sig_digits_keeps_small_shares_precise(tmp_layout):
    def build(ctx):
        return [
            Dataset("demo_unit_sig", _share_rows(ctx), "shares, 9 significant digits", ratio_sig_digits=9),
            Dataset("demo_unit_plain", _share_rows(ctx), "shares, default rounding"),
            Dataset("demo_unit_money", rows(ctx), "money rows, opted in but not percent/ratio", ratio_sig_digits=9),
        ]

    mod = make_unit(build)
    assert fetch_module(mod, tmp_layout).ok
    r = build_module(mod, tmp_layout)
    assert r.ok, r.message
    out = tmp_layout.clean / "demo_unit"
    assert pl.read_parquet(out / "demo_unit_sig.parquet")["value"].to_list() == [0.000123456789, 12.3456789]
    assert pl.read_parquet(out / "demo_unit_plain.parquet")["value"].to_list() == [0.000123, 12.345679]
    plain_money = pl.read_parquet(out / "demo_unit_money.parquet")["value"].to_list()
    assert plain_money == [150000.0, -0.01]  # INR_crore rows keep the default 6 decimals (and -0.0 -> 0.0 rule)
    cat = json.loads((out / "_datasets.json").read_text(encoding="utf-8"))
    assert cat["demo_unit_sig"]["ratio_sig_digits"] == 9 and "ratio_sig_digits" not in cat["demo_unit_plain"]


def test_unused_pins_are_reported_and_pruned_only_on_request(tmp_layout, capsys):
    mod = make_unit(ok_build)
    both = lambda ctx: [ctx.fetch(SRC, f"https://example.org/{n}", name=n) for n in ("demo.csv", "old.csv")]  # noqa: E731
    mod.fetch = both
    assert fetch_module(mod, tmp_layout).ok
    mod.fetch = lambda ctx: ctx.fetch(SRC, "https://example.org/demo.csv", name="demo.csv")
    assert fetch_module(mod, tmp_layout).ok
    assert "not requested by this run" in capsys.readouterr().out
    assert f"{SRC}/old.csv" in F.PinStore.load(tmp_layout, "demo_unit").pins  # reported, not removed
    r = fetch_module(mod, tmp_layout, prune=True)
    assert r.ok and "pruned 1" in r.message
    assert set(F.PinStore.load(tmp_layout, "demo_unit").pins) == {f"{SRC}/demo.csv"}


def test_prune_is_refused_after_a_run_with_warnings(tmp_layout):
    mod = make_unit(ok_build)
    mod.fetch = lambda ctx: [ctx.fetch(SRC, f"https://example.org/{n}", name=n) for n in ("demo.csv", "old.csv")]
    assert fetch_module(mod, tmp_layout).ok

    def warned(ctx):
        ctx.fetch(SRC, "https://example.org/demo.csv", name="demo.csv")
        ctx.warn("old.csv skipped: host challenged")

    mod.fetch = warned
    r = fetch_module(mod, tmp_layout, prune=True)
    assert r.ok and any("--prune skipped" in w for w in r.warnings)
    assert f"{SRC}/old.csv" in F.PinStore.load(tmp_layout, "demo_unit").pins


@pytest.mark.parametrize(
    "unit, uap, ok",
    [
        ("EUR_million", "EUR million", True),
        ("EUR_million", "Rs crore", False),  # rupee caption on euro rows
        ("INR_crore", "EUR million", False),  # euro shown as rupees: no INR_per_EUR series exists
    ],
)
def test_euro_rows_against_provenance(tmp_layout, unit, uap, ok):
    def build(ctx):
        return [D("demo_unit_eur", _share_rows(ctx, unit=unit, uap=uap, price_basis="current"))]

    mod = make_unit(build)
    assert fetch_module(mod, tmp_layout).ok
    r = build_module(mod, tmp_layout)
    assert r.ok == ok, r.message
    if not ok:
        assert "row units disagree with provenance" in r.message and ("euro" in r.message or "rupee" in r.message)
