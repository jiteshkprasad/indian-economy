"""Independent verification of the SAM `households` block (Phase 2 verifier, 2026-09-30; SPEC s.3 rule 3).

This file does NOT import pipeline.sam (no block, framework or spec code) and does not use polars.
Every expected number is recomputed here with DuckDB SQL (plus a few lines of plain Python for the
log-MPCE placement models) from:
- data/clean/hces_consumption: A2 (persons, households, avg MPCE), A10F (item value / quantity per person
  per 30 days by all-India fractile class), A10SW (State item imputed values, S8 memo check);
  survey window period '2023-08/2024-07' only;
- data/clean/io_tables: SUT 2023-24 use (PFCE and GFCE by product) and supply (p144 by industry), ICIO India;
- data/clean/mospi_nas_2026: St 1.1 PFCE, 1.13 FISIM to PFCE, 1.14, 8.13;
- data/clean/rbi_financial_accounts (T52(b) household stocks), rbi_banking_corporate (RTP SCB rates);
- data/clean/labour_enterprise_surveys: AIDIS 2019 quintile table (i9, i5) and press note;
- data/concordance/io_tables_sut_product_to_sam34.csv and the new hces2324_item_to_sut_product.csv
  (committed, DECISIONS D2-15; its rules are re-checked here against A10F item roles);
- data/sam/2023-24/blocks/*_entries.parquet / *_constraints.parquet of all built blocks (double counting,
  production's pfce.* targets).
It is compared with the block's written outputs (data/sam/2023-24/blocks/households_*): a census of all
1,230 entries, all 4 constraints and every numeric satellite row that has an independent recomputation.

Method rules recomputed (docs/phase2/plans/households.md s.2 and s.8, CROSS_REVIEW XR-5/10/15/20/22, gap map):
- groups: HCES person quintiles within rural/urban (p00_05+p05_10+p10_20, p20_30+p30_40, ... p80_90+p90_95+p95_100);
- HCES spending V(item, group) = value per person (30 d) x A2 persons x 12 / 1e7, summed over classes;
- C1a/C4d: SUT PFCE of product p x V_key(p, g) / sum_g V_key(p, g) (key items from the concordance);
- C4a: govt = SUT supply p144 x industry 67; rest = PFCE p144 - govt; actual = rest x r, imputed = rest x (1-r),
  r = V520 / (V520 + V539); keys 520 (actual, govt proxy), 539 (imputed);
- C4b: FISIM (NAS 1.13) split by (r* - r_D) x D and (r_L - r*) x L, r* = RTP SCB return on investments,
  r_D = cost of deposits, r_L = return on advances, D / L = average of 31 Mar 2023 and 2024 T52(b) stocks;
  group keys = AIDIS per-household values by AIDIS class mapped by cumulative HCES household overlap;
  FISIM_D by AIDIS financial assets (plan s.2.4 step 3), FISIM_L by institutional cash loans;
  explicit fees = SUT p142 - FISIM and insurance = SUT p143, both keyed by AIDIS financial assets;
- S8 (satellite): HCES free rice (061) / wheat (062) quantity shares x SUT GFCE on paddy / wheat.

Findings recorded in docs/phase2/verify/households.md (V-HH-n). A confirmed defect is a strict xfail with its id.
Builder fixes of 2026-09-30 (docs/phase2/issues/households.md, "Verification dispositions"): V-HH-1 fixed, so its
strict xfail is now an ordinary test; V-HH-2 fixed, so the census keys FISIM_D by aidis_fin_assets (was
aidis_deposits, the defect it pinned). No other expectation was changed.
"""

# ruff: noqa: E501  (long DuckDB SQL literals are kept on one line so each rule reads as one statement)
from __future__ import annotations

import math
from functools import cache
from pathlib import Path

import duckdb
import pytest

pytestmark = [pytest.mark.quality, pytest.mark.sam]

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean"
BLOCKS = ROOT / "data" / "sam" / "2023-24" / "blocks"
SAT = BLOCKS / "households_satellites"
CONC = ROOT / "data" / "concordance"
YEAR = "2023-24"
SW = "2023-08/2024-07"  # HCES 2023-24 survey window
TOL = 0.01  # Rs crore: census tolerance
GROUPS = ["H_R1", "H_R2", "H_R3", "H_R4", "H_R5", "H_U1", "H_U2", "H_U3", "H_U4", "H_U5"]
CLASSES = ["p00_05", "p05_10", "p10_20", "p20_30", "p30_40", "p40_50", "p50_60", "p60_70", "p70_80", "p80_90",
           "p90_95", "p95_100"]  # fmt: skip
CLASS_Q = [1, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 5]  # plan s.2.0: person quintile of each A2 fractile class


def _p(path: Path) -> str:
    return path.as_posix()


def _grp_values() -> str:
    rows = []
    for area, a in (("rural", "R"), ("urban", "U")):
        for cls, qn in zip(CLASSES, CLASS_Q, strict=True):
            rows.append(f"('{area}_{cls}', 'H_{a}{qn}', '{area}')")
    return ", ".join(rows)


@cache
def con() -> duckdb.DuckDBPyConnection:
    for f in ("households_entries", "households_constraints", "households_provenance", "households_checks"):
        if not (BLOCKS / f"{f}.parquet").exists():
            pytest.fail(f"{f}.parquet missing: run `uv run python -m pipeline sam households`")
    c = duckdb.connect()
    hc = CLEAN / "hces_consumption"
    io = CLEAN / "io_tables"
    les = CLEAN / "labour_enterprise_surveys"
    c.execute(f"""
        create table grp as select * from (values {_grp_values()}) t(cls, grp, area);
        create table a2 as select geography, household_group cls, item_code, value, prov_id
          from '{_p(hc / "hces_consumption_a2_fractile_persons.parquet")}'
          where period = '{SW}' and item_code in ('persons', 'households', 'avg_mpce');
        create table a10 as select substr(product, 6) item, household_group cls, item_code, value, unit, prov_id,
               regexp_extract(dim_other, 'item_role=([a-z_]+)', 1) irole
          from '{_p(hc / "hces_consumption_a10f_item_fractile.parquet")}' where period = '{SW}';
        create table roles as select item, any_value(irole) irole, count(distinct irole) nroles from a10 group by 1;
        -- HCES spending by item and SAM group, Rs crore a year at HCES scale
        create table V as
          select v.item, g.grp, sum(v.value * p.value * 12 / 1e7) val
          from a10 v join a2 p on p.cls = v.cls and p.item_code = 'persons' and p.geography = 'IN'
          join grp g on g.cls = v.cls
          where v.item_code = 'value_per_person_30d' group by all;
        create table Q as
          select v.item, g.grp, sum(v.value * p.value * 12) tonnes
          from a10 v join a2 p on p.cls = v.cls and p.item_code = 'persons' and p.geography = 'IN'
          join grp g on g.cls = v.cls
          where v.item_code = 'qty_per_person_30d' and v.unit = 'tonnes' group by all;
        create table conc as select * from read_csv('{_p(CONC / "hces2324_item_to_sut_product.csv")}', all_varchar=true);
        create table pmap as select cast(sut_product as integer) p, commodity
          from read_csv('{_p(CONC / "io_tables_sut_product_to_sam34.csv")}', all_varchar=true);
        create table use as select series_id, value, prov_id from '{_p(io / "io_tables_sut_use.parquet")}'
          where period = '{YEAR}';
        create table sup as select series_id, value, prov_id from '{_p(io / "io_tables_sut_supply.parquet")}'
          where period = '{YEAR}';
        create table pfce as
          select cast(regexp_extract(series_id, 'sut_p(\\d{{3}})', 1) as integer) p, value, prov_id from use
          where regexp_matches(series_id, '^use\\.pfce\\.sut_p\\d{{3}}\\.current$');
        create table theirs as select * from '{_p(BLOCKS / "households_entries.parquet")}';
        create table tcons as select * from '{_p(BLOCKS / "households_constraints.parquet")}';
        create table tprov as select * from '{_p(BLOCKS / "households_provenance.parquet")}';
        create table tchecks as select * from '{_p(BLOCKS / "households_checks.parquet")}';
        create table allent as select * from read_parquet('{_p(BLOCKS)}/*_entries.parquet', union_by_name=true);
        create table allcons as select * from read_parquet('{_p(BLOCKS)}/*_constraints.parquet', union_by_name=true);
        create table aidis as select series_id, value, prov_id
          from '{_p(les / "labour_enterprise_surveys_aidis_2019_quintile.parquet")}';
        create table pn as select series_id, value, prov_id
          from '{_p(les / "labour_enterprise_surveys_aidis_2019_press_note.parquet")}';
    """)
    # ---------------------------------------------------------------- C1a / C4d: HCES item keys by product
    c.execute("""
        create table keyv as
          select cast(k.sut_product as integer) p, k.ref, k.component, k.key_quality, V.grp, sum(V.val) kv
          from conc k join V on V.item = k.hces_item where k.ref in ('C1a', 'C4d') group by all;
        create table exp_c1 as
          select m.commodity r, kv.grp c, kv.ref rf,
                 case when kv.ref = 'C1a' then 'sut_p' || lpad(cast(kv.p as varchar), 3, '0') else kv.component end comp,
                 f.value * kv.kv / sum(kv.kv) over (partition by kv.p, kv.ref) v,
                 kv.p, kv.key_quality q
          from keyv kv join pfce f on f.p = kv.p join pmap m on m.p = kv.p;
    """)
    # ---------------------------------------------------------------- C4a dwellings
    c.execute("""
        create table c4a_par as select
          (select value from use where series_id = 'use.pfce.sut_p144.current') pfce144,
          (select value from sup where series_id = 'supply.output.sut_p144.sut_i67.current') govt,
          (select sum(val) from V where item = '520') v520,
          (select sum(val) from V where item = '539') v539;
        create table exp_c4a as
          with k as (select grp, sum(val) filter (where item = '520') k520, sum(val) filter (where item = '539') k539
                     from V where item in ('520', '539') group by 1),
               s as (select *, v520 / (v520 + v539) r from c4a_par)
          select 'C_DWEL' r, k.grp c, 'C4a' rf, 'actual_rent' comp,
                 (pfce144 - govt) * r * k520 / sum(k520) over () v from k, s
          union all select 'C_DWEL', k.grp, 'C4a', 'imputed_rent',
                 (pfce144 - govt) * (1 - r) * k539 / sum(k539) over () from k, s
          union all select 'C_DWEL', k.grp, 'C4a', 'govt_housing', govt * k520 / sum(k520) over () from k, s;
    """)
    # ---------------------------------------------------------------- C4b: FISIM split (XR-5) and AIDIS keys
    t52 = CLEAN / "rbi_financial_accounts" / "rbi_financial_accounts_hh_finsav_52ab.parquet"
    rtp = CLEAN / "rbi_banking_corporate" / "rbi_banking_corporate_rtp_banks.parquet"
    c.execute(f"""
        create table t52 as select series_id, period, value from '{_p(t52)}'
          where period in ('2023-03-31', '2024-03-31')
            and series_id in ('t52b.fa_deposits_bank.current', 't52b.fa_deposits_nonbank_ofi.current', 't52b.fl.current');
        create table rates as select regexp_extract(series_id, 'scb_cost_return\\.([a-z_]+)\\.scb', 1) k, value
          from '{_p(rtp)}' where period = '{YEAR}' and vintage = '2025-12-29'
            and series_id in ('rtp.scb_cost_return.return_on_investments.scb',
                              'rtp.scb_cost_return.cost_of_deposits.scb',
                              'rtp.scb_cost_return.return_on_advances.scb');
        create table fisim_par as select *,
            (rs - rd) * D / ((rs - rd) * D + (rl - rs) * L) dshare,
            fisim * (rs - rd) * D / ((rs - rd) * D + (rl - rs) * L) fd,
            fisim * (rl - rs) * L / ((rs - rd) * D + (rl - rs) * L) fl,
            D24 / (D24 + L24) dshare_stock
          from (select
            (select value from rates where k = 'return_on_investments') rs,
            (select value from rates where k = 'cost_of_deposits') rd,
            (select value from rates where k = 'return_on_advances') rl,
            (select sum(value) / 2 from t52 where series_id <> 't52b.fl.current') D,
            (select sum(value) / 2 from t52 where series_id = 't52b.fl.current') L,
            (select sum(value) from t52 where series_id <> 't52b.fl.current' and period = '2024-03-31') D24,
            (select sum(value) from t52 where series_id = 't52b.fl.current' and period = '2024-03-31') L24,
            (select value from '{_p(CLEAN / "mospi_nas_2026" / "mospi_nas_2026_s1_13.parquet")}'
               where period = '{YEAR}' and series_id = 's1_13.private_final_consumption_expenditure.current') fisim
          );
        -- cumulative HCES household range of each SAM group within its area (groups ordered by MPCE)
        create table ghh as select g.area, g.grp, sum(a.value) hh from grp g
          join a2 a on a.cls = g.cls and a.geography = 'IN' and a.item_code = 'households' group by all;
        create table grange as select area, grp, hh,
            (sum(hh) over (partition by area order by grp) - hh) / sum(hh) over (partition by area) lo,
            sum(hh) over (partition by area order by grp) / sum(hh) over (partition by area) hi,
            sum(hh) over (partition by area) area_hh
          from ghh;
        create table aclass as select * from (values (1), (2), (3), (4), (5)) t(k);
        create table overlap as select g.area, g.grp, a.k,
            greatest(0, least(g.hi, a.k * 0.2) - greatest(g.lo, (a.k - 1) * 0.2)) * g.area_hh ov_hh
          from grange g, aclass a;
        create table aidis_per_hh as
          select regexp_extract(series_id, '^i[59]\\.([a-z_]+)_per_hh', 1) measure,
                 regexp_extract(series_id, '\\.(rural|urban)_q', 1) area,
                 cast(regexp_extract(series_id, '_q(\\d)\\.all', 1) as integer) k, value
          from aidis where regexp_matches(series_id, '^i9\\.(financial_assets|cash_loan|fixed_assets|valuables)_per_hh\\.(rural|urban)_q\\d\\.all\\.current$')
             or regexp_matches(series_id, '^i5\\.ava_per_hh\\.(rural|urban)_q\\d\\.all\\.current$');
        create table pnv as select series_id, value from pn;
        create table akeys as
          select o.grp, o.area, p.measure, sum(o.ov_hh * p.value) / 1e7 lvl
          from overlap o join aidis_per_hh p on p.area = o.area and p.k = o.k group by all;
        create table area_par as select area,
            (select value / 100 from pnv where series_id = 'pn.debt_share_institutional.' || area || '.all') inst,
            (select value / 100 from pnv where series_id = 'pn.debt_share_noninstitutional.' || area || '.all') noninst,
            least(1.0, (select value / 100 from pnv where series_id = 'pn.asset_share_deposits.' || area || '.all')
                  * (select value from pnv where series_id = 'pn.ava_per_hh.' || area || '.all.current')
                  / (select value from pnv where series_id = 'pn.ava_financial_per_hh.' || area || '.all.current')) dep_ratio
          from (values ('rural'), ('urban')) t(area);
        create table hh_key_exp as
          select grp, 'aidis_fin_assets' akey, lvl from akeys where measure = 'financial_assets'
          union all select grp, 'aidis_cash_loans', lvl from akeys where measure = 'cash_loan'
          union all select k.grp, 'aidis_inst_loans', k.lvl * a.inst from akeys k join area_par a using (area)
            where measure = 'cash_loan'
          union all select k.grp, 'aidis_noninst_loans', k.lvl * a.noninst from akeys k join area_par a using (area)
            where measure = 'cash_loan'
          union all select grp, 'aidis_fixed_assets', lvl from akeys where measure = 'fixed_assets'
          union all select grp, 'aidis_valuables', lvl from akeys where measure = 'valuables'
          union all select grp, 'aidis_total_assets', lvl from akeys where measure = 'ava'
          union all select k.grp, 'aidis_deposits', k.lvl * a.dep_ratio from akeys k join area_par a using (area)
            where measure = 'financial_assets';
        create table exp_c4b as
          with sh as (select grp, akey, lvl / sum(lvl) over (partition by akey) s from hh_key_exp)
          select 'C_FINS' r, grp c, 'C4b' rf, 'fisim_deposits' comp, fd * s v from sh, fisim_par
            where akey = 'aidis_fin_assets'  -- plan s.2.4 step 3 (V-HH-2 fixed; was aidis_deposits)
          union all select 'C_FINS', grp, 'C4b', 'fisim_loans', fl * s from sh, fisim_par where akey = 'aidis_inst_loans'
          union all select 'C_FINS', grp, 'C4b', 'explicit_fees',
            ((select value from use where series_id = 'use.pfce.sut_p142.current') - fisim) * s
            from sh, fisim_par where akey = 'aidis_fin_assets'
          union all select 'C_INSR', grp, 'C4b', 'insurance_service',
            (select value from use where series_id = 'use.pfce.sut_p143.current') * s
            from sh where akey = 'aidis_fin_assets';
    """)
    c.execute("""
        create table mine as
          select r, c, rf, comp, v from exp_c1 where v <> 0
          union all select * from exp_c4a where v <> 0
          union all select * from exp_c4b where v <> 0;
    """)
    return c


def q(sql: str) -> list[tuple]:
    return con().execute(sql).fetchall()


def one(sql: str):
    rows = q(sql)
    assert len(rows) == 1, (sql, rows)
    return rows[0][0]


def clean_value(rel: str, series_id: str, period: str = YEAR) -> float:
    return one(f"select value from '{_p(CLEAN / rel)}' where period = '{period}' and series_id = '{series_id}'")


def sat(name: str) -> str:
    return f"'{_p(SAT / (name + '.parquet'))}'"


# ------------------------------------------------------------------------------------------ 1 inputs
def test_inputs_single_vintage_and_survey_window():
    assert q(f"select distinct vintage from '{_p(CLEAN / 'hces_consumption' / 'hces_consumption_a10f_item_fractile.parquet')}' "
             f"where period = '{SW}'") == [("2025-01-30",)]  # fmt: skip
    assert one("select count(*) from pfce") == 119
    assert one("select sum(value) from pfce") == pytest.approx(
        one("select value from use where series_id = 'use.pfce.total.current'"), abs=0.01
    )
    # every A2 class row used is in the group map, 24 classes
    assert one("select count(*) from grp") == 24
    assert (
        one("select count(*) from a2 where geography='IN' and item_code='persons' and cls in (select cls from grp)")
        == 24
    )


def test_group_persons_are_quintiles():
    rows = q("""select g.area, g.grp, sum(a.value) from grp g join a2 a on a.cls=g.cls and a.geography='IN'
                and a.item_code='persons' group by all""")
    tot = {}
    for area, _, v in rows:
        tot[area] = tot.get(area, 0) + v
    for area, g, v in rows:
        assert v / tot[area] == pytest.approx(0.2, abs=1e-4), (g, v / tot[area])
    assert sum(tot.values()) == 1_217_643_800


# ------------------------------------------------------------------------------------------ 2 concordance rules
def test_concordance_rules():
    # leaf items only (539 memo only in C4a)
    bad_role = q("""select k.ref, k.hces_item, r.irole from conc k left join roles r on r.item = k.hces_item
                    where not (r.irole = 'leaf' or (k.hces_item = '539' and k.ref = 'C4a' and r.irole = 'memo'))""")
    assert bad_role == []
    excluded_from_c1a = {"640", "641", "642", "643", "061", "062", "070", "071", "072", "073", "074", "075", "282",
                         "520", "539", "522", "405", "406", "408", "411", "412", "413", "414", "421", "422", "424"}  # fmt: skip
    used = {r[0] for r in q("select distinct hces_item from conc where ref = 'C1a'")}
    assert used & excluded_from_c1a == set()
    # every leaf item is used or excluded with a reason
    leaves = {r[0] for r in q("select item from roles where irole = 'leaf'")}
    assert len(leaves) == 381
    covered = {r[0] for r in q("select distinct hces_item from conc")}
    assert leaves - covered == set()
    assert one("select count(*) from conc where ref = 'excluded' and (note is null or note = '')") == 0
    # every PFCE product except 142-144 has a non-empty key; no key on products without PFCE
    keyed = {r[0] for r in q("select distinct cast(sut_product as integer) from conc where ref in ('C1a','C4d')")}
    with_pfce = {r[0] for r in q("select p from pfce where value <> 0")}
    assert with_pfce - keyed == {142, 143, 144}
    assert keyed - with_pfce == set()
    # one key quality per product
    assert (
        q("select sut_product from conc where ref in ('C1a','C4d') group by 1 having count(distinct key_quality) > 1")
        == []
    )


# ------------------------------------------------------------------------------------------ 3 entries census
def test_entry_census_every_value():
    rows = q(f"""
        select coalesce(m.rf, t.ref), coalesce(m.r, t.row), coalesce(m.c, t.col), coalesce(m.comp, t.component),
               m.v, t.value
        from mine m full outer join theirs t
          on m.r = t.row and m.c = t.col and m.rf = t.ref and m.comp = t.component
        where m.v is null or t.value is null or abs(m.v - t.value) > {TOL}
    """)
    assert rows == [], rows[:20]
    assert one("select count(*) from theirs") == one("select count(*) from mine") == 1230
    per_ref = dict(q("select ref, count(*) from theirs group by 1"))
    assert per_ref == {"C1a": 1140, "C4a": 30, "C4b": 40, "C4d": 20}
    assert one("select max(abs(m.v - t.value)) from mine m join theirs t on m.r = t.row and m.c = t.col "
               "and m.rf = t.ref and m.comp = t.component") < 1e-5  # fmt: skip


def test_entry_metadata():
    assert q("select distinct status, role from theirs") == [("estimated", "free")]
    assert one("select count(*) from theirs where tol_rel is not null or bop_function is not null") == 0
    assert one("select count(*) from theirs where value <= 0") == 0
    # confidence: C1a/C4d from the concordance key quality; C4a actual medium, others low; C4b low
    bad = q("""select t.ref, t.row, t.col, t.component, t.confidence, e.q from theirs t
               join exp_c1 e on e.r=t.row and e.c=t.col and e.rf=t.ref and e.comp=t.component
               where t.confidence <> case e.q when 'direct' then 'medium' else 'low' end""")
    assert bad == []  # 1e-11 relative: the framework's 12-significant-digit cap on satellite values
    assert q("select component, confidence from theirs where ref='C4a' group by all order by 1") == [
        ("actual_rent", "medium"), ("govt_housing", "low"), ("imputed_rent", "low")]  # fmt: skip
    assert q("select distinct confidence from theirs where ref='C4b'") == [("low",)]
    assert q("select distinct confidence from theirs where ref='C4d'") == [("medium",)]
    counts = dict(q("select confidence, count(*) from theirs group by 1"))
    assert counts == {"medium": 880, "low": 350}


def test_refs_per_commodity_and_no_double_counting():
    refs = dict(q("select row, string_agg(distinct ref, ',' order by ref) from theirs group by 1"))
    assert refs.pop("C_DWEL") == "C4a"
    assert refs.pop("C_FINS") == "C4b" and refs.pop("C_INSR") == "C4b"
    assert refs.pop("C_HLTH") == "C4d" and refs.pop("C_EDUC") == "C4d"
    assert set(refs.values()) == {"C1a"} and len(refs) == 26
    assert one("select count(*) from theirs where row in ('C_OILG','C_OMIN','C_MTLS') or component = 'sut_p125'") == 0
    # no other block writes COM <- HH (NPISH C4c, free grain, jewellery would all show up here)
    others = q("select block, ref, count(*) from allent where row like 'C\\_%' escape '\\' and col like 'H\\_%' escape '\\' "
               "and block <> 'households' group by all")  # fmt: skip
    assert others == []
    # free PDS grain is GFCE (government C2a) and equals the S8 control
    food = one("select sum(value) from allent where row='C_CROP' and col='G_CEN' and ref='C2a'")
    gfce = one(
        "select sum(value) from use where series_id in ('use.gfce.sut_p001.current','use.gfce.sut_p002.current')"
    )
    assert food == pytest.approx(gfce, abs=0.01)
    # the two SUT PFCE memo rows are not provenance inputs
    memo = one("select string_agg(prov_id, ',') from use where series_id like 'use.pfce.purchases%'")
    assert memo == "io_tables:221b6f549118,io_tables:221b6f549118"
    assert one("select count(*) from tprov where inputs like '%io_tables:221b6f549118%'") == 0


# ------------------------------------------------------------------------------------------ 4 totals
def test_official_totals():
    tot = one("select sum(value) from theirs")
    assert tot == pytest.approx(one("select value from use where series_id='use.pfce.total.current'"), abs=0.01)
    nas11 = clean_value("mospi_nas_2026/mospi_nas_2026_s1_1.parquet", "s1_1.pfce.current")
    assert abs(tot - nas11) <= 1.0
    # per commodity = production's pfce.* targets (not re-declared here, XR-15)
    bad = q("""select c.constraint_id, c.target, coalesce(s.v, 0) from allcons c
               left join (select lower(row) r, sum(value) v from theirs group by 1) s on 'pfce.' || s.r = c.constraint_id
               where c.block = 'production' and c.constraint_id like 'pfce.%' and abs(c.target - coalesce(s.v, 0)) > 0.01""")
    assert bad == []
    assert one("select count(*) from allcons where block='production' and constraint_id like 'pfce.%'") == 34
    assert one("select count(*) from tcons where constraint_id like 'pfce.%' or constraint_id like 'hh.c1.c_%'") == 0
    # C4a / C4b / C4d components
    comp = dict(q("select component, sum(value) from theirs where ref <> 'C1a' group by 1"))
    govt = one("select value from sup where series_id='supply.output.sut_p144.sut_i67.current'")
    assert comp["govt_housing"] == pytest.approx(govt, abs=1e-4)
    own = clean_value("mospi_nas_2026/mospi_nas_2026_s8_13.parquet", "s8_13.ownership_of_dwellings.output.current")
    assert abs(comp["actual_rent"] + comp["imputed_rent"] - own) <= 0.5
    fisim = one("select fisim from fisim_par")
    assert comp["fisim_deposits"] + comp["fisim_loans"] == pytest.approx(fisim, abs=1e-4)
    p142 = one("select value from use where series_id='use.pfce.sut_p142.current'")
    assert comp["fisim_deposits"] + comp["fisim_loans"] + comp["explicit_fees"] == pytest.approx(p142, abs=1e-4)


def test_fisim_split_xr5():
    rs, rd, rl, dd, ll, fd, fl, ds, dss = q("select rs, rd, rl, D, L, fd, fl, dshare, dshare_stock from fisim_par")[0]
    assert (rs, rd, rl) == (6.7, 4.8, 9.4)
    comp = dict(q("select component, sum(value) from theirs where ref='C4b' group by 1"))
    assert comp["fisim_deposits"] == pytest.approx(fd, abs=1e-4)
    assert comp["fisim_loans"] == pytest.approx(fl, abs=1e-4)
    params = dict(q(f"select measure, value from {sat('hh_keys')} where key='fisim_params'"))
    assert params["r_star"] == rs and params["r_deposits"] == rd and params["r_loans"] == rl
    assert params["deposits_avg_stock"] == pytest.approx(dd, abs=1e-6)
    assert params["loans_avg_stock"] == pytest.approx(ll, abs=1e-6)
    assert params["deposit_share"] == pytest.approx(ds, abs=1e-12)
    assert params["deposit_share_stock_weights_sensitivity"] == pytest.approx(dss, abs=1e-12)
    assert params["fisim_deposits"] == pytest.approx(fd, abs=1e-6)


# ------------------------------------------------------------------------------------------ 5 constraints
def test_constraints_census():
    rows = {
        r[0]: r[1:]
        for r in q("select constraint_id, target, tol_abs, tol_rel, kind, refs, components, rows, cols from tcons")
    }
    assert set(rows) == {"hh.c1.total", "hh.c4a.govt_housing", "hh.c4a.imputed_rent", "hh.c4b.fisim"}
    hh = ",".join(GROUPS)
    nas11 = clean_value("mospi_nas_2026/mospi_nas_2026_s1_1.parquet", "s1_1.pfce.current")
    t, ta, tr, k, refs, comps, _rws, cols = rows["hh.c1.total"]
    assert (t, ta, tr, k, refs, comps, cols) == (pytest.approx(nas11, abs=1e-6), 1.0, 0.0, "equal", None, None, hh)
    assert len(_rws.split(",")) == 34
    govt = one("select govt from c4a_par")
    assert rows["hh.c4a.govt_housing"][:7] == (govt, 1.0, 0.0, "equal", "C4a", "govt_housing", "C_DWEL")
    imp = one("select sum(v) from exp_c4a where comp='imputed_rent'")
    t, ta, tr, k, refs, comps, rws, _ = rows["hh.c4a.imputed_rent"]
    assert (ta, tr, k, refs, comps, rws) == (0.0, 0.1, "band", "C4a", "imputed_rent", "C_DWEL")
    assert t == pytest.approx(imp, abs=1e-5)
    fisim = one("select fisim from fisim_par")
    t, ta, tr, k, refs, comps, rws, _ = rows["hh.c4b.fisim"]
    assert (ta, tr, k, refs, comps, rws) == (1.0, 0.0, "equal", "C4b", "fisim_deposits,fisim_loans", "C_FINS")
    assert t == pytest.approx(fisim, abs=1e-6)
    # every constraint holds at the prior
    assert one("select sum(value) from theirs") == pytest.approx(nas11, abs=1.0)


def test_constraint_record_status_honest():
    # V-HH-1 (fixed 2026-09-30): the band target is the same modelled quantity as the imputed_rent entries
    st = one(
        "select p.status from tcons c join tprov p on p.prov_id = c.prov_id where constraint_id='hh.c4a.imputed_rent'"
    )
    assert st == "estimated"


# ------------------------------------------------------------------------------------------ 6 provenance
def test_provenance_inputs_resolve_and_status():
    # all inputs of household records resolve to a clean record or to a households/production record
    clean_ids = set()
    for d in CLEAN.iterdir():
        f = d / "_provenance.parquet"
        if f.exists():
            clean_ids |= {r[0] for r in duckdb.sql(f"select prov_id from '{_p(f)}'").fetchall()}
    sam_ids = {r[0] for r in q("select prov_id from tprov")}
    inputs = {i for (s,) in q("select inputs from tprov where inputs is not null") for i in s.split(",")}
    assert inputs - clean_ids - sam_ids == set()
    # entries cite records of the block with the same status
    assert (
        q(
            "select t.prov_id from theirs t left join tprov p using (prov_id) where p.prov_id is null or p.status <> t.status"
        )
        == []
    )
    # every HCES-keyed C1a/C4a/C4d record cites the survey-window assumption record
    sw = one("select prov_id from tprov where method like 'Survey-window assumption%'")
    missing = q(f"""select distinct t.prov_id from theirs t join tprov p using (prov_id)
                    where t.ref in ('C1a','C4a','C4d') and p.inputs not like '%{sw}%'""")
    assert missing == []
    # the C1a/C4d records cite the SUT product prov and the A10F and A2 records they read
    a10 = one("select string_agg(distinct prov_id, ',') from a10 where item_code='value_per_person_30d'")
    a2p = one("select string_agg(distinct prov_id, ',') from a2 where geography='IN' and item_code='persons'")
    assert a10 == "hces_consumption:50e52b2e99e0" and a2p == "hces_consumption:e5e8a3696a31"
    bad = q("""select distinct t.prov_id from theirs t join tprov p using (prov_id) where t.ref in ('C1a','C4d')
               and not (p.inputs like '%hces_consumption:50e52b2e99e0%' and p.inputs like '%hces_consumption:e5e8a3696a31%'
                        and p.inputs like '%io_tables:f6d331e96230%')""")
    assert bad == []


# ------------------------------------------------------------------------------------------ 7 satellites
def test_hh_keys_levels_and_shares():
    k = f"{sat('hh_keys')}"
    # shares = level / sum(level) for every key with levels
    bad = q(f"""select a.key, a.household_group, a.value, b.value / sum(b.value) over (partition by b.key)
                from {k} a join {k} b on a.key=b.key and a.household_group=b.household_group
                where a.measure='share' and b.measure='level'
                qualify abs(a.value - b.value / sum(b.value) over (partition by b.key)) > 1e-11""")
    assert bad == []
    # AIDIS keys recomputed from the overlap mapping
    bad = q(f"""select e.akey, e.grp, e.lvl, s.value from hh_key_exp e join {k} s
                on s.key = e.akey and s.household_group = e.grp and s.measure = 'level'
                where abs(s.value - e.lvl) > 1e-4""")
    assert bad == []
    n = one(
        f"select count(*) from hh_key_exp e join {k} s on s.key=e.akey and s.household_group=e.grp and s.measure='level'"
    )
    assert n == 80
    # proxies equal to aidis_fin_assets (households-7)
    for proxy in ("aidis_equity", "aidis_mf", "aidis_small_savings"):
        assert (
            one(f"""select max(abs(a.value - b.value)) from {k} a join {k} b using (household_group, measure)
                       where a.key='{proxy}' and b.key='aidis_fin_assets'""")
            == 0
        )
    # population and HCES keys
    exp = dict(
        q("""select g.grp || '|' || a.item_code, sum(a.value) from grp g join a2 a on a.cls=g.cls
                    and a.geography='IN' and a.item_code in ('persons','households') group by all""")
    )
    got = dict(q(f"select household_group || '|' || replace(replace(key,'pop_',''),'persons','persons'), value "
                 f"from {k} where key in ('pop_persons','pop_households') and measure='level'"))  # fmt: skip
    assert {kk: v for kk, v in got.items()} == pytest.approx(exp, abs=1e-6)
    ht = dict(
        q("""select g.grp, sum(p.value * m.value * 12 / 1e7) from grp g
                   join a2 p on p.cls=g.cls and p.geography='IN' and p.item_code='persons'
                   join a2 m on m.cls=g.cls and m.geography='IN' and m.item_code='avg_mpce' group by 1""")
    )
    got = dict(q(f"select household_group, value from {k} where key='hces_total' and measure='level'"))
    assert got == pytest.approx(ht, abs=1e-5)
    for key, item in (("hces_food", "981"), ("hces_nonfood", "984"), ("hces_durables", "983")):
        exp = dict(q(f"select grp, val from V where item = '{item}'"))
        got = dict(q(f"select household_group, value from {k} where key='{key}' and measure='level'"))
        assert got == pytest.approx(exp, abs=1e-5), key
    # c4a_*, c4b_*, pfce_total equal the block's own entries by group
    for comp in ("actual_rent", "imputed_rent", "govt_housing", "fisim_deposits", "fisim_loans", "explicit_fees",
                 "insurance_service"):  # fmt: skip
        key = ("c4a_" if comp in ("actual_rent", "imputed_rent", "govt_housing") else "c4b_") + comp
        exp = dict(q(f"select col, sum(value) from theirs where component = '{comp}' group by 1"))
        got = dict(q(f"select household_group, value from {k} where key='{key}' and measure='level'"))
        assert got == pytest.approx(exp, abs=1e-5), key
    exp = dict(q("select col, sum(value) from theirs group by 1"))
    got = dict(q(f"select household_group, value from {k} where key='pfce_total' and measure='level'"))
    assert got == pytest.approx(exp, abs=1e-5)


def test_hh_group_map_and_hces_items():
    rows = q(f"select hces_class, household_group, measure, value from {sat('hh_group_map')}")
    assert len(rows) == 72
    exp = {
        (c, i): v
        for c, i, v in q("select cls, item_code, value from a2 where geography='IN' and cls in (select cls from grp)")
    }
    gmap = dict(q("select cls, grp from grp"))
    for cls, g, m, v in rows:
        assert gmap[cls] == g
        assert v == pytest.approx(exp[(cls, m)], abs=1e-6)
    bad = q(f"""select s.hces_item, s.household_group, s.value, V.val from {sat("hh_hces_items")} s
                left join V on V.item = s.hces_item and V.grp = s.household_group
                where V.val is null or abs(V.val - s.value) > 1e-6 + 1e-11 * abs(V.val)""")
    assert bad == []


def test_s8_food_stik():
    s = sat("s8_food_stik")
    for item, code, p in (("rice_free", "061", "p001"), ("wheat_free", "062", "p002")):
        gf = one(f"select value from use where series_id='use.gfce.sut_{p}.current'")
        qty = dict(q(f"select grp, tonnes from Q where item='{code}'"))
        tq = sum(qty.values())
        got_q = dict(q(f"select household_group, value from {s} where item='{item}' and measure='qty'"))
        got_v = dict(q(f"select household_group, value from {s} where item='{item}' and measure='value'"))
        assert got_q == pytest.approx(qty, rel=1e-9)
        assert got_v == pytest.approx({g: gf * v / tq for g, v in qty.items()}, abs=1e-5)
        uv = one(f"select value from {s} where item='{item}' and measure='unit_value_inr_per_kg'")
        assert uv == pytest.approx(gf * 1e7 / (tq * 1000), rel=1e-9)
    tot = dict(q(f"select household_group, value from {s} where item='total' and measure='value'"))
    assert sum(tot.values()) == pytest.approx(
        one("select sum(value) from use where series_id in ('use.gfce.sut_p001.current','use.gfce.sut_p002.current')"),
        abs=1e-4,
    )
    # S8 per person falls from Q1 to Q5 within each area
    pp = dict(q("select g.grp, sum(a.value) from grp g join a2 a on a.cls=g.cls and a.geography='IN' "
                "and a.item_code='persons' group by 1"))  # fmt: skip
    for a in "RU":
        per = [tot[f"H_{a}{i}"] / pp[f"H_{a}{i}"] for i in range(1, 6)]
        assert per == sorted(per, reverse=True)


def test_s8_memo_rows_at_a10sw_unit_values():
    """memo_070..075: A10F free quantities valued at A10SW all-India R/U imputed unit values (value / qty);
    hces_valued: A10SW value per person x area persons x 12 / 1e7 (the check against SUT GFCE)."""
    sw = CLEAN / "hces_consumption" / "hces_consumption_a10sw_state_item_imputed.parquet"
    a10sw = {
        (it, hg, ic): v
        for it, hg, ic, v in q(
            f"select substr(product, 6), household_group, item_code, value from '{_p(sw)}' "
            f"where period = '{SW}' and geography = 'IN'"
        )  # fmt: skip
    }
    s = sat("s8_food_stik")
    got = {(i, g): v for i, g, v in q(f"select hces_item, household_group, value from {s} "
                                       f"where series_id like 'memo_%' and measure = 'value'")}  # fmt: skip
    n = 0
    for (item, g), v in got.items():
        area = "rural" if g.startswith("H_R") else "urban"
        uv = a10sw[(item, f"{area}_all", "value_per_person_30d")] / a10sw[(item, f"{area}_all", "qty_per_person_30d")]
        qty = one(f"select tonnes from Q where item = '{item}' and grp = '{g}'")
        assert v == pytest.approx(qty * uv / 1e7, rel=1e-9, abs=1e-6), (item, g)
        n += 1
    assert n == 50  # 070, 071, 073, 074, 075 x 10 groups; 072 (qty rounds to 0 t) not valued
    assert {i for i, _ in got} == {"070", "071", "073", "074", "075"}
    ap = dict(q("select g.area, sum(a.value) from grp g join a2 a on a.cls=g.cls and a.geography='IN' "
                "and a.item_code='persons' group by 1"))  # fmt: skip
    for item, code in (("rice_free", "061"), ("wheat_free", "062")):
        exp = sum(a10sw[(code, f"{a}_all", "value_per_person_30d")] * ap[a] * 12 / 1e7 for a in ("rural", "urban"))
        assert one(f"select value from {s} where item='{item}' and measure='hces_valued'") == pytest.approx(
            exp, rel=1e-9
        )


def test_aidis_overlap_and_state_xwalk_levels():
    ov = {
        (k, g, m): v
        for k, g, m, v in q(f"select aidis_class, household_group, measure, value from {sat('hh_aidis_overlap')}")
    }
    exp = {(f"{a}_q{k}", g): h for a, g, k, h in q("select area, grp, k, ov_hh from overlap where ov_hh > 1e-9")}
    assert {(k, g) for k, g, m in ov if m == "households"} == set(exp)
    for (k, g), h in exp.items():
        assert ov[(k, g, "households")] == pytest.approx(h, rel=1e-9)
    # State x area rows 'all' sum their classes; consumption = persons x class MPCE x 12 / 1e7
    s = sat("hh_state_xwalk")
    bad = q(f"""with c as (select geography, area, household_group, measure, sum(value) v from {s}
                           where hces_class <> 'all' and measure in ('persons','consumption') group by all)
                select a.geography, a.area, a.household_group, a.measure, a.value, c.v from {s} a join c
                  using (geography, area, household_group, measure)
                where a.hces_class = 'all' and abs(a.value - c.v) > 1e-6 * greatest(1, abs(c.v))""")
    assert bad == []
    bad = q(f"""select p.geography, p.area, p.hces_class, p.household_group, c.value, p.value * m.value * 12 / 1e7
                from {s} p join {s} c using (geography, area, hces_class, household_group)
                join a2 m on m.geography = p.geography and m.cls = p.area || '_' || p.hces_class and m.item_code='avg_mpce'
                where p.measure='persons' and c.measure='consumption' and p.hces_class <> 'all'
                  and abs(c.value - p.value * m.value * 12 / 1e7) > 1e-6""")
    assert bad == []


def test_c4c_npish_memo():
    icio = CLEAN / "io_tables" / "io_tables_icio_india.parquet"
    npish, hfce = q(f"""select sum(value) filter (where series_id like '%.npish.current'),
                               sum(value) filter (where series_id like '%.hfce.current')
                        from '{_p(icio)}' where period='2022-23'
                          and (regexp_matches(series_id, '^icio\\.(dom|imp)\\..*\\.(npish|hfce)\\.current$')
                               or series_id in ('icio.tls.npish.current','icio.tls.hfce.current'))""")[0]
    got = dict(q(f"select series_id, value from {sat('c4c_npish_memo')}"))
    assert got["npish_fce"] == pytest.approx(npish, rel=1e-9)
    assert got["hfce"] == pytest.approx(hfce, rel=1e-9)
    assert got["npish_share"] == pytest.approx(npish / (npish + hfce), rel=1e-9)


def test_c4a_imputed_rent_sensitivity():
    s = sat("c4a_imputed_rent_sensitivity")
    imp = dict(q("select c, v from exp_c4a where comp='imputed_rent'"))
    area_w = {}
    for area in ("rural", "urban"):
        b = one(f"select value from pn where series_id='pn.asset_share_building.{area}.all'") / 100
        ava = one(f"select value from pn where series_id='pn.ava_per_hh.{area}.all.current'")
        hh = one(f"select sum(hh) from ghh where area='{area}'")
        area_w[area] = b * ava * hh
    rs = area_w["rural"] / (area_w["rural"] + area_w["urban"])
    assert one(f"select value from {s} where series_id='rural_urban_share_aidis_building.rural'") == pytest.approx(
        rs, rel=1e-9
    )
    total = sum(imp.values())
    exp = {}
    for area, share in (("R", rs), ("U", 1 - rs)):
        sub = {g: v for g, v in imp.items() if g[2] == area}
        for g, v in sub.items():
            exp[g] = total * share * v / sum(sub.values())
    got = dict(q(f"select household_group, value from {s} where measure='aidis_building_variant'"))
    assert got == pytest.approx(exp, abs=1e-4)
    diff = dict(q(f"select household_group, value from {s} where measure='diff'"))
    assert diff == pytest.approx({g: exp[g] - imp[g] for g in exp}, abs=1e-4)
    moved = sum(v for g, v in diff.items() if g.startswith("H_R"))
    assert moved == pytest.approx(210_681, abs=1)


def test_c1a_hces_nas_ratio_products():
    s = sat("c1a_hces_nas_ratio")
    # items keying several products split in proportion to those products' SUT PFCE
    got = dict(q(f"select code, value from {s} where level='product' and measure='ratio'"))
    exp = dict(
        q("""with ik as (select distinct cast(sut_product as integer) p, hces_item from conc where ref in ('C1a','C4d')),
                    w as (select ik.p, ik.hces_item, f.value / sum(f.value) over (partition by ik.hces_item) w, f.value pf
                          from ik join pfce f on f.p = ik.p),
                    hv as (select item, sum(val) v from V group by 1)
                    select 'sut_p' || lpad(cast(w.p as varchar),3,'0'), sum(w.w * hv.v) / any_value(w.pf)
                    from w join hv on hv.item = w.hces_item group by w.p""")
    )
    assert set(got) >= set(exp)
    assert {k: got[k] for k in exp} == pytest.approx(exp, rel=1e-9)


# ------------------------------------------------------------------------------------------ 8 placement models
def _spread(lm: list[float]) -> list[tuple[float, float]]:
    n = len(lm)
    lo = [0.0] * n
    hi = [0.0] * n
    for j in range(n):
        if j > 0:
            lo[j] = (lm[j - 1] + lm[j]) / 2
        if j < n - 1:
            hi[j] = (lm[j] + lm[j + 1]) / 2
    lo[0] = 2 * lm[0] - hi[0]
    hi[n - 1] = 2 * lm[n - 1] - lo[n - 1]
    return list(zip(lo, hi, strict=True))


def _frac(lo: float, hi: float, a: float, b: float) -> float:
    return max(0.0, min(hi, b) - max(lo, a)) / (hi - lo)


def _classes(geo: str, area: str) -> list[tuple[str, float, float]]:
    rows = dict(q(f"select cls || '|' || item_code, value from a2 where geography='{geo}' and cls like '{area}_p%'"))
    out = []
    for cls in CLASSES:
        p, m = rows.get(f"{area}_{cls}|persons"), rows.get(f"{area}_{cls}|avg_mpce")
        if p and m:
            out.append((cls, p, m))
    return out


@cache
def national_xwalk() -> tuple[list[float], dict[tuple[str, int], float]]:
    cls_all = []
    for area, a in (("rural", "R"), ("urban", "U")):
        cl = _classes("IN", area)
        iv = _spread([math.log(m) for _, _, m in cl])
        for (cls, p, _), (lo, hi) in zip(cl, iv, strict=True):
            cls_all.append((f"H_{a}{CLASS_Q[CLASSES.index(cls)]}", p, lo, hi))
    total = sum(p for _, p, _, _ in cls_all)

    def cdf(x: float) -> float:
        return sum(p * _frac(lo, hi, -1e9, x) for _, p, lo, hi in cls_all)

    cuts = []
    for qq in (0.2, 0.4, 0.6, 0.8):
        a, b = min(lo for *_, lo, _ in cls_all), max(hi for *_, hi in cls_all)
        for _ in range(200):
            mid = (a + b) / 2
            a, b = (mid, b) if cdf(mid) < qq * total else (a, mid)
        cuts.append((a + b) / 2)
    edges = [-1e9, *cuts, 1e9]
    out: dict[tuple[str, int], float] = {}
    for g, p, lo, hi in cls_all:
        for k in range(5):
            out[(g, k + 1)] = out.get((g, k + 1), 0.0) + p * _frac(lo, hi, edges[k], edges[k + 1])
    return [math.exp(x) for x in cuts], out


def test_national_quintile_xwalk():
    cuts, exp = national_xwalk()
    got = {(g, int(qq[1])): v for g, qq, v in q(f"select household_group, national_quintile, value "
                                                   f"from {sat('hh_national_quintile_xwalk')} where measure='persons'")}  # fmt: skip
    assert got == pytest.approx(exp, rel=1e-6, abs=1.0)
    sh = q(
        f"select household_group, sum(value) from {sat('hh_national_quintile_xwalk')} where measure='share' group by 1"
    )
    assert all(abs(v - 1) < 1e-9 for _, v in sh)
    assert [round(c) for c in cuts] == [2846, 3696, 4734, 6413]


def test_state_xwalk_model():
    s = sat("hh_state_xwalk")
    cut = {}
    for area in ("rural", "urban"):
        m = {cls: mm for cls, _, mm in _classes("IN", area)}
        cut[area] = [-1e9] + [(math.log(m[x]) + math.log(m[y])) / 2 for x, y in
                              (("p10_20", "p20_30"), ("p30_40", "p40_50"), ("p50_60", "p60_70"), ("p70_80", "p80_90"))] + [1e9]  # fmt: skip
    got = {(g, a, c, grp): v for g, a, c, grp, v in
           q(f"select geography, area, hces_class, household_group, value from {s} where measure='persons' and hces_class <> 'all'")}  # fmt: skip
    geos = [r[0] for r in q("select distinct geography from a2 where geography like 'IN-%' order by 1")]
    n = 0
    for geo in geos:
        for area, a in (("rural", "R"), ("urban", "U")):
            cl = _classes(geo, area)
            if not cl:
                continue
            iv = _spread([math.log(mm) for _, _, mm in cl]) if len(cl) > 1 else None
            for j, (cls, p, _) in enumerate(cl):
                for k in range(5):
                    w = _frac(*iv[j], cut[area][k], cut[area][k + 1]) if iv else None
                    if w is None:
                        continue
                    v = got.get((geo, area, cls, f"H_{a}{k + 1}"), 0.0)
                    assert v == pytest.approx(w * p, rel=1e-6, abs=1e-3), (geo, area, cls, k)
                    n += 1
    assert n > 3000


def test_plausibility_bands():
    by = dict(q("select col, sum(value) from theirs group by 1"))
    tot = sum(by.values())
    rural = sum(v for g, v in by.items() if g.startswith("H_R")) / tot
    assert 0.45 <= rural <= 0.62 and rural == pytest.approx(0.5177, abs=5e-4)
    assert (by["H_R5"] + by["H_U5"]) / tot == pytest.approx(0.3984, abs=5e-4)
    food = dict(q("select col, sum(value) from theirs where row in ('C_CROP','C_FOOD','C_LVST','C_FOFI') group by 1"))
    for a in "RU":
        sh = [food[f"H_{a}{i}"] / by[f"H_{a}{i}"] for i in range(1, 6)]
        assert sh == sorted(sh, reverse=True), (a, sh)
