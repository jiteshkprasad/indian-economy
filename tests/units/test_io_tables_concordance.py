"""The committed SUT -> 34-sector SAM concordance (data/concordance/io_tables_*.csv, owned by the
io_tables unit), transcribed from docs/phase0/ACCOUNT_STRUCTURE.md section 2.

- every SUT industry 1-67 and product 1-155 maps to exactly one SAM activity / commodity;
- the three files agree with each other and with the SUT labels the unit parses;
- the NAS broad-group counts equal the SUT note's Table 5.1;
- applied to the clean 2023-24 SUT, the concordance reproduces the GVA shares, import shares (M/S)
  and export shares (X/Q) printed in ACCOUNT_STRUCTURE section 2 (so the table in the doc and the
  machine-readable files describe the same mapping).
"""

from __future__ import annotations

import csv
from collections import Counter

import polars as pl
import pytest

from pipeline.core import checks
from pipeline.core.paths import REPO_ROOT
from pipeline.ingest.io_tables import sut as SUT

pytestmark = pytest.mark.quality
CONC = REPO_ROOT / "data" / "concordance"


def _read(name: str) -> list[dict[str, str]]:
    with open(CONC / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def sectors():
    return _read("io_tables_sam34_sectors.csv")


@pytest.fixture(scope="module")
def industries():
    return _read("io_tables_sut_industry_to_sam34.csv")


@pytest.fixture(scope="module")
def products():
    return _read("io_tables_sut_product_to_sam34.csv")


def _rng(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.replace(" ", "").split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def test_every_industry_maps_exactly_once(industries, sectors):
    codes = [int(r["sut_industry"]) for r in industries]
    assert sorted(codes) == list(range(1, 68))
    assert not [c for c, n in Counter(codes).items() if n != 1]
    acts = {r["activity"] for r in sectors}
    assert len(acts) == 34
    assert {r["activity"] for r in industries} == acts  # every activity has at least one industry


def test_every_product_maps_exactly_once(products, sectors):
    codes = [int(r["sut_product"]) for r in products]
    assert sorted(codes) == list(range(1, 156))
    assert not [c for c, n in Counter(codes).items() if n != 1]
    coms = {r["commodity"] for r in sectors}
    assert len(coms) == 34
    assert {r["commodity"] for r in products} == coms


def test_sector_file_ranges_match_mapping_files(sectors, industries, products):
    ind = {int(r["sut_industry"]): r["activity"] for r in industries}
    prod = {int(r["sut_product"]): r["commodity"] for r in products}
    seen_i: list[int] = []
    seen_p: list[int] = []
    for s in sectors:
        assert s["activity"] == "A_" + s["commodity"][2:]  # same suffix on both sides (ACCOUNT_STRUCTURE s.2)
        for i in _rng(s["sut_industries"]):
            assert ind[i] == s["activity"], (i, s["activity"])
            seen_i.append(i)
        for p in _rng(s["sut_products"]):
            assert prod[p] == s["commodity"], (p, s["commodity"])
            seen_p.append(p)
    assert sorted(seen_i) == list(range(1, 68)) and sorted(seen_p) == list(range(1, 156))
    assert [int(s["sam_no"]) for s in sectors] == list(range(1, 35))


def test_labels_equal_the_sut_workbook_labels(industries, products):
    assert [r["sut_industry_label"] for r in industries] == list(SUT.INDUSTRIES)
    assert [r["sut_product_label"] for r in products] == list(SUT.PRODUCTS)


# SUT note Table 5.1 (printed p. 5): industries and products per NAS broad group 1..11
TABLE_5_1 = {
    1: (4, 41), 2: (6, 10), 3: (30, 75), 4: (4, 4), 5: (1, 1), 6: (2, 3), 7: (7, 7), 8: (2, 2), 9: (6, 7),
    10: (1, 1), 11: (4, 4),
}


def test_nas_group_counts_match_note_table_5_1(industries, products):
    ni = Counter(int(r["nas_group"]) for r in industries)
    npr = Counter(int(r["nas_group"]) for r in products)
    assert {g: (ni[g], npr[g]) for g in TABLE_5_1} == TABLE_5_1


def test_oilg_swap_note(products):
    """Products 43 and 44 (whose rows are swapped in the 2023-24 file) both map to C_OILG."""
    r = {int(x["sut_product"]): x for x in products}
    assert r[43]["commodity"] == r[44]["commodity"] == "C_OILG"
    assert "swapped" in r[43]["note"] and "swapped" in r[44]["note"]


# ACCOUNT_STRUCTURE s.2, columns GVA%, M/S% and X/Q% ("my calculations from SUT 2023-24")
DOC = {
    "CROP": (12.07, 1.6, 4.2), "LVST": (4.80, 0.3, 0.6), "FOFI": (2.46, 0.4, 0.2), "COAL": (0.48, 60.2, 1.0),
    "OILG": (0.54, 85.6, 0.0), "OMIN": (1.02, 12.3, 11.0), "FOOD": (1.24, 6.8, 8.3), "BVTB": (0.46, 4.8, 5.8),
    "TXAP": (1.49, 5.5, 23.3), "WOOD": (0.92, 8.7, 5.3), "GJOM": (0.46, 32.9, 21.4), "RPET": (0.99, 10.0, 34.6),
    "CHEM": (1.67, 25.4, 20.6), "PHRM": (0.87, 3.9, 33.9), "NMMN": (0.84, 4.9, 7.6), "MTLS": (1.40, 11.7, 10.1),
    "MACH": (1.70, 24.8, 18.1), "ELEQ": (0.94, 29.3, 20.3), "TREQ": (1.64, 10.8, 13.3), "CNST": (8.62, 0.3, 0.5),
    "UTIL": (2.77, 0.0, 0.0), "TRAD": (7.25, 0.4, 0.1), "HOTL": (1.29, 0.0, 0.0), "TRNS": (4.05, 1.9, 11.6),
    "COMM": (1.48, 2.1, 3.2), "FINS": (5.60, 1.8, 3.3), "INSR": (0.68, 0.0, 9.8), "DWEL": (7.59, 0.0, 0.0),
    "BSRE": (4.66, 19.1, 29.6), "ITSV": (6.66, 6.2, 52.7), "EDUC": (4.11, 10.7, 4.9), "HLTH": (1.46, 0.1, 0.2),
    "OSRV": (1.96, 21.0, 37.8), "PADM": (5.82, 0.5, 0.3),
}


def test_concordance_reproduces_account_structure_shares(industries, products):
    ind = {SUT.industry_code(int(r["sut_industry"])): r["activity"][2:] for r in industries}
    prod = {SUT.product_code(int(r["sut_product"])): r["commodity"][2:] for r in products}
    va = checks.load_dataset("io_tables", "io_tables_sut_va").filter(
        (pl.col("period") == "2023-24") & (pl.col("item_code") == "gva_production")
    )
    gva = va.with_columns(pl.col("industry").replace_strict(ind).alias("s"))
    tot = gva["value"].sum()
    got_gva = {k: round(100 * x / tot, 2) for k, x in gva.group_by("s", maintain_order=True).agg(pl.col("value").sum()).iter_rows()}
    sup = checks.load_dataset("io_tables", "io_tables_sut_supply").filter(
        (pl.col("period") == "2023-24") & pl.col("product").str.starts_with("sut_p") & pl.col("industry").is_null()
    )
    use = checks.load_dataset("io_tables", "io_tables_sut_use").filter(
        (pl.col("period") == "2023-24") & pl.col("product").str.starts_with("sut_p") & (pl.col("item_code") == "exports")
    )
    by = (
        pl.concat([sup, use])
        .with_columns(pl.col("product").replace_strict(prod).alias("s"))
        .group_by("s", "item_code", maintain_order=True)
        .agg(pl.col("value").sum())
        .pivot(on="item_code", index="s", values="value")
        .fill_null(0.0)
    )
    got = {}
    for r in by.iter_rows(named=True):
        m, q = r["imports_after_cif"], r["supply_bp"]
        got[r["s"]] = (got_gva[r["s"]], round(100 * m / (q + m), 1), round(100 * r["exports"] / q, 1))
    assert got == DOC
