# Phase 0 — Technology stack and repository structure (proposal)

Status: **proposal for Checkpoint A**. Nothing is scaffolded yet.
Prepared: 2026-09-29. **Revised the same day after an independent review.** Section 11 lists each review point and what I did with it.
Every version number below was checked live on 2026-09-29 (PyPI, npm registry, endoflife.date, official docs). The evidence is in section 10.
Scope: SPEC sections 6–9 (stack, repo layout, tests, workflows). Data-source research is done by other Phase 0 agents and is **not** covered here.

---

## 0. Decision summary

| # | Area | Recommendation | Main alternative rejected | Why (one line) |
|---|------|----------------|---------------------------|----------------|
| 1 | Python version | **Python 3.14** (3.14.7 current), pinned in `.python-version` | 3.13 / 3.15 | Every key package ships Windows wheels for 3.14 (checked). Supported to Oct 2030. 3.15 is still a release candidate. |
| 2 | Environment and lockfile | **uv** (0.12.x) with a committed `uv.lock` | pip + requirements.txt, conda | One tool installs Python itself plus exact versions from a cross-platform lockfile. |
| 3 | Dataframes | **polars is the only transform engine in the pipeline.** pandas is used only inside ingest adapters for awkward Excel/PDF. **DuckDB is used by verifier agents** to recompute figures independently, and for ad-hoc queries, but never inside the pipeline. | pandas everywhere; polars and DuckDB both in the pipeline | One engine is less to learn and gives fewer sources of non-determinism. polars has a SQL context for places where SQL reads better. A second engine used by the verifiers fits SPEC rule 3. |
| 4 | Numerics | **numpy + scipy** | — | Standard. Used for matrix inversion, RAS and multipliers. |
| 5 | Schema checks | **pandera** (0.33) schemas for every clean table | hand-written asserts; Great Expectations | Declarative, supports polars, and lives in the codebase. |
| 6 | Tests | **pytest** (9.1) with markers per layer and per phase. No snapshot library: the sha256 manifest plus schema tests cover exported JSON. | unittest; syrupy snapshots | De-facto standard. Snapshot "update" commands make it too easy to accept changed data silently. |
| 7 | Byte-identical re-runs | **Pinned threads** (BLAS/OpenMP/polars = 1) + `PYTHONHASHSEED=0` + **canonical rounding** of every float before writing + one shared Parquet/JSON writer + a **sha256 manifest**. The **Linux CI runner is the authoritative build**: exact hash match there. On Windows, a documented tolerance comparison is used. | "Trust it"; raw-byte equality across operating systems | Probe: `np.linalg.inv` gives different bytes with 1, 4 or 28 BLAS threads, but identical bytes after rounding to 1e-10 (section 10). |
| 8 | Versioning of series | **Content hashes + `data/manifest.json` in git.** The manifest records a **code hash** (a hash of the source tree plus `uv.lock`), not a git commit. Raw files are archived outside git, and their `.meta.json` sidecars are committed. | DVC; git-LFS; recording the git commit | Outputs are small (MBs). A git commit hash cannot name the commit that contains it, so it would change hashed outputs on every commit. |
| 9 | Provenance | Every value row carries a `prov_id`. A **provenance table** keyed by `prov_id` holds source, URL, table/series ID, retrieval date, unit, price basis, base year, vintage, status, raw-file hash, method note and code hash. A **lineage table** covers derived values and SAM cells. | Metadata only at file level | SPEC rule 1 demands per-figure provenance, including "estimated" labels on individual years. |
| 10 | Orchestration | **`just`** (a task runner) with `[windows] set shell := ["powershell.exe", "-NoLogo", "-Command"]`. Every recipe is a one-line call into Python or npm. A small Python **stage runner** (`python -m pipeline.run`) does a **full rebuild by default**; caching is opt-in, with a precisely defined key. | Makefile; Snakemake; Dagster; a hand-rolled skip-if-unchanged by default | `make` is not installed on your PC. By default `just` needs `sh`, which is **not** on your PATH (checked), hence the Windows shell setting. A full rebuild cannot leave stale outputs. |
| 11 | Raw-data cache | `data/raw/<source>/<YYYY-MM-DD>/…` is written only by fetch code and never overwritten. The raw files are **not in git**, but their `.meta.json` sidecars are. **`just fetch-archive`** restores raw files from the archive by sha256. Raw and repro tests **fail loudly** if raw files are missing. | Commit raw files; skip tests silently when raw is absent | Some raw files are too large for git, and redistribution depends on each licence. CI and fresh clones still need raw files to prove reproducibility. |
| 12 | SAM balancing | **Custom RAS/GRAS in numpy** (transparent, handles negative cells) + **cross-entropy via cvxpy 1.9 with the Clarabel solver**. Every cell change is logged to Parquet and summarised in `BALANCING.md`. | `ipfn` package; GAMS; scipy SLSQP | `ipfn` was last released Dec 2021. GAMS is commercial. SLSQP is unreliable with ~10k variables. cvxpy ships an open solver for the exponential cone that entropy objectives need. |
| 13 | SAM multipliers | numpy offline → export **only the coefficient matrix A_n**, rounded to a stated precision (1e-12). **Both numpy and the browser compute M = (I − A_n)⁻¹ from that same exported A_n.** Identity and parity tests run on the exported file. | Exporting A_n and M rounded separately; a server-side API | A_n and M rounded separately disagree with each other. A ≤100×100 inversion takes milliseconds in TypeScript. |
| 14 | ABM offline | **Custom numpy-vectorised ABM** (agents as arrays) | Mesa 3.5 (Mesa 4 in alpha) | Macro ABMs with 10⁵+ households are slow as per-object Python. The array design ports 1:1 to the browser. Mesa's API is mid-transition to v4. |
| 15 | ABM in browser | **Plain TypeScript with typed arrays in a Web Worker**, same seeded PRNG as Python. Parity is tested against a Python "lite" reference **within a documented tolerance on aggregate outputs**, in Chromium, WebKit and Firefox. | Pyodide; Rust/WASM | Pyodide needs about 8.9 MB compressed before numpy even starts (measured). Rust adds a third language. Exact parity is impossible because JS `Math` precision varies by browser (MDN). |
| 16 | Web framework | **Next.js 16** (Active LTS). Pin **`next@^16.3.7`** at scaffold time: 16.3.7 is a security release announced for 30 Sep 2026, and 16.3.6 is current today. App Router, `output: 'export'` static site, React 19. **TypeScript `~6.0.3`, not 7.x.** | Astro 7; SvelteKit 2; TypeScript 7 | This is your stated preference and runs on Vercel. TypeScript 7.0 ships no compiler API, and Microsoft says MDX workflows must stay on 6.0 for now. |
| 17 | Flow visualisation | **D3 (v7.9) with custom rendering**: a d3-sankey "unrolled circular flow" view with **fixed node order across years**, a SAM matrix/heat-map view **drawn on canvas** (with a table alternative), and a d3-chord view for transfers. Zooming is semantic (group/ungroup accounts), not pinch-to-zoom. | ECharts 6 Sankey; Observable Plot; deck.gl; visx | A SAM is **circular by definition**, and both d3-sankey and ECharts Sankey reject cycles (the ECharts issue was closed "not planned"). Either way we must design the unrolling ourselves, so we take D3's full control and small size. |
| 18 | i18n | **next-intl** (its docs explicitly support static export, with a locale prefix required). UI text lives in `web/messages/<locale>.json`, story text in `web/content/<locale>/`, with an `/en/` URL prefix from day one. `/` → `/en/` is a permanent redirect in `vercel.json`. Numbers use `Intl.NumberFormat('en-IN')`. | Hard-coded English strings; an in-house loader | Hindi can be added without touching components. |
| 19 | Accessibility | WCAG 2.2 AA: every chart has a "view as table" alternative, keyboard navigation, no drag-only interactions, ≥24 px targets and `prefers-reduced-motion`. Automated axe checks run in Playwright. | Retrofitting later | WCAG 2.2 has been a W3C Recommendation since 12 Dec 2024. Its new AA criteria (2.5.7 dragging, 2.5.8 target size) apply directly to a slider and a zoomable chart. |
| 20 | Hosting | **Vercel, static only** (no server functions) + a **`vercel.json`** for the root redirect, immutable caching of versioned data, and security headers. **Supabase is not needed** for Phases 0–6 as specified. | Supabase from day one | No feature in the SPEC needs a database. Scenarios fit in a shareable URL. Next's static export cannot emit redirects or headers itself. |
| 21 | CI / scheduled refresh | **GitHub Actions**: tests on every push/PR. Phase 6 cron jobs fetch → rebuild → test → **open a pull request using a dedicated token** (fine-grained PAT or GitHub App), so the normal CI runs on it automatically. | Auto-publishing refreshed data; opening PRs with the default `GITHUB_TOKEN` | "No silent fallbacks": a person or verifier agent approves data changes. PRs opened with `GITHUB_TOKEN` get CI runs that wait for manual approval (GitHub docs). |
| 22 | Monitoring | A failed refresh or format change → the workflow opens a GitHub Issue labelled `source-broken`, and GitHub sends its failure email. **An external "dead-man's switch" monitor** is pinged by each successful scheduled run, so a silently disabled schedule is noticed. Vercel Web Analytics / Speed Insights (free tier) cover the site. | A heartbeat workflow in the same repo; a paid observability stack | A heartbeat inside the repo is disabled by the same 60-day inactivity rule as the jobs it is meant to watch. |
| 23 | Test commands | `just test` = every offline Python layer + vitest (fast, no browser). `just test-web` = production build + Playwright (e2e, a11y, worker, parity in 3 browsers). `just test-live` = network canaries. `just test-phase N`. Lighthouse CI and size-limit run **in CI only**. | One command that also runs browsers and Lighthouse | Meets SPEC §7 ("tests that pass with one command") without making the owner's command brittle. |
| 24 | Node.js | **Node 24.x LTS**, pinned in `web/package.json` `engines` ("24.x") and `.nvmrc`. `web/package-lock.json` is committed and `npm ci` is used everywhere. Stay on 24 until **Vercel lists 26.x** (today it offers 24.x, 22.x and 20.x). | Moving to Node 26 on 2026-10-28 | The build must run on the same major version locally, in CI and on Vercel. |
| 25 | Line endings | **`.gitattributes` from the first commit**: `* text=auto eol=lf`, explicit `eol=lf` for json/yaml/md/csv/py/ts, and `binary` for parquet/xlsx/pdf. All writers use `newline="\n"`. A test fails if any hashed text file contains CRLF. | Relying on each machine's git config | Your git sets `core.autocrlf=true` system-wide (checked), which would make committed JSON hash differently on Windows and Linux. |

**Decisions I need from you** are in section 9: repo public or private, Vercel plan, raw-data archive location, and three new access items (a PR token for refresh jobs, an archive credential for CI, and an external heartbeat monitor).

---

## 1. Data pipeline

### 1.1 Python version — Python 3.14
- Current releases: 3.14.7 (5 Aug 2026, supported to 31 Oct 2030) and 3.13.15 (supported to 31 Oct 2029). Python 3.15 is only at `v3.15.0rc2`.
- I checked the current releases of pandas 3.0.6, DuckDB 1.5.6, numpy 2.5.3, scipy 1.18.1, pyarrow 25.0.1, cvxpy 1.9.3, Clarabel, OSQP and SCS. All of them publish Windows wheels for Python 3.14. polars ships as a pure wrapper plus a runtime wheel. Note that numpy and scipy now **require** Python ≥ 3.12.
- The determinism probes in section 1.5 were re-run on **Python 3.14.7** during the revision (Windows only; Linux is unverified until the first CI run).
- Pyodide 314.x (the in-browser Python) is also built on Python 3.14. We are not shipping Pyodide, but it keeps that option open.
- **Rejected: 3.13.** It is equally workable but has one year less support. **Rejected: 3.15**, which is not final yet. Revisit in mid-2027.
- uv downloads and manages its own Python, so your existing global Python 3.12.7 stays as it is.

### 1.2 uv + `uv.lock`
- uv's docs call `uv.lock` "a *universal* or *cross-platform* lockfile" and say it "should be checked into version control". The same exact versions install on your Windows PC and on the Linux GitHub runner.
- CI runs `uv sync --locked`, which fails if the lockfile is out of date. Per the docs: "uv will raise an error instead of updating the lockfile".
- **Rejected: pip + requirements.txt**, which has no Python-version management and weaker cross-platform locking. **Rejected: conda**, which is heavy, slower and brings no benefit for this package set.

### 1.3 polars as the one pipeline engine; pandas at the edges; DuckDB for verifiers
- **Where each is used:**
  - *Ingest adapters* turn messy government Excel, PDF and HTML into tidy tables. They may use pandas (plus openpyxl or fastexcel) and pdfplumber, because those handle merged headers and odd sheets best. They must convert to polars immediately.
  - *All pipeline transformations*, including cleaning, joins, SAM assembly and aggregation, use polars. Where a step reads better as SQL (e.g. "sum GST by account where year = 2022-23"), use polars' built-in `pl.SQLContext`, which I checked exists in polars 1.44.2. That keeps SQL readability without a second engine.
  - *Verifier agents* (SPEC rule 3) recompute spot-check figures with **DuckDB SQL straight on the Parquet files**. Using a different engine is a feature for independent checking. Comparisons use a tolerance, because the two engines do not agree to the last bit: in my probe, polars and DuckDB group sums differed in 461 of 500 groups, by at most 1.9e-15 relative.
- **Rejected: pandas everywhere.** pandas 3.0 is much improved, but index alignment and silent dtype coercion remain the most common sources of quiet numeric errors. Speed is not the reason: the data is small.
- **Rejected: polars and DuckDB both inside the pipeline**, as the first draft proposed. It meant two engines to learn and two sets of threading and ordering rules to police.

### 1.4 Validation — pandera
- One pandera schema per clean table covers column types, allowed units (`INR_crore`, `USD_million`, …), `price_basis ∈ {current, constant}`, non-null `prov_id`, value ranges and unique keys.
- pandera 0.33 validates pandas, polars, pyarrow and more; the docs list "pandas, polars, dask, modin, ibis, and pyspark".
- **Rejected: Great Expectations.** It needs heavier configuration and a separate "data docs" site, which is overkill here.

### 1.5 Byte-identical re-runs (SPEC Phase 1: "re-running must reproduce identical output")
**What the probes show** (scratch folder, not the repo; details in section 10):
- *Parquet writers are deterministic when versions are pinned.* The same 200,000-row table was written twice with pyarrow, pandas, polars and DuckDB, and gave identical bytes each time. This was first run on 3.13.15 and re-run for polars and pyarrow on 3.14.7. The file footer records the writer version, so **pinned versions (`uv.lock`) are essential**.
- *Linear algebra is not byte-stable across thread counts.* On the same PC with Python 3.14.7 and numpy 2.5.3, inverting a 400×400 matrix gave three different SHA-256 values with `OPENBLAS_NUM_THREADS` = 1, 4 and default (28). After rounding to 10 decimals, all three matched. Your 28-core PC and a 4-vCPU GitHub runner would therefore disagree at the bit level unless threads are pinned and output is rounded.
- *Set order changes per process.* The same set of account labels iterated in a different order under `PYTHONHASHSEED` = 1, 2 and 3.
- *Aggregations:* DuckDB documents that floating-point `sum`/`fsum`/`avg` are "affected by ordering". In my probe, neither DuckDB nor polars group sums changed with thread count, but one probe is not a guarantee, so threads are pinned anyway.

**Rules the pipeline will enforce:**
1. **One writer module** (`pipeline/common/io.py`) for every Parquet and JSON file.
   - **Parquet:** fixed zstd compression, a fixed row-group size, no pandas index, and no timestamps inside the file.
   - **JSON:** `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)`, UTF-8, `newline="\n"`, and one trailing newline.
     - `allow_nan=False` makes a stray NaN an error instead of invalid JSON. Python's default writes `NaN`, which `JSON.parse` rejects (checked).
     - A missing value is written as `null` plus a `status` field, never as NaN.
2. **Canonical rounding before writing.** Every float column is rounded to a precision declared in its pandera schema. The default for ₹ crore values is 6 decimals; coefficient matrices use 12. After rounding, `x + 0.0` removes negative zero: Python writes `round(-1e-12, 6)` as `-0.0`, and `+ 0.0` turns it into `0.0` (checked). The manifest hashes this canonical form.
3. **Everything is sorted by its full primary key before writing.** polars `group_by`/`unique` must use `maintain_order=True` or be followed by an explicit sort. The polars docs say `maintain_order` "Ensure[s] that the order of the groups is consistent with the input data". A simple test scans pipeline code for `group_by(`/`unique(` calls that lack either.
4. **Account order comes only from a committed ordered list** in `pipeline/sam/accounts.yaml` (a YAML list, not a mapping). Matrix rows and columns are never built by iterating a set or dict.
5. **Pinned environment.** `just` and CI export `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `POLARS_MAX_THREADS=1` and `PYTHONHASHSEED=0`. Verifier DuckDB sessions run `SET threads=1`. The pipeline entry point **refuses to start** if any of these is missing. The data is small, so single-threading costs little. Offline ABM scenario batches may run as parallel *processes*, each one single-threaded.
6. The retrieval time lives only in the provenance table and comes from the raw file's `.meta.json`. A re-run from the same raw files therefore changes nothing.
7. **Authoritative build = Linux CI.** `data/manifest.json` is the one produced by CI.
   - `pytest -m repro` in CI does a full rebuild from the archived raw files and requires an **exact** hash match.
   - On Windows, `pytest -m repro` compares keys and schemas exactly and values within a stated tolerance, and prints every file whose bytes differ. It never passes silently: the report says "tolerance mode, not byte-identical".
8. A test runs a small pipeline slice under two different `PYTHONHASHSEED` values and requires identical hashes.

### 1.6 Versioning of series — content hashes + manifest (not DVC, not git-LFS)
- `data/manifest.json` lists every produced file with its SHA-256 (of the canonical form), row count, schema hash and **`code_hash`**. `code_hash` is a SHA-256 over the sorted contents of `pipeline/`, `models/`, `pipeline/stages.yaml` and `uv.lock`. It is deterministic, so it does not change when only docs or tests change.
- **Volatile run metadata stays out of hashed files.** Git commit, run time, host, operating system and thread settings go to `data/runs/<timestamp>.json`, which is git-ignored and excluded from the manifest. CI keeps these as workflow artifacts, and refresh PRs quote them in the PR description.
- The manifest is committed, so any version of the data can still be named by the git commit that contains it.
- **Vintages:** when MOSPI or RBI revise a series, the new release is stored **alongside** the old one, with a `vintage` (release date) and `base_year` column; nothing is overwritten. This matters now. Per search results (a PIB release and a MOSPI press note dated 27-02-2026 appeared in results; I did not open them), MOSPI released a new GDP series with base year **2022-23**, replacing 2011-12. The pipeline must therefore hold both base-year series side by side, and treat any splice of old and new series as `derived` with a documented method. *Verifying the base-year facts is the MOSPI recon agent's job; this is a design implication only.*
- **Rejected: DVC.** It is a capable tool, but it adds its own commands, cache and remote storage for a dataset measured in megabytes.
- **Rejected: git-LFS.** GitHub Free gives 10 GiB storage and 10 GiB bandwidth, and git-LFS adds pointer-file confusion for agents. GitHub blocks individual files over 100 MiB and recommends repos under 1 GB, so large raw files stay out of git either way.

### 1.7 Provenance attached to every value
Tables are stored in "long" format. Every value row has:

`series_id | period | value | unit | price_basis | base_year | vintage | status | prov_id`

- `status` ∈ `official`, `derived` (arithmetic on official numbers), `estimated` (a modelled or imputed value, which the UI must label), `balanced` (changed by the SAM balancing).
- **`data/provenance/provenance.parquet`**, keyed by `prov_id`, holds: `source_id` (from `registry.yaml`), exact URL, table/series ID, sheet/page/cell reference, retrieval timestamp (from `.meta.json`), raw-file SHA-256, licence, unit as published, conversion applied, method note, and **`code_hash`** (not the git commit; see 1.6).
- **`data/provenance/lineage.parquet`** records `output_prov_id → input_prov_id(s)` plus the operation, so every derived number and SAM cell can be traced back to source documents.
- A pandera rule and a test make sure **no value row lacks a valid `prov_id`**, and that any `estimated` row links to a method note.
- The web export carries a compact version, so clicking any flow on the Map shows its source links (SPEC Phase 3).

### 1.8 Orchestration — `just` + a tiny stage runner
- The **`justfile`** holds the handful of commands you would type: `just setup`, `just fetch`, `just fetch-archive`, `just pipeline`, `just sam`, `just models`, `just export`, `just test`, `just test-web`, `just web`.
  - The first lines are `set export`, the pinned environment variables from 1.5, and:
    ```
    [windows]
    set shell := ["powershell.exe", "-NoLogo", "-Command"]
    ```
    Without this, `just` runs recipes with `sh`. Its manual says "`sh` must be available in the PATH" on Windows. On your PC, `sh` is not on PATH, and `bash` resolves to `C:\Windows\system32\bash.exe` (the WSL launcher, not Git Bash). Both were checked. The older `windows-shell` setting is **deprecated** in the current manual in favour of this `[windows]` attribute.
  - Every recipe is a single shell-neutral call (`uv run python -m pipeline.run …`, `npm --prefix web ci`, `npm --prefix web run …`), so the same recipe behaves the same way under PowerShell and `sh`. All logic lives in Python or npm scripts, not in the justfile.
  - Install: `winget install --id Casey.Just --exact` or `uv tool install rust-just`. The latest release is 1.58.0.
  - **To verify at scaffold time:** `just setup` and `just test` are run on your PC before I claim they work.
- **`pipeline/run.py`** is a small runner. Stages are declared in `pipeline/stages.yaml` (name, inputs, outputs, function) and run in dependency order.
  - **The default is a full rebuild.** The data is small, so a full run should take minutes; this will be measured in Phase 1. CI always does a full rebuild.
  - **`--cache` is opt-in, for local iteration only.** A stage is skipped only if its cache key is unchanged. The key is the input file hashes + `code_hash` (the whole `pipeline/` and `models/` trees + `uv.lock`) + the stage's parameters from `stages.yaml` + the pinned environment variables. Every skip decision is printed ("SKIPPED sam.assemble: key unchanged").
- **Rejected: Makefile.** `make` is not installed on your PC (checked: `make: command not found`), and Make syntax is unfriendly on Windows.
- **Rejected: Snakemake 9** (its own rule language and DAG concepts) and **Dagster 1.13** (a server, UI and asset framework). Both are too heavy for ~30 stages. We can switch to one of them later if the DAG grows past ~100 stages.
- **Considered, not chosen: dropping `just`** in favour of `uv run task <name>`. `just --list` gives you a readable menu of commands and costs one install. If `just` causes trouble on your PC, the Python entry point is the fallback, since every recipe is already a one-line Python/npm call.

### 1.9 Raw-data caching and the archive
- Only fetch code writes to `data/raw/<source_id>/<YYYY-MM-DD>/<original_filename>`. It places a `.meta.json` beside each file: URL, HTTP status, `ETag`/`Last-Modified`, SHA-256, size, user-agent, retrieval time and robots/terms note. Files are never edited or overwritten; a new download goes into a new dated folder.
- **Git:** the raw files are ignored, and the sidecars are committed:
  ```
  data/raw/**
  !data/raw/**/
  !data/raw/**/*.meta.json
  ```
- **Archive:** every raw file is also uploaded to the raw-data archive (location is your decision, section 9 Q3) under its sha256.
  - **`just fetch-archive`** restores `data/raw` on a fresh clone or in CI by reading the committed `.meta.json` files and downloading each file by hash, verifying the hash as it goes.
  - This is a **prerequisite** of the reproducibility design. Without it, CI has nothing to rebuild from.
- **No silent skips.** If raw files are missing, `-m raw` and `-m repro` **fail** with the message "raw files missing: run `just fetch-archive`".
  - The only way to skip them is the explicit flag `just test --no-raw`, and the test summary then prints a banner: "RAW/REPRO NOT CHECKED".
  - CI never uses that flag.
- If the archive is private, CI needs a read credential stored as a GitHub Actions secret (section 9, access request).
- A test fails if any file under `data/raw` has a hash that doesn't match its `.meta.json`, which catches hand edits.
- GitHub Release assets allow files under 2 GiB each, with "no limit on the total size of a release, nor bandwidth usage". But a public repo would redistribute files, which each source's licence must permit.
- HTTP client: `httpx` with polite rate limits, a real User-Agent string, retries (`tenacity`), and **no** bypassing of logins, CAPTCHAs or robots rules. Blocks are logged to `ISSUES.md`.

---

## 2. SAM balancing

### 2.1 Methods
1. **RAS / GRAS (custom numpy, ~100 lines).**
   - Classic RAS scales rows and columns alternately until row totals equal column totals.
   - Plain RAS cannot handle negative cells, which a SAM does contain: change in stocks, net product taxes, some net transfers. So we implement **GRAS** (Junius & Oosterhaven 2003), which treats positive and negative parts separately.
   - Writing it ourselves keeps every iteration inspectable. It is a textbook algorithm, not a research risk.
2. **Cross-entropy (cvxpy 1.9.3 + Clarabel).**
   - This minimises the information distance between the prior (unbalanced) SAM and the balanced one, subject to constraints: row sum = column sum, **known cells fixed** (e.g. official GDP, BOP totals, tax receipts), optional bounds, and inequality constraints. This is the Robinson–Cattaneo–El-Said approach used in IFPRI-style SAMs.
   - cvxpy "is distributed with the open source solvers CLARABEL, OSQP, and SCS", and Clarabel and SCS both support the exponential cone that entropy objectives need. **No commercial solver is required.**
   - Solver output is rounded to the declared precision before it is written (section 1.5 rule 2), because solver iterates are not bit-stable across machines.
3. **Policy:** run both methods. Cross-entropy is the primary result because it respects fixed official totals. RAS/GRAS is a cross-check. Any cell where the two methods disagree by more than a threshold is raised as a finding.

**Rejected:**
- `ipfn` on PyPI: last release 1.4.4 on 2021-12-30, and it is a black box.
- GAMS: the traditional tool for SAM balancing, but it needs a commercial licence and is not reproducible by the public.
- `scipy.optimize.minimize` (SLSQP): unreliable at ~5,000–10,000 variables.

### 2.2 Logging every adjustment
- Each balancing run writes `data/sam/<year>/balancing_log.parquet`: one row per cell with prior value, balanced value, absolute and % change, direction, whether the cell was fixed, and the constraint(s) that bind. It also records the method, tolerance, iterations, convergence, solver status and objective. Wall-clock times go to the unhashed run log.
- `pipeline/sam/report.py` renders `BALANCING.md` from the log: the largest adjustments, adjustments by account block, and **every cell whose change exceeds the stated threshold, each with an explanation field that must be filled in**. A test fails if any such cell has an empty explanation (SPEC Phase 2 acceptance test 4).
- The acceptance tests (row totals equal column totals, GDP three ways, government, BOP and flow-of-funds totals) run as `pytest -m identities`.

---

## 3. Models

### 3.1 SAM multipliers
- Offline (numpy):
  - Partition the SAM into endogenous accounts (production, factors, households, and usually firms) and exogenous accounts (government, capital, RoW; the choice is documented).
  - Compute the coefficient matrix A_n **and round it to 1e-12**. From here on, this rounded A_n is the single source of truth.
  - Compute M = (I − A_n)⁻¹ **from the rounded A_n**, plus the standard decompositions (Pyatt–Round transfer, open-loop and closed-loop effects).
- Export `web/public/data/<data_version>/multipliers.json`: account labels, **the rounded A_n only**, and leakage shares (imports, taxes, savings). M is not exported.
  - For ~60–100 accounts, that is 3,600–10,000 numbers, about half the earlier estimate because M is gone.
  - Most cells are zero, so a sparse encoding may shrink it further. Measured size is checked against the ≤ 80 KB budget.
- In the browser:
  - On load, a small TypeScript LU solver computes M from A_n once, which takes a few milliseconds.
  - A shock is a vector, and the result is M × shock, which takes microseconds.
  - Tax-rate shocks change A_n itself, so the same solver re-inverts it.
- Tests (all run on **the exported JSON file**, not on Python's in-memory matrices):
  - M ≥ I element-wise, column sums > 1, (I − A_n)·M ≈ I, and the multiplier balance identity.
  - Parity: TypeScript M × shock vs numpy M × shock on 20 random shocks, within a stated relative tolerance (1e-9).

### 3.2 ABM offline — custom numpy-vectorised
- **Design:** each agent type (households, firms by sector, banks, government Centre/States, RBI, RoW) is a set of numpy arrays, not Python objects. Each simulation step is a sequence of vectorised functions (earn → consume → produce → borrow/lend → tax → transfer → policy rule).
- Calibration makes the steady state reproduce the Phase 2 SAM. That is itself a test: `pytest -m abm_steady_state`.
- **Rejected: Mesa.** Current stable is 3.5.1 (March 2026), and a `4.0.0a0` pre-release exists, so the API is mid-transition. Mesa's object-per-agent style is also slow for 10⁵–10⁶ households and does not map onto a browser port.
- **Reproducibility:** one seeded **portable PRNG** (xoshiro128\*\* or PCG32, implemented identically in Python and TypeScript) instead of numpy's default generator.
  - Python and browser runs produce **the same random draws**.
  - Their outputs are compared **within a documented tolerance on aggregate outputs**, not number-for-number (see 3.3 for why).
  - The offline ABM runs with threads pinned (section 1.5), and its outputs are rounded before writing.
- Precomputed scenario results (the SPEC presets) are written to `data/model_outputs/abm/` and exported to the web as JSON.

### 3.3 ABM in the browser — TypeScript in a Web Worker
- A scaled-down "lite" ABM (for example, 2,000 households and 30 firms) runs in a **Web Worker**, so the page stays responsive. It is written in plain TypeScript with `Float64Array`s.
- It talks to the page through plain `postMessage`, batching one message per N steps and passing results as **transferable `ArrayBuffer`s** so they are not copied.
- **Parity, honestly stated.** Exact equality between Python and browsers is impossible:
  1. MDN: "Many `Math` functions have a precision that's implementation-dependent … Even the same JavaScript engine on a different OS or architecture can give different results!"
  2. numpy's `sum` uses "partial pairwise summation" depending on axis and memory layout, while a TypeScript loop sums sequentially.
  3. A model with feedback (credit, thresholds, policy rules) amplifies tiny differences over many steps.

  So the lite model follows these rules:
  - The specification exists once, as a Python reference implementation (`models/abm/lite_reference.py`) written in **plain sequential loops**. It avoids `np.sum` and `math.fsum`, because the point is to use *the same* summation order as the TypeScript loop, not a more accurate one.
  - **No `Math.exp`/`log`/`pow` in state updates.** Where a curve is needed, both sides use the same small deterministic implementation (e.g. a lookup table with linear interpolation), ported line-for-line.
  - **Discrete decisions (defaults, thresholds) compare the integer PRNG output** against integer cut-offs, never floats derived from it, so a 1e-16 difference cannot flip a decision.
  - Tests compare **aggregates per step** (GDP proxy, credit, prices, government balance) with a tolerance that is documented and allowed to widen with step count. A Playwright run executes the worker in **Chromium, WebKit and Firefox** against the same golden file. vitest alone runs only in Node/V8.
- **Rejected: Pyodide.** Measured from the CDN for 314.0.7, the compressed downloads are `pyodide.asm.wasm` 3.44 MB, `python_stdlib.zip` 2.51 MB and the numpy wheel 2.93 MB. That is about 8.9 MB before the first result, which is too much for mobile users on Indian networks.
- **Rejected: Rust/WASM.** It adds a third language and toolchain that you and future agents would have to maintain. Revisit it only if the TypeScript version proves too slow, which is unlikely at a few thousand agents.

---

## 4. Frontend

### 4.1 Framework — Next.js 16 static export
- **Versions.** npm `latest` today is **16.3.6** (22 Sept 2026). The Next.js blog calls 16.x **"Active LTS"** and 15.x **"Maintenance LTS"**. endoflife.date lists 15.x as supported only until 2026-10-21.
- **Security (corrected).**
  - On **22 Sept 2026**, Next.js shipped an out-of-band fix for one critical upstream issue (16.3.6 / 15.5.26).
  - On **23 Sept 2026**, it *announced* a scheduled release for **30 Sept 2026**: 16.3.7 and 15.5.27, addressing "nine vulnerabilities: one critical, two high, five medium, and one low".
  - So **pin `next@^16.3.7`** at scaffold time. If it is somehow not published by then, pin the newest patched release and log it in `ISSUES.md`.
  - A static export has no Next.js server in production, but the client runtime still ships to browsers and build-time code runs in CI. So **Dependabot** watches the `npm` and `github-actions` ecosystems. Python packages are upgraded deliberately with `uv lock --upgrade` in a reviewed PR.
- **TypeScript: pin `typescript@~6.0.3`** (plain package, released 2026-04-16), not 7.x.
  - The TypeScript 7.0 announcement (8 Jul 2026) says "TypeScript 7.0 does not ship with an API. We expect TypeScript 7.1 to ship with a new (and different) API". It also says workflows using "Vue, MDX, Astro, Svelte, and others" must stay on TypeScript 6.0 for now.
  - Our stories are MDX, and editor tooling and typescript-eslint also need the API.
  - Next's own docs say TS 7 works for `next build` only via the local `tsc` CLI, and flag `experimental.useTypeScriptCli` as experimental.
  - Revisit when TS 7.1 ships its API. The decision goes in `DECISIONS.md` at scaffold time.
- **Static export.** The guide (version 16.3.6, updated 2026-08-25) confirms that `output: 'export'` produces plain HTML/CSS/JS. Server Components run at build time, and GET route handlers can emit static JSON.
- **Not supported in static export:** cookies, rewrites, redirects, headers, Proxy, ISR, default image optimisation and Server Actions. **We do need two of these, so they move to `vercel.json`** (section 5.1):
  - a **permanent redirect** `/` → `/en/`. next-intl's static-export recipe is a root page calling `redirect('/en')`, which in a static build is a client-side redirect. That adds a round-trip to first paint on mobile and is weaker for SEO. The root page stays only as a fallback for serving `out/` locally.
  - **response headers**: immutable caching for versioned data and security headers.
- **Rejected: Astro 7.3.5.** It is excellent for content-heavy sites with small interactive "islands", but our core is a single large interactive application (Map → Engine → Simulator sharing state). Astro could be reconsidered if the Methodology/Stories pages grow into a big content site.
- **Rejected: SvelteKit 2.70.3.** It has a smaller ecosystem and is less familiar to you and to most coding agents.

### 4.2 Flow visualisation — D3 with a purpose-built design
**The key design fact:** a SAM is a *circular* flow. Firms pay households, households buy from firms, and money returns to where it started. Sankey layouts need a directed acyclic graph:
- The d3-sankey README says it visualises "flow between nodes in a directed acyclic network".
- ECharts' Sankey throws "Sankey is a DAG, the original data has cycle!", and the request to support cycles (apache/echarts #19505) was **closed as not planned**.

So no off-the-shelf Sankey can draw the SAM directly. We need a designed view. Proposed views, all from the same data:
1. **Circular-flow Sankey (unrolled).**
   - Columns follow the SAM's logic: Activities → Factors → Institutions (households by rural/urban × quintile, firms, government, RoW) → Uses (consumption, investment, government, exports) → back to Activities, which are drawn as a returning ribbon or a repeated column.
   - Laid out with d3-sankey (5.6 KB). Its last npm release was 2019 and the repo was last pushed in Nov 2023, so we **vendor** it (BSD-3 licence allows this) and own any fixes.
   - **Node order is fixed across years.** The order comes from `accounts.yaml` via d3-sankey's `nodeSort`, and the layout is precomputed offline per year. When the time slider plays, ribbons change thickness but nodes never jump position.
2. **SAM matrix / heat-map.** This shows the SAM as accountants know it: rows are receipts, columns are payments, and it is zoomable by block.
   - It is the honest "full detail" view.
   - At ~100×100 it has ~10,000 cells, so it is drawn on **`<canvas>` by default**, with a keyboard-navigable "view as table" alternative and SVG only for the highlighted row, column and labels.
3. **Chord view** (d3-chord, which takes a square flow matrix) for inter-institution transfers, where cycles are natural (Centre ↔ States, banks ↔ households).
4. **Zoom levels** (SPEC: whole economy → sector → sub-flow) are **semantic**. Tapping a node splits it into its sub-accounts; breadcrumbs and buttons go back. This beats pinch-zoom on phones and avoids drag-only interaction (WCAG 2.5.7).
5. **Rendering and animation.**
   - The Sankey and chord views use SVG, since they have a few hundred links after aggregation.
   - Animations (the time slider, and the Phase 4 ripple on the Map) are driven by D3 transitions or `requestAnimationFrame` **outside React reconciliation**. React owns the structure; D3 owns per-frame attribute updates.
   - All animation stops under `prefers-reduced-motion`.

**Rejected alternatives:**
- **ECharts 6.1** (Apache-2.0): its Sankey has the same DAG limit, the full bundle is 1.12 MB minified (tree-shaking helps), and it gives less control over explain-mode animations.
- **Observable Plot 0.6.17**: has no Sankey or chord mark (checked by searching its published bundle).
- **visx `@visx/sankey` 4.0**: a React wrapper around the same d3-sankey. We may borrow its React patterns, but it adds nothing to the layout problem.
- **deck.gl 9.4**: GPU rendering for millions of points or maps; overkill here, and it costs bundle size.
- **sigma.js / cytoscape**: force-directed network graphs. Their free-form layouts suit social networks, not ordered economic flows.

### 4.3 Time slider, themes, accessibility, i18n, performance
- **Time slider.** It is a native `<input type="range">` styled for the site, plus ◀ ▶ step buttons and a "play" button.
  - It is keyboard-operable and needs no drag (WCAG 2.5.7). Year changes are announced through an `aria-live` region.
  - A year is "available" only if the time series has official or derived data for it. Estimated years are visibly marked.
- **Themes.** Light and dark, using CSS custom properties, following `prefers-color-scheme` with a manual toggle.
  - Every colour pair is checked for contrast in both themes: 4.5:1 for text and 3:1 for chart marks (WCAG 1.4.3 and 1.4.11).
  - Colour is never the only signal.
- **Accessibility (WCAG 2.2 AA):**
  - "View as table" for every chart.
  - Nodes and links reachable by keyboard.
  - Focus never hidden behind sticky headers (2.4.11).
  - Targets at least 24×24 px (2.5.8).
  - Animations paused under `prefers-reduced-motion`.
  - Plain-language labels.
  - Tested with `@axe-core/playwright` 4.13 in `just test-web`, plus a manual screen-reader pass at Checkpoint C.
- **i18n:**
  - **next-intl 4.14.7.** Its docs cover static export explicitly: "Using a locale prefix is required", "The locale can't be negotiated on the server" and "Static rendering is required". This resolves the item the first draft left unverified.
  - UI strings in `web/messages/en.json` (ICU MessageFormat).
  - Stories and explanations in `web/content/en/*.mdx`.
  - Routes under `/en/…` from the start; `/` → `/en/` via `vercel.json`.
  - Indian number formatting (`Intl.NumberFormat('en-IN')`, and ₹ lakh crore helpers).
  - A Devanagari-capable font subset (loaded only when Hindi is on) to be added later.
- **Web Worker in the production build.** The Turbopack bundler (the Next 16 default) has had a run of worker-related fixes in 16.3.x release notes (#96307, #96432, #97419). So `just test-web` loads the Simulator **from the exported `out/` folder** in Chromium and WebKit and asserts that the worker returns results.
- **Performance budget (mobile first).** size-limit 14.1 and Lighthouse CI (`@lhci/cli` 0.15.1, last released June 2025) run **in CI only**, not in `just test`, because Lighthouse scores are noisy. You can run them locally with `just test-perf`.

| Budget item | Limit | Enforced |
|---|---|---|
| JS on first load (framework + D3 modules, gzipped) | ≤ 200 KB | CI gate (size-limit) |
| Data for first view (reference-year Map JSON, gzipped) | ≤ 150 KB; other years lazy-loaded | CI gate (size-limit) |
| Engine data (`multipliers.json`, gzipped) | ≤ 80 KB, loaded when the Engine opens | CI gate (size-limit) |
| ABM worker (code + calibration, gzipped) | ≤ 120 KB, loaded when the Simulator opens | CI gate (size-limit) |
| Largest Contentful Paint (Lighthouse mobile profile) | < 2.5 s | CI, median of 3 runs |
| Interaction to Next Paint | < 200 ms | CI, median of 3 runs |
| Lighthouse scores | Performance ≥ 90, Accessibility = 100 | CI, median of 3 runs |
| Animation smoothness (slider play, Engine ripple) on 4× CPU throttle | median frame ≤ 20 ms (≈ 50 fps), no long task > 100 ms | CI **report** from a Playwright trace. It becomes a gate once the numbers prove stable. |

- **Web data format:** JSON written by the one writer in section 1.5. **Vercel compresses on the fly**, so the pipeline does not pre-gzip.
  - If pre-compression is ever added, it must use `gzip.GzipFile(..., mtime=0)` with no filename. On Python 3.14, `gzip.compress` already defaults to `mtime=0`, but `GzipFile` still stamps the current time and the filename (checked).
  - **Rejected: shipping Parquet to the browser** (`hyparquet`/`parquet-wasm`) or **DuckDB-WASM**. They are not needed at these sizes, and DuckDB-WASM costs megabytes.

---

## 5. Hosting and infrastructure

### 5.1 Vercel — static only
- The site is served as static files. There are no serverless functions, and nothing runs Python at build time on Vercel.
  - The pipeline runs locally or in GitHub Actions.
  - Its web outputs (`web/public/data/<data_version>/…`) are committed.
  - Vercel only runs `npm ci && next build`.
- **Node version.** Vercel offers **24.x (default), 22.x and 20.x** and "automatically rolls out minor and patch updates". `engines.node` selects only the *major* version.
  - So we pin `"engines": {"node": "24.x"}` and accept Vercel's patch roll-forward.
  - Locally and in CI, `.nvmrc` (`24`) and `actions/setup-node` with `node-version-file` keep the same major.
  - Your machine has 24.14.0; the latest 24.x is 24.21.0. Updating is recommended but not required.
  - Move to 26 only after Vercel lists it.
- **`vercel.json`** (committed at `web/vercel.json`):
  - `redirects`: `{ "source": "/", "destination": "/en/", "permanent": true }` (Vercel docs: `permanent: true` gives a 308).
  - `headers`:
    - `/data/(.*)` → `Cache-Control: public, max-age=31536000, immutable`. This is safe because every data file sits under a versioned folder that never changes.
    - All pages → a Content-Security-Policy, `X-Content-Type-Options: nosniff` and `Referrer-Policy: strict-origin-when-cross-origin`.
  - *Unverified:* that Vercel applies `vercel.json` redirects and headers to a Next.js `output: 'export'` deployment exactly as described. This is the first test in Phase 3: a Playwright/`curl` check against a preview deployment.
- **Plan caveat (needs your decision).** Vercel's fair-use page says Hobby is "non-commercial personal use only". It defines commercial use as any deployment "used for the purpose of financial gain of **anyone** involved in any part of the production", including "Advertising the sale of a product or service". Donations are not commercial. If the site promotes Udgam Labs' services, it likely needs **Pro** ($20 per developer seat per month, per the Hobby page).
- Hobby includes 100 GB/month Fast Data Transfer and 100 deployments per day, which is ample for a static site.

### 5.2 Supabase — not needed now
Nothing in SPEC Phases 0–6 needs a database:
- Scenarios can be encoded in the URL, so they are shareable without storage.
- Data is static JSON.
- "What changed" notes are generated at build time.

Supabase free projects also pause after a week without database activity ("inactive if it does not receive sufficient user database activity over the past week"), which suits an always-on public site badly.

**Supabase would be justified if** we add any of these:
- (a) user accounts or saved/named scenarios beyond URL length limits;
- (b) a public "report a data error" or feedback form that needs moderation;
- (c) server-side queries over data too large to ship statically (e.g. unit-level microdata explorers);
- (d) server-side rate-limited heavy ABM runs.

None of these is in scope; I would log such a decision in `DECISIONS.md` if it arises.

### 5.3 GitHub Actions
- **`ci.yml`** runs on every push and PR:
  1. `uv sync --locked`;
  2. `just fetch-archive` (using the archive secret);
  3. `just test` (full rebuild, exact manifest check; this is the authoritative build);
  4. `npm ci`, the web build and `just test-web`;
  5. size-limit and Lighthouse CI.
  - Install uv with `astral-sh/setup-uv` (docs example: v9.0.0, pinned by commit SHA) and pin the uv version.
  - Actions are free for public repos on standard runners. Private repos on GitHub Free get 2,000 minutes per month.
- **`refresh-<source>.yml` (Phase 6)** runs on a cron matched to each source's release calendar. The flow is: fetch → compare hashes/ETags → if changed, archive the new raw file, rebuild, test → **open a PR** titled e.g. "GST collections Aug-2026: +X% YoY". Merging deploys. Two GitHub defaults block this and must be handled:
  1. "By default, when you create a new repository in your personal account, workflows are not allowed to create or approve pull requests."
  2. Even when allowed, "when a workflow using `GITHUB_TOKEN` creates or updates a pull request, the resulting `pull_request` event creates workflow runs in an **approval-required** state". So `ci.yml` would not run automatically on refresh PRs, and untested data could be merged by mistake.

  **Fix:** the refresh workflow opens PRs with a **fine-grained personal access token** (scoped to this one repo: Contents read/write, Pull requests read/write) or a **GitHub App** token, stored as the secret `REFRESH_PR_TOKEN`. Then `ci.yml` runs on refresh PRs like any other. `ci.yml` is also made a **required status check** on `main`. *Unverified:* whether required checks and branch protection are available on a **private** repo on GitHub Free. The GitHub page I checked did not state plan availability. This is checked when you decide Q1.
- **Schedules can die silently.** GitHub's docs say "in a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days". Scheduled runs "can be delayed … some queued jobs may be dropped", and the minimum interval is 5 minutes.
  - A heartbeat workflow **in the same repo** would be disabled by the same rule, so the first draft's idea is dropped.
  - Instead, every scheduled run pings an **external dead-man's-switch monitor** at the end. If no ping arrives within the expected window (e.g. 35 days), the monitor emails you. This needs a free account with such a service (not yet evaluated; section 9).
  - *Unverified:* whether commits made by a workflow count as "repository activity" for the 60-day rule, so we do not rely on that.
- **`canary.yml`** runs weekly and checks each registered source URL, HTTP status and a "format fingerprint" (header rows, sheet names, column count). A change opens an Issue. It pings the same external monitor.
- **`.github/dependabot.yml`**: weekly updates for `npm` (in `web/`) and `github-actions`.

### 5.4 Monitoring and alerts
- **Data sources:** a failed refresh or format change opens a GitHub Issue labelled `source-broken`. The workflow creator also gets GitHub's failure email (per GitHub's docs, scheduled-workflow notifications go to "the user who initially created the workflow"). The external dead-man's switch covers the case where nothing runs at all.
- **Site:** Vercel Web Analytics (Hobby: 50,000 events per month) and Speed Insights (10,000 events per 30 days) for real-user performance. A third-party uptime monitor for the site itself is optional and hardly needed for a static CDN site.

---

## 6. Testing — layers and the one command

| Layer | Tool | What it proves | Marker / command | In `just test`? |
|---|---|---|---|---|
| Unit | pytest | Functions do what they say (unit conversions, parsers on saved fixtures, RAS on textbook examples) | `-m unit` | yes |
| Schema / contract | pandera in pytest | Every clean table has the right columns, types, units, keys, declared rounding and a valid `prov_id` | `-m schema` | yes |
| Data quality | pytest | Values in plausible ranges; year-to-year continuity; breaks and revisions against the previous vintage flagged (not silently accepted) | `-m quality` | yes |
| Raw integrity | pytest | Every raw file's hash matches its `.meta.json` (no hand edits). **Fails if raw files are missing.** | `-m raw` | yes |
| Hygiene | pytest | No CRLF in hashed text files; no NaN/Infinity/`-0.0` in exported JSON; no `group_by`/`unique` without order control; pinned environment variables present; identical hashes under two `PYTHONHASHSEED` values | `-m hygiene` | yes |
| Accounting identities | pytest | SAM rows = columns; GDP three ways (with the official discrepancy only); government, BOP and flow-of-funds totals match sources within tolerance | `-m identities` | yes |
| Balancing audit | pytest | No cell moved beyond the threshold without a written explanation | `-m balancing` | yes |
| Reproducibility | pytest | A full rebuild from archived raw data reproduces `manifest.json`: exact on Linux CI; stated tolerance, loudly labelled, on Windows | `-m repro` | yes |
| Model | pytest | Multiplier properties **on the exported A_n**; ABM steady state reproduces the SAM; COVID-2020 and 2022 rate-hike direction checks | `-m models` | yes |
| Python ↔ TypeScript parity | pytest + vitest on shared golden files | TypeScript multipliers and lite ABM match the Python reference within documented tolerance | `-m parity` + vitest | yes |
| Web unit | vitest 5 | Formatting, data loading, maths in TypeScript | vitest | yes |
| End-to-end + a11y + worker + browser parity | Playwright 1.63 + axe-core | Pages render from `out/`; keyboard paths work; no WCAG violations; worker returns results; lite-ABM parity in Chromium, WebKit, Firefox | `just test-web` | no (needs browsers and a build) |
| Performance | size-limit, Lighthouse CI, Playwright trace | Budgets in §4.3 | CI; `just test-perf` locally | no |
| Live canaries (network) | pytest | Sources still reachable and in the same format | `just test-live` | no |

- `just test` runs every offline Python layer plus vitest. It needs no browser download and no network apart from `just fetch-archive` on a fresh clone. `just test-phase N` runs only the layers that exist at phase N, and each phase adds its own.
- If raw files are absent, `just test` **fails** and tells you to run `just fetch-archive`. `just test --no-raw` is the only way to skip, and it prints "RAW/REPRO NOT CHECKED".
- Verification records from the "different agent" rule (SPEC §3.3) live in `docs/verification/`. A test checks that at least 10% of Phase 1 values have a spot-check record. Verifiers recompute with DuckDB (section 1.3).

---

## 7. Repository structure

```
India Economy Model/
├── SPEC.md                  # the brief (you own it; agents don't edit it)
├── DECISIONS.md             # dated decision log with reasons
├── SOURCES.md               # human-readable source catalogue (from Phase 0 recon)
├── ISSUES.md                # loud log of failures, gaps, unclosed reconciliations
├── BALANCING.md             # generated report of every SAM balancing adjustment
├── CLAUDE.md                # rules and how-tos for future agents working in this repo
├── README.md                # what this is, how to run it (3 commands)
├── justfile                 # the only commands you need; [windows] set shell := powershell
├── pyproject.toml           # Python project + tool settings (ruff, pytest markers)
├── uv.lock                  # exact Python dependency versions (committed)
├── .python-version          # "3.14"
├── .gitattributes           # * text=auto eol=lf; *.parquet/*.xlsx/*.pdf binary  (from the first commit)
├── .gitignore               # data/raw/** except *.meta.json; data/runs/; web/out; node_modules
├── .editorconfig            # end_of_line = lf, utf-8
├── .github/
│   ├── dependabot.yml       # npm (web/) + github-actions, weekly
│   └── workflows/           # ci.yml, canary.yml, refresh-*.yml (Phase 6)
├── data/
│   ├── registry.yaml        # machine-readable source registry (URL, access, licence, cadence…)
│   ├── manifest.json        # sha256 (canonical form) + rows + schema hash + code_hash per produced file
│   ├── raw/                 # fetched files exactly as downloaded; files git-ignored, .meta.json committed
│   ├── runs/                # per-run metadata (git commit, time, host, versions); git-ignored, never hashed
│   ├── clean/               # typed, unit-normalised long tables per source (Parquet)
│   ├── provenance/          # provenance.parquet (per prov_id) and lineage.parquet (derivations)
│   ├── sam/                 # per reference year: accounts, unbalanced SAM, balanced SAM, balancing log
│   ├── timeseries/          # the ~50 top flows across years (Phase 2)
│   └── model_outputs/       # multiplier results, precomputed ABM scenario results
├── pipeline/                # Python code that turns raw → clean → SAM → web data
│   ├── run.py               # stage runner (full rebuild by default; --cache opt-in, logged)
│   ├── stages.yaml          # the stage graph: inputs, outputs, function, params per stage
│   ├── common/              # env guard (threads, hash seed), io (Parquet/JSON writer), fetch/cache,
│   │                        #   archive (fetch-archive), hashing (code_hash), units, provenance, schemas
│   ├── ingest/              # one module per source family (e.g. mospi_nas, mospi_sut, rbi_bop,
│   │                        #   rbi_fof, cga, gst, dgcis, sebi, …; final list follows SOURCES.md)
│   ├── sam/                 # accounts.yaml (ordered list), assembly, GRAS, cross-entropy, identities, report
│   ├── timeseries/          # builds the top-flows series (+ precomputed Sankey layouts per year)
│   └── export/              # writes compact, deterministic JSON for the website
├── models/                  # the Engine and the Simulator (Python)
│   ├── multiplier/          # A_n (rounded) + decompositions + export
│   └── abm/                 # vectorised ABM: agents, rules, calibration, scenarios/*.yaml, lite_reference.py
├── web/                     # the Next.js website (static export)
│   ├── package.json         # engines.node "24.x"; next ^16.3.7; typescript ~6.0.3
│   ├── package-lock.json    # exact web dependency versions (committed; npm ci everywhere)
│   ├── .nvmrc               # "24"
│   ├── next.config.ts       # output: 'export'
│   ├── vercel.json          # / → /en/ (308), immutable /data cache, security headers
│   ├── src/app/[locale]/    # pages: map, engine, simulator, stories, methodology (+ root redirect fallback)
│   ├── src/components/      # Map views (sankey, canvas matrix, chord), slider, explain panels
│   ├── src/lib/             # TS maths (LU solve, M from A_n), PRNG, formatting (₹ crore, en-IN)
│   ├── src/workers/         # abm-lite Web Worker
│   ├── messages/            # UI text per language (en.json now; hi.json later)
│   ├── content/             # stories & methodology text per language (en/ now, MDX)
│   ├── public/data/         # generated JSON from pipeline/export, under <data_version>/ (committed)
│   └── tests/               # vitest unit tests + Playwright e2e/accessibility/worker/parity
├── tests/                   # Python tests, one folder per layer
│   ├── unit/  schema/  quality/  raw/  hygiene/  identities/  balancing/
│   ├── repro/  models/  parity/  live/
│   └── fixtures/            # tiny saved source extracts and textbook SAMs for tests
└── docs/
    ├── phase0/              # recon, verification notes, this proposal
    ├── methodology/         # long-form methods (balancing, estimation, multipliers, ABM)
    ├── verification/        # independent spot-check records (value, document, page, verdict)
    └── reports/             # end-of-phase reports (built, failed, estimated, agents/tokens/time)
```

Notes on the layout:
- `pipeline/` and `models/` are both installable Python packages in one uv project. Tests import them directly.
- `web/public/data/` is the **only** bridge between Python and the website, so the website can be rebuilt without Python.
- `data/raw/` (except the `.meta.json` sidecars) and `data/runs/` are the only git-ignored data. Everything else in `data/` is small enough to commit, and the manifest makes every version addressable. If `data/clean` ever exceeds ~200 MB, we revisit this; the options would be Release assets or DVC.
- `.gitattributes` content:
  ```
  * text=auto eol=lf
  *.json text eol=lf
  *.yaml text eol=lf
  *.yml  text eol=lf
  *.md   text eol=lf
  *.csv  text eol=lf
  *.py   text eol=lf
  *.ts   text eol=lf
  *.tsx  text eol=lf
  *.mdx  text eol=lf
  *.parquet binary
  *.xlsx    binary
  *.xls     binary
  *.pdf     binary
  *.zip     binary
  ```

---

## 8. Setup you will actually do (preview; not done yet)
1. Install `just` (`winget install --id Casey.Just --exact`). uv 0.12.5 and Node 24.14.0 are already installed on your PC (checked). Updating uv to 0.12.20 and Node to the latest 24.x is recommended.
2. `just setup`: uv installs Python 3.14 and the locked packages; `npm ci` installs the exact web packages; `just fetch-archive` restores raw files once the archive exists.
3. `just test`: everything offline should pass. `just test-web` runs the browser tests. `just web` opens the site locally.
4. Before Checkpoint B, I run steps 2–3 on your PC under PowerShell, and in CI on Linux, and report both results. I will not claim these work until then.

---

## 9. Open questions and access requests for you

1. **Public or private GitHub repo?** Public means free unlimited Actions minutes and transparency, but raw files must not be redistributed unless licences allow. Private means 2,000 free minutes per month, and possibly no required status checks on GitHub Free (unverified; see 5.3).
2. **Vercel plan.** Is the site purely non-commercial (Hobby is fine), or will it promote Udgam Labs (Pro needed, per Vercel's definition)?
3. **Raw-data archive location.** This is now a **prerequisite** for the reproducibility test, not a nice-to-have. Options:
   - a private GitHub repo's Release assets;
   - a private cloud bucket (e.g. Supabase Storage or Vercel Blob; either would be your account);
   - local disk plus manual backup. This option cannot serve CI.

   I recommend a private archive until each source's licence is confirmed.
4. **Access needed at scaffold time (Phase 1, not now):**
   - a GitHub repository, with Actions enabled;
   - a Vercel project linked to it, with preview deployments protected until Checkpoint C;
   - **new:** a **read credential for the raw archive**, stored as a GitHub Actions secret (e.g. `RAW_ARCHIVE_TOKEN`), so CI can run `just fetch-archive`.
5. **Access needed for Phase 6:**
   - **new:** a **fine-grained personal access token** (this repo only; Contents read/write + Pull requests read/write) or a **GitHub App** installed on the repo, stored as `REFRESH_PR_TOKEN`, so refresh PRs trigger CI normally;
   - alternatively, enable "Allow GitHub Actions to create and approve pull requests" in repo settings. But PRs opened with `GITHUB_TOKEN` would still wait for you to click "Approve workflows to run";
   - **new:** a free account with an **external dead-man's-switch / cron monitor** of your choice (I have not evaluated providers), whose ping URLs go in as secrets.

   No API keys are needed for the stack itself; data-source keys are listed by the source agents.
6. Owner preference: should agents also create GitHub Issues for `ISSUES.md` entries, or keep `ISSUES.md` as the single log? I suggest the file stays canonical and Issues are used only for automated alerts.

---

## 10. Evidence log (what was checked, where, and what it showed)

All checks were made on 2026-09-29. Items marked **[rev]** were added or re-checked during the review revision.

**Package versions**
- **PyPI JSON API** (`https://pypi.org/pypi/<pkg>/json`), latest version and upload date:
  - pandas 3.0.6 (2026-09-17, requires Python ≥3.11); polars 1.44.2 (2026-09-09); duckdb 1.5.6 (2026-09-28); numpy 2.5.3 (2026-09-06, ≥3.12); scipy 1.18.1 (2026-08-21, ≥3.12); pyarrow 25.0.1 (2026-08-10)
  - pandera 0.33.1 (2026-09-01); pytest 9.1.1 (2026-06-19); uv 0.12.20 (2026-09-28); cvxpy 1.9.3 (2026-09-19)
  - mesa 3.5.1 (2026-03-15; release list also shows `4.0.0a0`); dvc 3.67.1; snakemake 9.27.0; dagster 1.13.24
  - ipfn 1.4.4 (2021-12-30); rust-just 1.58.0; pdfplumber 0.11.10; fastexcel 0.21.0; httpx 0.28.1. (syrupy 6.1.1 was checked but is no longer proposed.)
  - Windows wheels for cp313 and cp314 are present for pandas, duckdb, numpy, scipy, pyarrow, cvxpy, clarabel, osqp and scs.
- **npm registry** (`https://registry.npmjs.org/<pkg>`):
  - **[rev]** `next`: dist-tag `latest` = 16.3.6 (published 2026-09-22T16:19Z); `backport` = 15.5.26; `canary` = 16.4.0-canary.52. 16.3.7 is not yet published (see the blog below).
  - **[rev]** `typescript`: `latest` = 7.0.2 (2026-07-08); `next` = 7.1.0-dev.20260928.1; stable 6.0.x versions exist: 6.0.2 (2026-03-23) and **6.0.3 (2026-04-16)**. `@typescript/typescript6` `latest` = 6.0.2 (2026-07-06).
  - **[rev]** `next-intl` `latest` = 4.14.7 (2026-09-24).
  - react 19.3.0; astro 7.3.5; @sveltejs/kit 2.70.3
  - d3 7.9.0 (2024-03-12); d3-sankey 0.12.3 (2019-09-02, BSD-3-Clause); echarts 6.1.0 (Apache-2.0); @observablehq/plot 0.6.17; @visx/sankey 4.0.0; deck.gl 9.4.0
  - pyodide 314.0.7 (MPL-2.0); vitest 5.0.2; @playwright/test 1.63.0; @axe-core/playwright 4.13.0; size-limit 14.1.0; @lhci/cli 0.15.1 (2025-06-25)

**Runtimes and tools**
- **endoflife.date API:**
  - Python 3.14 latest 3.14.7 (2026-08-05), EOL 2030-10-31; 3.13 EOL 2029-10-31.
  - **[rev]** `nextjs`: cycle 16 `lts: true`, latest 16.3.6 (2026-09-22); cycle 15 EOL 2026-10-21, latest 15.5.26.
  - **[rev]** `nodejs`: cycle 26 LTS from 2026-10-28 (latest 26.10.0); cycle 24 LTS, active support to 2026-10-20, EOL 2028-04-30, **latest 24.21.0** (2026-09-08).
- **GitHub API:** cpython tags show `v3.15.0rc2` as newest. **[rev]** casey/just latest release 1.58.0 (2026-08-03T20:31Z). d3/d3-sankey `pushed_at` 2023-11-13, 37 open issues.
- **Local machine:** Python 3.12.7, uv 0.12.5, Node v24.14.0, npm 10.8.1, git 2.47.0; `make: command not found`; `just: command not found`.
  - **[rev]** `git config --show-origin --get-all core.autocrlf` → `file:C:/Program Files/Git/etc/gitconfig	true`.
  - **[rev]** PowerShell `(Get-Command sh)` → nothing; `(Get-Command bash).Source` → `C:\Windows\system32\bash.exe`. Git's own `sh.exe` exists at `C:\Program Files\Git\bin\sh.exe` but is not on PATH.

**Probes** (scratch folder outside the repo)
- **Parquet determinism probe** (original, Python 3.13.15): 200k rows written twice per library; pyarrow True, pandas True, polars True, DuckDB (ordered) True, DuckDB (unordered) True. `created_by` values: `parquet-cpp-arrow version 25.0.1`, `Polars`, `DuckDB version v1.5.6 (build 069cc9f9b5)`. pandas files embed a `pandas` metadata key.
- **[rev] Parquet re-run on Python 3.14.7** (polars 1.44.2, pyarrow 25.0.1, zstd, row groups 50k): `{'polars': True, 'pyarrow': True}`.
- **[rev] BLAS thread probe** (Python 3.14.7, numpy 2.5.3, `inv(I − A)` with a 400×400 A, seed 42). SHA-256 prefix of raw bytes, then of the values rounded to 10 decimals:
  - `OPENBLAS_NUM_THREADS=1` → `f6c5b164d7bb4256` / `22e500b4022349d8`
  - `=4` → `c293456ca7484966` / `22e500b4022349d8`
  - default (28) → `7f2d233dfd992041` / `22e500b4022349d8`

  Raw bytes differ by thread count; the rounded values are identical. This confirms the reviewer's finding with different hashes, because the reviewer's matrix was different.
- **[rev] Aggregation thread probe** (200k rows, 500 groups): DuckDB `sum` hash identical at `threads` = 1, 2, 8 and 28 (`e3e5a2cf5192`). polars `group_by().sum()` was identical with default threads and `POLARS_MAX_THREADS=1` (`dc227a1e853a`). **polars and DuckDB disagree with each other** in 461 of 500 group sums, max abs diff 4.2e-7, max rel diff 1.9e-15. `pl.SQLContext` exists in polars 1.44.2 and ran a GROUP BY query.
- **[rev] Hash-seed probe** (Python 3.14.7): the first 4 elements of the same 8-label set were `['HH_urban_q5','FIRMS_pvt','ROW','RBI']`, `['GOV_states','RBI','GOV_centre','FIRMS_pvt']` and `['ROW','GOV_centre','HH_urban_q5','RBI']` under `PYTHONHASHSEED` = 1, 2 and 3.
- **[rev] JSON probe:**
  - `json.dumps({'a': float('nan'), 'b': round(-1e-12, 6)})` → `{"a": NaN, "b": -0.0}`
  - `round(-1e-12, 6) + 0.0` → `0.0`
  - `allow_nan=False` raises "Out of range float values are not JSON compliant: nan"
  - Node 24: `JSON.parse('{"a":NaN}')` → `Unexpected token 'N', "{"a":NaN}" is not valid JSON`
- **[rev] gzip probe:**
  - Python 3.14.7 `gzip.compress` header mtime field = 0, and two calls 1.1 s apart were identical.
  - Python 3.12.7 `gzip.compress` mtime field = current time.
  - `GzipFile` on both versions writes the current time, plus the filename when given.
  - Python 3.14 docs (`https://docs.python.org/3.14/library/gzip.html`): "Changed in version 3.14: The mtime parameter now defaults to 0 for reproducible output"; for `GzipFile`, "If mtime is omitted or None, the current time is used."
- **Pyodide size probe:** `https://cdn.jsdelivr.net/pyodide/v314.0.7/full/` returned HTTP 200. Compressed transfer sizes: `pyodide.asm.wasm` 3,438,516 B (9,598,218 B uncompressed), `python_stdlib.zip` 2,505,313 B, `numpy-2.4.6-cp314-…wasm32.whl` 2,929,885 B.
- **Library size probe (jsDelivr, minified):** d3-sankey 5,652 B; d3 279,706 B; Observable Plot 209,183 B; ECharts 1,121,883 B. A grep of Plot's bundle for "sankey" and "chord" found no matches.

**Framework and library docs**
- **Next.js static export guide** (`https://nextjs.org/docs/app/guides/static-exports`, version 16.3.6, lastUpdated 2026-08-25): "After running `next build`, Next.js will create an `out` folder…". The unsupported list includes Cookies, Rewrites, Redirects, Headers, Proxy, ISR, default-loader Image Optimization and Server Actions.
- **[rev] Next.js blog** (`https://nextjs.org/blog`):
  - 22 Sept 2026 "Next.js Security Update for a Critical Upstream Issue": "Upgrade to 16.3.6 (Active LTS) or 15.5.26 (Maintenance LTS) now."
  - 23 Sept 2026 "Upcoming Next.js September Security Release" (`/blog/upcoming-nextjs-security-release-september-2026`): "Next.js is preparing a scheduled security release for **September 30, 2026**… will address nine vulnerabilities… one critical, two high, five medium, and one low. We plan to publish **16.3.7** and **15.5.27**".
  - The first draft wrongly called the 23 Sept post a release.
- **[rev] Next.js TypeScript docs** (`https://nextjs.org/docs/app/api-reference/config/typescript`, version 16.3.6, lastUpdated 2026-08-25): "TypeScript 7 does not currently provide the JavaScript compiler API… Next.js uses the project-local `tsc` CLI by default"; "`experimental.useTypeScriptCli` is experimental and its behavior may change."
- **[rev] TypeScript 7.0 announcement** (`https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/`, 8 Jul 2026): "TypeScript 7.0 does not ship with an API. We expect TypeScript 7.1 to ship with a new (and different) API." Workflows using "Vue, MDX, Astro, Svelte, and others" (and Angular templates) must rely on TypeScript 6.0. Side-by-side setup: `"@typescript/native": "npm:typescript@^7.0.2"`, `"typescript": "npm:@typescript/typescript6@^6.0.2"`.
- **[rev] next-intl static export** (`https://next-intl.dev/docs/routing/middleware`, static export section): "Using a locale prefix is required", "The locale can't be negotiated on the server", "Static rendering is required". It recommends a root page calling `redirect('/en')`.
- **uv docs** (`https://docs.astral.sh/uv/concepts/projects/layout/`): "uv.lock is a universal or cross-platform lockfile … This file should be checked into version control". (`…/projects/sync/`): `--locked`: "uv will raise an error instead of updating the lockfile". (`…/guides/integration/github/`): `astral-sh/setup-uv` v9.0.0 pinned by SHA.
- **pandera docs** (`https://pandera.readthedocs.io/en/stable/`): "validate … pandas, polars, dask, modin, ibis, and pyspark"; banner "New in Pandera 0.33.0".
- **DuckDB order preservation** (`https://duckdb.org/docs/current/sql/dialect/order_preservation.html`): no order guarantee for joins, `GROUP BY`, `ORDER BY` ("may employ unstable sorting algorithms"), etc.
- **[rev] DuckDB aggregates** (`https://duckdb.org/docs/current/sql/functions/aggregates.html`): for `sum`/`fsum` (and `avg`/`favg`), "The floating-point versions of this function are affected by ordering."
- **[rev] polars `DataFrame.group_by`** (`https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.group_by.html`): `maintain_order`: "Ensure that the order of the groups is consistent with the input data. This is slower than a default group by."
- **[rev] numpy.sum** (`https://numpy.org/doc/stable/reference/generated/numpy.sum.html`, v2.5): "often numpy will use a numerically better approach (partial pairwise summation)… the improved precision is only used when the summation is along the fast axis in memory. Note that the exact precision may vary depending on other parameters."
- **[rev] MDN Math** (`https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Math`): "Many `Math` functions have a precision that's implementation-dependent. This means that different browsers can give a different result. Even the same JavaScript engine on a different OS or architecture can give different results!"
- **cvxpy solvers** (`https://www.cvxpy.org/tutorial/solvers/index.html`): "CVXPY is distributed with the open source solvers CLARABEL, OSQP, and SCS"; CLARABEL, SCS and ECOS support EXP cones.
- **Mesa docs** (`https://mesa.readthedocs.io/latest/`): "An Apache2 licensed agent-based modeling (or ABM) framework in Python"; Mesa 4 available as a pre-release.
- **Pyodide docs** (`https://pyodide.org/en/stable/usage/downloading-and-deploying.html`): version 314.0.7; "The full distribution is quite large (200+ megabytes)".
- **just manual:**
  - `https://just.systems/man/en/packages.html`: `winget install --id Casey.Just --exact`; `uv tool install rust-just`.
  - **[rev]** `https://just.systems/man/en/prerequisites.html`: "On Windows, `just` works with the `sh` provided by Git for Windows, GitHub Desktop, or Cygwin. After installation, `sh` must be available in the `PATH`…"; PowerShell example `set shell := ["powershell.exe", "-c"]`.
  - **[rev]** `https://just.systems/man/en/settings.html`: `windows-shell` and `windows-powershell` are marked "(Deprecated. Use the `[windows]` attribute on `set shell`.)".
  - **[rev]** Full manual (`/man/en/print.html`) example: `[windows]` / `set shell := ['cmd', '/c']` (conditional attributes on settings, since 1.56.0).
- **[rev] Turbopack worker issues** (GitHub API):
  - vercel/next.js #98841 "[Turbopack] `new Worker(url, { type: 'module' })` is emitted with `type: undefined`…" (created 2026-09-17T19:53:58Z) and #99389 "Turbopack: web worker bootstrap throws when a query is appended to the worker URL" (created 2026-09-28T22:46:56Z).
  - **Both were closed within ~1 minute of creation, with label `invalid link`.** That looks like an automated close for a missing or invalid reproduction link, not a fix. So they are **not** confirmed bugs, and the fix version the reviewer called unverified does not exist.
  - Next.js release notes do show repeated worker fixes in 16.3.x: #96307 "Fix Turbopack worker URL context lookup" (16.3.0-canary.100), #96432 "Fix component chunks for workers" (16.3.0-canary.105), and #97419 "Fix Turbopack worker chunk loading with asset prefix" (16.3.2). That supports testing the worker from the production build.

**Flow-visualisation evidence**
- **d3-sankey README** (`https://github.com/d3/d3-sankey`): "Visualize flow between nodes in a directed acyclic network."
- **ECharts** issue `https://github.com/apache/echarts/issues/19505` "[Feature] Support for Cycles in Sankey Diagrams": **Closed as not planned**. Error text "Sankey is a DAG, the original data has cycle!" appears in issues #12788 and #13267 (search results).
- The ECharts option page (`https://echarts.apache.org/en/option.html#series-sankey`) returned only navigation to the fetch tool, so ECharts' zoom/aria options are **unverified**. This does not change the recommendation.
- **d3-chord** (`https://d3js.org/d3-chord`): input is an n×n matrix of non-negative flows; version 7.9.0.
- Observable Plot marks page (`https://observablehq.com/plot/features/marks`) returned **HTTP 429**. The replacement evidence is the bundle grep above.

**Standards and i18n**
- **WCAG 2.2** (`https://www.w3.org/TR/WCAG22/`): "W3C Recommendation 12 December 2024". New AA criteria: 2.4.11, 2.5.7, 2.5.8, 3.3.8; new A criteria: 3.2.6, 3.3.7.
- **next-intl** (`https://next-intl.dev/docs/routing/setup`): static rendering via `generateStaticParams`/`next/root-params`. Static export is covered on the middleware page (above).

**Hosting, CI and storage**
- **[rev] Vercel Node versions** (`https://vercel.com/docs/functions/runtimes/node-js/node-js-versions`, last_updated 2026-02-27): "Current available versions are: 24.x (default) 22.x 20.x. Only major versions are available. Vercel automatically rolls out minor and patch updates when needed". `engines.node` `24.x` → "latest 24.x version". The related links include "Node.js 20 is being deprecated on October 1, 2026".
- **[rev] Vercel `vercel.json`** (`https://vercel.com/docs/project-configuration/vercel-json`, last_updated 2026-08-14): `redirects[].permanent`: "When `true`, the status code is 308. When `false` the status code is 307"; `headers` supported. Whether these apply to a Next `output: 'export'` deployment is **not stated** there, so it is unverified and is tested in Phase 3.
- **Vercel Hobby** (`https://vercel.com/docs/plans/hobby`, last_updated 2026-09-14): 100 GB Fast Data Transfer; 100 deployments/day; "the Hobby plan restricts users to non-commercial, personal use only"; developer seats "$20 per user / month".
- **Vercel fair use** (`https://vercel.com/docs/limits/fair-use-guidelines`, 2026-09-14): commercial = "financial gain of anyone involved in any part of the production"; examples include "Advertising the sale of a product or service"; "Asking for Donations does not fall under commercial usage".
- **Supabase:**
  - `https://supabase.com/docs/guides/platform/billing-on-supabase`: "You are granted two free projects."
  - `https://supabase.com/docs/guides/platform/free-project-pausing`: "A Free plan project is considered inactive if it does not receive sufficient user database activity over the past week"; restorable "for up to 1 year after it was paused".
  - An older changelog entry says 90 days; the current docs page is taken as authoritative.
- **GitHub Actions schedule** (`https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows`): 5-minute minimum; delays and "some queued jobs may be dropped"; "automatically disabled when no repository activity has occurred in 60 days" (public repos).
- **[rev] GITHUB_TOKEN** (`https://docs.github.com/en/actions/concepts/security/github_token`): "events triggered by the `GITHUB_TOKEN` will not create a new workflow run, with the following exceptions… when a workflow using `GITHUB_TOKEN` creates or updates a pull request, the resulting `pull_request` event creates workflow runs in an approval-required state."
- **[rev] Repo Actions settings** (`https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository`): "By default, when you create a new repository in your personal account, workflows are not allowed to create or approve pull requests." The toggle is "Allow GitHub Actions to create and approve pull requests".
- **[rev] Protected branches** (`https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches`): the fetched page gave **no** general plan-availability statement, so availability for private repos on GitHub Free is unverified.
- **GitHub Actions billing** (`https://docs.github.com/en/billing/concepts/product-billing/github-actions`): "free … for public repositories that use standard GitHub-hosted runners"; GitHub Free private: 2,000 minutes.
- **GitHub notifications** (`https://docs.github.com/en/actions/concepts/workflows-and-actions/notifications-for-workflow-runs`): "Notifications for scheduled workflows are sent to the user who initially created the workflow."
- **GitHub large files** (`https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github`): warning at 50 MiB, "GitHub blocks files larger than 100 MiB", repos "ideally less than 1 GB".
- **Git LFS billing** (`https://docs.github.com/en/billing/concepts/product-billing/git-lfs`): Free accounts get 10 GiB storage and 10 GiB bandwidth.
- **GitHub releases** (`https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases`): "Each file included in a release must be under 2 GiB"; "no limit on the total size of a release, nor bandwidth usage".

**Context only (not verified by me)**
- **MOSPI base year:** web search returned a PIB release (`https://www.pib.gov.in/PressReleasePage.aspx?PRID=2233518`) and a MOSPI press note PDF titled "Press Note on New Series of GDP Estimates with Base Year 2022-23" dated 27-02-2026. I did **not** open these; confirmation belongs to the MOSPI recon agent. They are cited only because they shape the schema (`base_year` and `vintage` columns).

**Not evaluated / still unverified**
- Third-party uptime or dead-man's-switch monitors (a provider choice is needed; section 9).
- Whether `vercel.json` redirects and headers apply to a Next static-export deployment (Phase 3 test).
- Whether branch protection and required checks are available on private repos under GitHub Free.
- Whether workflow-made commits count as "repository activity" for the 60-day schedule rule.
- Linux behaviour of all determinism probes (the first CI run is the test).
- That `just setup` / `just test` work end-to-end on your PC (to be run at scaffold time).

---

## 11. Review log

An independent review (2026-09-29) raised 17 points. Each is listed with its disposition and a one-line reason. Facts the review relied on were re-checked live before any change (section 10, items marked [rev]).

| # | Severity | Point (short) | Disposition | Reason (one line) | Where changed |
|---|---|---|---|---|---|
| 1 | major | CI repro test can't run: `data/raw` is git-ignored and the archive is undecided; tests may skip silently | **Accepted** | Without restorable raw files the repro promise is empty, and a silent skip breaks SPEC rule 4. `just fetch-archive` was added, tests fail loudly, and an archive secret became an access request. | §0 #11, §1.9, §5.3, §6, §9 Q3–4 |
| 2 | major | Manifest and provenance embed the git commit → self-reference and churn | **Accepted** | A commit hash can't name its own commit. Replaced with a deterministic `code_hash`; volatile metadata moved to unhashed `data/runs/`. | §0 #8–9, §1.6, §1.7 |
| 3 | major | Floats not byte-stable across thread counts/machines; probe was on 3.13 | **Accepted** | Re-verified on 3.14.7: three different hashes at 1/4/28 BLAS threads, identical after rounding. Threads are pinned, output is canonically rounded, and Linux CI is authoritative with a labelled tolerance mode on Windows. | §0 #7, §1.1, §1.5, §2.1, §3.2 |
| 4 | major | Ordering randomness: set order, polars `group_by`, dict-derived account order | **Accepted** | Re-verified set order changing under PYTHONHASHSEED 1/2/3 and the polars `maintain_order` docs. Added ordered `accounts.yaml`, order-control lint, `PYTHONHASHSEED=0` and a two-seed test. | §1.5 rules 3–5, 8; §6 hygiene |
| 5 | major | `just` fails on the owner's PC (no `sh` on PATH; `bash` is WSL) | **Accepted, with a correction** | Re-verified locally. The suggested `set windows-shell` is **deprecated** in the current manual, so the justfile uses `[windows] set shell := [...]` instead, and every recipe is a one-line Python/npm call. | §0 #10, §1.8, §8 |
| 6 | major | `core.autocrlf=true` will break manifest hashes; `.gitattributes` unspecified | **Accepted** | Re-verified (`C:/Program Files/Git/etc/gitconfig true`). Full `.gitattributes` content from the first commit, LF writers and a CRLF test. | §0 #25, §1.5 rule 1, §6, §7 |
| 7 | major | Skip-if-unchanged runner can leave stale outputs; "code" undefined | **Accepted** | A full rebuild is now the default and always used in CI. Opt-in `--cache` has a defined key (whole-tree code hash + `uv.lock` + params + env), and every skip is logged. | §0 #10, §1.8 |
| 8 | major | "Number-for-number" Python↔browser parity is impossible and self-contradictory | **Accepted, with a correction** | MDN and numpy docs re-verified; wording is now "within documented tolerance on aggregate outputs". I did **not** adopt the suggestion to use `math.fsum` in the reference: fsum sums more accurately than a TS loop, which would widen the gap. Both sides use the same sequential loop. Parity also runs in Chromium, WebKit and Firefox. | §0 #15, §3.2, §3.3, §6 |
| 9 | major | Refresh PRs blocked by GitHub defaults; in-repo heartbeat dies with the schedule | **Accepted** | Both GitHub doc quotes re-verified. A dedicated PAT/App token for PRs, CI as a required check, and an external dead-man's switch; the in-repo heartbeat was dropped. The "commit a heartbeat file" workaround was **not** adopted because whether bot commits count as activity is unverified. | §0 #21–22, §5.3, §5.4, §9 Q5 |
| 10 | minor | JSON/gzip details: NaN, `-0.0`, gzip mtime, separators/encoding | **Accepted, with a correction** | NaN and `-0.0` re-verified and fixed with one JSON writer (`allow_nan=False`, `+0.0`, fixed separators, UTF-8, trailing `\n`). On Python 3.14, `gzip.compress` **already** defaults to `mtime=0` (docs and probe), so the review's gzip result holds only for 3.12 or `GzipFile`. We avoid pre-gzipping and let Vercel compress. | §1.5 rules 1–2, §4.3 |
| 11 | minor | Separately rounded A_n and M disagree; tests run on unrounded matrices | **Accepted** | Only the rounded A_n is exported, both sides compute M from it, and tests run on the exported file. This also halves the payload. | §0 #13, §3.1, §6 |
| 12 | minor | Next.js security claim wrong; 16.3.6 superseded on 30 Sept | **Accepted** | Re-verified on the blog: 23 Sept was an *announcement* of 16.3.7/15.5.27 for 30 Sept. Text corrected, `next@^16.3.7` pinned, Active/Maintenance LTS noted, Dependabot added. | §0 #16, §4.1, §5.3, §10 |
| 13 | minor | TypeScript 7 has no API; conflicts with MDX; unverified question is answerable | **Accepted** | Re-verified the TS 7.0 announcement and Next's TS docs. Pinned the plain `typescript@~6.0.3` (exists on npm, 2026-04-16), which is simpler than the alias setup, until TS 7.1 ships its API. | §0 #16, §4.1, §10 |
| 14 | minor | Node/npm not pinned; Node 26 plan doesn't fit Vercel | **Accepted, with a correction** | Re-verified that Vercel offers 24.x/22.x/20.x only and that the latest 24.x is 24.21.0. `package-lock.json`, `npm ci`, `.nvmrc` and `engines` were added, and we stay on 24. Correction: per Vercel's docs, `engines.node` selects only the **major** version; Vercel still rolls minor and patch versions itself. | §0 #24, §5.1, §7, §8 |
| 15 | minor | Site needs a redirect and headers that static export lacks | **Accepted** | next-intl static-export docs re-verified (a client-side root redirect is its recipe). `vercel.json` added with a 308 `/`→`/en/`, immutable data caching and security headers. That Vercel applies it to a static export is left **unverified** and is the first Phase 3 test. | §0 #18, #20; §4.1; §4.3; §5.1; §7 |
| 16 | minor | Browser performance: worker in Turbopack prod build, 10k SVG rects, animation jank, Sankey reordering | **Accepted, with an evidence correction** | The two cited Turbopack issues were bot-closed as `invalid link` within a minute, so they are not confirmed bugs. But 16.3.x release notes show repeated worker fixes, so the `out/` worker test is still justified. Canvas matrix, animation outside React, fixed node order and a frame-time report (a gate once stable) were added. | §4.2, §4.3, §6, §10 |
| 17 | minor | Stack too heavy: three engines, syrupy + manifest, Lighthouse in `just test` | **Partly accepted** | Dropped syrupy. Lighthouse, size-limit and Playwright moved out of `just test`. polars is now the only pipeline engine (it has a SQL context). **Kept DuckDB**, but only for verifier recomputation and ad-hoc queries: SPEC §7 names it, and an independent engine suits SPEC rule 3. Test markers are kept because they map one-to-one to layers. | §0 #3, #6, #23; §1.3; §4.3; §6 |

Summary: 17 points reviewed. 16 accepted (5 with a factual correction to the review), 1 partly accepted, 0 rejected outright. Every version fact the review cited was re-checked; all matched except these corrections: `windows-shell` is deprecated; `gzip.compress` defaults to `mtime=0` on 3.14; `engines.node` selects only the major version on Vercel; and the two Turbopack issues were closed as invalid, not fixed.
