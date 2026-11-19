"""The canonical CLEAN table and PROVENANCE table schemas (pandera + a few cross-column rules).

Clean tables are long/tidy: one row = one published number (or one labelled estimate) for one
series, one period and one vintage. See docs/phase1/PIPELINE_GUIDE.md for how to fill each column.
"""

from __future__ import annotations

import pandera.polars as pa
import polars as pl

from pipeline.core.geo import geography_problem
from pipeline.core.units import (
    PERIOD_PATTERNS,
    UNITS,
    clean_label,
    period_ok,
    period_start,
    vintage_end,
    vintage_problem,
)

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------------------------

STATUSES = ("official", "derived", "estimated")
STOCK_FLOW = ("flow", "stock", "n/a")
ESTIMATE_STAGES = (
    "Final",  # NAS final estimate (new series: third estimate); also 'Final Accounts'
    "TRE",  # third revised estimate (old NAS series)
    "SRE",  # second revised estimate (old NAS series)
    "FRE",  # first revised estimate
    "PE",  # provisional estimate
    "SAE",  # second advance estimate
    "FAE",  # first advance estimate
    "AE",  # advance estimate (unnumbered)
    "QE",  # quick estimate (old NAS series)
    "BE",  # budget estimate
    "RE",  # revised estimate (budget)
    "Actuals",  # accounts actuals (CGA, CAG, budget 'Actuals')
    "Provisional",  # provisional data of non-NAS sources (RBI, trade, ...)
    "Revised",  # revised data of non-NAS sources
    "Partially Revised",  # RBI's 'PR' flag (BoP, IIP, external debt): some components revised
    "Preliminary",
    "Audited",
    "Unaudited",
    "n.a.",  # the source has no estimate-stage concept (e.g. a survey report)
)
PRICE_BASIS_RE = r"^(current|constant_\d{4}_\d{2}|n/a)$"

# Optional classification columns ("dims"). Values are codes without spaces; the published text
# goes in item_label. Use only the dims your table actually has; leave the rest null.
DIMS = (
    "institution",  # institutional sector / sub-sector (e.g. households, nfc_public, gg_centre)
    "industry",  # activity / industry (NAS industry code, NIC code or a documented slug)
    "product",  # product / commodity (SUT product code, HS code, COICOP code)
    "instrument",  # financial instrument (deposits, loans, gsec, equity, ...)
    "counterparty",  # the other side of a flow (from-whom-to-whom), e.g. rest_of_world
    "geography",  # 'IN' (all India), a pipeline.core.geo State/UT code ('IN-MH'), or a partner's ISO3
    "household_group",  # rural/urban x quintile or other household class (e.g. rural_q1)
    "side",  # credit | debit | net | receipts | payments | assets | liabilities | uses | resources
    "dim_other",  # anything else as 'key=value;key=value' with keys sorted
)

_ID = r"^[a-z0-9][a-z0-9_]*$"
_CODE = r"^[a-z0-9][a-z0-9_.\-]*$"
_DIM = r"^[A-Za-z0-9][A-Za-z0-9_.:\-]*$"
_DIM_OTHER = r"^[a-z_]+=[^;=\s][^;=]*(;[a-z_]+=[^;=\s][^;=]*)*$"
# all India, an ISO 3166-2:IN State/UT, a project historical code (IN-XAP, ...; pipeline/core/geo.py),
# or a partner's ISO 3166-1 alpha-3. 'IN-..' codes are further checked against geo.ALL_CODES.
_GEOGRAPHY = r"^(IN|IN-[A-Z]{2}|IN-X[A-Z]{2}|[A-Z]{3})$"
_VINTAGE = r"^\d{4}(-\d{2}(-\d{2})?)?$"
_FY = r"^\d{4}-\d{2}$"
PROV_ID_RE = r"^[a-z][a-z0-9_]*:[0-9a-f]{12}$"

# ---------------------------------------------------------------------------------------------
# Clean table
# ---------------------------------------------------------------------------------------------


def _s(*checks: pa.Check, nullable: bool = False) -> pa.Column:
    return pa.Column(pl.String, list(checks), nullable=nullable)


CLEAN_COLUMNS: dict[str, pa.Column] = {
    "dataset": _s(pa.Check.str_matches(r"^[a-z][a-z0-9_]*$")),
    "series_id": _s(pa.Check.str_matches(_CODE)),
    "source_id": _s(pa.Check.str_matches(_ID)),
    "table_id": _s(pa.Check.str_length(1, 200)),
    "item_code": _s(pa.Check.str_matches(_CODE)),
    "item_label": _s(pa.Check.str_length(1, 500)),
    **{
        d: _s(pa.Check.str_matches({"geography": _GEOGRAPHY, "dim_other": _DIM_OTHER}.get(d, _DIM)), nullable=True)
        for d in DIMS
    },
    "stock_flow": _s(pa.Check.isin(list(STOCK_FLOW))),
    "period": _s(pa.Check.str_length(4, 15)),
    "period_type": _s(pa.Check.isin(list(PERIOD_PATTERNS))),
    "value": pa.Column(pl.Float64, nullable=False),
    "unit": _s(pa.Check.isin(list(UNITS))),
    "price_basis": _s(pa.Check.str_matches(PRICE_BASIS_RE)),
    "base_year": _s(pa.Check.str_matches(_FY), nullable=True),
    "vintage": _s(pa.Check.str_matches(_VINTAGE)),
    "estimate_stage": _s(pa.Check.isin(list(ESTIMATE_STAGES))),
    "status": _s(pa.Check.isin(list(STATUSES))),
    "prov_id": _s(pa.Check.str_matches(PROV_ID_RE)),
}
CLEAN_KEY = ("dataset", "series_id", "vintage", "period")
OPTIONAL_CLEAN_COLUMNS = (*DIMS, "base_year")  # the runner adds these as nulls when absent
# Within one (dataset, series_id) these must never vary: a series is one line item, one set of
# dims, one unit, one price basis, one frequency, from one source.
SERIES_INVARIANTS = ("source_id", "item_code", *DIMS, "stock_flow", "period_type", "unit", "price_basis")

CLEAN_SCHEMA = pa.DataFrameSchema(
    CLEAN_COLUMNS, strict=True, ordered=True, unique=list(CLEAN_KEY), name="clean", coerce=False
)
CLEAN_DTYPES: dict[str, pl.DataType] = {c: (pl.Float64() if c == "value" else pl.String()) for c in CLEAN_COLUMNS}

# ---------------------------------------------------------------------------------------------
# Provenance table
# ---------------------------------------------------------------------------------------------

PROV_COLUMNS: dict[str, pa.Column] = {
    "prov_id": _s(pa.Check.str_matches(PROV_ID_RE)),
    "ingest_unit": _s(pa.Check.str_matches(_ID)),
    "source_id": _s(pa.Check.str_matches(_ID)),
    "url": _s(pa.Check.str_matches(r"^https?://"), nullable=True),
    "raw_path": _s(pa.Check.str_matches(r"^data/raw/"), nullable=True),
    "raw_sha256": _s(pa.Check.str_matches(r"^[0-9a-f]{64}$"), nullable=True),
    "retrieved_at": _s(pa.Check.str_matches(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"), nullable=True),
    "table_id": _s(pa.Check.str_length(1, 200)),
    "locator": _s(pa.Check.str_length(1, 1000)),
    "unit_as_published": _s(pa.Check.str_length(1, 200)),
    "conversion": _s(pa.Check.str_length(1, 500)),
    "price_basis": _s(pa.Check.str_matches(PRICE_BASIS_RE)),
    "base_year": _s(pa.Check.str_matches(_FY), nullable=True),
    "vintage": _s(pa.Check.str_matches(_VINTAGE)),
    "release": _s(pa.Check.str_length(1, 300)),
    "status": _s(pa.Check.isin(list(STATUSES))),
    "method": _s(pa.Check.str_length(1, 4000), nullable=True),
    "inputs": _s(
        pa.Check.str_matches(r"^[a-z][a-z0-9_]*:[0-9a-f]{12}(,[a-z][a-z0-9_]*:[0-9a-f]{12})*$"), nullable=True
    ),
    "notes": _s(pa.Check.str_length(1, 4000), nullable=True),
}
PROV_KEY = ("prov_id",)
PROV_SCHEMA = pa.DataFrameSchema(PROV_COLUMNS, strict=True, ordered=True, unique=list(PROV_KEY), name="provenance")
PROV_DTYPES: dict[str, pl.DataType] = {c: pl.String() for c in PROV_COLUMNS}


# ---------------------------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------------------------


class CleanDataError(ValueError):
    """A clean or provenance table breaks the contract. The message lists the failing rows."""


def _fmt(df: pl.DataFrame, limit: int = 25) -> str:
    with pl.Config(tbl_rows=limit, tbl_cols=20, fmt_str_lengths=80, tbl_width_chars=200):
        return str(df.head(limit))


def _run_pandera(schema: pa.DataFrameSchema, df: pl.DataFrame, what: str) -> None:
    try:
        schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as e:
        raise CleanDataError(f"{what}: schema violations\n{_fmt(e.failure_cases)}") from None
    except pa.errors.SchemaError as e:  # pragma: no cover - lazy=True normally aggregates
        raise CleanDataError(f"{what}: {e}") from None


def _bad_vintages(df: pl.DataFrame) -> list[tuple[str, str]]:
    return [(v, why) for v in df["vintage"].unique(maintain_order=True).to_list() if (why := vintage_problem(v))]


def conform_clean(df: pl.DataFrame, dataset: str) -> pl.DataFrame:
    """Add the `dataset` column and absent optional columns, cast to schema dtypes, order columns.

    Unknown columns are an error (no silent drops). Missing required columns are an error.
    """
    if "dataset" in df.columns:
        wrong = df.filter(pl.col("dataset") != dataset)
        if wrong.height:
            raise CleanDataError(f"{dataset}: rows carry a different dataset name, e.g. {wrong['dataset'][0]!r}")
    else:
        df = df.with_columns(pl.lit(dataset).alias("dataset"))
    extra = [c for c in df.columns if c not in CLEAN_COLUMNS]
    if extra:
        raise CleanDataError(f"{dataset}: columns not in the clean schema: {extra}")
    for c in OPTIONAL_CLEAN_COLUMNS:
        if c not in df.columns:
            df = df.with_columns(pl.lit(None, dtype=pl.String).alias(c))
    missing = [c for c in CLEAN_COLUMNS if c not in df.columns]
    if missing:
        raise CleanDataError(f"{dataset}: required columns missing: {missing}")
    try:
        df = df.select([pl.col(c).cast(t, strict=True) for c, t in CLEAN_DTYPES.items()])
    except pl.exceptions.PolarsError as e:
        raise CleanDataError(f"{dataset}: cannot cast to schema dtypes: {e}") from None
    return df


def validate_clean(df: pl.DataFrame, what: str = "clean table") -> None:
    """Raise CleanDataError unless `df` satisfies the clean-table contract."""
    _run_pandera(CLEAN_SCHEMA, df, what)
    problems: list[str] = []

    inf = df.filter(pl.col("value").is_infinite())
    if inf.height:
        problems.append(f"infinite values:\n{_fmt(inf)}")

    # Python-level checks run on unique values only, so large tables stay fast.
    pairs = df.select("period", "period_type").unique(maintain_order=True)
    bad_pairs = [(p, t) for p, t in pairs.iter_rows() if not period_ok(p, t)]
    if bad_pairs:
        problems.append(
            "period does not match period_type (fy='2023-24', fq='Q1 2026-27', fh='H1 2023-24', "
            f"cy='2024', cq='2024-Q1', month='2024-12', date='2024-03-31', sy='2023-08/2024-07'): {bad_pairs[:20]}"
        )

    bad_vintages = _bad_vintages(df)
    if bad_vintages:
        problems.append(f"impossible vintage (publication date): {bad_vintages[:20]}")

    geos = [v for v in df["geography"].unique(maintain_order=True).to_list() if v is not None]
    bad_geos = [why for v in geos if (why := geography_problem(v))]
    if bad_geos:
        problems.append("geography outside the project State/UT code set (DECISIONS D1-9): " + "; ".join(bad_geos[:20]))

    others = [v for v in df["dim_other"].unique(maintain_order=True).to_list() if v is not None]
    unsorted = [v for v in others if (k := [kv.split("=", 1)[0] for kv in v.split(";")]) != sorted(set(k))]
    if unsorted:
        problems.append(f"dim_other keys must be unique and sorted ('a=1;b=2'): {unsorted[:20]!r}")

    if not bad_pairs and not bad_vintages:
        # A period cannot start after the release that reports it, except budget estimates (BE)
        # and our own estimates (projections).
        combos = (
            df.filter((pl.col("status") == "official") & (pl.col("estimate_stage") != "BE"))
            .select("period", "period_type", "vintage")
            .unique(maintain_order=True)
        )
        future = [(p, v) for p, t, v in combos.iter_rows() if period_start(p, t) > vintage_end(v)]
        if future:
            problems.append(
                "period starts after its vintage (publication date); only BE rows or status 'estimated' may: "
                f"{future[:20]}"
            )

    for col in ("item_label", "table_id"):
        vals = df[col].unique(maintain_order=True).to_list()
        bad = [v for v in vals if clean_label(v) != v]
        if bad:
            problems.append(f"{col} is not canonical (use units.clean_label): {bad[:20]!r}")

    const = df.filter(pl.col("price_basis").str.starts_with("constant_"))
    bad_base = const.filter(
        pl.col("base_year").is_null()
        | (pl.col("price_basis").str.slice(9).str.replace("_", "-") != pl.col("base_year"))
    )
    if bad_base.height:
        problems.append(
            "constant-price rows need base_year equal to the price basis year "
            f"(constant_2022_23 -> '2022-23'):\n{_fmt(bad_base.select('series_id', 'price_basis', 'base_year'))}"
        )

    varying = (
        df.group_by("dataset", "series_id", maintain_order=True)
        .agg([pl.col(c).n_unique().alias(c) for c in SERIES_INVARIANTS])
        .unpivot(index=["dataset", "series_id"], variable_name="column", value_name="n_distinct")
        .filter(pl.col("n_distinct") > 1)
    )
    if varying.height:
        problems.append(
            "a series_id must have one source, item_code, dims, stock_flow, period_type, unit and "
            f"price_basis; these vary:\n{_fmt(varying)}"
        )

    if problems:
        raise CleanDataError(f"{what}:\n" + "\n\n".join(problems))


def validate_provenance(df: pl.DataFrame, what: str = "provenance") -> None:
    """Raise CleanDataError unless `df` satisfies the provenance contract."""
    _run_pandera(PROV_SCHEMA, df, what)
    problems: list[str] = []
    off = df.filter(
        (pl.col("status") == "official")
        & pl.any_horizontal(pl.col("url", "raw_path", "raw_sha256", "retrieved_at").is_null())
    )
    if off.height:
        problems.append(f"official records need url, raw_path, raw_sha256 and retrieved_at:\n{_fmt(off)}")
    nomethod = df.filter((pl.col("status") != "official") & pl.col("method").is_null())
    if nomethod.height:
        problems.append(f"derived/estimated records need a method:\n{_fmt(nomethod.select('prov_id', 'status'))}")
    no_inputs = pl.col("inputs").is_null() & pl.col("raw_path").is_null()
    untraced = df.filter(
        ((pl.col("status") == "derived") & no_inputs)
        | ((pl.col("status") == "estimated") & no_inputs & pl.col("notes").is_null())
    )
    if untraced.height:
        problems.append(
            "derived records need inputs or a raw file; estimated records need inputs, a raw file or notes "
            f"(SPEC rule 1: every number traceable):\n{_fmt(untraced.select('prov_id', 'status'))}"
        )
    bad_vintages = _bad_vintages(df)
    if bad_vintages:
        problems.append(f"impossible vintage (publication date): {bad_vintages[:20]}")
    if problems:
        raise CleanDataError(f"{what}:\n" + "\n\n".join(problems))
