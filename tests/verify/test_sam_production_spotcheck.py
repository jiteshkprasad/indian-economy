"""Independent verification of the SAM `production` block (Phase 2 verifier, 2026-09-30; SPEC s.3 rule 3).

This file does NOT import pipeline.sam (no block, framework or spec code) and does not use polars.
Every expected number is recomputed here with DuckDB SQL from:
- data/clean/io_tables/io_tables_sut_{supply,use,va}.parquet (SUT 2023-24, 155 products x 67 industries),
- data/concordance/io_tables_sut_{product,industry}_to_sam34.csv (the committed concordances),
- data/clean/mospi_nas_2026/mospi_nas_2026_s1_1 / _s7_1.parquet and io_tables_sut_note_totals (controls),
- pipeline/sam/accounts.yaml read as plain YAML (account groups only).
It is then compared, entry by entry and constraint by constraint (a census, not a sample), with the
block's written outputs in data/sam/2023-24/blocks/production_*.parquet.

Recomputation rules (from docs/phase0/GAP_MAP.md and data/gap_map.csv, not from the builder's code):
- only real SUT cells: product codes `sut_pNNN`, industry codes `sut_iNN` (memo rows 'cif',
  'purchases_*' and the 'total' row/column are excluded); a product/industry is mapped by the concordance;
- P1 ACT<-COM output; P2 COM<-ACT ic; P3 COM<-M_TTM = -(negative TTM cells); P4 M_TTM<-COM = positive
  TTM cells; P5 COM<-R_ROW exports; P6 R_ROW<-COM imports after CIF; P8 T_CUST<-COM import duty; P9
  T_PSUB<-COM product subsidies (negative); P10 T_PROD<-ACT net production taxes; I3 COM<-K_DSTK cii;
  D4 C_*<-X_DISC = 0 (NAS 1.1 discrepancy is 0 in 2023-24). Aggregates that sum to exactly 0 are absent.
- anchored allowance: Rs 1 crore per SUT cell aggregated (FRAMEWORK_REQUESTS deviation 1).
- constraints: P7 (7 product-tax accounts x commodity), C1 (commodity x HH), C2 (x GOV), I1 (x CAP, refs
  I1/I1a), I2 (x CAP, refs I2/I2a), V1 (F_LREG+F_LCAS x activity), V2 (F_MIXD+F_GOSC x activity, OS/MI +
  CFC), one per commodity/activity, target 0 where the SUT has no cell, tol_abs = number of cells.

Two defects were recorded here as strict xfails
(docs/phase2/verify/framework_production_block_verification_spec_rule_.md): V-1 (the anchored tol_rel was
rounded to 6 decimals on write) and V-5 (the I2 constraint record named NAS as its source). Both were fixed
in the Wave A review (docs/phase2/FRAMEWORK_REQUESTS.md) and the markers removed, as instructed here; the
regression pin of the old rounding became a pin of the fix (tol_rel written to 12 significant digits).
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import duckdb
import pytest
import yaml

pytestmark = [pytest.mark.quality, pytest.mark.sam]

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean"
BLOCKS = ROOT / "data" / "sam" / "2023-24" / "blocks"
CONC = ROOT / "data" / "concordance"
YEAR = "2023-24"
TOL = 0.01  # Rs crore: census tolerance (task contract)
NAS_TOL = 5.0  # Rs crore: SUT rounding vs NAS (RECONCILIATION.md: <= 3 crore)
PRODUCT_TAX_ACCOUNTS = "T_CGST,T_SGST,T_GCES,T_UEXC,T_SVAT,T_SEXC,T_OPRT"


def _p(path: Path) -> str:
    return path.as_posix()


@cache
def con() -> duckdb.DuckDBPyConnection:
    for f in ("production_entries", "production_constraints", "production_provenance", "production_checks"):
        if not (BLOCKS / f"{f}.parquet").exists():
            pytest.fail(f"{f}.parquet missing: run `uv run python -m pipeline sam production`")
    c = duckdb.connect()
    io = CLEAN / "io_tables"
    c.execute(f"""
        create table pmap as select 'sut_p' || lpad(sut_product, 3, '0') product, commodity, nas_group
          from read_csv('{_p(CONC / "io_tables_sut_product_to_sam34.csv")}', all_varchar=true);
        create table imap as select 'sut_i' || lpad(sut_industry, 2, '0') industry, activity, nas_group
          from read_csv('{_p(CONC / "io_tables_sut_industry_to_sam34.csv")}', all_varchar=true);
        create table sut as
          select 'S' tbl, item_code, product, industry, value, vintage, prov_id, dim_other
            from '{_p(io / "io_tables_sut_supply.parquet")}' where period = '{YEAR}'
          union all select 'U', item_code, product, industry, value, vintage, prov_id, dim_other
            from '{_p(io / "io_tables_sut_use.parquet")}' where period = '{YEAR}'
          union all select 'V', item_code, product, industry, value, vintage, prov_id, dim_other
            from '{_p(io / "io_tables_sut_va.parquet")}' where period = '{YEAR}';
        -- real cells only: product rows sut_pNNN (or none, VA block), industry columns sut_iNN (or none)
        create table cells as
          select s.*, p.commodity, i.activity from sut s
          left join pmap p using (product) left join imap i using (industry)
          where (s.product like 'sut_p%' or s.product is null) and (s.industry like 'sut_i%' or s.industry is null);
        create table theirs as select * from '{_p(BLOCKS / "production_entries.parquet")}';
        create table tcons as select * from '{_p(BLOCKS / "production_constraints.parquet")}';
        create table tprov as select * from '{_p(BLOCKS / "production_provenance.parquet")}';
        create table tchecks as select * from '{_p(BLOCKS / "production_checks.parquet")}';
    """)
    # expected entries: (row, col, ref, value, n_cells, role, source table, item)
    specs = [
        ("P1", "activity", "commodity", "S", "output", "", "anchored"),
        ("P2", "commodity", "activity", "U", "ic", "", "anchored"),
        ("P3", "commodity", "'M_TTM'", "S", "ttm", "and value < 0", "anchored"),
        ("P4", "'M_TTM'", "commodity", "S", "ttm", "and value > 0", "anchored"),
        ("P5", "commodity", "'R_ROW'", "U", "exports", "", "anchored"),
        ("P6", "'R_ROW'", "commodity", "S", "imports_after_cif", "", "anchored"),
        ("P8", "'T_CUST'", "commodity", "S", "import_duty", "", "fixed"),
        ("P9", "'T_PSUB'", "commodity", "S", "product_subsidies", "", "fixed"),
        ("P10", "'T_PROD'", "activity", "V", "net_production_taxes", "", "fixed"),
        ("I3", "commodity", "'K_DSTK'", "U", "cii", "", "anchored"),
    ]
    parts = []
    for ref, r, col, tbl, item, extra, role in specs:
        keys = [k for k in (r, col) if not k.startswith("'")]
        notnull = " and ".join(f"{k} is not null" for k in keys)
        sign = "-" if ref == "P3" else ""
        parts.append(
            f"select {r} r, {col} c, '{ref}' rf, {sign}sum(value) v, count(*) n, '{role}' rl, "
            f"string_agg(distinct prov_id, ',' order by prov_id) pids "
            f"from cells where tbl = '{tbl}' and item_code = '{item}' {extra} and {notnull} group by all"
        )
    c.execute("create table mine_all as " + " union all ".join(parts))
    c.execute("""create table mine as
        select * from mine_all where v <> 0
        union all select distinct commodity, 'X_DISC', 'D4', 0.0, 0, 'fixed', null from pmap""")
    return c


def q(sql: str) -> list[tuple]:
    return con().execute(sql).fetchall()


def one(sql: str):
    rows = q(sql)
    assert len(rows) == 1, (sql, rows)
    return rows[0][0]


@cache
def groups() -> dict[str, list[str]]:
    acc = yaml.safe_load((ROOT / "pipeline" / "sam" / "accounts.yaml").read_text(encoding="utf-8"))["accounts"]
    out: dict[str, list[str]] = {}
    for a in acc:
        out.setdefault(a["group"], []).append(a["code"])
    return out


def nas(dataset: str, series_id: str) -> float:
    return one(
        f"select value from '{_p(CLEAN / 'mospi_nas_2026' / (dataset + '.parquet'))}' "
        f"where period = '{YEAR}' and series_id = '{series_id}'"
    )


# ------------------------------------------------------------------------------------------ 1 inputs
def test_single_vintage_and_complete_concordances():
    assert q("select distinct vintage from sut") == [("2026-08-31",)]
    assert one("select count(*) from pmap") == 155 and one("select count(distinct product) from pmap") == 155
    assert one("select count(*) from imap") == 67 and one("select count(distinct industry) from imap") == 67
    unmapped = q(
        "select product, industry from cells where (product like 'sut_p%' and commodity is null) "
        "or (industry like 'sut_i%' and activity is null)"
    )
    assert unmapped == []
    assert {r[0] for r in q("select distinct commodity from pmap")} == set(groups()["COM"])
    assert {r[0] for r in q("select distinct activity from imap")} == set(groups()["ACT"])


def test_crude_gas_label_swap_is_harmless():
    """io_tables Q1: in 2023-24 SUT rows 43 (labelled natural gas) and 44 (crude) hold each other's data.
    The clean data flag the pair; both products (and industries 6/7) map to one SAM sector."""
    assert q("select commodity from pmap where product in ('sut_p043','sut_p044') group by 1") == [("C_OILG",)]
    assert q("select activity from imap where industry in ('sut_i06','sut_i07') group by 1") == [("A_OILG",)]
    flags = q("select distinct product, dim_other from sut where product in ('sut_p043','sut_p044') order by 1")
    assert [p for p, _ in flags] == ["sut_p043", "sut_p044"]
    assert all("label_swap_period=2023-24" in (d or "") for _, d in flags)
    # the evidence of the swap: row 43 carries the crude-petroleum industry's output in 2023-24
    assert one("select industry from sut where item_code='output' and product='sut_p043' "
               "and industry in ('sut_i06','sut_i07')") == "sut_i06"  # fmt: skip


# ------------------------------------------------------------------------------------------ 2 entries
def test_entry_census_every_value():
    rows = q(f"""
        select coalesce(m.rf, t.ref), coalesce(m.r, t.row), coalesce(m.c, t.col), m.v, t.value
        from mine m full outer join theirs t on m.r = t.row and m.c = t.col and m.rf = t.ref
        where m.v is null or t.value is null or abs(m.v - t.value) > {TOL}
    """)
    assert rows == [], rows[:20]
    assert one("select count(*) from theirs") == one("select count(*) from mine") == 1064
    per_ref = dict(q("select ref, count(*) from theirs group by 1"))
    assert per_ref == {"P1": 145, "P2": 715, "P3": 2, "P4": 19, "P5": 31, "P6": 30, "P8": 19, "P9": 16,
                       "P10": 33, "I3": 20, "D4": 34}  # fmt: skip
    assert q("select row, col, ref, component from theirs group by all having count(*) > 1") == []


def test_entry_roles_status_and_metadata():
    bad = q("""select t.ref, t.row, t.col, t.role, m.rl from theirs t
               join mine m on m.r=t.row and m.c=t.col and m.rf=t.ref where t.role <> m.rl""")
    assert bad == []
    assert q("select distinct status from theirs") == [("official",)]
    assert q("select distinct component from theirs") == [("total",)]
    assert one("select count(*) from theirs where confidence is not null or bop_function is not null") == 0
    assert one("select count(*) from theirs where role = 'fixed' and tol_rel is not null") == 0
    assert one("select count(*) from theirs where role = 'anchored' and tol_rel is null") == 0
    assert one("select count(*) from theirs where value = 0 and ref <> 'D4'") == 0
    # the only aggregate that sums to exactly zero: P10 for public administration (SUT prints 0)
    assert q("select r, c, rf from mine_all where v = 0") == [("T_PROD", "A_PADM", "P10")]


def test_anchored_tol_as_written_is_the_allowance_to_12_significant_digits():
    """Pin of the V-1 fix: tol_rel = n_cells / |value| to 12 significant digits (relative error <= 1e-11)."""
    bad = q("""select t.ref, t.row, t.col, t.tol_rel, m.n / abs(m.v) from theirs t
               join mine m on m.r=t.row and m.c=t.col and m.rf=t.ref
               where t.role = 'anchored' and abs(t.tol_rel / (m.n / abs(m.v)) - 1) > 1e-11""")
    assert bad == []


def test_anchored_allowance_is_one_crore_per_cell_as_balanced():
    bad = q("""select t.ref, t.row, t.col, t.value, m.n, t.tol_rel from theirs t
               join mine m on m.r=t.row and m.c=t.col and m.rf=t.ref
               where t.role = 'anchored' and (t.tol_rel <= 0 or abs(t.tol_rel * abs(t.value) - m.n) > 0.01)""")
    assert bad == [], f"{len(bad)} anchored entries whose written allowance is not n_cells crore: {bad[:5]}"


def test_signs_and_structure():
    assert one("select count(*) from theirs where ref = 'P9' and value >= 0") == 0  # subsidies negative
    for ref in ("P3", "P4", "P5", "P6", "P8"):
        assert one(f"select count(*) from theirs where ref = '{ref}' and value <= 0") == 0, ref
    assert {r[0] for r in q("select row from theirs where ref = 'P3'")} == {"C_TRAD", "C_TRNS"}
    assert q("select distinct col, role from theirs where ref = 'D4'") == [("X_DISC", "fixed")]
    assert one("select count(distinct row) from theirs where ref = 'D4'") == 34
    # no commodity both supplies margin services and pays margins
    assert q("select a.row from theirs a join theirs b on a.row = b.col where a.ref='P3' and b.ref='P4'") == []


def test_margins_and_cif():
    ttm_neg = one(
        "select sum(value) from cells where tbl='S' and item_code='ttm' and value < 0 and commodity is not null"
    )
    ttm_pos = one(
        "select sum(value) from cells where tbl='S' and item_code='ttm' and value > 0 and commodity is not null"
    )
    assert one("select sum(value) from theirs where ref='P3'") == pytest.approx(-ttm_neg, abs=TOL)
    assert one("select sum(value) from theirs where ref='P4'") == pytest.approx(ttm_pos, abs=TOL)
    assert abs(ttm_pos + ttm_neg) < 1.0  # the TTM column nets to ~0 (+0.33 crore: SUT rounding)
    # imports after CIF = imports + CIF adjustment, product by product; the adjustment sits on air and
    # water transport and insurance only, and offsets the 'cif' memo row
    gap = one("""select max(abs(coalesce(i,0) + coalesce(a,0) - coalesce(f,0))) from (
        select product, sum(value) filter (where item_code='imports') i,
               sum(value) filter (where item_code='cif_adj') a,
               sum(value) filter (where item_code='imports_after_cif') f
        from cells where tbl='S' and product like 'sut_p%' group by 1)""")
    assert gap < 1e-6
    adj = q("select product from cells where tbl='S' and item_code='cif_adj' and value <> 0 order by 1")
    assert [r[0] for r in adj] == ["sut_p137", "sut_p138", "sut_p143"]
    memo = one("select value from sut where tbl='S' and item_code='cif_adj' and product='cif'")
    assert one(
        "select sum(value) from cells where tbl='S' and item_code='cif_adj' and product like 'sut_p%'"
    ) == pytest.approx(-memo, abs=1e-6)
    assert q("select * from theirs where ref='P6' and col='C_INSR'") == []  # insurance imports = CIF adjustment
    # memo rows (CIF, purchases abroad / of non-residents) are in no entry: totals equal the SUT 'total' rows
    for ref, tbl, item in (("P6", "S", "imports_after_cif"), ("P5", "U", "exports")):
        total = one(f"select value from sut where tbl='{tbl}' and item_code='{item}' and product='total'")
        assert one(f"select sum(value) from theirs where ref='{ref}'") == pytest.approx(total, abs=TOL)


# ------------------------------------------------------------------------------------------ 3 constraints
def _expected_constraints() -> list[tuple]:
    g = groups()
    spec = [  # ref, table, items, key, stem, rows, cols, refs
        ("P7", "S", "'product_taxes'", "commodity", "product_taxes", PRODUCT_TAX_ACCOUNTS, "{k}", None),
        ("C1", "U", "'pfce'", "commodity", "pfce", "{k}", ",".join(g["HH"]), None),
        ("C2", "U", "'gfce'", "commodity", "gfce", "{k}", ",".join(g["GOV"]), None),
        ("I1", "U", "'gfcf'", "commodity", "gfcf", "{k}", ",".join(g["CAP"]), "I1,I1a"),
        ("I2", "U", "'valuables'", "commodity", "valuables", "{k}", ",".join(g["CAP"]), "I2,I2a"),
        ("V1", "V", "'ce'", "activity", "ce", "F_LREG,F_LCAS", "{k}", None),
        ("V2", "V", "'os_mi','cfc'", "activity", "os_mi_cfc", "F_MIXD,F_GOSC", "{k}", None),
    ]
    out = []
    for ref, tbl, items, key, stem, rows, cols, refs in spec:
        got = {k: (v, n) for k, v, n in q(
            f"select {key}, sum(value), count(*) from cells where tbl='{tbl}' and item_code in ({items}) "
            f"and {key} is not null group by 1")}  # fmt: skip
        for k in groups()["COM" if key == "commodity" else "ACT"]:
            v, n = got.get(k, (0.0, 0))
            out.append((f"{stem}.{k.lower()}", ref, rows.replace("{k}", k), cols.replace("{k}", k), refs, v, float(n)))
    return out


def _acct_order(codes: str) -> str:
    full = yaml.safe_load((ROOT / "pipeline" / "sam" / "accounts.yaml").read_text(encoding="utf-8"))["accounts"]
    order = {a["code"]: i for i, a in enumerate(full)}
    return ",".join(sorted(set(codes.split(",")), key=order.__getitem__))


def test_constraint_census():
    exp = {r[0]: r for r in _expected_constraints()}
    got = {r[0]: r for r in q("select constraint_id, ref, rows, cols, refs, target, tol_abs, tol_rel, kind, components "
                              "from tcons")}  # fmt: skip
    assert set(exp) == set(got) and len(got) == 238
    bad = []
    for cid, (_, ref, rows, cols, refs, target, n) in exp.items():
        _, gref, grows, gcols, grefs, gtarget, gtol, gtolrel, kind, comps = got[cid]
        # stored account lists are comma-joined in accounts.yaml order
        if (gref, grows, gcols, grefs) != (ref, _acct_order(rows), _acct_order(cols), refs):
            bad.append((cid, "selection", grows, gcols, grefs))
        if abs(gtarget - target) > TOL or gtol != n or gtolrel != 0 or kind != "equal" or comps is not None:
            bad.append((cid, gtarget, target, gtol, n, gtolrel, kind, comps))
    assert bad == [], bad[:10]


# ------------------------------------------------------------------------------------------ 4 NAS totals
@cache
def totals() -> dict[str, float]:
    t = {ref: one(f"select coalesce(sum(value), 0) from theirs where ref = '{ref}'") for ref in
         ("P1", "P2", "P5", "P6", "P8", "P9", "P10", "I3")}  # fmt: skip
    for ref in ("P7", "C1", "C2", "I1", "I2", "V1", "V2"):
        t["t" + ref] = one(f"select sum(target) from tcons where ref = '{ref}'")
    t["os_mi"] = one("select sum(value) from cells where tbl='V' and item_code='os_mi' and activity is not null")
    t["cfc"] = one("select sum(value) from cells where tbl='V' and item_code='cfc' and activity is not null")
    return t


def _nas_cases():
    def gva(t):
        return t["P1"] - t["P2"]

    def npt(t):  # net product taxes
        return t["tP7"] + t["P8"] + t["P9"]

    s11, s71 = "mospi_nas_2026_s1_1", "mospi_nas_2026_s7_1"
    return [
        ("gdp_production", lambda t: gva(t) + npt(t), s11, "s1_1.gdp.current"),
        ("gdp_expenditure", lambda t: t["tC1"] + t["tC2"] + t["tI1"] + t["I3"] + t["tI2"] + t["P5"] - t["P6"], s11,
         "s1_1.gdp_expenditure.current"),
        ("gdp_income", lambda t: t["tV1"] + t["tV2"] + t["P10"] + npt(t), s11, "s1_1.gdp.current"),
        ("gva", gva, s11, "s1_1.gva_basic.current"),
        ("pfce", lambda t: t["tC1"], s11, "s1_1.pfce.current"),
        ("gfce", lambda t: t["tC2"], s11, "s1_1.gfce.current"),
        ("gfcf", lambda t: t["tI1"], s11, "s1_1.gfcf.current"),
        ("cis", lambda t: t["I3"], s11, "s1_1.cis.current"),
        ("valuables", lambda t: t["tI2"], s11, "s1_1.valuables.current"),
        ("exports", lambda t: t["P5"], s11, "s1_1.exports.current"),
        ("imports", lambda t: t["P6"], s11, "s1_1.imports.current"),
        ("product_taxes", lambda t: t["tP7"] + t["P8"], s11, "s1_1.taxes_on_products.current"),
        ("product_subsidies", lambda t: -t["P9"], s11, "s1_1.subsidies_on_products.current"),
        ("cfc_nas11", lambda t: t["cfc"], s11, "s1_1.cfc.current"),
        ("output", lambda t: t["P1"], s71, "s7_1.total.output.current"),
        ("ic", lambda t: t["P2"], s71, "s7_1.total.ic.current"),
        ("ce", lambda t: t["tV1"], s71, "s7_1.total.ce.current"),
        ("os_mi", lambda t: t["os_mi"], s71, "s7_1.total.os_mi.current"),
        ("cfc_nas71", lambda t: t["cfc"], s71, "s7_1.total.cfc.current"),
        ("os_mi_cfc", lambda t: t["tV2"] - t["os_mi"] - t["cfc"], None, None),  # V2 targets = OS/MI + CFC exactly
        ("net_production_taxes", lambda t: t["P10"], s71, "s7_1.total.net_production_taxes.current"),
    ]  # fmt: skip


@pytest.mark.parametrize("name,fn,ds,sid", _nas_cases(), ids=[c[0] for c in _nas_cases()])
def test_production_totals_match_nas_2026(name, fn, ds, sid):
    v = fn(totals())
    if ds is None:
        assert abs(v) < 1e-6
        return
    assert abs(v - nas(ds, sid)) <= NAS_TOL, (name, v, nas(ds, sid))


def test_ic_matches_the_sut_note_and_output_by_nas_group():
    note_ic = one(f"select value from '{_p(CLEAN / 'io_tables' / 'io_tables_sut_note_totals.parquet')}' "
                  f"where period = '{YEAR}' and item_code = 'ic'")  # fmt: skip
    assert abs(totals()["P2"] - note_ic) <= 2.0
    codes = {"1": "agri", "2": "mining", "3": "manufacturing", "4": "utilities", "5": "construction",
             "6": "trade_hotels", "7": "transport_comm", "8": "financial", "9": "real_estate_prof",
             "10": "public_admin", "11": "other_services"}  # fmt: skip
    by_group = dict(
        q("""select i.nas_group, sum(c.value) from cells c join imap i using (industry)
                         where c.tbl='S' and c.item_code='output' and c.commodity is not null group by 1""")
    )
    for g, code in codes.items():
        if g in ("9", "11"):
            continue
        assert abs(by_group[g] - nas("mospi_nas_2026_s7_1", f"s7_1.{code}.output.current")) <= NAS_TOL, code
    both = nas("mospi_nas_2026_s7_1", "s7_1.real_estate_prof.output.current") + nas(
        "mospi_nas_2026_s7_1", "s7_1.other_services.output.current"
    )
    assert abs(by_group["9"] + by_group["11"] - both) <= NAS_TOL  # R&D: SUT group 11, NAS group 9


def test_checks_file_values_reproduce():
    """The block's own control-total file: every check passes and its SAM side equals this recomputation."""
    t = totals()
    assert one("select count(*) from tchecks") == 35 and one("select bool_and(ok) from tchecks")
    mine = {"gdp_production": t["P1"] - t["P2"] + t["tP7"] + t["P8"] + t["P9"], "pfce": t["tC1"], "gfce": t["tC2"],
            "gfcf": t["tI1"], "cis": t["I3"], "valuables": t["tI2"], "exports": t["P5"], "imports": t["P6"],
            "output": t["P1"], "ic_nas71": t["P2"], "ce": t["tV1"], "os_mi_cfc": t["tV2"],
            "net_production_taxes": t["P10"], "product_subsidies": -t["P9"]}  # fmt: skip
    for cid, v in mine.items():
        assert one(f"select sam_value from tchecks where check_id = '{cid}'") == pytest.approx(v, abs=TOL), cid


# ------------------------------------------------------------------------------------------ 5 provenance
@cache
def clean_prov() -> dict[str, tuple]:
    out = {}
    for unit in ("io_tables", "mospi_nas_2026"):
        for pid, src, status in q(
            f"select prov_id, source_id, status from '{_p(CLEAN / unit / '_provenance.parquet')}'"
        ):
            out[pid] = (src, status)
    return out


def test_every_prov_id_resolves_and_inputs_are_the_cells_aggregated():
    prov = {r[0]: r for r in q("select prov_id, status, inputs, method, source_id from tprov")}
    assert one("select count(*) from tprov") == 19
    used = {r[0] for r in q("select prov_id from theirs union select prov_id from tcons")}
    assert used <= set(prov)
    for pid, status, inputs, method, _ in prov.values():
        assert status == "official" and method and inputs
        for i in inputs.split(","):
            assert i in clean_prov(), (pid, i)
            assert clean_prov()[i][1] == "official", (pid, i)
    # entries: one record per ref, whose inputs are exactly the clean prov_ids of the cells aggregated
    for ref, pids in q("select rf, string_agg(distinct pids, ',') from mine where rf <> 'D4' group by 1"):
        want = ",".join(sorted(set(pids.split(","))))
        rec = q(f"select distinct prov_id from theirs where ref = '{ref}'")
        assert len(rec) == 1, ref
        assert prov[rec[0][0]][2] == want, ref
    # D4: the NAS 1.1 discrepancy (0) is the input
    d4 = q("select distinct prov_id from theirs where ref = 'D4'")[0][0]
    disc_pid = one(f"select prov_id from '{_p(CLEAN / 'mospi_nas_2026' / 'mospi_nas_2026_s1_1.parquet')}' "
                   f"where period = '{YEAR}' and series_id = 's1_1.discrepancies.current'")  # fmt: skip
    assert prov[d4][2] == disc_pid
    assert nas("mospi_nas_2026_s1_1", "s1_1.discrepancies.current") == 0.0


def test_record_source_id_matches_its_inputs():
    bad = []
    for pid, src, inputs in q("select prov_id, source_id, inputs from tprov"):
        srcs = {clean_prov()[i][0] for i in inputs.split(",")}
        if srcs != {src}:
            bad.append((pid, src, srcs))
    assert bad == []
