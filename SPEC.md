# SPEC — India's Economy as a Working Model

> Kickoff prompt to paste into Claude Code (Opus 5.5):
>
> **ultracode** — Read `SPEC.md` in full. Execute **Phase 0 only**, then stop at Checkpoint A and report to me. Do not start later phases until I approve.

---

## 1. Mission

Build a free, public, live website that shows the entire Indian economy as one connected, balanced system: every major flow of money between households, firms, banks, the Centre, the States, the RBI, markets and the rest of the world. Then let anyone run "what if" scenarios on it.

The goal is **awe plus truth**. A 15-year-old in Patna and a fund manager in Mumbai should both learn something real within 60 seconds. Every number must be traceable to a public source. Nothing is invented.

Three layers, built in order:

1. **The Map** — a balanced Social Accounting Matrix (SAM) of India for the latest available year, plus a time series of key flows, visualized interactively.
2. **The Engine** — a SAM multiplier model (Leontief / SAM multipliers) that runs live in the browser for scenario shocks.
3. **The Simulator** — an agent-based model (ABM) of households, firms, banks, government, RBI and rest-of-world, calibrated to the SAM, for richer scenarios.

## 2. About me (the owner)

- I'm Jitesh, founder of Udgam Labs. I'm a vibe coder, not a programmer: explain decisions in plain English and keep the codebase clean enough that future agents can extend it.
- I have finance training (CFA L2, FRM, IIM Lucknow MBA), so don't dumb down the economics when talking to me. Do make the public site accessible to everyone.
- Work autonomously. Ask me only at the checkpoints below, or when a decision is genuinely ambiguous or irreversible.
- I can arrange access to data sources that need a login or key. List what you need; don't work around access restrictions.

## 3. Non-negotiable rules

1. **No fabricated data.** Every figure carries provenance: source, URL, table or series ID, retrieval date, unit, and price basis (current vs constant). If a number is estimated, label it `estimated`, record the method, and show that label in the UI.
2. **Verify first.** Before relying on any source, confirm it exists, what its latest release is, the current GDP base year, its release lag and its license. Do not assume from memory. Base years and table vintages change.
3. **Independent verification.** Any agent that extracts or computes data must be checked by a different agent that did not produce it. Verifiers try to break the result, not confirm it.
4. **No silent fallbacks.** If a source fails, a series is missing or a reconciliation doesn't close, log it loudly in `ISSUES.md` rather than patching around it.
5. **Respect licenses and terms of service.** Prefer the official open-data licence (GODL-India) and other open sources. Attribute every source on the site. No scraping that violates a site's terms.
6. **Honest framing.** The simulator is illustrative, not a forecast. Say so clearly in the UI. Show uncertainty and model limits.
7. **Budget discipline.** Run one phase at a time. At the end of each phase, report agents spawned, approximate tokens used and wall-clock time.

## 4. Scope of flows (must all be represented)

- **Production and income:** GDP by production (GVA by sector), by expenditure (consumption, investment, government, net exports) and by income (compensation of employees, operating surplus, mixed income), including the official statistical discrepancy.
- **Government:** Union and State receipts and expenditure separately, transfers from Centre to States (Finance Commission devolution, grants), subsidies, interest payments, deficits and borrowing.
- **Taxes:** GST (CGST, SGST, IGST, cess), income tax, corporate tax, customs, excise, and what share each institution pays.
- **Households:** split at minimum rural/urban and by consumption quintile (use the latest household consumption survey), plus income sources, consumption, savings and financial vs physical assets.
- **Firms:** non-financial corporations, split public and private where the data allows.
- **Financial system:** RBI, banks, NBFCs, insurance and pension funds, mutual funds. Show credit flows, deposits and the Flow of Funds between sectors.
- **Markets:** equity (primary issuance, FPI and DII flows), government and corporate bonds, money markets.
- **External sector:** trade in goods and services by major partner and product group, remittances, FDI, FPI, ECBs, NRI deposits, outward investment, forex reserves (full balance of payments).

## 5. Candidate data sources (verify each in Phase 0; add better ones you find)

Official Indian:
- **MOSPI:** National Accounts Statistics, Supply-Use Tables / Input-Output tables (find the latest published vintage), household consumption survey, PLFS, ASI, IIP, CPI, WPI.
- **RBI:** DBIE database, Handbook of Statistics on the Indian Economy, Flow of Funds accounts, Balance of Payments, State Finances study, banking statistics, remittance surveys.
- **Ministry of Finance:** Union Budget documents, Controller General of Accounts monthly accounts, CBDT and CBIC data, GST collection releases.
- **Commerce:** DGCI&S and TradeStat export/import data.
- **Markets:** SEBI bulletin, NSDL FPI data, AMFI, NSE/BSE, CCIL.
- **States:** RBI State Finances study, PRS Legislative Research state budget analyses.

International (for gaps and cross-checks):
- OECD Inter-Country Input-Output tables, ADB multi-regional IO tables, World Bank WDI, IMF (IFS, BOP, GFS), UN Comtrade, BIS.

## 6. Phases, deliverables and definitions of done

### Phase 0 — Reconnaissance (ultracode: one agent per source family, plus verifiers)

- Build `SOURCES.md` and `data/registry.yaml`. For each source, record URL, access method (API, bulk download, PDF, HTML), format, license, frequency, latest release date, release lag, coverage years and known quirks.
- Confirm the current GDP base year and the latest Supply-Use Table or IOTT year. Recommend a **SAM reference year**: the latest year where production, expenditure, income, government, BOP and Flow of Funds data all exist.
- Produce a **gap map**: which SAM cells can be filled from official data, which need international tables, and which need estimation. Include the estimation method for each.
- Propose the SAM account structure: target 20–35 production sectors, 2–4 factor accounts, institutional accounts per Section 4, capital account, taxes, RoW. Justify the granularity.
- Propose the tech stack (see Section 7) and the repo structure.

**Checkpoint A:** report the reference year, gap map, account structure, stack and anything you need me to arrange access to. Wait for my approval.

### Phase 1 — Data pipeline

- Reproducible ingestion scripts per source: raw data → cleaned, typed, unit-normalised tables (₹ crore, current prices unless stated) with provenance attached.
- Every series is versioned. Re-running the pipeline must reproduce identical output.
- Automated tests for schema, units, ranges and continuity (flag breaks and revisions).
- **Done when:** all Phase 0 "officially fillable" cells have clean data with provenance, and a verifier has spot-checked at least 10% of values against the original documents.

### Phase 2 — The balanced SAM

- Assemble the unbalanced SAM from Phase 1 data.
- Balance it with RAS and/or cross-entropy. Report every adjustment's size and direction in `BALANCING.md`. Large adjustments are findings, not noise.
- **Acceptance tests:**
  - every account's row total equals its column total, within stated tolerance;
  - GDP from production, expenditure and income matches official figures, allowing only the official discrepancy;
  - government, BOP and Flow of Funds totals match their official sources within tolerance;
  - no cell changes by more than a stated threshold during balancing without a logged explanation.
- Also build a lighter annual time series of the top ~50 flows for as many years as data allows.

**Checkpoint B:** show me the SAM, the balancing report and the biggest surprises in the data. Wait for approval.

### Phase 3 — The Map (website v1)

- An interactive flow visualization (Sankey or network) of the whole economy, with **zoom levels**: whole economy → sector → sub-flow. The time slider covers every year in the time series.
- Click any flow to see its value, its share of GDP, its trend, a plain-English explanation and its source links.
- **Explain mode:** guided stories, e.g. "Where does your GST rupee go?", "How a remittance from Dubai moves through India", "Who funds the government's deficit?"
- Mobile-first, fast (static data where possible), accessible, with light and dark themes. English first; structure the text so Hindi and other languages can be added later.
- A "Methodology & sources" page that is honest about estimates and limits.

**Checkpoint C:** give me a preview link before any public deploy.

### Phase 4 — The Engine (SAM multiplier model, live in browser)

- Compute SAM multipliers and let users apply shocks: government spending, export demand, remittance changes, investment, tax rate changes.
- Show the ripple through sectors, income groups, government revenue and imports, animated on the Map.
- **Validation:** document the multiplier model's assumptions (fixed prices, excess capacity) in plain English. Cross-check headline multipliers against published Indian estimates and explain differences.

### Phase 5 — The Simulator (agent-based model)

- Agents: households (heterogeneous, calibrated to survey distributions), firms by sector, banks, government (Centre and States), RBI with a policy rule, and rest-of-world.
- Calibrate so the model's steady state reproduces the Phase 2 SAM.
- **Scenario presets:** repo rate ±100bp, a GST rate change, oil price shock, monsoon failure, sudden FPI outflow, fiscal stimulus, and a remittance collapse.
- **Validation:** it should reproduce the *direction* and rough magnitude of known episodes (e.g. the 2020 COVID shock and the 2022 rate-hike cycle). Report where it fails.
- Run the heavy ABM offline in Python and precompute scenario results. Ship a lighter, scaled-down version (in a Web Worker) so users can tweak parameters live.

### Phase 6 — Live updates

- Scheduled jobs refresh sources on their release cycle and rebuild affected layers. Surface "what changed" on the site (e.g. "New GST data: collections up X% YoY").
- Monitoring: alert me when a source breaks or changes format.

## 7. Technology preferences

- **Data and models:** Python (pandas or polars, DuckDB, numpy/scipy), output as versioned Parquet plus compact JSON for the web.
- **Frontend:** Next.js + D3 (or a better choice you can justify), deployed on Vercel. I already use Vercel and Supabase.
- Prefer a static-first architecture. Use Supabase only if something genuinely needs a database, and explain why.
- Every phase leaves tests that pass with one command.

## 8. Repo conventions

- `SPEC.md` (this file), `DECISIONS.md` (dated decision log with reasons), `SOURCES.md`, `ISSUES.md`, `BALANCING.md`, `CLAUDE.md` (how future agents should work in this repo).
- `data/raw` is never edited by hand. `data/clean`, `data/sam`, `models/`, `web/`, `tests/`.
- Small, reviewable commits with clear messages.

## 9. How to use workflows

- Split each phase into workflows: **understand → build → verify**. Use a separate verification workflow whose agents did not do the building.
- Run parallel agents where the work is truly parallel (one per source, one per SAM block, one per scenario). Don't use them for tasks that need a single coherent design, like the account structure or the UI.
- End every phase with a short report covering what was built, what failed, what is estimated, open questions, and the agents, tokens and time used.
