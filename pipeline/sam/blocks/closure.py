"""Closure block: household saving by group (K4a), the X_DISC <- household allocation (D1), and the
pre-balancing diagnostics of DESIGN_BRIEF s.5.4. Plan: docs/phase2/plans/closure.md (its s.8 cross-plan
review and DECISIONS D2-1..D2-18 override the plan body).

Reads
- The validated outputs of all eight other blocks (production, households, factors, taxes, government,
  fincorp, rest_of_world, capital_financial): every entry, every constraint, and households' `hh_keys`
  satellite (`pop_persons` levels, for per-capita saving and the population D1 sensitivity).
- Clean data, NAS 2026 (vintage 2026-08-31, Final for 2023-24, base 2022-23; `vintage="latest"`, an explicit
  choice: every series below has one vintage today): mospi_nas_2026_s1_9 (household, NFC, FC, GG saving),
  mospi_nas_2026_s1_14 (institutional GDI, FCE, saving), mospi_nas_2026_s1_1 (GNDI, PFCE, GFCE, saving,
  product taxes and subsidies), mospi_nas_2026_derived_residuals (published household residual D1, S-I
  errors D3, CE receivable), mospi_nas_2026_s6_1 (RoW property income and transfers, NAS CIF),
  mospi_nas_2026_s7_1a/b/c and mospi_nas_2026_s8_15_1 (sector operating surplus and CFC, for the
  required-flow table); io_tables_sut_supply / io_tables_sut_use (SUT CIF adjustment, valuables total);
  io_tables_ifpri_2223_datapaper (IFPRI 2022/23 saving rates: plausibility only, never a constraint).

Writes
- K4a (10 entries, K_HH <- H_g, free, low, estimated): each group's saving as the pure residual of its current
  account (gross income - every outlay other than saving - its D1 share): option A of the plan (s.5 C7).
  The NAS total (s1_9 household saving) is a constraint (`k4.hh_saving_total`, tol Rs 0.5 crore); the prior
  sum misses it by Z, the headline finding (it is not pre-allocated: option B is published in `hh_saving`).
- D1 (10 entries, X_DISC <- H_g, fixed, estimated): DECISIONS D2-3: the total is D2 + D3 + D4 exactly as the
  other blocks wrote them (so the pinned X_DISC account closes), split pro rata to each group's prior gross
  income (gap map D1), rounding remainder on the largest group. The published household residual is a
  +-Rs 1 crore band constraint (`d1.published_total`), all of whose members are fixed (documentation; the
  balancer skips it) and the build fails if the written total is further than Rs 1 crore from it.
- Satellites: `hh_saving` (group accounts, saving rates, option B, D1 sensitivities, IFPRI comparison),
  `prior_imbalance` (s.5.4: each account's prior row and column totals and imbalance), `constraint_gaps`
  (every declared constraint's prior sum against its band), `institution_gaps` (delivered net distributive
  flows by flow class against what NAS totals require), `xdisc_identity` (D1 vs D2 + D3 + D4). Satellite rows
  carry the status of what they are computed from (STATUS_RULE, verification V-CLO-3): 'estimated' where an
  estimated entry or input enters, 'derived' for arithmetic on official/derived numbers and for counts,
  'official' only for an unchanged copy of one published figure; one provenance record per status.

Fails loudly (SamError) on: a household entry with both row and column in H_* (intra-household flows are
memo only); a household-touching ref outside the plan's whitelist (s.2.1 step 2, s.8 item 2), e.g. R9, R3a,
R8 or T3 in an H_* cell (double counting, CROSS_REVIEW XR-11); a non-finite value; a written D1 total more
than Rs 1 crore from the published residual; a group whose residual saving is smaller than Rs 1 crore in
absolute value (z >= 0 would lock an unstable sign, plan s.6 R6); a lost entry (the global prior identity).
Warns (and docs/phase2/issues/closure.md explains) on: a household ref present for some groups only (R12a
is expected on H_U4/H_U5 only); an implausible group saving rate; the K4 prior-sum check (it fails by Z).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Any

import polars as pl

from pipeline.sam import spec
from pipeline.sam.accounts import Accounts
from pipeline.sam.framework import BlockContext, BlockResult, SamError, Satellite, constraint, entry

BLOCK = "closure"
REFS = ["K4a", "D1"]
DEPENDS = ["production", "households", "factors", "taxes", "government", "fincorp", "rest_of_world",
           "capital_financial"]  # fmt: skip

VINTAGE = "latest"  # an explicit choice: every NAS / SUT series read here carries one vintage (31 Aug 2026)
NAS19, NAS114, NAS11 = "mospi_nas_2026_s1_9", "mospi_nas_2026_s1_14", "mospi_nas_2026_s1_1"
NASRES, NAS61 = "mospi_nas_2026_derived_residuals", "mospi_nas_2026_s6_1"
SUPPLY, USE = "io_tables_sut_supply", "io_tables_sut_use"
IFPRI = "io_tables_ifpri_2223_datapaper"
# source_id of records whose inputs span several sources: the NAS totals every closure number is tied to
SRC = "mospi_nas_2026_publication"

K4_TOL = 0.5  # Rs crore: K4 is published to 6 decimals; 1.9 = 1.14 = 5.3 exactly
D1_BAND = 1.0  # Rs crore: DECISIONS D2-3, the written D1 total vs the published household residual
MIN_ABS_SAVING = 1.0  # Rs crore: a smaller residual would be absent or sign-unstable (plan s.6 R6)
PLAUSIBLE_RATE = (-25.0, 50.0)  # % of gross income: outside this a group's saving is a finding (plan s.2.1 step 8)
GLOBAL_IDENTITY_TOL = 1e-3  # Rs crore: sum of all account imbalances (an entry lost if larger)

# Plan s.2.1 step 2 and s.8 item 2: the only refs that may touch H_* (at group level).
RESOURCE_REFS = ("F1a", "F2", "F3a", "F3b", "F3c", "R8a", "R9a", "R9c", "R9d", "R10", "R11a", "R17")
USE_REFS = ("C1a", "C4a", "C4b", "C4d", "T3a", "R9b", "R16", "R12a", "R17", "R5", "R7x")
CONSUMPTION_REFS = ("C1a", "C4a", "C4b", "C4d")
PARTIAL_GROUPS_OK = ("R12a",)  # rest_of_world plan: outward transfers on H_U4 and H_U5 only
# Where a household part must be written instead (the message of the loud failure)
MISFILED = {
    "R9": "R9a (XR-11)", "R3": "R8a", "R3a": "R8a (CROSS_REVIEW 2: H <- G interest is fincorp R8a)",
    "R4": "R8a", "R8": "R8a", "T3": "T3a", "C1": "C1a", "C4c": "nothing (NPISH memo only)",
    "R11": "R11a", "R12": "R12a", "F1": "F1a", "F3": "F3a/F3b/F3c", "K4": "K4a (closure)",
}  # fmt: skip

# Flow classes of the distributive account (plan s.2.3 item 3); G <- T_PIT/T_CIT are current taxes too.
FLOW_CLASSES = {
    "property_income": ("R3", "R3a", "R3b", "R4", "R5", "R6", "R7", "R7x", "R8", "R8a", "R9c", "R13", "R14", "R14a"),
    "current_taxes": ("T3", "T3a", "T4", "T4a"),
    "social": ("R9", "R9a", "R9b", "R9d"),
    "other_transfers": ("R1", "R2", "T2b", "R10", "R11", "R11a", "R12", "R12a", "R15", "R16", "R17", "R18"),
}  # fmt: skip
INCOME_TAX_ACCOUNTS = ("T_PIT", "T_CIT")
CLASS_ORDER = ("factor_income", "taxes_on_production_imports", "property_income", "current_taxes", "social",
               "other_transfers", "unclassified", "final_consumption", "saving", "discrepancy")  # fmt: skip
DISTRIBUTIVE = ("property_income", "current_taxes", "social", "other_transfers", "unclassified")
# Plan table 2.4-C: the one published NAS total each institution's requirement starts from
NAS_TOTALS = {
    "HH": (NAS114, "s1_14.households_npish.gross_disposable_income.current"),
    "E_NFPU": (NAS19, "s1_9.public_non_financial_corporations.current"),
    "E_NFPR": (NAS19, "s1_9.private_non_financial_corporations.current"),
    "FC": (NAS19, "s1_9.financial_corporations.current"),
    "GG": (NAS114, "s1_14.gg.gross_disposable_income.current"),
}  # fmt: skip
# Status of a diagnostic satellite row (verification V-CLO-3), appended to the method of each diagnostic record
STATUS_RULE = (
    " Status by row, one record per status citing the prov_ids its rows are computed from: 'estimated' where any "
    "entry, constraint target or clean input the row adds up is estimated (even where a total happens to match a "
    "published figure); 'derived' where all of them are official or derived, and for counts of entries (they "
    "depend on which entries exist, not on their values); 'official' only for a row that copies one published "
    "figure or an official constraint target unchanged."
)


# =============================================================================================
# build
# =============================================================================================


def build(ctx: BlockContext) -> BlockResult:
    acc = ctx.accounts
    hh = acc.in_group("HH")
    dep = pl.concat([ctx.block_entries(b) for b in DEPENDS], how="vertical").sort(list(spec.ENTRY_KEY))
    ctx.log(f"read {dep.height} entries of {len(DEPENDS)} blocks")

    problems, partial = check_household_entries(dep, hh)
    if problems:
        raise SamError("household entries break the closure contract (plan s.2.1 step 2):\n  " + "\n  ".join(problems))
    for p in partial:
        ctx.warn(p)

    # --- D1: total = D2 + D3 + D4 as written (DECISIONS D2-3) ------------------------------------------
    disc = dep.filter(pl.col("col") == "X_DISC")
    d_by_ref = {r: float(disc.filter(pl.col("ref") == r)["value"].sum()) for r in ("D2", "D3", "D4")}
    other = disc.filter(~pl.col("ref").is_in(["D2", "D3", "D4"]))
    if other.height:
        raise SamError(f"X_DISC column holds refs other than D2/D3/D4: {sorted(set(other['ref']))}")
    d1_tot = d_by_ref["D2"] + d_by_ref["D3"] + d_by_ref["D4"]
    d1_pub, d1_pub_pid = ctx.value(NASRES, "derived.household_residual.current", vintage=VINTAGE)
    if abs(d1_tot - d1_pub) > D1_BAND:
        raise SamError(
            f"X_DISC identity: D2 + D3 + D4 as written = {d1_tot:,.6f} is {d1_tot - d1_pub:+,.6f} crore from the "
            f"published household residual {d1_pub:,.6f} (band +-{D1_BAND}; DECISIONS D2-3)"
        )
    disc_pids = sorted(set(disc["prov_id"].to_list()))
    d1_total_pid = ctx.prov(
        ref="D1",
        status="derived",
        inputs=[*disc_pids, d1_pub_pid],
        source_id=SRC,
        method=(
            "Gap map D1, DECISIONS D2-3: the D1 total written = sum of the X_DISC column as the other blocks wrote it "
            "(D2 rest_of_world R_ROW <- X_DISC, SUT CIF; D3 capital_financial K_* <- X_DISC, NAS S-I errors; D4 "
            "production C_* <- X_DISC, 0), so the pinned X_DISC account closes exactly. The published household "
            "residual (NAS 2026 derived: St 1.14 household GDI - FCE - gross saving) must lie within +-Rs 1 crore; "
            "the difference is rounding in the published statements and is logged."
        ),
    )
    inc = group_sums(dep, hh, side="row")
    out = group_sums(dep, hh, side="col")
    d1 = split_pro_rata(d1_tot, inc)
    hh_pids = {g: sorted(set(dep.filter((pl.col("row") == g) | (pl.col("col") == g))["prov_id"].to_list())) for g in hh}
    # V-CLO-4: the split key is prior gross income, so the record cites the income-side entries only
    income_pids = sorted(set(dep.filter(pl.col("row").is_in(hh))["prov_id"].to_list()))
    d1_pid = ctx.prov(
        ref="D1",
        status="estimated",
        inputs=[d1_total_pid, *income_pids],
        source_id=SRC,
        method=(
            "Gap map D1 allocation (ESTIMATED): the D1 total (D2 + D3 + D4 as written) split over the 10 household "
            "groups in proportion to each group's prior gross income (the sum of all entries with row = H_g, i.e. "
            "factor income, property income and current transfers received), rounded to 6 decimals with the "
            "remainder on the group with the largest income. Pinned (fixed): X_DISC is never balanced. Neutral "
            "between 'income overstated' and 'consumption or saving understated' (plan s.5 C6); PFCE and "
            "population splits are published in hh_saving as a sensitivity."
        ),
    )

    # --- K4a: pure residual (option A) ------------------------------------------------------------------
    k4_nas, k4_pid = ctx.value(NAS19, "s1_9.household_sector.current", vintage=VINTAGE)
    k4a = {g: inc[g] - out[g] - d1[g] for g in hh}
    small = {g: v for g, v in k4a.items() if abs(v) < MIN_ABS_SAVING}
    if small:
        raise SamError(
            f"K4a residual smaller than Rs {MIN_ABS_SAVING} crore for {small}: the entry would be absent or its sign "
            "unstable under balancing (plan s.6 R6); fix the income or outlay keys upstream"
        )
    k4a_pid = {
        g: ctx.prov(
            ref="K4a",
            status="estimated",
            inputs=[*hh_pids[g], d1_pid, k4_pid],
            source_id=SRC,
            method=(
                f"Gap map K4a, {g}: residual of the group's current account (option A, plan s.5 C7) = gross income "
                "(all entries with row = the group) - consumption, current taxes, current transfers and property "
                "income paid (all entries with column = the group, other than K4a and D1) - its D1 share. Not "
                "rescaled: the 10 residuals sum to NAS 2026 St 1.9 household saving only after balancing, which "
                "enforces the K4 constraint (closure `k4.hh_saving_total`); the gap Z is reported in hh_saving."
            ),
        )
        for g in hh
    }
    entries = [entry("X_DISC", g, "D1", d1[g], prov_id=d1_pid, status="estimated", role="fixed") for g in hh]
    entries += [
        entry("K_HH", g, "K4a", k4a[g], prov_id=k4a_pid[g], status="estimated", role="free", confidence="low")
        for g in hh
    ]
    z = sum(k4a.values()) - k4_nas
    ctx.log(f"K4a prior sum {sum(k4a.values()):,.2f} vs NAS {k4_nas:,.2f}: Z = {z:+,.2f} crore")

    # --- constraints --------------------------------------------------------------------------------
    k4_con_pid = ctx.prov(
        ref="K4",
        status="official",
        inputs=[k4_pid],
        method="Gap map K4: NAS 2026 Statement 1.9 item 1.4 gross saving of households incl. NPISH (= St 1.14 "
        "households gross saving = St 5.3 household saving), as published: the target of sum K_HH <- H_* (K4a).",
    )
    d1_con_pid = ctx.prov(
        ref="D1",
        status="derived",
        inputs=[d1_pub_pid],
        method="Gap map D1: the published household residual (NAS 2026 derived series: St 1.14 household GDI - "
        "FCE - gross saving) as the target of the written D1 total, with a +-Rs 1 crore band (DECISIONS D2-3).",
    )
    cons = [
        constraint("k4.hh_saving_total", "K4", ["K_HH"], hh, k4_nas, prov_id=k4_con_pid, tol_abs=K4_TOL,
                   refs=["K4a"], description="NAS 2026 St 1.9 household gross saving = sum of K4a over the 10 groups "
                   "(same selection and target as capital_financial's K4 constraint)"),
        constraint("d1.published_total", "D1", ["X_DISC"], hh, d1_pub, prov_id=d1_con_pid, tol_abs=D1_BAND,
                   kind="band", refs=["D1"], description="Published NAS household residual; the written D1 (= D2 + "
                   "D3 + D4 as written, DECISIONS D2-3) lies within +-Rs 1 crore (all members fixed: documentation)"),
    ]  # fmt: skip

    # --- the assembled prior: dependencies + own entries --------------------------------------------
    own = pl.DataFrame(entries, schema=spec.ENTRY_DTYPES, orient="row").with_columns(pl.lit(BLOCK).alias("block"))
    prior = pl.concat([dep, own.select(dep.columns)], how="vertical").sort(list(spec.ENTRY_KEY))
    imb = account_imbalances(prior, acc)
    total_imb = float(imb["imbalance"].sum())
    if abs(total_imb) > GLOBAL_IDENTITY_TOL:
        raise SamError(f"sum of all prior account imbalances is {total_imb:+.6f} crore (must be 0: an entry was lost)")
    dep_cons = pl.concat([ctx.block_constraints(b) for b in DEPENDS], how="vertical")
    own_cons = constraints_frame(cons, BLOCK, acc)
    all_cons = pl.concat([dep_cons.select(own_cons.columns), own_cons], how="vertical").sort(["block", "constraint_id"])
    gaps = constraint_gaps(prior, all_cons)
    flows = institution_flows(prior, acc)
    uncl = flows.filter((pl.col("flow_class") == "unclassified") & (pl.col("net").abs() > spec.BALANCE_TOL))
    if uncl.height:
        ctx.warn(
            "institution flows with a ref outside the plan's flow classes (institution_gaps 'unclassified'): "
            + ", ".join(f"{i} {v:+,.2f}" for i, v in uncl.select("institution", "net").rows())
        )

    imb_rows = imbalance_rows(imb, account_lineage(prior, acc.codes))
    diag_method = (
        "DESIGN_BRIEF s.5.4 pre-balancing diagnostics: for every account of accounts.yaml, the prior row total "
        "(receipts), column total (payments) and imbalance (row - column, Rs crore and % of the larger total) over "
        "all nine blocks' entries (closure's included), the number of non-fixed entries in its row and column, and "
        "its rank by absolute imbalance. Large imbalances are findings to trace to a source disagreement, not things "
        "to balance away."
    )
    cons_meta = constraint_targets(ctx, all_cons)
    cons_method = (
        "Pre-balancing constraint gaps: for every constraint every block declared (not merged), the sum of the "
        "prior entries it selects (row in rows, col in cols, ref in refs and component in components when given) "
        "against its band target +- max(tol_abs, tol_rel*|target|) (min: lower bound only; max: upper only); "
        "outside_band marks a total the prior misses before the solver moves anything. The target row takes the "
        "status of the declaring block's constraint record."
    )
    req, req_pids = required_flows(ctx)
    tot_pids = {k: _v(ctx, ds, sid)[1] for k, (ds, sid) in NAS_TOTALS.items()}
    inst_method = (
        "Institution gaps (plan s.2.3 item 3, table 2.4-C): per institution (each H_g, all households, "
        "E_NFPU, E_NFPR, each FC and all FC, G_CEN, G_STA and GG) the prior's receipts and payments with accounts "
        "outside the set by class: factor income (from FAC), taxes on production and imports (GG from T_* other "
        "than T_PIT/T_CIT), property income, current taxes (incl. GG <- T_PIT/T_CIT), social benefits and "
        "contributions, other current transfers (by gap-map ref), final consumption, saving and the discrepancy. "
        "Delivered net distributive flows are compared with the amount NAS 2026 totals require: households GDI - "
        "CE receivable - gross OS/MI (St 1.14, derived residuals, 7.1C); NFC and FC saving - gross operating "
        "surplus (St 1.9; 7.1A/7.1B less financial rows and 8.15.1); GG GDI - GOS - net taxes on production and "
        "imports (St 1.14, 8.15.1, 1.1, 7.1A/B/C). Their sum equals NAS 6.1's net property income and transfers "
        "from the rest of the world. nas_total copies one published figure (St 1.14 GDI or St 1.9 saving)."
    )
    xd_pid = ctx.prov(
        ref="D1",
        status="derived",
        inputs=[d1_total_pid, d1_pub_pid, *disc_pids, *xdisc_reference_pids(ctx)],
        source_id=SRC,
        method="X_DISC identity (plan s.2.3 item 4): the published household residual D1, the written D2, D3, D4 "
        "and D1 totals and the residual D1_published - (D2 + D3 + D4) as written; with the SUT and NAS 6.1 CIF "
        "adjustments and the NAS S-I errors as references. 'derived' although capital_financial's split of D3 over "
        "the K_* accounts is estimated: the split keeps the published S-I errors total, which is all this table "
        "uses (check d3.written_vs_nas).",
    )

    hh_sat, hh_findings = hh_saving_satellite(ctx, prior, hh, inc, out, d1, k4a, k4_nas, d1_tot, k4a_pid, d1_pid,
                                              k4_pid, d1_total_pid)  # fmt: skip
    for f in hh_findings:
        ctx.warn(f)

    sats = {
        "hh_saving": hh_sat,
        "prior_imbalance": Satellite("K4a", _sat(with_records(ctx, imb_rows, ref="K4a", method=diag_method),
                                                 ["account", "group", "measure"]),
                                     "Pre-balancing account imbalances (DESIGN_BRIEF s.5.4)"),
        "constraint_gaps": Satellite("K4a", _sat(with_records(ctx, constraint_gap_rows(gaps, cons_meta), ref="K4a",
                                                              method=cons_method),
                                                 ["constraint_id", "block", "ref", "kind", "outside_band", "measure"]),
                                     "Every declared constraint's prior sum against its band (pre-balancing)"),
        "institution_gaps": Satellite("K4a", _sat(with_records(ctx, institution_rows(flows, req, req_pids, tot_pids),
                                                               ref="K4a", method=inst_method),
                                                  ["institution", "members", "measure"]),
                                      "Delivered vs required net distributive flows by institution (pre-balancing)"),
        "xdisc_identity": Satellite("D1", xdisc_frame(ctx, d_by_ref, d1_tot, d1_pub, xd_pid),
                                    "X_DISC identity: published D1 vs D2 + D3 + D4 as written"),
    }  # fmt: skip

    _checks(ctx, d_by_ref, d1_tot, d1_pub, d1_pub_pid, d1_total_pid, entries, k4a, k4_nas, k4_pid, dep, req)
    _log_diagnostics(ctx, imb, gaps, z)
    return BlockResult(entries=entries, constraints=cons, satellites=sats)


# =============================================================================================
# pure functions (unit-tested on small fixtures in tests/sam/test_sam_closure.py)
# =============================================================================================


def check_household_entries(ent: pl.DataFrame, hh: Sequence[str]) -> tuple[list[str], list[str]]:
    """Plan s.2.1 step 2. Returns (problems that fail the build, warnings). Problems: an intra-household entry;
    a household-touching ref outside the whitelist; a non-finite value. Warnings: a household ref present for
    some groups only (except PARTIAL_GROUPS_OK)."""
    hs = set(hh)
    problems: list[str] = []
    warnings: list[str] = []
    touch = ent.filter(pl.col("row").is_in(hh) | pl.col("col").is_in(hh))
    for r in touch.iter_rows(named=True):
        key = f"{r['row']} <- {r['col']} [{r['ref']}/{r['component']}] (block {r.get('block', '?')})"
        v = r["value"]
        if v is None or not math.isfinite(v):
            problems.append(f"{key}: non-finite value {v!r}")
        if r["row"] in hs and r["col"] in hs:
            problems.append(f"{key}: intra-household flow (memo only, ACCOUNT_STRUCTURE s.11)")
            continue
        side, allowed = ("resource", RESOURCE_REFS) if r["row"] in hs else ("use", USE_REFS)
        if r["ref"] not in allowed:
            hint = f"; write it under {MISFILED[r['ref']]}" if r["ref"] in MISFILED else ""
            problems.append(f"{key}: ref {r['ref']} is not an allowed household {side} ref {list(allowed)}{hint}")
    for side, col in (("resource", "row"), ("use", "col")):
        sub = touch.filter(pl.col(col).is_in(hh))
        for ref, groups in sub.group_by("ref", maintain_order=True).agg(pl.col(col).unique().sort()).sort("ref").rows():
            if ref in PARTIAL_GROUPS_OK or len(groups) == len(hh):
                continue
            missing = [g for g in hh if g not in groups]
            warnings.append(
                f"household {side} ref {ref} has entries for {len(groups)} of {len(hh)} groups (none for "
                f"{', '.join(missing)}): check it is not a household total written on one group"
            )
    return problems, warnings


def group_sums(ent: pl.DataFrame, hh: Sequence[str], *, side: str, exclude_refs: Iterable[str] = ("K4a", "D1")) -> dict:
    """Per household group: the sum of entries with row = g (side='row', gross income) or col = g (side='col',
    outlays), excluding closure's own refs."""
    ex = list(exclude_refs)
    sub = ent.filter(pl.col(side).is_in(hh) & ~pl.col("ref").is_in(ex))
    by = fsum_by(sub, side)
    return {g: float(by.get(g, 0.0)) for g in hh}


def fsum_by(df: pl.DataFrame, key: str, col: str = "value") -> dict[str, float]:
    """Exact per-group sums (math.fsum): a polars group_by sum depends on the thread count in its last bits, which
    made repro builds differ (Wave C, 2026-10-01)."""
    vals: dict[str, list[float]] = {}
    for k, v in zip(df[key].to_list(), df[col].to_list(), strict=True):
        vals.setdefault(k, []).append(v)
    return {k: math.fsum(v) for k, v in vals.items()}


def split_pro_rata(total: float, key: dict[str, float]) -> dict[str, float]:
    """total x key_g / sum(key), rounded to 6 decimals; the remainder goes to the group with the largest key
    (first in key order on a tie) so the parts add to the total exactly (to float precision)."""
    s = sum(key.values())
    if not (s > 0) or any(v < 0 for v in key.values()):
        raise SamError(f"pro-rata key must be non-negative with a positive sum: {key}")
    big = max(key, key=lambda g: (key[g], -list(key).index(g)))
    out = {g: round(total * v / s, 6) for g, v in key.items()}
    out[big] = total - sum(v for g, v in out.items() if g != big)
    return out


def account_imbalances(ent: pl.DataFrame, acc: Accounts) -> pl.DataFrame:
    """One row per account (accounts.yaml order): row_total, col_total, imbalance = row - col, imbalance_pct
    (of the larger absolute total; null when both are 0), n_var_row / n_var_col (non-fixed entries), rank by
    |imbalance| (ties in matrix order)."""
    var = pl.col("role") != "fixed"
    rs, cs = fsum_by(ent, "row"), fsum_by(ent, "col")  # exact sums (repro)
    rt = ent.group_by("row", maintain_order=True).agg(var.sum().cast(pl.Int64).alias("n_var_row"))
    rt = rt.with_columns(pl.col("row").replace_strict(rs, return_dtype=pl.Float64).alias("row_total"))
    ct = ent.group_by("col", maintain_order=True).agg(var.sum().cast(pl.Int64).alias("n_var_col"))
    ct = ct.with_columns(pl.col("col").replace_strict(cs, return_dtype=pl.Float64).alias("col_total"))
    base = pl.DataFrame({"account": acc.codes, "group": [acc.group(c) for c in acc.codes],
                         "_o": list(range(len(acc.codes)))},
                        schema={"account": pl.String(), "group": pl.String(), "_o": pl.Int64()})  # fmt: skip
    df = (
        base.join(rt.rename({"row": "account"}), on="account", how="left", maintain_order="left")
        .join(ct.rename({"col": "account"}), on="account", how="left", maintain_order="left")
        .with_columns(pl.col("row_total", "col_total").fill_null(0.0), pl.col("n_var_row", "n_var_col").fill_null(0))
        .with_columns((pl.col("row_total") - pl.col("col_total")).alias("imbalance"))
    )
    big = pl.max_horizontal(pl.col("row_total").abs(), pl.col("col_total").abs())
    df = df.with_columns(
        pl.when(big > 0).then(100.0 * pl.col("imbalance") / big).otherwise(None).alias("imbalance_pct")
    )
    # rank on |imbalance| rounded to 1e-4 crore (below the 0.01 balance tolerance): the sums carry ~1e-9
    # float noise that depends on the hash seed and thread count, and near-zero accounts would otherwise
    # swap ranks between builds (repro)
    key = pl.col("imbalance").abs().round(4)
    df = df.sort([key, pl.col("_o")], descending=[True, False]).with_row_index("rank", offset=1)
    return df.with_columns(pl.col("rank").cast(pl.Int64)).sort("_o").drop("_o")


def constraints_frame(cons: list[dict[str, Any]], block: str, acc: Accounts) -> pl.DataFrame:
    """Own constraint dicts in the written format (comma-joined lists, accounts.yaml order) + block."""
    order = acc.index
    rows = []
    for c in cons:
        rows.append({**{k: c[k] for k in spec.CONSTRAINT_DTYPES if k not in ("rows", "cols", "refs", "components")},
                     "rows": ",".join(sorted(set(c["rows"]), key=order.__getitem__)),
                     "cols": ",".join(sorted(set(c["cols"]), key=order.__getitem__)),
                     "refs": None if c["refs"] is None else ",".join(sorted(set(c["refs"]))),
                     "components": None if c["components"] is None else ",".join(sorted(set(c["components"]))),
                     "block": block})  # fmt: skip
    return pl.DataFrame(rows, schema={**spec.CONSTRAINT_DTYPES, "block": pl.String()}, orient="row")


def constraint_band(target: float, tol_abs: float, tol_rel: float, kind: str) -> tuple[float, float]:
    tol = max(tol_abs, tol_rel * abs(target))
    lo = -math.inf if kind == "max" else target - tol
    hi = math.inf if kind == "min" else target + tol
    return lo, hi


def constraint_gaps(ent: pl.DataFrame, cons: pl.DataFrame) -> pl.DataFrame:
    """Per declared constraint: prior_sum (the entries it selects), target, lo, hi, gap = prior_sum - target,
    outside = prior_sum outside [lo, hi] (by more than the balance tolerance); entry_status (weakest() of the
    selected entries' statuses) and entry_prov_ids (their sorted prov_ids)."""
    out = []
    for c in cons.iter_rows(named=True):
        sel = pl.col("row").is_in(c["rows"].split(",")) & pl.col("col").is_in(c["cols"].split(","))
        if c["refs"]:
            sel &= pl.col("ref").is_in(c["refs"].split(","))
        if c["components"]:
            sel &= pl.col("component").is_in(c["components"].split(","))
        sub = ent.filter(sel)
        s = float(sub["value"].sum())
        lo, hi = constraint_band(c["target"], c["tol_abs"], c["tol_rel"], c["kind"])
        outside = s < lo - spec.BALANCE_TOL or s > hi + spec.BALANCE_TOL
        out.append({"constraint_id": f"{c['block']}:{c['constraint_id']}", "block": c["block"], "ref": c["ref"],
                    "kind": c["kind"], "n_members": sub.height, "prior_sum": s, "target": c["target"],
                    "lo": lo, "hi": hi, "gap": s - c["target"], "outside": outside,
                    "entry_status": weakest(sub["status"].to_list()),
                    "entry_prov_ids": sorted(set(sub["prov_id"].to_list()))})  # fmt: skip
    schema = {"constraint_id": pl.String(), "block": pl.String(), "ref": pl.String(), "kind": pl.String(),
              "n_members": pl.Int64(), "prior_sum": pl.Float64(), "target": pl.Float64(), "lo": pl.Float64(),
              "hi": pl.Float64(), "gap": pl.Float64(), "outside": pl.Boolean(), "entry_status": pl.String(),
              "entry_prov_ids": pl.List(pl.String())}  # fmt: skip
    return pl.DataFrame(out, schema=schema, orient="row").sort("constraint_id")


def flow_class(ref: str, other_account: str, other_group: str, *, receipt: bool) -> str:
    """Class of an entry seen from an institution: `other_account` is the counterpart (the column of a receipt,
    the row of a payment)."""
    if receipt and other_group == "FAC":
        return "factor_income"
    if receipt and other_group == "TAX":
        return "current_taxes" if other_account in INCOME_TAX_ACCOUNTS else "taxes_on_production_imports"
    if not receipt and other_group == "COM":
        return "final_consumption"
    if not receipt and other_group == "CAP":
        return "saving"
    if not receipt and other_group == "DISC":
        return "discrepancy"
    for cls, refs in FLOW_CLASSES.items():
        if ref in refs:
            return cls
    return "unclassified"


def institution_sets(acc: Accounts) -> dict[str, list[str]]:
    hh, nfc, fc, gov = (acc.in_group(g) for g in ("HH", "NFC", "FC", "GOV"))
    sets: dict[str, list[str]] = {g: [g] for g in hh}
    sets["HH"] = hh
    for a in nfc + fc:
        sets[a] = [a]
    sets["FC"] = fc
    for a in gov:
        sets[a] = [a]
    sets["GG"] = gov
    return sets


def institution_flows(ent: pl.DataFrame, acc: Accounts) -> pl.DataFrame:
    """Per institution set and class: receipts, payments and net (receipts - payments) with accounts outside
    the set, with status (weakest() of the class's entries) and prov_ids (theirs, sorted). Internal flows (both
    ends in the set) cancel and are left out."""
    grp = {c: acc.group(c) for c in acc.codes}
    rows = []
    for name, members in institution_sets(acc).items():
        agg: dict[str, list[float]] = {c: [0.0, 0.0] for c in CLASS_ORDER}
        sts: dict[str, set[str]] = {c: set() for c in CLASS_ORDER}
        pids: dict[str, set[str]] = {c: set() for c in CLASS_ORDER}
        rec = ent.filter(pl.col("row").is_in(members) & ~pl.col("col").is_in(members))
        pay = ent.filter(pl.col("col").is_in(members) & ~pl.col("row").is_in(members))
        for side, frame, other_col in ((0, rec, "col"), (1, pay, "row")):
            for ref, other, v, st, pid in frame.select("ref", other_col, "value", "status", "prov_id").iter_rows():
                c = flow_class(ref, other, grp[other], receipt=side == 0)
                agg[c][side] += v
                sts[c].add(st)
                pids[c].add(pid)
        for c in CLASS_ORDER:
            r, p = agg[c]
            rows.append({"institution": name, "members": ",".join(members), "flow_class": c, "receipts": r,
                         "payments": p, "net": r - p, "status": weakest(sts[c]),
                         "prov_ids": sorted(pids[c])})  # fmt: skip
    schema = {"institution": pl.String(), "members": pl.String(), "flow_class": pl.String(), "receipts": pl.Float64(),
              "payments": pl.Float64(), "net": pl.Float64(), "status": pl.String(),
              "prov_ids": pl.List(pl.String())}  # fmt: skip
    return pl.DataFrame(rows, schema=schema, orient="row")


def weakest(statuses: Iterable[str]) -> str:
    """Status of arithmetic over inputs (STATUS_RULE, verification V-CLO-3): 'estimated' if any input is estimated,
    else 'derived' (arithmetic on official or derived numbers, or an empty sum)."""
    return "estimated" if "estimated" in set(statuses) else "derived"


def account_lineage(ent: pl.DataFrame, codes: Sequence[str]) -> dict[str, dict[str, tuple[str, list[str]]]]:
    """Per account: {'row': (status, prov_ids), 'col': (status, prov_ids)} of the entries in its row / column:
    status = weakest() of their statuses, prov_ids sorted."""
    out: dict[str, dict[str, tuple[str, list[str]]]] = {c: {"row": ("derived", []), "col": ("derived", [])}
                                                        for c in codes}  # fmt: skip
    for side in ("row", "col"):
        agg = ent.group_by(side, maintain_order=True).agg(
            pl.col("status").unique().sort().alias("st"), pl.col("prov_id").unique().sort().alias("pids")
        )
        for acct, st, pids in agg.rows():
            if acct not in out:
                raise SamError(f"entry on an account not in accounts.yaml: {acct}")
            out[acct][side] = (weakest(st), list(pids))
    return out


def constraint_targets(ctx: BlockContext, cons: pl.DataFrame) -> dict[str, tuple[str, str]]:
    """'block:constraint_id' -> (status of the constraint's provenance record, its prov_id)."""
    out = {}
    for blk, cid, pid in cons.select("block", "constraint_id", "prov_id").iter_rows():
        rec = ctx.lookup_prov(pid)
        if rec is None:
            raise SamError(f"constraint {blk}:{cid}: provenance record {pid} does not resolve")
        out[f"{blk}:{cid}"] = (str(rec["status"]), pid)
    return out


def _main_source(ctx: BlockContext, inputs: Sequence[str]) -> str | None:
    """source_id for a record over `inputs`: None (the framework takes the inputs' one source) when they share
    one; else SRC when it is among them; else the source most of the inputs come from (ties: first by name)."""
    srcs = [str(r["source_id"]) for i in inputs if (r := ctx.lookup_prov(i)) is not None and r.get("source_id")]
    distinct = sorted(set(srcs))
    if len(distinct) <= 1:
        return None
    if SRC in distinct:
        return SRC
    return min(distinct, key=lambda s: (-srcs.count(s), s))


def with_records(ctx: BlockContext, rows: list[dict[str, Any]], *, ref: str, method: str) -> list[dict[str, Any]]:
    """Diagnostic rows carry `status` and `_inputs` (the prov_ids the row's number is computed from). Registers one
    record per status (method + STATUS_RULE; inputs = the union of its rows' inputs) and sets each row's prov_id."""
    by: dict[str, set[str]] = {}
    for r in rows:
        by.setdefault(r["status"], set()).update(r["_inputs"])
    pid = {}
    for st in sorted(by):
        ins = sorted(by[st])
        src = _main_source(ctx, ins)
        pid[st] = ctx.prov(ref=ref, status=st, inputs=ins, source_id=src, method=method + STATUS_RULE)
    return [{**{k: v for k, v in r.items() if k != "_inputs"}, "prov_id": pid[r["status"]]} for r in rows]


# =============================================================================================
# clean-data readers
# =============================================================================================


def _v(ctx: BlockContext, ds: str, sid: str) -> tuple[float, str]:
    return ctx.value(ds, sid, vintage=VINTAGE)


def required_flows(ctx: BlockContext) -> tuple[dict[str, dict[str, float]], list[str]]:
    """Plan table 2.4-C, recomputed from clean NAS 2026: the net distributive flows (property income, current
    taxes on income, social contributions and benefits, other current transfers; gross basis) that each
    institution must receive (+) or pay (-) to reach its NAS totals. Returns ({set: {item: value}}, prov_ids)."""
    pids: set[str] = set()

    def v(ds: str, sid: str) -> float:
        x, p = _v(ctx, ds, sid)
        pids.add(p)
        return x

    a, b, c, g = "mospi_nas_2026_s7_1a", "mospi_nas_2026_s7_1b", "mospi_nas_2026_s7_1c", "mospi_nas_2026_s8_15_1"
    gg_gos = v(g, "s8_15_1.total.os.current") + v(g, "s8_15_1.total.cfc.current")
    fc_pub_gos = v(a, "s7_1a.financial.os.current") + v(a, "s7_1a.financial.cfc.current")
    fc_pvt_gos = v(b, "s7_1b.financial.os.current") + v(b, "s7_1b.financial.cfc.current")
    nfc_pub_gos = v(a, "s7_1a.total.os.current") + v(a, "s7_1a.total.cfc.current") - fc_pub_gos - gg_gos
    nfc_pvt_gos = v(b, "s7_1b.total.os.current") + v(b, "s7_1b.total.cfc.current") - fc_pvt_gos
    hh_osmi = v(c, "s7_1c.total.os_mi.current") + v(c, "s7_1c.total.cfc.current")
    ntpi = (v(NAS11, "s1_1.taxes_on_products.current") - v(NAS11, "s1_1.subsidies_on_products.current")
            + v(a, "s7_1a.total.net_production_taxes.current") + v(b, "s7_1b.total.net_production_taxes.current")
            + v(c, "s7_1c.total.net_production_taxes.current"))  # fmt: skip
    tot = {k: v(ds, sid) for k, (ds, sid) in NAS_TOTALS.items()}  # households and GG: GDI; NFC and FC: saving
    ce = v(NASRES, "derived.ce_receivable_by_residents.current")
    req = {
        "HH": {"nas_total": tot["HH"], "primary_income": ce + hh_osmi, "required_net": tot["HH"] - ce - hh_osmi},
        "E_NFPU": {"nas_total": tot["E_NFPU"], "primary_income": nfc_pub_gos},
        "E_NFPR": {"nas_total": tot["E_NFPR"], "primary_income": nfc_pvt_gos},
        "FC": {"nas_total": tot["FC"], "primary_income": fc_pub_gos + fc_pvt_gos},
        "GG": {"nas_total": tot["GG"], "primary_income": gg_gos + ntpi, "required_net": tot["GG"] - gg_gos - ntpi},
    }  # fmt: skip
    for k in ("E_NFPU", "E_NFPR", "FC"):  # GDI = saving (no final consumption)
        req[k]["required_net"] = req[k]["nas_total"] - req[k]["primary_income"]
    row = (v(NAS61, "s6_1.property_and_entrepreneurial_income_from_rest_of_the_world.current")
           - v(NAS61, "s6_1.property_and_entrepreneurial_income_to_the_rest_of_the_world.current")
           + v(NAS61, "s6_1.other_current_transfers_to_resident_sectors_other_than_gener.current")
           - v(NAS61, "s6_1.other_current_transfers_by_resident_sectors_other_than_gener.current"))  # fmt: skip
    req["DOMESTIC"] = {"required_net": sum(req[k]["required_net"] for k in ("HH", "E_NFPU", "E_NFPR", "FC", "GG"))}
    req["ROW_NET"] = {"required_net": row}
    return req, sorted(pids)


def xdisc_reference_pids(ctx: BlockContext) -> list[str]:
    return [
        _v(ctx, SUPPLY, "supply.cif_adj.cif.current")[1],
        _v(ctx, NAS61, "s6_1.adjustment_for_cif_in_import_of_services.current")[1],
        _v(ctx, NASRES, "derived.si_errors_omissions.current")[1],
    ]


# =============================================================================================
# satellites
# =============================================================================================

SAT_SCHEMA_BASE = {"series_id": pl.String(), "value": pl.Float64(), "unit": pl.String(), "status": pl.String(),
                   "prov_id": pl.String()}  # fmt: skip


def _sat(rows: list[dict[str, Any]], dims: Sequence[str]) -> pl.DataFrame:
    schema = {"series_id": pl.String(), **{d: pl.String() for d in dims}}
    schema.update({k: v for k, v in SAT_SCHEMA_BASE.items() if k != "series_id"})
    df = pl.DataFrame(rows, schema=schema, orient="row")
    bad = df.filter(pl.col("value").is_null() | ~pl.col("value").is_finite())
    if bad.height:
        raise SamError(f"satellite rows with non-finite values: {bad['series_id'].to_list()[:10]}")
    return df.sort("series_id")


def _lin(*parts: tuple[str, Sequence[str]]) -> tuple[str, list[str]]:
    """(status, prov_ids) of a number computed from several (status, prov_ids) parts: weakest(), union."""
    return weakest(s for s, _ in parts), sorted({p for _, ps in parts for p in ps})


def imbalance_rows(imb: pl.DataFrame, lin: dict[str, dict[str, tuple[str, list[str]]]]) -> list[dict[str, Any]]:
    """prior_imbalance rows with `status` and `_inputs` (STATUS_RULE): row_total from the account's row entries,
    col_total from its column, imbalance and imbalance_pct from both; the counts n_var_row / n_var_col 'derived';
    rank (it orders every account's imbalance) from all entries."""
    rank = _lin(*(lin[a][s] for a in lin for s in ("row", "col")))
    rows = []
    for r in imb.iter_rows(named=True):
        a = r["account"]
        row, col = lin[a]["row"], lin[a]["col"]
        both = _lin(row, col)
        how = {"row_total": ("INR_crore", row), "col_total": ("INR_crore", col), "imbalance": ("INR_crore", both),
               "imbalance_pct": ("percent", both), "n_var_row": ("count", ("derived", row[1])),
               "n_var_col": ("count", ("derived", col[1])), "rank": ("count", rank)}  # fmt: skip
        for m, (unit, (st, ins)) in how.items():
            if r[m] is None:
                continue  # imbalance_pct of an empty account: undefined, not 0
            rows.append({"series_id": f"{a.lower()}.{m}", "account": a, "group": r["group"], "measure": m,
                         "value": float(r[m]), "unit": unit, "status": st, "_inputs": ins})  # fmt: skip
    return rows


def constraint_gap_rows(gaps: pl.DataFrame, targets: dict[str, tuple[str, str]]) -> list[dict[str, Any]]:
    """constraint_gaps rows with `status` and `_inputs` (STATUS_RULE): prior_sum from the selected entries; target
    with the status of the constraint's record (official stays official: a copy); lo / hi (target +- tolerance)
    and gap by weakest(); n_members 'derived'."""
    rows = []
    for r in gaps.iter_rows(named=True):
        t_status, t_pid = targets[r["constraint_id"]]
        tgt = (t_status, [t_pid])
        ent = (r["entry_status"], list(r["entry_prov_ids"]))
        how = {"prior_sum": ("INR_crore", ent), "target": ("INR_crore", tgt), "lo": ("INR_crore", _lin(tgt)),
               "hi": ("INR_crore", _lin(tgt)), "gap": ("INR_crore", _lin(ent, tgt)),
               "n_members": ("count", ("derived", ent[1] or [t_pid]))}  # fmt: skip
        base = {"constraint_id": r["constraint_id"], "block": r["block"], "ref": r["ref"], "kind": r["kind"],
                "outside_band": "yes" if r["outside"] else "no"}  # fmt: skip
        for m, (unit, (st, ins)) in how.items():
            x = float(r[m])
            if not math.isfinite(x):
                continue  # the open side of a min/max constraint
            rows.append({**base, "series_id": f"{r['constraint_id']}.{m}", "measure": m, "value": x, "unit": unit,
                         "status": st, "_inputs": ins})  # fmt: skip
    return rows


def institution_rows(
    flows: pl.DataFrame, req: dict[str, dict[str, float]], req_pids: Sequence[str], tot_pids: dict[str, str]
) -> list[dict[str, Any]]:
    """institution_gaps rows with `status` and `_inputs` (STATUS_RULE): flow-class nets, delivered_net and imbalance
    from the entries they add up; required_net and nas_primary_income 'derived' from NAS (table 2.4-C); nas_total
    'official' (one published figure); gap and primary_income_gap by weakest() of both sides."""
    rows = []
    nas = ("derived", list(req_pids))

    def add(inst: str, measure: str, value: float, members: str, lin: tuple[str, Sequence[str]]) -> None:
        rows.append({"series_id": f"{inst.lower()}.{measure}", "institution": inst, "members": members,
                     "measure": measure, "value": value, "unit": "INR_crore", "status": lin[0],
                     "_inputs": list(lin[1])})  # fmt: skip

    by: dict[str, tuple[str, dict[str, dict[str, Any]]]] = {}
    for r in flows.iter_rows(named=True):
        by.setdefault(r["institution"], (r["members"], {}))[1][r["flow_class"]] = r
    delivered_lin = {}
    for inst, (members, cls) in by.items():
        lin = {c: (cls[c]["status"], cls[c]["prov_ids"]) for c in CLASS_ORDER}
        for c in CLASS_ORDER:
            add(inst, f"{c}.net", cls[c]["net"], members, lin[c])
        delivered = sum(cls[c]["net"] for c in DISTRIBUTIVE)
        delivered_lin[inst] = _lin(*(lin[c] for c in DISTRIBUTIVE))
        add(inst, "delivered_net", delivered, members, delivered_lin[inst])
        imbalance = sum(cls[c]["net"] for c in CLASS_ORDER)
        add(inst, "imbalance", imbalance, members, _lin(*lin.values()))
        if inst in req:
            q = req[inst]
            add(inst, "required_net", q["required_net"], members, nas)
            add(inst, "gap", delivered - q["required_net"], members, _lin(delivered_lin[inst], nas))
            add(inst, "nas_total", q["nas_total"], members, ("official", [tot_pids[inst]]))
            add(inst, "nas_primary_income", q["primary_income"], members, nas)
            prim = cls["factor_income"]["net"] + cls["taxes_on_production_imports"]["net"]
            add(inst, "primary_income_gap", prim - q["primary_income"], members,
                _lin(lin["factor_income"], lin["taxes_on_production_imports"], nas))  # fmt: skip
    for k in ("DOMESTIC", "ROW_NET"):
        add(k, "required_net", req[k]["required_net"], "", nas)
    insts = ("HH", "E_NFPU", "E_NFPR", "FC", "GG")
    dom_delivered = sum(
        sum(r["net"] for r in flows.filter((pl.col("institution") == i) & pl.col("flow_class").is_in(DISTRIBUTIVE))
            .iter_rows(named=True))
        for i in insts
    )  # fmt: skip
    dom = _lin(*(delivered_lin[i] for i in insts))
    add("DOMESTIC", "delivered_net", dom_delivered, "", dom)
    add("DOMESTIC", "gap", dom_delivered - req["DOMESTIC"]["required_net"], "", _lin(dom, nas))
    return rows


def xdisc_frame(ctx: BlockContext, d: dict[str, float], d1_tot: float, d1_pub: float, pid: str) -> pl.DataFrame:
    sut_cif = _v(ctx, SUPPLY, "supply.cif_adj.cif.current")[0]
    nas_cif = _v(ctx, NAS61, "s6_1.adjustment_for_cif_in_import_of_services.current")[0]
    d3_pub = _v(ctx, NASRES, "derived.si_errors_omissions.current")[0]
    items = {
        "d1_published": d1_pub, "d2_written": d["D2"], "d3_written": d["D3"], "d4_written": d["D4"],
        "d1_written": d1_tot, "residual_published_minus_written": d1_pub - d1_tot,
        "ref_d2_sut_cif": sut_cif, "ref_d2_nas61_cif": nas_cif, "ref_d3_nas_si_errors": d3_pub,
        "residual_with_nas61_cif": d1_pub - (nas_cif + d["D3"] + d["D4"]),
    }  # fmt: skip
    rows = [{"series_id": k, "item": k, "value": float(v), "unit": "INR_crore", "status": "derived", "prov_id": pid}
            for k, v in items.items()]  # fmt: skip
    return _sat(rows, ["item"])


def copied_status(statuses: Iterable[str]) -> str:
    """Status of numbers copied unchanged: their own status when they share one, else weakest()."""
    s = set(statuses)
    return next(iter(s)) if len(s) == 1 else weakest(s)


def _hh_keys_persons(ctx: BlockContext, hh: Sequence[str]) -> tuple[dict[str, float] | None, list[str], str | None]:
    """Persons by group from households' hh_keys (`pop_persons`, measure `level`), their prov_ids and status; None
    (and a warning) if the satellite does not publish it under the agreed name (CROSS_REVIEW 4.3)."""
    keys = ctx.satellite("households", "hh_keys")
    need = {"key", "measure", "household_group"}
    if not need <= set(keys.columns):
        ctx.warn(f"hh_keys lacks columns {sorted(need - set(keys.columns))}: per-capita saving and the population D1 "
                 "sensitivity are not published")  # fmt: skip
        return None, [], None
    p = keys.filter((pl.col("key") == "pop_persons") & (pl.col("measure") == "level"))
    got = dict(p.select("household_group", "value").rows())
    if sorted(got) != sorted(hh):
        ctx.warn(f"hh_keys pop_persons levels cover {sorted(got)}, not the 10 groups: per-capita saving and the "
                 "population D1 sensitivity are not published")  # fmt: skip
        return None, [], None
    return {g: float(got[g]) for g in hh}, sorted(set(p["prov_id"].to_list())), copied_status(p["status"].to_list())


def hh_saving_satellite(
    ctx: BlockContext,
    prior: pl.DataFrame,
    hh: Sequence[str],
    inc: dict[str, float],
    out: dict[str, float],
    d1: dict[str, float],
    k4a: dict[str, float],
    k4_nas: float,
    d1_tot: float,
    k4a_pid: dict[str, str],
    d1_pid: str,
    k4_pid: str,
    d1_total_pid: str,
) -> tuple[Satellite, list[str]]:
    findings: list[str] = []
    pfce = group_sums(prior.filter(pl.col("ref").is_in(CONSUMPTION_REFS)), hh, side="col")
    transfers = group_sums(prior.filter(pl.col("ref").is_in([r for r in USE_REFS if r not in CONSUMPTION_REFS])), hh,
                           side="col")  # fmt: skip
    persons, person_pids, person_status = _hh_keys_persons(ctx, hh)
    ifpri = ctx.rows(IFPRI, series_id=["ifpri.t11.savings_rate.rural", "ifpri.t11.savings_rate.urban"],
                     period="2022-23", vintage=VINTAGE, unit="percent", price_basis=None)  # fmt: skip
    ifpri_rate = dict(ifpri.select("series_id", "value").rows())
    z = sum(k4a.values()) - k4_nas
    tot_inc = sum(inc.values())
    pid = ctx.prov(
        ref="K4a",
        status="estimated",
        inputs=[*sorted(set(k4a_pid.values())), d1_pid, k4_pid, *person_pids],
        source_id=SRC,
        method="Household saving by group (plan s.2.1 steps 3-8): gross income, outlays other than saving, D1 key "
        "and share, K4a (option A, the prior entries), option B (K4a - Z x income share, so the sum equals NAS; "
        "published only), saving / gross income, saving / disposable income (gross income - current taxes, "
        "transfers and property income paid), saving / (PFCE + saving) (the analogue of IFPRI's rate), saving per "
        "person (hh_keys pop_persons), and the D1 splits by PFCE and by population as a sensitivity; Z = sum K4a - "
        "NAS St 1.9 household saving; rural/urban saving / (PFCE + saving) for comparison with IFPRI 2022/23 T11 "
        "(old base, national quintiles: only the rural and urban aggregates are comparable). Rows that copy one "
        "figure unchanged (NAS K4, persons, the D1 total, the IFPRI rates) cite their own records, with the status "
        "of what they copy (verification V-CLO-3).",
    )
    k4_nas_pid = ctx.prov(
        ref="K4a",
        status="official",
        inputs=[k4_pid],
        method="hh_saving row all.k4_nas: NAS 2026 Statement 1.9 gross saving of households incl. NPISH, as published "
        "(the figure Z is measured against).",
    )
    d1_all_pid = ctx.prov(
        ref="K4a",
        status="derived",
        inputs=[d1_total_pid],
        method="hh_saving row all.d1: the D1 total written (D2 + D3 + D4 as the other blocks wrote them, DECISIONS "
        "D2-3), copied from its derived record.",
    )
    ifpri_status = copied_status(ifpri["status"].to_list())
    ifpri_pid = ctx.prov(
        ref="K4a",
        status=ifpri_status,
        inputs=sorted(set(ifpri["prov_id"].to_list())),
        method="hh_saving rows <area>.ifpri_saving_rate_2022_23: IFPRI 2022/23 India SAM data paper Table 11 rural "
        "and urban household saving rates (old base, national quintiles), copied unchanged; comparison only, never "
        "a constraint (plan s.5 C8).",
    )
    persons_pid = (
        ctx.prov(
            ref="K4a",
            status=person_status,
            inputs=person_pids,
            method="hh_saving rows <group>.persons: persons by household group as households' hh_keys satellite "
            "publishes them (key pop_persons, measure level), copied unchanged.",
        )
        if persons and person_status
        else None
    )
    own = {pid: "estimated", k4_nas_pid: "official", d1_all_pid: "derived", ifpri_pid: ifpri_status}
    if persons_pid:
        own[persons_pid] = str(person_status)
    rows: list[dict[str, Any]] = []

    def add(sid: str, group: str, measure: str, value: float, unit: str = "INR_crore", rec: str = pid) -> None:
        rows.append({"series_id": sid, "household_group": group, "measure": measure, "value": float(value),
                     "unit": unit, "status": own[rec], "prov_id": rec})  # fmt: skip

    d1_pfce = split_pro_rata(d1_tot, pfce) if all(v > 0 for v in pfce.values()) else None
    d1_pop = split_pro_rata(d1_tot, persons) if persons else None
    for g in hh:
        gl = g.lower()
        disp = inc[g] - transfers[g]
        add(f"{gl}.gross_income", g, "gross_income", inc[g])
        add(f"{gl}.outlays_excl_saving", g, "outlays_excl_saving", out[g])
        add(f"{gl}.pfce", g, "pfce", pfce[g])
        add(f"{gl}.current_transfers_paid", g, "current_transfers_paid", transfers[g])
        add(f"{gl}.disposable_income", g, "disposable_income", disp)
        add(f"{gl}.d1_key", g, "d1_key", inc[g] / tot_inc, "ratio")
        add(f"{gl}.d1", g, "d1", d1[g])
        add(f"{gl}.k4a", g, "k4a", k4a[g])
        add(f"{gl}.k4a_option_b", g, "k4a_option_b", k4a[g] - z * inc[g] / tot_inc)
        rate = 100.0 * k4a[g] / inc[g]
        add(f"{gl}.saving_rate_gross_income", g, "saving_rate_gross_income", rate, "percent")
        if disp > 0:
            add(
                f"{gl}.saving_rate_disposable_income",
                g,
                "saving_rate_disposable_income",
                100.0 * k4a[g] / disp,
                "percent",
            )
        if pfce[g] + k4a[g] > 0:
            add(f"{gl}.saving_rate_spending", g, "saving_rate_spending", 100.0 * k4a[g] / (pfce[g] + k4a[g]), "percent")
        if d1_pfce:
            add(f"{gl}.d1_by_pfce", g, "d1_by_pfce", d1_pfce[g])
        if persons and d1_pop:
            add(f"{gl}.persons", g, "persons", persons[g], "count", rec=str(persons_pid))
            add(f"{gl}.k4a_per_person", g, "k4a_per_person", k4a[g] * 1e7 / persons[g], "INR")
            add(f"{gl}.d1_by_population", g, "d1_by_population", d1_pop[g])
        lo, hi = PLAUSIBLE_RATE
        if not lo <= rate <= hi:
            findings.append(f"{g}: saving {k4a[g]:,.0f} crore is {rate:+.1f}% of gross income, outside [{lo}%, {hi}%]")
        elif rate < 0:
            findings.append(f"{g}: negative saving ({rate:+.1f}% of gross income); IFPRI rates are all positive")
    for area, groups, key in (
        ("rural", [g for g in hh if g.startswith("H_R")], "ifpri.t11.savings_rate.rural"),
        ("urban", [g for g in hh if g.startswith("H_U")], "ifpri.t11.savings_rate.urban"),
    ):
        s = sum(k4a[g] for g in groups)
        den = sum(pfce[g] + k4a[g] for g in groups)
        add(f"{area}.saving_rate_spending", area.upper(), "saving_rate_spending", 100.0 * s / den, "percent")
        add(f"{area}.ifpri_saving_rate_2022_23", area.upper(), "ifpri_saving_rate_2022_23", ifpri_rate[key], "percent",
            rec=ifpri_pid)  # fmt: skip
        ctx.log(f"{area} saving / (PFCE + saving) {100.0 * s / den:.1f}% vs IFPRI 2022/23 {ifpri_rate[key]:.1f}%")
    add("all.k4a_sum", "ALL", "k4a_sum", sum(k4a.values()))
    add("all.k4_nas", "ALL", "k4_nas", k4_nas, rec=k4_nas_pid)
    add("all.z", "ALL", "z", z)
    add("all.gross_income", "ALL", "gross_income", tot_inc)
    add("all.d1", "ALL", "d1", d1_tot, rec=d1_all_pid)
    return Satellite("K4a", _sat(rows, ["household_group", "measure"]), "Household saving by group; Z", decimals=9), (
        findings
    )


# =============================================================================================
# checks and log
# =============================================================================================


def _checks(
    ctx: BlockContext,
    d: dict[str, float],
    d1_tot: float,
    d1_pub: float,
    d1_pub_pid: str,
    d1_total_pid: str,
    entries: list[dict[str, Any]],
    k4a: dict[str, float],
    k4_nas: float,
    k4_pid: str,
    dep: pl.DataFrame,
    req: dict[str, dict[str, float]],
) -> None:
    ctx.check("d1.written_vs_published", "D1 written (= D2 + D3 + D4 as written) vs the published household residual "
              "(DECISIONS D2-3 band)", d1_tot, d1_pub, target_prov_id=d1_pub_pid, tol_abs=D1_BAND)  # fmt: skip
    gdi, _ = _v(ctx, NAS114, "s1_14.households_npish.gross_disposable_income.current")
    fce, _ = _v(ctx, NAS114, "s1_14.households_npish.final_consumption_expenditure.current")
    sav, _ = _v(ctx, NAS114, "s1_14.households_npish.gross_savings.current")
    ctx.check("d1.published_identity_s1_14", "Published D1 = NAS 1.14 household GDI - FCE - gross saving",
              gdi - fce - sav, d1_pub, target_prov_id=d1_pub_pid, tol_abs=0.01)  # fmt: skip
    parts = [_v(ctx, NAS11, f"s1_1.{s}.current")[0] for s in ("gndi", "pfce", "gfce", "gross_saving")]
    ctx.check("d1.published_identity_s1_1", "Published D1 = NAS 1.1 GNDI - PFCE - GFCE - gross saving",
              parts[0] - parts[1] - parts[2] - parts[3], d1_pub, target_prov_id=d1_pub_pid, tol_abs=0.01)  # fmt: skip
    cif, cif_pid = _v(ctx, SUPPLY, "supply.cif_adj.cif.current")
    ctx.check("d2.written_vs_sut_cif", "D2 (rest_of_world) vs the SUT CIF adjustment (plan s.5 C3)", d["D2"], cif,
              target_prov_id=cif_pid, tol_abs=0.01)  # fmt: skip
    d3, d3_pid = _v(ctx, NASRES, "derived.si_errors_omissions.current")
    ctx.check("d3.written_vs_nas", "D3 (capital_financial) vs NAS saving-investment errors and omissions", d["D3"], d3,
              target_prov_id=d3_pid, tol_abs=0.01)  # fmt: skip
    val, val_pid = _v(ctx, USE, "use.valuables.total.current")
    gold, _ = _v(ctx, NAS19, "s1_9.saving_in_the_form_of_gold_and_silver_ornaments.current")
    d3_hh = float(dep.filter((pl.col("ref") == "D3") & (pl.col("row") == "K_HH"))["value"].sum())
    ctx.check("d3.k_hh_vs_unsectored_valuables", "D3 -> K_HH vs SUT valuables - NAS 1.9 household gold (I2a; plan s.5 "
              "C5)", d3_hh, val - gold, target_prov_id=val_pid, tol_abs=1e-3)  # fmt: skip
    d1_written = sum(e["value"] for e in entries if e["ref"] == "D1")
    ctx.check("x_disc.prior_closure", "X_DISC row (D1 entries) = column (D2 + D3 + D4 as written)", d1_written, d1_tot,
              target_prov_id=d1_total_pid, tol_abs=spec.BALANCE_TOL)  # fmt: skip
    ctx.check("k4.prior_sum_vs_nas", "Sum of prior K4a (pure residuals) vs NAS 1.9 household saving: fails by Z, the "
              "headline finding (balancing enforces the K4 constraint)", sum(k4a.values()), k4_nas,
              target_prov_id=k4_pid, tol_abs=K4_TOL)  # fmt: skip
    row_pid = _v(ctx, NAS61, "s6_1.property_and_entrepreneurial_income_from_rest_of_the_world.current")[1]
    ctx.check("required_flows.identity", "Sum of the institutions' required net distributive flows (table 2.4-C) = "
              "NAS 6.1 net property income and current transfers from the RoW", req["DOMESTIC"]["required_net"],
              req["ROW_NET"]["required_net"], target_prov_id=row_pid, tol_abs=0.01)  # fmt: skip


def _log_diagnostics(ctx: BlockContext, imb: pl.DataFrame, gaps: pl.DataFrame, z: float) -> None:
    top = imb.sort("rank").head(10)
    ctx.log("largest prior account imbalances (row - column, Rs crore):")
    for r in top.iter_rows(named=True):
        pct = "" if r["imbalance_pct"] is None else f" ({r['imbalance_pct']:+.2f}%)"
        ctx.log(f"   {r['rank']:>3} {r['account']:<8} {r['imbalance']:>+18,.2f}{pct}")
    frozen = imb.filter((pl.col("n_var_row") + pl.col("n_var_col") == 0) & (pl.col("row_total").abs()
                                                                          + pl.col("col_total").abs() > 0))  # fmt: skip
    if frozen.height:
        ctx.log(f"accounts with no non-fixed entry (cannot be balanced): {', '.join(frozen['account'])}")
    out = gaps.filter(pl.col("outside"))
    ctx.log(f"{out.height} of {gaps.height} declared constraints are outside their band in the prior")
    for r in out.sort(pl.col("gap").abs(), descending=True).head(10).iter_rows(named=True):
        ctx.log(f"   {r['constraint_id']}: prior {r['prior_sum']:,.2f} vs target {r['target']:,.2f} ({r['gap']:+,.2f})")
    ctx.log(f"household aggregate gap Z = {z:+,.2f} crore (K_HH prior imbalance comes from it)")
