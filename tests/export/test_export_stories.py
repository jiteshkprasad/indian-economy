"""Story figures, recomputed independently (docs/phase3/PLAN.md s.4.9, s.3.8). Owner: U5.

Every figure in `pipeline/export/stories/<slug>.yaml` is recomputed here with DuckDB SQL written by hand
from the parquet files (no pipeline code, and no reading of the YAML selectors), and compared with the
exported `web/public/data/<data_version>/stories/<slug>.json`. Base figures are SQL; derived figures
(per 100, ratios, sums, differences) are arithmetic on those. The test also checks:
- the figure ids here equal the YAML's figure ids (nothing exported goes unchecked);
- `satellite_share` families add up to their balanced totals (within Rs 0.01 crore);
- net borrowing = liabilities - financial assets for the Centre and the States (within Rs 0.01 crore), and
  every figure the story calls "borrowing" is positive;
- the qualitative claims the story text makes (orderings and signs), so the prose cannot drift from the data;
- every step's highlighted/selected link and node id exists in the aggregated SAM at that step's zoom.

The value comparisons need the real export (`uv run python -m pipeline export`). Without it they are
skipped with an explicit reason; the data-only checks always run.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import duckdb
import pytest
import yaml

pytestmark = pytest.mark.export

REPO = Path(__file__).resolve().parents[2]
SAM = REPO / "data" / "sam" / "2023-24"
TS = REPO / "data" / "timeseries"
STORIES = REPO / "pipeline" / "export" / "stories"
SLUGS = ("gst-rupee", "remittance-dubai", "deficit-funding")

TOL = {"inr": 0.01, "pct_gdp": 1e-6, "pct": 1e-6, "per100": 1e-4}


# ----------------------------------------------------------------------------------------------- data


def connect() -> duckdb.DuckDBPyConnection:
    """An in-memory DuckDB with views over the parquet files and the account groups."""
    c = duckdb.connect()
    c.execute(f"create view s as select * from read_parquet('{SAM / 'sam_balanced.parquet'}')")
    c.execute(f"create view e as select * from read_parquet('{SAM / 'sam_entries_balanced.parquet'}')")
    c.execute(
        "create view p7b as select * from read_parquet("
        f"'{SAM / 'blocks' / 'taxes_satellites' / 'p7b_tax_by_use.parquet'}')"
    )
    c.execute(
        "create view s3 as select * from read_parquet("
        f"'{SAM / 'blocks' / 'rest_of_world_satellites' / 's3_remittance_sources.parquet'}')"
    )
    c.execute(f"create view ts as select * from read_parquet('{TS / 'top_flows.parquet'}')")
    c.execute(f"create view tsdef as select * from read_parquet('{TS / 'top_flows_definitions.parquet'}')")
    accounts = yaml.safe_load((REPO / "pipeline" / "sam" / "accounts.yaml").read_text(encoding="utf-8"))["accounts"]
    c.execute("create table acc(code varchar, grp varchar)")
    c.executemany("insert into acc values (?, ?)", [(a["code"], a["group"]) for a in accounts])
    return c


@pytest.fixture(scope="module")
def con() -> duckdb.DuckDBPyConnection:
    return connect()


def q(c: duckdb.DuckDBPyConnection, sql: str) -> float:
    row = c.execute(sql).fetchone()
    assert row is not None
    return float(row[0] or 0.0)


def g(group: str) -> str:
    """SQL subquery: the account codes of an accounts.yaml group."""
    return f"(select code from acc where grp = '{group}')"


GST = "('T_CGST', 'T_SGST', 'T_GCES')"
GOVS = "('G_CEN', 'G_STA')"
KGOVS = "('K_GCEN', 'K_GSTA')"


def cells(rows: str, cols: str) -> str:
    return f"select sum(value) from s where row in {rows} and col in {cols}"


def ents(where: str) -> str:
    return f"select sum(value) from e where {where}"


def gdp_2023(c: duckdb.DuckDBPyConnection) -> float:
    return q(
        c,
        "select value from ts where flow_id = 'M01' and period = '2023-24' and variant = 'published' "
        "and base_year = '2022-23'",
    )


def ts_main(c: duckdb.DuckDBPyConnection, flow: str, period: str) -> tuple[float, str | None]:
    """PLAN s.3.7.1: published rows; base 2022-23, else 2011-12, else the single null-base row; no ties."""
    rows = c.execute(
        "select value, base_year from ts where flow_id = ? and period = ? and variant = 'published'",
        [flow, period],
    ).fetchall()
    for want in ("2022-23", "2011-12", None):
        hit = [r for r in rows if r[1] == want]
        if hit:
            assert len(hit) == 1, f"{flow} {period}: {len(hit)} candidates at base {want}"
            return float(hit[0][0]), want
    raise AssertionError(f"{flow} {period}: no published row")


def ts_share(c: duckdb.DuckDBPyConnection, flow: str, period: str) -> float:
    """PLAN s.3.7.2: value x display_sign / GDP of the same period on the same base."""
    value, base = ts_main(c, flow, period)
    sign = q(c, f"select display_sign from tsdef where flow_id = '{flow}'")
    if base is None:
        base = "2022-23" if period >= "2022-23" else "2011-12"
    den = q(
        c,
        "select value from ts where flow_id = 'M01' and variant = 'published' "
        f"and period = '{period}' and base_year = '{base}'",
    )
    return value * sign / den


def p7b_rescaled(c: duckdb.DuckDBPyConnection, account: str, use: str) -> float:
    """p7b share of `use` within one tax account (all its components), times that account's balanced row."""
    share = q(
        c,
        f"select sum(value) filter (where use_type = '{use}') / sum(value) from p7b where tax_account = '{account}'",
    )
    total = q(c, cells(f"('{account}')", g("COM")))
    return share * total


def prorata(c: duckdb.DuckDBPyConnection, receiver: str) -> float:
    """Sum over commodities of household purchases x (receiver's cell in the commodity column / column total)."""
    return q(
        c,
        f"""
        with base as (select row as k, sum(value) as b from s
                      where col in {g("HH")} and row in {g("COM")} group by row),
             num as (select col as k, sum(value) as n from s
                     where row = '{receiver}' and col in {g("COM")} group by col),
             den as (select col as k, sum(value) as d from s where col in {g("COM")} group by col)
        select sum(b * coalesce(n, 0) / d) from base join den using (k) left join num using (k)
        """,
    )


# ------------------------------------------------------------------------------------- the figures

Fig = Callable[[duckdb.DuckDBPyConnection, dict[str, float]], float]


def per100(part: str, whole: str) -> Fig:
    return lambda c, v: 100.0 * v[part] / v[whole]


def ratio_gdp(num: str) -> Fig:
    return lambda c, v: v[num] / gdp_2023(c)


def total(*ids: str) -> Fig:
    return lambda c, v: sum(v[i] for i in ids)


def minus(a: str, b: str) -> Fig:
    return lambda c, v: v[a] - v[b]


def sql(text: str) -> Fig:
    return lambda c, v: q(c, text)


def rescaled(account: str, use: str) -> Fig:
    return lambda c, v: p7b_rescaled(c, account, use)


def gst_rupee() -> dict[str, Fig]:
    f: dict[str, Fig] = {
        # levels on the receipt side (what each government collects); see the YAML comment
        "gst_total": sql(cells(GOVS, GST)),
        "gst_commodity_side": sql(cells(GST, g("COM"))),
        "gst_total_gdp": ratio_gdp("gst_total"),
        "cgst_total": sql(cells("('G_CEN')", "('T_CGST')")),
        "sgst_total": sql(cells("('G_STA')", "('T_SGST')")),
        "cess_total": sql(cells("('G_CEN')", "('T_GCES')")),
        "utgst": sql(ents("row = 'G_CEN' and col = 'T_CGST' and ref = 'T1a' and component = 'utgst'")),
        "cgst_per100": per100("cgst_total", "gst_total"),
        "sgst_per100": per100("sgst_total", "gst_total"),
        "cess_per100": per100("cess_total", "gst_total"),
    }
    for k, acct in (("cnst", "C_CNST"), ("treq", "C_TREQ"), ("chem", "C_CHEM"), ("txap", "C_TXAP")):
        f[f"gst_{k}"] = sql(cells(GST, f"('{acct}')"))
        f[f"gst_{k}_per100"] = per100(f"gst_{k}", "gst_commodity_side")
    uses = {"pfce": "pfce", "ic": "ic", "gfcf": "gfcf", "gfce": "gfce", "valu": "valuables"}
    accts = {"cgst": "T_CGST", "sgst": "T_SGST", "cess": "T_GCES"}
    for u, use in uses.items():
        for a, acct in accts.items():
            f[f"till_{u}_{a}"] = rescaled(acct, use)
        f[f"till_{u}"] = total(*(f"till_{u}_{a}" for a in accts))
        f[f"till_{u}_per100"] = per100(f"till_{u}", "gst_commodity_side")
    f |= {
        "gst_centre": sql(cells("('G_CEN')", "('T_CGST', 'T_GCES')")),
        "gst_states": sql(cells("('G_STA')", "('T_SGST')")),
        "gst_centre_per100": per100("gst_centre", "gst_total"),
        "gst_states_per100": per100("gst_states", "gst_total"),
        "comp_grants": sql(
            ents("row = 'G_STA' and col = 'G_CEN' and ref = 'T2b' and component = 'compensation_grants'")
        ),
        "cess_loan_transfer": sql(
            ents("row = 'G_STA' and col = 'G_CEN' and ref = 'T2b' and component = 'cess_loan_recovery'")
        ),
        "b2b_repaid": sql(
            ents("row = 'K_GSTA' and col = 'I_LOAN' and ref = 'K8e' and component = 'gst_b2b_repayment'")
        ),
        "cess_passed": total("comp_grants", "cess_loan_transfer"),
        "cess_passed_per100": per100("cess_passed", "cess_total"),
        "devol_cgst": sql(ents("row = 'G_STA' and col = 'G_CEN' and ref = 'R1' and component = 'cgst'")),
        "cgst_ex_utgst": minus("cgst_total", "utgst"),
        "devol_cgst_per100": per100("devol_cgst", "cgst_ex_utgst"),
        # what the States keep: the cess-loan transfer passes straight through them (repays K8e), so it is apart
        "gst_to_states_kept": total("gst_states", "devol_cgst", "comp_grants"),
        "gst_to_states_kept_per100": per100("gst_to_states_kept", "gst_total"),
        "cess_loan_per100_gst": per100("cess_loan_transfer", "gst_total"),
        # consolidated general government: no saving, no Centre<->State transfers
        "gg_current": sql(ents(f"col in {GOVS} and row not in {GOVS} and row not in {KGOVS}")),
        "gg_capital": sql(ents(f"col in {KGOVS} and row not in {KGOVS} and ref in ('I1a', 'I3a', 'K6')")),
        "gg_outlays": total("gg_current", "gg_capital"),
        "gg_goods_services": sql(ents(f"col in {GOVS} and row in {g('COM')} and ref = 'C2a'")),
        "gg_interest": sql(ents(f"col in {GOVS} and row not in {GOVS} and ref in ('R3a', 'R8a', 'R9c', 'R14')")),
        "gg_pensions": sql(ents(f"col in {GOVS} and row in {g('HH')} and ref = 'R9a'")),
        "gg_cash_transfers": sql(ents(f"col in {GOVS} and row in {g('HH')} and ref = 'R10'")),
        "gg_corp_transfers": sql(ents(f"col in {GOVS} and ref = 'R18'")),
        "gg_fin_assets": sql(cells(g("INST"), KGOVS)),
        "gg_product_subsidies": sql(ents(f"row in {GOVS} and col = 'T_PSUB' and ref = 'P9a'")),
        "gg_production_subsidies": sql(
            ents(f"row in {GOVS} and col = 'T_PROD' and ref = 'P10a' and component = 'gross_subsidies'")
        ),
        "gg_subsidies_paid": lambda c, v: -(v["gg_product_subsidies"] + v["gg_production_subsidies"]),
        "gg_subsidies_per100": per100("gg_subsidies_paid", "gg_outlays"),
    }
    for k in ("goods_services", "interest", "pensions", "cash_transfers", "corp_transfers", "capital"):
        f[f"gg_{k}_per100"] = per100(f"gg_{k}", "gg_outlays")
    return f


def remittance_dubai() -> dict[str, Fig]:
    rur = "('H_R1', 'H_R2', 'H_R3', 'H_R4', 'H_R5')"
    urb = "('H_U1', 'H_U2', 'H_U3', 'H_U4', 'H_U5')"
    f: dict[str, Fig] = {
        "remit_total": sql(ents(f"row in {g('HH')} and col = 'R_ROW' and ref = 'R11a'")),
        "remit_gdp": ratio_gdp("remit_total"),
        "remit_value_first": lambda c, v: ts_main(c, "F43", "2006-07")[0],
        "remit_share_first": lambda c, v: ts_share(c, "F43", "2006-07"),
        "remit_share_2023": lambda c, v: ts_share(c, "F43", "2023-24"),
        "remit_value_latest": lambda c, v: ts_main(c, "F43", "2025-26")[0],
        "uae_remit": sql("select sum(value) from s3 where country = 'ARE' and measure = 'inr_crore'"),
        "uae_share": sql("select sum(value) from s3 where country = 'ARE' and measure = 'share'"),
        "usa_share": sql("select sum(value) from s3 where country = 'USA' and measure = 'share'"),
        "remit_rural": sql(ents(f"row in {rur} and col = 'R_ROW' and ref = 'R11a'")),
        "remit_urban": sql(ents(f"row in {urb} and col = 'R_ROW' and ref = 'R11a'")),
        "remit_top": sql(ents("row in ('H_R5', 'H_U5') and col = 'R_ROW' and ref = 'R11a'")),
        "remit_bottom": sql(ents("row in ('H_R1', 'H_U1') and col = 'R_ROW' and ref = 'R11a'")),
        "hh_consumption": sql(cells(g("COM"), g("HH"))),
        "hh_saving": sql(cells("('K_HH')", g("HH"))),
        "hh_taxes": sql(cells(g("TAX"), g("HH"))),
        "hh_finance": sql(cells(g("FC"), g("HH"))),
        "hh_abroad": sql(cells("('R_ROW')", g("HH"))),
        "hh_to_gov": sql(cells(g("GOV"), g("HH"))),
        "hh_residual": sql(cells("('X_DISC')", g("HH"))),
        "hh_outlays_all": sql(f"select sum(value) from s where col in {g('HH')}"),
    }
    parts = ("consumption", "saving", "taxes", "finance", "abroad", "to_gov", "residual")
    f["hh_outlays"] = total(*(f"hh_{p}" for p in parts))
    for p in parts:
        f[f"hh_{p}_per100"] = per100(f"hh_{p}", "hh_outlays")
    for k in ("rural", "urban", "top", "bottom"):
        f[f"remit_{k}_per100"] = per100(f"remit_{k}", "remit_total")
    for a, acct in {
        "cgst": "T_CGST",
        "sgst": "T_SGST",
        "cess": "T_GCES",
        "uexc": "T_UEXC",
        "svat": "T_SVAT",
        "sexc": "T_SEXC",
        "oprt": "T_OPRT",
    }.items():
        f[f"pfce_tax_{a}"] = rescaled(acct, "pfce")
    f |= {
        "pfce_gst": total("pfce_tax_cgst", "pfce_tax_sgst", "pfce_tax_cess"),
        "pfce_other_tax": total("pfce_tax_uexc", "pfce_tax_svat", "pfce_tax_sexc", "pfce_tax_oprt"),
        "pfce_imports": lambda c, v: prorata(c, "R_ROW"),
        "pfce_margins": lambda c, v: prorata(c, "M_TTM"),
    }
    for k in ("gst", "other_tax", "imports", "margins"):
        f[f"pfce_{k}_per100"] = per100(f"pfce_{k}", "hh_consumption")
    return f


def deficit_funding() -> dict[str, Fig]:
    inst = g("INST")
    f: dict[str, Fig] = {
        "saving_cen": sql(ents("row = 'K_GCEN' and col = 'G_CEN' and ref = 'K3a'")),
        "saving_sta": sql(ents("row = 'K_GSTA' and col = 'G_STA' and ref = 'K3a'")),
        "saving_gg": total("saving_cen", "saving_sta"),
        "saving_gg_gdp": ratio_gdp("saving_gg"),
        "invest_cen": sql(ents("col = 'K_GCEN' and ref in ('I1a', 'I3a')")),
        "invest_sta": sql(ents("col = 'K_GSTA' and ref = 'I1a'")),
        "captr_cen": sql(ents("col = 'K_GCEN' and ref in ('K6', 'R2k')")),
        "captr_sta": sql(ents("col = 'K_GSTA' and ref = 'K6'")),
    }
    for k, acct in (("cen", "K_GCEN"), ("sta", "K_GSTA")):
        f[f"nonfin_in_{k}"] = sql(f"select sum(value) from s where row = '{acct}' and col not in {inst}")
        f[f"nonfin_out_{k}"] = sql(f"select sum(value) from s where col = '{acct}' and row not in {inst}")
        # net borrowing = minus net lending: positive when the government borrows
        f[f"nb_{k}"] = minus(f"nonfin_out_{k}", f"nonfin_in_{k}")
        f[f"assets_{k}"] = sql(f"select sum(value) from s where col = '{acct}' and row in {inst}")
        f[f"liab_{k}"] = sql(f"select sum(value) from s where row = '{acct}' and col in {inst}")
        f[f"nb_{k}_fin"] = minus(f"liab_{k}", f"assets_{k}")
        f[f"nb_{k}_gdp"] = ratio_gdp(f"nb_{k}")
    f |= {
        "nb_gg": total("nb_cen", "nb_sta"),
        "nb_gg_gdp": ratio_gdp("nb_gg"),
        "liab_cen_gsec": sql(cells("('K_GCEN')", "('I_GSEC')")),
        "liab_cen_ssav": sql(cells("('K_GCEN')", "('I_SSAV')")),
        "liab_cen_other": sql(
            f"select sum(value) from s where row = 'K_GCEN' and col in {inst} and col not in ('I_GSEC', 'I_SSAV')"
        ),
        "liab_sta_gsec": sql(cells("('K_GSTA')", "('I_GSEC')")),
        "liab_sta_loan": sql(cells("('K_GSTA')", "('I_LOAN')")),
        "liab_sta_other": sql(
            f"select sum(value) from s where row = 'K_GSTA' and col in {inst} and col not in ('I_GSEC', 'I_LOAN')"
        ),
        "assets_cen_eqty": sql(cells("('I_EQTY')", "('K_GCEN')")),
        "assets_cen_loan": sql(cells("('I_LOAN')", "('K_GCEN')")),
        "assets_cen_k9": sql(ents("row = 'I_OTHR' and col = 'K_GCEN' and ref = 'K9'")),
        "assets_cen_k9b": sql(ents("row = 'I_OTHR' and col = 'K_GCEN' and ref = 'K9b'")),
        "assets_cen_k9_net": total("assets_cen_k9", "assets_cen_k9b"),
        "assets_cen_named": total("assets_cen_eqty", "assets_cen_loan", "assets_cen_k9_net"),
        "assets_cen_rest": minus("assets_cen", "assets_cen_named"),
        "assets_sta_depo": sql(cells("('I_DEPO')", "('K_GSTA')")),
        "assets_sta_k9": sql(ents("row = 'I_OTHR' and col = 'K_GSTA' and ref = 'K9'")),
        "assets_sta_named": total("assets_sta_depo", "assets_sta_k9"),
        "assets_sta_rest": minus("assets_sta", "assets_sta_named"),
        "gsec_issued": sql(cells(KGOVS, "('I_GSEC')")),
        "gsec_bought": sql("select sum(value) from s where row = 'I_GSEC'"),
        "gsec_bank": sql(cells("('I_GSEC')", "('K_BANK')")),
        "gsec_insp": sql(cells("('I_GSEC')", "('K_INSP')")),
        "gsec_row": sql(cells("('I_GSEC')", "('K_ROW')")),
        "gsec_nbfc_mf": sql(cells("('I_GSEC')", "('K_NBFC', 'K_MUTF')")),
        "gsec_hh": sql(cells("('I_GSEC')", "('K_HH')")),
        "gsec_rbi": sql(cells("('I_GSEC')", "('K_RBI')")),
        "gsec_others": sql(
            "select sum(value) from s where row = 'I_GSEC' and col not in "
            "('K_BANK', 'K_INSP', 'K_ROW', 'K_NBFC', 'K_MUTF', 'K_HH', 'K_RBI')"
        ),
        "hhfin_depo": sql(ents("row = 'I_DEPO' and col = 'K_HH' and ref = 'K7a'")),
        "hhfin_inpe": sql(ents("row = 'I_INPE' and col = 'K_HH' and ref = 'K7a'")),
        "hhfin_ssav": sql(ents("row = 'I_SSAV' and col = 'K_HH' and ref = 'K7a'")),
        "int_cen_prev": lambda c, v: ts_main(c, "F25", "2022-23")[0],
        "int_cen": lambda c, v: ts_main(c, "F25", "2023-24")[0],
        "int_cen_gdp": lambda c, v: ts_share(c, "F25", "2023-24"),
        "int_sta": lambda c, v: ts_main(c, "F26", "2023-24")[0],
        "int_sta_gdp": lambda c, v: ts_share(c, "F26", "2023-24"),
    }
    for k in ("bank", "insp", "row", "hh"):
        f[f"gsec_{k}_per100"] = per100(f"gsec_{k}", "gsec_issued")
    return f


SPECS: dict[str, Callable[[], dict[str, Fig]]] = {
    "gst-rupee": gst_rupee,
    "remittance-dubai": remittance_dubai,
    "deficit-funding": deficit_funding,
}


def evaluate(c: duckdb.DuckDBPyConnection, slug: str) -> dict[str, float]:
    """Evaluate in dependency order: retry figures whose inputs are not computed yet."""
    pending = dict(SPECS[slug]())
    done: dict[str, float] = {}
    while pending:
        progressed = False
        for fid, fn in list(pending.items()):
            try:
                done[fid] = fn(c, done)
            except KeyError:
                continue
            del pending[fid]
            progressed = True
        assert progressed, f"{slug}: unresolvable figures {sorted(pending)}"
    return done


@pytest.fixture(scope="module")
def values(con: duckdb.DuckDBPyConnection) -> dict[str, dict[str, float]]:
    return {slug: evaluate(con, slug) for slug in SLUGS}


def load_yaml(slug: str) -> dict:
    return yaml.safe_load((STORIES / f"{slug}.yaml").read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------- spec <-> recomputation


@pytest.mark.parametrize("slug", SLUGS)
def test_every_yaml_figure_is_recomputed_here(slug: str) -> None:
    spec = load_yaml(slug)
    assert spec["slug"] == slug
    assert set(spec["figures"]) == set(SPECS[slug]()), "figure ids differ between the YAML and this test"
    used = {fid for step in spec["steps"] for fid in step["figures"]}
    assert used <= set(spec["figures"]), f"steps name unknown figures: {sorted(used - set(spec['figures']))}"
    ids = [s["id"] for s in spec["steps"]]
    assert len(ids) == len(set(ids)), "duplicate step ids"


# ------------------------------------------------------------------------------- identities in the data


def test_gst_satellite_shares_add_up(con: duckdb.DuckDBPyConnection, values: dict[str, dict[str, float]]) -> None:
    """Each tax account's rescaled p7b parts add up to its balanced total; for GST the five use types are all."""
    for acct in ("T_CGST", "T_SGST", "T_GCES", "T_UEXC", "T_SVAT", "T_SEXC", "T_OPRT"):
        uses = [
            r[0]
            for r in con.execute(
                "select distinct use_type from p7b where tax_account = ? order by 1", [acct]
            ).fetchall()
        ]
        parts = sum(p7b_rescaled(con, acct, u) for u in uses)
        assert parts == pytest.approx(q(con, cells(f"('{acct}')", g("COM"))), abs=0.01), acct
    v = values["gst-rupee"]
    assert sum(v[f"till_{u}"] for u in ("pfce", "ic", "gfcf", "gfce", "valu")) == pytest.approx(
        v["gst_total"], abs=0.01
    )


def test_gst_receipts_equal_the_commodity_side(con: duckdb.DuckDBPyConnection) -> None:
    """The story reads GST levels on the receipt side and splits them on the commodity side (T_* <- C_*).
    Each tax account pays one government and balances, so the two sides must agree."""
    for acct, gov in (("T_CGST", "G_CEN"), ("T_SGST", "G_STA"), ("T_GCES", "G_CEN")):
        receipts = q(con, cells(f"('{gov}')", f"('{acct}')"))
        assert receipts == pytest.approx(q(con, cells(f"('{acct}')", g("COM"))), abs=0.01), acct
        assert receipts == pytest.approx(q(con, f"select sum(value) from s where col = '{acct}'"), abs=0.01), acct


def test_net_borrowing_equals_liabilities_minus_assets(values: dict[str, dict[str, float]]) -> None:
    v = values["deficit-funding"]
    for k in ("cen", "sta"):
        assert v[f"nb_{k}"] == pytest.approx(v[f"nb_{k}_fin"], abs=0.01), k
    assert v["assets_cen_named"] + v["assets_cen_rest"] == pytest.approx(v["assets_cen"], abs=0.01)
    assert v["liab_cen_gsec"] + v["liab_cen_ssav"] + v["liab_cen_other"] == pytest.approx(v["liab_cen"], abs=0.01)
    assert v["liab_sta_gsec"] + v["liab_sta_loan"] + v["liab_sta_other"] == pytest.approx(v["liab_sta"], abs=0.01)
    assert v["gsec_issued"] == pytest.approx(v["gsec_bought"], abs=0.01)


def test_outlay_parts_are_complete(values: dict[str, dict[str, float]]) -> None:
    r = values["remittance-dubai"]
    assert r["hh_outlays"] == pytest.approx(r["hh_outlays_all"], abs=0.01)
    assert r["remit_rural"] + r["remit_urban"] == pytest.approx(r["remit_total"], abs=0.01)
    gst = values["gst-rupee"]
    current = ("goods_services", "interest", "pensions", "cash_transfers", "corp_transfers")
    assert sum(gst[f"gg_{k}"] for k in current) == pytest.approx(gst["gg_current"], abs=0.01)
    assert gst["gst_centre"] + gst["gst_states"] == pytest.approx(gst["gst_total"], abs=0.01)
    assert gst["cgst_total"] + gst["sgst_total"] + gst["cess_total"] == pytest.approx(gst["gst_total"], abs=0.01)


def test_claims_made_in_the_story_text(con: duckdb.DuckDBPyConnection, values: dict[str, dict[str, float]]) -> None:
    """The MDX states these facts in words (no digits), so they are pinned to the data here."""
    gst, rem, dfc = values["gst-rupee"], values["remittance-dubai"], values["deficit-funding"]
    # gst-rupee: the four named products are the four largest, construction first
    top = [
        r[0]
        for r in con.execute(
            f"select col from s where row in {GST} group by col order by sum(value) desc limit 4"
        ).fetchall()
    ]
    assert top[0] == "C_CNST" and set(top) == {"C_CNST", "C_TREQ", "C_CHEM", "C_TXAP"}
    # "households pay more than half of all GST at the till; investment and business inputs about a fifth each"
    tills = {u: gst[f"till_{u}"] for u in ("pfce", "ic", "gfcf", "gfce", "valu")}
    assert max(tills, key=tills.get) == "pfce" and gst["till_pfce_per100"] > 50
    assert 15 < gst["till_ic_per100"] < 25 and 15 < gst["till_gfcf_per100"] < 25
    # "CGST and SGST are about the same size; the cess is much smaller"
    assert abs(gst["cgst_per100"] - gst["sgst_per100"]) < 5 and gst["cess_per100"] < 15
    # "most of the cess goes on to the States, but not all of it"; transfers are positive; repayment negative
    assert 50 < gst["cess_passed_per100"] < 100
    assert gst["b2b_repaid"] < 0 and gst["b2b_repaid"] == pytest.approx(-gst["cess_loan_transfer"], abs=0.01)
    # "the States keep more than half of all GST"; the cess-loan transfer passes through them and is apart
    assert gst["gst_to_states_kept_per100"] > 50 and gst["cess_loan_per100_gst"] > 0
    assert gst["gst_to_states_kept_per100"] + gst["cess_loan_per100_gst"] == pytest.approx(
        100 * (gst["gst_states"] + gst["devol_cgst"] + gst["cess_passed"]) / gst["gst_total"], abs=1e-6
    )
    # spending: goods and services first, interest second; subsidies are negative taxes
    gg = {
        k: gst[f"gg_{k}"]
        for k in ("goods_services", "interest", "pensions", "cash_transfers", "corp_transfers", "capital")
    }
    assert sorted(gg, key=gg.get, reverse=True)[:2] == ["goods_services", "interest"]
    assert gst["gg_product_subsidies"] < 0 and gst["gg_production_subsidies"] < 0
    # "adding them back would raise outlays by ... for every hundred rupees": a positive amount
    assert gst["gg_subsidies_paid"] > 0 and gst["gg_subsidies_per100"] > 0
    # remittance: the USA is the largest source and the UAE the second
    shares = dict(con.execute("select country, value from s3 where measure = 'share'").fetchall())
    ranked = sorted((k for k in shares if k != "others"), key=shares.get, reverse=True)
    assert ranked[:2] == ["USA", "ARE"]
    # richer households receive more than poorer ones; urban groups receive more than rural ones
    assert rem["remit_top"] > rem["remit_bottom"] and rem["remit_urban"] > rem["remit_rural"]
    # the rupee amount grew many times over while the share of GDP stayed in the same range
    assert rem["remit_value_latest"] > 5 * rem["remit_value_first"]
    assert abs(rem["remit_share_2023"] - rem["remit_share_first"]) < 0.01
    # consumption is the largest use of household income, saving the second; the residual is positive
    hh = {p: rem[f"hh_{p}"] for p in ("consumption", "saving", "taxes", "finance", "abroad", "to_gov", "residual")}
    assert sorted(hh, key=hh.get, reverse=True)[:2] == ["consumption", "saving"]
    assert rem["hh_residual"] > 0
    # deficit: the Centre dissaves, the States save; "both the Centre and the States were net borrowers"
    assert dfc["saving_cen"] < 0 < dfc["saving_sta"] and dfc["saving_gg"] < 0
    assert dfc["nb_cen"] > 0 and dfc["nb_sta"] > 0 and dfc["nb_cen"] > dfc["nb_sta"]
    # buyers: banks first, insurers and pension funds second; the RBI a net seller
    buyers = {k: dfc[f"gsec_{k}"] for k in ("bank", "insp", "row", "nbfc_mf", "hh")}
    assert sorted(buyers, key=buyers.get, reverse=True)[:2] == ["bank", "insp"]
    assert dfc["gsec_rbi"] < 0
    # "so the buyers' shares add up to more than a hundred"
    assert (
        sum(dfc[f"gsec_{k}_per100"] for k in ("bank", "insp", "row", "hh"))
        + 100 * dfc["gsec_nbfc_mf"] / dfc["gsec_issued"]
        > 100
    )
    # the Centre's interest bill rose; "the amount owed rose" (K9b positive); the Centre's residual line is
    # K9 + K9b (the K9b offset sits inside K9_GCEN), so it differs from K9 alone by exactly K9b
    assert dfc["int_cen"] > dfc["int_cen_prev"]
    assert dfc["assets_sta_k9"] < 0 and dfc["assets_cen_k9b"] > 0
    assert dfc["assets_cen_k9_net"] == pytest.approx(dfc["assets_cen_k9"] + dfc["assets_cen_k9b"], abs=0.01)


# ------------------------------------------------------------------------------- step views exist


def _hierarchy() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """account -> level-0 id; account -> level-1 id (or the account when it is a level-1 leaf); every node id."""
    h = yaml.safe_load((REPO / "pipeline" / "export" / "hierarchy.yaml").read_text(encoding="utf-8"))
    l0: dict[str, str] = {}
    l1: dict[str, str] = {}
    for node in h["nodes"]:
        for child in node["children"]:
            if "account" in child:
                l0[child["account"]] = node["id"]
                l1[child["account"]] = child["account"]
            else:
                for a in child["accounts"]:
                    l0[a] = node["id"]
                    l1[a] = child["id"]
    return l0, l1, {}


def visible(account: str, preset: str, expanded: list[str], l0: dict[str, str], l1: dict[str, str]) -> str:
    top = l0[account]
    if preset == "simple":
        assert not expanded, "a simple-preset step cannot expand nodes (PLAN s.3.2)"
        return {"PRDS": "PRODUCERS", "PROD": "PRODUCERS", "FINM": "SI"}.get(top, top)
    if top not in expanded:
        return top
    mid = l1[account]
    return account if mid in expanded else mid


@pytest.mark.parametrize("slug", SLUGS)
def test_step_views_name_existing_links(con: duckdb.DuckDBPyConnection, slug: str) -> None:
    l0, l1, _ = _hierarchy()
    cell_rows = con.execute("select row, col, value from s where value <> 0").fetchall()
    for step in load_yaml(slug)["steps"]:
        view = step["view"]
        assert view["view"] == "sam" and view["year"] == "2023-24", step["id"]
        links: set[str] = set()
        nodes: set[str] = set()
        for row, col, value in cell_rows:
            payer = visible(col, view["preset"], view["expanded"], l0, l1)
            receiver = visible(row, view["preset"], view["expanded"], l0, l1)
            nodes |= {payer, receiver}
            if payer != receiver:
                links.add(f"{payer}--{receiver}" + ("" if value > 0 else "~neg"))
        wanted = list(view["highlight"]) + ([view["select"]] if view["select"] else [])
        missing = [i for i in wanted if i not in links and i not in nodes]
        assert not missing, f"{slug}/{step['id']}: not drawn at this zoom: {missing}"


# ------------------------------------------------------------------------------- the exported JSON


def exported_story(slug: str) -> dict:
    index_path = REPO / "web" / "public" / "data" / "index.json"
    if not index_path.exists():
        pytest.skip("REAL EXPORT NOT FOUND: run `uv run python -m pipeline export` (story values not compared)")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert not index.get("fixture"), "web/public/data holds the fixture, not the real export"
    rel = f"stories/{slug}.json"
    assert rel in index["files"], f"{rel} missing from index.json files"
    return json.loads((index_path.parent / index["data_version"] / rel).read_text(encoding="utf-8"))


@pytest.mark.parametrize("slug", SLUGS)
def test_exported_values_match_duckdb(values: dict[str, dict[str, float]], slug: str) -> None:
    story = exported_story(slug)
    spec = load_yaml(slug)
    assert story["slug"] == slug
    assert set(story["figures"]) == set(spec["figures"])
    assert [s["id"] for s in story["steps"]] == [s["id"] for s in spec["steps"]]
    bad = []
    for fid, fig in story["figures"].items():
        assert fig["unit"] == spec["figures"][fid]["unit"], fid
        want = values[slug][fid]
        if abs(fig["value"] - want) > TOL[fig["unit"]]:
            bad.append(f"{fid}: exported {fig['value']!r}, DuckDB {want!r}")
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("slug", SLUGS)
def test_exported_labels_are_honest(slug: str) -> None:
    """Estimated methods stay estimated (PLAN s.3.8); official totals only where the spec allows them."""
    story = exported_story(slug)
    spec = load_yaml(slug)
    for fid, fig in story["figures"].items():
        kind = spec["figures"][fid]["kind"]
        assert abs(sum(fig["composition"].values()) - 1) < 1e-3, fid
        if kind in ("satellite_share", "satellite_sum", "prorata_sum"):
            assert fig["split"] == "estimated" and fig["total"] is None, f"{fid}: {kind} must be estimated"
        assert fig["method"], f"{fid}: no method text"
    if slug == "remittance-dubai":
        assert story["figures"]["remit_total"]["total"] == "official"  # the R11 total is published (F43 passes)
        assert story["figures"]["remit_rural"]["split"] in ("estimated", "balancing_set")
    if slug == "deficit-funding":
        # the text says "That total is published" (NAS 1.9, constraint gov.k3.gg_saving)
        assert story["figures"]["saving_gg"]["total"] == "official"
        assert story["figures"]["saving_cen"]["total"] is None
        # "the households' direct purchases are a published figure"; the institutions' are not
        assert story["figures"]["gsec_hh"]["split"] == "official"
        assert all(story["figures"][f"gsec_{k}"]["split"] != "official" for k in ("bank", "insp", "row", "nbfc_mf"))
    if slug == "gst-rupee":
        assert story["figures"]["comp_grants"]["split"] == "official"
        assert story["figures"]["devol_cgst"]["split"] == "official"
        # the text says CGST and the cess sit at the edge of a judgement band and that the notes flag them
        for fid in ("cgst_total", "cess_total"):
            fig = story["figures"][fid]
            assert "judgement_band" in fig["flags"] and fig["split"] == "balancing_set", fid
        # products step: the shares are estimated, except construction, which balancing moved (level unexplained)
        cnst = story["figures"]["gst_cnst_per100"]
        assert cnst["split"] == "balancing_set" and "level_unexplained" in cnst["flags"]
        for k in ("treq", "chem", "txap"):
            assert story["figures"][f"gst_{k}_per100"]["split"] == "estimated", k
        # the text says the till shares are estimates
        for u in ("pfce", "ic", "gfcf", "gfce", "valu"):
            assert story["figures"][f"till_{u}_per100"]["split"] == "estimated", u
