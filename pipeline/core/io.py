"""Deterministic writers. Every Parquet, JSON, YAML and text file the pipeline writes goes through here.

Rules (STACK_AND_REPO s1.5):
- Parquet: explicit Arrow schema, rows sorted by the full key, zstd level 3, fixed row-group size,
  no pandas/polars metadata, no timestamps. Floats rounded to a declared precision, -0.0 -> 0.0,
  NaN/inf rejected.
- JSON: sorted keys, UTF-8, LF, trailing newline, allow_nan=False, floats canonicalised the same way.
- All text files are written with LF line endings, whatever the OS.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

DEFAULT_DECIMALS = 6  # 1e-6 crore = Rs 10; ample for Rs crore, percent and index values
PARQUET_OPTIONS: dict[str, Any] = dict(
    compression="zstd",
    compression_level=3,
    row_group_size=100_000,
    use_dictionary=True,
    write_statistics=True,
    version="2.6",
    data_page_version="1.0",
    store_schema=True,
    write_page_index=False,
)

_PL_TO_ARROW: dict[Any, pa.DataType] = {
    pl.String: pa.string(),
    pl.Float64: pa.float64(),
    pl.Int64: pa.int64(),
    pl.Boolean: pa.bool_(),
}


class NonFiniteValueError(ValueError):
    """A NaN or infinite float where none is allowed."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write via a temp file in the same folder, then rename (no half-written files)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def write_text(path: Path, text: str) -> None:
    """UTF-8, LF-only text file with exactly one trailing newline."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"
    atomic_write_bytes(path, text.encode("utf-8"))


# ---------------------------------------------------------------------------------------------
# floats
# ---------------------------------------------------------------------------------------------


def canonical_float(x: float, decimals: int = DEFAULT_DECIMALS) -> float:
    if not math.isfinite(x):
        raise NonFiniteValueError(f"non-finite float {x!r}")
    y = round(x, decimals)
    return 0.0 if y == 0 else y  # also turns -0.0 into 0.0


def canonical_floats(
    df: pl.DataFrame,
    decimals: int | dict[str, int | None] = DEFAULT_DECIMALS,
    allow_nan: Sequence[str] = (),
) -> pl.DataFrame:
    """Round every float column, normalise -0.0 to 0.0, and reject NaN/inf.

    `decimals` is one precision for all float columns or {column: precision}. A column mapped to
    None was already rounded by the caller (e.g. Dataset.ratio_sig_digits): it is not rounded
    again, but NaN/inf are still rejected and -0.0 still becomes 0.0.
    Columns listed in `allow_nan` may hold NaN (rare; the caller must justify it). Nulls are left
    alone here; whether a column may be null is the schema's business.
    """
    exprs = []
    for name, dtype in df.schema.items():
        if dtype not in (pl.Float64, pl.Float32):
            continue
        d = decimals if isinstance(decimals, int) else decimals.get(name, DEFAULT_DECIMALS)
        col = pl.col(name).cast(pl.Float64)
        bad_expr = col.is_infinite() if name in allow_nan else (col.is_infinite() | col.is_nan())
        if df.select(bad_expr.fill_null(False).any()).item():
            raise NonFiniteValueError(f"column {name!r} contains NaN or infinite values")
        rounded = col if d is None else col.round(d)
        exprs.append(pl.when(rounded == 0).then(pl.lit(0.0)).otherwise(rounded).alias(name))
    return df.with_columns(exprs) if exprs else df


# ---------------------------------------------------------------------------------------------
# Parquet
# ---------------------------------------------------------------------------------------------


def arrow_schema_for(df: pl.DataFrame) -> pa.Schema:
    fields = []
    for name, dtype in df.schema.items():
        at = _PL_TO_ARROW.get(dtype.base_type())
        if at is None:
            raise TypeError(
                f"column {name!r}: dtype {dtype} is not allowed in pipeline Parquet "
                "(use String, Float64, Int64 or Boolean)"
            )
        fields.append(pa.field(name, at, nullable=True))
    return pa.schema(fields)


def parquet_bytes(
    df: pl.DataFrame,
    *,
    sort_by: Sequence[str],
    decimals: int | dict[str, int | None] = DEFAULT_DECIMALS,
    allow_nan: Sequence[str] = (),
) -> bytes:
    """Canonical Parquet bytes for `df` (sorted, rounded, fixed options, no volatile metadata)."""
    missing = [c for c in sort_by if c not in df.columns]
    if missing:
        raise KeyError(f"sort key columns missing: {missing}")
    df = canonical_floats(df, decimals, allow_nan)
    df = df.sort(list(sort_by), nulls_last=True, maintain_order=True)
    schema = arrow_schema_for(df)
    table = df.to_arrow().cast(schema).replace_schema_metadata(None)
    buf = io.BytesIO()
    pq.write_table(table, buf, **PARQUET_OPTIONS)
    return buf.getvalue()


def write_parquet(
    df: pl.DataFrame,
    path: Path,
    *,
    sort_by: Sequence[str],
    decimals: int | dict[str, int | None] = DEFAULT_DECIMALS,
    allow_nan: Sequence[str] = (),
) -> str:
    """Write canonical Parquet; returns the sha256 of the bytes written."""
    data = parquet_bytes(df, sort_by=sort_by, decimals=decimals, allow_nan=allow_nan)
    atomic_write_bytes(path, data)
    return sha256_bytes(data)


def read_parquet(path: Path) -> pl.DataFrame:
    return pl.read_parquet(path)


# ---------------------------------------------------------------------------------------------
# JSON and YAML
# ---------------------------------------------------------------------------------------------


def _canon(obj: Any, decimals: int | None) -> Any:
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise NonFiniteValueError(f"non-finite float {obj!r} in JSON payload")
        if decimals is not None:
            return canonical_float(obj, decimals)
        return 0.0 if obj == 0 else obj
    if isinstance(obj, dict):
        return {str(k): _canon(v, decimals) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canon(v, decimals) for v in obj]
    return obj


def dumps_json(obj: Any, *, indent: int | None = 2, decimals: int | None = None) -> str:
    """Canonical JSON text: sorted keys, no NaN, fixed separators, trailing newline."""
    seps = (",", ":") if indent is None else (",", ": ")
    text = json.dumps(
        _canon(obj, decimals),
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        indent=indent,
        separators=seps,
    )
    return text + "\n"


def write_json(path: Path, obj: Any, *, indent: int | None = 2, decimals: int | None = None) -> str:
    """Write canonical JSON; returns sha256 of the bytes."""
    data = dumps_json(obj, indent=indent, decimals=decimals).encode("utf-8")
    atomic_write_bytes(path, data)
    return sha256_bytes(data)


def dumps_yaml(obj: Any, header: str = "") -> str:
    body = yaml.safe_dump(obj, sort_keys=True, allow_unicode=True, default_flow_style=False, width=1000)
    return (header.rstrip("\n") + "\n" if header else "") + body


def write_yaml(path: Path, obj: Any, header: str = "") -> None:
    write_text(path, dumps_yaml(obj, header))


def read_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
