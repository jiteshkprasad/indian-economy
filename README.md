# India's economy as a working model

One connected map of India's whole economy: every rupee, who pays it and who receives it.
Live at **https://indianeconomy.jitesh.app**.

- **128 accounts**, from households to the Reserve Bank, and **3,893 money flows** for 2023-24, each with its source.
- Built from **32 official sources** (national accounts, budgets, the Reserve Bank, tax and trade data), with
  **76 years** of history (1950-51 to 2025-26) for the main flows.
- Every account adds up to the rupee. Every number says how it was made: official, derived, estimated or set by
  balancing. A page lists what the map can't tell you yet.

## What is in this repo

| Folder | What it does |
|---|---|
| `pipeline/` | Python data pipeline: fetches official files, pins them by SHA-256, cleans them, builds and balances the social accounting matrix (SAM) |
| `data/registry.yaml`, `SOURCES.md` | Every source: URL, licence or terms, release, and how it is used |
| `data/raw/**/*.meta.json`, `data/raw_pins/` | Fingerprints of every downloaded file (the files themselves are not included) |
| `data/sam/` | The balanced 128-account SAM for 2023-24 and its certificates |
| `web/` | The website (Next.js static export on Cloudflare Workers): the map, stories, guess game, matrix explorer |
| `docs/` | The evidence trail: design, reconciliation, balancing and verification notes for each phase |
| `SPEC.md`, `DECISIONS.md`, `ISSUES.md`, `BALANCING.md` | The contract, every decision, every open issue, and every balancing move explained |

The project was built by one person working with AI coding agents. `CLAUDE.md` and `web/AGENTS.md` are the
instructions those agents followed; they are kept because they show how the work was organised.

## Running it

Python 3.14 with [uv](https://docs.astral.sh/uv/); `just` is optional.

```bash
uv sync --locked                       # install
uv run python -m pipeline fetch        # download and pin the official files (network)
uv run python -m pipeline build --with-deps
uv run python -m pipeline sam          # build and balance the SAM
uv run python -m pipeline test         # offline tests
```

The website (Node 24):

```bash
cd web && npm ci && npm run build      # static export in web/out
```

**Cleaned source tables are not included.** The private working copy keeps cleaned extracts of each source in
`data/clean/`. Several publishers do not allow their tables to be republished, so this public copy leaves them out;
`fetch` and `build` recreate them on your machine from the official files. Some tests need them, so run the build first.
Please follow each source's own terms (listed in `data/registry.yaml`) when you use them.

## Licence

- Code: MIT (see `LICENSE`).
- The model's own figures, the balanced SAM, docs and text: CC BY 4.0 (see `LICENSE-DATA.md`). Credit
  "Jitesh K Prasad, indianeconomy.jitesh.app".
- Official statistics belong to their publishers. Their terms apply to the source data, and each figure on the site
  credits its source.

Made by [Jitesh K Prasad](https://jiteshkprasad.com).
