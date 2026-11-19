# CLAUDE.md: how agents work in this repo

Read `SPEC.md` first. It is the contract. Then read `DECISIONS.md` (what has been decided), `ISSUES.md` (what is broken or open) and `SOURCES.md` / `data/registry.yaml` (where the data comes from).

## Status
- Phase 0 is complete and accepted (owner delegated autonomy on 2026-09-29).
- Phase 1 (data pipeline) is complete: 11 ingest units, 1.2M values with provenance, 98.6% independently spot-checked, all tests pass, byte-identical rebuilds. See docs/phase1/COVERAGE.md and RECONCILIATION.md.
- Phase 2 (balanced SAM) was approved at Checkpoint B on 2026-10-02 (DECISIONS D3-0): 128-account SAM for 2023-24 in `data/sam/2023-24/`, balanced and certified, all SPEC acceptance tests pass, every over-threshold move explained (`BALANCING.md`). Read `docs/phase2/CHECKPOINT_B.md`, `docs/phase2/SAM_GUIDE.md` (block contract) and DECISIONS D2-1..D2-24. Phase 3 (the Map website) is in progress on branch `phase3-map`; stop at Checkpoint C (preview link, no public deploy).
- `just sam` (= `uv run python -m pipeline sam`) builds all nine SAM blocks and balances; `sam BLOCK ... --no-balance` builds some; `just timeseries` builds the top-flows series.

## Rules that bite (from SPEC §3)
- **No fabricated data.** Every number needs a source id from `data/registry.yaml`, a URL, table/series id, retrieval date, unit and price basis. Estimates are labelled `estimated`, with a method.
- **Verify, don't remember.** Base years and vintages change (the GDP base moved to 2022-23 in Feb 2026, and the series has had several vintages since). Re-check before relying on a fact.
- **A different agent verifies.** Whoever builds a number does not check it.
- **No silent fallbacks.** Failures go into `ISSUES.md`.
- **Respect terms.** Several sources forbid scraping or require permission (see SOURCES.md §4–5). Don't bypass bot protection; ask the owner for a manual download instead.

## Layout
- `data/raw/`: downloaded files, never edited by hand, not committed (pinned by sha256 in a manifest from Phase 1).
- `data/clean/`, `data/sam/`: pipeline outputs. `data/registry.yaml`: the source registry. `data/gap_map.csv`: SAM cell → source/method.
- `docs/phase0/`: reference year, account structure, gap map, design review, stack proposal, and the per-family recon/verify notes (the evidence trail).
- `models/`, `web/`, `tests/`: empty until later phases.

## Commands
Python 3.14 via uv; `just` is optional (`uv tool install rust-just`). Each `just <recipe>` is exactly `uv run python -m pipeline <recipe>`, and the CLI pins threads, `PYTHONHASHSEED=0` and UTF-8 itself.
- `just setup` (= `uv sync --locked`): install the locked environment.
- `just fetch [UNIT ...] [--offline|--refresh]`: download and pin raw files (network; the DECISIONS D1-1/D1-2 access policy is enforced in `pipeline/core/policy.py`).
- `just build [UNIT ...] [--with-deps]`: offline build from pinned raw files into `data/clean/<unit>/`, then regenerate `data/manifest.json`. Units in DEPENDS are read as built unless `--with-deps`.
- `just test [pytest args]`: all offline tests. `just test-live`: network canaries.
- `just repro [UNIT ...]`: build three times (two hash seeds; 1 and 4 threads) and require byte-identical output that matches `data/manifest.json`.
- `just manifest [--check]`, `just coverage [UNIT ...]` (gap-map coverage), `just list`, `just verify-raw`.
- Writing an ingest unit: `docs/phase1/PIPELINE_GUIDE.md` is the contract; `pipeline/ingest/mospi_nas_2026.py` is the template.
- Pipeline data: `data/raw_pins/<unit>.yaml` pins raw bytes by sha256 (committed); `data/raw/**/*.meta.json` sidecars are committed and raw files are not; `data/registry_additions/<unit>.yaml` holds sources an agent added (unverified until merged).

## Owner
Jitesh (Udgam Labs): finance-trained (CFA L2, FRM, MBA), not a programmer. Explain decisions in plain English, don't dumb down the economics, and ask only at checkpoints or for genuinely irreversible or ambiguous choices.
