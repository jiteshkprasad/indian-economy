# SAM guide: the contract for block builders (Phase 2)

Read `docs/phase2/DESIGN_BRIEF.md` first (the orchestrator's contract), then this guide (the framework's contract: where the two differ, this guide wins and the difference is listed in `docs/phase2/FRAMEWORK_REQUESTS.md`). You also need `docs/phase0/ACCOUNT_STRUCTURE.md` (the 128 accounts and the §11 block diagram), `data/gap_map.csv` (your refs and their methods), `docs/phase1/COVERAGE.md` and `docs/phase1/RECONCILIATION.md` (which clean series exist and where sources disagree), and your block's plan in `docs/phase2/plans/`.

The working template is `pipeline/sam/blocks/production.py`, with its tests in `tests/sam/test_sam_production.py`. Copy its patterns.

Money is **₹ crore, current prices, FY 2023-24** unless a column says otherwise. Rows **receive**, columns **pay**: an entry `row=C_FOOD, col=H_R1` is rural-quintile-1 households paying for food.

## 1. What you own, and what you must not touch

| You own (create/edit freely) | Never edit |
|---|---|
| `pipeline/sam/blocks/<block>.py` or the package `pipeline/sam/blocks/<block>/` | `pipeline/sam/*.py`, `accounts.yaml`, `structure.yaml` (the framework) |
| `tests/sam/test_sam_<block>.py` | other blocks' modules, tests, outputs and issue files |
| `data/sam/2023-24/blocks/<block>_*` (written by `sam <block>`; never by hand) | anything under `pipeline/ingest/`, `data/clean/`, `data/raw/`, `data/raw_pins/` |
| `docs/phase2/issues/<block>.md` | `pipeline/core/*`, `pipeline/cli.py`, `pyproject.toml`, `uv.lock`, `justfile` |
| `pipeline/sam/explanations/<block>.yaml`: explanations of **your** block's over-threshold adjustments (after balancing, when asked; s.12) | `data/gap_map.csv`, `data/concordance/*`, `ISSUES.md`, `DECISIONS.md`, `BALANCING.md` (generated) |

- Do not commit. The orchestrator commits.
- If you need something from the framework (a new account pair in `structure.yaml`, a new dependency, a new bop tag, a helper), write it in `docs/phase2/FRAMEWORK_REQUESTS.md` with the gap-map ref that needs it. Do not work around it.
- If a clean series is wrong, report it (your issues file); do not patch it in your block.
- Private helpers go inside your package (`pipeline/sam/blocks/<block>/helpers.py`) or a module named `pipeline/sam/blocks/_<block>_*.py`. Every non-underscore module in `blocks/` must be a block.

## 2. Commands

`just <recipe>` and `uv run python -m pipeline <command>` are identical. Run from the repo root.

```
uv run python -m pipeline sam <block>              # build one block (DEPENDS read as built); balancing skipped
uv run python -m pipeline sam <block> --with-deps  # also rebuild the blocks in its DEPENDS first
uv run python -m pipeline sam                      # build every block in dependency order; once all nine
                                                   # DESIGN_BRIEF blocks exist: assemble, diagnose, balance,
                                                   # write data/sam/2023-24/ and BALANCING.md
uv run python -m pipeline sam --no-balance         # build everything, skip balancing
uv run python -m pipeline sam-report               # regenerate BALANCING.md from the balancing outputs
uv run python -m pipeline test -k sam_<block>      # your tests (+ `test tests/sam` for the framework's)
uv run python -m pipeline test                     # everything offline (Phase 1 tests too)
uv run python -m pipeline repro                    # full repro: build + sam three times, byte-identical
```

The CLI pins `PYTHONHASHSEED=0`, single-threaded BLAS/polars and UTF-8 by itself. `sam <block>` prints every control-total check (`ctx.check`) and warning, writes your outputs and regenerates `data/manifest.json` (which now hashes `data/sam/**` and `BALANCING.md` too). If validation fails, nothing of yours is written and the previous outputs stay.

`sam <block>` imports only the blocks it builds (with `--with-deps`, their DEPENDS too). A block module that does not import (a syntax error) or breaks the contract fails its own build and skips its dependents; it never stops another block's build. After any build, `sam` warns about **stale** blocks: a block whose DEPENDS were rebuilt after it read them (the catalog records the sha256 of what it read). Rebuild it; `tests/sam/test_sam_audit.py::test_every_sam_provenance_input_resolves` fails while a SAM record cites a record that no longer exists.

With a partial set of blocks, `sam` (no names) builds what exists, says which DESIGN_BRIEF blocks are still missing, and prints the largest prior imbalances of what is built so far (not written). `balancing_run.json`, the balanced SAM and `BALANCING.md` exist only after a full run.

## 3. A block in 30 lines

```python
"""<What this block builds>: refs, sources (dataset ids, vintages), what is estimated and how, what is skipped."""
from __future__ import annotations

import polars as pl

from pipeline.sam.framework import BlockContext, BlockResult, SamError, Satellite, constraint, entry

BLOCK = "factors"                        # == module name; one of the DESIGN_BRIEF s.4 blocks
REFS = ["V3", "V4"]                      # the gap-map refs you implement: a subset of accounts.OWNERSHIP[BLOCK]
DEPENDS = ["production"]                 # blocks whose outputs you read: a subset of accounts.BLOCK_DEPENDS[BLOCK]

def build(ctx: BlockContext) -> BlockResult:
    ce_in, pid_in = ctx.value("mospi_nas_2026_s6_1",
                              "s6_1.compensation_of_employees_from_rest_of_the_world.current", vintage="latest")
    ce_out, pid_out = ctx.value("mospi_nas_2026_s6_1",
                                "s6_1.compensation_of_employees_to_the_rest_of_the_world.current", vintage="latest")
    v3 = ctx.prov(ref="V3", status="derived", inputs=[pid_in],
                  method="NAS 2026 St 6.1 item 2 (CE from RoW), all to regular labour: assumption A-V3 "
                         "(seafarers, mission staff are salaried; gap map V3 note).")
    v4 = ctx.prov(ref="V4", status="official", inputs=[pid_out],
                  method="NAS 2026 St 6.1 item 7 (CE to RoW), as published.")
    entries = [
        entry("F_LREG", "R_ROW", "V3", ce_in, prov_id=v3, status="derived", role="anchored", tol_rel=0.02),
        entry("R_ROW", "F_LREG", "V4", ce_out, prov_id=v4, status="official", role="fixed"),
    ]
    return BlockResult(entries=entries)
```

**The split pattern** (most estimated blocks): an official total is spread with a key, the pieces are `free` entries, and the total is declared as a constraint so balancing can move the pieces but not the total.

```python
    key = ctx.satellite("households", "hh_keys").filter(pl.col("key") == "rent_share")   # shares summing to 1
    total, tpid = ctx.value("mospi_nas_2026_s7_1", "s7_1.real_estate_prof.os_mi.current", vintage="latest")
    pid = ctx.prov(ref="F3b", status="estimated", inputs=[tpid, *key["prov_id"].unique().sort().to_list()],
                   method="Gap map F3b: <official total> x <key> by group; assumption: <...> (why).")
    entries += [entry(r["household_group"], "F_GOSC", "F3b", total * r["value"], prov_id=pid, status="estimated",
                      role="free", confidence="medium") for r in key.iter_rows(named=True) if r["value"] != 0]
    cons.append(constraint("f3b_total", "F3b", ctx.accounts.in_group("HH"), ["F_GOSC"], total, prov_id=pid,
                           tol_abs=1.0, description="F3b sums to its official total"))
```

(The dataset, series and key names above are illustrative: find the real ones in the clean data and the plans.) `.unique()` and `.group_by()` in polars must keep a deterministic order: pass `maintain_order=True` or sort right after (a hygiene test checks every file under `pipeline/`).

`build(ctx)` must be deterministic (no clocks, no randomness without a fixed seed, no dict/set iteration order leaking into output) and offline. It never reads `data/raw`, the internet, or `data/clean` by path.

## 4. Reading data (`BlockContext`)

| Call | Returns | Notes |
|---|---|---|
| `ctx.value(dataset, series_id, period="2023-24", vintage=None, *, unit="INR_crore", price_basis="current")` | `(value, prov_id)` | fails unless exactly one row matches. With several vintages pass `vintage="YYYY-MM-DD"` or `vintage="latest"` (the latest vintage of each (series, period), ordered by the latest date a vintage can mean, so `"2026"` is later than `"2026-02-27"`; an explicit choice: say it in your method text) |
| `ctx.rows(dataset, *, series_id=None, period="2023-24", vintage=None, unit="INR_crore", price_basis="current", allow_empty=False, **dims)` | polars rows | everything after `dataset` is keyword-only. Filter by any clean column: `ctx.rows("io_tables_sut_va", item_code="ce", vintage="latest")`; `period=None` for all periods |
| `ctx.frame(dataset)` | the whole clean table | all periods and vintages; prefer `rows()` |
| `ctx.concordance(name)` | `data/concordance/<name>.csv` as strings | its sha256 goes in your block catalog; cite it in the method text |
| `ctx.block_entries(block)` / `ctx.block_constraints(block)` | a DEPENDS block's validated outputs | the block must be in your DEPENDS and built |
| `ctx.satellite(block, name)` | a DEPENDS block's satellite | e.g. `ctx.satellite("households", "hh_keys")` |
| `ctx.accounts` | `Accounts` | `.codes` (matrix order), `.in_group("HH")`, `.group(code)`, `.exists(code)`, `.allowed_cell(row, col)` |
| `ctx.log(msg)` / `ctx.warn(msg)` | | a warning is printed in the run summary; if it affects data it also goes in your issues file |

Dataset names are the clean dataset names (`mospi_nas_2026_s1_14`, `io_tables_sut_use`, ...): `uv run python -m pipeline list` shows them, and each unit's `_datasets.json` describes them.

**The readers fail loudly** (no silent empties): a `series_id`, dimension value, period or explicit vintage the dataset does not have raises, and so does an empty result (pass `allow_empty=True` when empty is a legitimate answer). **Units are checked**: every row returned must be `unit` at `price_basis` (defaults: ₹ crore at current prices). To read US$, rupees, percentages or constant-price rows, name them (`unit="USD_million"`, `price_basis="constant_2022_23"`, or `None` for any) and convert explicitly. Dollar series: convert with the external_sector `INR_per_USD` series and cite the rate's prov_id in `inputs` (DECISIONS D1-8); never type a rate. An `official` record over inputs you read in another unit or at constant prices must say how they were converted (`ctx.prov(..., conversion="...")`).

**Cross-block rule (DESIGN_BRIEF s.4).** Compute an intermediate that belongs to another block's domain only if that block does not publish it; otherwise read its entries or satellite. Publish reusable keys as a satellite (households publishes `hh_keys`) so nobody re-derives quintiles. A need outside your DEPENDS goes to FRAMEWORK_REQUESTS.md.

## 5. Entries (the SAM's sub-cells)

Build each with `entry(row, col, ref, value, *, prov_id, status, role, component="total", tol_rel=None, confidence=None, bop_function=None, note=None)`, or return a polars DataFrame with the columns of `pipeline/sam/spec.py::ENTRY_DTYPES`.

| column | rule |
|---|---|
| `row`, `col` | account codes from `pipeline/sam/accounts.yaml`; the pair of their groups must be allowed by `structure.yaml` (the §11 diagram) |
| `ref` | a gap-map ref in your `REFS` |
| `component` | lower-case slug separating sub-parts of one ref in one cell (`imputed_rent`, `gpf`); default `total`. The key `(row, col, ref, component)` must be unique (across all blocks) |
| `value` | ₹ crore, finite, signed as in the SAM (subsidies negative). **No zero entries**: a structural zero is simply absent. The only exception is a ref in `spec.ZERO_ENTRY_REFS` (`D4`: the cell exists but is 0 this year) |
| `status` | `official` (as published or pure aggregation), `derived` (arithmetic on official numbers), `estimated` (modelled; the UI labels it). Must equal the status of its provenance record |
| `role` | `fixed` (never moves: published cells you trust exactly, X_DISC cells), `anchored` (official but may move within `tol_rel`, e.g. a cash figure converted to accrual, or a rounded published cell), `free` (estimated: balancing may move it) |
| `tol_rel` | `anchored` only: allowed relative move (> 0; may exceed 1 for tiny cells, e.g. production's ₹1 crore-per-SUT-cell allowance on a ₹0.4 crore cell) |
| `confidence` | `free` only: `high` / `medium` / `low` |
| `bop_function` | RoW tag (`spec.BOP_FUNCTIONS`): FDI_equity, FDI_debt, FDI_reinvested_earnings, FPI_equity, FPI_debt, ECB, NRI_deposits, trade_credit, short_term_credit, ODI, reserves, external_assistance, banking_capital, errors_omissions, portfolio_abroad, other. Only on entries with `K_ROW` or `R_ROW` as row or column, or on the domestic mirror of a RoW line (ref `K7b`, `spec.BOP_MIRROR_REFS`: e.g. `I_EQTY <- K_NFPR` for ODI) |
| `prov_id` | from `ctx.prov(...)` in this block |
| `note` | short text; long method text belongs in the provenance `method` |

**Choosing a role.** Balancing minimises `Σ w·|a|·(z ln z − z + 1)` with `x = a·z`: the cost of moving an entry grows with its size and weight. Weights: anchored 16, free high 4, medium 1, low 0.25; fixed entries are constants. So:
- a published number you copy or aggregate: `fixed` if it is exact, `anchored` with the smallest honest tolerance if it is rounded or converted (cash→accrual: say 2–5%; say why in the method);
- an estimate with a good key (e.g. HCES shares applied to an official total): `free`, `medium` or `high`, **and** declare the official total as a constraint;
- a residual or a weak prior: `free`, `low`.
- An account whose every entry is `fixed` must already balance to ₹0.01 crore, which published tables rarely do (the SUT misses by up to ₹1 crore per line): leave a non-fixed entry in every account you close.

Signs never flip and zero stays zero in balancing: write every cell that can be non-zero, with its best prior, or balancing cannot put money there. A net flow whose sign is genuinely uncertain (e.g. a State government's saving near zero) can be written as two entries in the same cell with components such as `gross_pos` (+) and `gross_neg` (−): each keeps its sign but the net can cross zero; say so in the method.

Diagonal institution cells (e.g. `E_NFPR <- E_NFPR` inter-corporate dividends, `G_CEN <- G_CEN`) are allowed where the group pair is; they cancel in their own account's balance, so balancing leaves them at their prior unless a constraint moves them.

**Double counting (DESIGN_BRIEF s.4, Phase 0 design review).** PPF is in `I_INPE`/"PF & pension" or in `I_SSAV`, never both; free PDS grain is GFCE (C2a), never PFCE; jewellery is valuables (I2), never PFCE; funded pensions/PF/life insurance are financial (`I_INPE`), only D44 (R9c) and non-life (R17) are current; GST is post-settlement (no IGST account); stamp duty and land revenue are production taxes (P10a); X_DISC cells are pinned (`fixed`) and never balanced.

## 6. Constraints (official totals that are not single entries)

`constraint(constraint_id, ref, rows, cols, target, *, prov_id, description, tol_abs=0.0, tol_rel=0.0, kind="equal", refs=None, components=None)` says: the sum of all entries (of any block) with `row ∈ rows`, `col ∈ cols` and, if given, `ref ∈ refs` and `component ∈ components` lies within `target ± max(tol_abs, tol_rel·|target|)`. Balancing enforces it; if targets cannot all hold, phase 1 reports the minimum slack (s.12), never silently absorbed.

- `constraint_id`: unique in your block, `[a-z0-9][a-z0-9_.-]*`. Globally it becomes `<block>:<id>`.
- `ref`: any gap-map ref (the total it justifies may belong to another block's split, e.g. production declares C1 while households writes C1a).
- `kind`: `equal` for an official total (the tolerance only covers rounding), `band` for a range around a target (e.g. a cash figure that may differ from accrual by up to 3%; enforced like `equal`), `min` (sum ≥ target − tol) or `max` (sum ≤ target + tol) for one-sided limits (a cap on a household group, a floor on regular CE). A `min` and a `max` on the same selection make an asymmetric range.
- `refs`: use it when the cell mixes flows, e.g. `COM <- CAP` holds GFCF (`I1`, `I1a`) and valuables (`I2`, `I2a`).
- `components`: use it when a total covers only some components of a cell (e.g. FISIM on deposits vs explicit fees in `C_FINS <- H_*`).
- A constraint may cover other blocks' entries (e.g. a BoP current-receipts total over production's P5 and factors' V3): that is how cross-block acceptance totals become visible slack instead of silent imbalance.
- **Duplicates are fine, conflicts are errors.** Two blocks may declare the same selection (same rows, cols, refs, components) and kind with the same target; the tighter tolerance is kept and both declarations are listed. The same kind with a different target on one selection stops the assembly. Declarations of different kinds on one selection (say an `equal` and a `min`) are all kept, but the intervals they allow must intersect, else the assembly stops.
- A constraint whose selection can hold no entry (no (row, col) pair in rows × cols is allowed by `structure.yaml`) must allow 0 (a zero target); otherwise validation rejects it.
- Declare every official total your split must respect, and state the tolerance you need (production uses ₹1 crore per SUT cell aggregated). A zero target with no entries is allowed and documents that a use does not exist (e.g. no PFCE on `C_GJOM`).

Example (production, PFCE by commodity): `constraint("pfce.c_food", "C1", ["C_FOOD"], ctx.accounts.in_group("HH"), 2123456.0, prov_id=pid, tol_abs=15.0, description="SUT PFCE for C_FOOD")`.

## 7. Satellites

`BlockResult(satellites={"hh_keys": Satellite(ref, df, description, decimals=6)})`. A memo table outside the SAM: columns `series_id` (unique), any **String** dimension columns, `value` (Float64, finite), `unit` (from `pipeline.core.units.UNITS`: `INR_crore`, `ratio`, `percent`, `count`, ...), `status`, `prov_id`. `value` is rounded to `decimals` (6 to 12) on write: use 9 or more for small shares, or store levels and let readers normalise. `ref` must be one of your REFS (satellite refs P6a, P7b, S1–S9 are owned like cells). Written to `data/sam/2023-24/blocks/<block>_satellites/<name>.parquet`. Other blocks read them with `ctx.satellite(block, name)`.

## 8. Control-total checks

`ctx.check(check_id, description, sam_value, target, *, target_prov_id, tol_abs)` compares a SAM total you built with an official figure you **read from clean data** (never typed in): `target_prov_id` must be a clean record, or a SAM record that is `official`/`derived` with inputs (never your own estimate). A failed check is a warning, not an error: log the difference and its reason in your issues file. Checks are written to `<block>_checks.parquet` and shown by `sam <block>`; your tests assert the ones that must hold. Production has 35 (GDP three ways, PFCE, IC, trade, taxes, output by NAS group, the SUT's own totals).

## 9. Provenance

Every entry, constraint and satellite row has a `prov_id` from

```python
ctx.prov(ref="C1a", status="estimated", inputs=[pfce_pid, hces_pid, ...],
         method="Gap map C1a: SUT PFCE of each commodity split over the 10 groups by HCES 2023-24 Table A10F "
                "shares (leaf items only; jewellery 640-648 excluded); assumption: uniform scaling within a commodity.",
         notes=None, source_id=None, table_id=None, locator=None, vintage=None)
```

- The record uses the Phase 1 provenance schema (`pipeline/core/schema.py` `PROV_COLUMNS`) with `ingest_unit = sam_<block>`; the id is `sam_<block>:<12 hex>`, a hash of the record (same call, same id).
- `method` is required for every SAM record: plain words, precise enough for a verifier to reproduce the number from clean Parquet. Cite the gap-map ref, the datasets and series, the concordance and every assumption.
- `inputs` are the clean prov_ids you used (from `ctx.value` / the `prov_id` column of `ctx.rows`) and any SAM prov_ids of your own or your DEPENDS blocks. Each must resolve.
- `official` needs inputs, all of them official (pure aggregation); `derived` needs inputs; `estimated` needs inputs or `notes` naming the assumption or document.
- **An assumption is a record.** A parameter such as "CE from RoW goes 100% to regular labour" is stated in the `method` (or `notes`) of a `derived`/`estimated` record with its reason; never bury a number in code without a record.
- `source_id` defaults to the **source of the inputs** when they all share one. Inputs from several sources: pass the one the numbers mainly rest on; it must be among the inputs' sources unless `notes` say why. With no inputs, it defaults to the gap map's primary source of `ref`. `vintage` defaults to the latest vintage among the inputs (pass it when there are no inputs).
- **A record belongs to one ref.** An entry or satellite must cite a record made for its own ref (`ctx.prov(ref=...)`); a record made for another block's ref (e.g. production's `I2` valuables total) may back a constraint. The same record text registered for two refs is an error: give each ref its own method text.
- Use one record per block of numbers that share every field (one per ref and method is typical).

## 10. What validation rejects (all problems are listed at once)

Contract: `BLOCK` ≠ module name; a block not in DESIGN_BRIEF s.4; a ref not in the gap map, owned by another block, or claimed twice; `DEPENDS` outside the brief's table; a DEPENDS block not built.
Entries: unknown account; a structurally-zero (row group, column group) pair; ref not in REFS; bad component slug; non-finite or zero value (outside `ZERO_ENTRY_REFS`); bad status/role; `fixed` with tol/confidence, `anchored` without `tol_rel > 0`, `free` without confidence; bop tag outside the vocabulary or neither on a RoW entry nor on a `K7b` mirror; prov_id not registered in the block; entry status ≠ record status; a record made for another ref; duplicate key.
Constraints: bad id, unknown ref/accounts, empty or unknown refs filter, bad components filter, non-finite target, negative tolerance, bad kind, unregistered prov_id, a record made for another ref, no description, a non-zero target over a selection that can hold no entry.
Satellites: bad name, ref not owned, missing columns, non-String dims, null/non-finite values, duplicate series_id, unknown unit, status ≠ record status, a record made for another ref.
Checks: a `target_prov_id` that does not resolve, or that is a SAM record other than official/derived with inputs.
Provenance: Phase 1 schema, method present, inputs resolve, official only over official inputs, `source_id` among the inputs' sources (or explained), `conversion` stated for official records over inputs read in another unit.
Readers (`ctx.rows`, `ctx.value`): unknown series_id / dimension value / period / explicit vintage, an empty result, rows in another unit or price basis (unless named).
Empty results (no entries, constraints or satellites) are an error: no silent empties.

## 11. Outputs (`data/sam/2023-24/`, deterministic, through `pipeline/core/io`)

| File | Written by | Content |
|---|---|---|
| `blocks/<block>_entries.parquet` | `sam <block>` | your entries + `block`, sorted by key |
| `blocks/<block>_constraints.parquet` | `sam <block>` | your constraints (lists as comma-joined, account-ordered strings) |
| `blocks/<block>_checks.parquet` | `sam <block>` | your control-total checks |
| `blocks/<block>_provenance.parquet`, `_provenance.parquet` | `sam <block>` | your records; all blocks' records |
| `blocks/<block>_satellites/<name>.parquet` | `sam <block>` | satellites |
| `blocks/<block>_block.json` | `sam <block>` | catalog: refs, refs not implemented, counts, datasets and concordances read (with sha256), sha256 of the DEPENDS outputs read (stale detection), failed checks |
| `sam_entries_prior.parquet`, `sam_prior.parquet`, `prior_diagnostics.parquet`, `constraints.parquet` | full `sam` | assembled prior (entry and cell level), per-account imbalance, merged constraints |
| `balancing_log.parquet`, `balancing_constraints.parquet`, `balancing_run.json` | full `sam` | per entry: prior, balanced, change, polish change, weight, binding constraints, GRAS value, entry and cell explanation flags; per constraint: band, sums, binding; the run (solver and the options actually used, status, KKT certificate, phase-1 slack, polish, tolerances) |
| `sam_entries_balanced.parquet`, `sam_balanced.parquet`, `sam_balanced_matrix.csv` | full `sam`, only if it succeeded | balanced entries (status `balanced` where moved ≥ ₹1 crore; `prior_status` kept), cells, the 128×128 matrix in accounts.yaml order |
| `BALANCING.md` (repo root) | full `sam`, `sam-report` | generated report |

## 12. Balancing, and what it asks of you afterwards

Cross-entropy (DESIGN_BRIEF s.5.1): minimise `Σ w·|a|·(z ln z − z + 1)` with `x = a·z`, exact account balance, anchored boxes and constraint bands. How it is solved (`pipeline/sam/balance.py`; the Wave A and Wave B reviews in FRAMEWORK_REQUESTS.md say why):

1. **Pre-check (exact).** Accounts linked only through fixed entries must already close: if their fixed entries leave more than ₹0.01 crore, the run fails and names them (an `X_DISC`-style account whose published cells miss by ₹0.1 crore fails here). A miss within ₹0.01 crore is accepted and reported. A constraint none of whose entries can move (all fixed, or none written) is checked here too: if their sum is outside its band, the run names it as a conflict between fixed data and the constraint and counts it as slack (a finding, like any slack below).
2. **Phase 1, minimum slack (an LP).** If the anchored bounds and constraint bands cannot all hold together, the LP finds the smallest total slack (₹ crore) and places it on few constraints; those bounds are widened by that slack (+ ₹0.001 crore) and every slack above ₹0.01 crore is a finding (BALANCING.md, then ISSUES.md). Slack appears **only** when the problem is really infeasible. Another placement of the same total may exist: read the finding as "these constraints conflict", then trace the source disagreement. If balance itself is impossible (a sign lock: an account whose fixed entries leave a gap that no variable entry can close with its sign), the run fails and says where the infeasibility shows and which account causes it.
3. **Phase 2, cross-entropy.** The framework's own dual Newton method (`--solver NEWTON`, the default): exact to about ₹1e-6 crore, deterministic, and well scaled although entries run from ₹0.01 to ₹3e7 crore. It copes with narrow windows, such as a constraint or an account whose movable entries are anchored and meet the other side only within a fraction of a crore (which the widening in step 2 creates whenever a constraint conflicts with anchored boxes). If it has not converged after 100 steps (a heavily constrained problem whose dual is nearly polyhedral: the real SAM's ~1,000 narrow anchored boxes and ~280 tight bands), the **interior-point fallback** runs (DECISIONS D2-23): the framework's own log-barrier path-following method on the same dual (every anchored box and band smoothed by a logarithmic barrier scaled to its own width, so weights spanning eleven orders of magnitude do not matter; the barrier weight shrinks from 0.1 to 1e-10), then the dual Newton method again from its multipliers, which finishes to the certificate's accuracy. If that fails too, the older proximal path is tried; if nothing converges, the run fails and the message names the entries forced to (almost) zero, or those with the smallest z. `balancing_run.json` records the path taken (`solver_options.path`: `direct`, `interior-point fallback` or `proximal fallback`). `--solver CLARABEL` (any cvxpy solver) is an override **for diagnosis only**: at realistic size its answers rarely pass the certificate, and the run then fails. No silent switch: whatever the path, the certificate decides.
4. **KKT certificate.** Whatever the solver, the answer must prove its own optimality (feasibility, stationarity, complementary multipliers, duality gap). If it cannot, the run fails. An entry that balance or a constraint forces to (almost) zero (balanced to below one millionth of its prior) also fails the run, named, when its prior is ₹1 crore or more: signs never flip and zeros never appear, so either the cell is a structural zero (drop the entry) or the data or the constraint that forces it is wrong. A smaller entry forced to zero is accepted and listed in the solver notes (check the constraint that forces it).
5. **Polish** on **free** entries, only when an account is off by more than ₹1e-4 crore after the solve (normally never). It closes every account while holding the sum of every constraint at (or outside) a bound, and of any other constraint it would push out of its band; a constraint sum it has to move for exact balance is reported. It never flips a sign, and it refuses to hide an imbalance above ₹1 crore: either fails the run. The change per entry is in `balancing_log.parquet` (`polish_change`).

GRAS runs on the same prior as a cross-check; its differences are findings only when it converged. Thresholds (spec.py, s.5.3): an entry, **or a cell** (the sum of its entries), needs an explanation when it moves ≥ ₹5,000 crore, or ≥ ₹500 crore and ≥ 10%.

After a full run:
1. Read BALANCING.md: pre-balancing imbalances first (they are findings: trace each large one to its source disagreement before accepting what the solver did; the section "Before balancing: where the gaps come from" shows closure's Z, each institution's delivered and required income by flow class, and the constraints the prior already violates, from closure's satellites `hh_saving`, `institution_gaps` and `constraint_gaps`), then slack findings, then the adjustments to your entries.
2. For each over-threshold adjustment of your entries, add an explanation to **your block's file** `pipeline/sam/explanations/<block>.yaml` (DECISIONS D2-22; same format as the shared `pipeline/sam/explanations.yaml`, whose header shows it: a top-level `explanations:` list): `row`, `col`, `ref`, `component`, the `prior` and `balanced` value you explain (from `balancing_log.parquet`), `why` citing the conflicting sources, and `sources`. A cell with several entries whose total moved over the threshold needs a cell-level item (`ref: "*"`, `component: "*"`, the cell's prior and balanced totals); it may go in any block's file (a cell can hold several blocks' entries: agree who writes it) or in the shared file. An entry-level item in a block's file must explain an entry **of that block**. The audit and BALANCING.md read the shared file and every `explanations/<block>.yaml`; a key explained in two files (or twice in one) is an error, and so is a file in `explanations/` not named after a DESIGN_BRIEF block. An explanation no longer counts once a later run changes the entry by more than ±20% or ₹500 crore from the change it explains (it is then listed as stale; so is an item that explains nothing the run needs, or an entry-level item in another block's file). `tests/sam/test_sam_audit.py` fails while any is missing or stale.
3. Any non-zero slack needs an ISSUES.md entry naming its constraint id (the orchestrator merges your issues file into ISSUES.md).

## 13. Tests you write (`tests/sam/test_sam_<block>.py`, marker `sam`)

The framework tests (`tests/sam/test_sam_structure.py`, `_framework.py`, `_balance.py`, `_pipeline.py`) already cover the contract, validation and balancing. Your file adds, as production's does:
- **Fresh build equals the files** (`build_block_module(mod, Layout.default(), write=False)`, compare with `pipeline.core.io.canonical_floats(fresh.entries, {"value": 6, "tol_rel": None})`: entries are written with `value` to 6 decimals and `tol_rel` unrounded, 12 significant digits): no stale outputs.
- **Your checks pass** (the ones that must).
- **Totals recomputed from clean Parquet** in the test itself (polars or DuckDB), never typed in: e.g. the sum of your entries per ref equals the clean series it comes from; your constraint targets equal their sources.
- **Roles, statuses and structure** you promise (e.g. X_DISC entries fixed; no entry outside the cells your ref allows).
- **Identities your block closes** (e.g. the F_GOSC row equals its column once F3a–F3c are in).

## 14. Issues and verification

`docs/phase2/issues/<block>.md`, same format as Phase 1:

```
# <block>: Phase 2 issues
| # | Severity | Issue | Impact / what the block does | Status |
|---|---|---|---|---|
| <block>-1 | major | ... | ... | OPEN |

## Control totals vs sources
## Assumptions (each also a provenance record)
## Framework requests
```

Log every default, dropped item, conflict, assumption and failed check. A different agent verifies each block independently from clean Parquet with DuckDB (not your code) in `docs/phase2/verify/<block>.md`.

## 15. Done means

1. `uv run python -m pipeline sam <block>` succeeds with no unexplained warning; your outputs are in `data/sam/2023-24/blocks/`.
2. `uv run python -m pipeline test -k sam_<block>` passes and `uv run python -m pipeline test` has no failures of yours.
3. Every ref in your REFS is implemented or listed as not implemented (with why) in your issues file; the block catalog shows `refs_not_implemented`.
4. The module docstring says what is read (datasets, vintages), what is written, what is estimated and how, and what is skipped and why. The issues file is up to date.
