# Verification: the `capital_financial` block (SPEC s.3 rule 3)

Verifier: an independent agent (not the capital_financial builder or integrator), 2026-10-01.

Scope: the capital_financial block only: refs I1a, I2, I2a, I3a, K1, K4 (constraint), K7, K7a, K7b, K8, K8a, K8d, K9, K9b, D3; its 19 constraints, 24 checks, 10 satellites and 43 provenance records. I recomputed every entry, every constraint target and every check target from `data/clean` Parquet with DuckDB SQL, plain Python and numpy: my own RAS for I1a, and my own pairwise control-side reconciliation of the FSF 2023-24 leaf statements for K7/K8/K8d. I read only the dependency outputs the block is entitled to read (fincorp's `fc_public_private`, government's K8e entries, rest_of_world's `row_financial_counterparts` and R14a entries, households' `hh_keys`), plus all built blocks' `*_entries.parquet` for K9, market clearing and double counting. I did not import or call `pipeline/sam/blocks/capital_financial/` or any `pipeline.sam` module. I read the builder's `params.py` (the stated rules) and, after my K9 pair did not reproduce from the published decomposition, `residuals.py`, to see how the pair is grouped.

Regression test: `tests/verify/test_sam_capital_financial_spotcheck.py`: **19 passed, 3 xfailed**. The 3 xfails are conditional on V-CF-1 (the block is stale against government) and turn into ordinary passes once the block is rebuilt. The test imports neither `pipeline.sam` nor polars.

I ran the full offline suite once at the end (2026-10-01): 4,026 passed, 8 failed, 51 skipped, 32 xfailed. Three of the failures are V-CF-1:
- `test_sam_capital_financial.py::test_built_outputs_equal_a_fresh_build`;
- `::test_built_k_accounts_close_and_markets_clear`;
- `test_sam_audit.py::test_every_sam_provenance_input_resolves`.

The other five are not this block's: households hygiene; fincorp's fresh build, which is also stale against government; the framework broken-sibling test; and two timeseries tests.

Outputs checked: the build of 2026-10-01 00:04 IST (`capital_financial_*`: 444 entries, 19 constraints, 10 satellites, 24 checks, 43 records). While I was verifying, government was rebuilt at 00:15 and closure was first built at 00:16. Both matter below.

## Verdict

**Every number the block writes reproduces from clean data and the plan's rules. The FSF reconciliation, the largest and most novel part, matches cell by cell. One integration defect needs a rebuild now (V-CF-1). Three documentation and logging gaps are minor (V-CF-2 to V-CF-4).**

- **Entries: census, 444 of 444.** 209 of them are Rs 10,000 crore or more in absolute value.
  - I1a (130 entries): my RAS gives the same values to within Rs 0.00024 crore (convergence noise).
  - I2, I2a, I3a, D3 and K1 (18 entries): match to within 5e-7.
  - K7a/K8a (19 entries): exact.
  - K7b `hh_cp` (23) and `row_cp` (37): match to within 1e-6.
  - K7/K8/K8d (195 entries in 101 cells): all 101 cells match to within 2e-6.
  - K9 (20 entries): every account's net matches. The exception is K_GCEN/K_GSTA, which are off by ±1,594.81 against the current government outputs (V-CF-1).
  - K9b (2 entries): exact.
- **Constraint targets: census, 19 of 19.** Kind, tolerance and filters also match. 18 of the 19 hold on the assembled prior of all nine built blocks. `cf.k4.hh_saving` does not: it is short by 11,43,179.72, because closure's own K4a prior sums to 47,47,150.73. That shortfall is closure's, not this block's. The constraint is identical to closure's `k4.hh_saving_total` in rows, cols, refs, target, tolerance and kind.
- **Check targets: census, 24 of 24.** All recompute from clean records, and all pass.
- **Satellites.** Every recomputable row matches:
  - `fsf_instrument_closure` (24 rows);
  - `s4_fwtw_sam` (the 149 domestic pairs equal my reconciliation; row and column sums equal the entries);
  - `s4_fsf_dual_reports` (263 triples; the chosen value is the control side's report);
  - `s5_hh_wealth` (40 rows; totals equal T52(b) 4,14,70,111.9 / 1,21,30,649.0);
  - `s4_hdfc_merger_memo` (18 rows; merger effect 5,25,274 / 1,10,114);
  - `gg_gfcf_key`;
  - `capital_formation_by_account`;
  - `k9_decomposition` (its terms add up to K9 to 1e-3);
  - `k9_sensitivity`: `insurer_strip_off` and `d3_all_k_nfpu` are exact; `equity_issuer_control` matches to within Rs 127 crore on the three OFC accounts, where OFC-to-OFC pairs use a slightly different internal split convention, and exactly elsewhere.
- **Market clearing (all blocks' prior):** every I_* account except I_OTHR clears to Rs 0.00. I_OTHR is off by -0.25 (Walras). K_DSTK closes. Every domestic K account closes except K_GCEN (+1,594.81), K_GSTA (-1,594.81) and K_HH (closure's K4a, above).
- **Double counting:** no key is duplicated across blocks. The only cells this block shares with another block are the two Centre→States I_LOAN cells with government's K8e (-78,104). There, `dom` 1,19,895.65 + K8e = FSF 41,791.65 = Union AFS net 41,791.66, as planned.
- **Provenance:** every entry's status equals its record's, and every record is made for the entry's ref. All inputs resolve, except two `sam_government` ids cited by the K9 record, which government's 00:15 rebuild replaced (V-CF-1).

## 1. Method (what I recomputed, and how)

All values are 2023-24, Rs crore, current prices, latest vintage: NAS and SUT 2026-08-31; FSF 2026-01-21; Union FA and IGAS-2 2024-12-10; RBI SF 2026-01-23; RBI AR 2024-05-30; RTP 2024-12-26; T52 2026-09-25.

1. **I1a (plan s.2.2).**
   - Rows: SUT `use.gfcf.sut_pNNN` summed to commodities with the committed concordance (12 non-zero commodities, total 92,45,762.485522).
   - Columns: NAS 1.11 by sector × SUT/NAS (1.0000000028).
   - GG split by the key (Union capital outlay 8,07,180.34 − heads 5002/5003/5201/5225/5275/4416/5465-5467 3,22,595.17 + IGAS-2 autonomous-body capital grants 1,39,896.67 = 6,24,481.85, against States' outlay 7,47,305.79 + IGAS-2 ULB capital 1,479.24), which gives a Centre share of 0.4547418.
   - K_RBI = RBI AR Δ net fixed assets + depreciation = 1,431.69. The rest of FC is split by fincorp's F4a GOS by ownership part.
   - Prior = column total × the sector's NAS 1.11 asset share × SUT(c)/SUT(asset group); then RAS to 1e-13.
2. **I2, I2a, I3a, D3, K1 (s.2.3-2.5).**
   - I2 = NAS 1.9 gold (= 5.3).
   - I2a = SUT valuables − I2.
   - CIS = NAS 1.14 GCF − 1.11 GFCF by sector, × SUT CII / Σ. GG goes to K_GCEN. Private FC CIS is split by private-part I1a.
   - D3: K_HH = I2a. The remainder (NAS S-I E&O − I2a) goes pro rata to 1.14 corporate GCF, with FC split by I1a + I3a.
   - K1 = NAS 1.9 NFC saving.
3. **K7a, K8a, K7b households (s.2.8-2.9).**
   - K7a: one entry per NAS 5.3 line. PPF = NSSF `nssf.ppf.additions`, moved from PF & pension to I_SSAV.
   - K8a: the five NAS 5.3 liability lines.
   - `hh_cp`: each line posted on the counterparties' own FSF reports, using the absolute-share rule (deposit-takers' F22/F29 to hh; issuers' F51 to hh, with co-op shares going to K_BANK; States' F3 to hh with the rest to K_GCEN; FC lenders' F4 on hh excluding insurers; government by FSF hh F4).
4. **K7b RoW:** each `row_financial_counterparts` line with a named counterpart goes into the same instrument and value. Lines tagged `unallocated_k9` and I_RESV are not posted. FDI reinvested earnings equal R14a by payer.
5. **K7/K8/K8d (s.2.7), my own implementation.**
   - Leaf statements are aggregated to SAM accounts (ODC incl. HFC-DT → K_BANK).
   - Issuer control applies to F21, F22/F29 (I_SSAV where the issuer is GG) and F3 issued by GG. Holder control applies to F3 non-GG (I_CBND), F4 and F51.
   - Counterparty `fc_ofc` is split over K_NBFC/K_MUTF/K_INSP by the OFC accounts' opposite-side reports (absolute share).
   - Currency and deposits of `other_resident` and unallocated holders go to K_NFPR. hh and row cells are dropped.
   - Insurers' equity = 6,00,014.27 − (10,33,563.07 − 6,42,399.00) = 2,08,850.20, spread by the MF sector's domestic F51 issuer mix. PF equity is taken as published.
   - Centre→States loans: FSF − K8e.
   - MF units = 3,44,281.21 − NAS 2,85,052.00, spread over the other holders' F52 at account level, with SFC/SIDC excluded.
   - F81/F89: each account's own report (all − hh − row), with the RBI↔Centre F89 reduced by K9b 1,23,457.77.
6. **K9 (s.2.10):** row − column of each domestic K account over all blocks' prior entries excluding K9 and K4a, plus NAS K4 for K_HH.
7. **Sensitivities (T24):** the equity issuer-control variant and the insurer-strip-off variant, recomputed from my own pairs.

## 2. Values checked

| Item | Count | Result |
|---|---:|---|
| Entries (census) | 444 | all match (I1a max 2.4e-4; FSF cells max 2e-6; others ≤ 5e-7). K_GCEN/K_GSTA K9: V-CF-1 |
| of which ≥ Rs 10,000 crore | 209 | all in the census |
| FSF reconciliation cells (K7/K8/K8d) | 101 | all match. The pos/neg component partition inside a cell follows leaf-level pairs, which I checked through the sign and label rule, not value by value |
| Entry labels (status/role/tol/confidence) | 444 | all follow the plan: K1, K7a, K8a, I2, I2a, D3 fixed; control-side published pairs derived/anchored 0.10; keyed and non-control pairs estimated/free medium; `fsf_f8x` free low; K7b free high; K9 free low; K9b anchored 0.02; I3a NAS sectors anchored 0.001 |
| Constraint targets (census) | 19 | all match; 18 hold on the prior (K4: closure's K4a) |
| Check targets (census) | 24 | all match; all pass |
| Satellite rows checked | 1,873 + 360 | match: every row of `s4_fsf_dual_reports` (1,052), `s4_fwtw_fsf` (360, as published), `s4_fwtw_sam` (195), `s5_hh_wealth` (40), `fsf_instrument_closure` (24); the recomputable rows of the other five |
| Provenance records | 43 | status and ref consistent; 2 inputs unresolved (V-CF-1) |

**Builder's claims, confirmed:**
- K9 by account (prior): K_BANK -4,90,704.90; K_RBI +1,37,628.32; K_NBFC +1,36,532.77; K_NFPU +1,35,930.44; K_NFPR +92,726.68; K_HH +91,495.77 (= government K6 to K_HH 89,940.09 + RoW 1,555.69, D2-6); K_INSP +46,377.87; K_MUTF +22,428.88. K_GCEN and K_GSTA reproduce the builder's -11,095.42 and -2,00,272.67 only against the government outputs it read; against the current ones they are -9,500.60 and -2,01,867.49. The sum over sectors is -38,952.24 either way.
- `nas_vs_fsf` = real − FSF published leaf net financial transactions. I recomputed the FSF totals from leaf `total` rows, for example K_HH 15,69,860.28 and K_NFPU 26,301.83.
- The prior imbalances in the issues file match: E_NFPR +6,42,174.81. E_NFPU is now +2,45,292.64 after government's rebuild (+2,43,316.33 before). Neither is caused by this block, whose K1 is NAS 1.9 exactly.

**Plan s.8 and DECISIONS, confirmed:**
- XR-3/D2-6: K9_HH = capital transfers to households.
- XR-17: residual pairs.
- XR-27/D2-16: K9b method states the offset.
- XR-6: the FC split uses the GOS fallback.
- XR-19: component names.
- XR-15: `cf.i1a.gfcf.total` and `cf.valuables.total` dropped.
- XR-18/D2-10: households is in DEPENDS; S5 reads `aidis_fin_assets`/`aidis_inst_loans`/`aidis_noninst_loans`/`aidis_fixed_assets`.
- Plan s.8.9:
  - PPF only in I_SSAV;
  - D3 → K_HH = I2a to the paisa;
  - Centre→State `dom` 1,19,895.65;
  - FSF RoW-counterparty cells dropped;
  - GG inventories 100% K_GCEN.
- D2-8 (institutional view):
  - Followed where clean data allow: Union ULB capital grants go to the States; central autonomous bodies go to the Centre, as in factors' F4b.
  - CSS-society GFCF and NHAI's sector are logged as open (capital_financial-11).

## 3. Findings

| # | Severity | Finding | Evidence | Recommended fix | Logged by builder? |
|---|---|---|---|---|---|
| V-CF-1 | major | **The block is stale against government.** Government was rebuilt at 2026-10-01 00:15, after this block's 00:04 build. Its K6 now books the IGAS-2 capital grants to statutory bodies (1,594.81) as GG (V-GOV-7): the Centre's K6 to K_NFPU fell from 18,028.97 to 16,434.16, and the States' residual rose by the same amount. So K_GCEN (+1,594.81) and K_GSTA (-1,594.81) no longer close in the prior. The K9 record `sam_capital_financial:bc2fcec56232` cites `sam_government:2e1af9eeccf5` and `:771cadf28ca5`, which no longer exist. The block's own tests `test_built_outputs_equal_a_fresh_build` and `test_built_k_accounts_close_and_markets_clear` fail now (2 failed, 31 passed), and so will `test_sam_audit.py::test_every_sam_provenance_input_resolves` | Catalog `dependency_hashes.government.entries` = 72e7…; the file is now 9c47…. Recomputed K9_GCEN -9,500.60 (built -11,095.42), K9_GSTA -2,01,867.49 (built -2,00,272.67) | Rebuild now: `uv run python -m pipeline sam capital_financial`, or a full `sam`. For consistency with V-GOV-7, consider adding `gia.cash.statutory_bodies_and_development_authorities.capital_assets` (1,594.81) to the Centre's GFCF key (share effect about 0.06 pp) | Anticipated (capital_financial-26), not yet done |
| V-CF-2 | minor | **The K9 pair is not what the provenance method says.** The method says `residual_pos`/`residual_neg` are "the sum of the positive and the negative terms of its exact decomposition". But the published `term:*` rows of `k9_decomposition` do not reproduce the pair. The entries use a different grouping (household and domestic layers combined per instrument; RoW as one term), which is only in the module docstring. The grouping also fixes the gross size of the pair, and so how cheaply balancing can move K9. Example: K_INSP's published terms give +12,28,946 / -11,82,568; the entries are +4,99,354 / -4,52,976, on a net of +46,378. The published I_INPE terms split one difference (FSF F6 15,83,622 vs NAS-based 12,16,340) into two lakh-crore terms of opposite sign | `k9_decomposition` `pos`/`neg` rows equal the entries; Σ positive `term:*` ≠ `pos` for 9 of 10 accounts | State the grouping in the K9 provenance method, or publish the pair terms as their own rows. Say in the issues file that the pair's gross size is a weight choice (free low × gross) | No |
| V-CF-3 | minor | **G-sec issuance constraint targets under-cite their inputs.** `cf.k8.gsec_centre` (11,53,484.31) and `cf.k8.gsec_states` (6,80,742.28) replace FSF's household and RoW holders with NAS 5.3 G-secs (split Centre/States by this block's own FSF rule) and rest_of_world's FPI G-sec split by issuer. Their records (`899367ec8d68`, `0b518200b55d`) cite only the FSF Centre statement, and are `derived` although part of the target rests on estimated splits | Target = FSF F3 all − hh − row + posting; recomputed exactly | Add `mospi_nas_2026:6c29d7e7857c`, `rbi_financial_accounts` St 3.2 and the rest_of_world record(s) to the inputs. Consider `estimated`. capital_financial-24 already says these targets are not independent evidence | Partly (capital_financial-24) |
| V-CF-4 | minor | **Some FSF cells are dropped without a line in the issues file.** They are visible only inside `k9_decomposition`. They are: insurers' F61 non-life technical reserves 25,132.54 (liability), which NAS 5.3 has no line for; non-household F6 holdings (nfc_pub -280.09, ODC NBFC-DT 60.33); NBFC F6 liabilities (NBFC-DT 13.32, NBFC-ND 29.26, HFC-ND -0.40); and F52 liabilities of SFC/SIDC/HFC-ND (98.78). All fall into K9 (mainly K_INSP) | FSF St 1.3.7.1 f61 liabilities 25,132.54; SAM_GUIDE s.14 says "log every … dropped item" | Add one issues line listing them, with the K9 account each lands in | No (capital_financial-6 covers only VIII/IX items) |

Observations (not defects):
- **The K9 pairs are large.** Examples: K_BANK +6,38,998 / -11,29,703 on a net of -4,90,705; K_NFPU +7,54,432 / -6,18,502 on +1,35,930. Being free/low, they are the cheapest entries in every K account and in I_OTHR, so balancing will route most K-account and I_OTHR adjustment through K9. That is the intent (K9 is the residual). Expect many `explanations.yaml` items for them after the first full run (capital_financial-27).
- **E_NFPR/E_NFPU.** K1 is fixed at NAS, so the +6.4 / +2.5 lakh cr current-account surpluses the other blocks imply for NFCs will be absorbed by other E_NFPR/E_NFPU flows in balancing. The builder's diagnosis (a finding for fincorp, factors, taxes and rest_of_world) is right.
- **K_HH is short by 11,43,180 in the prior** because closure's K4a sums to 47,47,151 against the 58,90,330 target. This is closure's, and the free K4a entries carry it.
- **Rule sensitivity.** K9 depends at the lakh-crore level on the equity control rule and the insurer strip (capital_financial-22, recomputed here). The 2022-23 validation run (plan T24) is still open.
