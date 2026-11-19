# Proposed SAM account structure (Phase 0)

Prepared 2026-09-29 by the SAM architect, for reference year **2023-24**, new 2022-23 base (see REFERENCE_YEAR.md). Sector shares below come from SUT 2023-24 (Aug-2026 vintage). I parsed the file myself; its sha256 is in REFERENCE_YEAR.md §4.

**Revised 2026-09-29 after three independent critiques.** Every change and every rejected point is listed in DESIGN_REVIEW.md. The main changes:
- 130 → **128 accounts**: T_IGST and T_STMP are removed.
- GST accounts are now on NAS's net, post-settlement basis.
- Stamp duty is a production tax.
- Food subsidy is government consumption, and FCI is part of G_CEN.
- Pensions, provident funds and insurance follow NAS conventions.
- The financial corporations are split into public and private parts.
- The flow-of-funds block has an explicit counterparty rule.
- The multiplier engine uses use-specific tax rates.

---

## Summary for the owner (plain English)

- **128 accounts in total.** That is small enough to invert live in the browser and large enough to tell every SPEC story.

  | Group | Accounts |
  |---|---|
  | Production activities | 34 |
  | Products (commodities) | 34 |
  | Trade-and-transport margin | 1 |
  | Factors of production | 4 |
  | Household groups | 10 |
  | Corporations (current accounts) | 6 |
  | Governments (Centre, States) | 2 |
  | Tax and subsidy accounts | 12 |
  | Rest of the world (current) | 1 |
  | Capital accounts | 11 |
  | Inventories | 1 |
  | Financial instruments | 11 |
  | Statistical discrepancy | 1 |
- **Activity-by-commodity SAM, not a symmetric one.** MoSPI publishes only Supply-Use Tables; there has been no official input-output table since 2007-08. Keeping activities (industries) and commodities (products) separate lets us use the official tables almost untouched. The alternative would need an extra modelling assumption to make a square industry-by-industry table. (The multiplier model built on it still assumes fixed product mixes and import shares; see D1.) About 10–30% of each manufacturing activity's output is a different product (for example, "machinery" firms also make miscellaneous metal goods), and this structure keeps that visible.
- **34 sectors**, chosen for the stories the site must tell:
  - crops (the monsoon);
  - crude oil and refineries (oil shocks);
  - construction;
  - IT services (the export engine: 6.7% of GVA, over half of its output is exported);
  - trade and transport;
  - finance and insurance;
  - dwellings (7.6% of GVA);
  - public administration;
  - gems & jewellery (gold imports).

  Tiny industries are merged where they tell no separate story. Every one of MoSPI's 67 industries and 155 products maps to exactly one SAM sector (checked in code).
- **4 factors:** regular-salaried wages, casual wages, mixed income (the self-employed and farmers), and gross operating surplus. Mixed income gets its own account because in India it is a huge income source, it flows only to households, and it is where monsoon shocks land.
- **10 household groups** (rural/urban × 5 consumption quintiles, from HCES 2023-24). Non-profit institutions (NPISH) stay inside households, as NAS does, because no official data separate them on the new base.
- **Corporations:**
  - Non-financial corporations are split public vs private.
  - Financial corporations are split RBI / banks / NBFCs / insurance & pension funds in the income accounts. Each of these is built as a public part plus a private part, so they add up to NAS's public-FC and private-FC totals.
  - Mutual funds appear only in the financial (flow-of-funds) block. They are pass-throughs with almost no income of their own.
- **Government:** Union and States separately. Local bodies sit inside "States" because their data are thin and they are funded through states. The Food Corporation of India sits inside the Union government, as in NAS 2026.
- **12 tax accounts:** CGST, SGST, GST compensation cess, customs, Union excise, State VAT/sales tax, State excise, other product taxes, product subsidies, net production taxes (which include stamp duty and land revenue), personal income tax and corporation tax.
  - These cover "where does your GST rupee go" and "who funds the deficit".
  - GST is recorded after the Centre–State settlement, as NAS does, so each rupee reaches one government once. IGST's route through settlement is shown as a memo layer, not a separate account.
- **Financial block:** 11 instruments, e.g. deposits, loans, G-secs, small savings, corporate bonds, equity, MF units, insurance & pension, and forex reserves. FDI, FPI, ECB and NRI deposits are tags on the rest-of-world rows of these instruments, not extra accounts.
- **One explicit statistical-discrepancy account** carries the official unclosed gaps (₹5.7 lakh crore household residual, ₹2.1 lakh crore NAS–BoP CIF gap). They are shown, not hidden.

---

## 1. Design decisions

| # | Decision | Chosen | Main alternative | Why |
|---|---|---|---|---|
| D1 | SAM form | **Activity × commodity (A×C)**, same 34 codes on both sides | Symmetric product×product or industry×industry | The official input is a 155×67 SUT with no official IOT. A×C uses supply and use as published: **no technology assumption in the data SAM**, no negative coefficients. The **multiplier model** built on it does assume (a) a fixed product mix per commodity (market shares: each commodity is supplied by activities in fixed proportions, i.e. the industry-technology/by-product assumption) and (b) fixed import shares by commodity (competitive imports). Both are listed in the Phase 4 assumption notes and matter when comparing with IOT multipliers. Off-diagonal production is material: at the 34-sector level the own-commodity share of activity output is 69.4% for machinery, 85.6% for non-metallic minerals and 87–92% for most manufacturing (my calc from the Supply table). A symmetric variant can be derived later **only** for comparison with published IOT multipliers (CSEP, NCAER), labelled `estimated (industry-technology)` |
| D2 | Valuation | Commodity accounts at **purchasers' prices** on the use side. Activities sell at **basic prices**. The commodity column adds imports, product taxes (by type), subsidies and margins | Everything at basic prices with valuation matrices | The SUT Use table exists only at purchasers' prices, and MoSPI publishes no valuation matrices. Basic-price uses would need estimated tax and margin matrices by use cell |
| D2a | Product taxes in the multiplier engine | The data SAM keeps product taxes in commodity columns (as the SUT). The **Phase 4 engine uses use-specific tax coefficients** from the valuation layer GAP_MAP P7b (tax by commodity × type × use: IC, PFCE, GFCE, GFCF, exports). GST and cess on exports = 0, and creditable GST on intermediate use is excluded | (a) Tax accounts paid by using accounts (activities, household groups, GOV, CAP) inside the SAM | With a single average rate per commodity, an export shock would create GST that does not exist and a consumption shock would be under-taxed. For GST (~₹19 lakh cr) that would distort the "GST rate change" preset and the GST-incidence story. (a) would put estimated cells into the published SAM and break the link to the SUT's product-tax vector. (b) keeps the published SAM official-shaped and fixes the engine. Decided now because it fixes the shape of the P7a output |
| D3 | Imports | **Competitive imports by commodity** (RoW row in commodity columns) | Non-competitive import matrix by using industry | The SUT gives imports by product (official), not by user. An import-use matrix is kept as an optional multiplier variant, estimated with ICIO/ADB priors |
| D4 | Margins | One margin account `M_TTM`. Commodities pay their trade-and-transport margin into it; it buys trade and transport services | Direct commodity→trade/transport cells | The SUT gives one combined TTM per product (sums to zero). Only the totals by margin-providing product are known. A single margin account uses both official vectors and needs no estimation |
| D5 | Gross vs net | **Gross** operating surplus / mixed income (CFC included in factor income); **gross** saving | Net | NAS 1.9 publishes **gross** saving by sector, which is our capital-account control. CFC by industry and sector goes to a memo (satellite) table |
| D6 | Sector disaggregation of stories finer than 34 sectors | The site's third zoom level reads the underlying **155×67 SUT** directly (e.g. fertiliser subsidy, gold imports, rice vs wheat) | More SAM accounts | Keeps the multiplier matrix ≤128 while every drill-down stays official |

## 2. Production activities and commodities (34 + 34)

Codes: activity `A_xxxx`, commodity `C_xxxx` (same suffix). "SUT ind." = column number (1–67) in the SUT 2022-23/2023-24 Use/Supply sheets. "SUT prod." = product serial number (1–155). NAS group = broad group in SUT note Table 5.1 / NAS Statement 7.1: 1 Agri-forestry-fishing; 2 Mining; 3 Manufacturing; 4 Electricity-gas-water-other utilities; 5 Construction; 6 Trade-repair-hotels; 7 Transport-storage-communication; 8 Financial; 9 Real estate-dwellings-professional; 10 Public administration; 11 Other services.

NIC 2008 codes are **indicative**. MoSPI's note says NIC 2008 and NPCMS 2011 (Revised)/NPCSS were used, but it publishes no machine-readable industry↔NIC or product↔NPCMS concordance (mospi_io verifier). The NIC column must be confirmed against *Sources and Methods 2026* or requested from NAD (see access requests).

GVA%, M/S and X/Q are my calculations from SUT 2023-24: GVA share; imports ÷ (domestic supply + imports); exports ÷ domestic output.

| # | Code | Name | SUT ind. | SUT prod. | NIC 2008 (indicative) | NAS grp | GVA% | M/S% | X/Q% | Why this boundary (Indian relevance · data · story) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | CROP | Crops | 1 | 1–27 | 011–013, 0161 | 1 | 12.07 | 1.6 | 4.2 | Largest single activity. **Monsoon story.** The SUT has one crop industry, so no activity split is possible without estimation. The rice/wheat (PDS, MSP) detail is shown from the product rows: free PDS grain is government consumption (GFCE on paddy ₹1,01,441 cr, wheat ₹62,531 cr). Farm income support (PM-KISAN etc.) sits in agriculture's net production subsidy (−₹2,03,683 cr) by default |
| 2 | LVST | Livestock | 2 | 28–35 | 014, 0162 | 1 | 4.80 | 0.3 | 0.6 | India is the largest milk producer. A distinct rural income source that is less monsoon-sensitive than crops |
| 3 | FOFI | Forestry & fishing | 3, 4 | 36–41 | 02, 03 | 1 | 2.46 | 0.4 | 0.2 | Small. Merged; both are primary, rural and household-run |
| 4 | COAL | Coal & lignite | 5 | 42 | 05 | 2 | 0.48 | 60.2* | 1.0 | Coal → power and steel. Energy-transition story. Coal PSUs (public NFC) |
| 5 | OILG | Crude petroleum & natural gas | 6, 7 | 43, 44 | 06 | 2 | 0.54 | **85.6** | 0.0 | **Oil-shock story.** 86% import-dependent. Merging crude and gas also neutralises the swapped product labels in the 2023-24 file (GAP_MAP §4, issue Q1) |
| 6 | OMIN | Other mining | 8, 9, 10 | 45–51 | 07, 08, 099 | 2 | 1.02 | 12.3 | 11.0 | Iron ore, bauxite, limestone: inputs to steel and cement |
| 7 | FOOD | Food products | 11–14 | 52–64, 67, 68 | 10 | 3 | 1.24 | 6.8 | 8.3 | Agro-processing link from crops and livestock. Edible-oil imports |
| 8 | BVTB | Beverages & tobacco | 15, 16 | 65, 66, 69 | 11, 12 | 3 | 0.46 | 4.8 | 5.8 | **Tax story.** Alcohol is the base of State excise and VAT. Tobacco carries Union excise and (to Jan 2026) GST compensation cess |
| 9 | TXAP | Textiles, apparel & leather | 17, 18, 19 | 70–78 | 13, 14, 15 | 3 | 1.49 | 5.5 | 23.3 | Labour-intensive exports. Cotton link to crops |
| 10 | WOOD | Wood, paper, printing & furniture | 35–38 | 79–82 | 16, 17, 18, 31 | 3 | 0.92 | 8.7 | 5.3 | Small; merged. No distinct story |
| 11 | GJOM | Gems, jewellery & other manufacturing | 39 | 125, 126 | 32 | 3 | 0.46 | **32.9** | 21.4 | Gems & jewellery are 71% of this industry's output (my calc). **Gold story**: G&J imports ₹6.57 lakh cr (~9% of pre-CIF imports of ₹71.6 lakh cr); valuables ₹3.76 lakh cr; re-export cutting and polishing |
| 12 | RPET | Coke & refined petroleum | 30 | 85, 86 | 19 | 3 | 0.99 | 10.0 | 34.6 | **Oil shock + fuel taxes** (Union excise, State VAT). Petroleum products carry ₹6.99 lakh cr of product taxes (SUT 2023-24). Large refined-product exports |
| 13 | CHEM | Chemicals (incl. fertilisers), rubber & plastics | 31, 33 | 83, 84, 87–91, 93–95 | 20, 22 | 3 | 1.67 | 25.4 | 20.6 | Fertiliser subsidy lives here: product 89 (−₹1,45,129 cr) plus a further −₹62,440 cr booked on product 90 "pesticides", which has zero imports (quirk Q6, asked of NAD). Both are inside C_CHEM, so the SAM is unaffected. Organic-chemical imports from China |
| 14 | PHRM | Pharmaceuticals | 32 | 92 | 21 | 3 | 0.87 | 3.9 | 33.9 | "Pharmacy of the world" export story. Health link |
| 15 | NMMN | Cement & non-metallic minerals | 34 | 96, 97 | 23 | 3 | 0.84 | 4.9 | 7.6 | Construction supply chain |
| 16 | MTLS | Basic metals (iron & steel, non-ferrous) | 20, 21 | 98–101 | 24 | 3 | 1.40 | 11.7 | 10.1 | Infrastructure input. Coal → steel link |
| 17 | MACH | Fabricated metals, machinery & repair | 22, 28, 40 | 102–108 | 25, 28, 33 | 3 | 1.70 | 24.8 | 18.1 | Capital-goods supplier (GFCF story). Import-intensive |
| 18 | ELEQ | Electronics, electrical & optical equipment | 23–27 | 109–117 | 26, 27 | 3 | 0.94 | 29.3 | 20.3 | Import dependence (China) and PLI mobile-phone exports. Split from MACH because the import story differs |
| 19 | TREQ | Transport equipment | 29 | 118–124 | 29, 30 | 3 | 1.64 | 10.8 | 13.3 | Automobiles: large, GST-heavy, cyclical |
| 20 | CNST | Construction | 41 | 127 | 41–43 | 5 | 8.62 | 0.3 | 0.5 | **Construction story.** 73% of its use goes to GFCF (₹54.3 of ₹74.6 lakh cr, my calc). CE is 52.5% of GVA (casual-labour intensive) |
| 21 | UTIL | Electricity, gas, water & other utilities | 42–45 | 128–131 | 35–39 | 4 | 2.77 | 0.0 | 0.0 | Electricity is 80% of this group. State power subsidies. Coal and gas input |
| 22 | TRAD | Trade & repair of motor vehicles | 53 | 132, 133 | 45–47 | 6 | 7.25 | 0.4 | 0.1 | **Trade story.** Supplies most of the margin account. Informal, high mixed income |
| 23 | HOTL | Hotels & restaurants | 54 | 134 | 55, 56 | 6 | 1.29 | 0.0 | 0.0 | Tourism and eating out. The SUT's product rows already include non-residents' purchases in India (₹2,80,978 cr, shown in a memo row), but place them mostly on "community/personal" and "recreation" services rather than on hotels. We keep the published allocation and tell the tourism story from the BoP travel line (GAP_MAP §4.1, Q3) |
| 24 | TRNS | Transport & storage (rail, road, water, air, support, warehousing) | 46–51 | 135–140 | 49–52 | 7 | 4.05 | 1.9 | 11.6 | **Transport story**; supplies part of the margins. Road transport is the largest diesel user (oil-shock channel). Railways are merged in: 0.59% of GVA, and the public/private split is carried by institutions, not activities |
| 25 | COMM | Communication & broadcasting | 52 | 141 | 53, 60, 61 | 7 | 1.48 | 2.1 | 3.2 | Telecom. Kept separate from IT services: domestic, capital-heavy, low export share (3.2% vs 52.7%), different import story. (The SUT's CE shares are not used as evidence here: IT's is a MoSPI group average, quirk Q2) |
| 26 | FINS | Financial services (banking, NBFC, other) | 55 | 142 | 64, 66 | 8 | 5.60 | 1.8 | 3.3 | **Financial-sector story.** FISIM. Its output accrues to RBI, banks and NBFCs via operating surplus |
| 27 | INSR | Insurance & pension services | 56 | 143 | 65 | 8 | 0.68 | 0.0 | 9.8 | Kept separate so the insurance-corporation account has its own production. CIF adjustment on insurance |
| 28 | DWEL | Ownership of dwellings | 57 | 144 | 68 (imputed) | 9 | 7.59 | 0.0 | 0.0 | 7.6% of GVA with zero CE. Covers owner-occupied (imputed) **and** rented dwellings; its PFCE (₹21,48,044 cr) also includes government-provided housing (S&M 2026). Crucial for household income and the housing story |
| 29 | BSRE | Real estate, legal, business services & renting | 61–64 | 145, 146, 148, 149 | 68 (market), 69–71, 73–75, 77–82 | 9 | 4.66 | 19.1 | 29.6 | Global capability centres and business-services exports. Imports of "other business services" ₹5.5 lakh cr |
| 30 | ITSV | Computer & related services | 60 | 150 | 62, 63 | 9 | 6.66 | 6.2 | **52.7** | **IT-exports story.** Over half of output is exported. Salaried urban households. The SUT's CE/GVA (70.9%) and production-tax/GVA (3.8%, ₹66,850 cr) are **pro-rata group averages**, not measured for IT (quirk Q2). A satellite gives IT's labour share from ASI/ASUSE or OECD evidence |
| 31 | EDUC | Education & research | 58 | 147, 152 | 72, 85 | 11 | 4.11 | 10.7 | 4.9 | Public (States) and private split via institutions. Study abroad appears on the import side |
| 32 | HLTH | Health & social care | 59 | 153 | 86–88 | 11 | 1.46 | 0.1 | 0.2 | Health spending (out-of-pocket vs government). Kept apart from education because the financing mix differs |
| 33 | OSRV | Community, personal & other services | 65, 66 | 154, 155 | 90–99 | 11 | 1.96 | 21.0 | 37.8 | Residual services, including recreation and broadcasting content trade |
| 34 | PADM | Public administration & defence | 67 | 151 | 84 | 10 | 5.82 | 0.5 | 0.3 | Government non-market output (CE is 80.8% of GVA). Centre vs States via institutions (NAS 4.1) |

\* COAL M/S uses imports ÷ (domestic supply + imports) for coal; steam and coking coal imports are large.

**Coverage check (done in code):** the 34 groups contain every SUT industry 1–67 once and every product 1–155 once. The script is in the session scratchpad (`agg.py`); it will be moved into Phase 1 tests as `tests/test_sector_map.py`.

**Rejected alternatives for sectors**
- *Splitting CROP into foodgrains / other crops as activities:* impossible without estimation, because the SUT has one crop industry. The commodity side could be split, but the drill-down already shows it. **Rejected: more estimated cells for no new identified data.**
- *A separate railways activity:* public ownership is shown through the institutional split (NAS 7.1A), so a 0.6%-of-GVA activity adds little.
- *Keeping all 67 industries:* 67×2 production accounts would take the SAM to ~200 accounts. Most gain nothing: CE/GVA ratios are identical within NAS broad groups (GAP_MAP §4, issue Q2), so the extra rows carry no independent factor information.
- *Fewer than 25 sectors:* we would lose the oil, gold, IT, pharma and electronics stories, and the separation of import-intensive manufacturing.

## 3. Factor accounts (4)

| Code | Name | Content | Data basis | Why |
|---|---|---|---|---|
| F_LREG | Labour — regular wage/salaried | CE paid to employees in regular wage/salaried employment (PLFS status 31), including all public-sector employees | NAS CE by industry (official total) × PLFS share of regular vs casual earnings by NIC section (estimated) | Salaried urban households vs casual rural households is India's defining labour divide. It drives the quintile distribution of income |
| F_LCAS | Labour — casual | CE paid to casual labourers (PLFS status 41/42/51), including MGNREGA wages if NAS classifies them as CE | As above. PLFS publishes casual wages by NIC section (Table 51); regular earnings by industry need unit data | Construction, agriculture and MGNREGA stories; the bottom quintiles |
| F_MIXD | Mixed income (gross) | Surplus of household unincorporated enterprises (own-account farmers, shopkeepers, transporters) including their CFC | NAS 7.1C household-sector OS/MI by industry (official, ₹85.9 lakh cr in 2023-24) **less** ownership of dwellings (owner-occupied and rented), NPISH and quasi-corporation surplus (estimated) | NAS does not separate MI from OS (mospi_nas quirk 7). It is ~1/3 of GVA. It flows only to households, and monsoon shocks hit it |
| F_GOSC | Gross operating surplus | OS + CFC of corporations and general government, plus the household sector's non-mixed-income surplus: (i) imputed rent of owner-occupiers, (ii) actual rent earned by household landlords, (iii) surplus of household partnerships, trusts and NPISH | NAS 1.14 GVA and CFC by sector; NAS 7.1A/B/C; SUT CFC by industry | Capital income, distributed to institutions. Every household-sector rupee paid in goes back out to household groups through three keyed cells (GAP_MAP F3a–F3c), so the account's row equals its column (Phase 2 test) |

**Rejected:**
- *A land factor:* no Indian source separates land rent. SAS 2019 leasing income is tiny and dated. Land returns stay inside F_MIXD.
- *Skill (education) split of labour:* feasible from PLFS unit data, but it overlaps with the regular/casual split and is less relevant to the stories. It can be added later as a satellite without changing the SAM.
- *Formal/informal labour:* PLFS "informal" (no written contract or social security) cuts across regular employment. It is kept as a memo satellite, because NAS CE is not classified that way.
- *Net factors:* rejected by D5.

## 4. Institutions — current accounts (18)

### 4.1 Households: 10 accounts
`H_R1 … H_R5` (rural MPCE quintiles 1 = poorest … 5) and `H_U1 … H_U5` (urban).
- **Quintile definition:** quintiles of *persons* by MPCE, within rural and within urban separately. They are built from HCES 2023-24's 12 fractile classes (Table A2/A10F: 0–5, 5–10, 10–20, …, 90–95, 95–100%), which aggregate exactly to quintiles (0–20, 20–40, 40–60, 60–80, 80–100). Using *person* quintiles matches the published tables.
- **Why 10 and not 20 or 40:** 10 is the SPEC minimum. Further splits (e.g. by occupation: farm/non-farm/salaried/casual, as IFPRI 2017-18 did) need HCES/PLFS unit data **linked** at household level. HCES has no income or occupation-earnings questions, and MoSPI's HCES Rider forbids using the auxiliary variables for estimation (mospi_households verifier). Revisit when microdata access is granted. The ABM can still use richer synthetic agents calibrated to these 10 groups.
- **NPISH:** kept **inside households**. NAS "Households including NPISH" (Statement 1.14) is the only new-base control, and PFCE includes NPISH consumption. No new-base NPISH data exist. Consequence: NPISH consumption and saving are spread over quintiles in proportion to household aggregates. The methodology page must say so. Rejected alternative: a separate NPISH account with fully invented values.

### 4.2 Non-financial corporations: 2 accounts
`E_NFPU` public NFCs (departmental enterprises such as railways and posts, plus non-departmental PSUs; central and state) and `E_NFPR` private NFCs (including foreign-controlled). Official split: NAS 1.9 and 1.14 publish GVA, saving, GCF and CFC for public and private NFCs separately.

**FCI is not in E_NFPU.** NAS 2026 reclassified the Food Corporation of India from a market to a non-market producer, so food subsidy is a social transfer in kind in GFCE (S&M 2026, QNA GFCE section: "Following the reclassification of the Food Corporation of India (FCI) from a market producer to a non-market producer, food subsidy is recorded as a social transfer in kind and consequently forms part of GFCE rather than product subsidies"). FCI therefore sits in **G_CEN**. The old-base FSF 2023-24 most likely still holds FCI and its borrowings (including NSSF loans) with public NFCs. This is to be confirmed; the K9 reconciliation carries an explicit FSF→NAS sector bridge for FCI and any other reclassified unit.

**Reinvested earnings.** Private NFCs pay reinvested earnings of foreign direct investors (D43) to RoW (GAP_MAP R14a). NAS 1.9 deducts them from private corporate saving: ₹1,63,704 cr in 2023-24.

### 4.3 Financial corporations: 4 current accounts + 1 financial-only

| Code | Institution | Current account? | Capital/financial? | Definition (follows RBI FSF sectors) | Why |
|---|---|---|---|---|---|
| E_RBI | Reserve Bank of India | Yes | Yes (K_RBI) | FSF S121 | Surplus transfer to the Centre, income on forex reserves and G-secs, monetary base. Official from the RBI Annual Report |
| E_BANK | Banks and other deposit-taking corporations | Yes | Yes | FSF **S122 ODCs** (SCBs, RRBs, cooperative banks, SFBs, and deposit-taking NBFCs/HFCs per FSF footnotes) | Deposits and credit story. Keeping RBI's ODC boundary makes the FoF block official. The **current account uses the same boundary**: STRBI for SCBs plus NABARD/RBI data for RRBs and co-operatives, not SCBs alone |
| E_NBFC | NBFCs, HFCs, AIFIs/DFIs (non-deposit-taking), financial auxiliaries | Yes | Yes | FSF OFCs (S123–S129) **minus** insurance, pension and MFs. Includes the administration funds of EPFO/CMPFO/NPS etc. (financial auxiliaries, S126) | Shadow-bank credit story (RTP Appendix VI.1 balance sheet, end-March 2024) |
| E_INSP | Insurance corporations & pension/provident funds | Yes | Yes | LIC, GIC and public general insurers, private insurers, and the **contribution funds** of EPFO, CMPFO, SMPFO, ATEPFO and NPS (Pension Funds, S129; settled by S&M 2026 §7.4.8) plus PF trusts | Follows NAS: life-insurance premiums and claims, and PF/pension contributions and withdrawals, are **financial** transactions (household saving in I_INPE), not current transfers. E_INSP's current account carries only its service output, net non-life premiums and claims, and the investment income it earns and passes to policyholders and members (D44). Its saving is therefore small, as NAS FC saving (₹9,91,448 cr) requires |
| — (K_MUTF only) | Mutual funds | **No** | Yes (K_MUTF) | SEBI-registered MFs | MFs have no saving of their own: income is attributed to unit holders. In current accounts, MF-held property income is recorded **look-through**, from issuer to ultimate holder, using SEBI unit-holding shares (HBS T72). Rejected: a zero-saving MF current account made of estimated cells with no new information |

**EPFO is settled.** S&M 2026 §7.4.8: "The contribution funds of organisations such as the Employees' Provident Fund Organisation (EPFO), Coal Mines Provident Fund Organisation (CMPFO), Seamen's Provident Fund Organisation (SMPFO), Assam Tea Employees Provident Fund Organisation (ATEPFO) and National Pension System (NPS) are included under this sub-sector [Pension Funds, S-129]. The administration funds … are separately classified under Financial Auxiliaries (S-126)." This matches FSF, where S129 is "Provident Funds and Pension (Non-Government)" and government PF (GPF) is a liability of the Centre and States (FSF 3.1, 3.2). The earlier "move to G_CEN" contingency is dropped.

**Public/private split.** The NAS controls are public FC and private FC saving and GVA (1.9, 1.14): public GVA ₹7,14,052 cr and saving ₹5,35,510 cr; private GVA ₹9,44,003 cr and saving ₹4,55,938 cr in 2023-24. Every FC sub-account straddles both totals:
- E_BANK includes public-sector banks, RRBs and State co-operative banks.
- E_NBFC includes AIFIs (NABARD, SIDBI, EXIM, NHB), SFCs/SIDCs and large public NBFCs (PFC, REC, IRFC).
- E_INSP includes LIC, the public general insurers and the EPFO/NPS funds.

So each sub-account's current account is built as a **public part + a private part**, estimated from ownership data: RBI Trend & Progress and public NBFC reports, IRDAI public vs private insurers, and NABARD for RRBs and co-operatives. The public parts must add up to NAS public FC and the private parts to NAS private FC (GAP_MAP F4a, K2a). The accounts stay four; the public/private parts are sub-rows used in estimation and shown in drill-down.

### 4.4 General government: 2 accounts
`G_CEN` Union government (Consolidated Fund plus public account items treated as government; includes UTs without legislature, **central autonomous bodies** and **FCI**). `G_STA` States + UTs with legislature + **local bodies** + **State autonomous bodies** (consolidated; state→local transfers netted inside).
- **Autonomous institutions** are "Autonomous Bodies (Centre and State)" (S&M 2026 §4.4). NAS 4.1 shows them as one block (NVA ₹1,53,164 cr). The SAM splits that block between G_CEN and G_STA using Union grants-in-aid to central autonomous bodies (IITs, AIIMS, CSIR/ICAR institutes, KVS/NVS, …) against States' grants to theirs. The split is labelled estimated (GAP_MAP F4b, C2a).
- **Why local bodies are inside States:** Finance Commission local-body grants flow through state treasuries. ULB data run only to 2023-24 (FC16 cityfinance dump) and panchayat data only to 2022-23 (RBI PRI report), with patchy coverage. NAS general government also consolidates them. A separate account would be mostly estimated. Local-body spending is shown as a drill-down memo.
- **Official controls:** NAS general government GVA, final consumption and saving (1.14/1.9) are for GG as a whole. The Centre/State split of saving is **estimated** from Union Finance Accounts and RBI State Finances / CAG, converted to NAS concepts. NAS 4.1 gives value added by Centre vs States (official). It splits 2023-24 net value added into:

  | Part of general government | NVA 2023-24 (₹ cr) |
  |---|---|
  | Centre (incl. UTs without legislature) | 5,77,519 |
  | States | 11,78,217 |
  | Local bodies | 2,18,133 |
  | Autonomous institutions | 1,53,164 |

  So local bodies' own production is official even though their accounts are consolidated into `G_STA`; it is available as a drill-down.

### 4.5 Pensions, provident funds and insurance: the NAS convention (applies to HH, E_INSP, G_CEN, G_STA)

NAS measures household saving from the asset side. S&M 2026 household-saving table: PF & pension funds = "Contribution + Recoveries − Withdrawals + Interest" (including Central and State GPF and PPF), and life insurance = "Increase in Life Fund". NAS 5.3 therefore puts ₹7,23,027 cr (PF & pension) plus ₹6,49,086 cr (insurance) inside household saving of ₹58,90,330 cr. The old-base NAS household account (NAS 2024 St 5.0) shows no social contributions paid and an empty D8. The SAM follows this:

| Flow | Treatment in the SAM |
|---|---|
| Contributions to and withdrawals from funded schemes (EPF/EPS, NPS, CMPF, PF trusts, GPF, PPF); life premiums and claims | **Financial transactions** (I_INPE / I_SSAV), not current transfers. Gross flows shown in satellite S9 for the story |
| Employer contributions to these schemes | Inside CE (factor income), so they are household income that is then saved |
| Investment income earned on the funds (EPFO interest credited, NPS returns, life-fund investment income, GPF/PPF interest) | **Property income attributed to policyholders and members (D44)**, E_INSP (or G) → households (GAP_MAP R9c) |
| Government employees' Old Pension Scheme (unfunded) | Government CE includes an **imputed** pension contribution (S&M 2026 §3.1.1): OPS pensions paid × (1 − k/39) for the Centre's civil employees, and unadjusted for defence and for States still on OPS. Households pay that imputed contribution back to G (D612, GAP_MAP R9b), and G pays pensions as a benefit (D62, R9). Without R9b the same pension value would be counted twice |
| Non-life insurance | Net premiums and claims as current transfers (R17); service charge in PFCE |

Closure tests (Phase 2):
- E_INSP gross saving ≈ its CFC plus retained shareholder profit, and it fits inside NAS FC saving.
- Household disposable income + X_DISC − PFCE = NAS household saving.

### 4.6 Rest of the world: `R_ROW` (current account)
Exports and imports by commodity; CE, investment income and transfers to and from RoW.

## 5. Tax and subsidy accounts (12)

Every tax account's row collects from its payers; its column pays the receiving government(s). Subsidies are negative taxes (so balancing must use GRAS, which handles negative cells; see STACK_AND_REPO §12).

**Classification follows NAS 2026** (S&M 2026 §4.6.1 gives as examples of product taxes "GST, excise, sales tax, customs", and says "land revenue and stamp duties are treated as production taxes"). **GST is on NAS's net, post-settlement basis** (S&M 2026 QNA product taxes: "net Central GST (CGST), net State GST (SGST), net Integrated GST (IGST), compensation cess"). In the Union accounts IGST (MH 0008) is only the unsettled residual (−₹4,850 cr in 2023-24), because IGST is apportioned into CGST and SGST. States' SGST (FC16 KFI, ₹8,00,112 cr) is already post-settlement. So there is **no T_IGST account**: each rupee of IGST reaches a government exactly once, and the settlement route is a memo layer (GAP_MAP S7) for the "GST rupee" story.

| Code | Account | Paid by (row entries) | Received by (column) | Notes |
|---|---|---|---|---|
| T_CGST | Central GST, post-settlement (incl. IGST apportioned to the Centre and the MH 0008 residual) | Commodities | G_CEN | Row target = MH 0005 + MH 0008 (₹8,20,622 − 4,850 cr cash, 2023-24), converted to NAS accrual. GST detail is estimated within the SUT's official product-tax vector (GAP_MAP P7a) |
| T_SGST | State GST, post-settlement (incl. IGST settled to States) | Commodities | G_STA | Row target = FC16 KFI A.1.1.2 (₹8,00,112 cr) + UTs with legislature |
| T_GCES | GST compensation cess | Commodities (tobacco, pan masala, aerated drinks, motor vehicles; coal cess follows the SUT's PFCE-based spread) | G_CEN only | Uses split in G_CEN → G_STA: compensation grants, plus ₹78,104 cr used in 2023-24 to recover the 2020-22 back-to-back loans (GAP_MAP T2b, K8e). Levied in 2023-24; abolished 1 Feb 2026 |
| T_CUST | Customs (BCD, SWS, AIDC, other cesses on imports) | Commodities (imported portion) | G_CEN | SUT import duty by product (₹2,28,887 cr) is official |
| T_UEXC | Union excise duties incl. road & infra cess, NCCD | Commodities (petroleum, tobacco) | G_CEN | Petroleum split from PPAC exchequer data |
| T_SVAT | State sales tax / VAT (non-GST goods: petroleum, alcohol) | Commodities | G_STA | |
| T_SEXC | State excise (alcohol) | Commodities (BVTB; any excess over C_BVTB's SUT tax logged and placed on HOTL/TRAD as licence fees pending NAD) | G_STA | State excise (₹2,49,133 cr) alone exceeds the SUT's product tax on alcoholic beverages (₹2,33,677 cr): the P7a pre-check will size the licence-fee component |
| T_OPRT | Other taxes on products (electricity duty, entertainment, other Centre/State product taxes) | Commodities | G_CEN, G_STA | Small residual account. Motor-vehicle tax moves here (on C_TREQ) only if NAD confirms it is a product tax |
| T_PSUB | Product subsidies (fertiliser, LPG/kerosene/petroleum, State power subsidies, others; **not food**) | Commodities (negative) | G_CEN, G_STA (negative) | SUT subsidy vector by product (₹5,76,422 cr) is official. Food subsidy is GFCE (free grain, G_CEN). Unexplained rows: Trade −₹1,05,007 cr (Q7), pesticides −₹62,440 cr (Q6) |
| T_PROD | Other taxes less subsidies on production, **incl. stamps & registration and land revenue** | Activities | G_CEN, G_STA | SUT vector by industry (net −₹57,442 cr). Gross taxes (stamps ₹2,20,289 cr, land revenue, professional tax, property taxes) and gross subsidies (farm income support such as PM-KISAN by default, interest subvention, DE losses) are kept as two sub-rows (GAP_MAP P10a). MoSPI spreads the net vector pro rata to GVA **within** its groups; the ratio differs a lot between groups (agriculture −6.4%, communication −7.1%, real estate/dwellings/professional incl. IT +3.8%) |
| T_PIT | Personal income tax & other direct taxes on households | Households (and household-sector firms) | G_CEN | Includes securities transaction tax (reported with income tax in the Budget) |
| T_CIT | Corporation tax | E_NFPU, E_NFPR, E_BANK, E_NBFC, E_INSP (RBI exempt: RBI Act s.48) | G_CEN | |

**Control totals and who wins.** Tax accounts carry cash receipts from the Finance Accounts and State accounts as OFFICIAL control totals, but the SAM cells are on the NAS accrual concept and must sum to the SUT's product-tax vector (₹30,15,341 cr). Where the two disagree, **the SUT margin wins** and the cash–accrual/coverage gap is logged (GAP_MAP T1a, T2x). Phase 1 test: the sum of product-tax row targets equals ₹30,15,341 cr within a stated tolerance.

**In the multiplier engine** the product-tax rates are use-specific (decision D2a; valuation layer GAP_MAP P7b): GST is zero on exports and creditable on most intermediate use.

The divisible pool and **devolution** are *not* a tax account. They are an explicit G_CEN → G_STA transfer (₹11.29 lakh cr to states in 2023-24 per FC16 KFI item A.1.3; the Centre-side figure is to be reconciled). This makes the Finance Commission story a single visible cell.

## 6. Capital accounts (11) and inventories (1)

`K_HH` (all households: the 10 groups' saving is pooled here), `K_NFPU`, `K_NFPR`, `K_RBI`, `K_BANK`, `K_NBFC`, `K_INSP`, `K_MUTF`, `K_GCEN`, `K_GSTA`, `K_ROW` (RoW capital & financial account), plus `K_DSTK` (change in inventories by commodity).
- Rows receive gross saving (from current accounts), capital transfers and incurrence of liabilities (from instrument columns).
- Columns pay GFCF and valuables (to commodities), inventory changes (to K_DSTK), capital transfers, and acquisition of financial assets (to instrument rows).
- **Why households share one capital account:** saving by quintile is derived (income − outlays). Physical investment and portfolios by quintile have no source newer than AIDIS 2019. One K_HH keeps the FoF block official (NAS 5.3 household instrument flows). Wealth by quintile goes to an AIDIS-based satellite for the ABM.

## 7. Financial instruments (11)

Each instrument account's **column** pays the sectors that incur liabilities; its **row** receives from the sectors that acquire assets. Row total = column total, so each market clears.

**Data fit (checked in the FSF 2023-24 workbook).** RBI's FSF publishes a separate balance-sheet statement for each sub-sector. Each statement shows outstanding stocks and transactions by SNA instrument (F1–F8), with the counterparty sector for every instrument. The sub-sectors are:

| FSF statement | Sub-sector |
|---|---|
| 1.1 | RBI |
| 1.2 | ODCs |
| 1.3.1–1.3.5 | AIFIs, SFCs, SIDCs, NBFC-ND, HFC-ND |
| 1.3.6 | Mutual funds |
| 1.3.7 | Insurance and PF/pension (non-government) |
| 2.1 / 2.2 | Public / private NFCs |
| 3.1 / 3.2 | Centre / States |
| 4 | Households |
| 5 | Rest of the world |

Every capital account above therefore maps to one FSF sub-sector or a sum of them. The instruments map one-to-one, or by issuer:

| FSF instrument | SAM instrument |
|---|---|
| F1 | `I_RESV` |
| F21 | `I_CURR` |
| F22/F29 deposits | `I_DEPO` for bank deposits; `I_SSAV` where the issuer is government |
| F3 debt securities | `I_GSEC` where the issuer is government; `I_CBND` otherwise |
| F4 | `I_LOAN` |
| F51 | `I_EQTY` |
| F52 | `I_MFUN` |
| F6 | `I_INPE` |
| F8 and NEC | `I_OTHR` |

The from-whom-to-whom detail is not needed inside the SAM, because instrument accounts are pooled markets. It feeds the "who funds whom" satellite instead (GAP_MAP S4).

**Counterparty rule (keeps every market clearing).** FSF's own tables clear by construction. The SAM replaces two of FSF's sectors with other official sources: households with new-base NAS 5.3 (assets +1,56,816 and liabilities +33,765 against FSF), and RoW with BoP/NAS 6.1. For each instrument, the difference is posted to the **named counterparty in the same instrument**:
- extra household bank deposits become extra K_BANK liabilities in I_DEPO;
- extra small savings become K_GCEN liabilities in I_SSAV;
- extra PF/pension assets become K_INSP liabilities (EPF/NPS) or K_GCEN/K_GSTA liabilities (GPF) in I_INPE;
- and so on.

Only then is each sector's NAS-vs-FSF net-lending residual posted to I_OTHR (GAP_MAP K7b, K9). Phase 2 test: every I_* row equals its column before and after balancing, and every counterpart posting appears in BALANCING.md.

**HDFC merger.** HDFC Ltd (a housing finance company, inside OFCs) merged into HDFC Bank (inside ODCs) on 1 Jul 2023. In both FSF and NAS 5.3 this shows up as transactions: FSF household loans from OFCs fall from ₹3,43,354 cr to ₹1,208 cr, while NAS bank advances jump to ₹18,56,521 cr. Once the FSF notes confirm it is a reclassification, it is removed from the K_BANK/K_NBFC transaction cells and logged as an "other change in volume". The site shows household borrowing by lender both as published and merger-adjusted.

| Code | Instrument | Main issuers → holders | FoF / BoP link |
|---|---|---|---|
| I_CURR | Currency | RBI → households, NFCs, banks | FSF F2 (part) |
| I_DEPO | Deposits (incl. **NRI deposits**, CDs) | Banks/ODCs → HH, NFCs, government, RoW | FSF F2. The RoW row is tagged `bop:NRI_deposits` |
| I_LOAN | Loans & advances (incl. **ECB**, trade credit from RoW, Centre→State loans, RBI WMA) | Banks, NBFCs, RoW, G_CEN → NFCs, HH, G_STA | FSF F4. RoW column tagged `bop:ECB`, `bop:short_term_credit`, `bop:FDI_debt` |
| I_GSEC | Government securities (G-secs, SDLs, T-bills) | G_CEN, G_STA → banks, insurance, RBI, PF/pension, MFs, **FPI** | FSF F3 (govt); DEA ownership pattern |
| I_SSAV | Small savings & public-account deposits (NSSF, PPF, post-office) | G_CEN (NSSF) → HH | FSF F2/F8; NAS 5.3 "small savings etc." (₹3,09,751 cr) plus the PPF part of NAS "PF & pension" (Phase 1 check that PPF is not in both); **"who funds the deficit"** |
| I_CBND | Corporate debt securities & commercial paper | NFCs, NBFCs, banks → MFs, banks, insurance, FPI | FSF F3 (non-govt); SEBI HBS T11/T14 |
| I_EQTY | Equity & investment-fund shares other than MF units (listed/unlisted, incl. **FDI equity**, **FPI equity**, **ODI**) | NFCs, FCs, RoW → HH, MFs, insurance, RoW | FSF F5; BoP DI/PI |
| I_MFUN | Mutual fund units | K_MUTF → HH (retail + HNI), corporates, banks | FSF F5 (part); SEBI T72 |
| I_INPE | Insurance, pension & PF entitlements (life fund, EPF/EPS, NPS, CMPF, PF trusts, GPF) | E_INSP; G_CEN/G_STA for GPF → HH | FSF F6. NAS 5.3 insurance (₹6,49,086 cr) + PF & pension (₹7,23,027 cr) less PPF. Under the NAS convention (§4.5), contributions and withdrawals of funded schemes flow **only** here, not through current accounts |
| I_RESV | Reserve assets (RBI claims on RoW: FCA, gold, SDR, IMF reserve position) | RoW → RBI | BoP reserve assets (flow, **not** the WSS stock) |
| I_OTHR | Other accounts receivable/payable, **BoP errors & omissions**, each sector's FoF–NAS residual, and named timing items | all | FSF F8 + residuals. Includes the RBI surplus timing item: RBI's 2023-24 surplus of ₹2,10,874 cr is accrued in FSF as payable, while the Centre's cash receipt in 2023-24 was ₹87,416 cr (GAP_MAP R6, K9b). Logged, never silent |

**RoW functional categories (the SPEC's FDI/FPI/ECB/NRI stories)** are carried as a `bop_function` tag on the RoW cells of these instruments, not as separate accounts. The tags are: FDI (equity, debt, reinvested earnings), FPI (equity, debt), ECB, NRI deposits, trade credit, ODI, reserves, other. This avoids double-classifying one flow and keeps each instrument market clearing.

## 8. Where each institutional split lives

| Institution | Current accounts (production → income → saving) | Capital & financial (FoF) block |
|---|---|---|
| Households | **10** (R/U × quintile) | **1** (K_HH) |
| NFCs | 2 (public/private) | 2 |
| RBI | 1 | 1 |
| Banks (ODCs) | 1 | 1 |
| NBFCs/HFCs/AIFIs | 1 | 1 |
| Insurance & pension | 1 | 1 |
| Mutual funds | — (look-through) | 1 |
| Government | 2 (Centre, States incl. local) | 2 |
| RoW | 1 | 1 (+ `bop_function` tags) |

## 9. Statistical discrepancy: `X_DISC` (1)

Pinned, excluded from balancing, shown on the site. **Always exogenous in the multiplier model**, so the household residual never acts as a leakage from household income. In the UI its cells are rendered as reconciliation items ("statistical discrepancy", "NAS–BoP CIF reconciliation"), never as trade or transfer flows. Its 2023-24 entries come from published NAS figures (derivation in REFERENCE_YEAR §5). NAS 6.1 itself records imports unadjusted (₹71,59,405 cr), with the CIF adjustment shown separately as item 18, and the current-account surplus as −₹2,08,891 cr; so the R_ROW ← X_DISC cell is faithful to NAS. The alternative, keeping RoW on the NAS 1.1 basis (current account +₹3,609 cr) with the CIF gap in I_OTHR, is logged in ISSUES.md.

| Cell (row ← column) | Value 2023-24 (₹ cr) | Meaning |
|---|---|---|
| X_DISC ← H_* (households pay) | 5,71,133 | Household GDI (residual) exceeds PFCE + household saving. Allocated to the 10 groups pro rata to gross income (estimated allocation of an official total) |
| R_ROW ← X_DISC | 2,12,499 | NAS–BoP reconciliation: the CIF adjustment deducted from imports of services in NAS 1.1/SUT but not in the BoP-based net capital inflow |
| K_* ← X_DISC | 3,58,634 | Official saving–investment errors & omissions (GCF − saving − NCI). It first finances the 2,04,105 of valuables with no sector (assigned to K_HH); the remaining 1,54,529 goes to the sector(s) whose FSF net lending most disagrees with NAS, decided in Phase 2 and logged |
| X_DISC ↔ commodities | 0 in 2023-24 | GDP expenditure discrepancy (non-zero in FRE/PE years, e.g. −1,07,438 in 2024-25). The account exists so later years plug in without redesign |

## 10. Full account list and dimension

| Group | Codes | Count |
|---|---|---|
| Activities | A_CROP A_LVST A_FOFI A_COAL A_OILG A_OMIN A_FOOD A_BVTB A_TXAP A_WOOD A_GJOM A_RPET A_CHEM A_PHRM A_NMMN A_MTLS A_MACH A_ELEQ A_TREQ A_CNST A_UTIL A_TRAD A_HOTL A_TRNS A_COMM A_FINS A_INSR A_DWEL A_BSRE A_ITSV A_EDUC A_HLTH A_OSRV A_PADM | 34 |
| Commodities | C_ + the same 34 suffixes | 34 |
| Margins | M_TTM | 1 |
| Factors | F_LREG F_LCAS F_MIXD F_GOSC | 4 |
| Households | H_R1 H_R2 H_R3 H_R4 H_R5 H_U1 H_U2 H_U3 H_U4 H_U5 | 10 |
| Corporations (current) | E_NFPU E_NFPR E_RBI E_BANK E_NBFC E_INSP | 6 |
| Government | G_CEN G_STA | 2 |
| Taxes/subsidies | T_CGST T_SGST T_GCES T_CUST T_UEXC T_SVAT T_SEXC T_OPRT T_PSUB T_PROD T_PIT T_CIT | 12 |
| RoW current | R_ROW | 1 |
| Capital | K_HH K_NFPU K_NFPR K_RBI K_BANK K_NBFC K_INSP K_MUTF K_GCEN K_GSTA K_ROW | 11 |
| Inventories | K_DSTK | 1 |
| Instruments | I_CURR I_DEPO I_LOAN I_GSEC I_SSAV I_CBND I_EQTY I_MFUN I_INPE I_RESV I_OTHR | 11 |
| Discrepancy | X_DISC | 1 |
| **Total** | | **128** |

Matrix: 128 × 128 = 16,384 cells, of which roughly 2,000–2,500 are structurally non-zero (dominated by the 34×34 use and make blocks).

Removed after review: `T_IGST` (IGST is inside post-settlement CGST and SGST, as in NAS; its route is memo S7) and `T_STMP` (stamp duty is a production tax inside T_PROD, per S&M 2026).

## 11. Block diagram (which blocks are non-zero)

Rows receive, columns pay. Legend: **U** use at purchasers' prices · **V** make/supply at basic prices · **Mg** margins · **Tx** taxes/subsidies · **VA** value added · **Yf** factor income · **Tr** transfers/property income · **S** saving · **I** investment demand · **F** financial flows · **M** imports / RoW receipts · **X** exports / RoW payments · **D** discrepancy · — structurally zero.

| Row \ Col | ACT | COM | MRG | FAC | HH | NFC | FC | GOV | TAX | ROW | CAP | DSTK | INST | DISC |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **ACT** | — | V | — | — | — | — | — | — | — | — | — | — | — | — |
| **COM** | U | — | Mg (to TRAD, TRNS) | — | U (PFCE) | — | — | U (GFCE) | — | X (exports) | I (GFCF, valuables) | I (CIS) | — | (D: GDP discrepancy, 0 in 2023-24) |
| **MRG** | — | Mg | — | — | — | — | — | — | — | — | — | — | — | — |
| **FAC** | VA | — | — | — | — | — | — | — | — | Yf (CE from RoW) | — | — | — | — |
| **HH** | — | — | — | Yf (CE incl. imputed pension contributions; mixed income; household-sector GOS: imputed rent, actual rent to landlords, partnerships/NPISH) | Tr (small, intra-HH remittances: memo only, 0) | Tr (dividends, interest) | Tr (interest, D44 investment income attributed to policyholders/PF members, non-life claims) | Tr (OPS pensions D62, cash benefits D62/D7, interest, GPF/PPF D44) | — | Tr (remittances) | — | — | — | — |
| **NFC** | — | — | — | Yf (GOS) | Tr (small) | Tr (dividends/interest) | Tr (interest, non-life claims) | Tr (subsidy-like transfers, interest) | — | Tr (investment income) | — | — | — | — |
| **FC** | — | — | — | Yf (GOS) | Tr (interest, net non-life premiums) | Tr (interest, net non-life premiums) | Tr (inter-FC interest) | Tr (interest on G-secs) | — | Tr (reserve income, interest) | — | — | — | — |
| **GOV** | — | — | — | Yf (GOS = CFC) | Tr (fees, fines, imputed social contributions D612) | Tr (PSU dividends) | Tr (RBI surplus, cash basis; PSB dividends) | Tr (**devolution, grants**, cess-funded compensation and loan recovery) | Tx (tax receipts) | Tr (grants from abroad) | — | — | — | — |
| **TAX** | Tx (T_PROD) | Tx (product taxes, subsidies, import duties) | — | — | Tx (T_PIT) | Tx (T_CIT) | Tx (T_CIT) | — | — | — | — | — | — | — |
| **ROW** | — | M (imports CIF-adj.; residents' purchases abroad are already inside product rows) | — | Yf (CE to RoW) | Tr (outward remittances, gifts) | Tr (FDI income incl. reinvested earnings D43, interest) | Tr (interest, FDI income incl. D43) | Tr (interest on ext. debt, grants) | — | — | — | — | — | D (CIF reconciliation) |
| **CAP** | — | — | — | — | S | S | S | S | — | S (RoW saving = CAD) | Tr (capital transfers) | — | F (liabilities incurred) | D (S–I E&O) |
| **DSTK** | — | — | — | — | — | — | — | — | — | — | I (CIS by sector) | — | — | — |
| **INST** | — | — | — | — | — | — | — | — | — | — | F (assets acquired) | — | — | — |
| **DISC** | — | — | — | — | D (HH residual) | — | — | — | — | — | — | — | — | — |

## 12. Why this granularity

1. **The stories are all first-class cells or accounts.** Monsoon (A_CROP → F_MIXD → rural quintiles); oil shock (C_OILG imports → A_RPET → T_UEXC/T_SVAT → A_TRNS); construction (K_* → C_CNST → F_LCAS); IT exports (R_ROW → C_ITSV → F_LREG → urban top quintiles); gold (R_ROW ← C_GJOM → K_HH valuables); GST rupee (C_* → T_CGST/T_SGST/T_GCES → G_CEN/G_STA → devolution and compensation, with IGST settlement from memo S7 and incidence by use from P7b); free food (G_CEN GFCE on grain → households, satellite S8); deficit financing (K_GCEN ← I_GSEC/I_SSAV ← banks, insurance, RBI, households, FPI); remittances (R_ROW → H_*); FDI/FPI/ECB/NRI (tagged K_ROW ↔ instruments).
2. **Size matched to the data.** Every production account aligns with SUT industries and products, so the 34+34 blocks are ~100% official. Finer institutional splits than those chosen would each add mostly estimated cells: household occupation groups, 20 household deciles, separate NPISH, separate local bodies, separate MF current account.
3. **Computation.** Endogenous accounts for the multiplier model come to ≤ 110 (ACT, COM, MRG, FAC, HH, possibly NFC and taxes). X_DISC, CAP, INST, GOV and ROW are exogenous. A 110×110 inversion takes milliseconds in the browser (STACK_AND_REPO decision 13). The whole 128-account SAM is ~16k cells, trivially small as JSON. The engine's assumptions must be stated on the methodology page:
   - fixed prices and excess capacity;
   - fixed product mix per commodity (market shares);
   - fixed import shares by commodity;
   - use-specific product-tax rates (D2a).
4. **Extensible without redesign.** State-level regionalisation, household occupation splits, skill labour and a CFC/net satellite can all be added as sub-accounts or satellites. The codes are stable.

## 13. Decisions I need at Checkpoint A

1. Approve **34 A × 34 C** with the mapping above (or name sectors to split or merge).
2. Approve **4 factors** (regular/casual labour rather than skill).
3. Approve **10 households**, with NPISH folded in, and local bodies inside States.
4. Approve **MF in the financial block only** (look-through in current accounts).
5. Approve the **X_DISC treatment** (published residuals shown, not balanced away; always exogenous).
6. Approve **NAS conventions adopted after review**:
   - GST on a net, post-settlement basis with no T_IGST account;
   - stamp duty as a production tax;
   - food subsidy as government consumption, with FCI in G_CEN;
   - funded pensions, PF and life insurance as financial flows, plus D44 and imputed OPS contributions;
   - farm income support as a production subsidy by default.
7. Approve the **RBI surplus on the Union's cash basis** (₹87,416 cr in 2023-24), with the accrued difference shown as a timing item.
8. Approve **use-specific tax rates in the multiplier engine** (D2a), with the published SAM keeping taxes in commodity columns.
