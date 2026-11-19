# V3 verification: accessibility, mobile, theme

Verifier V3, 2026-10-02, branch `phase3-map`, real export `2023-24.410aa99863` (not the fixture).
I did not build any of this. Scope per PLAN §7 row V3: axe results reviewed (not just counted), a manual keyboard walk-through of the map (§4.5.10), the phone view, matrix, stories and slider, screen-reader semantics, composited contrast in both themes, the first screen at 375 px, reduced motion, and WCAG 2.2 criteria 2.4.11, 2.5.7 and 2.5.8.

## Summary for the owner

The site is in good shape on the automated checks: axe finds **no WCAG A/AA violations** on any page, in light or dark, on desktop or phone. Colour contrast is good everywhere I measured. The phone layout never scrolls sideways, and the story and matrix keyboard models work.

Hands-on testing found **three accessibility failures that axe cannot see**. Each one breaks a WCAG 2.2 AA rule, so each is rated high:

1. **Keyboard users lose their place when they zoom the map.** Pressing `+` or `−` on a group sends keyboard focus to the top of the page.
2. **Several buttons show no focus outline at all.** This hits the "Complete picture / Top flows" and "Simple / Full map" toggles, the "Share of GDP / ₹ crore" toggle and the phone group cards.
3. **On desktop, a group can only be picked by clicking a bar about 16 px wide**, sometimes only 4 to 6 px tall. The test suite excuses the diagram from the target-size rule because a table offers the same choices. That is true for flows but not for groups.

There are also medium problems:
- When Play stops at the last year, the screen-reader announcement names the wrong year.
- The slider's break marks are drawn in the wrong place.
- The story's Next button drops off the screen after you press it.
- The diagram's labels shrink to 6 to 9 px in common views, and some overlap.

Each finding has a fix and the unit that owns it. Six of them are also coded as Playwright tests (`web/tests/verify/v3_a11y.spec.ts`). They fail today and should pass once the fixes land.

Screenshots for the Checkpoint C report are in `docs/phase3/screenshots/` (see the end of this file).

## How I tested

- Built with `npm run build` (under the build lock), copied `web/out/` to my scratchpad and served the copy with the project's own `serve-out` config (the `vercel.json` headers and redirects). Other verifiers' rebuilds could not change what I tested. Node 24.21.0, Playwright 1.63, Chromium 1243 and WebKit 2359. Firefox cannot launch on this host, so it was not tested.
- **axe**: `@axe-core/playwright` with `wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa` **plus `best-practice`**, and **without** the `[data-mark]` exclusion. 21 URLs (home, five map states, the full preset, the top-flows view, the story index, three stories, data, methodology, three flow pages including a `~neg` one, three series pages, 404) × 2 viewports (1280×800 and 375×812) × 2 colour schemes = 84 scans. I read every violation and every "incomplete" (needs review) node.
- Keyboard walk-throughs scripted in Chromium and WebKit (Tab order, roving focus, the focused element and its geometry after each key), plus screenshots of focus states.
- Accessibility tree checks (Playwright `ariaSnapshot` and Chromium CDP `Accessibility.getFullAXTree`).
- Contrast: computed from `styles/tokens.css` with the WCAG formula, compositing each kind colour at the opacities exported by `lib/sankey/style.ts` (0.55, 0.35, 0.12) over `--bg` and `--surface`, in both themes.
- Reflow at 320 px, the WCAG 1.4.12 text-spacing override, target sizes on 10 routes × 2 viewports, theme toggle versus OS scheme in both directions, and Play/pause with `page.clock`.

## Findings

Severity follows the brief: high = WCAG AA failure (or a wrong number, broken route, or failing test); medium = real but contained; low = polish. Owners are per PLAN §6.2.

### V3-01 (high): keyboard focus is lost when a map group is expanded or collapsed

- **Evidence.**
  - On `/en/`, I focused Households in the diagram and pressed `+`. The URL became `?x=HH` and `document.activeElement` became `<body>`. The next keys (`L`, `↓`, `Enter`) did nothing.
  - The same happens with `−`: on `/en/?x=HH`, I focused "Rural households" and pressed `−`. The URL became `?p=full` and focus went to `<body>`.
  - Reproduced in Chromium and WebKit.
  - A keyboard user has to Tab back in from the top of the page (about 25 stops) after every zoom step, and gets no announcement of what changed.
  - WCAG 2.4.3 Focus Order (A), and the PLAN §4.5.10 keyboard model.
  - `tests/e2e/map.spec.ts:73-80` hides the bug: after pressing `+` it calls `.focus()` on another node before pressing `L`.
- **Where.**
  - `web/src/components/map/SankeySvg.tsx:102-106`: the `+`/`−` handlers call `onExpand`/`onCollapse`. The focused node's key then leaves the layout, and nothing moves focus to its replacement.
  - The roving `focus` state at `SankeySvg.tsx:63,71` is keyed on node keys that no longer exist.
- **Owner.** U3.
- **Fix.**
  - When `+` is pressed, record a pending focus target: the expanded node's first child in hierarchy order. In `simple`, also map the old keys to their `full` equivalents. When `−` is pressed, the target is the parent.
  - In a `useLayoutEffect` keyed on the layout, focus `refs.current.get("n:"+target)` and set the roving state to it.
  - Announce the change through `LiveRegion`, e.g. "Households opened: Rural households, Urban households".
  - Change `map.spec.ts` to assert focus right after `+`/`−` without re-focusing.
- **Test.** `web/tests/verify/v3_a11y.spec.ts` "V3-01" (fails today).

### V3-02 (high): some buttons show no focus indicator because `overflow: hidden` clips the outline

- **Evidence.**
  - The global `:focus-visible` rule draws `outline: 2px` with `outline-offset: 2px`. That ring sits outside the button's box, and the parent's `overflow: hidden` clips it.
  - Keyboard focus is invisible on:
    - "Complete picture (2023-24)" and "Simple": nothing at all is visible;
    - "Top flows over time" and "Full map": only a 1 px sliver shows between the buttons;
    - the "Share of GDP / ₹ crore" toggle in the detail panel and on every flow and series page;
    - every phone group card ("Households ₹245.74 lakh crore…"). Screenshotted after a real Tab, the focused card looks exactly like an unfocused one.
  - The phone view is also what desktop users get at 200% zoom or more (below 640 CSS px). So the people most likely to need a focus ring lose it.
  - WCAG 2.4.7 Focus Visible (AA).
- **Where.**
  - `web/src/components/map/map.module.css:101-106` (`.segmented { overflow: hidden }`) and `:354-359` (`.card { overflow: hidden }`).
  - Used at `MapApp.tsx:156` and `:170`, `TrendChart.tsx:105`, and `MapMobile.tsx:72-75` (`.cardHead`).
- **Owner.** U3.
- **Fix.** Either:
  - draw the ring inside: `.segmented button:focus-visible, .cardHead:focus-visible { outline-offset: -4px; }` and, for the pressed (accent-filled) state, add `box-shadow: inset 0 0 0 2px var(--focus-halo)` so the ring stays 3:1 against `--accent`; or
  - remove `overflow: hidden` and round the first and last buttons instead.

  Add a check to `theme.spec.ts` or `mobile.spec.ts` that the focused element's outline box is not clipped by an ancestor.
- **Test.** "V3-02", desktop and phone (both fail today).

### V3-03 (high): on desktop, group (node) marks fail 2.5.8 target size, and the "equivalent control" exception does not cover them

- **Evidence.**
  - Node marks render 16.6 px wide at 1280 px. They are 12.3 px wide in the full map and 11.0 px with the panel open.
  - Discrepancies is 16.6×6.1 px (11×4 with the panel open).
  - Ribbon hit areas start right at the node's edge, so the 24 px spacing circle always overlaps another target.
  - `a11y.spec.ts:6-17` (and PLAN §4.5.10) exclude all of `[data-mark]` from axe's `target-size` rule. The reason given is that "the same function is always available on the same page through the list/table alternative". **That holds for links only.** "View as table" (`LinkTable.tsx`) lists flows with ≥ 24 px buttons, but at ≥ 640 px nothing outside the diagram lets a pointer user open a group's panel or reach its "Show its parts" button.
  - The `MapMobile` cards that would serve this purpose are `display: none` above 640 px.
  - WCAG 2.5.8 Target Size (Minimum) (AA).
- **Where.**
  - `web/src/components/map/SankeySvg.tsx:217-251`: the node `<g>`/`<rect>`, whose hit area is the rect alone because the label has `pointer-events: none`.
  - `web/src/lib/sankey/style.ts:34`: `nodeWidth: 16`.
  - The justification comment in `web/tests/e2e/a11y.spec.ts:6-17` and `mobile.spec.ts:5-8` (U2).
- **Owner.** U3 (fix), U2 (narrow the axe exclusion to `[data-mark="link"]` once nodes comply).
- **Fix.** Either:
  - draw a transparent hit rect for every node at least 24×24 CSS px (pad to `max(24/scale, w)` wide and `max(24/scale, h)` tall, centred, on top of the ribbon ends); or
  - add a list of groups (buttons that select the node) to the "View as table" panel on desktop.

  Then narrow the axe exclusion.
- **Test.** "V3-03" (fails today).

### V3-04 (medium): when Play reaches the last year, the screen-reader announcement names the previous year

- **Evidence.**
  - With `page.clock`, I started Play from 2021-22. When it reached 2025-26 and stopped by itself, the slider showed `aria-valuetext="2025-26"`, but the live region said **"2024-25: 56 of 69 flows have data"**. The correct text is "2025-26: 18 of 69 flows have data".
  - Pausing by hand announces the right year.
  - Play correctly makes no announcement on each tick.
- **Where.** `web/src/components/map/YearSlider.tsx:50-55` and `:76`. The interval calls `stop()` straight after `p.onChange(...)`, and `stop()` announces `idxRef.current`, which is only updated in a later effect.
- **Owner.** U3.
- **Fix.** `const stop = (i = idxRef.current) => { …; announce(i); }`, and call `stop(i)` inside the interval.
- **Test.** "V3-04" (fails today).

### V3-05 (medium): the slider's break markers and the "complete map" mark sit in the wrong place

- **Evidence.**
  - The tick row is positioned as a percentage of the **whole slider box**, which also holds the ◀ ▶ buttons, the year select, Play and "Complete map". It should be positioned along the range track.
  - At 1280 px, the green 2023-24 mark is drawn at x≈1181, under the "Complete map (2023-24)" button. The thumb at 2023-24 is at x≈788.
  - The base-change and source-change ticks (2011-12, 2022-23, …) are bunched at the right end under the buttons. On the phone they sit under the year select.
  - The legend says "The green mark is 2023-24, the year with the complete map", so the visual misleads. The marker notes also live only in the ticks' `title` attributes; the ticks are `aria-hidden`, and the notes for a year appear only when you navigate to that year.
- **Where.** `web/src/components/map/YearSlider.tsx:163-168`, `web/src/components/map/map.module.css:258-279`.
- **Owner.** U3.
- **Fix.** Put the ticks in a wrapper that shares the range input's box (the same flex item), and place each at `left: calc(12px + (100% - 24px) * i / last)` so it lines up with the thumb centre.
- **Test.** "V3-05" (fails today).

### V3-06 (medium): in stories, the focused Next button moves off-screen after use

- **Evidence.** On `/en/story/deficit-funding/` at 1280×800:
  - after pressing Next, the button's top moved to y=798;
  - after `End` it was at y=820, below the 800 px viewport;
  - the page does not scroll, so focus is still on the button but cannot be seen.

  The new step's text is announced ("Step 7 of 7: The cost: interest"), but a sighted keyboard user has lost their place. On the phone, Next sits below the text, map and list, so the new step's text starts far above the visible area. This is a 2.4.7 concern in practice, though not a strict failure.
- **Where.** `web/src/components/story/StoryPlayer.tsx:100-109`: focus moves only for `"jump"`; button and key moves do nothing about visibility.
- **Owner.** U5.
- **Fix.** After a button or key move, call `scrollIntoView({ block: "nearest" })` on the focused control. Or, on phones, scroll the new step's heading into view and keep focus on the button.

### V3-07 (medium): diagram text is very small in common views and does not grow with browser zoom

- **Evidence.**
  - Labels are SVG text sized in viewBox units (13 for nodes, 11.5 for values), so they scale with the drawing. Measured rendered sizes (CSS px, node label / value label):

    | View | Node label | Value label |
    |---|---:|---:|
    | Home at 1280 px | 13.5 | 11.9 |
    | Panel open | 8.9 | 7.9 |
    | Full map | 10.0 | 8.9 |
    | Story map | 7.2 | 6.4 |
    | 640 px wide (= a 1280 screen at 200% zoom) | 7.0 | 6.2 |

  - Between 640 and 1280 CSS px, browser zoom does not enlarge the labels at all.
  - The same information is in the marks' accessible names and in "View as table", which is why this is medium rather than a 1.4.4 failure.
- **Where.** `web/src/components/map/SankeySvg.tsx:252-295`, `map.module.css:47-62`.
- **Owner.** U3.
- **Fix.** Counter-scale label font size by `1/scale` (read the SVG's rendered width with a `ResizeObserver`), with a floor of 12 px for node labels and 11 px for value labels. Hide value labels that then collide (V3-08).

### V3-08 (low): value labels overlap node labels in the default desktop view

- **Evidence.** At 1280×800 on `/en/` (the Union government and Companies overlaps are visible in `screenshots/map-desktop-*.png`):
  - "₹10.77 lakh crore to Banks and financial institutions" is drawn over "States and local b…";
  - "₹34.73 lakh crore" over "Companies";
  - "₹58.90 lakh crore" over "Union government".

  Both labels in each pair become unreadable. The same text is still available in accessible names and the table.
- **Where.** `SankeySvg.tsx:266-296`: value labels are placed at the target's left edge with no collision check against node label boxes.
- **Owner.** U3.
- **Fix.** Before drawing a value label, test its estimated box against node label boxes and earlier value labels, and skip it on overlap. The value stays in the name, the panel and the table.

### V3-09 (low): the two "Producers" copies have identical accessible names

- **Evidence.** The accessibility tree lists "Producers: ₹369.09 lakh crore flows through it, 127.0% of GDP. Press + to show its parts" twice: once for the paying copy (column 0) and once for the receiving copy (the last column). The same applies to PRDS in the full map. A screen-reader user cannot tell the two apart.
- **Where.** `web/src/components/map/MapView.tsx:82-91`: node aria text built per node id, not per copy.
- **Owner.** U3 (text key in `map.json`).
- **Fix.** Append the copy: "(paying side: what it sells)" or "(receiving side: what is spent on it)".

### V3-10 (low): the `<svg>` root has no role, so some tools treat the diagram as an image

- **Evidence.**
  - The interactive buttons sit inside `<svg>` → `<g role="group">`. Playwright's accessibility snapshot (in both engines) shows the `<svg>` as `img`, and ARIA `img` makes its children presentational.
  - Chromium's own tree exposes it as `SvgRoot` and the 62 buttons are reachable, so this is a robustness risk with some browser and screen-reader combinations, not a confirmed failure.
- **Where.** `web/src/components/map/SankeySvg.tsx:122-149`.
- **Owner.** U3.
- **Fix.** Move `role="group"`, `aria-roledescription` and `aria-label`/`aria-describedby` from the inner `<g>` onto the `<svg>` element.

### V3-11 (low): non-interactive story maps announce keyboard instructions that do nothing

- **Evidence.** In stories, the map group is still `aria-describedby` the (visually hidden) help text "Arrow keys move between groups, Enter opens details, + and − zoom, L lists a group's flows.". The map has 0 focusable elements, and its label ("11 groups and 51 flows") does not say what the step highlights.
- **Where.** `web/src/components/map/SankeySvg.tsx:119-121` and `:143`.
- **Owner.** U3, with U5 for the label.
- **Fix.** Set `aria-describedby` only when `interactive`. Let `MapView` take an `ariaLabel` override that U5 fills with the highlighted flows.

### V3-12 (low): the theme toggle's accessible name does not match its visible label

- **Evidence.** The visible text is "Auto", but the name is "Change colour theme (now Theme: automatic)". "Auto" is not a word in the name, so a speech-control user saying "click Auto" may fail (2.5.3 Label in Name, borderline). "Theme:" is also doubled.
- **Where.** `web/messages/en/common.json:20-24`, `web/src/components/ui/ThemeToggle.tsx:47-52`.
- **Owner.** U2.
- **Fix.** Use a name that contains the visible word, e.g. "Colour theme: Auto. Change", with "Light" and "Dark" likewise.

### V3-13 (low): on phones, story step links are named just "2" … "7"

- **Evidence.** Below 640 px, step titles are `display: none`, so the progress links' accessible names drop to the bare digits ("link, 2"). Only the current step keeps its title.
- **Where.** `web/src/components/story/story.module.css:115-121`.
- **Owner.** U5.
- **Fix.** Hide the titles visually (the `visually-hidden` class) rather than with `display: none`, or add `aria-label="Step {n}: {title}"`.

### V3-14 (low): axe best-practice findings on permalink pages

- **Evidence.**
  - `heading-order` on every flow and series page: the `<h1>` is followed by `<h3>` ("What it is", "Trend", …) with no `<h2>`.
  - `landmark-unique` on series pages: region "Every year" (the `<section>`) contains a second region named "Every year" (the table's scroll wrapper).
- **Where.**
  - `web/src/components/map/FlowDetailPanel.tsx:176` (`H` is h1 or h2, but subsections are hard-coded `<h3>`, e.g. lines 258, 328, 333, 365).
  - `web/src/components/map/SeriesTable.tsx:17` and `:60`.
- **Owner.** U3.
- **Fix.** When `headingLevel === 1`, render subsections as `<h2>`. Drop the inner region's label, or name it "Every year (table, scrolls sideways)".

### V3-15 (low): the slider-thumb CSS has no effect

- **Evidence.** `.range::-webkit-slider-thumb { width: 24px; height: 24px }` is ignored without `appearance: none`. The thumb renders at about 15 CSS px in Chromium (measured at 2× DPR). The input box (710×44) still meets 2.5.8, but PLAN §2.1 and §4.6 promise a "thumb ≥ 24 px".
- **Where.** `web/src/components/map/map.module.css:241-248`.
- **Owner.** U3.
- **Fix.** Style the range with `appearance: none` on the input and the thumb, a visible 3:1 track and thumb border, and a focus ring. Or drop the claim from the PLAN text.

### V3-16 (low): the faintest heat-map colours nearly vanish

- **Evidence.**
  - The first stops of the ramps have very low contrast against the page background:

    | Theme | Colour | Contrast |
    |---|---|---:|
    | Light (on `#fbfaf7`) | `#c7e9b4` | 1.28:1 |
    | Light | `#fdd0a2` | 1.37:1 |
    | Dark (on `#121317`) | `#16384a` | 1.50:1 |
    | Dark | `#4a1a08` | 1.28:1 |

  - At the 128×128 view, the smallest flows are close to invisible.
  - The table, the all-cells list and the keyboard announcements carry the values, so this is not a 1.4.11 failure.
  - Similar but harmless: the kind swatches on phone cards and the "₹100" bar use the raw kind colours (production 2.93:1, factors 2.42:1, discrepancy 2.95:1 on `--surface` in light). The text beside them carries the meaning.
- **Where.** `web/src/lib/matrix/colour.ts:23-34`.
- **Owner.** U4.
- **Fix.** Start each ramp at a stop of at least 3:1 against `--bg`, or outline non-zero cells when the cells are 6 px or larger.

### V3-17 (low): phone "Full diagram": the help text is cut off, and the table toggle's wording is inconsistent

- **Evidence.**
  - Inside the phone's 2-D scroll region, the help line sits in the 1100 px-wide inner box. At 375 px it reads "Arrow keys move between groups, Enter opens deta…" until you scroll sideways.
  - Separately, "View as table" toggles to "Hide the list" (table versus list) with no `aria-expanded`.
- **Where.**
  - `web/src/components/map/MapApp.tsx:270-275` (`scrollInner`), with the help rendered by `SankeySvg.tsx:119`.
  - `MapApp.tsx:195-204`.
- **Owner.** U3.
- **Fix.** Render the help line outside the scroll region. Use "View as table" / "Hide the table" and add `aria-expanded`.

### V3-18 (low): internal source ids appear in reader-facing marker text

- **Evidence.** The series page for F49 (and others) lists markers such as "Source changes from mospi_nas_2026_api_b2011_back (NB) to mospi_nas_2026_oldbase_nas2025_s1_9 (NO)". These are pipeline ids, not plain English: an understandability problem and against the plain-English rule. The same notes feed the slider's "Breaks in the series this year" disclosure.
- **Where.** Marker `note` strings in `ts/series.json`, generated by `pipeline/export/timeseries.py`.
- **Owner.** U1, with U6 for wording.
- **Fix.** Map dataset ids to their registry titles (for example "NAS 2026, old-base back series" → "NAS 2026, new base") in the marker notes.

## Checked and found correct

**axe.** 0 WCAG A/AA violations in all 84 scans. Best-practice findings are listed in V3-14. I reviewed every "incomplete" node; all are axe being unable to compute a background, and all are fine:

| What axe could not resolve | Measured result |
|---|---|
| SVG node and value labels over ribbons and hatch | `--text` on a 3 px `--bg` halo: 16.3:1 light, 15.7:1 dark |
| Sticky table headers in scroll regions | Text on `--surface-2`: 6.3:1 or better in both themes |
| Trend-chart tick text such as "0" | Muted text on `--bg`: 7.0:1 light, 8.1:1 dark |
| The decorative ◆ marker | `aria-hidden` |

**Colour tokens** (composited, both themes):
- Text and UI:
  - text on bg: 16.3:1 light, 15.7:1 dark;
  - muted text: 6.3:1 or better;
  - accent and links: 6.7:1 or better;
  - focus colour against bg and surface: 6.4:1 or better;
  - accent-text on accent: 7.0:1 light, 8.6:1 dark;
  - badge text on badge backgrounds: 5.4:1 or better light, 6.8:1 or better dark;
  - the top-flows banner text: 14.6:1 light, 11.5:1 dark.
- Every `--k-*-edge` stroke against `--bg` and `--surface`:
  - light: 4.7:1 or better;
  - dark: 7.3:1 or better.
- Every ribbon is outlined by its edge stroke. Fills alone are 1.4:1 to 3.9:1, and the stroke makes up for that, as §4.11 intends.
- Hatch lines against the ribbon fill: 4.3:1 or better.
- Node rectangles use the edge colours: 4.7:1 or better.
- Dimmed (non-highlighted) ribbons in stories fall to 1.7:1 to 2.8:1 by design; they are context, not content.

**Theme.**
- The OS scheme is respected.
- The stored choice overrides the OS in both directions (light OS with dark stored, and the reverse), with 0 axe violations and no hydration or console errors.
- The heat-map canvas follows the toggle.
- Form controls get the right `color-scheme`.

**Keyboard model (§4.5.10), apart from V3-01:**
- The skip link moves focus to `<main>`.
- The diagram is a single Tab stop.
- ↑/↓/←/→ move between nodes, with a visible SVG focus ring (2.5 px focus colour plus a halo), in Chromium and WebKit.
- Enter opens the panel and focuses its heading; Esc closes it and returns focus to the mark that opened it.
- `L` enters the link list, ↓ moves, Enter opens the link, and Esc goes link → node → clear.
- "Close" returns focus to the opener.
- Table-row buttons and phone list rows open the panel, and Esc or Close returns focus to them.
- The top-flows view uses the same model.

**Slider.**
- `aria-valuetext` follows the year.
- ←/→/Home/End work.
- The live region announces on manual steps, select and pause, and not on Play ticks (apart from the end-of-Play bug in V3-04).
- Scrubbing into 2023-24 keeps the top-flows view.
- 2.5.7: dragging is never required, because the ◀ ▶ step buttons and the year `<select>` do the same.
- Play has Pause and stops at the end (2.2.2).

**Matrix (U4).**
- The heat-map is a single `role="application"` Tab stop with a visible outline and a cursor drawn on the canvas.
- Arrow keys move; the debounced live region announces "{payer} pays {receiver}: …".
- Enter zooms in and announces "Now showing 8 receivers by 8 payers"; Esc zooms out and restores the cursor; `T` opens the table and moves focus to its scroll region.
- The tablist supports ←/→/Home/End.
- Scroll regions are focusable and labelled.
- The matrix table uses `<th scope>`.
- The all-cells list has `aria-rowcount` and a "show all" option for screen readers.

**Stories (U5).**
- Previous/Next buttons and ←/→/Home/End within the player work; Next and Previous use `aria-disabled` at the ends.
- A polite announcement "Step n of 7: title" plays on each move.
- Jump links move focus to the step heading.
- `?step=` is kept with `replaceState`.

**2.4.11 Focus Not Obscured.**
- No fixed or sticky element overlaps content.
- The desktop panel and the story map are sticky side columns, not overlays.
- On phones, the panel is inserted below the map and focus goes to its heading, which scrolls into view.
- The sticky table headers in the matrix sit above rows that hold no focusable controls.

**2.5.8 Target Size** (apart from V3-03).
- I scanned all visible interactive elements outside the diagram on 10 routes at both viewports.
- Everything is at least 24×24 px, or is an inline link in text (exempt), or is a 20 px checkbox with a clickable label and room around it.
- Link marks are covered by "View as table" buttons (44 px tall rows).

**Phone (375×812).**
- No horizontal page scroll on any route.
- The first screen shows the h1, the GDP figure with its badge, and the first story link without scrolling.
- The phone map shows cards, not the Sankey; tapping a card opens "Money in" and "Money out" lists with rows at least 44 px tall and `aria-expanded`.
- "Full diagram" opens a focusable, labelled 2-D scroll region.

**Reflow and text spacing.**
- At 320 px, nothing is clipped outside a focusable scroll region: the wide tables (series years, panel entries) scroll inside `tabindex=0` regions, and the methodology code block wraps.
- The WCAG 1.4.12 spacing override causes no loss.

**Reduced motion.**
- `prefersReducedMotion()` stops the path tween.
- `globals.css` turns off CSS animations and transitions, including the view-switch fade.
- Play steps instantly.
- No auto-moving content.

**Page basics.** Every route has `lang="en"` and a unique, descriptive `<title>`. Landmarks are banner, main navigation, main and contentinfo.

## Not covered

- **Firefox.** It cannot launch on this host.
- **Real screen readers** (VoiceOver, NVDA). I checked semantics through the accessibility trees, not by listening. V3-10 is the main thing a real VoiceOver or Safari pass should confirm.

## Code checks (verifier-owned, for the orchestrator to land)

- `web/tests/verify/v3_a11y.spec.ts` and `web/tests/verify/playwright.v3.config.ts`.
- Run with `npx playwright test -c tests/verify/playwright.v3.config.ts` (it serves `out/` itself, or uses `PW_BASE_URL`).
- Six tests encode V3-01 to V3-05: V3-01, V3-02 on desktop, V3-02 on phone, V3-03, V3-04 and V3-05. All six **fail on the current build** and should pass after the fixes. `tsc --noEmit` and `eslint` are clean on them.

## Screenshots (`docs/phase3/screenshots/`)

- 36 PNGs, named `<page>-<desktop|phone>-<light|dark>.png`.
- Desktop shots are 1280×800 at 1× pixel density. Phone shots are 375×812 at 2× (750×1624 pixels).
- They were taken with the OS colour scheme emulated and reduced motion on.

| Name | What it shows |
|---|---|
| `home-*` | First screen |
| `map-*` | Home scrolled to "The map", simple preset |
| `topflows-*` | The top-flows view at 2004-05, with its banner |
| `panel-*` | The flow panel for Household consumption: beside the map on desktop, below it on the phone |
| `flow-*` | `/en/flow/HH--PRODUCERS/` |
| `story-*` | `/en/story/gst-rupee/`, step 1 |
| `data-*` | Top of `/en/data/` |
| `data-heatmap-*` | `/en/data/` scrolled to the heat-map |
| `methodology-*` | Top of `/en/methodology/` |

The desktop map shots show the label overlap in V3-08 as the product looks today.

## Round 2 (re-verification)

Re-verifier V3, 2026-10-02, branch `phase3-map`, real export `2023-24.8b1b533fd6`. I did not build or fix anything.

**How I tested.** I ran `npm --prefix web run build` (under the build lock), copied `web/out/` to a private scratch folder and served the copy with the project's `serve-out` config on its own port. Other re-verifiers' rebuilds therefore could not change what I tested. I scripted probes in Chromium and WebKit (Playwright 1.63), then ran the updated verifier spec with its own `--output` folder. Firefox still cannot launch on this host.

### Summary for the owner

All three high findings and all four medium findings are **closed**. Each fix holds in Chromium and WebKit, and each also holds in the harder cases I tried against it.

Two new **low** findings came up, and one of them is a side effect of the V3-07 fix:
- **V3-19**: the phone header nav clips the top and bottom of its links' focus rings. This existed before round 1 and I missed it then.
- **V3-20**: on phone story maps, the group labels are now cut to four or five letters ("Produ…", "Rest…", "Union…"), and two of them touch ("Compa…" runs into "Taxes").

Most of the round-1 low findings are still open (listed below). None of them fails WCAG AA.

### High and medium findings

| Id | Status | Evidence (round 2) |
|---|---|---|
| V3-01 (high), focus lost on + / − | **Closed** | <ul><li>`+` on every expandable group, in Chromium and WebKit, in both the simple and full maps, moves focus to that group's first part. That covers Producers, Wages/mixed income/profits, Households, Companies, Banks, Taxes, Saving and investment, Goods & services, Industries and Financial markets. Producers maps to `PRDS@out` in the simple map.</li><li>`−` on HH.RUR or HH.URB moves focus to HH, also with `?x=HH,TAX`.</li><li>Each zoom is announced ("Households opened into its parts. Focus is on the first part.", "Parts folded back into Households. …").</li><li>Arrow keys keep working afterwards.</li><li>On a group that cannot expand (Rest of world, the Union government, States, Discrepancies), focus stays on it and there is no announcement.</li><li>Same bug looked for elsewhere: the panel's "Show its parts" button and the group buttons keep focus, on desktop and phone.</li></ul> |
| V3-02 (high), clipped focus rings | **Closed** | <ul><li>The four toolbar toggles, the "Share of GDP / ₹ crore" toggle and the phone group cards all show a full ring.</li><li>I tabbed through 12 routes at 1280 and 375 px and checked every focused element for a missing or clipped ring.</li><li>No regressions. The only real clip left is the phone header nav (new **V3-19**, low: the sides of the ring still show, so 2.4.7 still passes).</li><li>The other hits were false positives: `body` overflow passes to the viewport, and a link at the bottom of the panel was confirmed visible in a screenshot.</li></ul> |
| V3-03 (high), node target size | **Closed** | <ul><li>Every interactive node has a hit rect (`[data-node-hit]`) of at least 24 × 24 CSS px. I checked 8 views at 1280, 1024 and 640 px, including the top-flows view and a dense map: `?x=HH,TAX,PRDS,PROD,NFC,FC` with the panel open.</li><li>At the centre of every node, `elementFromPoint` returns that node.</li><li>"View as table" now starts with one button per drawn group (`[data-group-button]`), all at least 24 px. That is 11 of 11 in the simple map and 35 of 35 in the dense map. Each opens the group's panel and its "Show its parts" button.</li><li>axe `target-size` with **no** `[data-mark]` exclusion: 0 violations (the e2e suite now excludes only `[data-mark="link"]`).</li><li>Leftover issue: in the densest views, neighbouring hit rects overlap by up to 6.8 px at 640 px (for example E_NBFC with E_INSP, and T_PSUB with T_PROD). The group buttons are a qualifying equivalent control, so this is not a failure.</li></ul> |
| V3-04 (medium), Play end announced the wrong year | **Closed** | `stop(i)` gets the index it stopped on. The verifier test passes: the live region matches the slider's `aria-valuetext` when Play ends. |
| V3-05 (medium), ticks in the wrong place | **Closed** | <ul><li>All 9 ticks (8 markers and the 2023-24 mark) sit within 0.01 px of their year's thumb centre. Checked at 1280 and 375 px in Chromium and WebKit.</li><li>A click at a tick's x selects that tick's year (1990-91, 2004-05, 2011-12, 2023-24, 2025-26).</li><li>The thumb is now 24 px (this also closes **V3-15**). The input's focus ring is visible in both themes.</li></ul> |
| V3-06 (medium), Next scrolled off-screen | **Closed** | <ul><li>Desktop, in all 3 stories and both engines: after Next ×8, Home, End and Previous, the focused button stays in view (top ≈ 744 of 800).</li><li>Phone: the new step's heading is scrolled to the top, and focus stays on the button below it. This is the alternative I proposed in round 1.</li><li>On desktop, when a step is taller than the screen, its heading can sit above the visible area. That cannot be avoided, because the step is taller than the screen.</li></ul> |
| V3-07 (medium), tiny labels | **Closed** | <ul><li>Group labels never go below 12.0 CSS px and value labels never below 11.0, in all views at 1280, 1024 and 640 px (= 200% zoom). That includes the panel-open, full, dense and top-flows maps.</li><li>Story maps at 1280, 800 and 375 px: group labels 12.0 px.</li><li>No value label overlaps a group label or another value label at any of these widths, which also closes **V3-08**.</li><li>Side effects:<ul><li>On phone story maps the labels are cut short and two collide (new **V3-20**).</li><li>At 640 px in the dense map, two "Manufac…" labels overlap.</li><li>Story maps now show no value labels at any width, because the collision check drops them all. The values are in the step text.</li></ul></li></ul> |

### Low findings

| Id | Status | Note |
|---|---|---|
| V3-08 | **Closed** | Value labels now go through a collision check (see V3-07). |
| V3-09 | Open | Both Producers copies are still named "Producers: ₹369.09 lakh crore flows through it, …". Test added (`test.fail`). |
| V3-10 | Open | `role="group"` is still on the inner `<g>`, not on the `<svg>`. |
| V3-11 | Open | `aria-describedby` still points at the keyboard help when the map is not interactive. |
| V3-12 | Open | Still "Change colour theme (now Theme: automatic)" against the visible "Auto". |
| V3-13 | Open | Phone step links are still named "2", "3", … |
| V3-14 | **Half fixed** | `heading-order` is gone (sections render as `<h2>` on permalink pages). `landmark-unique` remains on `/en/series/*`. Test added (`test.fail`). |
| V3-15 | **Closed** | The thumb is now 24 px in every engine. |
| V3-16 | Open | `colour.ts` is unchanged. |
| V3-17 | Open | The help line is still inside the phone scroll region, and "View as table" still has no `aria-expanded`. |
| V3-18 | Open | `/en/series/F49/` still shows `mospi_nas_2026_oldbase_nas2025_s1_9` and similar ids. |

### New findings

#### V3-19 (low): the phone header nav clips the top and bottom of its links' focus rings

- **Evidence.**
  - Below 640 px, `.nav` has `overflow-x: auto`, so `overflow-y` computes to `auto`. The 36 px-tall links' 2 px ring, at a 2 px offset, falls outside the nav's box on top and bottom.
  - A 3× screenshot of "Stories" shows only the left and right edges of the ring.
  - The sides are still visible, so 2.4.7 still passes. This is the same class of bug as V3-02.
- **Where.** `web/src/components/ui/ui.module.css` (phone `.nav` block, `overflow-x: auto`).
- **Owner.** U2.
- **Fix.** Either add `padding-block: 4px` to the scrolling nav (or `margin-block: -4px` with matching padding), or use `outline-offset: -2px` for `.nav a:focus-visible`.
- **Test.** "V3-19" (`test.fail`).

#### V3-20 (low): phone story maps: counter-scaled group labels are cut to a few letters and collide

- **Evidence.**
  - At 375 px the story map is 341 px wide. The 12 px floor makes labels about 34 viewBox units, so `fitLabel` cuts them to 4 or 5 letters: "Produ…", "Rest…", "House…", "Union…", "State…", "Savin…", "Discr…".
  - "Compa…" overlaps "Taxes" in all three stories.
  - The labels are `aria-hidden`, and the step text names the flows, so this is low.
- **Where.**
  - `web/src/components/map/SankeySvg.tsx`: `nodeFont` and `fitLabel`, with no node-label-to-node-label collision check.
  - Story map size: `StoryPlayer` `PHONE_MAP_HEIGHT`.
- **Owner.** U3, with U5.
- **Fix.** Either:
  - add a collision pass for node labels, which shortens or drops the lower-priority label; or
  - on phones, give the story map the same 2-D scroll treatment as the map's "Full diagram", or a short-label set.
- **Test.** "V3-20" (`test.fail`).

### Verifier tests (round 2)

`web/tests/verify/v3_a11y.spec.ts` and `playwright.v3.config.ts`. Run with:

```
PW_BASE_URL=… npx playwright test -c tests/verify/playwright.v3.config.ts --output <own folder>
```

- **The six round-1 tests now pass normally.** V3-03 now also accepts `[data-group-button]` as the equivalent control.
- **New tests that pass:**
  - V3-01: every expandable group, plus the announcement.
  - V3-03: the centre hit test in three views, including the dense map with the panel open.
  - V3-05: every tick, and click-to-select.
  - V3-06 desktop: Next, End and Home in 3 stories.
  - V3-06 phone: the heading comes into view.
  - V3-07: label sizes in 5 views, at 1280 and 640.
- **New `test.fail` tests for open findings:** V3-09, V3-14 (`landmark-unique`), V3-19 and V3-20. I checked that each one fails for the stated defect, not because of a selector error. Remove the mark when the defect is fixed.
- **Result:** 16 passed, 16 skipped (each test runs only in its own desktop or phone project). `eslint` and `tsc` are clean on these files.

**Also checked, no regressions:**
- axe (WCAG A/AA plus best-practice, no exclusions) on 8 routes at 1280 and 375 px in light: clean apart from V3-14's `landmark-unique`.
- axe in dark on 6 routes at both sizes: clean.
- No horizontal page scroll on 9 routes at 320 and 375 px, including after opening a phone group card (`.card` lost `overflow: hidden` and gained `min-width: 0`).

**Not covered.** Firefox (cannot launch). Real screen readers.
