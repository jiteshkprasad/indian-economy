# V1 Data fidelity: verification report (Phase 3, the Map)

Verifier: V1 (data fidelity). I built none of Phase 3. Date: 2026-10-02. Branch `phase3-map` at `f8481bc`. Real export: `web/public/data/2023-24.410aa99863`. Site built with `npm --prefix web run build`, which goes through the build lock, and served from `web/out/`.

## What I did

I recomputed the numbers from the Parquet files with DuckDB. No `pipeline` code was imported. The account hierarchy was re-typed from the PLAN §3.2 table. The curated YAML files were read as data:
- explanation items;
- judgement bands;
- old-base scope;
- link policy;
- story specs;
- `flows.yaml` account sets.

The display formatter was rewritten in Python from PLAN §3.3. It rounds half away from zero on the exact binary value, and it reproduces all of `golden/format_cases.json`.

I then compared three things with the export and the rendered site:
- the 80 flow pages, the 69 series pages and the methodology page, read from static HTML;
- 30 seeded panel states and all story figures, rendered by Playwright in Chromium;
- the 13×13 matrix table on `/en/data/`.

The checks are code:

| File | What it holds |
|---|---|
| `tests/verify/test_phase3_data_fidelity.py` | 25 pass and 7 strict xfails, one for each confirmed defect, in about 2 s. `uv run python tests/verify/test_phase3_data_fidelity.py` regenerates the Playwright expectations. |
| `web/tests/verify/v1_fidelity.spec.ts` with `playwright.v1.config.ts` | 33 tests, all pass. One is marked `test.fail` for V1-05. Run with `npx playwright test -c tests/verify/playwright.v1.config.ts`. The output folder is `web/test-results-v1/`. |
| `web/tests/verify/panel_states.json` | The 30 panel states, chosen with seed 20261002. |
| `web/tests/verify/story_expect.json` | The expected text and labels for every story figure. |

Each xfail fails for the stated reason (checked with `--runxfail`). When a defect is fixed, its xfail turns into an XPASS failure and must be removed.

## Summary

| Severity | Count | IDs |
|---|---|---|
| High | 5 | V1-01, V1-02, V1-03, V1-04, V1-05 |
| Medium | 4 | V1-06, V1-07, V1-08, V1-11 |
| Low | 3 | V1-09, V1-10, V1-12 |

The data layer is sound. I found no wrong number in the export: every cell, aggregate, label, pin, flag, series value and story figure agrees with my recomputation. The problems are all in how the site shows correct data:
- a unit mix-up in the entry list (V1-01);
- sign errors in the trend chart (V1-02) and in the deficit story's wording (V1-04);
- a node panel that measures the wrong node in the simple view (V1-05);
- total labels missing on the first screen (V1-03).

V5 and V2 found V1-01 and V1-04 independently (V5-01, V2-01).

---

## Findings

### V1-01 (high): "before → after" percentages in every entry list are 100 times too large
- **What happens:** for real data, `entries/*.json` `pct_change` is in **percent**. It is copied from `balancing_log.pct_change` without conversion: `pipeline/export/sam_export.py:244` and `:262`. The panel formats it as a **fraction**: `web/src/components/map/FlowDetailPanel.tsx:416-419` uses `<Num value={e.pct_change} fmt="pct" />`. The fixture computes a fraction (`pipeline/export/fixture.py:140`), so tests on the fixture could not catch it. The schema does not state the unit.
- **Evidence:** 2,692 entries disagree with (v − prior)/|prior|. On screen:
  - `/en/flow/HH--PRDS/`: "₹4.15 lakh crore → ₹4.15 lakh crore (−4.4%)". The real move is −0.044%.
  - `TAX--CEN~neg`: "−₹2.65 lakh crore → −₹2.31 lakh crore (1,298.9%)". The real move is 12.99%.
  - `FACT--HH`: "₹14.36 → ₹14.46 lakh crore (67.8%)". The real move is 0.68%.
  - The test `test_entry_pct_change_is_a_fraction` (xfail) shows this.
- **Owner:** U1. The export should match the fixture and the formatter: `pct_change / 100`. The unit should also be written into `entries.schema.json`. U3 needs no change once the data is fixed.

### V1-02 (high): trend charts plot the SAM 2023-24 point with the wrong sign for subsidies
- **What happens:** the series line is plotted from `share`, which already includes `display_sign`. The SAM point is `sam_value / GDP` with no `display_sign`:
  - `web/src/components/map/FlowDetailPanel.tsx:540` and `:676`;
  - drawn in `web/src/components/map/TrendChart.tsx:142-157`;
  - in ₹ mode, `sam.value` is not multiplied by the sign either.
- **Evidence:** `/en/series/F13/` (product subsidies) and the `PRDS--TAX~neg` panel both show the series at +2.0% of GDP, the axis running from 3.2% down to −2.0%, and "SAM 2023-24: −2.0%". So a check that passes (series 5.76 = SAM 5.76 lakh crore) looks like a 4-point gap. F30 (fertiliser subsidy) has the same problem. The test `test_trend_sam_point_uses_display_sign` (xfail) shows this.
- **Owner:** U3. Use `sam_value × display_sign` for both the share and the ₹ value of the point. The "SAM 2023-24" caption needs the same fix.

### V1-03 (high): first-screen household figures hide their official totals
- **What happens:** `FirstScreen.tsx:56` passes `total={null}` for every part of "Of every ₹100 households pay out". `summary.json` `headline.hh_outlays.parts` carries only `split_label`, with no total label (`pipeline/export/summary.py:52-80`). So the first screen shows:
  - "Goods and services ₹66.8 **Estimated**", although PFCE is pinned official (`HH--PRDS` is pinned to `households:hh.c1.total`; F01 passes);
  - "Saving ₹24.0 **Set by balancing**", although household saving is pinned official (`HH--SI`, NAS 1.9; F35 passes). Only the split across the 10 groups moved.
- **Why it matters:** PLAN §4.0 asks for "Official total · split estimated" where that is what the data says. As it stands, the most prominent figure on the site says household saving was set by balancing.
- **Evidence:** the test `test_first_screen_total_labels` (xfail). My independent cover check gives `official` for both `HH--PRDS` and `HH--SI`.
- **Owner:**
  - U1: add `total_label` and `pins` per part (the pinned total of that HH→group link);
  - U3: render `StatusBadge total=…`.

### V1-04 (high): the deficit story calls net lending "net borrowing", which flips the sign
- **What happens:** `nl_cen`, `nl_sta` and `nl_gg` are net *lending* (non-financial receipts − payments; −₹11.47, −₹5.84 and −₹17.31 lakh crore). The caption and prose call them net borrowing:
  - `web/messages/en/story.json:63`: "Net borrowing (national accounts), 2023-24";
  - `web/content/en/stories/deficit-funding.mdx:27`: "Net borrowing by the Centre was −3.9% of GDP …".
- **Why it matters:** a negative net borrowing means net lending, so the story's central figure reads the wrong way round.
- **Evidence:** the test `test_deficit_story_net_borrowing_sign` (xfail). V2-01 found the same.
- **Owner:** U5. Either label the figures "net lending (+) / net borrowing (−)", or add `nb_*` figures (kind `difference` with a and b swapped) and show positive net borrowing.

### V1-05 (high): the Saving-and-investment node panel in the simple view shows the wrong total
- **What happens:** in the simple preset the drawn SI node is SI ∪ FINM: ₹104.58 lakh crore, 36.0% of GDP, and the home page card agrees. Selecting it (`/en/?s=SI`) opens a panel showing **₹249.97 lakh crore, 86.0% of GDP**, which is the full-preset SI node. Its money-in and money-out lists also treat FINM as an outside partner.
- **Cause:** `web/src/lib/sankey/select.ts:13-30` `nodeAccounts()` finds the hierarchy node `SI` before it looks at the preset merges, so the preset is ignored. The same function is used for link endpoints (`resolveLink`). For the current data, simple-view links into or out of SI happen to equal the full-view ones (I checked all 80 permalinks), so this risk is latent there. The phone view opens the same panel.
- **Evidence:** the Playwright state "node SI (simple)" (marked `test.fail`) gets 24997045.3 where 10457892.46 is expected.
- **Owner:** U3. Resolve the node's accounts with the active preset (`presets[preset].merges[id]` first). Link ids that mean different things in the two presets (`HH--SI`, `SI--PRODUCERS`, `CEN--SI~neg`) should be resolved the same way.

### V1-06 (medium): the same figure gets different labels in different places, and per-100 badges contradict the prose
- **What happens:** per-100 figures take the least certain label of the part and the whole. When the whole is "set by balancing", every share inherits that label:
  - Consumption per ₹100 of household outlays reads "**Estimated**" on the first screen and "**Set by balancing**" in `remittance-dubai` step 4. The figure is the same.
  - Deficit story step 5: "Households bought only ₹1.4 **Set by balancing** directly", followed a few lines later by "the households' direct purchases are a published figure". `gsec_hh` is official; the badge comes from `gsec_issued`.
- **Owner:**
  - U1/U5: decide one rule for shares, for example labelling a per-100 by its part, with the denominator's label in the composition popover;
  - U3/U5: make the first screen and the story use it.

### V1-07 (medium): a cited source is not in `data/registry.yaml`
- **What happens:** `ifpri_nexus_sam_india_2022_23_paper` is cited by 28 cites in `provenance.json` (IFPRI income gradients, D2-19). It exists only in `data/registry_additions/io_tables.yaml`, which is unverified. PLAN §3.1 says the exporter fails on a source missing from the registry, and §5.1 item 3 says every source id is in `registry.yaml`. The exporter accepts the additions file instead.
- **Evidence:** the test `test_every_cited_source_in_registry` (xfail). 3 of my 50 sampled cites hit this source; the other 47 were fully correct.
- **Owner:** the orchestrator, who owns `data/registry.yaml`: verify and merge the entry. U1 should make the exporter's check match the PLAN, or the PLAN should state the exception.

### V1-08 (medium): published single figures are labelled "not held to a single published figure"
- **What happens:**
  - The GDP card (`FirstScreen.tsx:34`) shows "Official · Taken from a published official statistic. **The total is not held to a single published figure.**"
  - Every series panel and series page shows the same line for published series values (`FlowDetailPanel.tsx:678-690`; the `/en/series/F01/` header). The cause is `total={null}`.
  - The story evaluator gives `ts_value` figures `total = status` (PLAN §3.8). So the same F43 2023-24 value reads "Official total" in the remittance story and "not held to a single published figure" on its series page.
- **Evidence:** the test `test_published_single_figures_not_called_unpinned` (xfail).
- **Owner:** U3. Pass `total = summary.gdp.label` for GDP, and `total = status` for a single published series value. U2 could also stop showing `noTotal` text when the split is official and the figure has no parts.

### V1-11 (medium): "₹70.4 of every ₹100 of GST ended up with the States" counts money the States pay straight back
- **What happens:** `gst_to_states_all` = SGST + devolved CGST + `cess_passed`. `cess_passed` includes the ₹78,104 crore cess-loan transfer. The same story shows that this transfer is used to repay the GST back-to-back loans (`b2b_repaid` −₹78,104 crore, K8e). It passes through the States; it does not stay there. Without it the figure is ₹66.1.
- **Owner:** U5, with a V2 opinion. Use "is paid to the States" rather than "ended up with", or exclude the loan-recovery part and show it separately.

### V1-09 (low): F24 is listed inside Government although part of it sits in Saving and investment
- **What happens:** `ts/view.json` `internal.GOV` lists F24 (grants to States). Its SAM terms include R2k capital grants, K_GSTA ← K_GCEN, which lie inside SI, not GOV. Under PLAN §3.7.3 rule 1 it is neither a ribbon nor internal to one node; it belongs in the general list.
- **Evidence:** the test `test_ts_internal_lists_one_node` (xfail).
- **Owner:** U1 (the internal-list rule in the ts_view export).

### V1-10 (low): rounded shares do not add up, and no note says so
- **Where it shows:**
  - GST split: ₹46.9 + ₹45.1 + ₹8.1 = **100.1**.
  - "Who pays at the till": 99.9.
  - Government spending per ₹100: 99.9.
  - Centre's debts: ₹11.71 + ₹4.35 lakh crore + ₹6,468 crore = 16.12 against a total of **16.13**.
  - States' assets: ₹2.53 − ₹1.80 lakh crore + ₹50,837 crore = 1.24 against **1.25**.
- **Cause:** each value is correct and rounded on its own (half away from zero). No hidden drift was found beyond display rounding.
- **Owner:** U5. Add "may not add up because of rounding" under these tables, or use largest-remainder rounding for per-100 sets.

### V1-12 (low): the product-subsidy link shows "Derived total · split official"
- **What happens:** `PRDS--TAX~neg` (and `PRODUCERS--TAX~neg`) is pinned only by `ts:F13`. The F13 2023-24 row is `derived` because it is the NAS "Less subsidies" line × −1. The total therefore reads as less certain than its parts, which are all official SUT cells. This follows the §3.4.2 rule, but the label is odd.
- **Owner:** U1. Either treat a pure sign flip of an official line as official, or prefer a constraint pin of equal coverage.

---

## What I checked and found correct

### Cells
All 2,169 non-zero cells after rounding to 2 dp, with the parquet's 2,203 rows as the source:
- the value of each cell, and 66 negative cells;
- row and column balance of the exported cells (within 0.06 crore);
- the entries summing to their cells (within 2e-6).

### Hierarchy
- Every L0 and L1 group matches the PLAN §3.2 table.
- There are 168 nodes and 27 L1 groups.
- The `ts_nodes` and the simple preset merges are right.

### Level-0 aggregates
- 70 links (61 positive, 9 negative) over 62 external pairs, and 4 internal pairs (PRDS 79.20, NFC 2.56, FC 4.29, SI 7.28).
- Every negative part matches PLAN §3.2: −5.76, −2.71, −3.63, −2.86, −4.27, −8.55, −1.45 and −0.26, plus the ₹0.1 crore PROD→PRDS cell.
- All 13 node heights match: PRDS 677.82 … DISC 5.71. Inflow equals outflow for every node.

### Simple preset and level 1
- The simple preset has 61 links (37 forward with 1,199.12, 8 same-column with 73.84, 16 return with 46.90 lakh crore).
- Simple node heights: PRODUCERS 369.09, SI 104.58.
- Internal flows: PRODUCERS 966.43; SI 288.06 positive and −10.00 negative.
- Level 1 has 364 directed pairs (358 external, 6 internal), 32 with negative parts, 21 of them net negative.

### Rendered link values
- **All 80 `/en/flow/*` permalinks:** each headline value equals my aggregate (both presets agree where ids repeat) and each share of GDP is right. Every `data-num-value` text equals my formatter, apart from the V1-01 numbers, whose input is wrong.
- **Matrix:** the `/en/data/` 13×13 table equals the signed level-0 block sums, cell by cell.

### GDP and summary
- **GDP:** `summary.gdp` = M01 2023-24, base 2022-23, published (₹2,90,73,286.73 crore, same prov). The SAM's production-side GDP differs from it by 0.69 crore.
- **Headline:** the household outlays total (245.74) and its 7 parts and per-100 values equal the HH column by receiver group.
- **Labels and counts:**
  - label counts and absolute values: 1,127 / 114 / 2,180 / 472 entries; 1,261.66 / 223.94 / 802.71 / 389.81 lakh crore;
  - composition, moved_abs (28.38 lakh crore) and grand total.
- **Methodology figures:** judgement-band and old-base entries and values, assumption dependents (23, of which 6 direct), constraint and binding counts (429, 174), explanation counts, D1 to D4, and the time-series flag counts.

### Time series
- **Main series:**
  - all 1,937 main values follow the §3.7.1 base rule, with no ties;
  - base, status, stage ("n.a." becomes null), flags, segment and prov all match;
  - every share uses same-base GDP and `display_sign` (within 1.5e-6);
  - linked series exist for exactly the 10 linked flows, with M01 linked GDP;
  - the F29 and F52 alternative series match;
  - the GDP block matches;
  - every one of the 42 base_change, concept_break and segment_join flags has a marker;
  - all 69 SAM checks are copied exactly.
- **Series pages:** every number on the 69 series pages is a value × display_sign or a share, and is formatted correctly.

### Top-flows board
- **Ribbon rules:** all 16 ribbons satisfy rules 1 to 5, checked with my own re-implementation of eval_sam:
  - no SAM entry is shared between ribbons (no double counting);
  - the reversible flows are M10 (8 years), F32 (14 years) and F49 (2002-03, 2003-04, 2020-21);
  - every flow with a negative year is marked reversible.
- **Coverage and slots:** coverage per year and `slot_share` equal my recomputation.
- **Rendered board:** the 2020-21 and 1950-51 boards show correct signs and texts: Government gross saving −6.7%, current-account surplus −1.0%.

### Entries, labels and flags
- **All 3,893 entries:**
  - the §3.4.1 label, re-implemented with my own explanation-item matching (223 entry items: 151/64/8; 103 cell items: 73/26/4);
  - the verdict;
  - all 7 flags, including the 97 judgement-band members, the 36 old-base entries and an independent depends-on-assumption walk;
  - the binding lists;
  - the level-0 file.
- **Cells:** abs_o/d/e/b, the headline split, the flag bitmask, n_entries and the order of refs match for every cell.

### Pinned totals
- I recomputed pins independently: tight equal or band constraints with official or derived prov, plus passing series, with an exact-cover search.
- All 270 keys in `pinned.json` reproduce.
- No unlisted L0, simple or L1 link (positive, negative or pair) can be pinned.
- 16 of 62 L0 pairs are pinned as whole pairs. HH→PRDS, ROW→HH and HH→SI are official; NFC→SI is not pinned.

### Provenance
- **Records:** for all 516 exported records, an independent walk through SAM, time-series and clean provenance (2,340 records, no duplicates, none unresolved) reproduces:
  - the cite sources;
  - the URLs (one per table);
  - the withheld flags;
  - assumption and depends-on-assumption, and status.
- **RBI links:** no RBI URL appears anywhere in the exported JSON.
- **Attribution:** matches `registry.yaml` for every registered source.
- **Sample:** 50 seeded cites checked against the clean records (URL, table, retrieval date range, registry): 47 correct, 3 failed by V1-07.

### Stories
- **Figures:** all 183 story figures recomputed with my own evaluator: value, split, total, flags and composition all match. This includes:
  - satellite_share rescaling (the parts add up to the CGST, SGST and cess totals within ₹0.01 crore);
  - prorata imports and margins;
  - net lending = assets − liabilities (Centre −11.47, States −5.84);
  - every `check_equals`.
- **PLAN §4.9 orientation figures:** 8.62, 8.29 and 1.49 lakh crore; UTGST 5,772; compensation grants 44,946; cess loan 78,104; current outlays 57.26; capital outlays 14.14; financial assets 5.91; remittances 9.83; UAE 1,89,139; G-secs 11.71 and 6.65.
- **Rendered stories:** every `[data-fig-id]` in all three stories reads my formatted value, with the expected split and total labels, in both the static HTML and Chromium.

### Panel states
- 30 seeded panel states: 8 L0 full, 6 simple, 8 L1, 5 L2 (mixed zoom), and 3 nodes.
- 29 match my value, share text, total label and split label.
- The 30th is V1-05.
- All 909 numbers Playwright read from the panels and stories are formatted as my formatter does.

## Not checked or out of scope
- `tests/raw`, the Phase 1/2 spot checks and `tests/live`: the raw files are not on this machine.
- WebKit, Firefox and the phone viewport (V3, V4).
- Text and economics beyond what bears on numbers and signs (V2).
- The judgement-band and old-base lists themselves; I checked only their application.

---

## Round 2 (re-verification)

Re-verifier: V1 (data fidelity), independent of the fixers and the integrator. Date: 2026-10-02. Branch `phase3-map`, working tree on top of `1c35ac2` (nothing committed). Real export `web/public/data/2023-24.8b1b533fd6` (`tests/export/test_export_current.py` passes, so the export matches the current code and inputs). Site built through the build lock (`npm --prefix web run build`) and read from `web/out/`. Playwright output folder: `web/test-results-v1/`.

### Result

| ID | Severity | Round 2 | Evidence |
|---|---|---|---|
| V1-01 | High | **Closed** | All 3,859 exported `pct_change` values equal (value − prior)/\|prior\| from the unrounded parquet (worst gap 2.0e-5; the 34 nulls are entries that did not move or had a zero prior). On the static flow pages, all 525 "before → after (x%)" numbers are moves of that link's own entries. In Chromium, 161 entry moves across 27 panel states match too. `/en/flow/FACT--HH/` now reads 0.7% (it read 67.8%). The fixture and the schema state the unit. |
| V1-02 | High | **Closed** | On all 66 series pages that draw a chart with a SAM check, the "SAM 2023-24" caption equals `fmt(sam_value × display_sign / GDP)`, and every chart label has the line's sign. F13 reads 2.0% and F30 reads 0.71%, both positive. F25 and F27 have only two points, are shown as values and have no SAM point. |
| V1-03 | High | **Closed** | The first-screen card is now titled "Each ₹100 of household income" (V2-07). Each of its 7 parts shows the total label and pins from my own exact-cover search, and the split label from my own composition, in summary.json and on the page. Consumption reads "Official total · split estimated", saving "Official total · split set by balancing", sent abroad "Official total · split estimated" and not allocated "Derived total · split estimated". The other three show only their split. |
| V1-04 | High | **Closed** | The story now shows `nb_*` = liabilities − financial assets: Centre ₹11.47, States ₹5.84 and general government ₹17.31 lakh crore. The sentence reads "Net borrowing by the Centre came to 3.9% of GDP". There is no negative net borrowing anywhere in the story. My evaluator reproduces every `nb_*` figure and its `check_equals`. |
| V1-05 | High | **Closed** | The `test.fail` mark is removed and the state passes: SI in the simple view shows ₹104.58 lakh crore. I added a guard for every top-level node in both presets (24 panels): each panel equals the drawn height from my own aggregation. A probe of the top-flows board (ts scope) shows GOV ₹66.98 lakh crore with ₹69.98 internal, and SI ₹104.58, both equal to my TSN aggregation. |
| V1-06 | Medium | **Closed** | The rule is adopted: a per-100 share takes its part's split, total, flags and composition, and its method states the whole's label. My evaluator now follows that rule, and all 187 story figures match on value, labels, flags and composition. The remittance story's 7 household shares carry exactly the first-screen labels. `gsec_hh_per100` reads "Official", and the deficit sentence no longer contradicts its badge. |
| V1-07 | Medium | **Closed** | `ifpri_nexus_sam_india_2022_23_paper` is merged into `data/registry.yaml` as verified (DECISIONS D3-3). Every cited source is in `registry.yaml` itself. Every exported `registry_status` equals the registry's `verification.status`; the test is strengthened to check this. The residue is a wording difference, logged as R2-a below. |
| V1-08 | Medium | **Closed** | The GDP card reads "Official total · Taken from a published official statistic". None of the 69 series pages carries the "not held to a single published figure" line. The line remains only on sums of entries without a pin: 56 flow pages and the data page's "Flows inside Goods & services". There it is true. |
| V1-11 | Medium | **Closed** | "Ended up with the States" now binds `gst_to_states_kept_per100` = SGST + devolved CGST + compensation grants = ₹66.1. The cess-loan pass-through is shown separately: "₹4.2 … passed straight through and did not stay with them". My evaluator reproduces both. |
| V1-09 | Low | Open | F24 is still listed as internal to GOV (strict xfail kept). |
| V1-10 | Low | Open | Rounded per-100 sets still carry no "may not add up" note. |
| V1-12 | Low | Open | `PRDS--TAX~neg` is still "Derived total" (pin `ts:F13`). |

### Regressions looked for
- **Methodology figures** (new labels from V2-02 and V5-03): `hh_factor_income`, `disc_d1`…`disc_d3_si_errors`, `judgement_band_abs` and `old_base_abs` carry labels and pins.
  - I recomputed those labels and pins with my own composition and exact-cover search, and they match.
  - `disc_d3` (₹3,58,633.93 crore) equals the NAS derived S-I errors and omissions for 2023-24 in `mospi_nas_2026_derived_residuals.parquet`.
  - Every `<DataFig>` on the methodology pages (64) shows its summary value with my formatter.
  - Each labelled item is followed by a badge with its own labels. I mutation-checked this test, and it catches a wrong label.
- **Story YAML changes:** the new `nb_*`, `gst_to_states_kept*`, `cess_loan_per100_gst`, `gg_subsidies_*` and `assets_cen_k9_net` figures all match my evaluator.
  - The test change behind `gg_subsidies_paid` was in my own evaluator: it had ignored `coef` in `sum` terms.
  - All rendered `[data-fig-id]` texts and labels match, both in static HTML and in Chromium.
- **Other pages:** 80 flow pages, 69 series pages, the 13×13 matrix, the 30 seeded panel states and all story pages pass unchanged. All numbers Playwright observed are formatted as my formatter does.

### New observations (low)
- **R2-a:** the exporter still accepts a source that is only in `data/registry_additions/`, exporting it as `unverified`. PLAN §5.1 item 3 says every source id must be in `registry.yaml`. Today no cited source is in that position, and my test fails if one appears. The PLAN, which the orchestrator owns, should either state the exception or the check should be made strict.
- **R2-b:** the per-100 label rule (V1-06) is written only in `pipeline/export/stories.py` and in each figure's method text.
  - PLAN §3.8 (line 524) still lists only ratio, product and difference, and does not cover per100.
  - The methodology page "What the labels mean" does not tell readers that a share's badge describes its part, not the share. So "₹24.0 Official total" on the first screen could be read as a published share; the whole, household income, is set by balancing.
  - Suggested fix: one sentence in `status.mdx`, and a line in PLAN §3.8.

### Test files (round 2)
- `tests/verify/test_phase3_data_fidelity.py`: 34 pass and 1 strict xfail (V1-09).
  - The xfails for V1-01, -02, -03, -04, -07 and -08 are removed, and those tests now assert the fix:
    - V1-01 is checked against the parquet.
    - V1-02 covers all series.
    - V1-03 compares labels with my own cover search.
    - V1-04 requires the positive figures.
    - V1-08 covers all series pages.
  - The story evaluator follows the per100 rule and honours `coef`. The identities use `nb_*`, and the series-page check uses the signed SAM point.
  - New tests:
    - `test_share_labels_agree_between_first_screen_and_story` (V1-06);
    - `test_flow_pages_entry_moves` (V1-01 on static pages);
    - `test_methodology_pages_bound_figures`;
    - methodology label checks inside `test_methodology_figures`.
- `web/tests/verify/v1_fidelity.spec.ts`: 57 pass, with no `test.fail`.
  - The V1-05 mark is removed.
  - Each link panel's entry moves are checked against that link's parquet moves.
  - 24 all-node states were added.
- `web/tests/verify/panel_states.json` and `story_expect.json` were regenerated: moves were added, and there is a `nodes` list.
