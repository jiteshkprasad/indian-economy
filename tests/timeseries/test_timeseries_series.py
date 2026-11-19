"""The top-flows time series (DESIGN_BRIEF s.8; plan docs/phase2/plans/timeseries.md s.7): schema, provenance,
reproduction from clean data, the joins that justify the no-splice precedence, continuity and break flags, the
linked variant, signs, coverage and identities. Expected values are recomputed from data/clean in the test
(polars), never typed in; the only literals are the plan's rules (tolerances, counts, whitelists)."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys

import polars as pl
import pytest
from _ts_helpers import LAYOUT, TS_DIR, clean_prov, fy_start, output, series, series_base, value

from pipeline.core import io
from pipeline.core.io import canonical_floats, parquet_bytes
from pipeline.core.manifest import build_manifest
from pipeline.core.paths import REPO_ROOT
from pipeline.core.schema import PROV_SCHEMA
from pipeline.timeseries import build as ts

pytestmark = pytest.mark.sam

OLD, NEW = "2011-12", "2022-23"
# plan s.2.5: the flows whose linked_2022_23 variant the data allow (checked again below from the rows)
LINK_WHITELIST = {"M01", "M02", "F01", "F03", "M03", "F05", "F06", "F07", "M06", "F37"}
# plan s.2.1, typed from the plan (not from flows.yaml): segment code -> the clean datasets it may read
PLAN_SEGMENTS = {
    "NB": r"mospi_nas_2026_api_b2011_back",
    "NO": r"mospi_nas_2026_oldbase_nas2025_s(1_1|1_9|1_14|5_3)",
    "NA": r"mospi_nas_2026_api_b2011_annual",
    "NS": r"mospi_nas_2026_oldbase_soa_s(1_15|4_0)",
    "NN": r"mospi_nas_2026_(s1_1|s1_9|s1_11|s1_14|s5_3|s6_1|s7_1|derived_residuals)",
    "NP": r"mospi_nas_2026_api_b2022_annual",
    "T12": r"rbi_financial_accounts_hbs_saving",
    "BI": r"external_sector_invisibles_annual",
    "BO": r"external_sector_bop_overall_annual",
    "FI": r"external_sector_foreign_investment",
    "NR": r"external_sector_nri_deposits",
    "FT": r"state_fiscal_fc16_transfers",
    "AT": r"state_fiscal_rbi_sf_app_tables",
    "KF": r"state_fiscal_fc16_kfi",
    "RB": r"union_fiscal_rb_receipts",
    "AF": r"union_fiscal_afs",
    "EP": r"union_fiscal_exp_profile",
    "FS": r"state_fiscal_fc16_subsidies",
    "RS": r"rbi_banking_corporate_rbi_surplus_timing",
    "FF": r"rbi_financial_accounts_fsf_instrument_sector",
}
# RBI HBS Table 12 flows (plan s.2.2 / s.2.3): before 2011-12 their rows splice earlier bases (TSV-2)
T12_FLOWS = {"F36", "F37", "F39", "F40", "F41", "F42", "M09"}


@pytest.fixture(scope="module")
def fresh() -> ts.TsResult:
    return ts.build(LAYOUT)


@pytest.fixture(scope="module")
def rows() -> pl.DataFrame:
    return output("top_flows.parquet")


@pytest.fixture(scope="module")
def defs() -> pl.DataFrame:
    return output("top_flows_definitions.parquet")


@pytest.fixture(scope="module")
def prov() -> pl.DataFrame:
    return output("_provenance.parquet")


def _v(rows: pl.DataFrame, flow: str, period: str, base: str | None = None, variant: str = "published") -> float:
    df = rows.filter((pl.col("flow_id") == flow) & (pl.col("period") == period) & (pl.col("variant") == variant))
    df = df.filter(pl.col("base_year").is_null() if base is None else pl.col("base_year") == base)
    assert df.height == 1, (flow, period, base, variant, df)
    return float(df["value"][0])


def _has(rows: pl.DataFrame, flow: str, period: str, base: str) -> bool:
    return bool(
        rows.filter((pl.col("flow_id") == flow) & (pl.col("period") == period) & (pl.col("base_year") == base)).height
    )


# ------------------------------------------------------------------------------------------------
# definitions and freshness
# ------------------------------------------------------------------------------------------------


def test_definitions_load_and_count():
    d = ts.load_definitions()
    tiers = [f.tier for f in d.flows]
    assert tiers.count("core") == 54 and tiers.count("memo") == 15  # plan s.2.2 / s.2.3 (~50 flows + memos)
    ex = ts.load_explanations()
    cd = {f.flow_id for f in d.flows if f.check_class in ("C", "D")}
    assert cd <= set(ex), f"class C/D flows without a registered bridge: {sorted(cd - set(ex))}"


def test_outputs_equal_a_fresh_build(fresh, rows, defs, prov):
    """The files on disk are what the current code builds from the current clean data (no stale outputs)."""
    assert rows.equals(canonical_floats(fresh.rows).sort(list(ts.ROW_KEY), nulls_last=True))
    want = canonical_floats(
        fresh.definitions, {"link_ratio_2022_23": 12, "link_ratio_2023_24": 12, "tol_abs": 6, "tol_rel": 12}
    ).sort("flow_id")
    assert defs.equals(want)
    assert output("top_flows_coverage.parquet").equals(canonical_floats(fresh.coverage).sort("flow_id", "period"))
    assert prov.equals(fresh.provenance.sort("prov_id"))
    # the 2023-24 check table reads the SAM as it is now: stale after any `sam` or block rebuild (TSV-6)
    chk = canonical_floats(fresh.check, {"rel_diff": 12}).sort("flow_id")
    assert output("top_flows_sam_check.parquet").equals(chk), "stale check table: re-run `timeseries`"
    assert sorted(p.name for p in TS_DIR.iterdir() if p.is_file()) == sorted(ts.OUT_FILES)


def test_manifest_covers_the_time_series():
    files = build_manifest(LAYOUT)["files"]
    for name in ts.OUT_FILES:
        assert f"data/timeseries/{name}" in files


def test_build_is_independent_of_the_hash_seed(fresh):
    """Byte-identical outputs under another PYTHONHASHSEED (repro also checks 1 vs 4 threads)."""
    code = (
        "import hashlib; from pipeline.core.paths import Layout; from pipeline.core.io import parquet_bytes; "
        "from pipeline.timeseries import build as ts; r = ts.build(Layout.default()); "
        "print(hashlib.sha256(parquet_bytes(r.rows, sort_by=ts.ROW_KEY)).hexdigest(), "
        "hashlib.sha256(parquet_bytes(r.provenance, sort_by=('prov_id',))).hexdigest())"
    )
    env = {**os.environ, "PYTHONHASHSEED": "1"}
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    here = (
        hashlib.sha256(parquet_bytes(fresh.rows, sort_by=ts.ROW_KEY)).hexdigest(),
        hashlib.sha256(parquet_bytes(fresh.provenance, sort_by=("prov_id",))).hexdigest(),
    )
    assert tuple(out.stdout.split()) == here


# ------------------------------------------------------------------------------------------------
# schema
# ------------------------------------------------------------------------------------------------


def test_schema(rows, defs):
    assert dict(rows.schema) == ts.ROW_DTYPES
    assert dict(defs.schema) == ts.DEF_DTYPES
    assert dict(output("top_flows_coverage.parquet").schema) == ts.COVERAGE_DTYPES
    assert dict(output("top_flows_sam_check.parquet").schema) == ts.CHECK_DTYPES
    assert rows.select(ts.ROW_KEY).is_unique().all(), "(flow_id, variant, base_year, period) must be unique"
    assert set(rows["unit"]) == {"INR_crore"} and set(rows["price_basis"]) == {"current"}
    assert set(rows["period_type"]) == {"fy"}
    assert set(rows["status"]) <= {"official", "derived"}, "nothing is estimated in the time series"
    assert set(rows["variant"]) <= set(ts.VARIANTS)
    assert set(rows["base_year"].drop_nulls()) <= {OLD, NEW}
    assert all(math.isfinite(v) for v in rows["value"])
    assert set(rows["flow_id"]) == set(defs["flow_id"])
    periods = rows["period"].unique().to_list()
    assert all((fy_start(p) + 1) % 100 == int(p[5:]) for p in periods)
    assert max(periods, key=fy_start) == "2025-26", "the last complete FY"
    assert not rows.filter(pl.col("estimate_stage").is_in(["BE", "RE"])).height, "budget estimates are never used"
    flags = {f for s in rows["flags"].drop_nulls() for f in s.split(",")}
    assert flags <= set(ts.FLAGS)


def test_base_year_rules(rows):
    """Every NAS row has a base_year, base-less rows (BoP, fiscal, FSF, and RBI HBS Table 12 before 2011-12,
    which splices earlier bases) have none; both bases are present wherever old- and new-base segments overlap
    (2022-23, and 2023-24 unless the old base ends earlier)."""
    nas = rows.filter(pl.col("datasets").str.starts_with("mospi_nas_2026"))
    assert nas["base_year"].null_count() == 0
    other = rows.filter(~pl.col("datasets").str.starts_with("mospi_nas_2026"))
    assert (
        other.filter(pl.col("variant") != ts.LINK_VARIANT)["base_year"].null_count()
        == other.filter(pl.col("variant") != ts.LINK_VARIANT).height
    )
    assert rows.filter((pl.col("segment") == "T12") & pl.col("base_year").is_not_null()).height == 0
    main = rows.filter(pl.col("variant") == "published")
    for flow in sorted(set(main["flow_id"])):
        f = main.filter(pl.col("flow_id") == flow)
        old = set(f.filter(pl.col("base_year") == OLD)["period"])
        new = set(f.filter(pl.col("base_year") == NEW)["period"])
        if old and new:
            assert "2022-23" in old & new, flow
            if "2023-24" in old:
                assert "2023-24" in new, flow


def test_row_base_year_is_the_base_year_of_its_clean_inputs(rows):
    """Independent of flows.yaml (TSV-8): every non-linked row's base_year equals the base_year of each clean
    record it is computed from (read from data/clean with the same selection rules)."""
    bad = []
    for r in rows.filter(pl.col("variant") != ts.LINK_VARIANT).iter_rows(named=True):
        for sid in r["series_ids"].split(","):
            b = series_base(r["datasets"], sid)[r["period"]]
            if b != r["base_year"]:
                bad.append((r["flow_id"], r["segment"], r["period"], r["base_year"], b))
    assert not bad, bad[:10]


def test_segment_codes_and_datasets_follow_plan_2_1(rows, prov):
    """Independent of flows.yaml (TSV-1, TSV-8): every segment code is a plan s.2.1 code and every row reads a
    dataset of that code; the provenance records name the same codes."""
    for r in rows.select("segment", "datasets", "variant").unique().iter_rows(named=True):
        code = r["segment"].removeprefix("LINK:") if r["variant"] == ts.LINK_VARIANT else r["segment"]
        assert code in PLAN_SEGMENTS, r
        assert re.fullmatch(PLAN_SEGMENTS[code], r["datasets"]), r
    for t in prov["table_id"]:
        code = t.split(" segment ")[1] if " segment " in t else None
        assert code is None or code in PLAN_SEGMENTS, t


def test_loader_rejects_names_that_are_not_strings(tmp_path):
    """TSV-1: YAML 1.1 reads an unquoted NO as False; the loader must refuse it rather than write 'False'."""
    text = ts.FLOWS_YAML.read_text(encoding="utf-8")
    assert '{code: "NO", ' in text
    bad = tmp_path / "flows.yaml"
    bad.write_text(text.replace('{code: "NO", ', "{code: NO, ", 1), encoding="utf-8", newline="\n")
    with pytest.raises(ts.TsError, match="segment code False is not a string"):
        ts.load_definitions(bad)
    doc = io.read_yaml(ts.FLOWS_YAML)
    codes = {s["code"] for f in doc["flows"] for s in f["segments"]}
    assert all(isinstance(c, str) for c in codes) and codes <= set(PLAN_SEGMENTS)


def test_unknown_revision_round_is_an_error():
    """TSV-9: a NAS API revision round outside ROUNDS_LATEST cannot be ordered: the build must stop, not fall
    back silently to an older round."""
    defs = ts.load_definitions()
    f33 = next(f for f in defs.flows if f.flow_id == "F33")
    seg = next(s for s in f33.segments if s.code == "NA")
    term = seg.terms[0]
    reader = ts.Reader(ts.CleanIndex(LAYOUT))
    assert ts.read_term(reader, defs, seg, term, "F33 NA")  # today every round is known
    df = reader.frame(seg.dataset)
    extra = df.filter(pl.col("series_id").is_in(list(term.series))).head(1)
    assert extra.height == 1
    extra = extra.with_columns(pl.lit(term.template.format(round="fourth_revised_estimates")).alias("series_id"))
    reader.frames[seg.dataset] = pl.concat([df, extra])
    with pytest.raises(ts.TsError, match="fourth_revised_estimates"):
        ts.read_term(reader, defs, seg, term, "F33 NA")


# ------------------------------------------------------------------------------------------------
# provenance
# ------------------------------------------------------------------------------------------------


def test_provenance(rows, prov):
    PROV_SCHEMA.validate(prov)
    assert set(prov["ingest_unit"]) == {"timeseries"}
    own = {r["prov_id"]: r for r in prov.iter_rows(named=True)}
    cp = clean_prov()
    assert set(rows["prov_id"]) <= set(own), "every row cites a time-series record"
    assert set(own) <= set(rows["prov_id"]), "no unused records"
    for r in own.values():
        assert r["method"] and r["inputs"], r["prov_id"]
        ins = r["inputs"].split(",")
        recs = [own.get(i) or cp.get(i) for i in ins]
        assert all(x is not None for x in recs), f"{r['prov_id']}: unresolved inputs"
        if r["status"] == "official":
            assert all(x["status"] == "official" for x in recs), r["prov_id"]
    st = rows.select("prov_id", "status").unique(maintain_order=True)
    for pid, s in st.iter_rows():
        assert own[pid]["status"] == s, pid
    # derived rows name the method (sign flips, differences, links)
    for pid in rows.filter(pl.col("status") == "derived")["prov_id"].unique().to_list():
        assert own[pid]["method"].strip()


def test_rows_reproduce_their_clean_sources(rows, defs):
    """T1: every non-linked row equals the sum of coef x clean value of the series it names, with the latest
    vintage of that period (BE/RE excluded), and cites those clean records through its provenance record."""
    prov = {r["prov_id"]: r for r in output("_provenance.parquet").iter_rows(named=True)}
    coef: dict[tuple[str, str], dict[str, float]] = {}
    for d in defs.iter_rows(named=True):
        for s in json.loads(d["segments"]):
            coef[(d["flow_id"], s["code"])] = {t["series"]: t["coef"] for t in s["terms"]}
    for r in rows.filter(pl.col("variant") != ts.LINK_VARIANT).iter_rows(named=True):
        cf = coef[(r["flow_id"], r["segment"])]
        total, pids = 0.0, []
        for sid in r["series_ids"].split(","):
            label = sid if sid in cf else next(k for k in cf if "{round}" in k and k.split("{round}")[0] in sid)
            v, _vint, pid = series(r["datasets"], sid)[r["period"]]
            total += cf[label] * v
            pids.append(pid)
        assert abs(r["value"] - total) <= 1e-6 * max(1.0, abs(total)), (r["flow_id"], r["period"], r["value"], total)
        assert set(pids) <= set(prov[r["prov_id"]]["inputs"].split(",")), (r["flow_id"], r["period"])


def test_plan_examples(rows):
    assert _v(rows, "F23", "2023-24") == value(
        "state_fiscal_rbi_sf_app_tables", "at2.i-states_share_in_central_taxes.actuals", "2023-24"
    )
    assert _v(rows, "F36", "1990-91", None) == value(
        "rbi_financial_accounts_hbs_saving", "t12.assets.financial_assets.current", "1990-91"
    )
    want = value("mospi_nas_2026_api_b2011_back", "api.gcf_incl_errors_omissions.current", "1950-51") - value(
        "mospi_nas_2026_api_b2011_back", "api.gross_saving.current", "1950-51"
    )
    assert abs(_v(rows, "F49", "1950-51", OLD) - want) < 1e-6


def test_sign_flips_and_differences_are_derived(rows, defs):
    """A segment with any coefficient other than +1 (sign flips, differences) is derived, never official."""
    n = 0
    for d in defs.iter_rows(named=True):
        for s in json.loads(d["segments"]):
            if any(t["coef"] != 1 for t in s["terms"]):
                f = rows.filter((pl.col("flow_id") == d["flow_id"]) & (pl.col("segment") == s["code"]))
                assert f.height and set(f["status"]) == {"derived"}, (d["flow_id"], s["code"])
                n += 1
    assert n >= 8  # F13 (2), F30 (2), F49 NB, F54, M07 (2), M09 T12, M14 RB


# ------------------------------------------------------------------------------------------------
# T2: joins without splices are real equalities (they justify the precedence of plan s.2.1)
# ------------------------------------------------------------------------------------------------


def _max_gap(a: dict, b: dict, periods) -> float:
    return max(abs(a[p][0] - b[p][0]) for p in periods)


def test_t12_equals_old_base_nas_5_3():
    s53 = "mospi_nas_2026_oldbase_nas2025_s5_3"
    years = [ts.fy(y) for y in range(2011, 2024)]
    pairs = [
        ("t12.assets.financial_assets.current", ["gross_financial_saving"]),
        ("t12.liabilities.financial_liabilities.current", ["financial_liabilities"]),
        ("t12.assets.currency.current", ["currency"]),
        ("t12.assets.shares_debentures.current", ["shares_and_debentures"]),
        ("t12.assets.pf_pension_fund.current", ["provident_and_pension_funds"]),
        ("t12.assets.life_insurance_fund.current", ["insurance_funds"]),
        ("t12.assets.bank_deposits.current", ["with_banks", "with_co_operative_banks_and_societies"]),
        ("t12.liabilities.bank_advances.current",
         ["bank_advances", "loans_and_advances_by_co_operative_banks_and_societies"]),
    ]  # fmt: skip
    for t12, items in pairs:
        a = series("rbi_financial_accounts_hbs_saving", t12)
        parts = [series(s53, f"oldbase_nas2025_s5_3.{i}.current") for i in items]
        for p in years:
            assert abs(a[p][0] - sum(x[p][0] for x in parts)) <= 1.0, (t12, p)


def test_fc16_transfers_equal_rbi_at2_until_2022_23_then_switch():
    for tsm, at2 in (
        ("tsm.states_share.actuals", "at2.i-states_share_in_central_taxes.actuals"),
        ("tsm.total_grants.actuals", "at2.ii-grants_from_the_centre.actuals"),
    ):
        a, b = series("state_fiscal_fc16_transfers", tsm), series("state_fiscal_rbi_sf_app_tables", at2)
        assert _max_gap(a, b, [ts.fy(y) for y in range(2007, 2023)]) <= 1.0, tsm
        assert abs(a["2023-24"][0] - b["2023-24"][0]) > 1.0, f"{tsm}: the 2023-24 switch (plan s.6.3 F1) is gone"


def test_back_series_joins_the_nas_2025_old_base_in_2011_12():
    back, s11 = "mospi_nas_2026_api_b2011_back", "mospi_nas_2026_oldbase_nas2025_s1_1"
    for b, o in (("gdp", "gdp"), ("pfce", "pfce"), ("gfce", "gfce"), ("gfcf", "gfcf"), ("exports", "exports"),
                 ("imports", "imports"), ("gva", "gva_basic")):  # fmt: skip
        assert abs(value(back, f"api.{b}.current", OLD) - value(s11, f"oldbase_nas2025_s1_1.{o}.current", OLD)) <= 5


def test_old_base_current_account_derivation_is_exact():
    s11, s19 = "mospi_nas_2026_oldbase_nas2025_s1_1", "mospi_nas_2026_oldbase_nas2025_s1_9"
    gcf, sav = series(s11, "oldbase_nas2025_s1_1.gcf.current"), series(s11, "oldbase_nas2025_s1_1.gross_saving.current")
    nci = series(s19, "oldbase_nas2025_s1_9.net_capital_inflow_from_row.current")
    for p in nci:
        assert abs(gcf[p][0] - sav[p][0] - nci[p][0]) <= 1.0, p
    back = "mospi_nas_2026_api_b2011_back"
    nb = value(back, "api.gcf_incl_errors_omissions.current", OLD) - value(back, "api.gross_saving.current", OLD)
    assert abs(nb - nci[OLD][0]) <= 1.0


def test_union_gross_tax_revenue_derivation_equals_fc16(rows):
    rb = "union_fiscal_rb_receipts"
    for p in ("2022-23", "2023-24"):
        d = (
            value(rb, "rb.tr.total.total_tax_revenue", p)
            - value(rb, "rb.tr.0710.less_states_share", p)
            - value(rb, "rb.tr.total.net_less_nccd_transferred_to_the_national_disaster_response_fund", p)
        )
        assert abs(d - value("state_fiscal_fc16_transfers", "tsm.gtr.actuals", p)) <= 1.0, p
    assert rows.filter((pl.col("flow_id") == "M14") & (pl.col("period") == "2024-25"))["segment"].to_list() == ["RB"]


def test_bop_sources_agree_where_they_are_joined():
    fi = series("external_sector_foreign_investment", "t143.inr.fdi_to_india_net.current")
    bo = series("external_sector_bop_overall_annual", "bop_old.inr.ka.fdi.in_india.net.current")
    assert _max_gap(fi, bo, bo.keys()) <= 1.0
    inv, s61 = "external_sector_invisibles_annual", "mospi_nas_2026_s6_1"
    s61_rec = "s6_1.other_current_transfers_to_resident_sectors_other_than_gener.current"
    s61_pay = "s6_1.other_current_transfers_by_resident_sectors_other_than_gener.current"
    s61_inc = "s6_1.property_and_entrepreneurial_income_to_the_rest_of_the_world.current"
    for a, b in (
        ("invis.inr.private_transfers.receipts.current", s61_rec),
        ("invis.inr.private_transfers.payments.current", s61_pay),
        ("invis.inr.income.investment.payments.current", s61_inc),
    ):
        x, y = series(inv, a), series(s61, b)
        assert _max_gap(x, y, y.keys()) <= 1.0, a  # BoP is published rounded to the crore


def test_fertiliser_subsidy_sources_are_the_same_measure():
    fs = series("state_fiscal_fc16_subsidies", "sub.fertilizer.in.gg_centre")
    ep = series("union_fiscal_exp_profile", "stat7.fertiliser")
    assert _max_gap(fs, ep, ["2022-23", "2023-24"]) <= 1.0


# ------------------------------------------------------------------------------------------------
# continuity, breaks and the linked variant
# ------------------------------------------------------------------------------------------------


def test_series_are_continuous_within_base_and_variant(rows):
    for (flow, base, variant), g in rows.group_by(["flow_id", "base_year", "variant"], maintain_order=True):
        ys = sorted(fy_start(p) for p in g["period"])
        assert ys == list(range(ys[0], ys[-1] + 1)), f"{flow} base {base} {variant}: gap in {ys}"


def test_break_flags(rows, defs):
    main = rows.filter(pl.col("variant") == "published")
    both = (
        main.filter(pl.col("base_year").is_not_null())
        .group_by(["flow_id", "period"], maintain_order=True)
        .agg(pl.col("base_year").n_unique().alias("n"))
        .filter(pl.col("n") == 2)
    )
    want = {(f, p) for f, p, _ in both.iter_rows()}
    flagged = main.filter(pl.col("flags").fill_null("").str.contains("base_overlap"))
    got = set(zip(flagged["flow_id"], flagged["period"]))
    assert got == want, "base_overlap marks exactly the FYs with both NAS bases (the break stays visible)"
    assert ("F01", "2022-23") in want and ("F01", "2023-24") in want
    assert not rows.filter(
        (pl.col("variant") != "published") & pl.col("flags").fill_null("").str.contains("base_overlap")
    ).height
    # segment joins: the first FY of every segment that continues another in the same (base, variant)
    for d in defs.iter_rows(named=True):
        segs = json.loads(d["segments"])
        for s in segs:
            prev = [x for x in segs if x["base_year"] == s["base_year"] and x["variant"] == s["variant"]
                    and fy_start(x["to"]) + 1 == fy_start(s["from"])]  # fmt: skip
            r = rows.filter(
                (pl.col("flow_id") == d["flow_id"]) & (pl.col("segment") == s["code"]) & (pl.col("period") == s["from"])
                & (pl.col("variant") == s["variant"])
            )  # fmt: skip
            has = "segment_join" in (r["flags"][0] or "")
            assert has == bool(prev), (d["flow_id"], s["code"])
        for b in json.loads(d["breaks"] or "[]"):
            r = main.filter((pl.col("flow_id") == d["flow_id"]) & (pl.col("period") == b["period"]))
            assert r.height and all("concept_break" in (x or "") for x in r["flags"]), (d["flow_id"], b)
    assert json.loads(defs.filter(pl.col("flow_id") == "F18")["breaks"][0])[0]["period"] == "2017-18"
    # base_change (TSV-2): exactly where RBI HBS Table 12 (earlier bases, no base_year) hands over to the
    # old-base NAS 5.3 rows, in 2011-12, for the seven T12 flows; never in another variant
    got = {(f, p) for f, p, fl in rows.select("flow_id", "period", "flags").iter_rows() if "base_change" in (fl or "")}
    assert got == {(f, "2011-12") for f in T12_FLOWS}
    t12 = main.filter(pl.col("segment") == "T12")
    assert set(t12["flow_id"]) == T12_FLOWS and t12["period"].max() == "2010-11"


def test_linked_variant(rows, defs):
    linked = set(defs.filter(pl.col("link_policy") == "linked")["flow_id"])
    assert linked == LINK_WHITELIST
    assert set(rows.filter(pl.col("variant") == ts.LINK_VARIANT)["flow_id"]) == linked
    main = rows.filter(pl.col("variant") == "published")
    for d in defs.iter_rows(named=True):
        f = d["flow_id"]
        old = {p: _v(rows, f, p, OLD) for p in ("2022-23", "2023-24") if _has(rows, f, p, OLD)}
        new = {p: _v(rows, f, p, NEW) for p in old if _has(rows, f, p, NEW)}
        if "2022-23" in new:
            assert abs(d["link_ratio_2022_23"] - new["2022-23"] / old["2022-23"]) < 1e-9, f
        # TSV-5: the plan s.2.5 data rules are evaluated for every flow, recomputed here from the rows
        fm = main.filter((pl.col("flow_id") == f) & pl.col("base_year").is_in([OLD, NEW]))
        if not (set(fm["base_year"]) >= {OLD, NEW}):
            assert d["link_rules"].startswith("not applicable"), f
        else:
            ok = len(new) == 2 and abs(new["2022-23"] / old["2022-23"] - new["2023-24"] / old["2023-24"]) <= 0.02
            ok = ok and len({v > 0 for v in fm["value"] if v != 0}) == 1
            assert d["link_rules"].startswith("met" if ok else "not met"), (f, d["link_rules"])
            if ok and f not in linked:
                assert "unstable" not in d["link_reason"].lower(), f"{f}: refused as unstable, but the rules hold"
        if f not in linked:
            assert d["link_reason"], f"{f}: a refused link states why"
            continue
        r22, r23 = new["2022-23"] / old["2022-23"], new["2023-24"] / old["2023-24"]
        assert abs(r22 - r23) <= 0.02, f
        lk = rows.filter((pl.col("flow_id") == f) & (pl.col("variant") == ts.LINK_VARIANT))
        assert set(lk["status"]) == {"derived"} and set(lk["base_year"]) == {NEW}
        assert max(lk["period"], key=fy_start) == "2021-22"
        for r in lk.iter_rows(named=True):
            assert abs(r["value"] - _v(rows, f, r["period"], OLD) * r22) <= 1e-6 * max(1, abs(r["value"]))


# ------------------------------------------------------------------------------------------------
# signs, coverage, identities
# ------------------------------------------------------------------------------------------------


def test_signs(rows):
    assert rows.filter(pl.col("flow_id").is_in(["F13", "F30"]) & (pl.col("value") > 0)).height == 0
    bop = value("external_sector_bop_overall_annual", "bop_old.inr.monetary_movements.reserves.net.current", "2023-24")
    assert _v(rows, "F54", "2023-24") == -bop and _v(rows, "F54", "2023-24") > 0  # reserves rose in 2023-24


def test_coverage_matrix(rows):
    cov = output("top_flows_coverage.parquet")
    main = rows.filter(pl.col("variant") == "published")
    n = main.group_by(["flow_id", "period"], maintain_order=True).len()
    assert cov.height == n.height
    assert cov.join(n, on=["flow_id", "period"]).filter(pl.col("n_rows") != pl.col("len")).height == 0
    core = cov.filter(pl.col("tier") == "core").group_by("period", maintain_order=True).len()
    counts = dict(core.iter_rows())
    # plan s.2.6: all 54 core flows exist together only in 2022-23 and 2023-24
    assert (counts["2022-23"], counts["2023-24"], counts["2024-25"], counts["2025-26"]) == (54, 54, 42, 12)
    assert counts["2011-12"] == 38 and counts["1950-51"] == 5


def test_identities_on_the_new_base(rows):
    """T5 (new base 2022-23..2024-25, within Rs 5 crore)."""
    s11, s61, s71, s53 = "mospi_nas_2026_s1_1", "mospi_nas_2026_s6_1", "mospi_nas_2026_s7_1", "mospi_nas_2026_s5_3"
    for p in ("2022-23", "2023-24", "2024-25"):
        v = {f: _v(rows, f, p, NEW) for f in ("F01", "F02", "F03", "F04", "F05", "F06", "F07", "F08", "F09", "F10",
                                            "F35", "F36", "F37", "F39", "F40", "F41", "M01", "M02", "M03", "M04",
                                            "M05", "M06", "M09", "M10", "M12", "M13")}  # fmt: skip
        disc = value(s11, "s1_1.discrepancies.current", p)
        assert abs(v["M01"] - (v["F01"] + v["F02"] + v["F03"] + v["M10"] + v["F04"] + v["M03"] - v["M04"] + disc)) <= 5
        assert abs(v["M03"] - v["F05"] - v["F06"]) <= 5
        assert abs(v["M04"] - v["F07"] - v["F08"]) <= 5
        assert abs(v["M06"] - v["M04"] - v["M05"]) <= 5, (p, value(s61, "s6_1.imports.current", p))
        assert abs(v["M02"] - v["F09"] - v["F10"] - value(s71, "s7_1.total.net_production_taxes.current", p)) <= 5
        assert abs(v["M09"] - (v["F36"] - v["F37"])) <= 5
        assert abs(v["M13"] - (v["F01"] + v["F35"] + v["M12"])) <= 5
        others = sum(
            value(s53, f"s5_3.{i}.current", p)
            for i in ("with_non_banking_companies", "trade_debt_net", "currency", "claims_on_government")
        )
        assert abs(v["F36"] - (v["F39"] + others + v["F40"] + v["F41"])) <= 5, p
    for p in [ts.fy(y) for y in range(2011, 2024)]:
        assert abs(_v(rows, "M03", p, OLD) - _v(rows, "F05", p, OLD) - _v(rows, "F06", p, OLD)) <= 5
