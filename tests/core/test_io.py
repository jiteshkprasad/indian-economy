import json
import subprocess
import sys

import polars as pl
import pytest

from pipeline.core import io
from pipeline.core.env import ALLOW_HASHSEED_VAR, pinned_environ

pytestmark = pytest.mark.unit


def _frame(order=None):
    df = pl.DataFrame(
        {
            "k": ["b", "a", "c", "a"],
            "p": ["2023-24", "2023-24", "2022-23", "2022-23"],
            "v": [1.23456789, -1e-9, 3.0, 2.5],
        }
    )
    return df if order is None else df[order]


def test_parquet_is_byte_identical_across_writes_and_input_order(tmp_path):
    a = io.write_parquet(_frame(), tmp_path / "a.parquet", sort_by=["k", "p"])
    b = io.write_parquet(_frame(), tmp_path / "b.parquet", sort_by=["k", "p"])
    c = io.write_parquet(_frame([3, 2, 1, 0]), tmp_path / "c.parquet", sort_by=["k", "p"])
    assert a == b == c
    assert (tmp_path / "a.parquet").read_bytes() == (tmp_path / "c.parquet").read_bytes()


def test_parquet_canonical_floats(tmp_path):
    io.write_parquet(_frame(), tmp_path / "a.parquet", sort_by=["k", "p"])
    back = pl.read_parquet(tmp_path / "a.parquet")
    assert back["k"].to_list() == ["a", "a", "b", "c"]  # sorted by key
    vals = back["v"].to_list()
    assert vals[1] == 0.0 and str(vals[1]) == "0.0"  # -1e-9 rounds to -0.0, normalised to 0.0
    assert vals[2] == 1.234568  # 6 decimals
    assert pl.read_parquet_schema(tmp_path / "a.parquet") == {"k": pl.String, "p": pl.String, "v": pl.Float64}


def test_parquet_has_no_volatile_metadata(tmp_path):
    import pyarrow.parquet as pq

    io.write_parquet(_frame(), tmp_path / "a.parquet", sort_by=["k", "p"])
    md = pq.read_metadata(tmp_path / "a.parquet")
    keys = set((md.metadata or {}).keys())
    assert keys <= {b"ARROW:schema"}, keys  # no pandas/polars/timestamp metadata


def test_nan_and_inf_are_rejected(tmp_path):
    for bad in (float("nan"), float("inf")):
        df = pl.DataFrame({"k": ["a"], "v": [bad]})
        with pytest.raises(io.NonFiniteValueError):
            io.write_parquet(df, tmp_path / "x.parquet", sort_by=["k"])
    df = pl.DataFrame({"k": ["a"], "v": [float("nan")]})
    io.write_parquet(df, tmp_path / "y.parquet", sort_by=["k"], allow_nan=["v"])  # explicit opt-in


def test_unsupported_dtype_rejected(tmp_path):
    df = pl.DataFrame({"k": ["a"], "v": [1]}, schema={"k": pl.String, "v": pl.Int32})
    with pytest.raises(TypeError):
        io.write_parquet(df, tmp_path / "x.parquet", sort_by=["k"])


def test_json_is_canonical(tmp_path):
    obj = {"b": 1.0, "a": [-0.0, 1.23456789], "c": "₹ crore"}
    io.write_json(tmp_path / "a.json", obj, decimals=6)
    raw = (tmp_path / "a.json").read_bytes()
    assert b"\r\n" not in raw and raw.endswith(b"}\n")
    assert raw.index(b'"a"') < raw.index(b'"b"') < raw.index(b'"c"')
    assert json.loads(raw) == {"a": [0.0, 1.234568], "b": 1.0, "c": "₹ crore"}
    assert "₹".encode() in raw  # UTF-8, not \\u escapes
    with pytest.raises(io.NonFiniteValueError):
        io.dumps_json({"x": float("nan")})


def test_write_text_forces_lf(tmp_path):
    io.write_text(tmp_path / "t.md", "a\r\nb\rc\n\n")
    assert (tmp_path / "t.md").read_bytes() == b"a\nb\nc\n"


_SEED_SCRIPT = r"""
import sys, polars as pl
from pipeline.core import io
labels = {"HH_urban_q5", "FIRMS_pvt", "ROW", "RBI", "GOV_states", "GOV_centre", "HH_rural_q1", "BANKS"}
df = pl.DataFrame({"k": list(labels), "v": [float(len(x)) / 3 for x in labels]})
sys.stdout.write(io.sha256_bytes(io.parquet_bytes(df, sort_by=["k"])))
"""


@pytest.mark.hygiene
def test_output_independent_of_hash_seed():
    hashes = set()
    for seed in ("1", "2", "3"):
        env = pinned_environ({"PYTHONHASHSEED": seed, ALLOW_HASHSEED_VAR: "1"})
        out = subprocess.run([sys.executable, "-c", _SEED_SCRIPT], env=env, capture_output=True, text=True, check=True)
        hashes.add(out.stdout.strip())
    assert len(hashes) == 1, hashes
