# The Map: website (Phase 3)

A static Next.js 16 site that shows India's 2023-24 Social Accounting Matrix as money flowing between
producers, households, companies, banks, governments and the rest of the world. Every number on screen
comes from JSON written by `uv run python -m pipeline export` (see `docs/phase3/PLAN.md` §3); nothing is
typed into pages or prose.

## Requirements

- **Node 24** (`.nvmrc`; `engine-strict=true` makes npm refuse other versions). On the project Mac:
  `export PATH=/opt/homebrew/opt/node@24/bin:$PATH`.
- Python side: `uv sync --locked` at the repo root.

## Commands (run in `web/`)

| Command | What it does |
|---|---|
| `npm ci` | install the locked dependencies (use `node scripts/with-lock.mjs --lock install -- npm ci` while other agents work) |
| `npm run dev` | dev server; set `NEXT_DIST_DIR=.next-<you>` and `PORT` when several run at once |
| `npm run build` | static export to `out/` (takes the `build` lock; fails on fixture data unless `ALLOW_FIXTURE=1`) |
| `npm run start:out` | serve `out/` with the `vercel.json` headers and redirects on a free port |
| `npm run test:unit` | vitest (`tests/unit/**`) |
| `npm run test:web` | node check → contract check → vitest → build → first-load budget → Playwright + axe |
| `npm run typecheck`, `npm run lint` | `tsc --noEmit`, ESLint |
| `npm run gen:contract` | regenerate `src/data/contract.gen.ts` from `pipeline/export/schema/` |

From the repo root: `just export`, `just test`, `just web`, `just test-web` (PLAN §5).

## Data

- `public/data/index.json` and `public/data/<data_version>/…`: the real export (immutable, content-addressed).
- `fixtures/data/…`: a generated, balanced fixture with the same shape (`pipeline export --fixture`).
- `DATA_ROOT=public|fixtures|<absolute path>` picks the root (default: `public` once the real export exists).
  Fixture data is copied to `public/data-fixture/` (gitignored) for client fetches.
- Build time: `src/data/server.ts` reads files with `fs` and validates them. Client: `src/data/hooks.ts`.

## Layout

See PLAN §4.1 for the tree and §6.2 for who owns which file. Shared code (`src/data`, `src/lib/{format,status,url-state,ids}.ts`,
`src/components/ui`, `src/i18n`, `src/styles`, configs and scripts) belongs to the platform unit.

## Deploy

`vercel.json` (Root Directory `web`, `framework: null`) deploys `out/` as static files with the redirects and
security headers of PLAN §4.14. Deployment needs the owner's go-ahead (PLAN §9 Q2).
