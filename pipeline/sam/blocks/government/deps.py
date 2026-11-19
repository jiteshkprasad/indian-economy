"""government's integration boundary: everything it reads from other blocks, in one place (CROSS_REVIEW s.4.3).

`read_deps(ctx)` reads the built DEPENDS outputs; tests build a `Deps` by hand (synthetic fixtures) so the rest
of the block runs before the dependencies exist. Every number keeps the prov_id of the record it came from.

Read from:
- production: constraints `gfce.<commodity>` (SUT GFCE by commodity, the C2a row totals; not re-declared, XR-15)
  and the P9 entry T_PSUB <- C_RPET (the LPG subsidy the SUT books as a product subsidy; R10 `lpg_dbt` is the rest).
- factors: F4b entries G_CEN / G_STA <- F_GOSC (GG CFC by government: the institutional NAS 4.1 key, used as
  the C2a Centre column target and as CFC in the K3a bridge), F2 entries H_* <- F_MIXD component `nonfarm`
  (households' share of mining royalties, R7x) and component `farm` (the PM-KISAN key, R10 `pm_kisan`),
  satellite `factor_income_keys` key `public_sector_wage_key`
  (F_LREG x PLFS public-sector share: the R9a / R9b / R9d / R7x-households key, XR-10 item 8), satellite
  `gg_centre_state_key` (NAS 4.1 NVA of local bodies and autonomous institutions and the part of the latter that
  F4b gives the Centre: the key of the GG units outside the Union and State treasury accounts, used to allocate
  the unexplained remainder of the K3a saving bridge).
- households: satellite `hh_keys` key `pop_persons` (R10 cash transfers by population).
- taxes: entries G_* <- T_PIT / T_CIT (current taxes on income received by GG), used only for the D2-5 R9b
  evidence (GG disposable income with and without R9b).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl

from pipeline.sam.blocks.government.core import GOV, HH, Q
from pipeline.sam.framework import BlockContext, SamError

GFCE_COMMODITIES = ("C_CROP", "C_PADM", "C_EDUC", "C_HLTH", "C_CNST", "C_UTIL")  # the SUT's non-zero GFCE rows


@dataclass
class Deps:
    gfce: dict[str, Q]  # C_* -> SUT GFCE target (production constraint gfce.<c>), non-zero rows only
    p9_rpet: Q  # production P9 T_PSUB <- C_RPET (negative, Rs crore)
    f4b: dict[str, Q]  # G_CEN / G_STA -> CFC (factors F4b)
    public_wage_key: dict[str, Q]  # H_* -> level of the public-sector wage key (factors)
    mi_nonfarm: dict[str, Q]  # H_* -> non-farm mixed income (factors F2 `nonfarm`)
    mi_farm: dict[str, Q]  # H_* -> farm mixed income (factors F2 `farm`): the PM-KISAN key (R10 `pm_kisan`)
    pop: dict[str, Q]  # H_* -> persons (households hh_keys pop_persons)
    income_taxes: dict[str, Q]  # G_* -> T_PIT + T_CIT received (taxes T1a/T2x)
    outside_nva: dict[str, Q]  # G_* -> NAS 4.1 NVA of GG units outside the treasury accounts (factors' F4b split)
    notes: list[str] = field(default_factory=list)


def _q(v: float, pid: str) -> Q:
    return Q(float(v), frozenset({pid}))


def _by(df: pl.DataFrame, col: str, want: list[str], what: str) -> dict[str, Q]:
    out: dict[str, Q] = {}
    for r in df.iter_rows(named=True):
        k = str(r[col]).upper()
        if k not in want:
            raise SamError(f"government: {what}: unexpected {col} {r[col]!r}")
        out[k] = out.get(k, Q(0.0)) + _q(r["value"], r["prov_id"])
    missing = [k for k in want if k not in out]
    if missing:
        raise SamError(f"government: {what}: missing {missing}")
    return out


def _key(sat: pl.DataFrame, key: str, what: str) -> dict[str, Q]:
    for c in ("key", "household_group", "value", "prov_id"):
        if c not in sat.columns:
            raise SamError(f"government: {what} has no column {c!r} (columns {sat.columns})")
    df = sat.filter(pl.col("key") == key)
    if df.height == 0:
        raise SamError(f"government: {what} has no key {key!r} (keys {sorted(set(sat['key'].drop_nulls()))})")
    if "measure" in df.columns and (df["measure"] == "level").any():
        df = df.filter(pl.col("measure") == "level")
    elif "measure" in df.columns:
        df = df.filter(pl.col("measure") == "share")
    return _by(df, "household_group", HH, f"{what} {key}")


def read_deps(ctx: BlockContext) -> Deps:
    notes: list[str] = []

    pc = ctx.block_constraints("production")
    g = pc.filter(pl.col("constraint_id").str.starts_with("gfce."))
    gfce: dict[str, Q] = {}
    for r in g.iter_rows(named=True):
        code = str(r["constraint_id"]).split(".", 1)[1].upper()
        if r["target"] != 0:
            gfce[code] = _q(r["target"], r["prov_id"])
    if sorted(gfce) != sorted(GFCE_COMMODITIES):
        raise SamError(
            f"government: production's non-zero GFCE commodities are {sorted(gfce)}, the C2a method covers "
            f"{sorted(GFCE_COMMODITIES)}: extend the C2a mapping first"
        )
    pe = ctx.block_entries("production")
    p9 = pe.filter((pl.col("ref") == "P9") & (pl.col("row") == "T_PSUB") & (pl.col("col") == "C_RPET"))
    if p9.height != 1:
        raise SamError(f"government: production P9 T_PSUB <- C_RPET: {p9.height} entries, need 1")
    p9_rpet = _q(p9["value"][0], p9["prov_id"][0])

    fe = ctx.block_entries("factors")
    f4b = _by(fe.filter((pl.col("ref") == "F4b") & (pl.col("col") == "F_GOSC")), "row", GOV, "factors F4b")
    f2 = fe.filter((pl.col("ref") == "F2") & (pl.col("col") == "F_MIXD") & (pl.col("component") == "nonfarm"))
    mi_nonfarm = _by(f2, "row", HH, "factors F2 nonfarm")
    f2f = fe.filter((pl.col("ref") == "F2") & (pl.col("col") == "F_MIXD") & (pl.col("component") == "farm"))
    mi_farm = _by(f2f, "row", HH, "factors F2 farm")
    wage_key = _key(ctx.satellite("factors", "factor_income_keys"), "public_sector_wage_key",
                    "factors factor_income_keys")  # fmt: skip

    pop = _key(ctx.satellite("households", "hh_keys"), "pop_persons", "households hh_keys")

    te = ctx.block_entries("taxes")
    inc = te.filter(pl.col("row").is_in(GOV) & pl.col("col").is_in(["T_PIT", "T_CIT"]))
    income_taxes = _by(inc, "row", GOV, "taxes G_* <- T_PIT/T_CIT")
    outside_nva = _outside_nva(ctx.satellite("factors", "gg_centre_state_key"))
    return Deps(gfce, p9_rpet, f4b, wage_key, mi_nonfarm, mi_farm, pop, income_taxes, outside_nva, notes)


def _outside_nva(sat: pl.DataFrame) -> dict[str, Q]:
    """NVA (NAS 4.1) of the GG units the Union and State treasury accounts do not cover, by government, as factors'
    F4b splits them: Centre = the autonomous institutions F4b gives the Centre; States = local bodies + the rest of
    the autonomous institutions."""
    want = ("autonomous_to_centre", "nva.autonomous_institutions", "nva.local_bodies")
    got = {r["series_id"]: _q(r["value"], r["prov_id"]) for r in sat.iter_rows(named=True) if r["series_id"] in want}
    missing = [w for w in want if w not in got]
    if missing:
        raise SamError(f"government: factors gg_centre_state_key has no rows {missing}")
    cen = got["autonomous_to_centre"]
    sta = got["nva.local_bodies"] + got["nva.autonomous_institutions"] - cen
    if cen.v < 0 or sta.v <= 0:
        raise SamError(f"government: outside-treasury NVA key is not positive (Centre {cen.v}, States {sta.v})")
    return {"G_CEN": cen, "G_STA": sta}
