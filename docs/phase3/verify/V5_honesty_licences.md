# V5: Honesty and licences

Verifier V5, PLAN §7. Branch `phase3-map`, working tree clean, export `2023-24.410aa99863`. I checked the built site in `web/out/` (built 12:44 from the real export; I took a snapshot copy so concurrent builds could not change it under me), the export JSON, the content and message files, and the source code. I also ran the fixture guard and drove the site in Chromium (Playwright, 1280×800 and 375×812) against the snapshot.

I did not edit any builder-owned file and did not commit anything. My scripts are throwaway: they parse `out/**/*.html` with BeautifulSoup, plus three Playwright scripts. Each check below says how to repeat it.

## Verdict

**Two high findings: the Checkpoint C gate is not met.**
- **V5-01:** every "before → after balancing" percentage in the flow panel is 100 times too large.
- **V5-02:** the GDP card and every series page show "Official" next to the sentence "The total is not held to a single published figure."

The rest of the honesty work is sound:
- RBI links are withheld everywhere, including the JSON downloads and JS bundles.
- Attribution matches the registry.
- The top-flows banner shows for all 75 other years.
- Linked series are labelled "derived".
- No text claims a SAM for any other year.
- The fixture guard stops a production build.

## Findings

| id | sev | title | owner |
|---|---|---|---|
| V5-01 | high | Balancing move percentages shown ×100 (e.g. +7.3% shown as "726.3%") | U3 (display), U1 (unit contract, fixture) |
| V5-02 | high | "Official" figures say "The total is not held to a single published figure" (GDP, all 69 series pages, the panel's series value) | U2 (StatusBadge), U3 (callers) |
| V5-03 | medium | The methodology page claims "Every figure on this site carries a badge", but 18 money figures on that page have none | U6, U1 |
| V5-04 | medium | The first screen's "of every ₹100" parts drop the official totals: household saving reads "Set by balancing" and consumption "Estimated", while the map says "Official total · split …" | U1 (summary.headline schema), U3 |
| V5-05 | medium | Pinned-total disclosures show raw ids ("ts:M05", "closure:d1.published_total"), not the published figure that pins them | U2 / U3 |
| V5-06 | medium | The licence paragraph understates RBI: it says RBI permission is needed only "for links and caching", but republishing RBI-derived figures also needs permission (D1-1(d), SOURCES §4–5, CHECKPOINT_B §8) | U6 |
| V5-07 | medium | The "Choices accepted provisionally" list is incomplete against CHECKPOINT_B §6 / D3-0: D2-7 (rest_of_world-26) is missing, and 9 of the 13 §6c items are not named, including the fincorp-27 holder key (₹8.21 lakh crore) | U6 |
| V5-08 | medium | The IFPRI source cited by 263 SAM entries is not in `data/registry.yaml`. It is only in `data/registry_additions/` (status "unverified"), so its licence and attribution are unverified | orchestrator (merge/verify), U1 |
| V5-09 | low | Series pages headline the latest value (2025-26, PE/provisional) with no estimate-stage label; the stage appears only in the table | U3 |
| V5-10 | low | Explanation excerpts quote values from an older balancing run ("17,751 -> 3,035" next to a balanced ₹3,032 crore) | orchestrator (explanations), U1 |
| V5-11 | low | SVG ribbon value labels and the trend chart's "SAM 2023-24" point carry no status; status appears only in the tooltip, aria-label or panel | U3 |
| V5-12 | low | Small wording mismatches: CAG is missing from the permissions list in the licences paragraph (it is on the P1-9 list in "Open issues"); the household residual is called "published" in the prose but badged "Derived total" | U6 |
| V5-13 | low | The fixture guard lives only in the npm `build:nolock` script; a bare `next build` on fixture data succeeds and only the footer note shows it | U2 |
| V5-14 | low | The top-flows banner says "the {n} largest flows" (the ribbons are a curated list, not the largest), and shows n = 0 until `series.json` loads | U3 |

### V5-01 (high): balancing move percentages are 100 times too large

**Evidence.** `entries/*.json` `pct_change` is in **percent**. It is copied from `balancing_log.pct_change` (`pipeline/export/sam_export.py:244,262`). For example, H_R2 ← F_LREG F1a moved from 2,43,892 to 2,45,193, and `pct_change` = 0.533395. The panel formats it with `fmt="pct"`, which treats its input as a **fraction** (`web/src/lib/format.ts:10`) and multiplies by 100.

**Where.** `web/src/components/map/FlowDetailPanel.tsx:416-419`: `(<Num value={e.pct_change} fmt="pct" />)`.

**What the user sees.**
- Every "Before → after balancing" line on all 80 `/en/flow/*` pages and in the live panel at levels 0–2. For example, `/en/?p=full&x=HH&s=H_U5--K_HH` shows "₹12.00 lakh crore → ₹12.87 lakh crore (726.3%)"; the true move is +7.26%.
- On `/en/flow/CEN--NFC/`, one entry reads "₹17,751 crore → ₹3,032 crore (−8,291.8%)". The "why" text directly below it says "-82.9%".
- Unchanged entries can read "0.0%" when their real move is a few hundredths of a percent.

This is a wrong number on the most important honesty feature of the panel: how much balancing moved a figure. `fidelity.spec` cannot catch it, because the text equals `format(value)`; the value's unit is what is wrong.

**Related.** The fixture computes `pct_change` as a **fraction** (`pipeline/export/fixture.py:140`), so the fixture and the real export disagree on the unit. The schema (`pipeline/export/schema/entries.schema.json:61`) does not define the unit.

**Fix.**
- U1: choose one unit (a fraction, to match `format.ts`), export the real data as `pct_change / 100`, make the fixture agree, document it in the schema, and add a test: `pct_change ≈ change / |prior|`.
- Or U3: divide by 100 at the call site.
- In either case, add a vitest or e2e assertion on one known entry (H_U5 ← … K4a: +7.3%).

### V5-02 (high): "Official" next to "The total is not held to a single published figure"

**Evidence.** `StatusBadge` (`web/src/components/ui/StatusBadge.tsx:81-85`) shows `noTotal` ("The total is not held to a single published figure.") whenever `total` is null, whatever the split label. These callers pass `total={null}` for figures that **are** published figures:
- the GDP card on the first screen, `FirstScreen.tsx:34`. `/en/` shows "India's GDP in 2023-24 ₹290.73 lakh crore · Official", and activating the badge shows "Taken from a published official statistic. The total is not held to a single published figure.";
- the series value in the panel and on all 69 `/en/series/*` pages, `FlowDetailPanel.tsx:690` (for example, F01's ₹196.18 lakh crore);
- the methodology GDP badge (`SummaryBadge`).

**Why it matters.** GDP (NAS Statement 1.1) and a published series value are by definition held to a published figure. The disclosure contradicts the label next to it on the most prominent number on the site. This is misleading wording in the labelling system V5 is asked to certify.

**Fix.**
- U2: when `total` is null and `split` is `official` or `derived` for a single published figure, show a neutral line ("This is the published figure itself"), or add a `published` prop that suppresses `noTotal`.
- U3: pass it from FirstScreen and the series panel.
- Alternatively, U1 exports `gdp.total = "official"` (pinned by M01) and series rows carry `total = status`.

### V5-03 (medium): the methodology page says every figure has a badge; 18 there do not

`content/en/methodology/status.mdx:1` says "Every figure on this site carries a badge". The site's meta description says "every figure labelled by how it was made".

On `/en/methodology/`, 63 bound figures render and only GDP has a badge. The 18 unbadged money figures include:
- the SAM grand total ₹2,532.21 lakh crore;
- ₹28.38 lakh crore moved (9.8% of GDP);
- household factor income ₹192.46 lakh crore;
- the old-base ₹19.15 lakh crore and the judgement-band ₹30.12 lakh crore;
- the five X_DISC values: ₹5.71, ₹2.12, ₹2.04 and ₹1.55 lakh crore, and ₹0.0 crore.

U6 logged this (issues/U6.md, "Badges on methodology figures"), and U1 offered to export labels (issues/U1.md). Neither was done. The economic values are exactly the items whose status matters (X_DISC D1 = derived total, split estimated; factor income = derived total, split set by balancing on the map).

**Fix.** U1 exports `total`/`split` for `hh_factor_income`, `disc_*`, `judgement_band_abs` and `old_base_abs`, and U6 renders a badge after each. Alternatively, U6 rewrites the claim to "Every figure about the economy carries a badge; counts and rule thresholds on this page do not". The X_DISC and factor-income values still need badges.

### V5-04 (medium): the first screen's household parts hide their official totals

`summary.headline.hh_outlays.parts[*]` carries only `split_label` (`pipeline/export/summary.py:79`, `schemas.py:112`). `FirstScreen.tsx:56` renders `StatusBadge total={null}`. As a result:
- "Saving ₹24.0" reads **Set by balancing**, while the same flow on the map (HH→SI, household saving, NAS) reads "Official total · split set by balancing";
- "Goods and services ₹66.8" reads **Estimated**, while HH→PRODUCERS (PFCE) reads "Official total · split estimated".

A reader of the 60-second screen is told that household saving was set by balancing. PLAN §4.0 asks for "Official total · split estimated" where the data says so. Here the data says so for the consumption and saving parts.

**Fix.** U1 adds a `total_label` (pinned check) to each part. U3 passes it. The ₹-per-₹100 share can keep the split label.

### V5-05 (medium): pinned-total disclosures show ids, not the published figure

The badge disclosures read like this:
- "The total is held to a published figure: ts:M05" (`/en/flow/DISC--ROW/`);
- "closure:d1.published_total" (`/en/flow/HH--DISC/`);
- "production:valuables.c_gjom, ts:F03, ts:M10" (`/en/flow/SI--PRODUCERS/`).

PLAN §3.4.2 specifies a plain-English display: "Held to NAS Statement 1.14 PFCE within ₹1 crore". `constraints.json` already has `description` and the series have names. This is the reader's only way to see *what* makes a total official.

**Fix.** U2/U3 map each pin id to the constraint description or "series {name} ({id}), check passes".

### V5-06 (medium): the licence paragraph understates RBI's restriction

`content/en/methodology/sources.mdx:5` lists the RBI among the publishers that need permission only "for links and caching". The project's own records go further:
- DECISIONS D1-1(d): "RBI files are downloaded for internal processing only";
- CHECKPOINT_B §8: "RBI series are for internal processing only";
- SOURCES §4: RBI Handbook, BoP and debt releases carry "No licence statement; all rights reserved";
- SOURCES §5 1(a): permission is needed "to republish derived aggregates (BoP, Handbook, FSF, State Finances, banking) on the public site".

The site does republish RBI-derived figures: BoP-based flows, FSF counterparties, remittances (F43), and the RBI survey's UAE share. The remittance story itself says the survey figures "may be used here only for internal processing". So the methodology's licence statement is the less accurate of the two.

**Fix.** U6 says that RBI permission is needed both to link and cache and to republish RBI-derived figures, and that this blocks the public launch. Separately, for the orchestrator: nothing in code prevents a public deploy from showing RBI-derived figures, so the Checkpoint C report should list every RBI-sourced flow and story figure on the P1-9 list, not only the UAE figure.

### V5-07 (medium): the provisional-decisions list is incomplete

D3-0 accepts CHECKPOINT_B §6 (6a, 6b, 6c) provisionally. `content/en/methodology/provisional.mdx` names:
- 6a: D2-20, D2-19, D2-24, D2-11, D2-13, D2-21, D2-4 and D2-8. **D2-7 / rest_of_world-26 is missing.** That is the Union's IMF income and SDR charges sitting on the RBI. CHECKPOINT_B's suggestion was to *move* them, so it is unclear whether the "provisional acceptance on the suggestion" is reflected in the data at all.
- 6b: the bands, via limits. These are complete: 11 bands, 97 entries.
- 6c: only 4 of 13 items (fincorp-37, fincorp-34b, factors-24, households-1). Missing:
  - FISIM on household loans (3.24 lakh crore, households-19);
  - the private-NFC distributed-income holder key (8.21 lakh crore, fincorp-27);
  - ULB capital in the GG investment key;
  - the GG saving bridge remainder;
  - the R18 vs FC16 overlap;
  - the RoW property income re-split (rest_of_world-27);
  - premiums = claims by payer;
  - V-FIN-10;
  - the time-series whitelist.

**Fix.** U6 adds D2-7 and either names the remaining 6c items or says "and nine smaller open items (list)". The orchestrator confirms the D2-7 status.

### V5-08 (medium): an IFPRI source attributed from an unverified, unmerged registry entry

`provenance.sources.ifpri_nexus_sam_india_2022_23_paper` is cited by 263 SAM entries, 11 totals or bands, and 24 story figures. It exists only in `data/registry_additions/io_tables.yaml:3` and is shown on the site as "registry id … · unverified".

PLAN §3.5 says attribution is copied from `data/registry.yaml`. CLAUDE.md says additions are "unverified until merged". The exporter's error text claims every source is "in data/registry.yaml" (`pipeline/export/provenance.py:108`), but `load_registry()` evidently merges the additions.

The CC BY 4.0 licence and its "adapted, not endorsed" duty rest on an agent-added record nobody has verified. The site does print the IFPRI disclaimer, which is good.

**Fix.** The orchestrator verifies the licence and merges the entry into `registry.yaml` (or a verifier signs it off). U1 corrects the error wording and/or has `test_provenance` report sources that come from additions.

### V5-09 (low): series headlines omit the estimate stage

Series pages headline the latest value, for example "Value in 2025-26 ₹196.18 lakh crore … Official" for F01, which is a PE (provisional estimate). The stage is visible only in the "Every year" table. Methodology promises "the stage of each estimate is marked". `FlowDetailPanel.tsx:680-690` shows the value with no stage.

**Fix.** U3 adds "(provisional estimate)" or the stage beside the headline value when `stage[i]` is not null.

### V5-10 (low): stale numbers in the "why" excerpts

On `/en/flow/CEN--NFC/`, the entry shows "₹17,751 crore → ₹3,032 crore", and its "why" excerpt says "17,751 -> 3,035 (-14,716, -82.9%)". The explanation texts in `pipeline/sam/explanations/*.yaml` quote an older run's values.

**Fix.** The orchestrator refreshes the quoted numbers. Alternatively, U3 strips the numeric preamble and shows only the verdict text. V1 may want to count how many differ.

### V5-11 (low): diagram value labels and the SAM trend point have no status

The SVG labels on `/en/` carry no status text: 15 ribbon values (for example ₹164.16 lakh crore) and the stub labels ("₹10.77 lakh crore to Banks…"). The pattern encodes only the split label, and the total label appears only in the `<title>`, aria-label or panel. The trend chart's "◆ SAM 2023-24: 56.5% of GDP" point has no badge either. These are not `data-num-value`, so `fidelity.spec` does not check them.

**Fix.** U3 adds `data-num-value` to SVG value labels. Optionally, put a short status suffix where the ribbon is wide enough, and give the SAM point its link's badge text.

### V5-12 (low): wording mismatches

- `sources.mdx:5` lists permissions as "MoF, SEBI, GSTN and DGCI&S, and the RBI". ISSUES P1-9 and the page's own "Open issues" section also list CAG. The same paragraph says only CGA and FC16 are "on the list of reuse terms to confirm", but SOURCES §5 item 14 also lists PFRDA.
- `limits.mdx:25` and `map-desc` (HH--DISC) call the household residual "published", but its badge is "Derived total" (pin `closure:d1.published_total`, status derived).

**Fix.** U6 aligns the wording: "derived from published figures", or the badge kind if U1 decides it is official.

### V5-13 (low): a bare `next build` bypasses the fixture guard

The guard (`web/scripts/check-data.mjs`) runs only inside `npm run build:nolock` and `build-and-e2e.mjs`. `src/data/server.ts` (`loadIndex`) never checks `idx.fixture`, so `DATA_ROOT=fixtures npx next build` would produce a fixture site. Only the footer and methodology notes would mark it. Vercel uses `npm run build`, so the deploy path is safe.

**Fix.** U2 makes `loadIndex()` throw when `fixture === true && process.env.ALLOW_FIXTURE !== "1"`.

### V5-14 (low): top-flows banner wording

`messages/en/map.json` `ts.banner` says "you are seeing the {n} largest flows we have annual series for". The ribbons are the curated `ts/view.json` list (16 ribbons), not the n largest; for example 7 in 2004-05, while 24 flows have data. In `MapApp.tsx:221`, `drawnTs` is 0 until `series.json` arrives, so the banner briefly says "the 0 largest flows".

**Fix.** U3 rewords to "{n} of the main flows we have annual series for" and hides n until loaded.

## What I checked and found correct

1. **Fixture guard (PLAN §3.10).**
   - `DATA_ROOT=fixtures npm run build` exits 1 at `check-data` ("A production build on fixture data is not allowed"). `out/` was untouched (same mtime).
   - `check-data.mjs` directly: fixtures → exit 1; `ALLOW_FIXTURE=true` → exit 1 (only `"1"` counts); `ALLOW_FIXTURE=1` → exit 0 with the "E2E ON FIXTURE DATA … Checkpoint C may not cite it" banner; an absolute-path root → treated as fixture, exit 1; `DATA_ROOT=public` → OK, 26 files sha-verified.
   - A missing `public/data/index.json` defaults to fixtures, so it also fails (`src/data/root.mjs:15-16`).
   - The footer and methodology show a fixture warning when `index.fixture`. `out/` has no `data-fixture/`. A unit test covers the guard (`tests/unit/platform/scripts.test.ts:31`). See V5-13 for the bypass.
2. **No RBI hyperlinks.**
   - 0 occurrences of `rbi.org.in` anywhere in `out/`: 160 HTML pages, all JS chunks, and the downloadable `out/data/**` JSON including `provenance.json`.
   - External hrefs go only to mospi, cga, indiabudget, irdai, fincomindia, sebi, cgspace, pfrda, ppac, epfo and handle.net.
   - The 12 RBI sources render "Link withheld until RBI grants permission (ISSUES P1-9)" with name, publication, table and retrieval date (for example ROW→HH cites the Remittances Survey, Table 2).
   - `link_policy.yaml` covers the six RBI hosts.
3. **Attribution matches the registry.** For all 32 exported sources, `attribution` and `licence` equal the registry's `license.attribution` and `license.name` (31 from `registry.yaml`, 1 from additions: V5-08). The methodology source cards show publisher, licence, attribution, link mode, citation counts and registry id/status.
4. **Licence duties from SOURCES §4.**
   - MoSPI's prominent acknowledgement is met: each panel names publisher, table and retrieval date.
   - The IFPRI "adapted, not endorsed" disclaimer is present.
   - The methodology says plainly that permissions are pending and that this is a private preview, not a public launch.
   - "Open issues" lists RBI (including the remittance survey), MoF, SEBI, GSTN, DGCI&S and CAG.
   - The remittance story says the UAE figure's link is withheld and that it is on the permission list.
5. **Total labels only where pinned.**
   - All 80 `/en/flow/*` pages: the headline badge's `data-status-total` equals `pinned.json` for that link id (0 mismatches).
   - All 51 drawn links on `/en/` (simple preset): "Official/Derived total" appears in the aria-label exactly when the link is pinned, and of the right kind.
   - Pair-only pins (SI--PRDS, SI--PRODUCERS, both parts) show "Together with the other part of this pair…" and `panel.pairNote`.
   - The matrix `totalFor()` uses part and pair pins correctly.
   - All 120 story figures have a badge that equals the story JSON's total and split (0 mismatches).
6. **Every number has a badge (outside V5-03, V5-04 and V5-11).**
   - All 6,753 `data-num-value` elements in `out/` were scanned. Outside the methodology page, the only numbers without a badge in reach are entry rows in "What is inside", which carry a text label column ("Official", "Estimated", …).
   - Client states checked: home default, the table view (130 numbers, all badged), panel open, top-flows 2004-05 (56, all badged), and a series selected in a non-SAM year.
7. **Top-flows banner shows for every year other than 2023-24.**
   - Stepping the year `<select>` through all 76 periods at both viewports: every year ≠ 2023-24 switches to `data-view="ts"` with the visible banner "…not a complete, balanced account of the economy; that exists only for 2023-24", plus "See the complete map for 2023-24".
   - `?view=sam&y=1990-91` is forced to ts.
   - Scrubbing into 2023-24 keeps ts with the banner (PLAN §2.1.3).
   - No console errors.
8. **Linked series are labelled "derived".**
   - All 10 linked flows (F01, F03, F05, F06, F07, F37, M01, M02, M03, M06) show "Show the linked series (derived)", off by default.
   - Turning it on (F01) redraws the chart and shows "The linked series rescales earlier years to the 2022-23 base. It is derived, not published."
   - The markers read "Linked (derived) series: old-base value x …".
9. **No claim that the SAM exists for other years.**
   - All messages and content (MDX, map-text, map-desc) were searched for SAM/balanced/complete-map sentences naming another year: none.
   - The methodology says "No balanced map exists for any other year … does not interpolate … or project backwards". Titles say "A flow in the 2023-24 map". The panel says "only the 2023-24 SAM value exists" where no series matches.
10. **Methodology limits are complete against PLAN §4.10.5 and the brief, apart from V5-07.**
    - one-year SAM;
    - balancing (cross-entropy, certified, ₹28.38 lakh crore moved, 151/64/8 verdicts);
    - the 11 §6b judgement bands (97 entries, ₹30.12 lakh crore) listed in plain words, with "a test … if they are halved or doubled has not been run";
    - Checkpoint B provisional acceptance;
    - HCES at 44.3% of PFCE;
    - IFPRI gradients (D2-19);
    - no microdata (D1-2);
    - NPISH;
    - old-base structures (D2-21; 36 entries, ₹19.15 lakh crore);
    - the five X_DISC items, each described as what it is (D2 "not money paid abroad", D4 = 0);
    - splices, base break and the linking rule;
    - "not complete and not balanced" for top flows;
    - average shares, not multipliers;
    - "Not a forecast" at the top of the page and in "What this is not".
11. **CHECKPOINT_B §8 "estimated" categories (PLAN §3.4.4).**
    - All 1,787 entries touching a household-group account are `estimated` (1,519) or `balancing_set` (268); none is official or derived.
    - Official or derived cells in the FC, Centre/State and K8/K9 categories are published items, not the splits §8 lists: devolution R1, RBI surplus R6, BoP-based K8b, reserves K8c, NAS 5.3 household borrowing K8a, and tax receipts T1a.
    - No household-group, FC sub-sector or K9 split shows an `official` split label.

## How to repeat

- Fixture guard:
  ```
  cd web; export PATH=/opt/homebrew/opt/node@24/bin:$PATH
  DATA_ROOT=fixtures npm run build; echo $?
  ```
  It prints 1 and stops before `next build`.
- V5-01: open `out/en/flow/CEN--NFC/index.html` and find "−8,291.8%", or compare `pct_change` in `web/public/data/2023-24.410aa99863/sam/entries/HH.json` with `change/prior`.
- V5-02: on `/en/`, activate the GDP badge.
- RBI: run `grep -rIl rbi.org.in web/out`. It returns no files.

## Round 2 (re-verification)

Re-verifier for V5, 2026-10-02. I built nothing in Phase 3 and did not take part in the fixes. Branch `phase3-map`, uncommitted fixer and integrator changes, real export `2023-24.8b1b533fd6`. I built the site through the build lock (`with-lock.mjs --lock build`) and copied `out/` inside the same lock, so the copy is exactly the build of the current tree. All browser checks ran against that copy (Chromium, 1280×800, 375×812 and 320×640), served with the repo's own `serve-out` config. I edited no builder-owned file and committed nothing.

### Verdict

**Both high findings are closed, and all six medium findings are closed.** From V5's side, Checkpoint C is no longer blocked. Five low findings are still open and one is partly fixed. I found three new low findings and no regressions.

### High and medium findings

| id | sev | round 2 | evidence |
|---|---|---|---|
| V5-01 | high | **closed** | `pct_change` is now a fraction in the real export: `sam_export.py:263` divides the log's percent by 100, and the schema says "(0.05 = 5%)". Over 3,859 entries with a nonzero prior, all agree with (v − prior)/\|prior\|, and the fixture agrees too. On all 67 `/en/flow/*` pages with entries, 525 "Before → after balancing" lines were parsed: the shown % equals the move between the two shown values, with 0 mismatches. (The one difference beyond 1%, HH--CEN ₹2.21 → ₹2.08 crore, comes from rounding to two decimals.) In the live panel, `/en/?p=full&x=HH,SI&s=H_U5--K_HH` reads "₹12.00 lakh crore → ₹12.87 lakh crore (7.3%)". I checked for the same bug elsewhere: no story or summary figure with unit `pct`/`pct_gdp` has \|value\| > 1, and the only other `fmt="pct"` caller is `DataFig` on composition shares. The "−3972.4%" on `TAX--STA~neg` is cell-level text in a "why" excerpt (437 → −16,927 crore), and it is correct. |
| V5-02 | high | **closed** | `StatusBadge` has a new `single` prop. A figure with no composition or pins has no total line, and the sum-only wording became "The sum itself is not held…". The GDP card (`FirstScreen.tsx:35`) reads "Official total" and its disclosure reads only "Taken from a published official statistic." The same holds for the series value on `/en/series/F01/` and `/en/series/M01/`. The phrase "not held to a single published figure" is in no built HTML. Every non-compact caller that is an aggregate passes `composition`: FlowDetailPanel ×2, CellInfo, and HighlightList, which is compact. So no aggregate falls into `single` by default. PRDS--PROD, which is unpinned and all official, now reads "This amount adds up several entries … The sum itself is not held to a single published figure.", which is consistent. |
| V5-03 | medium | **closed** | The economic values now have `split_label`/`total_label`/`pins` in `summary.methodology`. These are `hh_factor_income`, `disc_d1`, `disc_d2`, `disc_d3`, `disc_d3_valuables`, `disc_d3_si_errors`, `judgement_band_abs` and `old_base_abs`. `disc_d4` = 0 and has no label. `limits.mdx` puts a `<SummaryBadge>` after each, and every badge on the built page equals the export. Examples: factor income ₹192.46 lakh crore "Derived total · split set by balancing"; D1 ₹5.71 "Derived total · split estimated"; D3 ₹3.59 "Estimated", with the text explaining why it has no total badge. `status.mdx` no longer says "every figure on this site". It now says the economic values carry badges and that counts, thresholds and whole-SAM totals do not. The 64 bound figures on `/en/methodology/` match that sentence: the unbadged ₹ figures are the SAM grand total, the amount moved, thresholds, the pin width and the four label sums over the whole SAM. |
| V5-04 | medium | **closed** | Each `hh_outlays.parts[*]` carries `total_label` and `pins`. `FirstScreen.tsx:58` passes them. On `/en/`, the badges read: Goods and services ₹66.8 "Official total · split estimated", Saving ₹24.0 "Official total · split set by balancing", Sent abroad "Official total · split estimated", Not allocated "Derived total · split estimated", and the other three "Set by balancing". These match the map's HH--PRDS, HH--SI, HH--ROW and HH--DISC links. At 375 px and 320 px the two-part badge stacks on two lines, no visible child overflows its row and the page width equals the viewport. |
| V5-05 | medium | **closed** | The badge panel lists each pin as a figure. DISC--ROW reads "The time series "Services import reconciliation (CIF adjustment)" (M05); the 2023-24 accounts match it (its check passes)." HH--DISC reads "Published NAS household residual; … Target ₹5.71 lakh crore; the balanced total is within ₹1.0 crore of it." SI--PRODUCERS shows the pair pins by description. Across all 160 built pages, the visible text contains no pin id: no `ts:F..`/`ts:M..` and no `<block>:<constraint>`. Residual wording is new low finding V5-17. |
| V5-06 | medium | **closed** | `sources.mdx` now says the RBI must give permission for two things, linking and caching, and republishing figures derived from its statistics. It names the RBI-derived figures the site shows and says this blocks a public launch. `issues.mdx` matches. The Bulletin's reproduction clause it cites agrees with SOURCES.md (lines 1110, 2065). There are still 0 `rbi.org.in` strings anywhere in `out/` (HTML, JS, JSON, txt). |
| V5-07 | medium | **closed** | `provisional.mdx` now has D2-7 / rest_of_world-26. It says honestly that the accepted move is **not** in the data yet: both items still sit with the RBI (U6 checked the parquet). It also covers all thirteen CHECKPOINT_B §6c items, checked one by one against `docs/phase2/CHECKPOINT_B.md:338-354`. The two proposed adjustments (ULB key, FDI payer bound) are marked as not yet in the data. |
| V5-08 | medium | **closed** | `ifpri_nexus_sam_india_2022_23_paper` has been merged into `data/registry.yaml` as verified (DECISIONS D3-3, ISSUES P3-O3), and `registry_additions/io_tables.yaml` has `sources: []`. All 32 sources in `provenance.json` are in `registry.yaml`, and their `attribution` and `licence` equal the registry's. None is `unverified`, and the methodology page shows no "unverified". The exporter's error text now names the additions (`provenance.py:109`). |

### Low findings (status only)

| id | round 2 |
|---|---|
| V5-09 | open: the F01 headline "Value in 2025-26 ₹196.18 lakh crore" still has no stage |
| V5-10 | open: `/en/flow/CEN--NFC/` still quotes "17,751 -> 3,035" next to a balanced ₹3,032 crore |
| V5-11 | open: the SVG value labels on `/en/` carry no `data-num-value` and no status |
| V5-12 | partly fixed: `limits.mdx` now calls the household residual "derived from those published figures" and PFRDA is named. The licence paragraph's permission list still omits CAG, which is on P1-9 and in `issues.mdx` |
| V5-13 | open: `loadIndex()` does not refuse fixture data. The npm guard still works: `DATA_ROOT=fixtures` exits 1, `ALLOW_FIXTURE=true` exits 1, and real data reads "OK, 26 files verified" |
| V5-14 | open: the banner still says "the {n} largest flows" (for example "the 7 largest flows" in 2004-05) |

### New findings (round 2)

| id | sev | title | owner |
|---|---|---|---|
| V5-15 | low | The per-₹100 label rule (V1-06: a share wears its part's label) is not stated on the methodology page. On the first screen, "₹66.8 · Official total · split estimated" sits next to a share of household income, a whole that has no pin. In the deficit story, "Households ₹1.4 per 100 · Official" sits next to a share whose denominator is labelled set by balancing. The story's method text and one story sentence disclose this, but `status.mdx` defines "Official" as "a published cell or total, used as it is", which a share is not. **Fix:** U6 adds one sentence to `status.mdx`: "A share per ₹100 carries the label of its own amount; the label of the whole it is divided by is in its method." | U6 |
| V5-16 | low | GDP is badged "Official total" on the first screen and series pages are badged "Official total" (`total = label` for single figures), but the methodology page's GDP badge reads "Official" (`SummaryBadge` passes `total={null}` for `{label}` items). Neither is wrong, but the same figure carries two wordings. **Fix:** U6/U3 pick one form for single published figures. | U3 / U6 |
| V5-17 | low | Some pin descriptions in the badge panel are raw pipeline text, not the plain English PLAN §3.4.2 asks for. Examples: "lies within +-Rs 1 crore (all members fixed: documentation)" and "(DECISIONS D2-3)" on HH--DISC, and "(1 SUT cell(s); 0 = no such use)" on SI--PRODUCERS. They name the right figure, and the bound target and tolerance are correct. **Fix:** orchestrator/U1 export a reader-facing `display` text per constraint, or U2 shows only the first clause. | U1 / U2 |

### Tests (V5-owned)

- `tests/verify/test_phase3_honesty.py` (new; V5 had no test file in round 1). It has 10 plain tests for the fixed findings and the round-1 checks that held: V5-01 on the export and on every flow page, V5-02, V5-03, V5-04, V5-05 on every page, V5-06, V5-07, V5-08, and no RBI links in `out/`. It also has 6 strict xfails for the open lows (V5-09 … V5-14), and each one fails for the stated reason under `--runxfail`. Result: `10 passed, 6 xfailed`.
- `web/tests/verify/v5_honesty.spec.ts` with `playwright.v5.config.ts` (output `web/test-results/v5`). It covers the client-rendered states: V5-01 (live panel, 7.3%), V5-02 (GDP and series disclosures), V5-03, V5-04 (per-part labels against `summary.json`) and V5-05 (pin text, no ids). V5-09 and V5-14 are `test.fail`. Result: 14 passed on desktop and phone. `tsc --noEmit` and eslint pass on the new files, and `ruff` is clean.
- Other checks I ran: `uv run pytest tests/export` (99 passed), `vitest run` (523 passed). Flow-page headline `data-status-total` equals `pinned.json` on all 80 flow pages (0 mismatches).

### How to repeat

```
export PATH=/opt/homebrew/opt/node@24/bin:$PATH
npm --prefix web run build
uv run pytest tests/verify/test_phase3_honesty.py -q
cd web && npx playwright test -c tests/verify/playwright.v5.config.ts
```
