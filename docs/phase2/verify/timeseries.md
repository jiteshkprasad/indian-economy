# Verification: the top-flows time series (SPEC s.3 rule 3)

Verifier: an independent agent (not the time-series builder), 2026-09-30.
Scope: `pipeline/timeseries/` (build.py, flows.yaml, explanations.yaml), the outputs in `data/timeseries/`, and the shared-file changes made for this step (`pipeline/cli.py`, `pipeline/core/manifest.py`, `justfile`).
Method: I wrote my own flow specification from `docs/phase2/plans/timeseries.md` s.2.1–2.3 (dataset, series ids, coefficients, year ranges, base years), not from flows.yaml. I recomputed the rows from `data/clean` with DuckDB and my own vintage and revision-round rules. I evaluated the SAM definitions with plain SQL on the blocks' entry files, and ran the CLI twice into scratch layouts.
Regression test: `tests/verify/test_timeseries_spotcheck.py`: 14 passed, and 5 strict xfails that record defects TSV-1 to TSV-5 below. It imports neither `pipeline.timeseries` nor polars.

## Verdict

**Needs fixes.** Every number in the series is right:

- 2,028 of 2,028 non-linked rows equal my recomputation from clean data (census). A stratified sample of 935 rows (36.9%) also matches on status, vintage, estimate stage, series ids and provenance inputs.
- All 504 linked rows match, and every 2023-24 value matches.
- Every "join without a splice" in the issues file holds in the data. The CLI output is byte-identical across hash seeds and thread counts.

What needs fixing is labels, base years and the 2023-24 check definitions. Two of these matter for the published series and three will break the post-balancing check:

- **TSV-1 (major, confirmed).** The segment code `NO` (old-base NAS 2025) is written as the string `"False"`. YAML 1.1 reads an unquoted `NO` as a boolean. This affects 513 of 2,532 rows (403 published and 110 `LINK:False`), 31 provenance records, 31 definition entries and 403 coverage rows.
- **TSV-2 (major, confirmed).** RBI HBS Table 12 rows for 1983-84..2010-11 are labelled `base_year = 2011-12`. The clean records for those years carry no base, and the Phase 1 note says to expect level breaks at 2004-05 and 2011-12. The break at 2011-12 is therefore hidden in 7 flows (196 rows), and F37's linked variant (28 rows) is built on those rows.
- **TSV-3 (major, confirmed on pre-balancing entries).** F27 and F28 (pensions) are class B, but they measure a different concept from the government block's R9 controls: −5.7% and −9.7% against a 2% band. Balancing cannot close this, and class B cannot be explained, so both flows will `fail`.
- **TSV-4 (major, confirmed on pre-balancing entries).** The registered F26 bridge adds UT coverage (+12,264.43) but ignores fincorp's netting of intra-State interest. A gap of −297.66 that passes turns into an `unexplained` residual of −12,562.10.
- TSV-5 to TSV-9 are minor. They cover the link-rule wording (M13), the stale check table, F25 passing only because its band is wide, the builder's tests reading the builder's own definitions, and an unknown revision round being skipped silently.

## 1. Recomputation record

### 1.1 Rows (tolerance 1e-6 relative)

| Check | Result |
|---|---|
| Row keys (flow, variant, base_year, FY), non-linked | 2,028 expected = 2,028 written; 0 missing, 0 extra; 69 flows (54 core, 15 memo) |
| Values, full census of non-linked rows | 0 mismatches |
| Stratified sample (per flow × variant × base × segment: first, middle, last and every 4th FY) | 935 of 2,532 rows (36.9%): 765 published, 161 linked, 5 proxy, 4 fc16; 457 old-base, 288 new-base, 190 base-less; 246 before 1990, 197 in 1990–2010, 492 from 2011 |
| Status (official only for a +1 sum of official lines of one table; F10 derived by plan) | 0 mismatches (e.g. F13, F30, F49 NB, F54, M07 NO/NN, M09 T12, M14 RB derived; F31 derived because its clean record is derived, timeseries-13) |
| Vintage (latest input vintage), estimate stage, series ids, unit/price basis | 0 mismatches; no row mixes estimate stages today |
| Linked variant: ratios from clean data vs `top_flows_definitions` | all 69 flows agree to 1e-9; 504 linked values = old(t) × r(2022-23), t ≤ 2021-22, status derived, base 2022-23 |
| Coverage by FY (plan s.2.6) | 5 (1950-51), 7, 13 (1983-84), 14, 15, 18, 19, 38 (2011-12), 40, 41, 42, 44, 54 (2022-23 and 2023-24), 42 (2024-25), 12 (2025-26): exactly the plan |
| `base_overlap` flags | exactly the FYs with both NAS bases (2022-23; 2023-24 where the old segment reaches it) |
| Unused available data | only the documented cases: KFI SGST zeros 2011-12..2016-17 (ts-14), RBI surplus FY 2026-27 (ts-13), T143 portfolio from 2020-21 (proxy stops where the BoP starts). BE/RE rows never fall inside a segment's range |

### 1.2 Joins and precedence rules (recomputed from clean data)

| Join (issues-file claim) | Recomputed |
|---|---|
| T12 = old-base NAS 5.3, 10 lines, 2011-12..2023-24 | max gap 0.49 crore |
| FC16 FT = RBI AT2, devolution and grants, 2007-08..2022-23 | max gap 0.5 / 0.3; 2023-24 switches (11,29,494 vs 11,29,761.5; 7,39,260 vs 5,27,931) |
| API back series = NAS 2025, 2011-12 (GDP, PFCE, GFCE, GFCF, exports, imports, GVA) | max 2.29 crore (GDP) |
| Old-base GCF − gross saving = net capital inflow, 2011-12..2023-24; NB 2011-12 | < 1e-6; NB 3,76,171 = NO |
| RB derivation of Union GTR = FC16 GTR, 2022-23 and 2023-24 | 30,54,191.64 / 34,65,518.58 vs 30,54,192 / 34,65,519 |
| T143 FDI = BoP FDI, 2020-21..2025-26 | equal |
| BoP invisibles = NAS 6.1, 2022-23..2024-25 | max 0.48 crore |
| FC16 fertiliser = Statement 7, 2022-23 and 2023-24 | 0.00 / 0.42 |
| NAS API "latest round" rule | for every FY 2011-12..2023-24 the chronologically latest `api.gdp` round equals NAS 2025 1.1 GDP; the latest rounds of the six sector GFCF series add up to NAS 2025 1.1 GFCF within 4.4 crore (API integer rounding). This validates the rule for F33 and F46, which the plan had only assumed |

### 1.3 SAM definitions vs the plan and the SAM cells (pre-balancing)

I compared flows.yaml's `sam.terms` with the plan's s.2.2/2.3 definitions and s.8 amendments by reading them. They agree:

- F25/F26 add R8a and R9c (XR-9, without component filters: ts-17).
- F20, F24, F29, F39, F41 and F42 use the XR-19 component names.
- F51–F53 use the agreed bop tags.
- F11 and F50 also list R3 as an optional ref in the RoW block. This is harmless.
- F04 also lists the X_DISC column. This is harmless: I2a is written on C_GJOM ← K_HH, and D4 is excluded.

I then evaluated every definition with plain SQL on the union of the 8 block entry files present at 22:30: every block except closure.

- **Guards: clean.** No unlisted ref sits in any flow's cells and no entry is matched twice. Every named component and bop tag exists. The only missing selectors are closure's K4a and D1 (F35, M12, M13). ts-16 is therefore largely resolved.
- **Class A: 44 flows can be evaluated, and all are within 1.0 crore of the time series.** The largest gap is F52: 3,69,274 vs 3,69,273, because the BoP is rounded.
- **Classes B, C and D** (Rs crore; tol = the build's rule; the verdict is what the build would give if balancing left these cells where they are):

| Flow | Class | TS 2023-24 | SAM (entries) | SAM − TS | Bridge | Residual | Tol | Predicted |
|---|---|---:|---:|---:|---:|---:|---:|---|
| F23 devolution | B 0.05% | 11,29,761.50 | 11,29,493.71 | −267.79 | | −267.79 | 564.88 | pass |
| F25 Centre interest | B 3% | 11,01,867.88 | 10,87,704.16 | −14,163.72 | | −14,163.72 | 33,056.04 | pass (TSV-7) |
| F27 Centre pensions | B 2% | 2,38,328.29 | 2,24,647.49 | −13,680.80 | | −13,680.80 | 4,766.57 | **fail** (TSV-3) |
| F28 State pensions | B 2% | 4,94,938.72 | 4,46,990.75 | −47,947.97 | | −47,947.97 | 9,898.77 | **fail** (TSV-3) |
| F14 GST Centre | C | 9,57,207.82 | 9,78,074.45 | +20,866.63 | +5,497.16 | +15,369.47 | 9,572.08 | unexplained |
| F15 SGST | C | 8,00,112.02 | 8,54,549.16 | +54,437.14 | +41,008.76 | +13,428.38 | 8,001.12 | unexplained |
| F16 Union excise | C | 3,05,362.18 | 3,10,237.25 | +4,875.07 | 0 | +4,875.07 | 3,053.62 | unexplained |
| F17 customs | C | 2,33,118.97 | 2,28,887.27 | −4,231.70 | −3,343.88 | −887.82 | 2,331.19 | pass |
| F18 State VAT | C | 3,97,467.06 | 4,12,892.30 | +15,425.24 | +8,937.04 | +6,488.20 | 3,974.67 | unexplained |
| F19 State excise | C | 2,49,133.50 | 2,62,398.84 | +13,265.34 | +9,142.00 | +4,123.34 | 2,491.34 | unexplained |
| F20 stamps | C | 2,20,289.49 | 2,28,154.98 | +7,865.49 | +7,865.49 | 0.00 | 2,202.89 | pass |
| F21 CIT | C | 9,11,055.01 | 9,11,055.01 | 0.00 | | 0.00 | 9,110.55 | pass |
| F22 PIT + STT | C | 10,44,725.55 | 10,44,763.68 | +38.13 | | +38.13 | 10,447.26 | pass |
| F24 grants | C | 5,27,931.00 | 6,96,018.36 | +1,68,087.36 | 0 | +1,68,087.36 | 5,279.31 | unexplained |
| F26 State interest | C | 4,94,910.97 | 4,94,613.30 | −297.66 | +12,264.43 | −12,562.10 | 4,949.11 | **unexplained** (TSV-4) |
| F29 food subsidy | C | 2,11,814.39 | 1,63,971.75 | −47,842.64 | 0 | −47,842.64 | 2,118.14 | unexplained |
| F30 fertiliser | C | −1,88,291.62 | −2,07,569.12 | −19,277.50 | 0 | −19,277.50 | 1,882.92 | unexplained |
| M08 CIT + PIT | C | 19,55,780.56 | 19,55,818.69 | +38.13 | | +38.13 | 19,557.81 | pass |
| M14 Union GTR | C | 34,65,519.00 | 33,72,308.56 | −93,210.44 | 0 | −93,210.44 | 34,655.19 | unexplained |
| F34 GG debt securities | D | 18,83,882.95 | 18,34,226.60 | −49,656.35 | 0 | −49,656.35 | 5 | unexplained |
| F48 NFC liabilities | D | 22,17,360.83 | 27,85,466.87 | +5,68,106.04 | 0 | +5,68,106.04 | 5 | unexplained |

Except for F26, the `unexplained` list matches the builder's own timeseries-11 list. F26 is new: it would pass without its bridge.

## 2. Base years and splices

- **Both bases stay visible where NAS overlaps.** Old and new NAS rows coexist in 2022-23 and 2023-24 with `base_overlap`, and M08's two measures are never joined. The linked variant is built only for the 10 whitelisted flows. It is derived, its ratios are computed from the rows, and it stops at 2021-22.
- **The hidden break is TSV-2.** For 1983-84..2010-11 the T12 clean rows carry `base_year = null`. Their Phase 1 provenance note (`rbi_financial_accounts:b803c97ba9f5`) says the RBI table splices in earlier-base figures without saying which base, and to expect level breaks at 2004-05 and 2011-12. The time series labels them 2011-12 and flags 2011-12 only as `segment_join`. The equality T12 = NAS 5.3 holds from 2011-12 onward only, so it cannot establish the base of earlier years. The series shows the drop: F36 goes from 10,79,867 (2010-11) to 9,32,729 (2011-12), −13.6%, with no break marker. The plan's s.2.0 rule caused this ("T12 rows, which are the same series as old-base NAS 5.3"), so the plan needs the same correction.
- Every other row's `base_year` equals the base of its clean inputs. I checked this for all 2,028 non-linked rows; the only exceptions are the 196 T12 rows.

## 3. Provenance

- **All 152 records are used, and every row cites one.** They are Phase 1 schema, `ingest_unit = timeseries`, content-hashed ids, `estimated` never appears, and every derived record has a method.
- **Every sampled row's record is consistent with the row.** It has the row's status and base_year. Its source is registered and is the source of its inputs. Its inputs include every clean record the row is computed from.
- **Linked records resolve** to the old-base segment records and both 2022-23 records.
- **URL and retrieval date are null.** This matches the Phase 1 convention for derived records (3 of 3 derived `mospi_nas_2026` records do the same). The inputs carry them.
- **TSV-1 leaks into provenance.** 31 records have `table_id` "top flows … segment False" and locator `segment=False`, which identify nothing.

## 4. Determinism, manifest, CLI and repro

- **Determinism.** I ran `python -m pipeline timeseries --out` twice into scratch layouts (a copy of data/clean and data/sam): PYTHONHASHSEED 0 with 1 thread, then PYTHONHASHSEED 1 with 4 threads. All five files were byte-identical between the runs. `top_flows`, `_definitions`, `_coverage` and `_provenance` were also byte-identical to the committed files. The committed `top_flows_sam_check.parquet` differs because it is stale (TSV-6). It took about 8 s per run.
- **Manifest.** `data/manifest.json` lists all five files, with sha256 and row counts equal to disk and no orphaned outputs. `build_manifest` skips a missing `data/timeseries` (scratch and Phase 1 layouts). `pipeline/timeseries/**` is in `code_hash` and in no unit's scoped hash.
- **CLI.** `timeseries [--out DIR]` is listed in `--help`, and `just --dry-run timeseries` resolves.
- **Repro.** A full `repro` runs `timeseries --out` after `sam` in each build. `REPRO_OUTPUT_DIRS = ("data/clean/", "data/sam/", "data/timeseries/")` drives two checks:
  - The tolerance diagnosis. It now maps `data/<kind>/<sub>` to `run<i>/<kind>/<sub>`, which matches `ts_dir = clean.parent/"timeseries"`. It prints non-parquet diffs instead of passing them to a frame comparison, which is an improvement for Phase 1.
  - The orphan check. The data/clean and data/sam part came from the framework (I-F10); the time-series part is new.

  A unit-scoped `repro UNIT` is unchanged: no sam, no timeseries, no orphan check. I did not run a full `repro`, because it needs a balancing `sam` run and closure is not built. Note that a full repro now depends on `sam` succeeding, which is a framework choice.
- **Full suite** (run once at the end, 2026-09-30): 3,851 passed, 4 failed, 56 skipped, 32 xfailed. All tests in `tests/timeseries`, this file, `tests/clean` (including `test_manifest_lists_the_files_on_disk`), `tests/core` and `tests/hygiene` pass. The 4 failures belong to other agents' files and none involves the CLI, the manifest or the time series:
  - `tests/sam/test_sam_framework.py::test_a_broken_sibling_module_does_not_stop_another_blocks_build`: "dependency 'production' has no module" in its fake-blocks setup.
  - `tests/verify/test_sam_households_spotcheck.py`, two tests: the C4b FISIM census.
  - `tests/verify/test_sam_solver_certificate.py::test_the_proximal_fallback_path_is_deterministic_across_hash_seeds_and_threads`: the solver took the direct path.

  A later re-run of this file together with `tests/hygiene` gave 39 passed and 5 xfailed. The one failure was `test_group_by_and_unique_control_order`, caused by a concurrent edit to `pipeline/sam/blocks/households/__init__.py:96` (not a time-series file).

## 5. Findings

| # | Severity | Finding | Evidence | Fix (for the builder; not applied) |
|---|---|---|---|---|
| TSV-1 | major | Segment code `NO` becomes `"False"` everywhere | PyYAML `safe_load` reads unquoted `NO` as boolean False: 31 `code: NO` in flows.yaml; `build.py` stores `str(s.get("code"))`. 403 published + 110 linked rows (`LINK:False`), 31 provenance `table_id`/`locator`, 31 segments in `top_flows_definitions.segments`, 403 coverage `segments` (the check table is unaffected: it uses new-base or base-less rows). The builder's tests compare codes with the same YAML, so they pass | Quote the code (`code: "NO"`) and make `load_definitions` reject a non-string `code` (and any non-string account/ref token); regenerate; keep `test_segment_codes_are_the_plan_codes` |
| TSV-2 | major | T12 rows before 2011-12 labelled base 2011-12; the break at 2011-12 (and 2004-05) is hidden | Clean T12 rows 1983-84..2010-11 have `base_year` null and the note "expect level breaks … 2004-05, 2011-12"; all other rows match their inputs' base. F36, F37, F39, F40, F41, F42, M09: 196 rows; F37 `linked_2022_23`: 28 rows scaled from them. F36 −13.6% at 2011-12 with only a `segment_join` flag | Give pre-2011-12 T12 rows `base_year = null` (or a distinct label), mark 2011-12 as a base change for these flows, and stop F37's link at the NAS 2025 years (2011-12..2021-22) unless the double base is stated; correct plan s.2.0 and timeseries-2 |
| TSV-3 | major | F27/F28 class-B definitions do not match the government block's R9 concept | Government R9: Centre = MH 2071 − NPS employer contribution (2071.01.117 + .902) − CGHS (2071.01.118) = 2,24,647.49, band 2%; States = RBI SF App. II pensions (all States + UTs) − PFRDA State employer NPS = 4,46,990.75, band 3%. TS: gross MH 2071 2,38,328.29 (−5.7%), KFI 28 States 4,94,938.72 (−9.7%). Even at the edge of government's bands the gaps (−3.9%, −7.0%) exceed F27/F28's 2%. Class B cannot be explained (the builder's own `test_explanations_are_well_formed` allows only C/D), so the build and `test_each_flow_equals_its_sam_definition_on_the_balanced_sam` will fail | Make F27/F28 class C with clean-series bridges for the NPS, CGHS and coverage items (the government block's inputs `union_fiscal:6becf86b484b`, `union_fiscal:805970785a6f`, `finsector_markets:218af9b82bb2`, `state_fiscal:2f80e9e102f2`), or define the series on government's net concept |
| TSV-4 | major | F26's registered bridge is incomplete: it creates an unexplained residual | fincorp's R3b States control (`sam_fincorp:908d589b1c4f`) = App. II interest less intra-State 'others' and SDLs held by States = 4,94,608.64 (band 1%). SAM entries 4,94,613.30 vs KFI 4,94,910.97: −297.66, which passes as is. The bridge (RBI SF St. 13 − KFI = +12,264.43) makes the residual −12,562.10 > 4,949.11; balancing can move the cells by only ±4,946 | Add the intra-State netting (fincorp's clean inputs) as a negative bridge term, or drop the coverage bridge; do not record the resulting residual as `explained_residual` |
| TSV-5 | minor | Link eligibility is declared, not found; one refusal reason is false | `link_flow` never tests the rules for `refused` flows. The rules of plan s.2.5 hold in clean data for 14 flows: the 10 whitelisted plus F39 (1.00939/1.01843), F42 (1.00315/1.01583), M11 (1.00000/1.00000) and M13 (0.98462/0.96561, gap 0.0190 ≤ 0.02). M13's stored reason "unstable overlap ratios" contradicts the 0.02 rule stated in the method; the summary's "the code finds exactly the plan's ten" is inaccurate | Evaluate the rules for every base-tied flow and store the real reason (whitelist, concept, HDFC merger, or the failing rule); fix the M13 text and the timeseries-5 wording |
| TSV-6 | minor | Committed `top_flows_sam_check.parquet` is stale; freshness test does not cover it | Written 22:17 before capital_financial/fincorp/government/RoW/factors were built: 18 flows have `sam_prior` 0 or partial (e.g. F25 43,651.72 vs 10,87,704.16 now). `test_outputs_equal_a_fresh_build` compares rows, definitions, coverage and provenance only | Re-run `timeseries` after each `sam` run (the orchestrator step) and add the check table to the freshness test |
| TSV-7 | minor | F25 passes only because of its 3% band | fincorp's Union control (NAS concept: MH 2049 less intra-Centre interest, debt management, recoveries, re-issue premium, plus NSSF interest to savers) 10,86,513.97; SAM 10,87,704.16 vs MH 2049 cash 11,01,867.88 (−1.29%). The term also sweeps in R14 `other_primary_income` on G_CEN (1,190.19), which is not interest | Consider class C with fincorp's `gov_interest_bridge` items as bridge series, and filter R14 to its interest components |
| TSV-8 | minor | The builder's "recomputed independently" test is not independent of flows.yaml | `test_rows_reproduce_their_clean_sources` takes series and coefficients from `top_flows_definitions` (built from flows.yaml), and `test_break_flags` compares segment codes with the same YAML; a wrong series or code in flows.yaml cannot fail them (that is how TSV-1 passed) | Keep an independent plan-based spec as in `tests/verify/test_timeseries_spotcheck.py` |
| TSV-9 | minor | An unknown NAS API revision round would be skipped silently | `read_term` reads only the rounds in the closed list `ROUNDS_LATEST`; a new round label would be ignored and an older round taken without a message (a silent fallback). All rounds present today are known (asserted in my test) | Fail when a `<stem>.rev_<round>` series exists whose round is not in the list |

## 6. Builder claims checked

| Claim (builder summary / issues file) | Verdict |
|---|---|
| 69 flows, 2,532 rows (2,006 published, 504 linked, 22 alternatives), 1950-51..2025-26 | confirmed |
| Every 2023-24 value equals the plan's figure from clean data (deviations: F22, M08 include STT) | confirmed (census); STT deviation follows D2-12 |
| Coverage 54 / 54 / 42 / 12 in 2022-23..2025-26 | confirmed, and every other line of plan s.2.6 |
| The joins that avoid a splice all hold | confirmed for 2011-12 onward; T12 before 2011-12 is not on the 2011-12 base (TSV-2) |
| Base break visible, `base_overlap` flags | confirmed for NAS 2025/2026; not for T12 at 2011-12 (TSV-2) |
| "The code finds exactly the plan's ten linkable flows" | not as stated (TSV-5) |
| Every row has a prov_id; 152 records, Phase 1 schema, citing clean prov_ids | confirmed (label defect TSV-1) |
| Nothing is estimated; BE/RE never used; latest vintage per (series, period); last FY 2025-26 | confirmed |
| Latest NAS API round verified against NAS 2025 GDP | confirmed; I also confirmed it for sector GFCF (sectors add up to NAS 2025 GFCF) |
| Hash-seed determinism; manifest covers data/timeseries; repro runs timeseries | confirmed (CLI in scratch layouts, seeds 0/1, threads 1/4) |
| Class-B bands "F27, F28 2% (assumed)" | the band is not the problem, the concept is (TSV-3) |
| The class C/D flows that will need `explained_residual` after balancing (F14–F22, F24, F26, F29, F30, F34, F48, M08, M14) | largely right: F17, F20, F21, F22 and M08 already pass on the block entries; F26 fails only because of its bridge (TSV-4) |

## 7. Not checked

- The balanced SAM: it does not exist yet, so the post-balancing verdicts above are predictions from the pre-balancing entries.
- A full `repro`: it needs a balancing `sam` run.
- The economic interpretation of the class C/D gaps beyond the concept checks above: that belongs to the owning blocks' verifiers.
- The optional flows X01–X11: they are not built (ts-15).

## Re-verification (wave C)

Re-verifier: a wave-C agent, 2026-10-01, independent of the wave-B fixer. Scope: the fixer's edits of 2026-09-30 (23:17) to `tests/verify/test_timeseries_spotcheck.py`, listed in `docs/phase2/issues/timeseries.md` under "Edits to the verifier's file". Every changed expectation was recomputed with DuckDB from `data/clean` and the rebuilt `data/timeseries`.

**Baseline.** The test file is untracked, so `git diff` is empty. I rebuilt the verifier's original file from the verifier's session transcript: its Write at 22:48 plus its two Edits. I also reversed the fixer's patch script (`fix_verify.py` in the session scratchpad). The two reconstructions agree, down to an identical AST.

Comparing the original with the file as found, the formatting differs (ruff; the ASTs are identical) and one section comment was reworded. Beyond that there are exactly five changes:

- the module docstring note;
- the base of the T12 segments in the plan spec;
- the row-count literal in `test_row_keys_equal_the_plan_spec`;
- four strict-xfail markers removed, with the test bodies unchanged;
- the TSV-3 test replaced.

No other test function and no other top-level statement changed. The fixer's claim holds: no expected value, rule or tolerance of the census was changed beyond the T12 base and the row count that follows from it.

| # | Change | Recomputation (DuckDB) | Verdict |
|---|---|---|---|
| 1 | Docstring note ("to be re-verified") | none needed | kept; extended with this pass |
| 2 | Plan spec: the seven T12 segments (F36, F37, F39, F40, F41, F42, M09) move from base `2011-12` to `None` | In clean `rbi_financial_accounts_hbs_saving`, all eight series used have `base_year` null for 1983-84..2010-11 (28 FYs; `units_of_uti` 26, to 2008-09) and base 2011-12 from 2011-12. In `top_flows`, all 196 T12 rows have base null. The flag `base_change` sits exactly on 2011-12 of the seven flows and nowhere else | **Confirmed.** This is the verifier's own TSV-2 fix |
| 3 | Row count 2,532 → 2,504 | Linked rows are the published old-base rows up to 2021-22 of the ten whitelisted flows. M01, M02, F01, F03, M03 and M06 have 72 each (NB 61 + NO 11). F05, F06, F07 and F37 have 11 each (NO only). Total 476. F37 loses its 28 T12 years (1983-84..2010-11) because those rows are no longer old-base. Written: 476 linked (F37: 2011-12..2021-22), 2,028 non-linked, 2,504 in all | **Confirmed** |
| 4a | TSV-1 marker removed | No segment reads `False`/`True`. The written segment codes are within the plan codes (NB, NO, NN, NP, NS, NA, T12, RB, KF, AT, FT, AF, EP, FS, RS, FF, BI, BO, FI, NR; LINK:NB, LINK:NO) | **Confirmed** |
| 4b | TSV-2 marker removed | See row 2 | **Confirmed** |
| 4c | TSV-4 marker removed (F26 test body unchanged) | The test passes on the block entries. The bridge (App. II interest − KFI − App. II 'others') is +658.07, and the residual −960.40 is within 4,949.11. That residual is fincorp's estimated SDL interest held by the States' own funds, which no clean series carries | **Confirmed** |
| 4d | TSV-5 marker removed | M13's old/new ratios are 0.984624 / 0.965610, 0.0190 apart. The stored reason no longer cites "unstable" ratios, and `link_rules` = "met: ... 0.0190 <= 0.02; one sign" | **Confirmed** |
| 5 | TSV-3 test: class-B band test replaced by a class-C bridge test | **F27:** AFS MH 2071 is 2,38,328.29 (Finance Accounts `fa9.2071.total` 2,38,328.30). The bridge is −(2071.01.117 9,399.19 + .902 −1.11 + .118 4,282.72) = −13,680.80, so TS + bridge = 2,24,647.49, which is government's `gov.r9.centre` 2,24,647.49 (the 0.006 gap is AFS/FA rounding). **F28:** KFI is 4,94,938.72. RBI SF App. II pensions 4,90,983.18 − PFRDA m7d State employer 43,992.43 = 4,46,990.75, exactly `gov.r9.states`, so the bridge is −47,947.97. The bridge series are the government block's own inputs (prov ids `union_fiscal:805970785a6f`, `state_fiscal:2f80e9e102f2`, `finsector_markets:218af9b82bb2`). Residuals on the block entries are +0.01 and 0.00 | **Confirmed and strengthened.** The test now carries its own bridge spec, `TSV3_BRIDGES`, written from government's R9 control methods. It fails if `explanations.yaml` lists different series, and it also checks AFS = FA MH 2071 within Rs 0.01 crore. Before, it took the series from the builder's file |

**Nothing is reverted.**

### Changes made in this pass

- **closure-18 (F35, M13).** F35 (household saving) and M13 (household GDI) contain closure's K4a. K4a equals NAS 1.9 only after balancing, where the K4 constraint binds (closure plan C7, option A). The pre-balancing test therefore no longer compares them with NAS. It requires M13 to miss NAS by F35's K4 gap and by nothing else. On the block entries F35 misses by −4,36,163.72 (Z) and M13 by −4,36,163.36. The 0.36 left over is the PFCE (+0.48) and D1 (−0.11) roundings, within Rs 5 crore.
- **New test: `test_class_a_flows_equal_their_sam_definition_on_the_balanced_sam`.** It runs plain SQL on `data/sam/2023-24/sam_entries_balanced.parquet`, with the anchored allowance taken on the prior, as in the build. All 47 class-A flows are within max(Rs 5 crore, allowance): F35 −0.50, M13 −1.61, M12 −0.11, F01 −1.00. The guards are clean for all 68 flows with SAM terms: no unlisted ref, no missing selector, no entry matched twice. `sam_eval` gained a `table` argument, and both entry tables carry an `allow_base` column.
- **Note on M13.** −1.61 passes here (class-A tolerance Rs 5 crore, plan s.7). It fails closure's `tests/sam/test_sam_identities.py::test_household_gdi`, whose tolerance is 1.0. That is a tolerance choice for the orchestrator (the balance run's item 3), not a time-series defect.

### Results

- `tests/verify/test_timeseries_spotcheck.py`: 20 passed. Before this pass: 18 passed, 1 failed (the class-A test, closure-18). `ruff check` and `ruff format --check` are clean.
- `tests/timeseries`: 34 passed. The two balanced-SAM tests now run instead of skipping.

**The s.1.3 predictions against the balanced run** (`top_flows_sam_check.parquet` after `timeseries` was re-run):
- As predicted: F17, F20, F21, F22, F23 and M08 pass. F25 passes (−5,614.30 against 11,018.68).
- F26 passes, but close to its tolerance: +3,981.05 against 4,949.11. The prior's −960.40 is fincorp's SDL estimate. Balancing adds +4,941.45 and puts fincorp's `r3b.states_nas_concept` on its +1% ceiling, which binds. Without a prior or band change the residual cannot exceed about +3,986 (timeseries-28).
- M14 passes (−20,037.42 against 34,655.19).
- F18 and F19 now pass: balancing brought them back toward cash.
- The other ten class-C/D flows are `explained` by the maintainer's `explained_residual` items. These were written in this wave by the same agent, so they are not independently verified (see below).

### Independence (SPEC s.3 rule 3)

- This pass is independent of the wave-B fixer.
- The same wave-C agent also did the time-series maintainer work in this wave: the `timeseries` re-run and the ten `explained_residual` items in `pipeline/timeseries/explanations.yaml`. It also made the two test changes above.
- Those items have **not** been checked by a different agent. A later verifier should recompute the decompositions quoted in each `why`. They are read from the balanced entries, the blocks' satellites (`gov_grants_bridge`, `s4_fsf_dual_reports`), `balancing_constraints.parquet` and clean FSF/NAS series.
