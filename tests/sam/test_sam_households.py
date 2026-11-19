"""The households block: its built outputs match a fresh rebuild, reproduce the official totals it splits
(SUT / NAS PFCE by commodity, FISIM, dwellings, GFCE on grain) and follow the plan's rules (docs/phase2/plans/
households.md s.7 and s.8). Every expected value is recomputed here from data/clean with polars, never typed in."""

from __future__ import annotations

import math

import polars as pl
import pytest

from pipeline.core.io import canonical_floats
from pipeline.core.paths import Layout
from pipeline.sam import spec
from pipeline.sam.blocks import households
from pipeline.sam.framework import SamPaths, _sig, build_block_module

pytestmark = pytest.mark.sam

LAYOUT = Layout.default()
PATHS = SamPaths(LAYOUT)
YEAR = spec.YEAR
SURVEY = "2023-08/2024-07"
GROUPS = ["H_R1", "H_R2", "H_R3", "H_R4", "H_R5", "H_U1", "H_U2", "H_U3", "H_U4", "H_U5"]
QUINTILE = {
    "p00_05": 1,
    "p05_10": 1,
    "p10_20": 1,
    "p20_30": 2,
    "p30_40": 2,
    "p40_50": 3,
    "p50_60": 3,
    "p60_70": 4,
    "p70_80": 4,
    "p80_90": 5,
    "p90_95": 5,
    "p95_100": 5,
}
SPECIAL = {"C_DWEL": "C4a", "C_FINS": "C4b", "C_INSR": "C4b", "C_HLTH": "C4d", "C_EDUC": "C4d"}


def _clean(unit: str, dataset: str, period: str | None = YEAR) -> pl.DataFrame:
    df = pl.read_parquet(LAYOUT.clean / unit / f"{dataset}.parquet")
    if period is not None:
        df = df.filter(pl.col("period") == period)
    latest = df.group_by("series_id", "period", maintain_order=True).agg(pl.col("vintage").max().alias("_v"))
    return df.join(latest, on=["series_id", "period"], maintain_order="left").filter(pl.col("vintage") == pl.col("_v"))


def _v(unit: str, dataset: str, sid: str, period: str = YEAR) -> float:
    return _clean(unit, dataset, period).filter(pl.col("series_id") == sid)["value"].item()


def _group(hces_class: str) -> str:
    area, frac = hces_class.split("_", 1)
    return f"H_{'R' if area == 'rural' else 'U'}{QUINTILE[frac]}"


@pytest.fixture(scope="module")
def built() -> pl.DataFrame:
    if not PATHS.built("households"):
        pytest.fail("households block not built: run `uv run python -m pipeline sam households`")
    return pl.read_parquet(PATHS.entries("households"))


@pytest.fixture(scope="module")
def cons() -> pl.DataFrame:
    return pl.read_parquet(PATHS.constraints("households"))


@pytest.fixture(scope="module")
def prov() -> pl.DataFrame:
    return pl.read_parquet(PATHS.provenance("households"))


@pytest.fixture(scope="module")
def fresh():
    r, valid = build_block_module(households, LAYOUT, write=False)
    assert r.ok, r.message
    return valid


def _sat(name: str) -> pl.DataFrame:
    return pl.read_parquet(PATHS.satellites("households") / f"{name}.parquet")


@pytest.fixture(scope="module")
def persons() -> pl.DataFrame:
    """A2 persons of the 24 all-India fractile classes, with their SAM group (recomputed here)."""
    a2 = _clean("hces_consumption", "hces_consumption_a2_fractile_persons", SURVEY)
    df = a2.filter(
        (pl.col("geography") == "IN")
        & (pl.col("item_code") == "persons")
        & ~pl.col("household_group").str.ends_with("_all")
    )
    return df.select(pl.col("household_group").alias("hces_class"), pl.col("value").alias("persons")).with_columns(
        pl.col("hces_class").map_elements(_group, return_dtype=pl.String).alias("group")
    )


@pytest.fixture(scope="module")
def hces_by_group(persons) -> pl.DataFrame:
    """A10F value per person x A2 persons x 12 / 1e7 by item code and SAM group (independent of the block)."""
    a10f = _clean("hces_consumption", "hces_consumption_a10f_item_fractile", SURVEY).filter(
        pl.col("item_code") == "value_per_person_30d"
    )
    df = a10f.select(
        pl.col("series_id").str.split(".").list.get(2).alias("code"),
        pl.col("household_group").alias("hces_class"),
        "value",
    )
    df = df.join(persons, on="hces_class", maintain_order="left").with_columns(
        (pl.col("value") * pl.col("persons") * 12 / 1e7).alias("crore")
    )
    return df.group_by("code", "group", maintain_order=True).agg(pl.col("crore").sum())


@pytest.fixture(scope="module")
def keymap() -> pl.DataFrame:
    return pl.read_csv(LAYOUT.concordance / "hces2324_item_to_sut_product.csv", infer_schema=False).with_columns(
        pl.col("sut_product", "component", "key_quality").fill_null("")
    )


@pytest.fixture(scope="module")
def sut_pfce() -> pl.DataFrame:
    u = _clean("io_tables", "io_tables_sut_use").filter(pl.col("item_code") == "pfce")
    conc = pl.read_csv(LAYOUT.concordance / "io_tables_sut_product_to_sam34.csv", infer_schema=False).select(
        ("sut_p" + pl.col("sut_product").str.zfill(3)).alias("product"), "commodity"
    )
    return u.filter(pl.col("product").str.starts_with("sut_p") & (pl.col("value") != 0)).join(
        conc, on="product", maintain_order="left"
    )


# --- contract --------------------------------------------------------------------------------------


def test_built_outputs_equal_a_fresh_build(built, cons, prov, fresh):
    want = canonical_floats(fresh.entries, {"value": 6, "tol_rel": None}).sort(list(spec.ENTRY_KEY))
    assert built.drop("block").equals(want)
    assert cons.drop("block").equals(canonical_floats(fresh.constraints).sort("constraint_id"))
    assert prov.equals(fresh.provenance.sort("prov_id"))
    for name, (sat, df) in fresh.satellites.items():
        # the framework caps satellite values at 12 significant digits on write (framework._sig, Wave C repro)
        df = df.with_columns(pl.Series("value", [_sig(v, sat.decimals) for v in df["value"].to_list()],
                                       dtype=pl.Float64))  # fmt: skip
        assert _sat(name).equals(canonical_floats(df, {"value": sat.decimals}).sort("series_id")), name
    assert set(fresh.satellites) == {
        "hh_keys",
        "hh_group_map",
        "hh_hces_items",
        "hh_state_xwalk",
        "hh_national_quintile_xwalk",
        "hh_aidis_overlap",
        "c1a_hces_nas_ratio",
        "c4a_imputed_rent_sensitivity",
        "c4b_fisim_split_sensitivity",
        "c4c_npish_memo",
        "s8_food_stik",
    }


def test_every_control_total_check_passes(fresh):
    failed = fresh.checks.filter(~pl.col("ok"))
    assert failed.height == 0, failed
    assert fresh.checks.height >= 60


def test_roles_statuses_and_provenance(built, cons, prov, fresh):
    assert set(built["status"]) == {"estimated"} and set(built["role"]) == {"free"}
    assert built.filter(pl.col("value") <= 0).height == 0  # no zero or negative consumption
    assert set(built["col"]) == set(GROUPS)
    for df in (built, cons):
        assert df["prov_id"].str.starts_with("sam_households:").all()
    for _, df in fresh.satellites.values():
        assert df["prov_id"].str.starts_with("sam_households:").all()
    est = prov.filter(pl.col("status") == "estimated")
    assert est["method"].str.len_chars().min() > 100
    conf = dict(built.group_by("ref", maintain_order=True).agg(pl.col("confidence").unique().sort()).iter_rows())
    assert conf["C4b"] == ["low"] and conf["C4d"] == ["medium"] and conf["C1a"] == ["low", "medium"]


# --- official totals (plan s.7 tests 1-7) ------------------------------------------------------------


def test_pfce_by_commodity_equals_the_sut_and_production(built, sut_pfce):
    want = dict(sut_pfce.group_by("commodity", maintain_order=True).agg(pl.col("value").sum()).iter_rows())
    got = dict(built.group_by("row", maintain_order=True).agg(pl.col("value").sum()).iter_rows())
    assert set(got) == set(want)
    assert len(want) == 31
    for com, v in want.items():
        assert got[com] == pytest.approx(v, abs=0.01), com
    prod = pl.read_parquet(PATHS.constraints("production")).filter(pl.col("constraint_id").str.starts_with("pfce."))
    for r in prod.iter_rows(named=True):
        assert got.get(r["rows"], 0.0) == pytest.approx(r["target"], abs=max(r["tol_abs"], 0.01)), r["rows"]


def test_pfce_total_and_memo_rows(built, prov, sut_pfce):
    tot = built["value"].sum()
    use = _clean("io_tables", "io_tables_sut_use").filter(pl.col("item_code") == "pfce")
    assert tot == pytest.approx(use.filter(pl.col("product") == "total")["value"].item(), abs=0.01)
    assert tot == pytest.approx(sut_pfce["value"].sum(), abs=0.01)
    assert tot == pytest.approx(_v("mospi_nas_2026", "mospi_nas_2026_s1_1", "s1_1.pfce.current"), abs=1.0)
    assert tot == pytest.approx(
        _v("mospi_nas_2026", "mospi_nas_2026_s1_14", "s1_14.households_npish.final_consumption_expenditure.current"),
        abs=1.0,
    )
    memo = use.filter(pl.col("product").str.starts_with("purchases_"))
    assert memo.height == 2
    ins = {i for s in prov["inputs"].drop_nulls().to_list() for i in s.split(",")}
    assert not set(memo["prov_id"].to_list()) & ins, "the SUT PFCE memo rows must not feed any record"


def test_c4a_dwellings(built, hces_by_group):
    c = built.filter(pl.col("ref") == "C4a")
    by = dict(c.group_by("component", maintain_order=True).agg(pl.col("value").sum()).iter_rows())
    supply = _clean("io_tables", "io_tables_sut_supply")
    govt = supply.filter(pl.col("series_id") == "supply.output.sut_p144.sut_i67.current")["value"].item()
    p144 = _v("io_tables", "io_tables_sut_use", "use.pfce.sut_p144.current")
    assert by["govt_housing"] == pytest.approx(govt, abs=1e-4)
    assert by["actual_rent"] + by["imputed_rent"] == pytest.approx(p144 - govt, abs=1e-4)
    assert by["actual_rent"] + by["imputed_rent"] == pytest.approx(
        _v("mospi_nas_2026", "mospi_nas_2026_s8_13", "s8_13.ownership_of_dwellings.output.current"), abs=0.5
    )
    assert c["value"].sum() == pytest.approx(p144, abs=1e-4)
    v520 = hces_by_group.filter(pl.col("code") == "520")["crore"].sum()
    v539 = hces_by_group.filter(pl.col("code") == "539")["crore"].sum()
    assert by["actual_rent"] / (by["actual_rent"] + by["imputed_rent"]) == pytest.approx(v520 / (v520 + v539), abs=1e-9)
    assert set(built.filter(pl.col("row") == "C_DWEL")["ref"]) == {"C4a"}


def test_c4b_fisim_fees_and_insurance(built):
    c = built.filter(pl.col("ref") == "C4b")
    by = dict(c.group_by("component", maintain_order=True).agg(pl.col("value").sum()).iter_rows())
    fisim = _v("mospi_nas_2026", "mospi_nas_2026_s1_13", "s1_13.private_final_consumption_expenditure.current")
    assert by["fisim_deposits"] + by["fisim_loans"] == pytest.approx(fisim, abs=1e-4)
    p142 = _v("io_tables", "io_tables_sut_use", "use.pfce.sut_p142.current")
    assert by["fisim_deposits"] + by["fisim_loans"] + by["explicit_fees"] == pytest.approx(p142, abs=1e-4)
    assert by["insurance_service"] == pytest.approx(_v("io_tables", "io_tables_sut_use", "use.pfce.sut_p143.current"))
    # XR-5: fincorp's reference-rate formula on average T52(b) stocks, recomputed here
    rtp = _clean("rbi_banking_corporate", "rbi_banking_corporate_rtp_banks")

    def rate(x):
        return rtp.filter(pl.col("series_id") == f"rtp.scb_cost_return.{x}.scb")["value"].item()

    rs, rd, rl = rate("return_on_investments"), rate("cost_of_deposits"), rate("return_on_advances")
    t = pl.read_parquet(LAYOUT.clean / "rbi_financial_accounts" / "rbi_financial_accounts_hh_finsav_52ab.parquet")

    def avg(sids):
        return (
            t.filter(pl.col("series_id").is_in(sids) & pl.col("period").is_in(["2023-03-31", "2024-03-31"]))[
                "value"
            ].sum()
            / 2
        )

    d = avg(["t52b.fa_deposits_bank.current", "t52b.fa_deposits_nonbank_ofi.current"])
    ln = avg(["t52b.fl.current"])
    share = (rs - rd) * d / ((rs - rd) * d + (rl - rs) * ln)
    assert by["fisim_deposits"] / fisim == pytest.approx(share, abs=1e-10)
    params = _sat("hh_keys").filter(pl.col("key") == "fisim_params")
    pv = dict(zip(params["measure"].to_list(), params["value"].to_list(), strict=True))
    assert pv["fisim_deposits"] == pytest.approx(by["fisim_deposits"], abs=1e-4)
    assert pv["fisim_loans"] == pytest.approx(by["fisim_loans"], abs=1e-4)
    assert (pv["r_star"], pv["r_deposits"], pv["r_loans"]) == (rs, rd, rl)


def _key_shares(name: str) -> dict[str, float]:
    k = _sat("hh_keys").filter((pl.col("key") == name) & (pl.col("measure") == "share"))
    return dict(k.select("household_group", "value").iter_rows())


def test_c4b_group_keys_follow_the_plan(built):
    """Plan s.2.4 step 3 (verification V-HH-2): FISIM on deposits, explicit fees and insurance are keyed by AIDIS
    financial assets (the press-note deposit share equals financial assets within its whole-percent rounding),
    FISIM on loans by institutional cash loans; aidis_deposits is published for fincorp R8a but keys nothing here."""
    c = built.filter(pl.col("ref") == "C4b")
    for comp, key in (
        ("fisim_deposits", "aidis_fin_assets"),
        ("fisim_loans", "aidis_inst_loans"),
        ("explicit_fees", "aidis_fin_assets"),
        ("insurance_service", "aidis_fin_assets"),
    ):
        e = dict(c.filter(pl.col("component") == comp).select("col", "value").iter_rows())
        tot = sum(e.values())
        share = _key_shares(key)
        assert e == pytest.approx({g: tot * share[g] for g in GROUPS}, abs=1e-5), comp
    # the area ratio behind aidis_deposits is 1 within the rounding of the whole-percent deposit share
    pn = _clean("labour_enterprise_surveys", "labour_enterprise_surveys_aidis_2019_press_note", "2018-06-30")

    def pv(sid):
        return pn.filter(pl.col("series_id") == sid)["value"].item()

    for a in ("rural", "urban"):
        dep = pv(f"pn.asset_share_deposits.{a}.all")
        ratio = pv(f"pn.ava_per_hh.{a}.all.current") / pv(f"pn.ava_financial_per_hh.{a}.all.current")
        assert (dep + 0.5) / 100 * ratio >= 1.0, a


def test_c4b_fisim_split_sensitivity(built):
    """Verification V-HH-3: the XR-5 split (SAM prior) against stock weights, loans without HFC housing loans and
    deposits only, each keeping the NAS total; recomputed here from T52(b), the RTP rates and hh_keys shares."""
    x = _sat("c4b_fisim_split_sensitivity")
    m = dict(x.select("series_id", "value").iter_rows())
    assert set(x["status"]) == {"estimated"}
    fisim = _v("mospi_nas_2026", "mospi_nas_2026_s1_13", "s1_13.private_final_consumption_expenditure.current")
    rtp = _clean("rbi_banking_corporate", "rbi_banking_corporate_rtp_banks")

    def rate(k):
        return rtp.filter(pl.col("series_id") == f"rtp.scb_cost_return.{k}.scb")["value"].item()

    rs, rd, rl = rate("return_on_investments"), rate("cost_of_deposits"), rate("return_on_advances")
    t = pl.read_parquet(LAYOUT.clean / "rbi_financial_accounts" / "rbi_financial_accounts_hh_finsav_52ab.parquet")

    def avg(sids):
        rows = t.filter(pl.col("series_id").is_in(sids) & pl.col("period").is_in(["2023-03-31", "2024-03-31"]))
        return rows["value"].sum() / 2

    d = avg(["t52b.fa_deposits_bank.current", "t52b.fa_deposits_nonbank_ofi.current"])
    ln, hfc = avg(["t52b.fl.current"]), avg(["t52b.fl_ofi_hfc.current"])
    assert m["param.hfc_loans_avg_stock"] == pytest.approx(hfc, abs=1e-6)
    assert m["param.raw_rate_fisim_total"] == pytest.approx((rs - rd) / 100 * d + (rl - rs) / 100 * ln, abs=1e-4)
    assert m["param.raw_rate_to_nas_ratio"] < 1  # the rate formula is only a split rule (V-HH-3)
    wd, wl = (rs - rd) * d, (rl - rs) * (ln - hfc)
    assert m["deposit_share.loans_excl_hfc"] == pytest.approx(wd / (wd + wl), abs=1e-12)
    assert m["deposit_share.deposits_only"] == 1.0
    prior = dict(
        built.filter(pl.col("component").is_in(["fisim_deposits", "fisim_loans"]))
        .group_by("col", maintain_order=True)
        .agg(pl.col("value").sum())
        .iter_rows()
    )
    kd, kl = _key_shares("aidis_fin_assets"), _key_shares("aidis_inst_loans")
    variants = ("xr5_sam_prior", "stock_weights", "loans_excl_hfc", "deposits_only")
    for v in variants:
        s = m[f"deposit_share.{v}"]
        got = {g: m[f"value.{v}.{g.lower()}"] for g in GROUPS}
        assert sum(got.values()) == pytest.approx(fisim, abs=1e-4), v
        assert got == pytest.approx({g: fisim * (s * kd[g] + (1 - s) * kl[g]) for g in GROUPS}, abs=1e-5), v
        if v == "xr5_sam_prior":
            assert got == pytest.approx(prior, abs=1e-5)
        else:
            assert {g: m[f"diff.{v}.{g.lower()}"] for g in GROUPS} == pytest.approx(
                {g: got[g] - prior[g] for g in GROUPS}, abs=1e-5
            )
    # moving FISIM from loans to deposits moves it towards urban groups (loans are relatively rural in AIDIS)
    assert m["deposit_share.xr5_sam_prior"] < m["deposit_share.loans_excl_hfc"] < m["deposit_share.stock_weights"]
    assert m["rural_share.deposits_only"] < m["rural_share.xr5_sam_prior"]


def test_c4d_health_and_education(built):
    for com, p, comp in (("C_HLTH", "153", "oop_health"), ("C_EDUC", "152", "oop_education")):
        c = built.filter(pl.col("row") == com)
        assert set(c["ref"]) == {"C4d"} and set(c["component"]) == {comp}
        assert c["value"].sum() == pytest.approx(
            _v("io_tables", "io_tables_sut_use", f"use.pfce.sut_p{p}.current"), abs=1e-4
        )


def test_s8_food_stik(fresh):
    s8 = _sat("s8_food_stik")
    for item, p in (("rice_free", "001"), ("wheat_free", "002")):
        val = s8.filter((pl.col("item") == item) & (pl.col("measure") == "value"))["value"].sum()
        assert val == pytest.approx(_v("io_tables", "io_tables_sut_use", f"use.gfce.sut_p{p}.current"), abs=1e-4)
    chk = fresh.checks.filter(pl.col("check_id") == "s8.vs_union_food_subsidy").row(0, named=True)
    assert chk["target"] == _v("union_fiscal", "union_fiscal_exp_profile", "stat7.food.food_subsidy")
    # quantity shares drive the values
    q = s8.filter((pl.col("item") == "rice_free") & (pl.col("measure") == "qty"))
    v = s8.filter((pl.col("item") == "rice_free") & (pl.col("measure") == "value"))
    assert (v["value"] / v["value"].sum()).to_list() == pytest.approx(
        (q["value"] / q["value"].sum()).to_list(), abs=1e-9
    )


# --- structure and double counting (tests 8-12) ---------------------------------------------------------


def test_refs_per_commodity(built):
    refs = dict(built.group_by("row", maintain_order=True).agg(pl.col("ref").unique().sort()).iter_rows())
    for com, r in refs.items():
        assert r == [SPECIAL.get(com, "C1a")], com
    assert not {"C_OILG", "C_OMIN", "C_MTLS"} & set(refs)
    assert "C4c" not in set(built["ref"])
    c1a = built.filter(pl.col("ref") == "C1a")
    assert c1a["component"].str.contains(r"^sut_p\d{3}$").all()
    assert "sut_p125" not in set(c1a["component"])  # gems & jewellery: valuables only


def test_key_concordance(keymap, hces_by_group, sut_pfce):
    a10f = _clean("hces_consumption", "hces_consumption_a10f_item_fractile", SURVEY)
    roles = dict(
        a10f.select(
            pl.col("series_id").str.split(".").list.get(2).alias("code"),
            pl.col("dim_other").str.extract(r"item_role=(\w+)").alias("role"),
        )
        .unique(maintain_order=True)
        .iter_rows()
    )
    leaves = {c for c, r in roles.items() if r == "leaf"}
    km = keymap.filter(pl.col("ref") != "excluded")
    for r in km.iter_rows(named=True):
        ok = roles.get(r["hces_item"]) == "leaf" or (r["ref"] == "C4a" and r["hces_item"] == "539")
        assert ok, r
    c1a_items = set(km.filter(pl.col("ref") == "C1a")["hces_item"].to_list())
    banned = {
        "640",
        "641",
        "642",
        "643",
        "061",
        "062",
        "070",
        "071",
        "072",
        "073",
        "074",
        "075",
        "282",
        "520",
        "539",
        "522",
        "405",
        "406",
        "408",
        "411",
        "412",
        "413",
        "414",
        "421",
        "422",
        "424",
    }
    assert not c1a_items & banned
    excluded = set(keymap.filter(pl.col("ref") == "excluded")["hces_item"].to_list())
    assert leaves <= set(km["hces_item"].to_list()) | excluded, "every leaf item is used or excluded"
    assert not excluded & set(km["hces_item"].to_list())
    assert keymap.filter(pl.col("ref") == "excluded")["note"].str.len_chars().min() > 10
    keyed = {"sut_p" + p.zfill(3) for p in km["sut_product"].to_list()}
    pf = set(sut_pfce["product"].to_list())
    assert pf - keyed == {"sut_p142", "sut_p143"}
    # every keyed product has non-zero HCES spending on its key
    for p in sorted(keyed):
        items = km.filter(("sut_p" + pl.col("sut_product").str.zfill(3)) == p)["hces_item"].to_list()
        assert hces_by_group.filter(pl.col("code").is_in(items))["crore"].sum() > 0, p


def test_group_definition(persons):
    gm = _sat("hh_group_map")
    classes = gm.filter(pl.col("measure") == "persons")
    assert classes.height == 24 and classes["hces_class"].n_unique() == 24
    assert dict(classes.select("hces_class", "household_group").iter_rows()) == dict(
        persons.select("hces_class", "group").iter_rows()
    )
    assert classes["value"].sum() == persons["persons"].sum()
    for area in ("rural", "urban"):
        sub = persons.filter(pl.col("hces_class").str.starts_with(area))
        by = sub.group_by("group", maintain_order=True).agg(pl.col("persons").sum())
        for g, p in by.iter_rows():
            assert abs(p / sub["persons"].sum() - 0.2) < 1e-4, g
    assert gm.filter(pl.col("measure") == "avg_mpce").height == 24


def test_entries_are_sut_pfce_times_hces_shares(built, keymap, hces_by_group, sut_pfce):
    km = keymap.filter(pl.col("ref").is_in(["C1a", "C4d"]))
    pf = dict(sut_pfce.select("product", "value").iter_rows())
    n = 0
    for p in km["sut_product"].unique(maintain_order=True).to_list():
        prod = "sut_p" + p.zfill(3)
        items = km.filter(pl.col("sut_product") == p)["hces_item"].to_list()
        key = dict(
            hces_by_group.filter(pl.col("code").is_in(items))
            .group_by("group", maintain_order=True)
            .agg(pl.col("crore").sum())
            .iter_rows()
        )
        tot = sum(key.values())
        comp = {"sut_p152": "oop_education", "sut_p153": "oop_health"}.get(prod, prod)
        e = dict(built.filter(pl.col("component") == comp).select("col", "value").iter_rows())
        got = [e.get(g, 0.0) for g in GROUPS]
        assert sum(got) == pytest.approx(pf[prod], abs=1e-4)  # entries are written to 6 decimals
        assert min(got) >= 0
        assert got == pytest.approx([pf[prod] * key.get(g, 0.0) / tot for g in GROUPS], abs=1e-5), prod
        n += 1
    assert n == 116


def test_survey_window_record_feeds_every_hces_keyed_record(prov):
    window = prov.filter(pl.col("method").str.starts_with("Survey-window assumption"))
    assert window.height == 1
    wid = window["prov_id"].item()
    hces_ids = set(pl.read_parquet(LAYOUT.clean / "hces_consumption" / "_provenance.parquet")["prov_id"].to_list())
    periods = {}
    for ds in ("hces_consumption_a10f_item_fractile", "hces_consumption_a2_fractile_persons"):
        df = pl.read_parquet(LAYOUT.clean / "hces_consumption" / f"{ds}.parquet")
        for pid, per in df.select("prov_id", "period").unique(maintain_order=True).iter_rows():
            periods.setdefault(pid, set()).add(per)
    n = 0
    for r in prov.filter(pl.col("prov_id") != wid).iter_rows(named=True):
        ins = set((r["inputs"] or "").split(","))
        hces = {i for i in ins if i in hces_ids and i in periods}
        ref = r["table_id"].split()[-1]  # default table_id 'SAM <year> gap-map <ref>'
        if hces and ref in ("C1a", "C4a", "C4b", "C4d") and r["status"] == "estimated":
            assert wid in ins or any(i.startswith("sam_households:") for i in ins), r["prov_id"]
            n += 1
        for i in hces:
            assert periods[i] == {SURVEY}, (r["prov_id"], i)
    assert n >= 116


# --- satellites (tests 13-15) ---------------------------------------------------------------------


def test_hh_keys(built, persons):
    k = _sat("hh_keys").filter(pl.col("key") != "fisim_params")
    names = set(k["key"].to_list())
    want = {
        "pop_persons",
        "pop_households",
        "hces_total",
        "hces_food",
        "hces_nonfood",
        "hces_durables",
        "pfce_total",
        "c4a_actual_rent",
        "c4a_imputed_rent",
        "c4a_govt_housing",
        "c4b_fisim_deposits",
        "c4b_fisim_loans",
        "c4b_explicit_fees",
        "c4b_insurance_service",
        "aidis_fin_assets",
        "aidis_cash_loans",
        "aidis_inst_loans",
        "aidis_noninst_loans",
        "aidis_fixed_assets",
        "aidis_valuables",
        "aidis_total_assets",
        "aidis_deposits",
        "aidis_equity",
        "aidis_mf",
        "aidis_small_savings",
    }  # CROSS_REVIEW s.4.3, exact names
    assert want <= names
    for key in sorted(names):
        lv = k.filter((pl.col("key") == key) & (pl.col("measure") == "level")).sort("household_group")
        sh = k.filter((pl.col("key") == key) & (pl.col("measure") == "share")).sort("household_group")
        assert lv["household_group"].to_list() == sorted(GROUPS)
        assert sh["value"].sum() == pytest.approx(1.0, abs=1e-9), key
        assert sh["value"].to_list() == pytest.approx((lv["value"] / lv["value"].sum()).to_list(), abs=1e-11), key
    pop = dict(
        k.filter((pl.col("key") == "pop_persons") & (pl.col("measure") == "level"))
        .select("household_group", "value")
        .iter_rows()
    )
    want_pop = dict(persons.group_by("group", maintain_order=True).agg(pl.col("persons").sum()).iter_rows())
    assert pop == pytest.approx(want_pop)
    for key, ref, comp in (
        ("c4a_imputed_rent", "C4a", "imputed_rent"),
        ("c4b_fisim_loans", "C4b", "fisim_loans"),
        ("pfce_total", None, None),
    ):
        e = built if ref is None else built.filter((pl.col("ref") == ref) & (pl.col("component") == comp))
        by = dict(e.group_by("col", maintain_order=True).agg(pl.col("value").sum()).iter_rows())
        lv = dict(
            k.filter((pl.col("key") == key) & (pl.col("measure") == "level"))
            .select("household_group", "value")
            .iter_rows()
        )
        assert lv == pytest.approx(by, abs=1e-5), key
    for proxy in ("aidis_equity", "aidis_mf", "aidis_small_savings"):
        a = k.filter((pl.col("key") == proxy) & (pl.col("measure") == "share"))["value"].to_list()
        b = k.filter((pl.col("key") == "aidis_fin_assets") & (pl.col("measure") == "share"))["value"].to_list()
        assert a == b


def test_aidis_overlap_weights():
    ov = _sat("hh_aidis_overlap")
    for m, by in (("share_of_aidis_class", "aidis_class"), ("share_of_group", "household_group")):
        s = ov.filter(pl.col("measure") == m).group_by(by, maintain_order=True).agg(pl.col("value").sum())
        assert s["value"].to_list() == pytest.approx([1.0] * s.height, abs=1e-9), m
        assert s.height == 10
    # every AIDIS class holds a fifth of its area's HCES 2023-24 households
    hh = ov.filter(pl.col("measure") == "households")
    per = hh.group_by("area", "aidis_class", maintain_order=True).agg(pl.col("value").sum())
    for area in ("rural", "urban"):
        vals = per.filter(pl.col("area") == area)["value"].to_list()
        assert vals == pytest.approx([sum(vals) / 5] * 5, rel=1e-12)


def test_state_xwalk():
    x = _sat("hh_state_xwalk")
    w = (
        x.filter(pl.col("measure") == "weight")
        .group_by("geography", "area", "hces_class", maintain_order=True)
        .agg(pl.col("value").sum())
    )
    assert w["value"].to_list() == pytest.approx([1.0] * w.height, abs=1e-9)
    assert w.height == 36 * 24
    a2 = _clean("hces_consumption", "hces_consumption_a2_fractile_persons", SURVEY).filter(
        (pl.col("geography") != "IN") & ~pl.col("household_group").str.ends_with("_all")
    )
    p = a2.filter(pl.col("item_code") == "persons").select("geography", "household_group", pl.col("value").alias("p"))
    m = a2.filter(pl.col("item_code") == "avg_mpce").select("geography", "household_group", pl.col("value").alias("m"))
    cons = p.join(m, on=["geography", "household_group"]).select((pl.col("p") * pl.col("m") * 12 / 1e7).sum()).item()
    agg = x.filter((pl.col("hces_class") == "all") & (pl.col("measure") == "consumption"))["value"].sum()
    assert agg == pytest.approx(cons, rel=1e-9)
    sh = (
        x.filter(pl.col("measure") == "consumption_share")
        .group_by("geography", "area", maintain_order=True)
        .agg(pl.col("value").sum())
    )
    assert sh["value"].to_list() == pytest.approx([1.0] * sh.height, abs=1e-9)
    assert x.filter(pl.col("area") == "rural")["household_group"].str.starts_with("H_R").all()


def test_national_quintile_xwalk(persons):
    x = _sat("hh_national_quintile_xwalk")
    sh = (
        x.filter(pl.col("measure") == "share")
        .group_by("household_group", maintain_order=True)
        .agg(pl.col("value").sum())
    )
    assert sh.height == 10 and sh["value"].to_list() == pytest.approx([1.0] * 10, abs=1e-9)
    q = (
        x.filter(pl.col("measure") == "persons")
        .group_by("national_quintile", maintain_order=True)
        .agg(pl.col("value").sum())
    )
    total = persons["persons"].sum()
    assert q["value"].to_list() == pytest.approx([total / 5] * 5, rel=1e-9)
    cuts = x.filter(pl.col("measure") == "cut_mpce").sort("series_id")["value"].to_list()
    assert cuts == sorted(cuts) and len(cuts) == 4

    # the poorest rural group sits mostly in the national bottom quintile, the richest urban one in the top
    def s(g, qq):
        return x.filter(
            (pl.col("household_group") == g) & (pl.col("national_quintile") == qq) & (pl.col("measure") == "share")
        )["value"].item()

    assert s("H_R1", "q1") > 0.5 and s("H_U5", "q5") > 0.5


def test_npish_memo():
    icio = _clean("io_tables", "io_tables_icio_india", "2022-23")
    sid = icio["series_id"]
    npish = icio.filter(sid.str.contains(r"^icio\.((dom|imp)\.[^.]+|tls)\.npish\.current$"))["value"].sum()
    hfce = icio.filter(sid.str.contains(r"^icio\.((dom|imp)\.[^.]+|tls)\.hfce\.current$"))["value"].sum()
    m = dict(_sat("c4c_npish_memo").select("series_id", "value").iter_rows())
    assert m["npish_share"] == pytest.approx(npish / (npish + hfce), abs=1e-12)
    assert m["npish_fce"] == pytest.approx(npish, rel=1e-12)


# --- plausibility (tests 16-19) ------------------------------------------------------------------------


def test_group_shares_are_plausible(built):
    by = dict(built.group_by("col", maintain_order=True).agg(pl.col("value").sum()).iter_rows())
    tot = sum(by.values())
    rural = sum(v for g, v in by.items() if g.startswith("H_R")) / tot
    assert 0.45 <= rural <= 0.62
    assert 0.30 <= (by["H_R5"] + by["H_U5"]) / tot <= 0.50


def test_engel_food_share_falls_with_quintile(built):
    food = built.filter(pl.col("row").is_in(["C_CROP", "C_FOOD", "C_LVST", "C_FOFI"]))
    f = dict(food.group_by("col", maintain_order=True).agg(pl.col("value").sum()).iter_rows())
    t = dict(built.group_by("col", maintain_order=True).agg(pl.col("value").sum()).iter_rows())
    for a in ("R", "U"):
        shares = [f[f"H_{a}{q}"] / t[f"H_{a}{q}"] for q in range(1, 6)]
        assert shares == sorted(shares, reverse=True), (a, shares)


def test_s8_per_person_falls_with_quintile():
    s8 = _sat("s8_food_stik").filter((pl.col("item") == "total") & (pl.col("measure") == "value"))
    pop = _sat("hh_keys").filter((pl.col("key") == "pop_persons") & (pl.col("measure") == "level"))
    pp = dict(pop.select("household_group", "value").iter_rows())
    v = {g: x / pp[g] for g, x in s8.select("household_group", "value").iter_rows()}
    for a in ("R", "U"):
        seq = [v[f"H_{a}{q}"] for q in range(1, 6)]
        assert seq == sorted(seq, reverse=True), (a, seq)


def test_hces_nas_ratio_in_range_for_direct_keys():
    r = _sat("c1a_hces_nas_ratio").filter((pl.col("level") == "commodity") & (pl.col("measure") == "ratio"))
    direct = r.filter(pl.col("key_quality") == "direct")
    assert direct.height >= 10
    assert direct["value"].is_between(0.05, 1.5).all(), direct
    assert all(math.isfinite(v) and v > 0 for v in r["value"].to_list())


# --- constraints --------------------------------------------------------------------------------------


def test_constraints(cons, built):
    ids = set(cons["constraint_id"].to_list())
    assert ids == {"hh.c1.total", "hh.c4b.fisim", "hh.c4a.govt_housing", "hh.c4a.imputed_rent"}
    assert not any(i.startswith("pfce.") for i in ids)  # production's targets are not re-declared (XR-15)
    c = {r["constraint_id"]: r for r in cons.iter_rows(named=True)}
    assert c["hh.c1.total"]["target"] == _v("mospi_nas_2026", "mospi_nas_2026_s1_1", "s1_1.pfce.current")
    assert c["hh.c1.total"]["tol_abs"] == 1.0
    assert c["hh.c4b.fisim"]["target"] == _v(
        "mospi_nas_2026", "mospi_nas_2026_s1_13", "s1_13.private_final_consumption_expenditure.current"
    )
    assert c["hh.c4b.fisim"]["components"] == "fisim_deposits,fisim_loans"
    assert c["hh.c4a.imputed_rent"]["kind"] == "band" and c["hh.c4a.imputed_rent"]["tol_rel"] == 0.10
    # every constraint holds at the prior
    for r in c.values():
        e = built.filter(pl.col("row").is_in(r["rows"].split(",")) & pl.col("col").is_in(r["cols"].split(",")))
        if r["components"]:
            e = e.filter(pl.col("component").is_in(r["components"].split(",")))
        tol = max(r["tol_abs"], r["tol_rel"] * abs(r["target"]))
        assert abs(e["value"].sum() - r["target"]) <= tol, r["constraint_id"]


def test_imputed_rent_band_record_is_estimated(cons, prov, built):
    """Verification V-HH-1: the band's target is the same modelled quantity as the imputed_rent entries (HCES rent
    ratio applied to the SUT level), so its record is `estimated` and cites the entries' record's inputs."""
    pid = cons.filter(pl.col("constraint_id") == "hh.c4a.imputed_rent")["prov_id"].item()
    rec = prov.filter(pl.col("prov_id") == pid).row(0, named=True)
    epid = built.filter(pl.col("component") == "imputed_rent")["prov_id"].unique().item()
    erec = prov.filter(pl.col("prov_id") == epid).row(0, named=True)
    assert rec["status"] == erec["status"] == "estimated"
    assert set(rec["inputs"].split(",")) == set(erec["inputs"].split(","))
    official = prov.filter(pl.col("prov_id").is_in(cons["prov_id"].to_list()) & (pl.col("status") == "official"))
    assert official.height == 3  # the three equality targets are published figures


def test_hces_dash_cells_are_logged_in_the_issues_file(keymap):
    """No silent fallback (verification V-HH-4): every key item whose A10F row lacks some fractile classes (cells
    printed '-', counted as 0) is named in the issues file."""
    a10f = _clean("hces_consumption", "hces_consumption_a10f_item_fractile", SURVEY).filter(
        pl.col("item_code") == "value_per_person_30d"
    )
    n = a10f.group_by(pl.col("series_id").str.split(".").list.get(2).alias("code")).agg(
        pl.col("household_group").n_unique().alias("n")
    )
    used = set(keymap.filter(pl.col("ref") != "excluded")["hces_item"].to_list())
    short = sorted(c for c, k in n.iter_rows() if c in used and k < 24)
    assert short, "expected some key items with '-' cells"
    text = (LAYOUT.root / "docs" / "phase2" / "issues" / "households.md").read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("| households-21 "))
    missing = [c for c in short if c not in line]
    assert not missing, missing


def test_imputed_rent_sensitivity(built):
    x = _sat("c4a_imputed_rent_sensitivity")
    m = {r["series_id"]: r["value"] for r in x.iter_rows(named=True)}
    prior = built.filter(pl.col("component") == "imputed_rent")
    assert sum(m[f"sam_prior.{g.lower()}"] for g in GROUPS) == pytest.approx(prior["value"].sum(), abs=1e-4)
    variant = sum(m[f"aidis_building_variant.{g.lower()}"] for g in GROUPS)
    assert variant == pytest.approx(prior["value"].sum(), abs=1e-4)  # same total, other rural/urban split
    pn = _clean("labour_enterprise_surveys", "labour_enterprise_surveys_aidis_2019_press_note", "2018-06-30")
    hh = _sat("hh_keys").filter((pl.col("key") == "pop_households") & (pl.col("measure") == "level"))
    n = {a: hh.filter(pl.col("area") == a)["value"].sum() for a in ("rural", "urban")}

    def pv(sid):
        return pn.filter(pl.col("series_id") == sid)["value"].item()

    b = {a: pv(f"pn.asset_share_building.{a}.all") * pv(f"pn.ava_per_hh.{a}.all.current") * n[a] for a in n}
    assert m["rural_urban_share_aidis_building.rural"] == pytest.approx(b["rural"] / (b["rural"] + b["urban"]))
    assert m["rural_urban_share_sam_prior.rural"] < m["rural_urban_share_aidis_building.rural"]
