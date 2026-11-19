"""fincorp's integration boundary: everything it reads from other blocks, in one place (CROSS_REVIEW s.4.3).

`read_deps(ctx)` reads the built DEPENDS outputs; tests build a `Deps` by hand (synthetic fixtures) so the
rest of the block can be exercised before the dependencies exist. Every number keeps the prov_id of the
dependency record it came from.

Read from:
- households: satellite `hh_keys` (group keys `aidis_fin_assets`, `aidis_inst_loans`, `aidis_deposits`,
  `aidis_equity`, `aidis_mf`, `aidis_small_savings`, `pop_persons`, `c4b_insurance_service`) and its C4b
  entries C_FINS <- H_* components `fisim_deposits` / `fisim_loans` (XR-5).
- factors: F1a entries H_* <- F_LREG (regular-wage key), satellite `factor_income_keys` key
  `public_sector_wage_key` (XR-10/8), F4 entries E_NFPU/E_NFPR <- F_GOSC (NFC GOS), constraint `f4.fc_gos`.
- government: R6 entry G_CEN <- E_RBI (RBI surplus, cash), R7 entries G_* <- E_* (dividends to GG) and R7x
  entries G_* <- E_NFPU/E_NFPR (interest and resource rents paid to GG; read only to measure the private NFCs'
  net property income for the D2-21 old-base structure of R8, dividends.py).
- rest_of_world: R13 / R14 / R14a entries (RoW property income by domestic account, XR-4, XR-12).
  Its components are read by name (ROW_* below); `check_row_components` stops the build if they change.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl

from pipeline.sam.blocks.fincorp.core import HH, Q
from pipeline.sam.framework import BlockContext, SamError

KEYS_NEEDED = (
    "aidis_fin_assets",
    "aidis_inst_loans",
    "aidis_deposits",
    "aidis_equity",
    "aidis_mf",
    "aidis_small_savings",
    "pop_persons",
    "c4b_insurance_service",
)
# asset-class keys households may not publish yet: fall back (logged) to the total financial-assets key
KEY_FALLBACK = {
    "aidis_deposits": "aidis_fin_assets",
    "aidis_equity": "aidis_fin_assets",
    "aidis_mf": "aidis_fin_assets",
    "aidis_small_savings": "aidis_fin_assets",
}
# rest_of_world component names (its plan s.2.3/2.4 and XR-4/XR-12)
ROW_RBI_UNEXPLAINED = "reserve_income_unexplained"
ROW_FPI = {
    "dated": ("G_CEN", "fpi_gsec_interest"),
    "tbills": ("G_CEN", "fpi_tbill_interest"),
    "sdl": ("G_STA", "fpi_sdl_interest"),
}  # instrument -> (payer, rest_of_world R14 component)
ROW_NOT_INTEREST = "other_primary_income"  # BoP 'other primary income', spread pro rata by rest_of_world
# rest_of_world components that are interest in a lender's P&L (DI and PI income, mostly dividends and RE, are not)
ROW_INTEREST_IN = ("oi_income",)  # R13
ROW_INTEREST_OUT = ("nri_deposit_interest", "oi_other_interest")  # R14
# BoP 'reserve assets' income debit, which rest_of_world assigns to E_RBI (its issues rest_of_world-13/-26: very
# probably the charges on India's SDR allocations, a G_CEN liability); the RBI Annual Report shows no such charge
ROW_RBI_DEBIT = "reserve_asset_debit"
# RoW dividends of direct-investment enterprises (R14), shown next to fincorp's FSF-share RoW memo (dividend_matrix)
ROW_DIV = "di_distributed"
# every rest_of_world R13/R14/R14a component this block knows. fincorp reads several by name (above), so a
# renamed, removed or new component stops the build instead of silently dropping out of a sum (no silent fallbacks)
ROW_KNOWN = {
    "R13": (
        "di_income",
        "oi_income",
        "other_primary_income",
        "pi_income",
        "reserve_asset_income",
        ROW_RBI_UNEXPLAINED,
    ),
    "R14": (
        ROW_DIV,
        "ext_assistance_interest",
        *(c for _, c in ROW_FPI.values()),
        "nri_deposit_interest",
        "oi_other_interest",
        ROW_NOT_INTEREST,
        "pi_other",
        ROW_RBI_DEBIT,
    ),
    "R14a": ("reinvested_earnings",),
}
# the components whose absence would change fincorp's numbers or checks (the rest are only known)
ROW_REQUIRED = (
    ("R13", ROW_RBI_UNEXPLAINED),
    ("R13", "oi_income"),
    *(("R14", c) for _, c in ROW_FPI.values()),
    ("R14", ROW_NOT_INTEREST),
    ("R14", ROW_RBI_DEBIT),
    ("R14", ROW_DIV),
    *(("R14", c) for c in ROW_INTEREST_OUT),
)


@dataclass
class Deps:
    hh_keys: dict[str, dict[str, Q]]  # key -> H_* -> level (consumers normalise)
    c4b_fisim: dict[str, dict[str, Q]]  # 'fisim_deposits' / 'fisim_loans' -> H_* -> Rs crore
    wage_regular: dict[str, Q]  # H_* -> F1a regular wages (F_LREG)
    wage_public: dict[str, Q]  # H_* -> public-sector wage key level
    nfc_gos: dict[str, Q]  # E_NFPU / E_NFPR -> GOS (factors F4)
    r6: Q  # RBI surplus to the Centre (government R6, cash)
    r7: dict[tuple[str, str], Q]  # (G_*, E_*) -> dividends received by government (government R7)
    row: list[dict] = field(default_factory=list)  # rest_of_world entries: row, col, ref, component, q
    factors_fc_gos: Q | None = None  # factors' FC GOS constraint target (a check only)
    prod_os: dict[str, Q] = field(default_factory=dict)  # production's OS/MI+CFC targets for A_FINS / A_INSR (checks)
    notes: list[str] = field(default_factory=list)  # fallbacks taken (also ctx.warn)
    # (G_*, payer) -> government R7x (interest and rents paid to GG by non-government units); D2-21 net D4 of E_NFPR
    r7x: dict[tuple[str, str], Q] = field(default_factory=dict)

    def key(self, name: str) -> dict[str, Q]:
        k = self.hh_keys.get(name)
        if k is None:
            raise SamError(f"fincorp: household key {name!r} not available (have {sorted(self.hh_keys)})")
        return k

    def row_sum(
        self,
        *,
        row: str | None = None,
        col: str | None = None,
        refs: tuple[str, ...] = ("R13", "R14"),
        comps: tuple[str, ...] | None = None,
        exclude: tuple[str, ...] = (),
    ) -> Q:
        out = Q(0.0)
        for e in self.row:
            if (row is None or e["row"] == row) and (col is None or e["col"] == col) and e["ref"] in refs:
                if (comps is None or e["component"] in comps) and e["component"] not in exclude:
                    out = out + e["q"]
        return out


def _q(v: float, pid: str) -> Q:
    return Q(float(v), frozenset({pid}))


def _group_levels(df: pl.DataFrame, what: str) -> dict[str, Q]:
    out: dict[str, Q] = {}
    for r in df.iter_rows(named=True):
        g = str(r["household_group"]).upper()
        if g not in HH:
            raise SamError(f"fincorp: {what}: unknown household group {r['household_group']!r}")
        out[g] = out.get(g, Q(0.0)) + _q(r["value"], r["prov_id"])
    missing = [g for g in HH if g not in out]
    if missing:
        raise SamError(f"fincorp: {what}: groups missing {missing}")
    return out


def _hh_keys(ctx: BlockContext, notes: list[str]) -> dict[str, dict[str, Q]]:
    sat = ctx.satellite("households", "hh_keys")
    for c in ("key", "household_group", "value", "prov_id"):
        if c not in sat.columns:
            raise SamError(f"fincorp: households hh_keys has no column {c!r} (columns {sat.columns})")
    have = set(sat["key"].drop_nulls().to_list())
    out: dict[str, dict[str, Q]] = {}
    for k in KEYS_NEEDED:
        name = k
        if k not in have and k in KEY_FALLBACK and KEY_FALLBACK[k] in have:
            name = KEY_FALLBACK[k]
            msg = f"hh_keys has no {k!r}: using {name!r} instead (XR-10 asks households to publish it)"
            ctx.warn(msg)
            notes.append(msg)
        if name not in have:
            raise SamError(f"fincorp: households hh_keys has no key {name!r} (keys: {sorted(have)})")
        df = sat.filter(pl.col("key") == name)
        if "measure" in df.columns and (df["measure"] == "level").any():
            df = df.filter(pl.col("measure") == "level")
        elif "measure" in df.columns:
            df = df.filter(pl.col("measure") == "share")
        out[k] = _group_levels(df, f"hh_keys {name}")
    return out


def read_households(ctx: BlockContext, notes: list[str]) -> tuple[dict, dict]:
    keys = _hh_keys(ctx, notes)
    hh_e = ctx.block_entries("households")
    c4b: dict[str, dict[str, Q]] = {}
    for comp in ("fisim_deposits", "fisim_loans"):
        df = hh_e.filter((pl.col("ref") == "C4b") & (pl.col("component") == comp) & (pl.col("row") == "C_FINS"))
        c4b[comp] = _group_levels(df.rename({"col": "household_group"}), f"households C4b {comp}")
    return keys, c4b


def read_factors(ctx: BlockContext) -> tuple[dict, dict, dict, Q | None]:
    fe = ctx.block_entries("factors")
    wage_regular = _group_levels(
        fe.filter((pl.col("ref") == "F1a") & (pl.col("col") == "F_LREG")).rename({"row": "household_group"}),
        "factors F1a F_LREG",
    )
    fik = ctx.satellite("factors", "factor_income_keys")
    pub = fik.filter(pl.col("key") == "public_sector_wage_key") if "key" in fik.columns else fik.clear()
    if "measure" in pub.columns:
        pub = pub.filter(pl.col("measure") == "level")
    if pub.height == 0:
        raise SamError("fincorp: factors factor_income_keys has no key 'public_sector_wage_key' (XR-10 item 8)")
    wage_public = _group_levels(pub, "factors public_sector_wage_key")
    gos = fe.filter((pl.col("col") == "F_GOSC") & pl.col("row").is_in(["E_NFPU", "E_NFPR"]))
    nfc_gos: dict[str, Q] = {}
    for r in gos.iter_rows(named=True):
        nfc_gos[r["row"]] = nfc_gos.get(r["row"], Q(0.0)) + _q(r["value"], r["prov_id"])
    if set(nfc_gos) != {"E_NFPU", "E_NFPR"}:
        raise SamError(f"fincorp: factors F4 GOS for E_NFPU/E_NFPR not found (have {sorted(nfc_gos)})")
    fc = ctx.block_constraints("factors").filter(pl.col("constraint_id").str.contains("fc_gos"))
    factors_fc_gos = _q(fc["target"][0], fc["prov_id"][0]) if fc.height == 1 else None
    return wage_regular, wage_public, nfc_gos, factors_fc_gos


def read_government(ctx: BlockContext) -> tuple[Q, dict, dict]:
    ge = ctx.block_entries("government")
    r6df = ge.filter((pl.col("ref") == "R6") & (pl.col("row") == "G_CEN") & (pl.col("col") == "E_RBI"))
    if r6df.height == 0:
        raise SamError("fincorp: government has no R6 entry G_CEN <- E_RBI")
    r6 = Q(0.0)
    for r in r6df.iter_rows(named=True):
        r6 = r6 + _q(r["value"], r["prov_id"])
    r7: dict[tuple[str, str], Q] = {}
    for r in ge.filter(pl.col("ref") == "R7").iter_rows(named=True):
        k = (r["row"], r["col"])
        r7[k] = r7.get(k, Q(0.0)) + _q(r["value"], r["prov_id"])
    if not r7:
        raise SamError("fincorp: government has no R7 entries")
    r7x: dict[tuple[str, str], Q] = {}
    for r in ge.filter(pl.col("ref") == "R7x").iter_rows(named=True):
        k = (r["row"], r["col"])
        r7x[k] = r7x.get(k, Q(0.0)) + _q(r["value"], r["prov_id"])
    return r6, r7, r7x


def read_row(ctx: BlockContext) -> list[dict]:
    re_ = ctx.block_entries("rest_of_world").filter(pl.col("ref").is_in(["R13", "R14", "R14a"]))
    row = [
        dict(row=r["row"], col=r["col"], ref=r["ref"], component=r["component"], q=_q(r["value"], r["prov_id"]))
        for r in re_.iter_rows(named=True)
    ]
    if not row:
        raise SamError("fincorp: rest_of_world has no R13/R14 entries")
    check_row_components(row)
    return row


def check_row_components(row: list[dict]) -> None:
    """Fail loudly when rest_of_world's R13/R14/R14a components differ from those fincorp reads by name."""
    have = {(e["ref"], e["component"]) for e in row}
    unknown = sorted(k for k in have if k[1] not in ROW_KNOWN.get(k[0], ()))
    missing = [k for k in ROW_REQUIRED if k not in have]
    if unknown or missing:
        raise SamError(
            "fincorp: rest_of_world's R13/R14/R14a components changed (review deps.py ROW_* and the sums that "
            f"use them): unknown {unknown}, missing {missing}"
        )


def read_production(ctx: BlockContext) -> dict[str, Q]:
    pc = ctx.block_constraints("production").filter(
        pl.col("constraint_id").is_in(["os_mi_cfc.a_fins", "os_mi_cfc.a_insr"])
    )
    return {r["constraint_id"].split(".")[1].upper(): _q(r["target"], r["prov_id"]) for r in pc.iter_rows(named=True)}


def read_deps(ctx: BlockContext) -> Deps:
    notes: list[str] = []
    keys, c4b = read_households(ctx, notes)
    wage_regular, wage_public, nfc_gos, factors_fc_gos = read_factors(ctx)
    r6, r7, r7x = read_government(ctx)
    return Deps(
        keys,
        c4b,
        wage_regular,
        wage_public,
        nfc_gos,
        r6,
        r7,
        read_row(ctx),
        factors_fc_gos,
        read_production(ctx),
        notes,
        r7x,
    )
