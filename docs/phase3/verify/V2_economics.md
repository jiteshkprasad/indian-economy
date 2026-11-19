# V2 Economics: verification report (Phase 3, the Map)

Verifier: V2 (economics). I built none of this. Date: 2026-10-02. Branch `phase3-map` at `f8481bc`, real export `web/public/data/2023-24.410aa99863`.

**What I read:** `web/content/en/map-text.json` and `map-desc.json` (every node, link, ref and series entry); the three story MDX files and their YAML specs (`pipeline/export/stories/*.yaml`) and exported figures (`stories/*.json`); all ten methodology MDX files; every user-visible string in `web/messages/en/{common,map,matrix,methodology,story}.json`; `pipeline/export/disc_text.yaml`, `old_base_scope.yaml` and `judgement_bands.yaml`. I checked them against DECISIONS (D0-5, D0-6, D0-7, D2-3, D2-8, D2-9, D2-11, D2-12, D2-13, D2-16, D2-21, D2-24), `docs/phase2/SAM_GUIDE.md`, `docs/phase2/CHECKPOINT_B.md` (§2, §5, §6b and §8) and PLAN §3.4, §3.8, §3.9, §4.0, §4.9 and §4.10.

**How:** I checked each text claim against the balanced parquet with DuckDB. That covered every level-0 link's contents by ref and component, X_DISC entries, K9/K9b, the old-base provenance methods, the remittance satellite and the time-series signs. I then read the **rendered** static build (`web/out/en/**`, built 12:49 after the 12:42 commit) to see what a reader actually gets: the home page, all 81 level-0 flow pages, the three stories and methodology.

Severity follows the brief. High means a wrong number, misleading economics or a broken page. Medium means a real but contained problem. Low means polish.

---

## Summary

| Severity | Count | IDs |
|---|---|---|
| High | 2 | V2-01, V2-02 |
| Medium | 7 | V2-03 … V2-09 |
| Low | 11 | V2-10 … V2-20 |

The core SAM conventions are right throughout:
- Rows receive and columns pay.
- GST is net and post-settlement, UTGST sits inside CGST, and the cess passes to the States.
- PM-KISAN is a transfer.
- NPISH are inside households.
- "Pooled, not traced" is said correctly.
- UAE vs Dubai and bank-channel vs BoP transfers are said correctly.
- Average vs marginal shares are kept apart, with no forecast or multiplier claims.

The two high findings are both in prose and labels, not in data. The deficit story calls a negative net-lending number "net borrowing". The methodology page gives a ₹1.55 lakh crore remainder as the published saving-investment errors and omissions, when the NAS-derived figure is ₹3.59 lakh crore.

**X_DISC panel (asked specifically):** it works. The `disc.D1/D2/D3_valuables/D3_si_errors/D4` keys exist in `web/messages/en/map.json` lines 206–213. `FlowDetailPanel.tsx` `DiscText` (lines 357–371) renders them under "What this discrepancy item is", and `panel-text.ts::discKeyOf` matches all five keys. The rendered pages show it:
- `flow/DISC--ROW/` shows the D2 text "...It is not money paid abroad."
- `flow/HH--DISC/` shows the D1 text.
- `flow/DISC--SI/` shows both D3 texts.

The D3 wording is wrong in substance (V2-02), and U1's issues file still lists the request as open (V2-16).

**First screen (60 s):** the h1, the GDP figure (₹290.73 lakh crore, official) and the "of every ₹100 households pay out" split (66.8 / 24.0 / 3.3 / 3.1 / 2.3 / 0.4 / 0.1, which sums to 100) are true to the data. The unallocated residual is kept on its own line. Two framing problems remain: the "Taxes ₹3.3" line implies households pay only ₹3.3 in tax (V2-07), and the GDP badge contradicts itself (V2-08).

---

## Findings

### V2-01 (high): the deficit story calls negative net lending "net borrowing"
- **Evidence:** the rendered `/en/story/deficit-funding/` has the caption "Net borrowing (national accounts), 2023-24". It then lists the Centre at −₹11.47 lakh crore, the States at −₹5.84 lakh crore and general government at −₹17.31 lakh crore. The prose says "Net borrowing by the Centre was **−3.9% of GDP**, by the States −2.0% of GDP, and by general government −6.0% of GDP".
- **Why it is wrong:** the figures are net *lending* (`nl_cen` = non-financial receipts − payments, negative). A negative "net borrowing" reads as net lending, so the sign of the story's central figure is inverted. The step's own text ("net lending when it is positive") does not rescue it.
- **Files:**
  - `web/content/en/stories/deficit-funding.mdx` lines 25 and 27;
  - `web/messages/en/story.json` line 63 (`captions.deficit-funding.gap`) and lines 152–157 (`nl_*` labels);
  - `pipeline/export/stories/deficit-funding.yaml` (`nl_cen`, `nl_sta`, `nl_gg`, `nl_*_gdp`).
- **Owner:** U5.
- **Fix:** either add `net_borrowing_*` figures as `product` × −1 of `nl_*` and bind the "net borrowing" sentence and caption to those (positive ₹11.47 lakh crore, 3.9% of GDP), or relabel the caption "Net lending (+) / net borrowing (−)" and rewrite line 27 as "The Centre's net lending was −3.9% of GDP, that is, it borrowed 3.9% of GDP". Add a vitest check that no figure labelled "borrowing" is negative.

### V2-02 (high): saving-investment errors and omissions are given as ₹1.55 lakh crore "as published"; the published (derived) figure is ₹3.59 lakh crore
- **Evidence:**
  - `data/clean/mospi_nas_2026/mospi_nas_2026_derived_residuals.parquet` has `derived.si_errors_omissions.current` 2023-24 = **3,58,633.93** crore (status derived).
  - The SAM's D3 total is 2,04,105.43 (`unsectored_valuables`, K_HH) + 1,54,528.50 (`si_errors`, corporate K accounts) = 3,58,633.93.
  - The provenance confirms this (`sam_capital_financial:aa6b1d108bbc`: "The D3 total is NAS 2026 derived S-I errors and omissions"; `:440555f6902a`: "NAS S-I errors and omissions **less the K_HH part**"). The ₹2.04 lakh crore "valuables with no sector" is carved out of the published E&O, and ₹1.55 lakh crore is the remainder.
- **What the reader sees:**
  - Methodology limits renders "Saving-investment errors and omissions, **₹1.55 lakh crore**: investment less saving less net capital inflow, **as published**. The total is published…" (`web/content/en/methodology/limits.mdx` line 28; line 27 lists valuables as a separate gap).
  - `map-desc.json` line 218 (`DISC--SI`) says "Two published items". But the valuables part is derived (SUT valuables − NAS household gold), and the panel itself labels it "Derived".
  - `map-desc.json` line 339 (`refs.D3`) says "the official saving-investment errors and omissions (published total…)".
  - `messages/en/map.json` line 212 (`disc.D3_si_errors`) says "The total is published".
  - `pipeline/export/disc_text.yaml` line 15 (summary "Published total") says the same.
- **Related:** `flow/DISC--SI/` shows "The total is not held to a single published figure", although the link total equals the NAS-derived E&O exactly. It is not in `pinned.json` because all its entries are fixed and no constraint was declared.
- **Owners:** U6 (limits.mdx, map-desc), U3 (map.json `disc.*`), U1 (disc_text summary, pin).
- **Fix:**
  - Describe D3 as one published (derived) total of ₹3.59 lakh crore, NAS saving-investment errors and omissions. The SAM attributes ₹2.04 lakh crore of it to valuables no sector finances (into the households' capital account) and spreads the rest (₹1.55 lakh crore) over the corporate capital accounts (estimated).
  - Add a `methodology.disc_d3` binding for the total.
  - Change "Two published items" to "Two parts of one published residual".
  - Optionally let U1 treat an all-fixed X_DISC link whose sum equals a clean series as pinned (derived).

### V2-03 (medium): the RBI surplus timing item is described the opposite way to D0-7, and its offset is hidden in the "reconciliation residual"
- **Evidence:**
  - `deficit-funding.mdx` line 54: "The Reserve Bank's surplus **is counted in the year it is earned**, but part of it reaches the Centre's treasury as cash only later."
  - In the SAM the Centre's income is the **cash** receipt: `G_CEN ← E_RBI R6 cash_basis` = ₹87,416 crore, the RBI's 2022-23 surplus (D0-7, D2-16). `map-desc` FC--CEN and R6 say "on the cash basis" too.
  - The K9b method (`sam_capital_financial:a55e888c87fa`) says the receivable is "offset by equal and opposite parts of K9_GCEN and K9_RBI: a financial reclassification with no income counterpart".
- **Effect:** the story's "Reconciliation residual −₹42,037 crore" for the Centre (`assets_cen_k9`) contains a −₹1.23 lakh crore offset of the +₹1.23 lakh crore timing item. The NAS-vs-FSF residual proper is about +₹0.81 lakh crore, but story line 53 describes the line as purely that.
- **Files:** `web/content/en/stories/deficit-funding.mdx` lines 41 and 51–54; `web/messages/en/story.json` lines 165–166; `pipeline/export/stories/deficit-funding.yaml` (`assets_cen_k9`, `assets_cen_k9b`).
- **Owner:** U5.
- **Fix:**
  - Reword line 54: "The map records the RBI surplus the Centre actually received in cash during the year. The surplus the RBI earned in 2023-24 was larger and was paid the following year; that difference is shown as money the RBI owes the Centre, and an equal amount is netted inside the reconciliation residual below."
  - Better: show `assets_cen_k9b + assets_cen_k9` as one netted line, or show the K9 line excluding the K9b offset, so the residual means what the text says.

### V2-04 (medium): the GST story says the national accounts treat subsidies as negative taxes "instead of adding to what they spend"
- **Evidence:** `gst-rupee.mdx` line 79: "subsidies are recorded in the national accounts as **negative taxes**, which reduce what governments collect instead of adding to what they spend".
- **Why it is wrong:** NAS counts subsidies as government current expenditure. DECISIONS D2-24 itself relies on "St 4.2 current expenditure = consumption + subsidies + current transfers". Booking product and production subsidies as negative entries in the tax accounts is **this SAM's** (and the SUT's) convention.
- **Consequence:** the "per ₹100 of outlays" (₹71.40 lakh crore) leaves out ₹9.18 lakh crore of subsidies, about 13% of outlays on the NAS concept. That raises every other share. The figures are disclosed, but the stated reason is wrong.
- **Owner:** U5.
- **Fix:** "In this map, as in the supply and use tables, subsidies are booked as negative taxes in the tax accounts, so they are not in the government columns counted here. In the government's own accounts they are spending: add them and outlays rise by about an eighth." Optionally add a `gg_outlays_incl_subsidies` figure.

### V2-05 (medium): the deficit story counts "railways" in government investment and reads the Centre's equity as share purchases
- **Evidence:** `deficit-funding.mdx` line 15 says "Governments also invest: roads, **railways**, buildings…" and line 43 says "It also put money into shares".
- **Why it is misleading:**
  - In this SAM, as in NAS, the Railways and Posts are departmental enterprises inside **public non-financial corporations** (`E_NFPU`; map-text `E_NFPU`; K3a method `sam_government:82907c4254ec`: "public NFCs in NAS, so outside GG saving"). Railway capex is in `K_NFPU` I1a (₹10.0 lakh crore of public-NFC GFCF), not in `invest_cen` (₹5.41 lakh crore).
  - The Centre's budget support to the Railways comes back as the Centre's financial asset. It sits in `assets_cen_eqty` (₹2.73 lakh crore, FSF holder report) as "shares and other equity".
  - A reader comparing ₹5.41 lakh crore with the Budget's capital expenditure will be confused, and "put money into shares" suggests PSU share purchases.
- **Owner:** U5.
- **Fix:** drop "railways" from the investment list or add: "Investment by the Railways and Posts is counted with public sector companies; the Centre's funding of them shows up below as equity." On line 43 say "put money into public enterprises, including its departmental enterprises, as equity".

### V2-06 (medium): the label "Taxes kept by the Centre" is on gross Union taxes before devolution
- **Evidence:**
  - `map-text.json` line 733 gives the label "Taxes kept by the Centre".
  - The home-page flow list (rendered) reads "Taxes pays Union government: Taxes kept by the Centre, ₹35.31 lakh crore".
  - `map-desc.json` line 191 says this is "before the Centre shares part of its tax pool with the States". ₹11.29 lakh crore of devolution and ₹1.23 lakh crore of cess pass on (CEN--STA ₹17.45 lakh crore).
- **Why it matters:** the label claims the opposite of the description, on a first-screen flow.
- **Owner:** U6.
- **Fix:** relabel "Taxes collected by the Centre (before sharing with the States)", or "Union taxes, before devolution". Keep "Taxes kept by the States" (correct, own taxes), or make both "Taxes received by…" for symmetry.

### V2-07 (medium): the first screen says households pay "Taxes ₹3.3" of every ₹100
- **Evidence:** `messages/en/map.json` line 13 (`first.hh.parts.taxes` = "Taxes") renders "Taxes ₹3.3".
- **Why it is misleading:** this is direct tax only (T3a income tax and professions tax, ₹8.18 lakh crore). GST alone on household purchases is ₹9.85 lakh crore (`till_pfce`), about ₹4.0 per ₹100 of outlays, and it sits inside "Goods and services". A 60-second reader learns that households pay about 3% of their outlays in tax, which is false.
- **Related:** the card title "Of every ₹100 households pay out" includes saving (₹24.0), which is not paid out.
- **Owner:** U3.
- **Fix:** relabel "Income tax", or "Taxes on income (taxes on purchases are inside goods and services)". Consider the title "Where every ₹100 of household income goes". The remittance story already uses "Taxes on income" (`story.json` `hh_taxes_per100`).

### V2-08 (medium): the GDP badge contradicts itself: "Official … The total is not held to a single published figure"
- **Evidence:**
  - Home page and methodology: GDP ₹290.73 lakh crore with the badge "Official". Its expandable note reads "Taken from a published official statistic." followed by "The total is not held to a single published figure."
  - `web/src/components/map/FirstScreen.tsx` line 34 passes `total={null}`. `web/src/components/ui/StatusBadge.tsx` lines 80–85 then prints `noTotal` by default.
  - The same contradiction appears on every single-label "Official" flow, for example `flow/PRDS--PROD/` and `flow/PROD--PRDS~neg/`.
- **Why it matters:** GDP is the published NAS 1.1 figure (summary `gdp.label` = official, prov `timeseries:dbc00fc46a1a`), so the first figure on the site carries a false note.
- **Owners:** U3 (FirstScreen) and U2 (StatusBadge).
- **Fix:**
  - For GDP pass `total="official"` with the pin "NAS 2026 Statement 1.1" (or let U1 add it to summary).
  - In StatusBadge, do not print `noTotal` when the split label is `official` or `derived` and the composition is 100% that label. Use e.g. "A single published figure" instead.

### V2-09 (medium): series F32 says "Negative in some years"; it is negative in every year shown
- **Evidence:** `map-desc.json` line 374. `data/timeseries/top_flows.parquet` F32 is negative in all 14 periods from 2011-12 to 2024-25 (for example 2020-21 −₹13.21 lakh crore, 2023-24 −₹3.18 lakh crore).
- **Owner:** U6.
- **Fix:** "Negative in every year of the series (dissaving)." Also check F11 ("negative in most years", 74 of 77: fine) and F49 ("a few years", 3: fine).

### V2-10 (low): the old-base flag text "(2022-23 NAS)" invites confusion with the new base year 2022-23
- **Evidence:** `messages/en/common.json` line 63: "Estimated with the old-base (2022-23 NAS) structure". The new GDP base year is also 2022-23. The structure is the 2011-12-base series' sequence of accounts for the year 2022-23 (D2-21). `matrix.json` uses a different, clearer text ("old-base national-accounts structure"). The comment at `pipeline/export/old_base_scope.yaml` line 3 repeats the wording.
- **Owners:** U2 (and U1 for the comment).
- **Fix:** "Estimated with the structure of the previous (2011-12 base) national-accounts series, year 2022-23."

### V2-11 (low): `old_base_scope.yaml` flags the quasi-corporate side of income tax but not the household side, which comes from the same old-base ratio
- **Evidence:**
  - `sam_taxes:e2b1eea55e10` (T3 quasi-corporations = (1 − 0.785483) × MH 0021, the old-base household D5 share) is in scope.
  - `sam_taxes:4279ef5046b4` (T3a household income tax total = the "household share of MH 0021" + STT …, the same 0.785483) is not, so ₹8.11 lakh crore of HH→TAX carries no old-base flag.
- **Assessment:** the rest of the list is right. I checked every SAM provenance method mentioning old-base, D2-21 or oldbase inputs: the four D2-21 fincorp records and T4a belong, and the IFPRI comparison and closure records carry no entries.
- **Owner:** U1.
- **Fix:** add `sam_taxes:4279ef5046b4` with the reason "level of the household total uses the old-base household D5 share (D2-11)", or record why the household side is exempt.

### V2-12 (low): the GST "net" gloss is not quite D0-5's "net"
- **Evidence:** `gst-rupee.mdx` line 7 explains "net" as input-tax credit not counted twice. D0-5 and ACCOUNT_STRUCTURE §5 take "net" from S&M 2026, "net GST collections", that is, after refunds and on the post-settlement basis.
- **Assessment:** the credit mechanism is true of any GST figure, so this is not wrong, but it is not what "net" means here.
- **Owner:** U5.
- **Fix:** "It is **net**: refunds are deducted, and, as with any GST, tax that businesses pay on inputs and claim back as a credit is not counted twice."

### V2-13 (low): "the household share is the economically final part of GST" ignores investment and government purchases
- **Evidence:** `gst-rupee.mdx` line 43. Line 29 of the same story says GST on construction "mostly stays where it lands" because households and governments are final buyers. GST on GFCF (₹22.1 per ₹100) and GFCE (₹1.4) is just as non-creditable.
- **Owner:** U5.
- **Fix:** "That is why the household share is the largest part of the GST that stays with a final buyer; GST on investment and on government purchases is also final."

### V2-14 (low): link descriptions say "estimated" where the badge says "Set by balancing"
- **Evidence:** the rendered flow pages show "Set by balancing" while `map-desc` says "split … is estimated" on CEN--PRDS, STA--PRDS, CEN--HH, STA--HH, FC--HH, NFC--HH, NFC--FC, HH--TAX, CEN--FC, STA--FC and STA--SI.
- **Related:** SI--PRDS (`map-desc.json` line 185) says "The totals follow national accounts", but its badge is "Estimated" with "not held to a single published figure".
- **Assessment:** this is not contradictory (balancing moves estimates), but PLAN §3.9 asks that the wording follow the labels.
- **Owner:** U6.
- **Fix:** add a standing clause such as "estimated, and moved in balancing where the badge says so", or tune per link. For SI--PRDS say "each component total (GFCF, inventories, valuables) follows national accounts".

### V2-15 (low): raw constraint ids are shown to readers in badge notes
- **Evidence:**
  - `flow/DISC--ROW/`: "The total is held to a published figure: ts:M05".
  - `flow/HH--DISC/`: "…: closure:d1.published_total".
- **Owner:** U2 (StatusBadge `pinnedBy`), or U1 if `pinned.json` should carry readable names.
- **Fix:** map pin ids to readable names, for example "NAS 2026 Statement 6.1, CIF adjustment" and "the NAS household residual (derived from NAS 1.14 / 1.9)".

### V2-16 (low): U1's issues file says the X_DISC `disc.*` request to U3 is still open; it is done
- **Evidence:** `docs/phase3/issues/U1.md` line 54 versus `messages/en/map.json` lines 206–213 and the rendered panels (see the Summary). `docs/phase3/requests/U1.md` line 6 is still `[ ]`.
- **Owner:** U1.
- **Fix:** close both.

### V2-17 (low): the FC--TAX description leaves out income tax paid by quasi-corporate financial firms
- **Evidence:** `map-desc.json` line 225 says "Corporation tax paid by banks, NBFCs and insurers". The cell also holds T3 `quasi_corporate` ₹1,733 crore from E_BANK (D2-11). NFC--TAX does mention this.
- **Owner:** U6.
- **Fix:** append "and a little personal income tax paid by co-operative and other banks that the accounts treat as companies".

### V2-18 (low): the F13 description does not mention the base-break concept change
- **Evidence:** `map-desc.json` line 355. `top_flows_definitions` F13 `link_reason`: "the old base includes food subsidy, the new base books it in GFCE". F29's text mentions the GFCE treatment; F13's does not, although the old-base years of F13 include the food subsidy.
- **Owner:** U6.
- **Fix:** "Before 2022-23 (old base) this includes the food subsidy; from 2022-23 free food grain is counted as government consumption, so the series drops at the break."

### V2-19 (low): remittance group labels say "fifth of households", but the groups are fifths of persons within each area
- **Evidence:** `story.json` lines 127–128 ("The fifth of households that spend the most (rural and urban)"). The groups are MPCE quintiles of persons (CHECKPOINT_B §3: 17.09 crore persons per rural group; map-text H_R1: "The fifth of rural people…"). R5 + U5 is the top fifth within each area, not the national top fifth.
- **Owner:** U5.
- **Fix:** "The richest fifth in villages and in towns (by spending per person)".

### V2-20 (low): the household residual's text says "published" while its badge says "Derived total"
- **Evidence:** `flow/HH--DISC/` shows "Derived total · split estimated" next to "The total is the published figure" (`map-desc.json` HH--DISC). Also `disc.D1` ("the gap the national accounts publish") and the first-screen note ("a gap the national accounts publish").
- **Why:** the clean series is `derived.household_residual` (GDI − PFCE − saving from published NAS tables).
- **Owners:** U6 and U3.
- **Fix:** "a gap implied by published national-accounts totals".

---

## Checked and found correct

- **Rows receive, columns pay:** methodology "what", `matrix.json` intro and table caption, `story.json` `list.link` ("{payer} pays {receiver}"), the aria strings in `map.json`, and all 81 level-0 link labels and descriptions (direction checked against the parquet's payer/receiver for each).
- **Reversed flows are described the right way round:**
  - subsidy legs: PRDS--TAX~neg ("from the subsidy account into the product markets"), PROD--TAX~neg, and TAX--CEN~neg / TAX--STA~neg ("from the Centre into the subsidy accounts");
  - capital and financial legs: CEN--SI~neg (dissaving, never "the Centre pays saving"), SI--PRDS~neg (inventory run-down), FINM--SI~neg (K8e back-to-back loan repayment, −₹78,104 crore) and SI--FINM~neg (RBI net G-sec sales: `gsec_rbi` −₹42,718 crore).
- **GST (D0-5):**
  - net and post-settlement with no IGST account (TAX node, T_CGST/T_SGST, PRDS--TAX, gst-rupee step 1);
  - UTGST inside CGST, named and shown (`utgst` ₹5,772 crore), and excluded from the devolution base (`devol_cgst_per100` = 3,42,787 / 8,56,560 = 40.0);
  - the cess passed to the States as compensation grants (₹44,946 crore, official) and loan-recovery transfers (₹78,104 crore, derived, D2-13 current), with the matching K8e repayment;
  - the judgement-band caveat on CGST and the cess;
  - the till shares summing to 100 with exports at zero (zero-rated);
  - the product ranking (construction 17.6, transport equipment 9.6, chemicals 7.5, textiles 7.4, recomputed from the parquet);
  - "interest comes second, ahead of investment" (21.7 > 19.8).
- **PM-KISAN (D2-24):** a transfer in CEN--HH ("treated as a transfer, not a subsidy"), R10, methodology "provisional" and "issues"; never described as a subsidy. Free grain is described as GFCE (CEN--PRDS, T_PSUB, F29, TAX--CEN~neg).
- **X_DISC items:**
  - D1: the household residual, never folded into consumption or saving (first screen, remittance story, HH--DISC).
  - D2: a CIF reconciliation, "not money paid abroad" (DISC--ROW label and text, `disc.D2`, M05).
  - D3: the valuables part goes to K_HH (correct per the parquet).
  - D4: zero in 2023-24.
  - "Balancing never moved these": true, all X_DISC entries are `fixed`.
  - The only error is the D3 total (V2-02).
- **Net borrowing vs fiscal deficit:**
  - The deficit story's "gap" step correctly separates national-accounts net lending from the Budget's fiscal deficit (loans and equity are financial assets; cash vs accrual; sector boundary). The YAML definition and the assets − liabilities check agree.
  - F34 says net G-sec issuance is neither concept.
  - CEN--SI~neg separates saving from the revenue deficit.
  - The only error is the sign in V2-01.
- **UAE vs Dubai and bank channel vs BoP:** remittance step "uae" states that Dubai cannot be isolated and that the share is bank-channel, applied to all transfers as an assumption. It also states the normalisation (shares sum to 99.80%) and that the US is larger (27.8% vs 19.2%, checked against the `s3_remittance_sources` satellite). The licence note and the withheld link are present. The `who` method text matches `sam_rest_of_world:46590e3f1880`.
- **"Pooled, not traced":** FINM node, SI--FINM, FINM.GOVD and I_GSEC ("pooled in one account"); deficit story "buyers" ("Centre and State securities together") and "households" steps; GST story "money is fungible".
- **No forecast or multiplier:**
  - Methodology "what" ("not a forecast… not a model of behaviour") and `methodology.json` `notForecast`; limits "average shares, not multipliers".
  - `story.json` `index.honesty`; remittance steps "use" (averages, not marginal) and "ripple" ("first round only").
  - A grep for multiplier, forecast, predict, boost and impact found no other uses.
- **Estimated and official wording against the exported labels:**
  - "published total" claims match `total = official` (remit_total, saving_gg, hh_consumption, hh_saving; HH--PRDS, HH--SI and ROW--HH are "Official total · split …").
  - "estimated" claims match `split = estimated` (till shares, product shares, remittance UAE and group shares, pfce taxes and imports).
  - "set by balancing" claims match (gst_cnst, CGST and cess). gsec_hh is official as stated.
  - Exceptions: V2-14 and V2-20.
- **Numbers in the prose:** none; all are bindings. The quantitative words "about a fifth" (22.1 and 21.9), "a little more" urban (52.6 vs 47.4), "much more" top vs bottom (46.3 vs 5.4), "similar range" (F43 share 2.6–4.0% from 2006-07 to 2025-26), "few years" of CA surplus (3) and "most years" F11 negative (74/77) are all true on the current export.
- **Methodology counts:** they match CHECKPOINT_B and PLAN: entries 151 / 64 / 8, cells 73 / 26 / 4 (= 224 / 90 / 12); label mix 47.1 / 8.4 / 30.0 / 14.6%; 11 judgement bands, 97 entries; old-base 36 entries, ₹19.15 lakh crore; moved ₹28.38 lakh crore, 9.8% of GDP. The description of the 12 unexplained items as all public-NFC flows matches `pipeline/sam/explanations/fincorp.yaml`.
- **Node and sector boundaries:** FCI inside the Union (D0-5); local bodies inside the States (D2-8); NPISH inside households; Railways and Posts in public NFCs; mutual funds only in the capital accounts; STT in T_PIT (D2-12); quasi-corporate income tax (D2-11) in NFC--TAX; motor-vehicle tax as a product tax (D2-4); R9d pensions in NFC--HH (D2-9); RBI surplus on the cash basis in FC--CEN and R6.
- **Units and framing:** "one lakh crore is one trillion rupees" (`matrix.json`); the gross-flows framing line; the time-series banner ("not a complete, balanced account").
- **`judgement_bands.yaml`:** equals CHECKPOINT_B §6b (11 ids).

## Not checked (out of scope or for other verifiers)

- Every figure's value against parquet (V1). I spot-checked only those quoted above.
- Accessibility and keyboard (V3), build and performance (V4), licences and every badge (V5). I flag V2-08 and V2-15 for U2 and V5 because they are about wording.
- I did not run the test suites. I read the built `out/`, which a concurrent verifier may rebuild; findings cite the source files, so they hold either way.

---

## Round 2 (re-verification)

Re-verifier: V2 (economics), independent of the fixers and the integrator. Date: 2026-10-02. Branch `phase3-map`, uncommitted working tree on top of `1c35ac2`. Real export `web/public/data/2023-24.8b1b533fd6`. I rebuilt the site through the build lock (`npm --prefix web run build`, finished 14:29:54) and read the rendered `web/out/en/**`. I also opened badge panels in Chromium with my own Playwright config. I changed no site or pipeline code.

**New verifier tests (V2 had none in round 1):**
- `tests/verify/test_phase3_economics.py` checks the export, DuckDB on the parquet files, the text sources and the static build. Result: 14 pass and 12 are strict xfails, one per open low finding. `uv run pytest tests/verify/test_phase3_economics.py`.
- `web/tests/verify/v2_economics.spec.ts` with `playwright.v2.config.ts` (output in `web/test-results-v2`) opens client-rendered badge panels. Result: 4 pass. Run `npx playwright test -c tests/verify/playwright.v2.config.ts` from `web/`.
- `tests/export` still passes with them: 113 passed, 12 xfailed.

### High and medium findings

| ID | Sev. | Verdict | Evidence (current code and build) |
|---|---|---|---|
| V2-01 | high | **closed** | `nb_cen`/`nb_sta`/`nb_gg` are +₹11.47 / +₹5.84 / +₹17.31 lakh crore and +3.9 / +2.0 / +6.0% of GDP. My test recomputes each as liabilities − financial assets from the parquet (`K_G* ← I_*` minus `I_* ← K_G*`). No `nl_*` is exported. The rendered step reads "both the Centre and the States were net borrowers … Net borrowing by the Centre came to 3.9% of GDP". I also checked every story figure whose label says "borrow": none is negative. |
| V2-02 | high | **closed** (one residual low, V2-22) | `summary.methodology.disc_d3` = 3,58,633.93 crore. This equals NAS `derived.si_errors_omissions.current` 2023-24 and the sum of all X_DISC D3 entries, and the record is in `prov`. The methodology page renders "Saving-investment errors and omissions, ₹3.59 lakh crore … one residual, derived from the published national accounts". It then shows the valuables part (₹2.04 lakh crore, Derived) and the remainder (₹1.55 lakh crore, Estimated). "as published" is gone. These texts now describe one derived residual in two parts: `map-desc` DISC--SI and refs.D3, `map.json` `disc.D3_si_errors` and `disc_text.yaml`. The flow page `flow/DISC--SI/` shows ₹3.59 lakh crore with that text. **Residual:** the link is still not pinned, so its badge says "The sum itself is not held to a single published figure". The limits page explains why. Logged as V2-22 (low). |
| V2-03 | medium | **closed** | The story now shows `assets_cen_k9_net` = K9 + K9b = +₹81,122 crore, which my test recomputes from the entries. It no longer shows K9 alone (−₹42,037 crore). The text now says income is counted on the cash basis, consistent with D0-7 and D2-16. It says the rise in the surplus owed (₹1.23 lakh crore, which equals the RBI surplus earned in 2023-24 less the one paid in cash during the year) has no matching income and is netted inside the residual. I checked this against the K9b method (`sam_capital_financial:a55e888c87fa`). Minor note: after balancing, the receivable (K_GCEN, ₹1,23,158.71 crore) and the payable (K_RBI, ₹1,23,430.47 crore) differ by ₹272 crore. That is immaterial to the text. |
| V2-04 | medium | **closed** | `gst-rupee.mdx` now says subsidies are negative taxes "in this map, as in the supply and use tables", and that in the government's own accounts and the national accounts they are spending. `gg_subsidies_paid` = ₹9.18 lakh crore. I recomputed it independently as every negative G ← T entry: P9a −5.76 lakh crore plus P10a gross subsidies −3.42 lakh crore. `gg_subsidies_per100` = 12.86 = paid / outlays × 100. |
| V2-05 | medium | **closed** | "railways" is gone from the investment list. A paragraph says the Railways and Posts are public enterprises whose investment sits with public companies. The equity sentence covers capital put into enterprises the Centre owns. The data confirm it: the Centre's I1a key (`sam_capital_financial:8c817b11d16a`) excludes Union heads 5002, 5003 and 5201. |
| V2-06 | medium | **closed** | The TAX--CEN label is now "Union taxes, before sharing with the States". The home flow list renders it, and "Taxes kept by the Centre" appears nowhere in the build or the sources. |
| V2-07 | medium | **closed** (related wording left in the remittance story, V2-21) | The first screen reads "Each ₹100 of household income … Income tax ₹3.3", with the note "GST and other taxes on purchases are inside goods and services". I checked the new title against the data. The household column total equals the household row total, ₹245.74 lakh crore (all receipts), and the seven parts sum to it, so "household income" is the right base. |
| V2-08 | medium | **closed** | The GDP badge is "Official total" with a `single` panel that reads only "Taken from a published official statistic". I scanned every built page (all badges with a panel): no badge whose total is official or derived, and no `single` panel, contains "not held to a single published figure". Aggregates such as PRDS--PROD now say "This amount adds up several entries … The sum itself is not held…", which is not a contradiction. Playwright confirms the GDP panel after hydration. |
| V2-09 | medium | **closed** | F32 now reads "Negative in every year of the series". The parquet has 16 rows and all 16 are negative. I looked for the same bug in every other sign claim in a series description; all match the data: F11 "most years" (74/77 negative), F49 "a few years" (3/77), M10 "some years" (8/78), and F13/F30 "shown as a positive amount paid" (all stored negative, display-flipped). |

### Low findings

| ID | Status | Note |
|---|---|---|
| V2-10 | open | `common.json` `flags.old_base_structure` still reads "(2022-23 NAS)". xfail test. |
| V2-11 | open | `sam_taxes:4279ef5046b4` is still missing from `old_base_scope.yaml`. xfail test. |
| V2-12 | open | The GST "net" gloss still omits refunds. xfail test. |
| V2-13 | open | The story still says "the economically final part of GST". xfail test. |
| V2-14 | open | SI--PRDS still says "The totals follow national accounts" while its badge is Estimated. xfail test. |
| V2-15 | closed (V5-05) | Pins are shown by name: "The time series “Services import reconciliation (CIF adjustment)” (M05)…" and the D1 constraint description with its target. Playwright checks that no raw id is shown. Residual polish is logged as V2-23. |
| V2-16 | partly | `requests/U1.md` is `[x]`, but `issues/U1.md` line 54 still says "Request to U3 still open". xfail test. |
| V2-17 | open | FC--TAX still omits quasi-corporate income tax. xfail test. |
| V2-18 | open | F13 still says nothing about the food-subsidy base break. xfail test. |
| V2-19 | open | `remit_top_per100`/`remit_bottom_per100` still say "fifth of households". xfail test. |
| V2-20 | partly | `disc.D1`, `limits.mdx` and `disc_text` now say "derived". Four places still say "published": `map-desc` HH--DISC ("The total is the published figure"), refs.D1 ("Published total"), the link label "Household residual (published discrepancy)" (also M12), and the remittance story line "Unallocated residual (published, not a choice)". xfail test. |

### New findings (round 2)

- **V2-21 (low): the remittance story still calls the household split "paid out".**
  - It reads "Of every hundred rupees that households paid out in 2023-24 (₹245.74 lakh crore in all)". The list includes Saving ₹24.0.
  - The first screen now titles the same numbers "Each ₹100 of household income" (the V2-07 fix).
  - Files: `web/content/en/stories/remittance-dubai.mdx` and `story.json`. Owner U5.
  - Fix: "Of every hundred rupees of household income…". Strict xfail `test_v2_21_…`.
- **V2-22 (low; the rest of V2-02): DISC--SI is not pinned.**
  - The link equals the NAS derived S-I errors and omissions to the paisa, but no balancing constraint holds it. Its flow-page badge and the methodology `disc_d3` badge therefore read "Estimated … not held to a single published figure". The limits page states the reason honestly.
  - Fix: a closure equality constraint on the NAS record (U1 and the pipeline/sam closure block, per the integrator note).
  - Strict xfail `test_v2_22_…`.
- **V2-23 (low): the new pin text shows internal constraint notes to readers.**
  - On `flow/HH--DISC/` the badge reads "Published NAS household residual; the written D1 (= D2 + D3 + D4 as written, DECISIONS D2-3) lies within +-Rs 1 crore (all members fixed: documentation)".
  - The identity is true in the data: 5.71 = 2.12 + 3.59 + 0 lakh crore, because X_DISC must close. But "as written", "+-Rs", "documentation" and a DECISIONS id are developer notation, and the text says "published" again (V2-20).
  - Other constraint descriptions in `sam/constraints.json` have the same style (for example "+-10% (the key assumes non-CE costs proportional to CE…)").
  - Fix: a reader-facing `label` per constraint (U1), or a short generic sentence plus the target (U2).

### Regressions looked for

- **Story text against the new labels.** I read every rendered story sentence that pairs a status word (published, estimated, balanced) with a badge, in all three stories. They agree after the V1-06 per-100 rule. Example: "Households bought only ₹1.4 Official directly", and the method text says the denominator was set by balancing.
- **Household card.** Its part labels match `summary.json`, and the parts sum to the base.
- **Deficit story.** Its figures and identities are consistent: `nb_gg` = `nb_cen` + `nb_sta`, and K9_net = K9 + K9b.
- **GST story.** The subsidy figures are signed consistently.

I found no regression in the economics.

**Not re-checked:** layout, a11y, performance and licences (V1, V3, V4 and V5).
