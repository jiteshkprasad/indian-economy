"""Identities of the exported SAM cells (PLAN s.5.1 item 1), on the real export and on the fixture.

Recomputed with DuckDB from the parquet files (real) and from the exported cells themselves (both)."""

from __future__ import annotations

from collections import defaultdict

import duckdb
import pytest
from _export_helpers import SAM

from pipeline.export.hierarchy import load_hierarchy

pytestmark = pytest.mark.export


def _cells(ex) -> list[tuple[str, str, float]]:
    h = ex.get("hierarchy.json")
    codes = [a["code"] for a in h["accounts"]]
    c = ex.get("sam/cells.json")
    assert all(len(c[k]) == c["n"] for k in c if k != "n")
    return [(codes[r], codes[k], v) for r, k, v in zip(c["row"], c["col"], c["v"], strict=True)]


def test_every_account_balances(ex) -> None:
    cells = _cells(ex)
    rows: dict[str, float] = defaultdict(float)
    cols: dict[str, float] = defaultdict(float)
    for r, c, v in cells:
        rows[r] += v
        cols[c] += v
    tol = 0.005 * len(cells)
    for a in set(rows) | set(cols):
        assert abs(rows[a] - cols[a]) <= tol, a


def test_cells_equal_parquet_totals(real) -> None:
    cells = _cells(real)
    con = duckdb.connect()
    got = {
        (r, c): v
        for r, c, v in con.execute(
            f"select row, col, round(value, 2) from read_parquet('{SAM / 'sam_balanced.parquet'}') "
            "where round(value, 2) <> 0"
        ).fetchall()
    }
    assert len(got) == len(cells) == 2169
    for r, c, v in cells:
        assert v == pytest.approx(got[(r, c)], abs=0.011)  # DuckDB rounds half away from zero
    rt = dict(
        con.execute(
            f"select row, sum(value) from read_parquet('{SAM / 'sam_balanced.parquet'}') group by row"
        ).fetchall()
    )
    mine: dict[str, float] = defaultdict(float)
    for r, _, v in cells:
        mine[r] += v
    for a, t in rt.items():
        assert mine[a] == pytest.approx(t, abs=0.005 * len(cells)), a


def test_composition_and_split_consistent(ex) -> None:
    from pipeline.export.status import LABEL_CODE, split_of

    c = ex.get("sam/cells.json")
    for i in range(c["n"]):
        _, lab = split_of(c["abs_o"][i], c["abs_d"][i], c["abs_e"][i], c["abs_b"][i])
        assert c["split"][i] == LABEL_CODE[lab]
        assert c["abs_o"][i] + c["abs_d"][i] + c["abs_e"][i] + c["abs_b"][i] >= abs(c["v"][i]) - 0.05
        assert c["n_entries"][i] >= 1 and c["refs"][i]


def test_level0_aggregates_equal_duckdb(real) -> None:
    """Positive and negative parts of every level-0 pair (full preset), DuckDB vs the exported cells."""
    h = load_hierarchy()
    m = h.preset_map("full")
    con = duckdb.connect()
    con.execute("create table m(code varchar, node varchar)")
    con.executemany("insert into m values (?, ?)", list(m.items()))
    sql = f"""
        select mc.node as payer, mr.node as receiver, sum(case when v > 0 then v else 0 end) pos,
               sum(case when v < 0 then v else 0 end) neg
        from (select row, col, round(value, 2) v from read_parquet('{SAM / "sam_balanced.parquet"}')) s
        join m mr on mr.code = s.row join m mc on mc.code = s.col
        where mr.node <> mc.node group by 1, 2"""
    want = {(p, q): (a, b) for p, q, a, b in con.execute(sql).fetchall() if a or b}  # D4 cells are zero
    got: dict = defaultdict(lambda: [0.0, 0.0])
    for r, c, v in _cells(real):
        if m[r] != m[c]:
            got[(m[c], m[r])][0 if v > 0 else 1] += v
    assert set(want) == set(got)
    for k, (a, b) in want.items():
        assert got[k][0] == pytest.approx(a, abs=0.01)
        assert got[k][1] == pytest.approx(b, abs=0.01)


def test_entries_sum_to_cells(ex) -> None:
    cells = {(r, c): v for r, c, v in _cells(ex)}
    sums: dict = defaultdict(float)
    n = 0
    for node in load_hierarchy().level0:
        for e in ex.get(f"sam/entries/{node}.json")["entries"]:
            sums[(e["row"], e["col"])] += e["v"]
            n += 1
    assert n == ex.get("summary.json")["sam"]["entries"]
    for k, v in cells.items():
        assert sums[k] == pytest.approx(v, abs=0.01 * 10)


def test_entry_pct_change_is_a_fraction(ex) -> None:
    """pct_change = (v - prior) / |prior| as a fraction (0.05 = 5%), not the balancing log's percent (V1-01).
    The exported v and prior are rounded to Rs 0.01 crore, so the recomputed ratio is allowed that much slack."""
    checked = big = 0
    bad = []
    for node in load_hierarchy().level0:
        for e in ex.get(f"sam/entries/{node}.json")["entries"]:
            if e["prior"] == 0:
                assert e["pct_change"] is None or e["pct_change"] == 0, e
                continue
            if e["pct_change"] is None:
                continue
            want = (e["v"] - e["prior"]) / abs(e["prior"])
            slack = 1e-6 + 0.0101 * (1 + abs(want)) / abs(e["prior"])
            checked += 1
            big += abs(want) >= 0.01
            if abs(e["pct_change"] - want) > slack:
                bad.append((e["row"], e["col"], e["ref"], e["component"], e["prior"], e["v"], e["pct_change"]))
    assert checked > 100 and big > 10, (checked, big)
    assert not bad, (len(bad), bad[:5])


def test_entry_pct_change_matches_balancing_log(real) -> None:
    """Real export: pct_change is the balancing log's percent divided by 100, entry by entry."""
    log = duckdb.sql(
        f"SELECT row, col, ref, component, pct_change FROM '{SAM / 'balancing_log.parquet'}' "
        "WHERE pct_change IS NOT NULL"
    ).fetchall()
    want: dict = defaultdict(list)
    for r, c, ref, comp, p in log:
        want[(r, c, ref, comp)].append(p / 100.0)
    got: dict = defaultdict(list)
    for node in load_hierarchy().level0:
        for e in real.get(f"sam/entries/{node}.json")["entries"]:
            if e["pct_change"] is not None:
                got[(e["row"], e["col"], e["ref"], e["component"])].append(e["pct_change"])
    assert set(got) == set(want)
    for k, ps in want.items():
        assert sorted(got[k]) == pytest.approx(sorted(ps), abs=1e-6), k
