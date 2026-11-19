# Phase 3 plan: The Map (website v1)

For: the builder agents (units U1 to U6), the independent verifiers (V1 to V5) and the orchestrator. Written 2026-10-02 on branch `phase3-map`, after Checkpoint B was approved (DECISIONS D3-0, D3-1). **Revision 2** (same day): rewritten after two independent reviews (economics/data and UX/engineering). Every review item and what was done about it is in Appendix A. Every number in this plan that changed in revision 2 was recomputed from the parquet files (scripts in the orchestrator's scratchpad; V1 re-derives them independently).

This plan is the contract for tonight. SPEC.md still overrides it. Where this plan and `docs/phase0/STACK_AND_REPO.md` differ, this plan wins, and the difference is listed as a proposed decision in section 8. Nothing here has been committed. **Builders and verifiers never commit, push or deploy.** The orchestrator commits (D3-1), and the preview deploy is gated (section 7.3).

Read first: `SPEC.md` (§3 rules, §6 Phase 3, §7 tech), `CLAUDE.md`, `DECISIONS.md`, `docs/phase2/CHECKPOINT_B.md` (especially §6b and §8, "What Phase 3 can rely on, and what it must label"), `docs/phase2/SAM_GUIDE.md` (§9 provenance, §11 outputs), `docs/phase0/STACK_AND_REPO.md` decisions 16 to 25, and `docs/phase0/ACCOUNT_STRUCTURE.md`.

Units in this plan: money is ₹ crore unless it says "lakh crore" (1 lakh crore = 1,00,000 crore). GDP 2023-24 = ₹290.73 lakh crore.

---

## 0. The plan in one page

- **What we ship tonight:** a static Next.js 16 site under `/en/` with five parts:
  1. the Map: an unrolled circular-flow diagram of the balanced 2023-24 SAM. It opens on a **simple** view (11 nodes: producers, factors, households, companies, banks, taxes, Centre, States, saving and investment, rest of world, discrepancies) and zooms to the full 13 groups, 27 sub-groups and 128 accounts;
  2. a time slider over all 76 years, 1950-51 to 2025-26, driving a "top flows" view built from the 69-flow time series;
  3. a flow detail panel showing value, % of GDP, trend, a plain-English explanation, status and sources;
  4. a canvas SAM heat-map with an accessible table;
  5. three guided stories, and a Methodology & sources page.
- **The first screen teaches something in 60 seconds** (SPEC §1), on a phone, with no interaction: a one-sentence headline, two or three headline figures with status badges, and three story cards, above the map (§4.0). A Playwright test checks this at 375×812.
- **Phones get a phone view.** Below 640 px the Sankey is not squeezed: the map becomes a list of the simple view's nodes with tappable "money in / money out" lists. The full diagram stays available in a scrollable panel (§4.5.9).
- **The data bridge is one command:** `uv run python -m pipeline export`. It is deterministic and writes compact JSON to `web/public/data/<data_version>/`. Every number on the site comes from that JSON. A generated, balanced fixture with the same shape lets the web units start before the real export exists (§3.10).
- **Honest labels:** each figure shows two things. The **total** says whether the sum is held to a published figure ("Official total"). The **split** says how its parts were made (official, derived, estimated, or set by balancing). "Set by balancing" is reserved for moves that matter (§3.4).
- **Honest time slider:** the full balanced picture exists only for 2023-24. Other years show the "top flows" view with its own banner. Both views size ribbons as a **share of GDP**, so they are comparable. There is no interpolation and no back-casting of the SAM.
- **Six units with strict file ownership:** U1 data export, U2 platform, U3 Map, U4 matrix, U5 stories, U6 methodology and map text (§6.2). Change requests go in `docs/phase3/requests/<your unit>.md`.
- **Gates:** `just test` (Python plus vitest, on Node 24 only) and `just test-web` (build, first-load budget, Playwright and axe), plus five verifier reports, then the Checkpoint C report. The protected Vercel preview needs the owner's go-ahead on the Vercel account (§9, Q2).

---

## 1. What exists (inspected 2026-10-02, not from memory)

**Balanced SAM** (`data/sam/2023-24/`, certified run: 83 Newton iterations, largest residual 2.32e-07 crore):

| File | Rows | Columns that matter |
|---|---:|---|
| `sam_balanced.parquet` | 2,203 cells (2,169 non-zero, 66 negative; all survive rounding to 2 dp) | `row` (receives), `col` (pays), `value` (₹ crore) |
| `sam_entries_balanced.parquet` | 3,893 entries | `row, col, ref, component, value, status, prior_status, role, tol_rel, confidence, bop_function, prov_id, note, block, prior, balanced, change` |
| `balancing_log.parquet` | 3,893, same row order as the entries | adds `weight, pct_change, polish_change, gras, gras_diff, gras_finding, binding` (comma-joined constraint ids), `explanation_required` (223 entries), `explained`, `cell_explanation_required` |
| `constraints.parquet` | 429 | `constraint_id, kind` (equal 304, band 93, max 22, min 10), `rows, cols, refs, components` (the member selector), `target, tol_abs, tol_rel, prov_id, description` |
| `balancing_constraints.parquet` | 429 | `constraint_id, lo, hi, prior_sum, balanced_sum, n_members, binding, ref, target`. **It has no `kind`; join it to `constraints.parquet`.** Binding: 125 equal, 48 band, 1 min. |
| `_provenance.parquet` | 453 records | Phase 1 provenance schema (`prov_id, source_id, url, retrieved_at, table_id, locator, unit_as_published, conversion, price_basis, base_year, vintage, status, method, inputs, notes`, …). **`url` and `retrieved_at` are null on every SAM record.** URLs come from walking `inputs` to the 1,735 clean records in `data/clean/*/_provenance.parquet` (59 of which have no URL themselves). |
| `blocks/*_satellites/*.parquet` | | e.g. `taxes_satellites/p7b_tax_by_use.parquet` (product taxes by tax account × commodity × use type `ic, pfce, gfce, gfcf, valuables, cii, exports`; status `estimated`; built on the **prior**, not the balanced SAM), `rest_of_world_satellites/s3_remittance_sources.parquet`, `closure_satellites/xdisc_identity.parquet` |
| `balancing_run.json` | | keys `status, iterations, max_imbalance, certificate, objective, solver, counts, …` |

Entry status crosstab (status / prior_status / role → count; ₹ lakh crore of absolute balanced value):
- balanced / estimated / free → 2,119 (1,085.97);
- official / official / anchored → 923 (747.79);
- estimated / estimated / free → 509 (97.66);
- official / official / fixed → 162 (136.98);
- balanced / derived / anchored → 60 (77.02);
- balanced / official / anchored → 42 (376.89; they moved ₹236 crore in all);
- derived / derived / anchored → 37 (73.37);
- derived / derived / fixed → 17 (73.55);
- estimated / estimated / fixed → 16 (7.26);
- balanced / derived / free → 7 (1.63);
- balanced / official / free → 1 (0.0007).

`status = balanced` means "moved ≥ ₹1 crore by balancing" (`pipeline/sam/spec.py` `MATERIAL_CHANGE`), and `prior_status` keeps the original. Of the 2,127 free entries with that status, 1,272 moved by less than 1% (median move 0.43%). **So `status = balanced` alone is not a useful public label** (§3.4).

The explanation threshold is `pipeline.sam.spec.needs_explanation`: a move ≥ ₹5,000 crore, or ≥ ₹500 crore and ≥ 10%. Explanations with verdicts are in `pipeline/sam/explanations/<block>.yaml`; `pipeline.sam.report.current_items(log, load_explanations())` returns the ones that apply to this run (223 entry items: 151 explained, 64 level unexplained, 8 unexplained; 103 cell items: 73, 26, 4), and `report.verdict()` reads the verdict word. The entries use 84 gap-map refs and 326 components; ref descriptions are in `data/gap_map.csv`.

**The X_DISC account is not one "residual".** It holds five different things (verified in the entries and `data/gap_map.csv`):

| Ref | Cells | ₹ lakh crore | What it is | Status of the parts |
|---|---|---:|---|---|
| D1 | X_DISC ← 10 household groups | 5.71 | Household residual: NAS household GDI − PFCE − household saving | Total published (M12 passes); the 10-group split is **estimated** (pro rata to gross income) |
| D2 | R_ROW ← X_DISC | 2.12 | NAS–BoP CIF reconciliation on imports of services | official. gap_map: "never as money paid abroad" |
| D3 `unsectored_valuables` | K_HH ← X_DISC | 2.04 | Valuables with no institutional sector, financed through X_DISC | derived |
| D3 `si_errors` | K_NFPR, K_NFPU, K_BANK, K_NBFC, K_INSP, K_RBI ← X_DISC | 1.55 | Saving–investment errors and omissions, assigned to sectors | Total published; the sector split is **estimated** |
| D4 | 34 commodity cells ← X_DISC | 0 | GDP expenditure discrepancy | official; **zero in 2023-24** (NAS 1.1) |

**Accounts** (`pipeline/sam/accounts.yaml`, the only source of matrix order) have 128 codes in 14 groups: ACT 34, COM 34, MRG 1, FAC 4, HH 10, NFC 2, FC 4, GOV 2, TAX 12, ROW 1, CAP 11, DSTK 1, INST 11, DISC 1. `pipeline/sam/structure.yaml` lists the allowed blocks. `pipeline.sam.accounts.Accounts.load()` reads both files. `pipeline.sam.balance.gras` is a sign-preserving RAS (used for the fixture, §3.10).

**Time series** (`data/timeseries/`):
- `top_flows.parquet` has 2,504 rows: 69 flows (54 core `F01`–`F54`, 15 memo `M01`–`M15`) over 76 FY periods, 1950-51 to 2025-26.
  - Columns: `flow_id, period, value, unit (INR_crore), price_basis, base_year (2011-12 | 2022-23 | null), variant, segment, datasets, series_ids, estimate_stage, vintage, status (official 1,871 | derived 633), flags, prov_id, note`.
  - Variants: `published` 2,006, `linked_2022_23` 476, `fc16_definition` 6 (F29), `proxy_total_portfolio` 16 (F52).
  - `flags`: `base_overlap` 136 rows, `segment_join` 34, `base_change` 7 (F36, F37, F39–F42, M09 at 2011-12), `concept_break` 1 (F18 at 2017-18). Segments splice sources: NB back series, NO 2011-12 to 2023-24, NN from 2022-23, NP for 2025-26; F23 and F24 switch from the FC16 transfers table to RBI State Finances at 2007-08.
  - The main-series rule in §3.7.1 gives exactly one candidate per flow-period (checked: 0 ties).
  - **Negative main values exist** (after the selection rule): F11 72 periods, F32 14, M10 8 (inventories), F49 3 (current-account deficit: 2002-03, 2003-04, 2020-21 were surpluses), F52 3, F54 3, F48 2, F40, F53, M12 one each; F13 and F30 (subsidies, `display_sign = −1`) are negative by convention.
- `top_flows_definitions.parquet`, per flow: `name, group, tier, display_sign`; SAM checks `check_class, sam_terms, excluded_refs`; linking `segments, link_policy` (linked for 10 flows), `link_reason, link_ratio_2022_23`; text `first_period, last_period, explanation, breaks`.
- `top_flows_sam_check.parquet`: 57 pass, 11 explained, 1 no_check (M15). Examples that matter for the panel: F14 (GST to the Centre) series 9.57 vs SAM 10.11 lakh crore (+5.6%, explained); F24 (grants to States) 5.28 vs 6.77 (+28.2%, explained; the SAM includes capital grants R2k and the cess-loan transfer); F25 (Centre's interest) has 2 periods only and is "explained".
- Coverage of the published variant: 12 flows in 1950-51, 22 in 1990-91, 50 in 2011-12, 69 in 2022-23, 68 in 2023-24, 56 in 2024-25 and 18 in 2025-26 (the PE year).
- GDP is `M01`. For 2023-24 the new-base value is ₹2,90,73,286.73 crore (NAS 2026; CHECKPOINT_B §1).

**Pipeline conventions to reuse** (`pipeline/core/io.py`): `write_json` / `dumps_json` (sorted keys; `indent=None` gives compact separators; `allow_nan=False`; −0.0 normalised; LF), `atomic_write_bytes`, `canonical_float`. `pipeline/core/manifest.py`: `repo_lock(layout)`, and `code_hash` (hashes `.py .yaml .json`). `pipeline/core/paths.py`: `Layout`, `REFERENCE_YEAR`. The CLI is `pipeline/cli.py`, re-executed with the pinned environment by `pipeline/__main__.py`. `tests/hygiene/test_hygiene.py` fails on any `group_by`/`unique` without order control in `pipeline/**/*.py`, and on CRLF. pytest runs with `--strict-markers`.

**Reusable functions:** `pipeline.timeseries.build.load_definitions()` and `eval_sam(flow, entries)`; `pipeline.sam.report.load_explanations`, `current_items`, `verdict`, `cell_changes`; `pipeline.sam.balance.band_of` and the member selector in `problem_from_frames` (reuse it to compute constraint members; do not re-implement it differently).

**Licence constraint that shapes the UI:** DECISIONS D1-1(d), ISSUES P1-9 and P0-7, and CHECKPOINT_B §8. **RBI series are for internal processing only; RBI pages may not be deep-linked or cached until RBI grants permission.** This covers RBI survey figures used in stories (the remittance survey, §4.9). MoF, SEBI, GSTN, DGCI&S and CAG permissions are outstanding. These block the public launch, not a private preview.

**Environment (checked on this machine):**
- `/opt/homebrew/bin/node` is **v26.10.0 and comes first on PATH**. Node 24 (v24.21.0, npm 11.19.0) is keg-only at `/opt/homebrew/opt/node@24/bin`. Every web command must use Node 24 explicitly (§4.15, §5).
- The OS is macOS 27.0 (build 26A425). Whether Playwright 1.63's WebKit runs on it is unverified (R2).
- `just` is not installed; every recipe is a one-line wrapper, so the underlying command works. No Playwright browsers are cached, and there is no Vercel CLI.
- npm latest today: `next` 16.3.8, `next-intl` 4.14.8, `d3` 7.9.0, `typescript` 6.0.3, `@playwright/test` 1.63.0, `vitest` 5.0.3, `@axe-core/playwright` 4.13.0, `@next/mdx` 16.3.8.

---

## 2. Scope of v1, mapped to SPEC §6 Phase 3

| SPEC bullet | v1 delivers | Not in v1 |
|---|---|---|
| Interactive flow visualisation with zoom levels whole economy → sector → sub-flow | An unrolled circular-flow Sankey of the 2023-24 SAM. **Simple view** (default, 11 nodes). **Level 0**, the full map, has 13 groups. **Level 1** has 27 sub-groups (a group with one account shows the account). **Level 2** is the 128 accounts. Zoom is semantic: select a node and press `+` (or the "Expand" button in its panel) to split it into its children; breadcrumbs or `−` go back. Mixed zoom is allowed. "Sub-flow" = the entries inside a cell (gap-map ref × component), listed in the detail panel. | The 155×67 SUT drill-down (ACCOUNT_STRUCTURE D6) moves to v2 (§9, Q6). Chord view: optional for U4; not a Checkpoint C gate. |
| Time slider covers every year in the time series | A slider over all 76 periods, plus a year `<select>`. See §2.1. | Animated SAM for other years: no SAM exists for them. |
| Click any flow → value, share of GDP, trend, plain-English explanation, source links | Flow detail panel (§4.7), plus a static, build-time-rendered permalink page for every level-0 link and every time-series flow. | Static pages for level-1 and level-2 links (they use URL state). |
| Explain mode: guided stories | Three stories (§4.9). Every number is bound to export JSON. Three story cards on the first screen. | More stories. |
| Mobile-first, fast (static data), accessible, light/dark; English first, i18n-ready | A first screen built for a phone (§4.0) and a dedicated phone map view (§4.5.9). The default state is rendered to HTML at build time (§4.4). WCAG 2.2 AA: a table or list alternative for every chart, a specified keyboard model, ≥ 24 px targets on every control (the diagram marks rely on the 2.5.8 "equivalent" exception, §4.5.10), reduced motion. Light and dark tokens. next-intl with `/en/`, all text in message or content files. | Hindi text (the structure is ready). |
| "Methodology & sources" page honest about estimates and limits | `/en/methodology/`: methods, the label rules, what is estimated (CHECKPOINT_B §8 list), limits, sources with the link policy and attribution, and the data version. | |

### 2.1 The honest time slider (proposed D3-2)

The facts:
- The balanced SAM exists for one year, 2023-24.
- The time series has 69 flows with uneven coverage: 12 flows in 1950-51, 69 in 2022-23, 18 in 2025-26.
- There is a base break at 2022-23 (old base 2011-12, new base 2022-23), and many more source splices: 34 `segment_join` rows, 7 `base_change` rows, 1 `concept_break`, and source switches such as F23/F24 at 2007-08.
- Ten flows also have a derived series ratio-linked to the 2022-23 base.

The design:

1. **One slider, two views.** The slider has 76 stops (`1950-51` … `2025-26`), labelled by FY. Arrow keys move one year; Home and End jump to the ends; the ◀ ▶ buttons step. A year `<select>` next to it is the precise control (at 343 px the 76 stops are ~4.5 px apart; the thumb itself is ≥ 24 px). Play advances once a second. Under `prefers-reduced-motion`, Play still works but steps instantly with no transitions.
2. **Announcements:** an `aria-live="polite"` region says "2004-05: 24 of 69 flows have data" only when the user steps manually, pauses or stops Play, never on every tick of Play.
3. **At 2023-24** there are two views: **"Complete picture (balanced SAM)"** and "Top flows". The 2023-24 stop carries a visible "complete map" tick. How you arrive decides the view:
   - opening the site, a permalink, the toggle or the "complete map" tick → complete picture;
   - **scrubbing or playing the slider into 2023-24 from another year keeps the top-flows view**, so nothing re-lays out under the user's thumb; a "See the complete map for 2023-24" button sits in the banner.
4. **At any other year** the view is **"Top flows over time"**, with a persistent banner (text in `messages/en/map.json`):
   > "For {year} you are seeing the {n} largest flows we have annual series for. This view is not a complete, balanced account of the economy; that exists only for 2023-24."
5. **Switching between the views** (toggle or tick) is an explicit 300 ms crossfade (instant under reduced motion) plus the banner change, never a silent re-layout. The two views share node positions where they share nodes (§3.2 `ts_nodes`), and **both size ribbons as a share of GDP** with the same px-per-%-of-GDP scale (§4.5.3), so ribbon widths are commensurable across the switch.
6. **Top-flows view mechanics:**
   - Nodes are `ts_nodes` (the simple view with taxes, Centre and States merged into "Government", because most fiscal and expenditure series are general-government totals).
   - It draws only the ribbons listed in `ts/view.json` (§3.7.3).
   - Ribbon width is the flow's **share of GDP on the same base** (§3.7.2). ₹ crore is shown on hover, focus and in the panel.
   - Node slots are sized to the maximum over all years, so nodes do not move while scrubbing.
   - A flow with no value in a year is **not drawn**. It is listed under "No data for {year}". It is never interpolated or carried forward.
   - A flow whose value changes sign in a year (F49, M10) is drawn reversed that year with a "reversed this year" marker and its own text (§3.7.3 rule 4).
7. **Markers on the slider and in every trend chart**, generated from data, never hand-placed:
   - every `base_change`, `concept_break` and `segment_join` flag, and every segment boundary, as a tick with its note ("New GDP base (2022-23). Earlier years are on the 2011-12 base; levels are not directly comparable, shares are closer."; "Source changes from FC16 tables to RBI State Finances");
   - the estimate stage: "provisional" for PE (2025-26) and FRE/SRE/TRE as published.
   `test_series.py` and a vitest test check that every flag in the parquet appears as a marker.
8. **Linked series:** flows with `link_policy = linked` offer a "show linked series (derived)" switch in the trend chart. It is off by default, and the derived series is labelled.
9. **Selecting a SAM flow while the slider is on another year:** the panel shows the 2023-24 SAM value, says so, and shows the matched time series (§3.7.4) for the slider year. If no series matches: "No annual series; only the 2023-24 SAM value exists."
10. **URL:** slider moves use `replaceState`, so Back does not step back through years; Back restores selection and zoom (pushState). `map.spec.ts` tests exactly that.

---

## 3. The data export contract (owner: U1)

### 3.1 Command, determinism, versioning

- **Command:** `uv run python -m pipeline export [--out DIR] [--check] [--fixture]`, and `just export`.
  - It adds an `export` subparser in `pipeline/cli.py` that calls `pipeline.export.build.cmd_export(layout, args)`.
  - Code lives in `pipeline/export/` (a package: `__init__.py, build.py, hierarchy.py, provenance.py, status.py, pinned.py, timeseries.py, stories.py, formats.py, fixture.py`), plus config, curated lists and schemas (§6.2).
- **Inputs (read-only):**
  - `data/sam/2023-24/{sam_balanced, sam_entries_balanced, balancing_log, constraints, balancing_constraints, _provenance}.parquet`, `balancing_run.json`, `blocks/*_satellites/*.parquet` (stories only);
  - `data/timeseries/*.parquet`; `data/clean/*/_provenance.parquet`; named clean datasets (stories only);
  - `data/registry.yaml`, `data/gap_map.csv`, `pipeline/sam/accounts.yaml`, `pipeline/sam/explanations/*.yaml`;
  - `pipeline/export/*.yaml`, `pipeline/export/stories/*.yaml`.
- **Output:**
  - `web/public/data/index.json` (unversioned, small);
  - `web/public/data/<data_version>/…` (immutable). `data_version = "2023-24." + sha256(canonical JSON of the files map in index.json)[:10]`.
  - After a successful write, the exporter deletes any other folder in `web/public/data/` whose name matches `^\d{4}-\d{2}\.[0-9a-f]{10}$`. It deletes nothing else.
  - `--fixture` writes the generated fixture to `web/fixtures/data/` instead (§3.10).
- **Determinism:** all JSON goes through `pipeline.core.io.dumps_json(obj, indent=None, decimals=None)` after explicit rounding (§3.3); no timestamps, hostnames or absolute paths; `group_by(..., maintain_order=True)` and explicit sorts; byte-identical output under `PYTHONHASHSEED` 0 and 1 (test).
- **Locking:** the exporter writes under `pipeline.core.manifest.repo_lock(layout)`. It writes the version folder first and replaces `index.json` last, atomically, so a running dev server never sees an index pointing at a missing folder.
- **`--check`:** exports into a temp folder and compares bytes with `web/public/data/`. It exits 1 and lists the differing files when they differ. `tests/export/test_export_current.py` runs it.
- **Not in `data/manifest.json`** (proposed D3-6): reproducibility is enforced by `--check` and the hash-seed test. `index.json` records the sha256 of every input file and `export_code_hash` (sha256 over `pipeline/export/**`).
- **No silent fallbacks.** The exporter fails with a message naming the item when: a provenance id does not resolve; a time-series period has two candidate rows for the main series; an account is missing from the hierarchy; a story figure selects nothing; a source id is not in the registry; a value is non-finite; an entry matches no label branch (§3.4); a curated list names an id that does not exist; a ribbon has a negative year and is not marked `reversible` (§3.7.3). Warnings that are not failures are printed and written to `docs/phase3/issues/U1.md`.

### 3.2 The account hierarchy for semantic zoom: `pipeline/export/hierarchy.yaml` (committed)

Rules:
- Every one of the 128 accounts appears exactly once as a leaf.
- A group with one account is not created: the account is the node.
- Ids: level-0 ids are UPPER words; level-1 ids are `<L0>.<WORD>`; level-2 ids are the account codes.
- `order` is the global vertical order. `col` is the level-0 column of the unrolled layout (§4.5).
- Children inherit their parent's `col`.

| L0 id | Plain name (English text lives in map-text.json) | col | Level-1 children (accounts) |
|---|---|---|---|
| PRDS | Goods & services (product markets) | 0 (payer copy) and 8 (receiver copy) | `PRDS.AGRI` (C_CROP, C_LVST, C_FOFI), `PRDS.MINE` (C_COAL, C_OILG, C_OMIN), `PRDS.MANU` (C_FOOD, C_BVTB, C_TXAP, C_WOOD, C_GJOM, C_RPET, C_CHEM, C_PHRM, C_NMMN, C_MTLS, C_MACH, C_ELEQ, C_TREQ), `PRDS.CNUT` (C_CNST, C_UTIL), `PRDS.TTC` (C_TRAD, C_HOTL, C_TRNS, C_COMM), `PRDS.FIRE` (C_FINS, C_INSR, C_DWEL, C_BSRE, C_ITSV), `PRDS.PSOC` (C_EDUC, C_HLTH, C_OSRV, C_PADM), leaf `M_TTM` |
| PROD | Industries (production) | 1 | `PROD.AGRI` … `PROD.PSOC` (the same split over A_*) |
| ROW | Rest of the world (current account) | 1 | leaf `R_ROW` |
| FACT | Wages, mixed income and profits (factor incomes) | 2 | `FACT.LAB` (F_LREG, F_LCAS), leaves `F_MIXD`, `F_GOSC` |
| HH | Households | 3 | `HH.RUR` (H_R1..H_R5), `HH.URB` (H_U1..H_U5) |
| NFC | Companies (non-financial) | 3 | leaves `E_NFPU`, `E_NFPR` |
| FC | Banks and financial institutions | 3 | leaves `E_RBI`, `E_BANK`, `E_NBFC`, `E_INSP` |
| TAX | Taxes (collection accounts) | 4 | `TAX.GST` (T_CGST, T_SGST, T_GCES), `TAX.OIND` (T_CUST, T_UEXC, T_SVAT, T_SEXC, T_OPRT), `TAX.DIR` (T_PIT, T_CIT), leaves `T_PSUB`, `T_PROD` |
| CEN | Union government | 5 | leaf `G_CEN` |
| STA | States and local bodies | 5 | leaf `G_STA` |
| SI | Saving and investment (capital accounts) | 6 | `SI.CORP` (K_NFPU, K_NFPR), `SI.FIN` (K_RBI, K_BANK, K_NBFC, K_INSP, K_MUTF), `SI.GOV` (K_GCEN, K_GSTA), leaves `K_HH`, `K_ROW`, `K_DSTK` |
| DISC | **Discrepancies and reconciliation items** | 6 | leaf `X_DISC` |
| FINM | Financial markets (instruments) | 7 | `FINM.MONEY` (I_CURR, I_DEPO), `FINM.GOVD` (I_GSEC, I_SSAV), `FINM.SEC` (I_CBND, I_EQTY, I_MFUN), `FINM.OTH` (I_RESV, I_OTHR), leaves `I_LOAN`, `I_INPE` |

**Counts:** 13 level-0 nodes, 27 level-1 groups, 128 accounts (168 hierarchy nodes).

**Presets** (also in the YAML, `presets:`). A preset is a set of merges applied on top of level 0:
- `simple` (the default): `PRODUCERS` = PRDS + PROD, a split node drawn at column 0 (payer copy) and the last column (receiver copy); `SI` absorbs FINM. 11 nodes. Flows inside a merged node are internal (listed, not drawn). Return flows are drawn as stubs, not arcs (§4.5.6).
- `full`: level 0 as in the table.
- Expanding any node in `simple` switches the rest of the map to `full` first, then expands, so zoom always starts from the 13 groups.

**Prototype check** (recomputed for revision 2 from `sam_balanced.parquet`; the account cell is the atom, §4.5.3):
- `full`: 66 non-zero directed pairs, 4 of them internal (margins inside PRDS 79.20 lakh crore, NFC→NFC 2.56, FC→FC 4.29, SI→SI 7.28). 9 external pairs contain negative cells, so level 0 draws **70 links** (61 positive parts, 9 negative parts).
- Negative parts at level 0 (₹ lakh crore): PRDS→TAX −5.76 (product subsidies, T_PSUB), TAX→CEN −2.71 and TAX→STA −3.63 (subsidies paid by the Centre and States through T_PSUB), PROD→TAX −2.86 (production subsidies), CEN→SI −4.27 (the Centre's negative gross saving), SI→FINM −8.55, FINM→SI −1.45, SI→PRDS −0.26 (inventory run-downs), PROD→PRDS −0.000001 (one ₹0.10 crore cell).
- Drawn node heights at level 0 (₹ lakh crore; drawn inflow = drawn outflow): PRDS 677.82 (each copy), PROD 578.51, FACT 265.25, SI 249.97, HH 245.74, FINM 145.39, ROW 80.15, NFC 64.27, TAX 60.70, CEN 43.80, FC 41.78, STA 38.79, DISC 5.71.
- `simple`: 61 drawn links (37 forward, 8 same-column carrying 73.84, 16 return carrying 46.90). The largest forward bands are the household story: PRODUCERS→FACT 264.63, FACT→HH 192.46, HH→PRODUCERS 164.16, SI→PRODUCERS 100.31, PRODUCERS→ROW 69.47, ROW→PRODUCERS 64.79, HH→SI 58.90. Internal: inside PRODUCERS 966.43 (intermediate use 311.59, output 575.64, margins 79.20); inside SI 288.06 positive and 10.00 negative (the financial round trip and SI→SI).
- Level 1 has 364 non-zero directed pairs (6 internal); 32 have a negative part, 21 of them net negative.

**Also in the YAML:**
- `ts_nodes`: the top-flows view nodes = the `simple` preset with TAX, CEN and STA merged into `GOV` (9 nodes: PRODUCERS, ROW, FACT, HH, NFC, FC, GOV, SI, DISC).
- `kinds`: a hue family per node kind (production, factors, households, corporations, government, rest of world, capital/finance, discrepancy). Token names only; hex values live in U2's tokens.

`tests/export/test_hierarchy.py` checks: every account appears exactly once; parent/child relations are consistent; `order` is unique; every level-0 node has a `col`; every preset and `ts_nodes` covers every account exactly once; the prototype figures above are reproduced (counts and node heights, to 0.01 lakh crore).

### 3.3 Units, rounding, formatting

**Money:** ₹ crore, current prices. SAM values for FY 2023-24. Time series by FY.

**Rounding in JSON:** money 2 decimals; shares and ratios 6 decimals; composition fractions 4 decimals. The exporter rounds with `canonical_float(x, d)` and dumps with `decimals=None`. Exported cells keep their sign.

**Share of GDP:** `value / GDP`.
- SAM figures use **M01 2023-24, base 2022-23, published** (₹2,90,73,286.73 crore). Its prov is the `timeseries:` record of that row (NAS 2026 Statement 1.1). The exporter also checks this equals GDP from the SAM's production side within ₹1 crore (CHECKPOINT_B §1 reports +0.61).
- Time-series shares use §3.7.2.
- **Framing line** (U3 puts it beside every "% of GDP" figure on a gross flow, from `map.json`): "Gross flows can exceed GDP. GDP counts only final output once; the map also shows the inputs firms buy from each other and the money that passes through financial markets." Without it, "Producers → Industries 198% of GDP" reads as an error.

**Display formatting** (one rule set; `web/src/lib/format.ts` implements it and `pipeline/export/formats.py` mirrors it for tests and verifiers):

| Kind | Rule | Example |
|---|---|---|
| `inr` | \|v\| ≥ 1,00,000 crore → `₹{v/1e5:.2f} lakh crore`. 1,000 ≤ \|v\| < 1,00,000 → `₹{round(v):en-IN} crore`. 10 ≤ \|v\| < 1,000 → `₹{round(v)} crore`. \|v\| < 10 → `₹{v:.1f} crore`. Negative: a leading "−" (U+2212). | ₹2.09 lakh crore; ₹25,102 crore |
| `pct_gdp` | ≥ 1% → 1 decimal; 0.01% to 1% → 2 decimals; < 0.01% → "<0.01%" | 0.72% of GDP |
| `per100` | ₹ per ₹100, 1 decimal: `₹{v:.1f}` | ₹46.9 |
| `pct` | Shares that are not of GDP, 1 decimal | 19.2% |

Grouping uses `Intl.NumberFormat('en-IN')`. The golden file `pipeline/export/golden/format_cases.json` (owner U1) holds about 40 input → output pairs that both implementations must reproduce (vitest and pytest).

### 3.4 Labels and flags (proposed D3-3, revised)

Two questions are answered separately, because a sum of estimated parts can be pinned to a published total:
- **Total label:** is this aggregate's sum held to a published figure?
- **Split label:** how were the parts made?

#### 3.4.1 Entry labels (the atoms)

Four entry labels. `pipeline/export/status.py` applies the branches in order; an entry matching none **fails the export**.

| # | Condition | Label | Panel text when the entry moved |
|---|---|---|---|
| 1 | `role = free` and `status = balanced` and **the move matters**: `explanation_required` (≥ ₹5,000 crore, or ≥ ₹500 crore and ≥ 10%), or the entry or its cell has a current explanation item (any verdict), or the entry is a member of a **judgement band** that binds (§3.4.3) | `balancing_set` ("Set by balancing") | "Balancing moved this from ₹{prior} to ₹{balanced}. {verdict and why}" |
| 2 | `prior_status = official` | `official` | "Adjusted by {pct}% in balancing, within its declared tolerance" (anchored) or "Adjusted by {pct}% in balancing" (free) |
| 3 | `prior_status = derived` | `derived` | same |
| 4 | `prior_status = estimated` | `estimated` | "Adjusted by {pct}% in balancing" |
| else | — | export fails, naming the entry | |

Result on the real data (recomputed): official 1,127 entries (₹1,261.66 lakh crore of absolute value), derived 114 (223.94), estimated 2,180 (802.71), set by balancing 472 (389.81); total 3,893 (2,678.11). Under revision 1's rule, 2,127 entries (₹1,087.6 lakh crore) were labelled "balanced", most for sub-1% moves.

#### 3.4.2 Aggregate labels (a cell, a link at any zoom, a story figure)

- **`split`** = `composition` (shares of absolute value by entry label: o, d, e, b, summing to 1) and the **headline split label**: the least certain label carrying ≥ 10% of the aggregate's absolute value (order: official < derived < estimated < balancing_set). The UI always shows the composition bar.
- **`total`** = `official` or `derived` when the aggregate's entry set is **exactly** a disjoint union of "pins", and the balanced sum of each pin is within its tolerance; otherwise `null`. A pin is either:
  - a constraint of kind `equal` or `band` whose width is ≤ max(₹1 crore, 0.1% of |target|) and whose prov status is official or derived (member entries computed with the pipeline's own selector, §1); or
  - a time-series flow whose 2023-24 SAM check verdict is `pass` (its entries via `eval_sam`).
  The total label is the least certain status among its pins (a time-series pin takes the status of its 2023-24 row).
- On the real data, **16 of the 62 level-0 pairs have an official or derived total** (as whole pairs), including HH→PRDS (PFCE, NAS; F01), HH→SI (household saving; F35), ROW→HH (remittances, R11 total; F43), FACT→HH (two constraints), PROD→FACT (covered by passing time-series flows), FC→SI, PRDS→ROW and ROW→PRDS (M04, M03), HH→DISC (M12) and DISC→ROW (M05).
- **Display:** a badge such as "Official total · split estimated" or "Estimated" (no total). Hover or focus shows the composition and which published figure pins the total ("Held to NAS Statement 1.14 PFCE within ₹1 crore").
- Because the browser cannot see entries, the exporter precomputes the total label for **every node pair at any zoom** that has entries (about 4,500 pairs, mixed zoom included), separately for the positive part (`<id>`), the negative part (`<id>~neg`) and the whole pair (`<id>~pair`), and exports only the pinned ones (`sam/pinned.json`, §3.6). A link not listed has no official total. When only the pair is pinned (e.g. PRDS→TAX: product taxes and product subsidies together are held to M07, net taxes on products), both parts' panels say so: "Together with the subsidy leg, held to …".
- `golden/status_cases.json` (U1) holds entry cases for every branch and aggregate cases, including **HH→PRDS, ROW→HH and HH→SI = official total**, NFC→SI = no total, and an unexplained E_NFPU cell = set by balancing. `status.ts` (U2) and `status.py` both pass it.

#### 3.4.3 Curated lists (`pipeline/export/`, owner U1, each with a test)

- **`judgement_bands.yaml`**: the binding bands that CHECKPOINT_B §6b says set a level by judgement. Exactly these 11 constraint ids: `government:gov.cofog.current_transfers`, `government:gov.cofog.capital_transfers`, `government:gov.r9d.railways`, `government:gov.r9d.posts`, `government:gov.r2.css_outside_treasury`, `government:gov.r18.psu_revenue_grants`, `taxes:t1.cgst`, `taxes:t1.gces`, `taxes:t1.uexc`, `factors:f4b.centre`, `taxes:t4a.nfpu` (97 entries). `test_status.py` asserts the list equals this §6b set and that each id is binding in this run. Rounding-tolerance bands (GFCE ±₹1 crore, NAS CIS ±₹0.1 crore, RBI saving ±₹2,500 crore) are not in it. The other 37 binding bands are not flagged; the panel lists every binding constraint of an entry with its description anyway, and U1 lists those 37 in `issues/U1.md` for the owner (are any of them §6b-type judgements?).
- **`old_base_scope.yaml`**: the prov ids whose method applies the D2-21 old-base sequence-of-accounts structure. It starts with the 4 records whose method cites D2-21 (`sam_fincorp:9262b50cc877, 9ea6c4e525b0, c1a4fab1d145, f6cf865ac4ad`; 26 entries, ₹7.70 lakh crore). U1 reviews the candidates the reviewers named (T4a corporation tax by sector, T3) against DECISIONS D2-21 and records each decision with a reason. A transitive walk is **not** used (it would reach 46 entries and ₹72 lakh crore, mostly not D2-21). The test checks every listed id exists and that the flagged entry set equals the list's entries.
- **`disc_text.yaml`**: the panel text for each X_DISC ref (§3.4.4).

#### 3.4.4 Flags (a bitmask on cells; a list on entries)

| Bit | Name | Rule | UI text (map.json) |
|---|---|---|---|
| 1 | `judgement_band` | Member of a binding constraint in `judgement_bands.yaml` | "Level set by a judgement band, not by data (Checkpoint B §6b)" |
| 2 | `unexplained` | Current explanation verdict "unexplained" (entry or cell) | "Balancing moved this and the reason is not yet documented" |
| 4 | `level_unexplained` | Verdict "level unexplained" | "Direction explained, level not" |
| 8 | `old_base_structure` | Prov id in `old_base_scope.yaml` | "Estimated with the old-base (2022-23 NAS) structure" |
| 16 | `discrepancy` | Row or column is X_DISC. Text per ref from `disc_text.yaml`: D1 "Published total (household residual); split across groups estimated"; D2 "NAS–BoP reconciliation item (CIF adjustment on services imports), not money paid abroad"; D3 valuables "Derived: valuables with no institutional sector"; D3 s-i errors "Published total (saving–investment errors and omissions); split by sector estimated"; D4 "GDP expenditure discrepancy: zero in 2023-24" | per ref |
| 32 | `has_negative` | Some entry in the aggregate is negative | explains a reversed ribbon |
| 64 | `depends_on_assumption` | The prov walk (§3.5) reaches a record with no URL leaf whose method is an assumption (today `sam_fincorp:ec21dc1c9670`, the R17 non-life household share; 6 SAM records take it as input) | "Uses a stated assumption; method one click away" |

CHECKPOINT_B §8 requires "estimated" on every household-group split, inter-institution property income, FC sub-sector split, Centre/State split, and K9 residuals and FSF counterparties. These come out `estimated` or `balancing_set` as split labels. V5 verifies that none shows an `official` split label.

### 3.5 Provenance and link policy (proposed D3-7)

- **Resolution:** for every prov id used by an exported entry, time-series row, constraint or story figure, the exporter walks `inputs` transitively through SAM, time-series and clean provenance (cycle-safe), collects the clean records with a non-null `url` ("leaves"), and groups them by `source_id` into `cites`. Checked: 0 unresolved ids; every one of the 283 entry prov ids and all 152 time-series prov ids reach at least one URL leaf; no prov id is duplicated across the SAM, time-series and clean files. One entry prov can fan out to 152 leaves.
- **Order of cites** (§4.7 shows the top 5): by **direct-input order** (the order of `inputs` on the record nearest the entry), then by how many of the aggregate's entries cite the source, then by source id. The walk carries no value weights, so revision 1's "ranked by value share" is dropped.
- **Link policy:** `pipeline/export/link_policy.yaml` maps URL hosts to `deep`, `landing` (registry `urls.landing` only) or `withheld` (no link). Initial file: `rbi.org.in`, `www.rbi.org.in`, `rbidocs.rbi.org.in`, `data.rbi.org.in`, `dbie.rbi.org.in`, `cimsdbie.rbi.org.in` → `withheld` (D1-1(d)); every other host → `deep`. 514 leaf URLs are on RBI hosts. A test fails if any exported URL's host is `withheld` or unknown to the policy file. Withheld citations render the source name, publication, table id and retrieval date, with "Link withheld until RBI grants permission (ISSUES P1-9)".
- **Clean records without a URL** (59): cited by name and table only, with "no public URL recorded".
- **Attribution:** `sources[*].attribution` is copied from `registry.yaml` `license.attribution`. U6's sources table shows it.

### 3.6 Files and JSON shapes

TypeScript notation. `Cr` = number (₹ crore, 2 dp). `Share` = number (6 dp). `Idx` = integer index into `hierarchy.accounts`. Arrays in "columnar" objects all have length `n`. `Label = "official" | "derived" | "estimated" | "balancing_set"`.

```ts
// web/public/data/index.json  (unversioned)
type DataIndex = {
  schema_version: 2;
  data_version: string;                       // "2023-24.3f9a0c21be" or "2023-24.fixture0000"
  fixture: boolean;                           // true only in web/fixtures/data
  reference_year: "2023-24";
  gdp_base_year: "2022-23";
  inputs: Record<string, string>;             // repo path -> sha256
  export_code_hash: string;
  files: Record<string, { sha256: string; bytes: number }>;   // paths relative to <data_version>/
};

// <v>/summary.json  (first view)
type Summary = {
  gdp: { year: "2023-24"; value: Cr; prov: string; label: "official" };
  headline: {                                 // the first screen, section 4.0
    hh_outlays: { total: Cr; total_label: "official" | "derived" | null; prov: string[];
      parts: Array<{ key: "consumption" | "saving" | "taxes" | "financial_services_and_interest"
        | "transfers_abroad" | "to_government" | "unallocated_residual"; value: Cr; per100: number;
        split_label: Label }> };
    gdp_note: string | null;                  // message key, not prose
  };
  sam: {
    accounts: 128; cells_nonzero: number; entries: number; refs: number;
    grand_total: Cr;
    composition: { o: number; d: number; e: number; b: number };
    labels: Record<Label, { entries: number; abs: Cr }>;
    balancing: { status: string; iterations: number; max_imbalance: number;
                 moved_abs: Cr; moved_share_of_abs: number };
  };
  methodology: Record<string, { value: number; unit: "inr" | "pct_gdp" | "pct" | "count"; prov: string[] }>;
  ts: { flows: 69; core: 54; memo: 15; first: "1950-51"; last: "2025-26"; rows: number };
};

// <v>/hierarchy.json  (first view)
type Hierarchy = {
  nodes: Array<{ id: string; level: 0 | 1 | 2; parent: string | null; children: string[];
                 accounts: string[]; order: number; col: number; kind: NodeKind; expandable: boolean }>;
  accounts: Array<{ code: string; idx: Idx; group: string; l0: string; l1: string | null; name_tech: string }>;
  columns: string[][];                        // full view: level-0 ids per column; "PRDS" in col 0 and col 8
  split_node: "PRDS";
  presets: Record<"simple" | "full", { merges: Record<string, string[]>; columns: string[][];
                                       split_node: string; return_flows: "arcs" | "stubs" }>;
  ts_nodes: Array<{ id: string; accounts: string[]; order: number; col: number; kind: NodeKind }>;
};

// <v>/sam/cells.json  (first view; all 2,169 non-zero account cells, the atoms)
type Cells = {
  n: number;
  row: Idx[]; col: Idx[];                     // row receives, col pays
  v: Cr[];                                    // signed
  abs_o: Cr[]; abs_d: Cr[]; abs_e: Cr[]; abs_b: Cr[];   // abs value by entry label
  split: (0 | 1 | 2 | 3)[];                   // headline split label of the cell
  flags: number[];                            // bitmask, section 3.4.4
  n_entries: number[];
  refs: string[][];                           // distinct refs in the cell, by |value| desc
};

// <v>/sam/pinned.json  (first view, small) — official/derived totals, section 3.4.2
type Pinned = Record<string /* link id at any zoom, plus "~pair" ids, section 3.4.2 */,
  { total: "official" | "derived"; pins: string[] /* constraint ids or "ts:F01" */ }>;

// <v>/sam/entries/<L0 id>.json  (lazy; entries whose ROW account is in that L0 node; 13 files)
type Entries = {
  node: string;
  entries: Array<{
    row: string; col: string; ref: string; component: string;
    v: Cr; prior: Cr; change: Cr; pct_change: number | null;
    status: "official" | "derived" | "estimated" | "balanced";   // as in parquet
    prior_status: "official" | "derived" | "estimated";
    role: "fixed" | "anchored" | "free";
    label: Label;                             // section 3.4.1
    confidence: "high" | "medium" | "low" | null;
    bop_function: string | null;
    prov: string;
    flags: string[];
    verdict: "explained" | "level unexplained" | "unexplained" | null;
    why: string | null;
    binding: string[];                        // constraint ids
  }>;
};

// <v>/sam/constraints.json  (lazy)
type Constraints = Record<string, { kind: "band" | "equal" | "max" | "min"; ref: string;
  description: string; target: Cr; lo: Cr | null; hi: Cr | null; balanced_sum: Cr;
  binding: boolean; judgement: boolean; prov: string }>;

// <v>/sam/refs.json  (lazy) — the 84 refs from data/gap_map.csv
type Refs = Record<string, { row_block: string; col_block: string; description: string;
  gap_status: string; primary_source: string; method: string }>;

// <v>/provenance.json  (lazy; split into provenance/<prefix>.json if it exceeds 120 KB gzipped)
type Provenance = {
  records: Record<string, {
    source: string; status: "official" | "derived" | "estimated"; table: string; locator: string | null;
    method: string; vintage: string | null; base_year: string | null; price_basis: string; unit: string;
    conversion: string | null; assumption: boolean; depends_on_assumption: boolean;
    cites: Array<{ source: string; tables: string[]; urls: Array<string | null>;
                   withheld: boolean; retrieved: [string, string] }>;   // ordered, section 3.5
  }>;
  sources: Record<string, { name: string; publisher: string; landing: string | null;
    link_mode: "deep" | "landing" | "withheld"; licence: string; attribution: string;
    registry_status: string }>;
};

// <v>/ts/series.json  (loaded after first paint)
type Series = {
  periods: string[];                          // 76
  gdp: { main: (Cr | null)[]; main_base: (string | null)[]; linked: (Cr | null)[]; prov: (string | null)[] };
  flows: Array<{
    id: string; tier: "core" | "memo"; group: string; display_sign: 1 | -1; name_tech: string;
    check: { class: string; verdict: "pass" | "explained" | "no_check";
             ts_value: Cr | null; sam_value: Cr | null; rel_diff: number | null; explanation: string | null };
    link_policy: "linked" | "refused"; link_reason: string | null;
    markers: Array<{ period: string; kind: "base_change" | "concept_break" | "segment_join" | "segment"
                     | "break"; note: string }>;       // every flag and segment boundary, section 2.1
    main: SeriesArrays; linked: SeriesArrays | null;
    alts: Array<{ variant: "fc16_definition" | "proxy_total_portfolio"; arrays: SeriesArrays }>;
  }>;
};
type SeriesArrays = { v: (Cr | null)[]; share: (Share | null)[]; base: (string | null)[];
  status: ("official" | "derived" | null)[]; stage: (string | null)[]; flags: (string | null)[];
  segment: (string | null)[]; prov: (string | null)[] };

// <v>/ts/view.json  (first view of the top-flows board)
type TsView = {
  coverage: number[];                         // per period: flows with a main value
  ribbons: Array<{ flow: string; from: string; to: string; reversible: boolean;
                   reversed_text_key: string | null }>;   // ts_nodes ids; money flows from -> to
  internal: Record<string /* ts node */, string[] /* flows listed in that node's panel */>;
  slot_share: Record<string, Share>;          // per ts node: max over years of max(in, out) share
};

// <v>/ts/cover.json  (lazy) — which SAM cells each series measures in 2023-24 (signed values)
type Cover = Record<string, { cells: Array<[Idx, Idx, Cr]>; abs_total: Cr }>;

// <v>/stories/<slug>.json  (lazy, per story) — section 3.8
type Story = {
  slug: string;
  figures: Record<string, { value: number; unit: "inr" | "pct_gdp" | "per100" | "pct";
    total: "official" | "derived" | null; split: Label; composition: { o: number; d: number; e: number; b: number };
    flags: string[]; prov: string[]; method: string; note_key: string | null }>;
  steps: Array<{ id: string; view: { view: "sam" | "ts"; preset: "simple" | "full"; year: string;
    expanded: string[]; highlight: string[]; select: string | null }; figures: string[] }>;
};
```

**Ids used across the site:**
- Node id: a hierarchy id (or a preset id: `PRODUCERS`, `GOV`).
- **Link id** `<payer>--<receiver>` for the positive part, and `<payer>--<receiver>~neg` for the negative part (drawn reversed, receiver → payer). Money flows from the column account to the row account. Examples: `HH--PRDS`, `PRDS--TAX~neg` (product subsidies, drawn Taxes → Goods & services).
- Time-series flow id: `F01`.

### 3.7 Time series in the export

#### 3.7.1 Main series, one value per period, no silent choice

For each flow and period, take the `published` rows: base 2022-23 if present, else base 2011-12, else the single row with `base_year = null`. More than one candidate at the same priority fails the export (checked today: none). `linked` takes the `linked_2022_23` rows before 2022-23 and the main new-base rows from 2022-23 on. Other variants go to `alts`, labelled. Values are exported as stored; the UI multiplies by `display_sign`, so a subsidy shows as a positive "subsidy paid".

#### 3.7.2 Share of GDP on the same base

`share = value × display_sign / GDP(period, base)`, where GDP = M01 `published` for the same period, with the row's `base_year` when non-null; when null (fiscal, BoP and FSF series), base 2022-23 for periods ≥ 2022-23, else 2011-12. Linked series use the M01 `linked_2022_23` row. A missing denominator fails the export.

#### 3.7.3 Ribbons for the top-flows board (`pipeline/export/ts_view.yaml`, owner U1)

A flow may be a ribbon only if all five rules hold. `tests/export/test_ts_view.py` checks them mechanically:
1. Every SAM term in its `sam_terms` maps, through `ts_nodes`, into one (payer → receiver) pair of different nodes, equal to the declared `from` → `to`. Flows whose terms fall inside one ts node go to `internal` (listed in that node's panel).
2. No two ribbons share a SAM entry (prevents double counting, e.g. F03 GFCF and its parts).
3. Its main series has ≥ 10 periods.
4. **Sign:** if any main value × `display_sign` < 0, the YAML must mark the flow `reversible: true` with a `reversed_text_key` (that year's ribbon is drawn reversed with a marker), or the export fails. Flows that are a net of mixed-sign content by definition (F11, M09, M11) are never ribbons.
5. Its 2023-24 SAM check is `pass` or `explained` (the check text is shown in the panel).

Starting list (U1 confirms each against the rules and records any rejection with its reason):
- F01 HH→PRODUCERS; F02 GOV→PRODUCERS; F03 SI→PRODUCERS; M10 SI→PRODUCERS (inventories; `reversible`, 8 negative years: "inventories ran down");
- M03 ROW→PRODUCERS (exports); F07 PRODUCERS→ROW (imports of goods, 2011-12+);
- F09, F10 PRODUCERS→FACT;
- F35 HH→SI; F45 NFC→SI; F49 ROW→SI (`reversible`, 3 surplus years: "current-account surplus: India lent to the rest of the world");
- F43 ROW→HH; F44 HH→ROW;
- **M07 PRODUCERS→GOV, "net taxes on products"** (taxes on products less product subsidies; from 1950-51).
- Internal to GOV, listed in its panel: F21 corporation tax, F22 income tax (2022-23 on), F18 State VAT, F19 State excise, F23 devolution, F24 grants. Revision 1's separate TAX node, which made product taxes appear to "become" corporation tax, is gone.

Every flow not drawn appears in the board's list view with its value and share.

#### 3.7.4 Matching SAM flows to series (the "trend" in the detail panel)

`ts/cover.json` gives, for each series, the SAM cells it measures in 2023-24 (signed, via `eval_sam`) and `abs_total` = Σ|covered|. For a clicked link L (at any zoom):
- `inside` = Σ|covered cells in L| / `abs_total` (how much of the series lies in L);
- `covers` = Σ|covered cells in L| / Σ|cells of L| (how much of L the series explains).

| inside | covers | Panel |
|---|---|---|
| ≥ 95% | ≥ 99.5% | "Trend" (the same flow) |
| ≥ 95% | < 99.5% | "Related series (covers {covers}% of this flow)" |
| 50% to 95% | any | "Overlapping series ({inside}% of it is in this flow; the rest is {where})", e.g. F24 grants on Centre→States: the rest is capital grants inside Saving and investment |
| < 50% | | not shown |

Every trend chart **plots the SAM 2023-24 value as a separate marker** with the check text (`pass`, or `explained` with its explanation; "explained", not "confirmed", per CHECKPOINT_B §8), so a gap such as F14 (series 9.57, SAM 10.11 lakh crore) is visible, not hidden. A series with fewer than 3 periods (F25 has 2) is shown as "values", not "trend".

### 3.8 Story figures (`pipeline/export/stories/<slug>.yaml`, owner U5; evaluator owner U1)

```yaml
slug: gst-rupee
figures:
  gst_total:
    kind: sam_sum                    # sam_sum | entries_sum | satellite_sum | satellite_share | clean_value
                                     # | ts_value | ratio | product | difference | per100
    terms: [{rows: [T_CGST, T_SGST, T_GCES], cols: "@COM"}]     # account codes, @GROUP or node:<id>
    unit: inr
  gst_total_gdp: {kind: ratio, num: {ref: gst_total}, den: {gdp: "2023-24"}, unit: pct_gdp}
  cgst_on_pfce:
    kind: satellite_share            # p7b shares applied to the BALANCED total
    table: taxes/p7b_tax_by_use
    share_of: {tax_account: T_CGST, component: total, use_type: pfce}   # numerator
    within:   {tax_account: T_CGST, component: total}                   # denominator
    total: {kind: sam_sum, terms: [{rows: [T_CGST], cols: "@COM"}]}
    unit: inr
  uae_remittances:
    kind: satellite_sum
    table: rest_of_world/s3_remittance_sources
    where: {country: ARE, measure: inr_crore}
    unit: inr
```

- The evaluator (U1) resolves each kind and computes `total`, `split` and `composition` with §3.4; a ratio, product or difference takes the least certain split label of its parts and a total label only if every part has one.
- **`satellite_share`**: applies the satellite's shares (built on the prior) to the balanced total. Its split label is `estimated` and its method reads "prior split, rescaled to the balanced total". `test_export_stories.py` checks that the parts of every such family sum to the total within ₹0.01 crore. Revision 1 summed the p7b satellite directly, which does not add up to the balanced GST (CGST 8.34 vs 8.62 lakh crore, SGST 8.55 vs 8.29, cess 1.44 vs 1.49).
- It collects prov ids and generates a plain `method` string from the spec.
- A selector that matches nothing fails the export.

### 3.9 Where the plain-English text lives (proposed D3-8)

| Text | File | Owner | Shape |
|---|---|---|---|
| UI chrome | `web/messages/en/common.json` | U2 | next-intl ICU messages; namespaces merged at load |
| Map UI (first screen, banner, panel, slider, legends, flag texts, framing line) | `web/messages/en/map.json` | U3 | |
| Matrix and data page UI | `web/messages/en/matrix.json` | U4 | |
| Story UI (step controls, story titles and card blurbs) | `web/messages/en/story.json` | U5 | |
| Methodology UI | `web/messages/en/methodology.json` | U6 | |
| **Node, link, ref and series labels and one-sentence explanations** | `web/content/en/map-text.json` (labels and `short`) and `web/content/en/map-desc.json` (`desc`, lazy) | U6 | `{ nodes: {<id>: {label, short}}, links: {<link id>: {label}}, refs: {<ref>: {label}}, series: {<F01>: {label}} }` and `{ nodes: {<id>: desc}, links: {...}, refs: {...}, series: {...}, components?: {<ref>.<component>: label} }`. Coverage: all 168 hierarchy nodes plus `PRODUCERS` and `GOV`; every level-0 link id of the full and simple presets (positive and `~neg`, about 75); all 84 refs; all 69 series. |
| Story prose | `web/content/en/stories/<slug>.mdx` | U5 | MDX; numbers only through `<StoryFig id="…"/>` |
| Methodology prose | `web/content/en/methodology/*.mdx` | U6 | MDX; numbers only through `<DataFig path="sam.labels.estimated.abs"/>` bindings to summary.json |

`<StoryFig>` and `<DataFig>` are different components with different names, passed **per page** through the MDX `components` prop (stories pass `StoryFig`, methodology passes `DataFig`), never registered globally. U2's `src/mdx-components.tsx` registers neither (only typography). U2 creates both stubs at t0 in `components/ui/` so U5 and U6 compile. The `no-digits` test covers both MDX trees; the `fig-id` test (U5) checks `<StoryFig id>` against story JSON; a `data-fig-path` test (U6) checks `<DataFig path>` against summary.json.

Writing rules for all text:
- Plain English for a 15-year-old, without dumbing down the economics.
- Rows receive and columns pay, so say "X pays Y" or "money flows from X to Y".
- Never state a number in prose; numbers come from data bindings. `tests/unit/content/no-digits.test.ts` (U6) bans digit runs in MDX and map text, except FY labels (`\d{4}-\d{2}`), SNA codes in parentheses and names such as "15th Finance Commission".
- Name the concept precisely: "net borrowing (national accounts)" vs the Budget's "fiscal deficit"; "the Centre's negative gross saving (dissaving)", never "the Centre pays saving".
- Say "estimated" where the split label says so; say "official total" only where `total` says so.

### 3.10 Fixture (owner U1, first deliverable)

- **Generated, not hand-written:** `pipeline/export/fixture.py` (run by `uv run python -m pipeline export --fixture`) builds a synthetic SAM on the **real 128 accounts and real hierarchy**:
  - random positive values (seeded, numpy `default_rng(20261002)`) on the real non-zero pattern, balanced with `pipeline.sam.balance.gras` to equal row and column totals;
  - exactly 2 negative cells (one inside a level-0 pair that also has positive cells, one alone) and 1 internal flow inside PRDS, then re-balanced by GRAS (sign-preserving);
  - synthetic entries (1–3 per cell, every label and flag represented), constraints, refs, provenance (source `fixture`, `link_mode: deep`, landing `https://example.invalid/`), 69 synthetic series over 76 periods with gaps, two sign changes and every marker kind, and the three stories (figures computed by the real evaluator from the synthetic data).
  - It then runs the same writer as the real export, so the fixture has every file in §3.6.
- **Path:** `web/fixtures/data/index.json` and `web/fixtures/data/2023-24.fixture0000/**`, with `fixture: true`. The `data_version` pattern is `^\d{4}-\d{2}\.([0-9a-f]{10}|fixture0000)$`.
- **Validation:** the same JSON Schemas (`pipeline/export/schema/*.schema.json`) and the same Python identity tests (`test_identities.py` runs on both).
- **Serving** (U2, §4.4): `DATA_ROOT=fixtures` makes the build-time loader read `web/fixtures/data/` and `scripts/sync-fixture.mjs` copy it to `web/public/data-fixture/` (gitignored) for client fetches. `DATA_ROOT` defaults to `public` once `web/public/data/index.json` exists, and to `fixtures` before.
- **Guard:** `scripts/check-data.mjs` (U2) fails `next build` when the data root is the fixture and `ALLOW_FIXTURE=1` is not set. `ALLOW_FIXTURE=1` is allowed for e2e runs before the real export exists; such runs print "E2E ON FIXTURE DATA" and Checkpoint C may not cite them.
- `web/tests/unit/contract/contract.test.ts` (U1) validates the fixture and the real export against the schemas with ajv.

---

## 4. Web architecture

### 4.0 The first screen (owner U3; data U1; story cards U5)

At `/en/`, before any interaction, a phone user (375×812) sees, top to bottom:
1. An `<h1>`: "India's economy, as money flowing between people, firms, governments and the world." (message key; no digits).
2. Two or three **headline cards** bound to `summary.json`, each with its status badge:
   - GDP 2023-24 (`inr`, official);
   - "Of every ₹100 households pay out" (`per100` from `summary.headline.hh_outlays`, "Official total · split estimated" where that is what the data says): consumption, saving, taxes, and the rest; the unallocated published residual (X_DISC D1) is its own line, never folded into consumption or saving. Prototype on the real data: consumption ₹66.8, saving ₹24.0, taxes ₹3.3, financial services and interest ₹3.1, unallocated residual ₹2.3, other ₹0.5.
3. Three **story cards** (`StoryCards` from `components/story/index.ts`, U5), each a ≥ 44 px tall link.
4. Then the map: the `simple` preset, with return flows as stubs. "Full map" is one tap away.

The default state of all of this is rendered to HTML at build time (§4.4), so it shows without JavaScript and is the LCP element. `tests/e2e/first-screen.spec.ts` (U3) loads `/en/` at 375×812 with no scrolling and no input and asserts that the h1, at least one `[data-num-value]` headline figure with a badge, and at least one story link are inside the first viewport.

### 4.1 Directory tree (owner in brackets)

```
web/
  package.json, package-lock.json, .nvmrc ("24"), .npmrc (engine-strict=true), tsconfig.json,
  next.config.ts, eslint.config.mjs, vitest.config.ts, playwright.config.ts, vercel.json, README.md   [U2]
  scripts/  check-data.mjs  sync-fixture.mjs  gen-contract.mjs  with-lock.mjs  serve-out.mjs
            first-load.mjs  node-check.mjs                                                      [U2]
  messages/en/  common.json [U2]  map.json [U3]  matrix.json [U4]  story.json [U5]  methodology.json [U6]
  content/en/   map-text.json, map-desc.json [U6]  stories/*.mdx [U5]  methodology/*.mdx [U6]
  fixtures/data/**                                   (generated by `pipeline export --fixture`)  [U1]
  public/data/**                                     (generated by `pipeline export` only)       [U1]
  public/data-fixture/**                             (gitignored copy, scripts/sync-fixture.mjs)  [U2]
  public/  favicon.svg, og.png                                                                    [U2]
  src/
    mdx-components.tsx                               (typography only; required by App Router)    [U2]
    app/layout.tsx                                   (pass-through, returns children)            [U2]
    app/not-found.tsx                                (own <html lang="en"><body>; emits 404.html)  [U2]
    app/page.tsx                                     (client redirect fallback to /en/)          [U2]
    app/[locale]/layout.tsx                          (<html lang suppressHydrationWarning>)      [U2]
    app/[locale]/not-found.tsx                                                                    [U2]
    app/[locale]/page.tsx              (first screen + Map)                                       [U3]
    app/[locale]/flow/[id]/page.tsx    (L0 link permalinks)                                       [U3]
    app/[locale]/series/[id]/page.tsx  (69 series pages)                                          [U3]
    app/[locale]/data/**               (heat-map, table, downloads)                               [U4]
    app/[locale]/story/page.tsx, story/[slug]/page.tsx                                            [U5]
    app/[locale]/methodology/**                                                                   [U6]
    i18n/  routing.ts  request.ts                                                                 [U2]
    styles/ tokens.css  globals.css                                                               [U2]
    data/  contract.gen.ts (generated, ownerless)  server.ts (build-time fs loader)  load.ts (client fetch)
           hooks.ts  aggregate.ts  index-data.ts                                                  [U2]
    lib/   format.ts  status.ts  url-state.ts  ids.ts                                             [U2]
    lib/sankey/**  lib/ts-board/**                                                                [U3]
    lib/matrix/**                                                                                 [U4]
    lib/story/**                                                                                  [U5]
    components/ui/**   (AppShell, Header, Footer, ThemeToggle, StatusBadge, CompositionBar, SourceCitation,
                        ErrorState, LiveRegion, Disclosure, Tabs, Num, StoryFig stub, DataFig)    [U2]
    components/map/**     (index.ts exports MapView, MapMobile, FlowDetailPanel, FirstScreen)     [U3]
    components/matrix/**                                                                          [U4]
    components/story/**   (index.ts exports StoryPlayer, StoryCards, StoryFig)                    [U5]
    components/methodology/**                                                                     [U6]
  tests/
    unit/contract/** [U1]  unit/platform/** [U2]  unit/map/** [U3]  unit/matrix/** [U4]
    unit/story/** [U5]  unit/content/** [U6]
    e2e/smoke.spec.ts, a11y.spec.ts, theme.spec.ts, mobile.spec.ts, fidelity.spec.ts, headers.spec.ts   [U2]
    e2e/map.spec.ts, first-screen.spec.ts [U3]  e2e/matrix.spec.ts [U4]  e2e/story.spec.ts [U5]
    e2e/methodology.spec.ts [U6]
```

`tsconfig.json` paths: `@/*` → `src/*`, `@content/*` → `content/*`, `@messages/*` → `messages/*`. `exclude` covers `.next*/` (all per-unit dev dirs) and `out/`.

### 4.2 Routes (static export, `trailingSlash: true`)

| Route | Content | Count |
|---|---|---|
| `/` | Client redirect to `/en/` (fallback; Vercel 308s via vercel.json) | 1 |
| `/en/` | First screen and the Map: slider, view toggle, Sankey (or phone view), detail panel, "view as list/table" | 1 |
| `/en/flow/<link id>/` | Level-0 link permalink, rendered at build time (readable without JS) | ~75 (both presets; `generateStaticParams`, `dynamicParams = false`) |
| `/en/series/<F01>/` | A time-series flow: chart, all-years table, shares, markers, sources | 69 (`dynamicParams = false`) |
| `/en/story/` and `/en/story/<slug>/` | Story index; the three stories | 4 |
| `/en/data/` | Heat-map (canvas), table alternative, all non-zero cells list, JSON downloads | 1 |
| `/en/methodology/` | Methodology and sources (anchors `#status`, `#estimates`, `#limits`, `#sources`, `#data-version`) | 1 |
| `404.html` | From the root `app/not-found.tsx` | 1 |

### 4.3 State in the URL (U2 `lib/url-state.ts`; U3 and U5 use it)

`/en/?view=sam|ts&p=simple|full&y=2023-24&x=HH,TAX&s=HH--PRDS&t=table`

| Param | Meaning |
|---|---|
| `view` | `sam` or `ts`. Forced to `ts` when `y ≠ 2023-24`. |
| `p` | Preset (default `simple`) |
| `y` | Year label |
| `x` | Expanded node ids, kept in hierarchy order (implies `p=full`) |
| `s` | Selected link or node id |
| `t=table` | Table/list alternative open |

- Parsing validates against the hierarchy. An invalid value is dropped with a visible notice ("Link not found"), not silently.
- **The server-rendered page never reads the URL.** It renders the default state. A client child reads `window.location.search` after mount (or `useSearchParams` inside its own `<Suspense>` whose fallback is the server-rendered default, not a spinner) and then applies the state.
- `replaceState` for slider moves; `pushState` for selection, zoom and preset changes.

### 4.4 Data loading (U2)

- **Build time (server components, permalink pages, first screen):** `src/data/server.ts` reads `index.json` and `<data_version>/*.json` with `fs` from the data root (`DATA_ROOT`: `public` → `web/public/data/`, `fixtures` → `web/fixtures/data/`). It validates top-level keys and fails the build loudly on a mismatch.
- **Client:** `load.ts` fetches `${base}/${data_version}/<file>` (base `/data` or `/data-fixture`) with an in-memory promise cache. `index-data.ts` exposes `data_version` and `base`, injected at build time from `server.ts` (no static import of `public/data/index.json`, which would break before the first export).
- Hooks: `useSummary, useHierarchy, useCells, usePinned, useEntries(l0), useConstraints, useRefs, useProvenance, useSeries, useTsView, useCover, useStory(slug), useMapText(), useMapDesc()`.
- **First view:** summary, hierarchy, cells, pinned, ts/view and map-text. The server component passes the data it already read as props to the client map, so the client does not fetch them again; `<link rel="preload" as="fetch" crossOrigin="anonymous">` is used only for files the client does fetch (series.json).
- `series.json` and `map-desc.json` load after first paint; the rest on demand.
- **Failure handling:** a failed fetch or a schema mismatch renders `<ErrorState>` naming the file and calls `console.error`. Nothing renders made-up or partial numbers.
- `aggregate.ts`: `aggregate(cells, hierarchy, visible) → { links, internal }`. **The account cell is the atom.** For each directed pair of visible nodes it sums the **positive cells into one link and the negative cells into another** (`~neg`), with `abs_*`, OR'd flags and refs per link. Cells whose ends map to the same visible node go to `internal` for that node. Cells inside PRDS (margins, and in `simple` the whole producer loop) stay internal at every zoom. Total labels come from `pinned.json`, keyed by link id.

### 4.5 The unrolled circular Sankey (U3, `lib/sankey/`; proposed D3-5)

A SAM is circular, and d3-sankey and ECharts both reject cycles (STACK §4.2). We draw a **custom, deterministic layout** and do not vendor d3-sankey. d3 is used only for `d3-shape` paths, `d3-scale` and interpolation.

1. **Columns are fixed** (hierarchy `col`). `full`: 0 PRDS as payer ("sales of goods and services"); 1 PROD, ROW; 2 FACT; 3 HH, NFC, FC; 4 TAX; 5 CEN, STA; 6 SI, DISC; 7 FINM; 8 PRDS as receiver ("spending on goods and services"). `simple`: 0 PRODUCERS (payer); 1 ROW; 2 FACT; 3 HH, NFC, FC; 4 TAX; 5 CEN, STA; 6 SI, DISC; 7 PRODUCERS (receiver). The split node is drawn twice; every link out of it starts at the first copy and every link into it ends at the last. Both copies have the same drawn height (677.82 lakh crore for PRDS in `full`; 369.09 for PRODUCERS in `simple`).
2. **Node order within a column** is the hierarchy `order`, fixed for every zoom state and year. Expanded children replace their parent in place.
3. **Links and node heights.** Every drawn link is either the positive part or the negative part (`~neg`, drawn reversed) of a node pair (§4.4). A node's **height = the sum of its drawn inflow widths = the sum of its drawn outflow widths** (= positive receipts + |negative payments|, both net of internal flows). This equality holds exactly because every account balances, and it **does not depend on how other nodes are zoomed**, because the atoms (account cells) do not change sign when grouped. Expanding a node shows flows between its children, so the children's heights can add to more than the parent's; that is shown, not hidden ("₹X flows between these groups"). **Width scale: share of GDP** (value / GDP 2023-24), one px-per-%-of-GDP constant for the view, shared with the top-flows view, fixed across zoom states.
4. **Negative parts are drawn reversed** with a "reversed" marker and their own wording. At level 0: product subsidies (Taxes → Goods & services), subsidies paid by the Centre and the States (Centre → Taxes, States → Taxes), production subsidies (Taxes → Industries), "the Centre's negative gross saving (dissaving): the capital account covers the gap" (Saving and investment → Centre), inventory run-downs, and two financial-market netting items. The level-0 tax ribbons therefore show **taxes and subsidies separately**; nothing is silently net.
5. **Ports.**
   - Right side of a node (outgoing): forward links first, ordered by target column then target order; then same-column links; then return links, at the bottom.
   - Left side (incoming): forward links ordered by source column then source order; return links at the bottom.
   - So a return arc leaves from the bottom of its source and dives under without crossing that node's forward bands.
6. **Routing.**
   - **Forward** (target column > source column): a Sankey band. When it skips columns, it is routed through **reserved vertical gutters** between the nodes of each intermediate column (a virtual waypoint per skipped column; the layout reserves gutter space proportional to the bands that pass). No ribbon passes through a node that is not its endpoint.
   - **Same column** (HH↔FC, NFC↔FC, NFC→HH, CEN↔STA, DISC→SI: 8 links): a short side arc in a gutter to the right of that column, not under the diagram.
   - **Return** (target column < source column, except into the split node): arcs under the diagram. In `full`, 19 return links (18 node pairs) carry 195.16 lakh crore, 145.39 of it FINM→SI (its positive part plus the reversed negative part of SI→FINM). Lanes are ordered **by span** (outermost = longest span, ties by width), so the intervals nest and lanes do not cross. Lower opacity plus a ≥ 3:1 edge stroke (§4.11).
   - **Stubs** (the `simple` default): instead of arcs, a return link is drawn as a short labelled tab at both ends ("₹X back to Households"; 16 links, 46.90 lakh crore). Node heights still count them, so the diagram stays honest; a "Show return flows" switch turns stubs into arcs.
7. **Internal flows** (both ends in the same visible node, and every flow inside PRDS or PRODUCERS at every zoom) are not drawn. The node panel lists them ("₹79.20 lakh crore of trade and transport margins circulate inside this group").
8. **Small links:** a link narrower than 0.5 px is not drawn; each node shows "N small flows not drawn (₹X)", and they stay in the list and table.
9. **Phone view (< 640 px)**: the Sankey is not transposed. `MapMobile` shows the `simple` nodes as a vertical list of cards (name, total, % of GDP, badge). Tapping a card opens its "Money in" and "Money out" lists (the same data as the table alternative), each row ≥ 44 px, sorted by size, with a bar scaled to share of GDP; tapping a row opens the flow panel. A "Full diagram" button opens the desktop Sankey inside a focusable, labelled 2-D scroll region (`role="region"`, `tabindex="0"`). The "too much detail" guard is 60 visible links below 640 px and 400 above; when it trips, the UI asks the user to collapse a node or use the matrix view; it never silently drops links.
10. **Keyboard and screen readers** (one Tab stop for the diagram):
    - The diagram is a `<g role="group" aria-roledescription="flow map" aria-label="…">` with a visible help line above it: "Arrow keys move between groups, Enter opens details, + and − zoom, L lists a group's flows."
    - Nodes and links are `role="button"` with an `aria-label` such as "Households pay Goods & services ₹164.16 lakh crore, 56.5% of GDP, official total, split estimated".
    - Roving focus: ↑/↓ moves within a column; ←/→ moves to the nearest node in the next or previous column; Enter or Space selects (opens the panel); `+`/`−` expand or collapse; `L` enters the focused node's link list, where ↑/↓ moves between its links (outgoing, then incoming) and Esc returns to the node; Esc on a node clears the selection.
    - The focus ring is drawn in SVG (a 2 px `--focus` stroke rect or path outline, plus an offset halo), because Safari does not draw outlines on SVG elements.
    - The detail panel is a **non-modal** `role="region"` with a heading. Opening it moves focus to the heading; Esc or "Close" returns focus to the mark that opened it. On phones the panel is inserted **in the flow below the map** (pushing content down), not as an overlay, so focus is never obscured (2.4.11).
    - Target size: diagram marks can be thinner than 24 px. They rely on the WCAG 2.5.8 **"equivalent" exception**: the same function is always available on the same page through the list/table alternative, whose targets are ≥ 24 px. `a11y.spec.ts` excludes `[data-mark]` from axe's `target-size` rule and `mobile.spec.ts` excludes it from the box check, with this justification in a code comment and in the V3 brief.
    - "View as list" (default on phones) / "View as table" lists the current visible links: payer, receiver, value, % of GDP, total and split labels, flags.
11. **Rendering:**
    - SVG. **React renders the final attributes** (including `d`) of every node and link. A `useLayoutEffect` in `lib/sankey/animate.ts` performs a FLIP-style tween from the cached previous geometry to the new one by interpolating `d` with `requestAnimationFrame`, and writes nothing React owns except during the tween's frames; a new render cancels the running tween. D3 transitions are not used on React-owned elements. Under reduced motion there is no tween.
    - Ribbon fill = the payer's kind hue.
    - Ribbons whose split label is `estimated` or `balancing_set` get a pattern (estimated = hatch, set by balancing = cross-hatch), so colour is never the only signal. Where a ribbon is too thin for the pattern to show (< 6 px), the label text carries the status.
    - SVG text labels have a halo (`paint-order: stroke`, 3 px of `--bg`).
12. **Public API** (`components/map/index.ts`, stubbed by U3 in its first 15 minutes):

```ts
export type MapViewProps = {
  mode: "interactive" | "controlled";      // controlled = driven by props (stories)
  view: "sam" | "ts"; preset: "simple" | "full"; year: string; expanded: string[];
  selected?: string | null; highlight?: string[];     // link/node ids; others dimmed
  onlyHighlighted?: boolean;                          // stories on phones: draw only highlighted links
  onSelect?: (id: string | null) => void; returnFlows?: "stubs" | "arcs"; height?: number;
  initialData?: { summary: Summary; hierarchy: Hierarchy; cells: Cells; pinned: Pinned; tsView: TsView };
};
export function MapView(props: MapViewProps): JSX.Element;
export function MapMobile(props: Omit<MapViewProps, "height">): JSX.Element;
export function FlowDetailPanel(props: { id: string; year: string; onClose?: () => void }): JSX.Element;
export function FirstScreen(props: { summary: Summary }): JSX.Element;
```

Unit tests (vitest, U3):
- **Snapshots only on the fixture** (3 zoom states × 2 presets): node and link coordinates identical across runs.
- **Invariants on the fixture and the real export** (no coordinates, so a re-export never breaks them): for every node, Σ drawn inflow widths = Σ drawn outflow widths = node height (±0.01 px); port sums equal node height; a node's height is unchanged when any other node is expanded; the split node's two copies are equal; every link is classed forward, same-column or return by the column rule; **0 crossings among return lanes** (an arc-crossing counter); **no ribbon passes through a non-endpoint node rectangle** (geometric check of every path's sampled points); no NaN coordinates; reversed links preserve balance.
- The real-export invariants run in `just test` only when `web/public/data/index.json` exists and is not the fixture; otherwise the test prints "REAL-DATA INVARIANTS NOT RUN" (not a silent pass).

### 4.6 The top-flows board and the slider (U3, `lib/ts-board/`)

- Same renderer, different input. Nodes come from `ts_nodes` at fixed positions, slot heights from `slot_share`, ribbons from `ts/view.json`; widths are `share × scale` with the same scale as the SAM view (§4.5.3). Reversible ribbons draw reversed in their negative years.
- The banner (§2.1), a coverage counter "{n} of 69 flows", and lists of flows not drawn, flows internal to a node, and flows with no data this year.
- `YearSlider`: native `input[type=range]` (thumb ≥ 24 px) with `aria-valuetext="2004-05"`, a year `<select>`, step buttons, Play/Pause (kept under reduced motion, instant steps), marker ticks from `series.markers` (§2.1 item 7) and the "complete map" tick. Announcements per §2.1 item 2.
- Boundary behaviour per §2.1 items 3 and 5.

### 4.7 The flow detail panel (U3)

For a link (any zoom) or a node, the panel shows:
1. **Value** (`inr`), **% of GDP** (`pct_gdp`) with the framing line for gross flows (§3.3), and the **badge**: total label (from `pinned.json`) and split label with the composition bar. Each number carries `data-num-value` and `data-num-fmt` (fidelity test).
2. **Plain-English explanation:** a level-0 link uses `map-desc.links[id]`; otherwise a composed text "Mostly {ref label} ({share}%), {ref label} ({share}%)…".
3. **Trend:** the matched series (§3.7.4) as a small chart of % of GDP (default) or ₹ crore, with markers (§2.1) and the SAM 2023-24 point. "Open series page" links to `/en/series/<id>/`.
4. **What is inside:** for a level-2 cell, its entries (ref, component, value, label, prior → balanced and % change, verdict and `why` excerpt, binding constraints with descriptions, judgement-band note).
5. **Sources:** `SourceCitation` for the cites of the contributing prov records in the §3.5 order. Top 5, then "all N sources". Withheld links follow §3.5.
6. **Flags** in plain words (§3.4.4), with links to `/en/methodology/#status` and `#estimates`.

### 4.8 SAM heat-map and table alternative (U4)

- `components/matrix/SamHeatmap.tsx` draws the grid on **`<canvas>`**, devicePixelRatio-aware. Colour: a sequential scale on log10(|v|) with a separate hue for negatives. Block lines at level-0 boundaries.
- **Default zoom:** 13×13 blocks below 640 px (a 128×128 grid would be 2.7 px per cell at 343 px); 128×128 above. Zoom by block: select a block header → its level-1 or level-2 sub-matrix. Labels and the highlighted row and column are an SVG overlay. Hover or focus shows value, % of GDP, labels and flags.
- **Keyboard grid:** the canvas wrapper is `role="application"` with `aria-roledescription="matrix"`, `aria-label`, and a visible instruction line ("Arrow keys move the cursor, Enter zooms into a block, Esc zooms out, T opens the table"). The cursor is drawn on the canvas. A polite live region announces "{payer} pays {receiver}: {value}, {pct} of GDP, {labels}" after each move (debounced 150 ms).
- `components/matrix/MatrixTable.tsx` is the accessible alternative: an HTML `<table>` with `<th scope>` of the current zoom matrix (13×13 by default). Zero cells show "·". The "All non-zero cells" list (2,169 rows) is sortable and filterable by payer and receiver, rendered with `@tanstack/react-virtual`, with a "show all (no virtualisation)" switch for screen readers that need the full table.
- `/en/data/` also lists download links to every JSON file in the data version, with sizes and sha256 from index.json.
- The chord view (d3-chord, transfers among HH, NFC, FC, CEN, STA, ROW) is optional.

### 4.9 Explain mode: the story engine and the three stories (U5)

- **Engine:** `components/story/StoryPlayer.tsx` renders the MDX with `<Step id>` sections.
  - Desktop: a sticky `MapView mode="controlled"` beside a scrolling text column.
  - Phone: the step text first, then a compact `MapView` with `preset="simple"`, `onlyHighlighted` and a fixed height of 280 px, then an inline list of the highlighted flows with their values. Previous/Next buttons stay in the flow (not fixed over content).
  - Keyboard: Previous/Next buttons and ←/→ when the player has focus; a progress list; deep links `?step=<id>`. Reduced motion: no transitions between steps.
  - `<StoryFig id>` renders `figures[id]` with its formatter, badge (total and split) and `data-fig-id`. An unknown id fails the U5 vitest test.
- **Content plans** (U5 writes them; V2 checks the economics). All figures come from §3.8 specs. Values quoted below were recomputed for revision 2 and are for orientation only; the site shows the exported figures.
  1. **`gst-rupee` — "Where does your GST rupee go?"**
     - Total GST in the SAM: T_CGST + T_SGST + T_GCES row totals (₹8.62 + 8.29 + 1.49 lakh crore), net and post-settlement per D0-5, with the IGST settlement as a note. **T_CGST includes UTGST** (component `utgst`, ₹5,772 crore), named in the text. Flag: CGST and cess sit at the +5% judgement band edge (§3.4.3).
     - Split per ₹100 into CGST (incl. UTGST), SGST and cess.
     - The products that carry most GST (T_* ← C_* cells).
     - **Who pays at the till:** p7b use-type shares (household consumption, investment, intermediate use, government consumption, valuables, exports) applied to the balanced totals per tax account with `satellite_share`, labelled estimated, "prior split, rescaled". The text says that GST on intermediate use is mostly creditable, so the household share is the economically final part.
     - **Where it lands:** CGST, UTGST and cess are booked to the Centre and SGST to the States. **The cess does not stay with the Centre:** it pays compensation grants to the States (G_STA ← G_CEN T2b `compensation_grants`, ₹44,946 crore, official) and the cess-loan transfer (T2b `cess_loan_recovery`, ₹78,104 crore, derived) that repays the GST back-to-back loans (K_GSTA ← I_LOAN K8e `gst_b2b_repayment` −₹78,104 crore; D2-13). Both figures are shown, so the Centre's share is not overstated.
     - Devolution: the Centre's tax pool partly goes to States. The devolution total is official and exact, but the SAM does not apportion devolution by tax, so the story says so and gives no GST-specific devolution number.
     - **What governments spend on, per ₹100 of consolidated general-government outlays** (defined in the story YAML, all `sam_sum` terms): current outlays = the G_CEN and G_STA columns excluding K3a (saving) and all transfers between the Centre and the States (₹57.26 lakh crore); capital outlays = I1a, I3a and K6 from K_GCEN and K_GSTA to non-government accounts (₹14.14 lakh crore). Net acquisition of financial assets (₹5.91 lakh crore) is shown separately, not in the ₹100. Money is fungible; the story says so.
  2. **`remittance-dubai` — "How a remittance from Dubai moves through India"**
     - Household receipts from the RoW (R11a, ₹9.83 lakh crore), **official total** (the R11 total; F43 passes), with the split across household groups estimated. The share of GDP; the F43 series (2006-07 to 2025-26).
     - **The UAE part:** the `s3_remittance_sources` satellite figure (ARE ₹1,89,139 crore, share 0.192385), **labelled estimated**, method: the RBI survey's 19.2% bank-channel share for the UAE, normalised because the published shares sum to 99.80% (19.2 / 99.80 = 0.192385), applied to the NAS R11 total. Concept note: the survey measures inward remittances through banks; BoP private transfers also include local withdrawals from NRI deposits, so applying the share to the total is an approximation. The survey reports the UAE as a whole; Dubai cannot be isolated, and the story says so plainly.
     - **Licence:** the RBI survey is internal-processing-only until RBI permits reuse; this figure is added to the P1-9 permission list in the Checkpoint C report, and the citation is withheld (§3.5).
     - Which household groups receive it (estimated key).
     - What those households do with their income **on average**: consumption, taxes, saving, financial services and interest, transfers, and the **unallocated published residual** (X_DISC D1; 2.3% of household outlays) as its own line, never as consumption or saving. Group saving is itself a residual (closure-19), and the text says so. These are average propensities, not marginal ones.
     - **What the consumption buys:** product taxes on household purchases from rescaled p7b `pfce` shares (`satellite_share`, estimated); imports by commodity-column shares, labelled "estimated (proportionality assumption: households buy the same import mix as total supply)"; trade and transport margins shown as domestic.
     - "First round only; the full ripple comes with the Engine (Phase 4)."
  3. **`deficit-funding` — "Who funds the government's deficit?"**
     - Government gross saving: the Centre negative (dissaving), the States positive. Official GG total (NAS 1.9); the Centre/State split is estimated.
     - Government investment (I1a, I3a, K6 from K_GCEN / K_GSTA).
     - **Net lending (national accounts)**, explicitly distinguished from the Budget's fiscal deficit, defined in the YAML as the K_GCEN (or K_GSTA) row's non-instrument items minus its column's non-instrument items (I1a, I3a, K6, R2k). The evaluator checks that it equals Σ financial assets − Σ liabilities within ₹0.01 crore (it does: Centre −₹11.47 lakh crore, States −₹5.84).
     - Liabilities incurred by instrument (K_GCEN / K_GSTA ← I_*: G-secs, small savings, loans, other) and assets acquired, **including the K9 residuals** (Centre −₹0.42 lakh crore net, States −₹1.80) and the K9b RBI-surplus timing item (+₹1.23), shown as named bars so the instruments add up to net lending.
     - **"Who bought government securities (Centre and States)":** the I_GSEC row by acquirer (banks, insurers and pension funds, RoW (K8b), NBFCs, mutual funds, households (K7a, official), others; the RBI was a net seller). Issuers: the Centre ₹11.71 lakh crore and the States (SDLs) ₹6.65 lakh crore. The SAM pools the two, so it cannot say who bought the Centre's paper; the step title says "Centre and States". Acquirer cells are estimated (FSF-keyed) and then moved by balancing.
     - Households' financial saving behind those institutions (K_HH → I_DEPO / I_INPE / I_SSAV; official NAS 5.3 totals), with the text "pooled, not traced": the SAM routes money through instrument accounts, so it shows that household deposits and bank G-sec purchases happen in the same year, not that one funded the other.
     - The cost: interest paid (SAM cells) plus the F25 and F26 series. F25 has two periods (2022-23, 2023-24) and an "explained" check, so it is shown as two values with the check text, not as a trend.
- **Python-side test** (`tests/export/test_export_stories.py`, U5): recomputes every figure with **DuckDB SQL** written independently of the evaluator (tolerance 0.01 for money and 1e-6 for shares), checks `satellite_share` parts sum to their totals, and checks net lending = assets − liabilities.

### 4.10 Methodology and sources page (U6)

Sections:
1. What this is: a balanced SAM, rows receive and columns pay, the 2023-24 reference year, new base 2022-23; why gross flows exceed GDP.
2. How the SAM was built and balanced: cross-entropy, certified; anchored vs free; the moves sum to {summary.sam.balancing.moved_abs}.
3. The labels (§3.4): official total vs split; the four split labels and when "set by balancing" is used; the flags; the label counts from `summary.sam.labels`.
4. What is estimated: the CHECKPOINT_B §8 list, rendered from `methodology/estimates.mdx`, each item linking to the map (`/en/?p=full&x=HH&s=…`).
5. Limits, named plainly: HCES captures 44.3% of PFCE and the household split assumes the missing part is spread like the captured part (households-1); IFPRI gradients for factor income (D2-19); no microdata (D1-2); NPISH inside households; the old-base structures (D2-21); the judgement bands (§6b); the X_DISC items and what each is; the time series' splices, base break and linking rule; the top-flows view is not balanced; the stories use average shares, not multipliers. Each limit's number comes through `<DataFig>` bindings to `summary.json` (`summary.methodology`, filled by U1 on U6's request).
6. Sources table: every source in `provenance.sources` with publisher, licence, attribution, link mode, and the number of SAM entries and series that cite it.
7. Data version and how to reproduce: the commands, `index.json` inputs and the code hash.
8. Open issues: the ISSUES headlines that affect the site, plus the pending permissions (P1-9), including the RBI remittance survey figure.

### 4.11 Theming tokens and contrast (U2, `styles/tokens.css`)

- Colour tokens on `:root`: `--bg, --surface, --surface-2, --text, --text-muted, --border, --focus, --accent`.
- Status tokens: `--st-official, --st-derived, --st-estimated, --st-balancing`, plus patterns (estimated = hatch, set by balancing = cross-hatch).
- Kind hues: `--k-production, --k-factors, --k-households, --k-corporations, --k-government, --k-row, --k-capital, --k-discrepancy`, each with a `-edge` variant (≥ 3:1 against `--bg` and `--surface`) and a `-text` variant (≥ 4.5:1).
- Dark values: under `@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]`.
- The toggle stores its choice in `localStorage` (try/catch). An inline head script sets `data-theme` before paint; `<html>` carries `suppressHydrationWarning`.
- **Contrast is tested on what is drawn.** `lib/sankey/style.ts` (U3) exports the opacity constants (forward ribbon, return arc, dimmed). `tests/unit/platform/contrast.test.ts` (U2) imports them, composites each kind hue at each opacity over `--bg` and `--surface` in both themes, and requires: ≥ 3:1 for the composited fill, **or** a ≥ 3:1 `-edge` stroke drawn on that ribbon (the renderer draws the edge whenever the fill is below 3:1); ≥ 4.5:1 for label text against its halo; the hatch line colour ≥ 3:1 against the ribbon fill.
- System font stack with tabular numerals. No web fonts in v1.

### 4.12 i18n and static rendering (U2 sets the pattern; every page owner follows it)

- next-intl 4.14.x: `src/i18n/routing.ts` = `defineRouting({ locales: ['en'], defaultLocale: 'en', localePrefix: 'always' })`. No middleware (static export).
- `app/layout.tsx` is a pass-through (returns `children`). `[locale]/layout.tsx` renders `<html lang={locale} suppressHydrationWarning>`, has `generateStaticParams → [{locale: 'en'}]` and `export const dynamicParams = false`.
- **Every `page.tsx` and layout under `[locale]`, and every `generateMetadata`, calls `setRequestLocale(locale)` before any `getTranslations`.** Without it the route becomes dynamic and `output: 'export'` fails. `tests/unit/platform/static-locale.test.ts` (U2) greps every `page.tsx`/`layout.tsx` under `src/app/[locale]` and fails if one lacks `setRequestLocale`. It is in the §6.5 definition of done.
- `flow/[id]` and `series/[id]` export `dynamicParams = false` and `generateStaticParams` from the build-time loader.
- `app/not-found.tsx` (root) has its own `<html lang="en"><body>`; static export emits `404.html` from it.
- `request.ts` merges `messages/<locale>/*.json` under their namespace keys. The client `NextIntlClientProvider` receives only the `common` and `map` namespaces on `/en/` (each page passes the namespaces it needs), not all messages.
- `content/<locale>/…` is loaded with `import(\`@content/${locale}/…\`)`.
- A vitest test checks that every key used through `useTranslations` exists. Adding Hindi = `messages/hi/*.json`, `content/hi/**` and the locale. No component edits.

### 4.13 Performance budget

| Item | Budget | Enforced by |
|---|---|---|
| First-load JS of `/en/` (gzipped) | ≤ 200 KB | `scripts/first-load.mjs`: parses `out/en/index.html`, sums the gzipped size of every referenced `/_next/static/**` chunk, fails above budget; in `test:web` |
| First-view data inlined or fetched for `/en/` (summary + hierarchy + cells + pinned + ts/view + map-text, gzipped) | ≤ 150 KB | `test_json_hygiene.py` (sizes) |
| `ts/series.json` gz | ≤ 60 KB | `test_json_hygiene.py` |
| Any lazy data file gz | ≤ 120 KB | `test_json_hygiene.py` |
| LCP (Lighthouse mobile, served `out/`) | < 2.5 s | V4 report (median of 3, `@lhci/cli`) |
| TBT | < 200 ms | V4 report |
| Lighthouse Performance / Accessibility | ≥ 90 / 100 | V4 report |
| Slider play at 4× CPU throttle | median frame ≤ 20 ms | V4 report (not a gate) |

`map-desc.json` (descriptions) is lazy; only labels are in the first view. JSON imported into a client component counts as JS in `first-load.mjs`, so data is passed as props from the server component, not imported.

### 4.14 `next.config.ts` and `vercel.json` (U2)

- `next.config.ts`: `output: 'export'`, `trailingSlash: true`, `images: { unoptimized: true }`, `reactStrictMode: true`, `pageExtensions: ['ts','tsx','md','mdx']`, `distDir: process.env.NEXT_DIST_DIR ?? '.next'`; wrapped with `createMDX()` from `@next/mdx` (Turbopack accepts remark/rehype plugins only as **serialisable strings**, e.g. `remarkPlugins: ['remark-gfm']`) and the next-intl plugin; `typedRoutes` off.
- `web/vercel.json` (the Vercel project's Root Directory = `web`). `"framework": null` so Vercel deploys `out/` as plain static files and applies these redirects and headers itself:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": null,
  "buildCommand": "npm run build",
  "outputDirectory": "out",
  "redirects": [{ "source": "/", "destination": "/en/", "permanent": true }],
  "headers": [
    { "source": "/data/(.*)", "headers": [{ "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }] },
    { "source": "/data/index.json", "headers": [{ "key": "Cache-Control", "value": "public, max-age=0, must-revalidate" }] },
    { "source": "/(.*)", "headers": [
      { "key": "Content-Security-Policy", "value": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'" },
      { "key": "X-Content-Type-Options", "value": "nosniff" },
      { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
      { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=()" } ] }
  ]
}
```

- `'unsafe-inline'` for scripts is needed because a Next static export inlines its RSC payload and the theme script (proposed D3-11). No `unsafe-eval`.
- `/data/index.json` is listed after `/data/(.*)` so that it wins; with `framework: null` this ordering is Vercel's documented header behaviour for static output, but it is **unverified until the preview `curl` checks** (§7.2). `index.json` is read at build time only, so a wrong cache header is harmless at runtime (R9).
- The protected preview injects Vercel's toolbar scripts from `vercel.live`, which this CSP blocks. Expect CSP console errors on the protected preview only; the report notes them. The CSP is not loosened for that.

### 4.15 Working in one checkout: rules for every agent

- **Node 24 only.** Every web command runs through `scripts/node-check.mjs` (exit 1 with "Node {v} found; this project needs Node 24. Run: export PATH=/opt/homebrew/opt/node@24/bin:$PATH") or with `/opt/homebrew/opt/node@24/bin` first on PATH. `web/.npmrc` has `engine-strict=true`, so `npm` refuses Node 26.
- **npm install** (U2 at t0; later additions only through U2's requests file): always `node scripts/with-lock.mjs --lock install -- npm install --save-exact …`. **Dependencies freeze at t0 + 90 min**; after that a new dependency needs the orchestrator's approval and is installed when no unit is running tests (U2 announces it in its status file 5 minutes ahead).
- **Locks** (`scripts/with-lock.mjs`, atomic `mkdir web/.locks/<name>` with a pid file; a lock is stale only if its pid is dead, so a slow build is never stolen):
  - `build`: every `next build` and anything that writes `out/` (`npm run build`, `test:web`, `start:out`);
  - `install`: every `npm install`/`npm ci`.
- **Dev servers are not locked.** Each unit runs `npm run dev` with its own `NEXT_DIST_DIR=.next-u3` (etc.) and `PORT=0` (a free port, printed). Playwright and `serve-out.mjs` also take `port: 0` and print the URL.
- `vitest`, `tsc --noEmit` and `eslint` run concurrently; `tsconfig.json` excludes `.next*/` and `out/`, so a concurrent build cannot change what `tsc` reads (`next-env.d.ts` is committed and not regenerated by dev runs with a custom distDir).
- **Generated files are ownerless:** anyone may run `npm run gen:contract` (it writes `src/data/contract.gen.ts` from `pipeline/export/schema/*.json` deterministically); a test fails if it is stale. Nobody hand-edits it.
- `pipeline export` takes the repo lock. Run `just test` only after your own export finishes.
- **Interface first:** in its first 15 minutes each unit creates its public modules with typed stubs (`components/map/index.ts`, `components/story/index.ts`, …).
- **Data root while building:** before U1's `READY: export-core`, web units run with `DATA_ROOT=fixtures` (the default when there is no real export); afterwards `DATA_ROOT=public`.
- Problems go to `docs/phase3/issues/<unit>.md`; status to `docs/phase3/status/<unit>.md` (`READY: <milestone>`); requests to `docs/phase3/requests/<your unit>.md` as `- [ ] to U2: …`.

---

## 5. Test plan (one command each)

| Command | Runs | Must pass |
|---|---|---|
| `just export` = `uv run python -m pipeline export` | the exporter | exit 0 |
| `just test` = `uv run python -m pipeline test` | all existing offline Python layers + `tests/export` (marker `export`) + **vitest**. The vitest hook in `cmd_test` (U1) resolves node from `/opt/homebrew/opt/node@24/bin` if present, else PATH, checks `node -v` major == 24 and **fails loudly** with the PATH fix otherwise. Missing `web/node_modules` fails loudly unless `--no-web`, which prints "WEB UNIT TESTS NOT RUN" (proposed D3-10). | 0 failed (the existing 25 xfails stay) |
| `just test-web` = `npm --prefix web run test:web` | `node-check` → `gen:contract --check` → `vitest run` → `next build` (fixture guard) → `first-load.mjs` → Playwright against `out/` served by `serve-out.mjs` | 0 failed |
| `just web` = `npm --prefix web run dev` | local dev server | |

U1 adds the recipes to the justfile in the existing style (`sys.argv` inside a recipe is `['-c', <recipe name>, <args...>]`, so web recipes forward `sys.argv[2:]`):

```
# Phase 3: export web JSON (web/public/data/): just export [--check | --fixture]
export *args:
    @import subprocess, sys; sys.exit(subprocess.call([sys.executable, "-m", "pipeline", *sys.argv[1:]]))

# Phase 3: local website (needs Node 24: export PATH=/opt/homebrew/opt/node@24/bin:$PATH; npm ci in web/)
web *args:
    @import shutil, subprocess, sys; npm = shutil.which("npm") or sys.exit("npm not found on PATH"); sys.exit(subprocess.call([npm, "--prefix", "web", "run", "dev", "--", *sys.argv[2:]]))

# Phase 3: build + first-load budget + Playwright e2e and axe; args go to Playwright only
test-web *args:
    @import shutil, subprocess, sys; npm = shutil.which("npm") or sys.exit("npm not found on PATH"); sys.exit(subprocess.call([npm, "--prefix", "web", "run", "test:web", "--", *sys.argv[2:]]))
```

`test:web` is `node scripts/test-web.mjs`, which runs the chain step by step and passes its own arguments to the Playwright step only (npm forwards `--` arguments to the last command of a `&&` chain, which is why the chain is a script).

### 5.1 Python export tests (`tests/export/`, marker `export`; U1 unless noted)

1. `test_identities.py` (real export and fixture): exported cells re-aggregated per account equal `sam_balanced` row and column totals within 0.005 × n_cells; every account balances; the cell count equals the non-zero cells after rounding; level-0 aggregates (positive and negative parts) equal a DuckDB recomputation; the §3.2 prototype figures.
2. `test_gdp.py`: `summary.gdp.value` equals the M01 2023-24 base 2022-23 row, the NAS 1.1 value in clean `mospi_nas_2026`, and GDP from the SAM's production side within ₹1 crore; every time-series share recomputed within 1e-6; `summary.headline` parts sum to the total.
3. `test_provenance.py`: every prov id exists in `provenance.json`; every record has ≥ 1 cite or `assumption: true` with a method; `depends_on_assumption` equals an independent transitive walk; every source id is in `registry.yaml`; no URL host is `withheld` or unknown; every cite with a URL has a retrieval date; cite order follows §3.5.
4. `test_status.py`: the §3.4.1 rule re-implemented independently and compared on all 3,893 entries (counts: 1,127 / 114 / 2,180 / 472); no entry reaches the else branch; composition sums to 1 (±1e-4); `pinned.json` re-derived independently for all level-0 pairs (16 pinned) and a sample of 200 mixed-zoom pairs; `judgement_bands.yaml` equals the §6b set and each is binding; `old_base_scope.yaml` ids exist; flags match their definitions (e.g. exactly the entries with a current "unexplained" verdict carry `unexplained`); the golden file.
5. `test_hierarchy.py` (§3.2) and `test_ts_view.py` (the five ribbon rules in §3.7.3, including the sign rule over every year).
6. `test_series.py`: every main value equals the selected parquet row; no period outside the parquet's (no interpolation); every non-null value has a prov and a status; `linked` only for the 10 linked flows; **every `base_change`, `concept_break` and `segment_join` flag and every segment boundary appears in `markers`**.
7. `test_json_hygiene.py`: no NaN or Infinity; no `-0`; UTF-8 with LF; `index.json` sha256 values match; sizes within budget (§4.13).
8. `test_export_current.py` (`export --check`) and `test_export_determinism.py` (PYTHONHASHSEED 0 and 1, byte-identical).
9. `test_formats.py`: `formats.py` reproduces `golden/format_cases.json`.
10. `test_export_stories.py` (U5): §4.9.

### 5.2 vitest (`web/tests/unit/**`)

| Owner | Test files |
|---|---|
| U1 | `contract/contract.test.ts`: ajv validates fixture and real data against the schemas |
| U2 | `format.test.ts`, `status.test.ts` (golden files); `url-state.test.ts`; `aggregate.test.ts` (positive and negative parts, conservation, internal flows including PRDS at every zoom, flags OR'd); `contract-gen.test.ts`; `messages.test.ts`; `static-locale.test.ts` (§4.12); `contrast.test.ts` (§4.11) |
| U3 | layout invariants and fixture snapshots (§4.5); ts-board (slot stability, missing years, reversed years); panel composition text; trend matching (§3.7.4 table, including the 50–95% case); markers rendered for every flag |
| U4 | colour scale (log, negative hue); hit-testing (pixel → cell) at several DPRs; table aggregation equals `aggregate()` |
| U5 | every `<StoryFig id>` exists in its story JSON; every step's ids exist; the engine's state machine |
| U6 | map-text and map-desc completeness (§3.9); `no-digits.test.ts`; every `<DataFig path>` resolves in summary.json |

### 5.3 Playwright and axe (`web/tests/e2e/**`)

Config (U2): `reducedMotion: 'reduce'` by default; fixed `workers: 2`; `page.clock` for anything timed (Play); every sample list is fixed or seeded (`SEED=20261002`). Browsers: Chromium for everything; WebKit for smoke, map and story if it runs on this OS (R2). Viewports 375×812 and 1280×800.

| Owner | Spec | What it checks |
|---|---|---|
| U2 | `smoke.spec.ts` | Chromium, every route in §4.2: 200 from `out/`, an `<h1>`, no console error, no hydration warning |
| U2 | `a11y.spec.ts` | `@axe-core/playwright` with tags wcag2a, wcag2aa, wcag21aa, wcag22aa on **every route type** (home, 5 flow pages, 5 series pages, story index, 3 stories, data, methodology, 404), in light and dark, both viewports, plus the map with a panel open, the table open, and the phone view with a node opened; `target-size` excludes `[data-mark]` (§4.5.10); 0 violations |
| U2 | `theme.spec.ts` | The toggle persists; `prefers-color-scheme` is respected; no hydration warning after the head script |
| U2 | `mobile.spec.ts` | No horizontal scroll at 375 px; every interactive element outside `[data-mark]` is ≥ 24×24 px or meets the 2.5.8 spacing exception |
| U2 | `headers.spec.ts` | `vercel.json` parses and contains the §4.14 rules (with `framework: null`); `/data/` folder names match index.json |
| U2 | `fidelity.spec.ts` | Selects 10 listed links at levels 0, 1 and 2 (both presets). For every `[data-num-value]`, the text equals format(value), and the value equals an aggregation **written in the spec itself** from `cells.json` (it does not import `src/data/aggregate.ts`) |
| U3 | `first-screen.spec.ts` | §4.0, at 375×812, no scroll, no input |
| U3 | `map.spec.ts` | The §4.5.10 keyboard model: Tab once into the diagram → arrows move focus (visible SVG focus ring) → Enter opens the panel and focus moves to its heading → Esc returns focus to the mark → `+` expands → `L` enters the link list → ↓ moves → Enter opens the link; the slider moves by arrow keys and the live region announces on manual steps only; moving off 2023-24 switches to the top-flows view with the banner; scrubbing back into 2023-24 keeps the top-flows view; Back restores selection and zoom (not the year); "view as table" lists the visible links; at 375 px the phone view shows lists, not the Sankey |
| U4 | `matrix.spec.ts` | Canvas renders; the table toggle shows `<th scope>`; keyboard cursor and announcements; zoom into a block; 13×13 default at 375 px |
| U5 | `story.spec.ts` | Steps through each story with buttons and keys; every `[data-fig-id]` text equals format(story figure) |
| U6 | `methodology.spec.ts` | Every source in `provenance.sources` is listed; withheld sources have no `<a href>` to an RBI host; anchors exist |

Playwright browsers are installed once with `npx --prefix web playwright install chromium webkit` (network; about 300 MB).

---

## 6. Build breakdown

### 6.1 Units

| Unit | Builds | Est. effort |
|---|---|---|
| **U1 Data export** | `pipeline/export/**` (except stories YAML), schemas, curated lists, the generated fixture, the CLI subcommand and vitest hook, the justfile recipes, `tests/export/**` except the stories test, `web/tests/unit/contract/**`; runs the real export | ~5 h |
| **U2 Platform** | Scaffold, configs, `vercel.json`, i18n and static-rendering pattern, theming, routing shell, data layer (build-time loader, client loader, hooks, `aggregate`, generated types), shared UI components (incl. `DataFig` and the `StoryFig` stub), format and status libs, scripts, the test harness, the global e2e/a11y/fidelity specs | ~4–5 h |
| **U3 Map** | First screen, the unrolled Sankey (presets, zoom, routing, keyboard), phone view, slider, top-flows board, detail panel, the Map page, flow and series permalink pages | ~6 h |
| **U4 Matrix** | Canvas heat-map, accessible matrix table, virtualised all-cells list, `/en/data/` page, optional chord | ~3–4 h |
| **U5 Stories** | Story engine, story cards, the three stories' figure specs (YAML) and MDX, the story pages, the story tests including DuckDB recomputation | ~4–5 h |
| **U6 Methodology & map text** | `map-text.json`, `map-desc.json`, the Methodology & sources page, content tests | ~4 h |

### 6.2 Strict file ownership

Nobody edits a file they do not own. To change someone else's file, write a request (§4.15).

| Unit | Owns (create and edit) |
|---|---|
| U1 | `pipeline/export/**` except `pipeline/export/stories/**`; `pipeline/cli.py` (only the `export` subparser and the vitest hook in `cmd_test`); `justfile` (only the `export`, `web`, `test-web` recipes); `pyproject.toml` (only the `export` marker); `tests/export/**` except `test_export_stories.py`; `web/fixtures/**`; `web/public/data/**` (written only by the exporter); `web/tests/unit/contract/**`; `docs/phase3/{status,issues,requests}/U1.md` |
| U2 | Everything under `web/` not owned by another unit, including `package.json`, `package-lock.json`, `.npmrc`, `.nvmrc`, all configs, `vercel.json`, `scripts/**`, `src/mdx-components.tsx`, `src/app/layout.tsx`, `src/app/not-found.tsx`, `src/app/page.tsx`, `src/app/[locale]/layout.tsx`, `src/app/[locale]/not-found.tsx`, `src/i18n/**`, `src/styles/**`, `src/data/**` (except the generated `contract.gen.ts`, which is ownerless), `src/lib/{format,status,url-state,ids}.ts`, `src/components/ui/**`, `messages/en/common.json`, `public/{favicon.svg,og.png}`, `tests/unit/platform/**`, `tests/e2e/{smoke,a11y,theme,mobile,headers,fidelity}.spec.ts`, `web/README.md`; `docs/phase3/*/U2.md` |
| U3 | `src/app/[locale]/page.tsx`, `src/app/[locale]/flow/**`, `src/app/[locale]/series/**`, `src/components/map/**`, `src/lib/sankey/**`, `src/lib/ts-board/**`, `messages/en/map.json`, `tests/unit/map/**`, `tests/e2e/{map,first-screen}.spec.ts`; `docs/phase3/*/U3.md` |
| U4 | `src/app/[locale]/data/**`, `src/components/matrix/**`, `src/lib/matrix/**`, `messages/en/matrix.json`, `tests/unit/matrix/**`, `tests/e2e/matrix.spec.ts`; `docs/phase3/*/U4.md` |
| U5 | `pipeline/export/stories/**`, `tests/export/test_export_stories.py`, `content/en/stories/**`, `src/app/[locale]/story/**`, `src/components/story/**`, `src/lib/story/**`, `messages/en/story.json`, `tests/unit/story/**`, `tests/e2e/story.spec.ts`; `docs/phase3/*/U5.md` |
| U6 | `content/en/map-text.json`, `content/en/map-desc.json`, `content/en/methodology/**`, `src/app/[locale]/methodology/**`, `src/components/methodology/**`, `messages/en/methodology.json`, `tests/unit/content/**`, `tests/e2e/methodology.spec.ts`; `docs/phase3/*/U6.md` |
| Ownerless (generated) | `web/src/data/contract.gen.ts` (anyone runs `npm run gen:contract`); `web/public/data-fixture/**` (gitignored, `sync-fixture.mjs`) |
| Orchestrator only | `SPEC.md`, `CLAUDE.md`, `DECISIONS.md`, `ISSUES.md`, `BALANCING.md`, `data/**`, `pipeline/` outside `export/` and `cli.py`, `tests/` outside `tests/export/`, `docs/phase3/PLAN.md`, `docs/phase3/CHECKPOINT_C.md`, git |

**Shared code that only U2 may touch:** `src/data/**` (hooks, loaders, `aggregate`), `src/lib/{format,status,url-state,ids}.ts`, `src/components/ui/**` (StatusBadge, CompositionBar, SourceCitation, Num, ErrorState, LiveRegion, DataFig, StoryFig stub), `src/i18n/**`, `src/styles/**`, `src/mdx-components.tsx`, `scripts/**` and every config. `StoryFig`'s real implementation lives in `components/story/` (U5); U2's stub re-exports it once U5 is `READY: storyfig`.

### 6.3 Order and dependencies

```
t0 ──► U1: hierarchy.yaml + presets + schemas + golden files (READY: contract, ~45 min)
   │       ──► fixture generator (READY: fixture, ~90 min) ──► exporter core
   │       ──► real export without stories (READY: export-core, ~3 h) ──► story evaluator (READY: stories-eval)
   ├─► U2: npm install of all §6.4 deps under the install lock, WebKit smoke check, scaffold,
   │       [locale] shell, static-rendering pattern, tokens, i18n, build-time + client loaders with DATA_ROOT
   │       (READY: scaffold, ~90 min; deps frozen) ──► shared UI (READY: ui, ~3 h) ──► harness and e2e specs
   ├─► U3: stub MapView/MapMobile/FirstScreen (15 min) ──► pure layout lib + invariant tests on a tiny
   │       in-test matrix ──► on U1 READY: fixture, fixture snapshots ──► components after U2 READY: scaffold
   ├─► U4: stub ──► canvas renderer and hit-test lib ──► components after U2 READY: scaffold
   ├─► U5: stub (StoryPlayer, StoryCards, StoryFig) ──► stories/*.yaml figure specs (run the evaluator on
   │       U1 READY: stories-eval) ──► MDX drafts ──► StoryPlayer after U2 READY: ui and U3's MapView stub
   └─► U6: map-text.json / map-desc.json (ids are fixed in §3.2, §3.6 and U1's link list) ──► methodology MDX
           ──► page after U2 READY: ui
Integration (orchestrator): all READY: done ──► just export, just test, just test-web
   ──► fix loop (owners only) ──► verification wave (§7)
```

- All six units start at t0. Hard waits: components need U2 `READY: scaffold`; fixture-based tests need U1 `READY: fixture`; StoryPlayer needs U3's MapView stub; real numbers need U1 `READY: export-core` (stories need `READY: stories-eval`).
- U1 writes the level-0 link ids (both presets, positive and `~neg`) to `docs/phase3/status/U1.md` as soon as the hierarchy YAML exists (~20 minutes).

### 6.4 Dependencies U2 installs at t0 (exact versions recorded by the lockfile)

- **runtime:** `next@16.3.8`, `react@19`, `react-dom@19`, `next-intl@4.14.8`, `@next/mdx@16.3.8`, `@mdx-js/loader`, `@mdx-js/react`, `remark-gfm` (tables in methodology MDX), `@tanstack/react-virtual` (the all-cells list), and the d3 modules `d3-array, d3-scale, d3-shape, d3-chord, d3-interpolate, d3-format, d3-time-format` (the d3 7.9 set; no `d3-transition`/`d3-selection`, §4.5.11).
- **dev:** `typescript@6.0.3`, `@types/react`, `@types/react-dom`, `@types/mdx`, `@types/d3-*` for the above, `vitest@5`, `@vitest/coverage-v8`, `happy-dom`, `@testing-library/react`, `@playwright/test@1.63`, `@axe-core/playwright@4.13`, `ajv`, `ajv-formats`, `json-schema-to-typescript`, `eslint`, `eslint-config-next`, `serve-handler` (`serve-out.mjs`), `@lhci/cli` (V4's Lighthouse runs). `size-limit` is dropped; `first-load.mjs` replaces it (§4.13).
- `package.json`: `"engines": {"node": "24.x"}` with `.npmrc` `engine-strict=true`. Scripts: `dev, build, start:out, sync-fixture, gen:contract, test:unit, test:e2e, first-load, test:web, lint, typecheck`.

### 6.5 Definition of done (every unit)

- Its tests pass, and `tsc --noEmit` and `eslint` are clean on its files.
- No hard-coded number in components or content (only bindings).
- Every visible figure carries a badge (total and split).
- Every new string is in its namespace file.
- **Every page and layout it owns under `[locale]` calls `setRequestLocale`; dynamic segments set `dynamicParams = false`** (U3–U6).
- Its status file says `READY: done`, and its issues file lists what is not done and why.

---

## 7. Verification plan and Checkpoint C

Verifiers did not build anything and **try to break the result**. Each writes `docs/phase3/verify/V<n>_<topic>.md` with findings (id, severity, evidence, file and line, suggested owner unit) and runs its checks as code where possible, in `tests/verify/test_phase3_<topic>.py` or `web/tests/verify/*.spec.ts` (owned by the verifier; they land only with the orchestrator's approval).

| Verifier | Checks |
|---|---|
| **V1 Data fidelity** | Recomputes from parquet with **DuckDB only** (no pipeline code): every exported cell; every level-0 and level-1 aggregate (positive and negative parts); node heights; GDP and every share; every main time-series value and base selection; every story figure (incl. `satellite_share` rescaling and net lending = assets − liabilities); the entry labels; the pinned totals for all level-0 pairs; the flags. Walks provenance independently and samples 50 cites against the registry and clean records. Checks double counting among top-flows ribbons, sign errors (subsidies, negative saving, reversed years) and rounding drift. Renders every story and **the 30 panel states listed in `web/tests/verify/panel_states.json`** (chosen with seed 20261002) and compares on-screen text with its own Python formatter. |
| **V2 Economics** | Reads `map-text.json`, `map-desc.json`, the three stories and the methodology page against SAM conventions (rows receive, columns pay; GST net post-settlement D0-5; UTGST inside CGST; cess passed to States; NPISH inside households; PM-KISAN as a transfer D2-24; each X_DISC item described as what it is; the gross basis). Checks concept naming (net borrowing vs fiscal deficit, average vs marginal propensities, the UAE vs Dubai, bank-channel vs BoP transfers, "pooled, not traced"), that "estimated" and "official total" appear exactly where the labels say, and that nothing implies a forecast or a multiplier. Reviews `old_base_scope.yaml`. |
| **V3 Accessibility, mobile, theme** | axe results reviewed (not just counted), including the `[data-mark]` target-size exclusion and its justification; a manual keyboard walk-through of the map (§4.5.10), phone view, matrix, stories and slider; screen-reader semantics (roles, names, live regions); composited contrast in both themes; the first screen at 375 px; reduced motion; 2.4.11, 2.5.7 and 2.5.8. |
| **V4 Build, tests, performance** | A fresh worktree with Node 24: `uv sync --locked`, `npm ci`, `just export --check`, `just test`, `just test-web`. Determinism (two exports). `first-load.mjs`. Lighthouse mobile ×3 on `out/` (median LCP, TBT, Performance, Accessibility) with `@lhci/cli`. No console errors. Bundle composition (no full d3, no stray dependencies). The `vercel.json` semantics. |
| **V5 Honesty and licences** | Every number has a badge; total labels appear only where pinned; the top-flows banner shows off 2023-24; linked series are labelled "derived"; no RBI hyperlinks; attribution matches the registry; the methodology limits are complete; no claim that the SAM exists for other years; the fixture guard works (a production build on fixture data fails without `ALLOW_FIXTURE=1`). |

### 7.1 Gate to Checkpoint C

- All five verifier reports have no open "high" findings.
- `just test` and `just test-web` are green, on real data (not `ALLOW_FIXTURE`).
- `export --check` is clean.
- The Phase 3 headline section is merged into `ISSUES.md`.
- The proposed D3-x rows are listed for the owner in the report, but not written to DECISIONS.md without approval.

### 7.2 Checkpoint C deliverables (orchestrator)

1. `docs/phase3/CHECKPOINT_C.md` for the owner, in plain English: what was built; screenshots (desktop and mobile, light and dark) in `docs/phase3/screenshots/`; the verifier summaries; what is estimated and how the site shows it; known limits; the decisions to confirm (D3-2 … D3-17); the questions in §9; whether WebKit e2e ran; agents spawned, approximate tokens and wall-clock time (SPEC rule 7).
2. **A protected preview link:** a Vercel *preview* deployment (not production) of `web/`, with Deployment Protection (Vercel Authentication) on. Then `curl -I` checks of the 308 redirect, the `/data/` immutable header, the CSP and the `index.json` cache header against the preview, with the results in the report (and the expected `vercel.live` CSP errors noted).
3. Until the owner authorises the Vercel step (§9, Q2), the fallback deliverable is the built `out/` folder, `npx serve out` instructions and the screenshots. The report says plainly that no link exists yet.

---

## 8. Proposed decisions (for the owner at Checkpoint C; not written to DECISIONS.md)

| # | Decision | Reason |
|---|---|---|
| D3-2 | **Honest time slider:** the balanced map only for 2023-24; every other year shows a "top flows" board with a banner, share-of-GDP widths on the same base, no interpolation, data-driven markers for every base change, splice and concept break, linked (derived) series off by default; scrubbing never silently switches views. | A SAM exists for one year; inventing others would break SPEC rule 1. |
| D3-3 | **Two labels per figure:** an "official total" label when the sum is pinned to a published figure (equal or narrow band, or a passing series check), and a split label (official, derived, estimated, set by balancing). "Set by balancing" only where the move needs an explanation, has a verdict, or sits on a §6b judgement band; smaller moves keep their prior label with "adjusted by X%". | Makes CHECKPOINT_B §8 mechanical: "reliable" totals read as reliable, and estimates are not hidden behind a near-universal "balanced" label. |
| D3-4 | **Zoom hierarchy and presets:** a simple 11-node default (producers merged, financial markets folded into saving and investment), 13 level-0 groups (Centre and States separate), 27 level-1 groups, 128 accounts. The SUT 155×67 drill-down moves to v2. | The first screen must teach in 60 seconds; the full map remains one tap away. |
| D3-5 | **Custom unrolled-circular layout** in the browser: account cells as atoms, positive and negative parts drawn separately, nested return lanes, gutter routing, stubs in the simple view, internal flows listed. | Only one SAM year exists; zoom states are combinatorial; d3-sankey cannot route return flows; heights must not change with zoom. |
| D3-6 | **Web data contract:** content-addressed `web/public/data/<data_version>/` plus `index.json`; JSON Schemas with generated types; money 2 dp, shares 6 dp; reproducibility by `export --check` and a hash-seed test, not `data/manifest.json`. | Immutable caching; no changes to Phase 1/2 manifest code. |
| D3-7 | **Citations resolved to clean-data leaves**, ordered by direct input; RBI hosts cited without links until permission. | SAM records carry no URLs themselves. |
| D3-8 | **Messages split by namespace**; map labels and descriptions in two content files; `StoryFig` and `DataFig` passed per page. | Parallel work without conflicts; small first load. |
| D3-9 | **Story numbers only through bindings** to export-computed figures; satellites rescaled to balanced totals; a lint bans digits in prose; independent DuckDB recomputation. | Number fidelity by construction. |
| D3-10 | **`just test` also runs vitest on Node 24**, failing loudly on the wrong Node or missing `node_modules` unless `--no-web`. | One command per layer; no silent environment fallback. |
| D3-11 | **CSP** allows inline scripts (Next static export's RSC payload and the theme script), no `eval`; `vercel.json` with `framework: null`. | A known framework constraint; headers applied by Vercel to static output. |
| D3-12 | **Static permalink pages** for level-0 links of both presets (~75) and the 69 series, rendered at build time; deeper selections live in the URL. | Keeps the export small; deep links work without JS. |
| D3-13 | **System fonts** with tabular numerals. | Performance budget. |
| D3-14 | **The preview** is a Vercel preview deployment with Deployment Protection, created only after the owner authorises it. | SPEC Checkpoint C. |
| D3-15 | **The remittance story** uses average shares, says "first round only", labels the UAE figure estimated (bank-channel survey share applied to all transfers), and says Dubai cannot be isolated. | Honest framing; no model claims before the Engine. |
| D3-16 | **One number-formatting rule set**, mirrored in Python and checked with golden files. | Verifiers can recompute what the screen shows. |
| D3-17 | **Phones get a list-based map view**, not a transposed Sankey; diagram marks rely on the WCAG 2.5.8 "equivalent" exception, with the list/table as the ≥ 24 px route. | A 13-column Sankey cannot be read at 343 px; accessibility is met by the equivalent, not by pretending thin ribbons are big targets. |

---

## 9. Risks and open questions

### 9.1 Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | Next 16.3.8 + next-intl 4.14 + `@next/mdx` under Turbopack in static export misbehaves (MDX by locale, `setRequestLocale` coverage, build-time fs reads). | U2 proves the stack in its first 90 minutes with one MDX page (remark-gfm as a string plugin), one dynamic segment with `dynamicParams = false`, and one server component reading data with `fs`. If MDX fails, stories and methodology become JSON step files rendered by a tiny renderer; the bindings are unchanged; logged in `issues/U2.md`. |
| R2 | Playwright browsers (~300 MB) cannot be downloaded, or **WebKit does not run on macOS 27** (unverified). | U2 runs `npx playwright install chromium webkit` and one WebKit smoke test at t0. If WebKit fails, it is logged in ISSUES, WebKit e2e is marked "NOT RUN ON THIS HOST" (never a silent pass), and the Checkpoint C report says so and proposes a Linux CI run. If Chromium cannot be installed, `test:web` reports "E2E NOT RUN" and Checkpoint C waits. |
| R3 | The full map is still hard to read (return arcs, gutters). | The simple preset is the default; return flows are stubs there; V2/V3 review legibility; the phone view does not use the Sankey. |
| R4 | The top-flows board is sparse in early years (12 flows in 1950-51). | Shown honestly with the coverage counter. |
| R5 | `provenance.json` or `pinned.json` exceeds its budget. | Split by prefix (provenance) or by level (pinned); the contract allows it. |
| R6 | Agents collide in one checkout (installs under running tests, builds, ports, generated files). | §4.15: install and build locks with pid-based staleness, dependency freeze at t0 + 90 min, per-unit dev dirs and ports, ownerless generated files. |
| R7 | Content drifts from data. | No digits in prose (lint), V2 review, V1 fidelity check. |
| R8 | The label thresholds (explanation threshold for "set by balancing"; 10% for the split headline; pin width ≤ max(₹1 crore, 0.1%)) are not what the owner wants. | Isolated in `status.py`/`status.ts`, one golden file; raised at Checkpoint C (Q5). |
| R9 | Vercel header precedence differs from what is assumed. | `index.json` is read at build time only; the preview `curl` checks confirm it. |
| R10 | Time: about six units in one night, with more scope than revision 1 (first screen, phone view, pinned totals). | The chord view is optional; level-1/2 permalink pages are out; the "Full diagram" region on phones can ship as a link to the desktop layout if time runs out (logged). |
| R11 | The build-time SVG render of the map and the client hydrate disagree (hydration mismatch). | The layout is a pure function of data and preset; the server renders the default state only; the client applies URL state after mount; `smoke.spec` fails on any hydration warning. |

### 9.2 Questions for the owner (defaults in brackets; nothing blocks tonight)

1. Approve the proposed decisions D3-2 … D3-17. [Proceed as proposed.]
2. **Vercel:** may we create a project under your Vercel account and deploy a protected preview? Hobby or Pro? STACK §5.1 notes that Hobby is non-commercial only. [No deploy until you say yes; local build plus screenshots meanwhile.]
3. **Pre-launch permissions** (RBI deep links, caching and the remittance survey figure; MoF, SEBI, GSTN, DGCI&S, CAG; ISSUES P1-9 and P0-7) are needed before any public launch. [The preview withholds RBI links.]
4. The site title and attribution line: "India's Economy as a Working Model", by Udgam Labs? [Use that title; credit Udgam Labs in the footer.]
5. The labels: is "set by balancing" (reserved for moves that need an explanation, have a verdict or sit on a judgement band) the right cut, and should the other 37 binding bands also be flagged? [As proposed; the 37 are listed in the report.]
6. The SUT 155×67 drill-down (ACCOUNT_STRUCTURE D6): v2, or needed before launch? [v2.]

---

## Appendix A. Review responses

Critique 1 (economics/data) and critique 2 (UX/engineering), item by item. "Adopted" means the fix is in the plan as the reviewer proposed; otherwise the change or the reason is given.

### A.1 Critique 1 (economics/data)

| # | Item | What was done |
|---|---|---|
| 1 | Blocker: official totals labelled "balanced" | Adopted, generalised: `total` and `split` labels (§3.4.2). A total is pinned by an exact disjoint union of narrow official/derived constraints or passing series checks. Re-checked: 16 of 62 level-0 pairs pinned, including HH→PRDS, HH→SI, ROW→HH, FACT→HH and PROD→FACT. Golden cases added. Pins are precomputed for all 4,505 node pairs (`pinned.json`). |
| 2 | "Balanced" threshold far too low | Adopted (§3.4.1): "set by balancing" only when the move needs an explanation, has a verdict, or sits on a judgement band; otherwise prior label plus "adjusted by X%". Re-checked: 472 entries (₹389.81 lakh crore abs) instead of 2,127 (₹1,087.6). |
| 3 | `band_edge` catches rounding bands; no `kind` join; ignores the binding `min` | Adopted the curated list (`judgement_bands.yaml`, exactly the 11 §6b ids, test against §6b) and documented the join. The binding `min` (v1a public-admin CE floor) and the other 37 binding bands are not flagged; the panel lists every binding constraint anyway, and U1 lists the 37 for the owner (Q5). |
| 4 | X_DISC mis-described | Adopted: per-ref text (`disc_text.yaml`), node renamed "Discrepancies and reconciliation items", D4 = 0 stated; the §1 table records all five items, verified in the entries. |
| 5 | Node heights break with negatives and change with zoom; PRDS 750.99 vs 671.79 | Adopted: account cell is the atom; positive and negative parts are separate links; height = drawn inflow = drawn outflow, independent of other nodes' zoom; tax and subsidy legs drawn separately. Re-checked heights listed in §3.2 (PRDS 677.82, CEN 43.80, TAX 60.70). |
| 6 | Sign check not mechanical (F49, M10) | Adopted (§3.7.3 rule 4): any negative year requires `reversible: true` with text, or the export fails; F49 (3 years) and M10 (8) are reversible; F11, M09, M11 excluded. |
| 7 | TAX node misleading in top-flows view | Adopted: TAX merged into GOV in `ts_nodes`; M07 drawn PRODUCERS→GOV "net taxes on products"; tax heads listed in the GOV panel. |
| 8 | p7b is the prior split | Adopted: `satellite_share` kind, labelled estimated, "prior split, rescaled", parts-sum test. Re-checked the gaps (8.34 vs 8.62, 8.55 vs 8.29, 1.44 vs 1.49). |
| 9 | Cess flows on to States; UTGST | Adopted: compensation grants (₹44,946 crore, official), cess-loan transfer (₹78,104 crore, derived, T2b `cess_loan_recovery`) and the K8e repayment shown; UTGST named (₹5,772 crore). |
| 10 | "Per ₹100 of government outlays" double counts | Adopted: consolidated GG outlays defined in YAML (current ₹57.26 lakh crore excluding K3a and Centre–State transfers; capital ₹14.14 from I1a, I3a, K6 to non-government accounts); financial assets (₹5.91) shown separately. |
| 11 | UAE figure label and concept | Adopted: the s3 figure, labelled estimated; 0.192385 reconciled as 19.2 / 99.80; bank-channel concept note; added to the P1-9 permission list. |
| 12 | "What the consumption buys" assumptions | Adopted: rescaled p7b `pfce` for taxes; imports labelled estimated (proportionality); margins domestic; X_DISC D1 as its own "unallocated published residual" line (2.3% of household outlays); group saving named as a residual. |
| 13 | Story 3 economics | Adopted, with one correction: acquirer cells are mostly K8d, but households are K7a (official) and RoW K8b. Title "government securities (Centre and States)"; "pooled, not traced"; K9 residuals and K9b shown; net lending defined and checked (Centre −11.47, States −5.84 lakh crore, assets − liabilities match); F25 shown as two values, not a trend. |
| 14 | Trend matching | Adopted the absolute-share basis and the SAM 2023-24 marker; added a 50–95% "overlapping series" tier so F24 (77% inside Centre→States) is still shown, with where the rest sits. Re-checked F14 (+5.6%) and F24 (+28.2%). |
| 15 | Only one base break on the slider | Adopted: every `segment_join` (34), `concept_break` (1), `base_change` (7) and segment boundary is a data-driven marker, tested. |
| 16 | `old_base_structure` scope | Adopted: curated `old_base_scope.yaml` starting from the 4 records (26 entries, ₹7.70 lakh crore), with U1 deciding T4a and T3 explicitly; no transitive walk; V2 reviews. |
| 17 | `assumption_only` never fires | Adopted: transitive `depends_on_assumption` (6 SAM records take the R17 assumption as input). |
| 18 | Provenance ranking undefined | Adopted: direct-input order, then frequency, then source id; the 59 URL-less clean records cited by name and table. |
| 19 | Margins at level 1 | Adopted: flows inside PRDS (and PRODUCERS) stay internal at every zoom and are listed. |
| 20 | Label table not exhaustive | Adopted: an explicit else branch fails the export; the test asserts it is never reached. |
| 21 | Framing of gross flows and dissaving | Adopted: framing line beside % of GDP on gross flows (§3.3); "the Centre's negative gross saving (dissaving)" wording (§3.9, §4.5.4). |

### A.2 Critique 2 (UX/engineering)

| # | Item | What was done |
|---|---|---|
| 1 | No 60-second lesson on a phone | Adopted: §4.0 first screen (h1, headline cards with badges incl. "of every ₹100 households pay out", three story cards), `simple` default preset, `first-screen.spec.ts` at 375×812. One change: return flows in the simple preset are drawn as labelled stubs rather than switched off, so node heights still add up visibly. |
| 2 | Level 0 unreadable at 375 px | Adopted: no transposed Sankey below 640 px; `MapMobile` list view; full diagram in a focusable 2-D scroll region; guard of 60 links below 640 px. |
| 3 | Return-link port order causes crossings | Adopted: return ports at the bottom on both sides; lanes nested by span; a crossing-count test (expected 0). |
| 4 | Same-column links under the diagram; long bands through nodes | Adopted: same-column side arcs in a gutter; gutter routing with virtual waypoints for skipped columns; "no ribbon through a non-endpoint node" invariant test. |
| 5 | Keyboard model contradictory | Adopted: one Tab stop, the exact arrow/Enter/`+`/`−`/`L`/Esc grid, `role="button"` marks in a `flow map` group with a help line, SVG focus ring, non-modal panel with focus to heading and back on Esc, in-flow panel on phones; `map.spec.ts` rewritten to it. |
| 6 | Target size fails the axe gate | Adopted: the 2.5.8 "equivalent" exception via the always-present list/table; marks stay focusable for keyboard users; `[data-mark]` excluded from axe `target-size` and `mobile.spec` with a written justification (proposed D3-17). |
| 7 | Contrast test does not test what is drawn | Adopted: composited colours at the real opacities (constants imported from `lib/sankey/style.ts`), edge strokes when fill < 3:1, label halos, hatch visibility, status in the label on thin ribbons. |
| 8 | Views do not line up at the 2022-23/2023-24 boundary | Adopted: both views scale by share of GDP with one constant; explicit crossfade plus banner; scrubbing into 2023-24 keeps the top-flows view. The node-set change (GOV vs TAX/CEN/STA) remains, but only on an explicit switch; `ts_nodes` now equals the simple preset otherwise. |
| 9 | Fixture cannot be served; dev data path undefined | Adopted: `DATA_ROOT` switch, build-time `fs` loader instead of a static JSON import, `sync-fixture.mjs` into `public/data-fixture/`, `ALLOW_FIXTURE=1` for early e2e (never cited at Checkpoint C); the exporter replaces `index.json` last and atomically. |
| 10 | Fixture must be balanced | Adopted: `pipeline/export/fixture.py` generates it on the real accounts with `pipeline.sam.balance.gras` (2 negatives, 1 internal flow), validated with the same schemas and identity tests; `fixture0000` allowed in the version pattern. |
| 11 | `setRequestLocale` everywhere | Adopted: every page, layout and `generateMetadata`; `dynamicParams = false`; a grep test; in the definition of done. |
| 12 | `mdx-components.tsx` location | Adopted: `web/src/mdx-components.tsx`; `@content/*` alias; string plugins under Turbopack noted in R1 and §4.14. |
| 13 | Two `<Fig>` bindings share one name | Adopted: `<StoryFig id>` and `<DataFig path>`, passed per page; U2 stubs both; tests pointed at each. |
| 14 | Parallel-checkout hazards | Adopted: installs under an install lock and a freeze at t0 + 90 min; per-unit `NEXT_DIST_DIR` and `port: 0` for dev, only builds locked, pid-based staleness (no stealing); tsconfig excludes `.next*`; generated files ownerless. |
| 15 | Dependency list incomplete | Adopted: `@tanstack/react-virtual`, `@lhci/cli`, `remark-gfm` added; `d3-selection`/`d3-transition` dropped with the FLIP decision; `size-limit` replaced by `first-load.mjs`. |
| 16 | Client-only Map risks LCP; permalinks need build-time data | Adopted: default state rendered at build time from `fs`; URL state applied by a client child after mount; the same loader for permalink pages; `crossOrigin="anonymous"` on fetch preloads, and first-view data passed as props instead of preloaded twice. |
| 17 | First-load JS budget unenforceable | Adopted: `first-load.mjs` sums the chunks referenced by `out/en/index.html`; descriptions lazy (`map-desc.json`); `NextIntlClientProvider` gets only the page's namespaces. |
| 18 | `just test` runs vitest on Node 26 | Adopted: `.npmrc` `engine-strict=true`; `cmd_test` resolves Node 24 from the keg path or fails loudly; `node-check.mjs` in every web script. |
| 19 | `test-web` recipe passes the recipe name | Adopted: `sys.argv[2:]`, `shutil.which("npm")`, and `scripts/test-web.mjs` routes arguments to Playwright only. |
| 20 | Node-height invariant vs negatives | Adopted (with item 1.5): height = Σ drawn inflow = Σ drawn outflow, tested exactly. |
| 21 | Snapshot churn | Adopted: coordinate snapshots only on the fixture; invariants on real data. |
| 22 | Root layout, `lang`, 404, hydration warning | Adopted: pass-through root layout, `<html lang suppressHydrationWarning>` in `[locale]/layout.tsx`, root `not-found.tsx` with its own `<html>`/`<body>`. |
| 23 | `vercel.json` with the Next preset unverified; CSP vs preview toolbar | Adopted: `"framework": null`; precedence verified by the preview `curl` checks; `vercel.live` CSP errors expected on the protected preview and noted, CSP not loosened. |
| 24 | Reduced motion and the slider | Adopted: Play kept with instant steps; announcements only on manual step, pause or stop; ≥ 24 px thumb plus a year `<select>`; `map.spec` asserts Back restores selection and zoom, not the year. |
| 25 | Test matrix too large and non-deterministic | Adopted: axe on every route type plus 5 flow and 5 series pages in both themes and viewports; smoke on all routes in Chromium; `reducedMotion: 'reduce'`, `page.clock`, fixed workers, seeded or listed samples (V1's 30 panel states listed in a file); `fidelity.spec` aggregates with its own code. |
| 26 | WebKit on macOS 27 unknown | Adopted into R2: install and smoke at t0; if unsupported, logged, marked "not run on this host", and reported; Linux CI proposed. |
| 27 | React and D3 contend for `d` | Adopted: React renders final attributes; a `useLayoutEffect` FLIP tween with rAF that a new render cancels; no D3 transitions on React-owned elements. |
| 28 | Heat-map and stories on a phone | Adopted: 13×13 default below 640 px; canvas grid role, instructions and live-region format specified; phone stories use the simple preset with only the highlighted links at a fixed height plus an inline flow list. |
