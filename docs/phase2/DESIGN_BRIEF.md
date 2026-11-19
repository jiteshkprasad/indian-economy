# Phase 2 design brief: the balanced SAM (FY 2023-24)

Written 2026-09-30 by the orchestrator. This is the contract for every Phase 2 agent. The framework agent turns it into code and into `docs/phase2/SAM_GUIDE.md` (the block builder's how-to, like `docs/phase1/PIPELINE_GUIDE.md`). If the brief and the guide disagree, the guide wins once it exists, and the difference goes in `docs/phase2/FRAMEWORK_REQUESTS.md`.

**Amendments after wave A (2026-09-30, DECISIONS D2-1 to D2-18):** the default solver is the framework's dual Newton method (D2-1); government also owns the new refs **R7x** and **R9d** (D2-9); dependencies added: government += taxes, fincorp += government and rest_of_world, capital_financial += households (D2-10); X_DISC closes with D1 = D2 + D3 + D4 (D2-3). Build order: production → households → factors → taxes, rest_of_world → government → fincorp → capital_financial → closure → (post-SAM) timeseries. The interface table agreed across blocks is `docs/phase2/plans/CROSS_REVIEW.md` §4.3.

Inputs you must know: `SPEC.md` §3 and §6 Phase 2; `docs/phase0/ACCOUNT_STRUCTURE.md` (128 accounts, §11 block diagram); `docs/phase0/GAP_MAP.md` and `data/gap_map.csv` (106 cells + 9 satellites, each with a method); `docs/phase0/DESIGN_REVIEW.md`; `DECISIONS.md`; `ISSUES.md`; `docs/phase1/COVERAGE.md` and `docs/phase1/RECONCILIATION.md` (what data exists and which sources disagree); `pipeline/ingest/*_coverage.yaml` (which clean series serve which gap-map ref).

## 1. What Phase 2 must deliver (SPEC §6)

1. An unbalanced SAM assembled from Phase 1 clean data, every entry with provenance and a status label.
2. A balanced SAM (cross-entropy primary, GRAS cross-check) with every adjustment logged; `BALANCING.md` generated from the log.
3. Acceptance tests: (a) every account's row total = column total within tolerance; (b) GDP from production, expenditure and income matches NAS allowing only the official discrepancy; (c) government, BoP and flow-of-funds totals match their sources within tolerance; (d) no cell moves more than the threshold without a logged explanation.
4. A lighter annual time series of the top ~50 flows for as many years as data allows.
5. Checkpoint B material: the SAM, the balancing report, the biggest surprises.

## 2. Code layout

```
pipeline/sam/
  accounts.yaml        # the 128 accounts as an ORDERED YAML LIST (code, group, name); the only source of matrix order
  structure.yaml       # which (row group, col group) blocks may be non-zero (ACCOUNT_STRUCTURE §11); anything else is an error
  framework.py         # BlockContext, BlockResult, block discovery, dependency order, validation   (name files as you see fit)
  assemble.py          # entries -> unbalanced SAM
  balance.py           # cross-entropy (cvxpy + Clarabel) and GRAS
  report.py            # BALANCING.md + summary tables
  explanations.yaml    # one explanation per over-threshold adjustment (filled after balancing)
  blocks/<block>.py    # one module (or package) per block; see §4
pipeline/timeseries/   # the top-flows series (§8)
data/sam/2023-24/      # outputs (§6); data/timeseries/ likewise
tests/sam/             # framework unit tests, block tests, identities, balancing audit
docs/phase2/           # SAM_GUIDE.md, plans/, issues/<block>.md, verify/<block>.md, FRAMEWORK_REQUESTS.md
```

`pipeline/core/*` stays the Phase 1 framework; the SAM framework may import from it (io writer, schema, provenance, layout, locks, env pinning) and may extend `cli.py`, `manifest.py` and `paths.py` where needed (the orchestrator owns those files and delegates that edit to the framework agent only).

## 3. Entries, constraints, satellites

A block returns a `BlockResult` with three kinds of output.

**Entries** (the SAM's sub-cells). One row per `(row, col, ref, component)`, unique:

| column | meaning |
|---|---|
| `row`, `col` | account codes from accounts.yaml. Rows receive, columns pay |
| `ref` | the gap-map ref this entry implements (P1, F3a, …); must belong to the block (§4) |
| `component` | slug distinguishing sub-parts of one ref in one cell (e.g. `imputed_rent`, `gpf`), default `total` |
| `value` | ₹ crore, current prices, FY 2023-24. Sign as in the SAM (subsidies negative) |
| `status` | `official` (as published or pure aggregation), `derived` (arithmetic on official numbers), `estimated` (modelled; the UI labels it) |
| `role` | `fixed` (never moves: official published cells, X_DISC cells), `anchored` (official but may move inside `tol_rel`, e.g. a cash figure converted to accrual), `free` (estimated; balancing may move it) |
| `tol_rel` | for `anchored` only: the allowed relative move (e.g. 0.02) |
| `confidence` | for `free`: `high` / `medium` / `low` (sets the balancing weight: moving a high-confidence entry costs more) |
| `bop_function` | RoW-instrument tag (FDI_equity, FDI_reinvested_earnings, FPI_equity, FPI_debt, ECB, NRI_deposits, trade_credit, ODI, reserves, other) or null |
| `prov_id` | a SAM provenance record (below) |
| `note` | short text; long method text goes in the provenance `method` |

A structural zero is simply absent. A zero-valued entry may be written only where the gap map says the cell exists but is zero this year (D4).

**Constraints** (official totals that are not single entries, e.g. "SUT PFCE of C_FOOD = Σ over the 10 household groups", "NAS gross saving of households = K_HH ← H_* total", "Union CGST cash = G_CEN ← T_CGST within 3%"). One row per constraint: `constraint_id`, `ref`, `rows` (list of account codes), `cols` (list), optional `refs` filter, `target`, `tol_abs`, `tol_rel`, `kind` (`equal` or `band`), `prov_id`, `description`. The constraint is: Σ entries with row∈rows, col∈cols (and ref∈refs if given) lies within target ± max(tol_abs, tol_rel·|target|). Blocks declare the constraints that justify their official totals; balancing enforces them.

**Satellites** (memo tables outside the SAM: P6a, P7b, S1–S9, household keys). A named long table in the clean schema style (`series_id`, dims, `value`, `unit`, `status`, `prov_id`). Other blocks may read them (e.g. household distribution keys).

**Provenance.** Every entry, constraint and satellite row has a `prov_id` from `ctx.prov(ref=…, method=…, inputs=[prov_ids], status=…)`. Records use the Phase 1 provenance schema (`pipeline/core/schema.py` PROV_COLUMNS), with `ingest_unit = sam_<block>`, `inputs` = the clean prov_ids (and other SAM prov_ids) used, `method` = the method in plain words (cite the gap-map ref and any assumption). An `estimated` record must have a non-empty `method`. No number may enter without a prov_id that traces to clean data or to an explicitly stated assumption (SPEC rule 1: an assumption parameter, e.g. "CE from RoW allocated 100% to regular labour", is itself recorded as a `derived`/`estimated` record with the reason).

**Reading clean data.** `ctx.value(dataset, series_id, period='2023-24', vintage=None)` returns (value, prov_id) and fails unless exactly one row matches; with several vintages the caller must name one. `ctx.frame(dataset)` returns the clean table. `ctx.block_entries(name)`, `ctx.satellite(block, name)` read built dependencies. Nothing is read from the internet or from `data/raw` directly in a block.

## 4. Blocks, ref ownership, dependencies

Every gap-map ref is owned by exactly one block. Official totals whose split is estimated (e.g. C1 vs C1a) are owned by the block that writes the split entries, which declares the total as a constraint; the block that has the total (production) may also declare it (duplicate constraints with the same target are fine; conflicting ones are an error).

| block | refs owned | depends on | notes |
|---|---|---|---|
| `production` | P1 P2 P3 P4 P5 P6 P7 P8 P9 P10 V1 V2 C1 C2 I1 I3 D4; satellites P6a (optional), S6 | — | SUT 2023-24 aggregated with the committed concordance; all `fixed`/official. Declares constraints for P7 (tax by commodity), V1, V2 (factor income by activity), C1, C2, I1 (final uses by commodity), valuables by commodity. **Built by the framework agent as the template block.** |
| `households` | C1a C4a C4b C4c C4d; satellites S8, `hh_keys` | production | Defines the 10 groups (HCES person quintiles, rural/urban). Publishes reusable distribution keys (population, consumption, rent, deposits/assets proxies…) as the `hh_keys` satellite so other blocks never re-derive quintiles |
| `factors` | V1a V2a V3 V4 F1 F1a F2 F3 F3a F3b F3c F4 F4b | production, households | F4a (FC sub-sector GOS split) belongs to `fincorp`; `factors` declares the FC GOS total as a constraint and writes F4 entries for NFC and GOV only |
| `taxes` | P7a P7b P9a P10a T1 T1a T2 T2x T3 T3a T4 T4a; satellite S7 | production, households, factors | P7b is a satellite (tax by commodity × type × use). T3a has no open input (ISSUES P1-4): method must be stated and labelled low confidence |
| `government` | C2a R1 R2 R2k T2b R6 R7 R9 R9a R9b R10 R15 R16 R18 K3 K3a K6 K8e | production, households, factors | Centre vs States; NAS-concept conversion of cash figures; the H9 grants residual logged |
| `fincorp` | F4a R3 R3a R3b R4 R5 R8 R8a R9c R17 K2 K2a; satellite S9 | production, households, factors | Interest, dividends, D44, non-life insurance; FC public/private parts; FISIM handling |
| `rest_of_world` | R11 R11a R12 R12a R13 R14 R14a K5 K8b K8c D2; satellites S1 S2 S3 | production, households | USD→INR with external_sector FX (D1-8); BoP functional tags |
| `capital_financial` | I1a I2 I2a I3a K1 K4 K7 K7a K7b K8 K8a K8d K9 K9b D3; satellites S4 S5 | production, rest_of_world, government, fincorp | The instrument block; K7b counterparty rule; HDFC merger; K9 residuals |
| `closure` | K4a D1 | all of the above | Household saving by group (residual, constrained to NAS total) and the X_DISC ← H_* allocation. Also the pre-balancing diagnostics (§5.4) |

A block may compute an intermediate it needs from another block's domain only if that block does not publish it; otherwise it reads the other block's entries or satellite. Any cross-block need that is not in this table goes to FRAMEWORK_REQUESTS.md.

**Double-counting rules to respect** (from Phase 0 design review): PPF is in `I_INPE`/"PF & pension" or in `I_SSAV`, never both; free PDS grain is GFCE (C2a), never PFCE; jewellery is valuables (I2), never PFCE; funded pensions/PF/life insurance are financial (I_INPE), only D44 (R9c) and non-life (R17) are current; GST is post-settlement (no IGST account); stamp duty and land revenue are production taxes (P10a); X_DISC cells are pinned and never balanced.

## 5. Balancing

### 5.1 Formulation (primary: cross-entropy)
- Variables: every entry with `role != fixed` and non-zero prior value a_e. Balanced value x_e = a_e·z_e with z_e ≥ 0 (signs never flip; zeros stay zero; no new cells).
- Objective: minimise Σ_e w_e·|a_e|·(z_e·ln z_e − z_e + 1) (the GRAS / minimum-information-loss form; convex, exponential cone). Weights w_e: high 4, medium 1, low 0.25; anchored 16.
- Constraints: for every account, Σ row = Σ column (exact); anchored entries 1−tol ≤ z ≤ 1+tol; every block constraint within its band.
- Infeasibility must not be silent: constraint bands and anchored bounds get non-negative slack variables with a large L1 penalty. Any non-zero slack is a finding, listed in BALANCING.md and ISSUES.md.
- Solver: cvxpy + Clarabel. If Clarabel fails the run fails with the solver status (no silent switch to another solver; a documented, explicit `--solver` option is allowed).
- Final accuracy: after solving, every account must satisfy |row − col| ≤ ₹0.01 crore. If solver tolerance leaves more, apply a documented exact polish on free entries only and log it.

### 5.2 Cross-check (GRAS)
GRAS (Junius & Oosterhaven 2003, Temurshoev et al. 2013 corrections) on the same prior with fixed entries held and each account's target total = mean of its prior row and column sums. Report every entry where cross-entropy and GRAS differ by more than the threshold (§5.3) as a finding.

### 5.3 Thresholds (stated, then tested)
- Balance tolerance: |row − col| ≤ ₹0.01 crore per account.
- Explanation required for an entry when |x − a| ≥ ₹5,000 crore, or when |x − a| ≥ ₹500 crore and |x − a|/|a| ≥ 10%. The explanation lives in `pipeline/sam/explanations.yaml` (keyed by row, col, ref, component) and says why the prior was off, citing the conflicting sources. A test fails if any such entry lacks one.

### 5.4 Pre-balancing diagnostics (in `closure` and the report)
Before balancing, report each account's prior imbalance (row − column) in ₹ crore and % of the account total, sorted. Large imbalances are findings first, not things to balance away: the investigating agent traces each to its source disagreement.

## 6. Outputs (`data/sam/2023-24/`)

Deterministic, written only through `pipeline/core/io`, sorted by full key, rounded (₹ crore to 6 decimals), included in `data/manifest.json` and in `repro`:
- `blocks/<block>_entries.parquet`, `blocks/<block>_constraints.parquet`, `blocks/<block>_satellites/*.parquet`
- `_provenance.parquet` (all SAM prov records)
- `sam_entries_prior.parquet`, `sam_entries_balanced.parquet` (entry level, with prior, balanced, change, status becomes `balanced` where changed materially)
- `sam_prior.parquet`, `sam_balanced.parquet` (cell level: row, col, value), and `sam_balanced_matrix.csv` (128 × 128, account order from accounts.yaml, for humans)
- `balancing_log.parquet` (per entry: prior, balanced, abs and % change, role, weight, binding constraints) and `balancing_run.json` (method, solver, status, objective, iterations, tolerances, slacks)
- `BALANCING.md` at the repo root, generated.

## 7. Tests (`just test` must pass; markers as in Phase 1 plus `sam`)
- Framework: GRAS and cross-entropy on textbook SAMs with known answers (including negative cells and fixed cells); determinism (two hash seeds, 1 vs 4 threads) of the balanced output; account order only from accounts.yaml.
- Blocks: each block's entries validate; refs owned; structure allowed; provenance complete; key official totals equal their sources (unit tests with values read from clean data, not typed in).
- Identities (SPEC acceptance): rows = columns; GDP three ways vs NAS 1.1 (production, expenditure, income) with only the official discrepancy (0 in 2023-24); government (GG saving, Centre/State tax totals vs Finance Accounts and FC16 within stated tolerance); BoP (current account, RoW account closes with D2); flow of funds (every I_* market clears; household financial saving = NAS 5.3); X_DISC cells unchanged.
- Balancing audit: no over-threshold entry without an explanation; no non-zero slack without an ISSUES.md entry.

## 8. Time series (top ~50 flows)
`pipeline/timeseries/`: pick ~50 flows that matter for the Map (e.g. PFCE, GFCE, GFCF, exports, imports, CE, operating surplus/mixed income, product taxes, subsidies, direct taxes, devolution, interest paid by government, remittances, FDI, household financial saving, borrowing by sector …), each defined as a mapping to SAM cells for 2023-24, and fill them for every year the clean data allow (NAS API old-base series from 1950-51; new-base from 2022-23; budget, BoP and RBI series). The old/new base break at 2022-23 stays visible (`base_year` column); any splice is `derived` with the method stated. Output `data/timeseries/top_flows.parquet` + a definitions table; each value has a prov_id. Tests: the 2023-24 value of each flow equals its SAM definition within tolerance (or the difference is explained).

## 9. Rules that bite
- No fabricated numbers; every value traces to clean data or a stated, recorded assumption. Estimated entries say so.
- A different agent verifies each block (independent recomputation from clean Parquet with DuckDB, not the builder's code).
- No silent fallbacks: every gap, default, conflict or dropped item goes into `docs/phase2/issues/<block>.md` (and headline items into ISSUES.md by the orchestrator).
- Don't edit Phase 1 ingest units or clean data. If a clean series is wrong, report it; don't patch around it silently.
- Don't commit; the orchestrator commits.
