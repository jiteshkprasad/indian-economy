# V4: build, tests, performance (Phase 3 verification)

Verifier V4 (PLAN §7). I did not build any of this. Everything below ran in a **fresh git worktree of HEAD `f8481bc`** (`/private/tmp/claude-501/v4-wt`, removed afterwards) with Node 24.21.0 / npm 11.19.0, unless it says otherwise. No builder-owned file was edited. Nothing was committed, pushed or deployed.

Repro scripts are in `docs/phase3/verify/V4_scripts/`. `vserve.mjs` is a Vercel-like static server: it applies the vercel.json redirects and headers (the last matching rule wins for each key) and compresses with brotli. `h418b.mjs` reproduces the hydration error. `cls.mjs` measures layout shift. `summarize.py` summarises Lighthouse results. To run the `.mjs` files, copy them into `web/` so that `@playwright/test` resolves.

## Verdict in one paragraph

The site builds and its tests pass in a clean checkout. It does not depend on anything that is uncommitted in the main checkout, and it builds even from `web/` on its own, which is what a Vercel project with Root Directory = `web` would do. The export is deterministic. The first-load JS is under budget, and Lighthouse mobile on `/en/` passes every PLAN §4.13 target when the site is served compressed, as Vercel serves it. I found the following problems, in order of severity:

- A Phase 2 smoke test fails on committed data, so `just test` is not green (this is outside Phase 3 code).
- An intermittent React hydration failure (#418) throws away and re-renders the whole document. It happens on most routes, with compressed delivery and a warm connection.
- Story pages shift layout on phones (CLS 0.17–0.20, so Lighthouse Performance is 0.89–0.91).
- About 300 KB (gzipped) of RSC prefetch on every visit to `/en/`.
- Hashed `/_next/static` chunks have no long-lived cache header.
- The local `serve-out.mjs` does not compress, so any Lighthouse run against `npm run start:out` reports a misleading Performance of 0.72 and LCP of 6.6 s.
- The seven d3 modules declared as dependencies are not used at all.

## Findings

| id | sev | title | owner |
|---|---|---|---|
| V4-01 | high | `just test` not green: `tests/sam/test_sam_production.py::test_production_prior_closed_with_pseudo_entries_balances` fails (KKT certificate), not a raw-file failure | orchestrator (Phase 2 code) |
| V4-02 | medium | Intermittent hydration failure (React #418): the whole `<html>` is discarded and client-rendered, on most routes, under compressed delivery with a warm connection | U2 |
| V4-03 | medium | Story pages: CLS 0.17–0.20 on phones (the SSR "all steps" layout collapses to the player after hydration). Lighthouse Performance 0.89–0.91 | U5 |
| V4-04 | medium | `/en/` prefetches about 300 KB (gzipped; about 1.7 MB raw) of RSC payloads for the header and story-card links on first visit, more than the whole 200 KB first-load JS budget | U2 (Header), U5 (StoryCards) |
| V4-05 | medium | vercel.json gives `/_next/static/**` (content-hashed) no `Cache-Control`. With `framework: null`, Vercel then serves `max-age=0, must-revalidate`, so every repeat view revalidates 11+ chunks | U2 |
| V4-06 | low | `scripts/serve-out.mjs` claims to serve "like Vercel would" but does not compress. Lighthouse against `npm run start:out` gives Perf 0.72 and LCP 6.6–18 s, not the real 0.99 and 1.8 s | U2 |
| V4-07 | low | Seven runtime d3 modules and seven `@types/d3-*` are declared but never imported. The Sankey and charts are hand-written, so this is a stray-dependency drift from PLAN §6.4 | U2 |
| V4-08 | low | Flow and series permalink pages skip a heading level (`h1` then `h3`), because they reuse FlowDetailPanel's `h3`s. Lighthouse a11y is 0.98 (`heading-order`, best practice, not a WCAG-tagged axe rule) | U3 |
| V4-09 | low | Flow, series and story pages carry 190–330 KB raw RSC payloads, inline plus a duplicate `.txt` (a flow page is 239 KB of HTML, of which 216 KB is the inline payload). `out/` is 118 MB and 1,001 files | U3, U5 |
| V4-10 | low | PLAN §4.15 says dev runs with a custom `NEXT_DIST_DIR` do not rewrite `next-env.d.ts`; they do (it gains `import "./.next-<dir>/dev/types/…"`). Only `npm run normalise` or a build restores it | U2 / orchestrator (PLAN text) |
| V4-11 | low | The baseline understates the out-of-scope failures: 12 `tests/units/*` tests also fail only because raw files are missing (`OfflineMissing`). This is not a defect, but Checkpoint C should list them | orchestrator |
| V4-12 | low | `next build` is not byte-reproducible: only the random `buildId` differs between two builds (952 files differ, all chunks identical). This is harmless; a `generateBuildId` would make `out/` reproducible | U2 |

### V4-01 (high): `just test` has a non-raw failure

- **Evidence.** `uv run python -m pipeline test` (no arguments) in the worktree gives: 3275 passed, 970 failed, 48 errors, 25 xfailed, 12 skipped. Vitest gives 500/500. Of the failures:
  - 663 are in `tests/raw` and about 390 in `tests/verify`; both are raw-file related, as expected.
  - 12 are in `tests/units/*`, also raw-file related (see V4-11).
  - One is not raw-related: `tests/sam/test_sam_production.py:217`, `test_production_prior_closed_with_pseudo_entries_balances`. The failure message is `KKT certificate FAILED (NEWTON): {'stationarity': 1.1e-16, …} … heavily constrained problem (FRAMEWORK_REQUESTS.md, WA-1 …)`.
- **It reproduces.** It fails the same way in the main checkout (`<repo>`). Its inputs are the committed `data/sam/2023-24/blocks/production` parquet files and the solver, with no raw files involved.
- **Why it matters.** `docs/phase2/FRAMEWORK_REQUESTS.md:91` cites this test as the smoke test proving M-F1 fixed V-2. PLAN §7.1 needs `just test` green.
- **Fix.** The orchestrator (Phase 2 owner) should investigate: a solver or library drift, or a block re-built after M-F1. Either fix it, or xfail it with an ISSUES.md entry, before Checkpoint C. It does not affect the Map's numbers, which come from the certified `sam_balanced.parquet`.

### V4-02 (medium): intermittent full-document hydration failure

- **Evidence.**
  - Serving `out/` with brotli compression (`V4_scripts/vserve.mjs`) and loading the routes one after another in one browser context (`h418b.mjs`) raised `Minified React error #418 … args[]=HTML` on 6/40 and then 5/40 page loads. Affected routes: `/en/`, `/en/?y=2010-11`, `/en/story/`, `/en/story/{gst-rupee,remittance-dubai}/`, `/en/methodology/`, `/en/flow/CEN--HH/`, and the 404 page.
  - It did not happen with a fresh context per load (0/40), with the same server uncompressed (0/80), with `serve-out.mjs`, which is uncompressed (0/40), or in `next dev` (0/16).
  - A MutationObserver shows no DOM change before the failure. Then, about 300–700 ms after DOMContentLoaded (with `readyState` = `interactive`), React removes every `<head>` meta/title/link and every `<body>` child and re-creates them. This happens even on the 7 KB `404.html`, whose only app code is the root `app/not-found.tsx`.
  - So the failure is timing-dependent, at the root, and seen under the conditions a real visitor gets from Vercel: compressed HTML and a reused connection.
- **Impact.** A console error, a full re-render (visible flicker, focus or scroll reset), and the SSR work wasted. The content is still correct afterwards.
- **Why the e2e suite misses it.** `smoke.spec.ts` uses a fresh page against the uncompressed `serve-out`, so it never meets these conditions.
- **Fix.**
  - U2: reproduce with `h418b.mjs`. Bisect the root layout and `app/not-found.tsx` (head script, `<html suppressHydrationWarning>`, metadata) against Next 16.3.8 Turbopack. The `next build --webpack` build fails on this config, so that comparison was not possible.
  - Add a smoke variant that loads routes sequentially in one context against a compressing server.
  - Re-check on the Vercel preview with the console open.

### V4-03 (medium): story-page layout shift on phones

- **Evidence.**
  - Lighthouse mobile (×3, compressed): `/en/story/gst-rupee/` CLS 0.201, 0.201, 0.201, Performance 0.90, 0.89, 0.89; `/en/story/deficit-funding/` CLS 0.181 ×3, Performance 0.91.
  - Playwright at 412 px and 375 px shows one shift at about 700 ms: `.story-module__grid` y 685→435, height 138→388. At 1280 px the score is 0.
- **Cause.**
  - `src/components/story/StoryPlayer.tsx:87-94`: the server renders every step in order (no `search`, `phone=false`). After hydration, `useSearch()` and `usePhone()` switch to the single-step player.
  - Line 194 also swaps the map height from `DESKTOP_MAP_HEIGHT` (560) to `PHONE_MAP_HEIGHT` (280).
- **Fix (U5).** Make the server layout match the hydrated phone layout. For example, set the map height with CSS (`@media (max-width:639.98px)`) instead of a JS prop, and reserve the player's box: hide the non-active steps with CSS that can apply before hydration, or render the collapsed player by default and keep the no-JS full text in `<noscript>` or a `details` element.

### V4-04 (medium): heavy RSC prefetch on first view

- **Evidence.** On a first visit to `/en/` (Playwright, real network log), Next `<Link>` viewport prefetch fetches the following (raw / gzip):

  | Prefetched RSC payload | Raw | Gzip |
  |---|---|---|
  | `/en/story/remittance-dubai/` | 333 KB | 59 KB |
  | `/en/story/deficit-funding/` | 293 KB | 60 KB |
  | `/en/story/gst-rupee/` | 292 KB | 60 KB |
  | `/en/` (its own payload, already inline in the HTML) | 240 KB | 52 KB |
  | `/en/data/` | 195 KB | 42 KB |
  | `/en/methodology/` | 116 KB | 21 KB |

  That is about 294 KB gzipped, beside 185 KB of first-load JS and a 68 KB HTML document. Every other page also prefetches the header targets, about 130 KB gzipped.
- **Owners.** `src/components/ui/Header.tsx:23,31` (U2) and `src/components/story/StoryCards.tsx:18` (U5).
- **Fix.** `prefetch={false}` on header and story-card links (or prefetch on hover only), and shrink the story payloads (see V4-09). This does not fail a PLAN gate, but it costs mobile-data users more than the whole JS budget.

### V4-05 (medium): no immutable cache for hashed chunks on Vercel

- **Evidence.**
  - `web/vercel.json` sets `Cache-Control` only for `/data/(.*)` and `/data/index.json`.
  - With `"framework": null`, Vercel does not add its Next.js `/_next/static` immutable rule.
  - Lighthouse flags `uses-long-cache-ttl` and `cache-insight` ("17 resources", about 204 KB).
- **Fix (U2).** Add `{ "source": "/_next/static/(.*)", "headers": [{ "key": "Cache-Control", "value": "public, max-age=31536000, immutable" }] }`. Optionally also add `"trailingSlash": true` to vercel.json so that `/en` redirects to `/en/` on Vercel as it does in `serve-out.mjs`; without it, Vercel may serve both URLs. Then extend `headers.spec.ts`.

### V4-06 (low): `serve-out.mjs` has no compression

- **Evidence.** Lighthouse ×3 against `serve-out` (`:4747`) gave Performance 0.70 / 0.72 / 0.72, LCP 18.2 s / 6.5 s / 6.6 s (median 6.6 s), FCP 2.85 s, with "Enable text compression: 2,316 KiB". The same `out/` behind `vserve.mjs` (brotli) gave 0.99 / 1.8 s.
- **File.** `web/scripts/serve-out.mjs:13-27`.
- **Fix.** Add gzip or brotli (for example the `compression` middleware in front of `serve-handler`), or document that `start:out` is not a performance harness.

### V4-07 (low): unused d3 dependencies

- **Evidence.**
  - `web/package.json:29-35,49-55` declare `d3-array, d3-chord, d3-format, d3-interpolate, d3-scale, d3-shape, d3-time-format` and their `@types`.
  - `grep -rn d3 src scripts tests` finds no import, only colour hex values in `tokens.css`.
  - No d3 code is in any chunk.
  - `ajv-formats`, `@testing-library/dom` and `@mdx-js/react` are also never imported (`@mdx-js/react` is an optional peer of `@next/mdx`).
- **Fix (U2).** Remove them, or record why they are kept. The bundle is not affected.

### V4-08 (low): heading order on permalink pages

- **Evidence.**
  - `/en/flow/CEN--HH/`: h1, then h3 "What it is", h3, h4, h3, h3, h3.
  - `/en/series/F01/`: h1, then h3, h3, h3, h2, h2.
  - The h3s come from `FlowDetailPanel.tsx:328,333,492,615,698,…`.
  - Lighthouse Accessibility is 0.98 on both. Axe with the WCAG tags passes, because `heading-order` is a best-practice rule.
- **Fix (U3).** Pass a heading level to the panel (h2 on permalink pages).

### V4-09 (low): large per-page RSC payloads

- **Evidence.**
  - `out/en/flow/CEN--HH/index.html` is 239 KB, of which 216 KB is the inline `self.__next_f` payload. The same data is also written to `index.txt` and `__next.$d$locale.flow.$d$id.__PAGE__.txt`.
  - The largest row is the full set of entry explanations for the link.
  - About 32 KB of `map-text` labels goes to a client provider on every flow page.
  - Totals: `out/en/flow` 61 MB, `out/en/series` 46 MB, `out/` 118 MB and 1,001 files.
  - Gzipped it is modest (flow page HTML 43 KB), so this is polish.
- **Risk to check.** Confirm at the preview that the deployment stays within Vercel's output limits.
- **Fix (U3, U5).** Render static text as server-only HTML instead of passing it as client props, and pass label subsets.

### V4-10 to V4-12 (low)

These are described in the table above. For V4-10: after my `next dev` run, `git status` showed `M web/next-env.d.ts`. `npm run normalise` restored it. PLAN §4.15 states the opposite.

## What I checked and found correct

- **Clean-worktree build.** `uv sync --locked` worked, and so did `npm ci`: 890 packages in 5 s. npm 11 did not run the install scripts of `@swc/core` (via next-intl), `@parcel/watcher`, `unrs-resolver` and `fsevents`; the build is unaffected. The main checkout had no uncommitted or untracked source files (`git status` clean; only gitignored caches), and the worktree reproduced everything.
- **Standalone `web/`.** `git archive HEAD web` extracted to a temp dir outside the repo builds with `npm ci && npm run build` (Vercel's Root Directory case). The output has the same file set as the in-repo build, and every chunk is byte-identical. Only `gen-contract.mjs` reads outside `web/`, and it is not in the build.
- **`export --check`.** "matches a fresh export (27 files)".
- **Python export tests.** `pipeline test tests/export`: 84 passed (includes `test_export_determinism`, PYTHONHASHSEED 0 and 1, real data and fixture).
- **Determinism, done independently.** Two real exports to separate `--out` dirs (the second with `POLARS_MAX_THREADS=1`) are byte-identical, and identical to the committed `web/public/data` (`2023-24.410aa99863`, 26 files, 3,718,655 bytes). `export --fixture --out` is byte-identical to the committed `web/fixtures/data`.
- **vitest.** 500/500, both directly and through the `pipeline test` hook.
- **`tsc --noEmit`, `eslint .` and `gen-contract --check`.** All clean.
- **`npm run test:web`** (my run used `--output=test-results-v4`): all steps passed.
  - `check-data` OK, 26 files verified.
  - `next build`: 159 static pages (80 flow, 69 series, 4 story, home, data, methodology, root, not-found).
  - Playwright: 534 passed, 203 skipped, 0 failed, on Chromium (desktop and phone) and WebKit (desktop). The skips are all project partitioning (desktop-only or phone-only specs); there are no fixture skips on real data. Firefox is not configured.
- **First-load JS for `/en/`.** 11 chunks, 185.1 KB gzipped (level 9), under the 200 KB budget with 15 KB of headroom. The largest are react-dom (71.5 KB), the Next runtime (45.0 KB) and intl-messageformat with next-intl (12.0 KB).
- **Data sizes.** `ts/series.json` is 39.4 KB gzipped (budget 60 KB). `/en/index.html` is 67.6 KB gzipped.
- **Bundle composition.**
  - No d3 at all (the PLAN's no-full-d3 rule is satisfied trivially), and no `d3-selection` or `d3-transition`.
  - No `eval` or `new Function` in any chunk, so the CSP without `unsafe-eval` holds.
  - No fixture data in `out/`: `public/data-fixture` is removed when the data root is public.
  - Exactly one data version is in `out/data/`.
- **Lighthouse 12.6.1 mobile, `@lhci/cli` 0.15.1, simulated throttling, 3 runs, `/en/` served by brotli `vserve.mjs` (Vercel-like).**

  | Metric | Runs | Median | PLAN target |
  |---|---|---|---|
  | Performance | 0.99 / 0.99 / 0.99 | 0.99 | ≥ 0.90 |
  | Accessibility | 1.00 ×3 | 1.00 | 1.00 |
  | LCP | 1.81 / 1.66 / 1.85 s | **1.81 s** | < 2.5 s |
  | TBT | 0 / 0 / 0 ms | **0 ms** | < 200 ms |
  | CLS | 0 | 0 | — |

  Best Practices and SEO were 1.00. The LCP element is `h1#first-h1`.

  Other routes, one run each:

  | Route | Performance | Accessibility | Note |
  |---|---|---|---|
  | `/en/data/` | 0.99 | 1.00 | |
  | `/en/methodology/` | 1.00 | 1.00 | |
  | `/en/story/` | 1.00 | 1.00 | |
  | `/en/flow/CEN--HH/` | 1.00 | 0.98 | V4-08 |
  | `/en/series/F01/` | 1.00 | 0.98 | V4-08 |
  | `/en/story/*` (three runs each) | 0.89–0.91 | 1.00 | V4-03 |

- **Slider Play at 4× CPU throttle** (CDP `setCPUThrottlingRate 4`, Play from 1950-51, 12 s). Median frame 16.7 ms, p99 16.8 ms, max 17 ms, 0 long tasks, at both 1280 px and 412 px. This passes the 20 ms target.
- **Console errors.** Probed with my own Playwright run on 12 routes at 375 px and 1280 px, with the vercel.json CSP applied. There were no CSP violations and no errors other than V4-02. The 404 route logs the expected "Failed to load resource: 404".
- **vercel.json semantics (static analysis plus the emulating server).**
  - Valid JSON; `framework: null`, `outputDirectory: out`, `buildCommand: npm run build`. The build needs no Python, because `web/public/data` is committed and verified by sha256.
  - `engines.node: 24.x` selects Node 24 on Vercel, and `node-check` and `engine-strict` accept it.
  - `/` → `/en/` is a 308 (permanent).
  - `/data/<version>/*` gets `public, max-age=31536000, immutable`, which is safe because the folder name is a content hash and the exporter deletes old versions.
  - `/data/index.json` gets `max-age=0, must-revalidate`, because the later rule overrides the same key. This matches Next and Vercel ordering semantics but is still unverified on Vercel itself (PLAN R9); `index.json` is only a build input and a download link (`Downloads.tsx:32`).
  - The CSP allows everything the site uses: inline RSC and theme scripts, same-origin `fetch` of `/data`, and no `blob:`, worker, external font or third-party origin.
  - `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy` and `Permissions-Policy` are present.
  - The Vercel 404 is served from `out/404.html`.
  - Still open: the V4-05 gap, and a `curl -I` re-check on the protected preview (PLAN §7.2).

## Commands used (for re-running)

```
git worktree add /private/tmp/claude-501/v4-wt HEAD
export PATH=/opt/homebrew/opt/node@24/bin:$PATH
uv sync --locked; (cd web && npm ci)
uv run python -m pipeline export --check
uv run python -m pipeline test tests/export -q          # 84 passed
uv run python -m pipeline test                          # full: see V4-01, V4-11
uv run python -m pipeline export --out A; POLARS_MAX_THREADS=1 uv run python -m pipeline export --out B; diff -r A B
npm --prefix web run test:web -- --output=test-results-v4
node V4_scripts/vserve.mjs <worktree>/web 4748
lhci collect --url=http://127.0.0.1:4748/en/ --numberOfRuns=3   # then python3 V4_scripts/summarize.py .lighthouseci
```

## Round 2 (re-verification)

Re-verified on 2026-10-02 by V4 (independent; I fixed nothing in builder or fixer code). Checked against the working tree of branch `phase3-map` (HEAD `1c35ac2` plus the integrator's uncommitted changes), data version `2023-24.8b1b533fd6`, Node 24.21.0. Every build went through the build lock (`npm --prefix web run build`). Browser checks ran on a snapshot copy of that `out/` (in my scratchpad), served by V4's `vserve.mjs` (vercel.json rules, brotli), so concurrent rebuilds by other re-verifiers could not change it under me. My Playwright output went to my own scratchpad folder. Nothing was committed, pushed or deployed.

### Status of the high and medium findings

| id | sev | round 2 | evidence |
|---|---|---|---|
| V4-01 | high | **closed** | See below. The smoke test passes 3/3 runs, deterministically (19 Newton steps each time). It is unmarked, every non-gap KKT criterion is still required, and the change is logged (ISSUES P3-O1 RESOLVED, P3-O2 OPEN; DECISIONS D3-2). |
| V4-02 | medium | **closed (locally)** | 0 of 232 page loads raised #418: `h418b.mjs shared` 3 × 40, plus 2 × 56 with the 404 page, an unknown locale and two more permalinks. Round 1 had 6/40 and 5/40. No client reference in any inline payload names a non-component (scan of all 160 HTML files). The re-check on the Vercel preview is still the orchestrator's (PLAN §7.2). |
| V4-03 | medium | **closed** | Layout shift is 0 on all three stories at 375, 412 and 1280 px, and on 6 other routes. Lighthouse mobile ×3 (brotli): gst-rupee, deficit-funding and remittance-dubai are each Performance 0.99, CLS 0, LCP about 1.7 s. Round 1 was 0.89–0.91 with CLS 0.18–0.20. |
| V4-04 | medium | **closed** | 0 RSC requests on view, scroll through, or hover over every link, on 8 routes at 1280 and 375 px. Round 1 measured about 1.7 MB raw (about 300 KB gzipped) on `/en/`. A click still navigates softly (`window` state kept) and fetches only the target's payload: gst-rupee 305 KB raw, methodology 131 KB. No `next/link` import bypasses the wrapper, and no caller opts back in to prefetch. |
| V4-05 | medium | **closed** | `vercel.json` gives `/_next/static/(.*)` `public, max-age=31536000, immutable`, and no later rule overrides `Cache-Control`. Applying the rules last-match-wins, every one of the files under `out/_next/static` gets the immutable header, while HTML pages and `/data/index.json` do not. Lighthouse `uses-long-cache-ttl` now reports 0 resources (it flagged 17). `trailingSlash: true` was added. |

**V4-01 in detail.** I instrumented a copy of the new test.
- The certificate's own `duality_gap_rel` on this synthetic prior is 3.5e-8, and its `ok` is False.
- The exact-identity gap, computed on the same iterate, is 8.0e-12. The objective is f = 1.86e-5.
- So the failure is cancellation noise, as ISSUES P3-O1 says, and the solver has not drifted.

The test now accepts the certificate's own gap only when it is within `64·eps·Σ|a|`, which here is 2.6e-5. That is a loose bound, but it is a secondary assertion: the exact-form gap and every other criterion are asserted strictly.

The certified SAM is unaffected. `balancing_run.json` has `certificate.ok` true, gap 3.15e-13 and objective 1.14e5. The framework fix (computing the gap in `balance.py` without cancellation) is logged as P3-O2 OPEN for a later phase. I agree with deferring it, because the fix would change the certified outputs.

**Full suite.** `uv run python -m pipeline test` gives 3349 passed, 969 failed, 48 errors and 44 xfailed. Every failure and error is in `tests/raw`, the Phase 1/2 `tests/verify/*_spotcheck.py`, or `tests/units/*`. Each of these is an `OfflineMissing` pinned raw file, or (in `test_gcca_parser_rejects_wrong_year`) a `data/raw` glob that finds nothing. No failure is in `tests/sam`, `tests/export` or `tests/verify/test_phase3_*`, and none has another cause.

### Regressions looked for in my area (none found)

- **Export determinism.** `export --check` reports "matches a fresh export (27 files)". Two independent exports (the second with `POLARS_MAX_THREADS=1 PYTHONHASHSEED=1`) are byte-identical to each other and to `web/public/data`. `tests/export`: 99 passed.
- **Web checks.** vitest 523/523. `tsc --noEmit`, `eslint .` and `gen-contract --check` are all clean.
- **Standalone `web/`.** The working-tree `web/` copied outside the repo builds with `npm ci && npm run build`. This shows `package-lock.json` is consistent with the trimmed `package.json`. Every chunk is byte-identical to the in-repo build, and the other 952 differing files differ only by the random `buildId`.
- **First-load JS for `/en/`** (`first-load.mjs`'s own rule): 12 chunks, 187.7 KB gzipped, under the 200 KB budget. Round 1 was 185.1 KB, so headroom has shrunk to 12.3 KB. Story pages are 186.5 KB, flow pages 170.6 KB, and `/en/data/` 177.6 KB.
- **Data and page sizes.** `ts/series.json` is 38.5 KB gzipped (budget 60 KB). `/en/index.html` is 67.2 KB gzipped.
- **Lighthouse mobile, brotli.**

  | Route | Runs | Performance | Accessibility | LCP | TBT | CLS |
  |---|---|---|---|---|---|---|
  | `/en/` | 3 | 0.99 ×3 | 1.00 | 1.68 s | 0 ms | 0 |
  | Each story | 3 | 0.99 | 1.00 | about 1.7 s | — | 0 |
  | `/en/flow/CEN--HH/` | 1 | 1.00 | 1.00 | — | — | — |
  | `/en/series/F01/` | 1 | 0.99 | 1.00 | — | — | — |
  | `/en/data/` | 1 | 0.99 | 1.00 | — | — | — |
  | `/en/methodology/` | 1 | 1.00 | 1.00 | — | — | — |
  | `/en/story/` | 1 | 1.00 | 1.00 | — | — | — |

  On every route Best Practices and SEO are 1.00, and `heading-order` passes.
- **Slider Play at 4× CPU** (1280 and 412 px): median frame 16.7 ms, p99 16.8 ms, 0 long tasks.
- **`npm --prefix web run test:web`** (my output folder in my scratchpad): every step passed.
  - vitest: 523/523.
  - `first-load`: 187.7 KB.
  - Playwright: 557 passed, 219 skipped, 0 failed, 0 flaky, on Chromium desktop and phone and on WebKit desktop. As in round 1, the skips are project partitioning (desktop-only or phone-only specs and WebKit's testMatch). No test was skipped for fixture data.
  - New fixer tests: `smoke.spec.ts` "inline RSC payloads reference only client components" and "hydration survives any one late script chunk" (V4-02); `story.spec.ts` "hydration does not shift the story page (V4-03)"; `headers.spec.ts` checks the immutable `/_next/static` rule and `trailingSlash` (V4-05).
  - The fixers added no regression test for V4-04. My spec below covers it.

### Low findings

| id | round 2 | note |
|---|---|---|
| V4-06 | open | `serve-out.mjs` still has no compression and its header comment still says it serves "like Vercel would". U2 declined the fix ("a local harness, not a performance gate"). The comment should at least say it does not compress, so nobody runs Lighthouse against it. Guarded by `test.fail` in my spec. |
| V4-07 | closed | The seven d3 modules, their `@types` and `ajv-formats` are gone; `npm ci` from the trimmed lock works. PLAN §6.4 still lists the d3 modules (a text drift, noted by U2). |
| V4-08 | closed | Lighthouse `heading-order` passes and Accessibility is 1.00 on the flow and series pages; `tests/e2e/headings.spec.ts` checks it. |
| V4-09 | open | Payload sizes are unchanged: the flow page is 237 KB raw and 42.9 KB gzipped; `out/` is 120 MB with 1,002 files. Polish only; check Vercel's output limits at the preview. |
| V4-10 | open (not re-tested) | PLAN §4.15 text unchanged. |
| V4-11 | orchestrator | Still true: 12 `tests/units` failures and 23 errors are raw-only (listed above). Checkpoint C should list them. |
| V4-12 | open, harmless | Two builds still differ only by `buildId`; I checked that the 1,002 files are equal once it is substituted. **Do not fix this with a constant `generateBuildId`.** Under the new immutable `/_next/static` rule, `_buildManifest.js`, `_ssgManifest.js` and `_clientMiddlewareManifest.js` keep fixed names inside the build-id folder, so a constant id would freeze them in browser caches for a year. A content-derived id would be safe. Guarded by `test_v4_05_fixed_name_build_files_sit_under_a_per_build_folder`. |

### New in round 2

| id | sev | title | owner |
|---|---|---|---|
| V4-13 | low | `web/.gitignore` ignores `test-results/` and `playwright-report/` but not the per-run folders (`test-results-v1`, `-v2`, `-u1fix`, …). Those show up as untracked and would be committed by a careless `git add -A` (`git status` already lists `web/test-results-v1/…` and `web/test-results-v2/.last-run.json`). Fix: `test-results*/`. | U2 / orchestrator |

### Verifier tests (V4-owned)

These are new; round 1 had no V4 test files.
- **`tests/verify/test_phase3_build_perf.py`**: 6 passed, 1 strict xfail.
  - V4-01: the smoke test is unmarked and still asserts each KKT criterion; the certified run is far above the noise floor; P3-O1 and P3-O2 are logged.
  - V4-05: the immutable rule covers every `/_next/static` file and no HTML page, and fixed-name files sit under a per-build folder.
  - V4-07: every runtime dependency is used, and no d3 is declared.
  - V4-13: `xfail(strict=True)`, open.
- **`web/tests/verify/v4_build_perf.spec.ts`** with `playwright.v4.config.ts`. The spec serves `web/out` itself, compressed and with the vercel.json rules applied, because V4-02 only showed under that delivery.
  - It checks V4-02 (sequential shared-context loads, 2 × 11 routes), V4-03 (CLS < 0.05 for every story at 375, 412 and 1280 px), V4-04 (no RSC request on view, scroll or hover; a click still soft-navigates and fetches only its own payload) and V4-05 (as served).
  - V4-06 is `test.fail`.
  - Result: 8 passed (including the expected failure), 4 skipped (desktop-only tests in the phone project). I ran it under the build lock immediately after a fresh build.
  - Run: `cd web && npx playwright test -c tests/verify/playwright.v4.config.ts --output=<own folder>`.

**Round 2 verdict.** All four medium findings and the high one are closed. Still open, as low: V4-06, V4-09, V4-10, V4-12 (harmless; do not "fix" it with a constant id) and the new V4-13. The remaining Checkpoint C items are unchanged:
- the console re-check of V4-02 on the Vercel preview;
- `curl -I` of the headers on the preview;
- Vercel's output limits for the 120 MB `out/`.
