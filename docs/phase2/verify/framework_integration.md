# Verification: SAM framework, integration lens (block contract and pipeline integration)

Verifier: independent agent (did not build the framework). Date: 2026-09-30. Scope: the block contract (SAM_GUIDE.md against the code), ref ownership and structure validation, provenance conformance, vintage handling, dependency ordering, the `sam` / `sam-report` CLI, the manifest and repro coverage of `data/sam`, whether Phase 1 still passes, and whether a new builder can work from the guide alone. Balancing numerics and production's economics are other lenses and are not covered here.

Method: I re-ran every claim myself. All probes ran in a scratch layout: a copy of `data/clean` under the session scratchpad, reached via `sam --out` or `Layout.scratch`. Fake block modules were injected through `pipeline.sam.blocks.__path__`, so no repo file was edited. I hashed `data/sam/**` and `data/manifest.json` before and after all probes, and both are unchanged. I committed nothing and fixed no code.

**Verdict: needs fixes.** The framework does what it claims: tests, repro, the production outputs and the provenance chain all check out. The block contract is mostly well guarded. But four integration gaps will hurt eight builders working in parallel:
- One builder's broken module stops everyone else's builds.
- Clean-data readers never check the unit, so a US-dollar or rupee number can enter as ₹ crore.
- A typo in a data filter returns an empty table silently.
- The default `source_id` has already put a wrong source on one production record.

## Claims reproduced

| Claim | Result |
|---|---|
| `pipeline test`: 3,483 passed, 6 skipped, 23 xfailed | **Reproduced**: 3,483 passed, 6 skipped, 1 deselected, 23 xfailed (265 s) |
| `sam production`: 1,064 entries, 238 constraints, 1 satellite, 35 checks, 19 provenance records | **Reproduced** in a scratch layout (`sam production --out`). All 7 output files are **byte-identical** (sha256) to `data/sam/2023-24/` |
| `repro`: REPRO OK on 222 files, two hash seeds, 1 vs 4 threads, matching `data/manifest.json` | **Reproduced**: "222 files, identical" ×2, "matches data/manifest.json for all 222 rebuilt files", REPRO OK. Note: the repro `sam` step builds only production and does not balance yet, so byte-identical balancing on real data is not yet exercised. Only the synthetic test in `test_sam_pipeline.py` covers it |
| `manifest --check` up to date | **Reproduced** |
| Phase 1 intact | Yes: all Phase 1 tests pass and all 211 clean files are identical in repro |
| `test -k sam_<block>` selects a block's tests | Yes (`-k sam_production`: 21 passed) |

## Provenance (independent DuckDB check over `data/clean/*/_provenance.parquet`)

- All 19 SAM records pass `PROV_SCHEMA`, with unique ids matching `PROV_ID_RE`, `ingest_unit = sam_production`, vintage 2026-08-31 and base year 2022-23.
- Every one of the 21 `inputs` resolves to a clean record, and all 21 are `official`. So the `official` status of each SAM record is justified as pure aggregation.
- Every entry, constraint and satellite `prov_id` resolves, and every check `target_prov_id` resolves to a clean record.
- Entry status equals record status everywhere.
- All clean rows cited are `INR_crore` at `current` prices.
- **One record names the wrong source (finding F3).**

## Validation: what I tried to break

Each probe below ran as an in-memory block through `build_block_module`.

| Probe | Outcome |
|---|---|
| Unknown account; structurally zero group pair; ref not in REFS; ref owned by another block (contract); block not in the brief; DEPENDS outside the brief | Rejected with clear messages |
| Duplicate key in a block; duplicate constraint id | Rejected. A duplicate key across blocks is impossible, because the key includes `ref` and each ref has one owner |
| `prov_id=None`; `prov_id` of a clean record or not registered in the block | Rejected ("entries have no prov_id" / "was not registered") |
| NaN, inf; anchored with NaN `tol_rel`; confidence `High`; status `balanced` | Rejected |
| Estimated record with no inputs and `notes=""`; empty method; method over 4,000 characters; future vintage; unknown `source_id` | Rejected. The long method is caught only at the final schema validation, but still with a clear message |
| Extra DataFrame column; missing `component` column (filled with `total`); string `"10"` value or Int value column (cast) | Rejected / accepted sensibly |
| Satellite: Int value, NaN value, Int dim, ref of another block, bad name, bad unit, duplicate `series_id` | Rejected |
| Constraint: rows passed as a plain string, NaN target, clean `prov_id`, refs filter not in the gap map | Rejected (the string case with an odd but clear message: "unknown accounts ['K', '_', 'H', 'H']") |
| **Entry of ref D1 citing a record made for ref K4a** | **Accepted** (F5) |
| **Record made with another block's ref (`ref="P1"` from closure)** | **Accepted**, and `source_id` is taken from P1 (F5) |
| **Constraint target ₹10 lakh crore over a selection that is structurally zero (`H_R1 <- X_DISC`)** | **Accepted**; it would show up only as slack at balancing (F7) |
| **`ctx.check` whose target is the block's own `estimated` record (a typed-in target)** | **Accepted** (F9) |
| "Wrong unit" | **Nothing to catch it**: entries have no unit column, and `ctx.value` returns USD millions, rupees, percentages and constant-price values as bare floats (F2) |

## Dependencies and CLI

- **Dependency ordering works.** `--with-deps` builds production before households before factors.
- **A missing dependency fails cleanly** with "not built: dependency production has no output (build it first)", exit 1.
- **Reading a block outside DEPENDS fails** with "reading block 'taxes' requires DEPENDS = [..., 'taxes']".
- **A dependency failure skips its dependents.**
- **A full `sam` with only some blocks built** names the missing blocks and prints the partial prior imbalances; nothing is written.
- **`sam-report` without a run** gives a clear message, exits 1 and writes nothing.
- **Unknown block names** are rejected.
- **But:** a broken sibling module blocks every build (F1), and rebuilding a dependency alone leaves its dependents stale without warning (F8).

## Can a new builder follow the guide alone?

Mostly yes. I extracted the "A block in 30 lines" example from SAM_GUIDE.md s.3 verbatim, installed it as `factors`, and it built and validated first time: 2 entries and 2 records, with the series ids real. Every API the guide documents exists with the stated behaviour:
- `ctx.value`, `rows`, `frame`, `concordance`, `block_entries`, `block_constraints`, `satellite`, `accounts.*`, `log`, `warn`, `prov`, `check`
- `entry()`, `constraint()`, `Satellite(decimals=)`, `BlockResult`
- the s.10 rejection list, with the exceptions in F5, F7 and F9

The doc inaccuracies that would mislead a builder are in F12.

## Findings

| # | Severity | Finding | Evidence | Fix |
|---|---|---|---|---|
| F1 | major | One broken block module stops every build, including `sam production` | `pipeline/sam/run.py:57` imports and contract-checks **every** module in `blocks/` before building anything, even for `sam <one block>`. `cmd_sam` catches only `SamError` (run.py:279). Probe: a sibling `factors.py` with a syntax error made `sam production` crash with an uncaught `SyntaxError` traceback; a sibling claiming ref P1 made `sam production` exit 1 ("sam: block factors: ref P1 is owned by block 'production'"). With 8 builders editing `blocks/` at once, any half-written module blocks everyone | Load only the requested blocks plus their DEPENDS closure when names are given. Wrap import and contract errors per block into a failed `BlockRun` (skipping only that block's dependents). Keep the global ref-ownership check, but report it without aborting unrelated builds |
| F2 | major | `ctx.value` / `ctx.rows` ignore unit and price basis, so a wrong unit enters the SAM undetected | `framework.py:325-359` returns bare floats and `ENTRY_DTYPES` has no unit. Clean data holds 354,973 `USD_million` rows, 201,125 `INR` rows, `percent` rows and constant-price rows. Probe: `ctx.value("external_sector_bop_bpm6_annual", "bpm6.usd.bpm6_1.credit.current")` returned 942,848.0 (USD million) with no warning; `s1_2...per_capita_gdp.constant_2022_23` returned 201,324 (rupees, constant prices). The guide's rule "Dollar series: convert with INR_per_USD" is on trust | Give `ctx.value` / `ctx.rows` `unit="INR_crore", price_basis="current"` parameters that are checked by default (raise on mismatch; the caller must name the unit to read USD or percent). Also check in `ctx.prov` that an `official` record's inputs are `INR_crore` / `current`, or that `conversion` is set. Document this in guide s.4 |
| F3 | major | The default `source_id` is the gap map's primary source of `ref`, not the source actually read; it already mislabels a production record | `framework.py:471-472`. `data/sam/2023-24/_provenance.parquet` record `sam_production:32d36a196321` (ref I2, valuables constraint targets) has `source_id = mospi_nas_2026_publication`, but all its inputs are `mospi_sut_2022base` SUT cells (the gap map lists NAS as I2's primary source). This breaks the rule that every number carries its true source id | Default `source_id` to the single source of the inputs. If the inputs mix sources, require an explicit `source_id` and reject one that is not among the inputs' sources unless `notes` explain why. Rebuild production afterwards |
| F4 | major | `ctx.rows` returns an empty frame silently for a typo in a dim value, series id, vintage or period, against the "no silent fallbacks" rule | `framework.py:325-347`. Probe: `rows("io_tables_sut_va", item_code="cee")`, a nonexistent `vintage="2031-01-01"`, `series_id="s1_1.gdp.curent"` and `period="2023-2024"` all return 0 rows, no error. A block that does `.sum()` then writes 0 or drops cells. `ctx.value` is safe (it demands exactly 1 row), but the guide recommends `rows()` for everything else | Raise when any requested `series_id`, dim value or explicit vintage is absent from the dataset, or when the result is empty, unless `allow_empty=True` |
| F5 | minor | A record's ref is not tied to the entry or satellite that uses it, and `ctx.prov` accepts refs owned by other blocks | `framework.py:438-441` checks only that the ref is in the gap map. `validate_entries` (715-719) compares status only. Probes: an entry with ref D1 citing a K4a record passed; closure made a record with `ref="P1"` whose `source_id` defaulted to P1's source. The record has no `ref` field (the ref appears only in the default `table_id` text) | Keep a `prov_id → ref` map in the context. Require entry and satellite `ref` to equal their record's ref. Allow other blocks' refs only on records used solely by constraints or checks |
| F6 | minor | Constraint merging detects conflicts only between constraints of the same `kind`; the guide says any different targets on one selection stop assembly | `assemble.py:61` groups by (rows, cols, refs, components, **kind**). Probe with the synthetic blocks: b1 `equal` 73,000 ± 10 plus b2 `band` 80,000 on the same selection merged OK (both kept); `equal` 73,000 plus `min` 80,000 also merged. Both pairs are infeasible and surface only as slack after solving | Group by selection only. Within a selection, intersect the intervals ([t−tol, t+tol] for equal/band, [t−tol, ∞) for min, (−∞, t+tol] for max) and raise if the intersection is empty. Or fix the guide's wording (SAM_GUIDE.md line 148) |
| F7 | minor | A constraint with a non-zero target over a selection that can hold no entries passes block validation | `validate_constraints` (framework.py:731-799) never checks the structure. Probe: rows `H_R1`, cols `X_DISC` (HH <- DISC is structurally zero), target 1e6: accepted. Balancing can only report it as slack | Reject when no (row, col) in rows × cols is `allowed_cell` and \|target\| > tolerance (the guide's "zero target with no entries" case stays allowed) |
| F8 | minor | Rebuilding a dependency alone leaves its dependents stale: their provenance inputs dangle, with exit 0 and no warning | Probe: build production + a households block citing production records, then `sam production` after a method-text change. Exit 0, and 10 of the households record's `sam_production:*` inputs no longer exist in `_provenance.parquet`; `manifest --check` would pass. A full `sam` rebuilds everything, so the end state is consistent, but builders iterate with `sam <block>` | After `sam <block>`, warn about built dependents ("households read the old production; rerun `sam households` or `sam --with-deps`"), using dependency hashes recorded in each catalog. Add an audit test that every `sam_*` input in `_provenance.parquet` resolves |
| F9 | minor | `ctx.check` accepts a target whose provenance is the block's own estimated record, so typed-in targets pass | `framework.py:899-901` only needs `target_prov_id` to resolve. Probe: `ctx.check(..., 123456.0, target_prov_id=<own estimated record>)` accepted, although the guide says targets are "read from clean data (never typed in)" | Require `target_prov_id` to be a clean record, or a SAM record with status `official`/`derived` and non-empty inputs |
| F10 | minor | Repro's comparison with `data/manifest.json` ignores files that the committed manifest lists but the rebuild does not produce | `pipeline/cli.py:146` iterates only `built.items()`. Orphaned `data/sam/**` outputs (a renamed or deleted block; `cmd_sam` only warns about them) stay in the manifest and repro still says OK | Also flag committed keys under `data/clean/` and `data/sam/` that are absent from the rebuild |
| F11 | minor | `select_vintage('latest')` orders vintages as strings, while `ctx.prov` orders them by `vintage_end` | `framework.py:263` vs `framework.py:468`. With `['2026', '2026-02-27']` for one (series, period), `latest` picks `2026-02-27`, but `vintage_end('2026')` = 2026-12-31 is later. No such mix exists in clean data today (all 1.2M rows checked), so there is no current effect | Use the same key (`vintage_end`, then the string) in both places |
| F12 | minor | Guide inaccuracies that would mislead a builder | (a) SAM_GUIDE.md line 96 shows `ctx.rows(dataset, series_id=None, …)`, but `series_id` is keyword-only (framework.py:329): `ctx.rows("ds", "sid")` raises TypeError. (b) Line 148 says different targets on one selection stop assembly (see F6). (c) Line 216 cites `canonical_floats` without saying it is `pipeline.core.io.canonical_floats`. (d) The s.3 split-pattern snippet uses `pl` while the 30-line template it continues never imports polars. (e) `accounts.check_ownership` (accounts.py:155) claims in its docstring to detect cycles but does not (`block_order` and a test do) | Correct the text: show `series_id=` as keyword-only, add `import polars as pl` to the template, name the import path, align the conflict wording with F6, and fix the docstring |

## What is sound

- **Output files.** Block outputs are written only after full validation (a failed block keeps its previous outputs), deterministically through `pipeline/core/io`, and are hashed in the manifest along with `BALANCING.md`.
- **Scratch and repro runs.** `Layout.sam` follows `clean`, so scratch and repro trees never touch the real one, and `BALANCING.md` for scratch trees is written next to the outputs.
- **Hygiene.** The polars-determinism hygiene test covers `pipeline/sam/**`.
- **Ownership table.** The table matches the gap map (a test checks it), and the dependency table is acyclic.
- **Errors.** Error messages list every problem at once and name the entry key.
