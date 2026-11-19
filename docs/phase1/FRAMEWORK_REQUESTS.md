# Framework requests: Phase 1 close-out dispositions

Date: 2026-09-29. Scope: every "Framework request" in `docs/phase1/issues/*.md`, plus the framework items in `docs/phase1/ACCESS_PLAN.md` §3. Binding decisions: DECISIONS.md D1-1 to D1-9. The how-to for every change is in `docs/phase1/PIPELINE_GUIDE.md`; this file records **what was asked, what was done, and why**.

Status words: **DONE** (implemented and tested), **CLOSED** (settled by a decision, no code needed), **DEFERRED** (sensible, but nothing needs it yet), **REJECTED** (with the reason).

## 1. Summary

| # | From | Request | Status | Where |
|---|---|---|---|---|
| 1 | io_tables FR-1 | `PJ` and `KToE` energy units | DONE | `units.UNITS` |
| 2 | hces FR2 | `kg`, `gram`, `litre`, `metre`, `kWh` | DONE | `units.UNITS` |
| 3 | io_tables FR-2 | `EUR_million` | DONE | `units.UNITS`, runner unit checks |
| 4 | external_sector | `INR_per_EUR`, `INR_per_GBP`, `INR_per_JPY100`, `INR_per_SDR` | DEFERRED | §3 |
| 5 | hces FR4 | significant-digit rounding for percent/ratio rows | DONE (opt-in) | `Dataset.ratio_sig_digits` |
| 6 | hces FR1, labour FR-2 | survey-year periods (Jul-Jun, Aug-Jul, Oct-Sep) | DONE | period type `sy` |
| 7 | state_fiscal 1 (D1-9) | one shared State/UT code map | DONE | `pipeline/core/geo.py`, schema check |
| 8 | mospi_nas FR-1, labour FR-1, hces FR3, ACCESS_PLAN §3 | legacy TLS renegotiation for api.mospi.gov.in only (D1-6) | DONE | `fetch.LEGACY_RENEGOTIATION_HOSTS` |
| 9 | state_fiscal 3, rbi_banking, ACCESS_PLAN §3 | per-host minimum gap (rbidocs 10 s, D1-4) | DONE | `fetch.HOST_MIN_INTERVAL_S` |
| 10 | state_fiscal 3, ACCESS_PLAN §3 | stop a host at its first challenge (D1-4) | DONE | `ChallengeServed`, `FetchContext` |
| 11 | rbi_banking_corporate | public `ctx.is_pinned()` | DONE | `FetchContext.is_pinned` |
| 12 | union_fiscal FR-uf-2 (D1-7) | form-encoded POST for public keyless pages | DONE | `ctx.fetch(..., form_body=)` |
| 13 | trade_satellites | form POST with a same-session CSRF token (TradeStat) | REJECTED | D1-7 |
| 14 | external_sector | estimate stage `Partially Revised` | DONE | `schema.ESTIMATE_STAGES` |
| 15 | trade_satellites | reuse of an existing raw file must keep its sidecar's `retrieved_at`; repair trade_satellites-14 | DONE | `fetch.fetch_file`; pin repaired |
| 16 | trade_satellites | `PinStore.save` retry on Windows `PermissionError` | DONE | `fetch.PinStore.save` |
| 17 | io_tables FR-3, state_fiscal 2, union_fiscal FR-uf-3 | unit-scoped `repro` code hash | DONE | `manifest.unit_code_hashes`, `cli repro` |
| 18 | finsector_markets 3 | `check_identity` with missing parts as zero | DONE (opt-in) | `checks.check_identity(missing_parts_as_zero=)` |
| 19 | finsector_markets 1 | enforce NSDL/AMFI terms in code | DONE (in `policy.py`) | §3 |
| 20 | rbi_financial_accounts | prune pins that fetch() no longer requests | DONE (report + guarded `--prune`) | runner, CLI |
| 21 | finsector_markets 2 (fw-3) | raw archive (PFRDA regenerates files) | REJECTED here: owner question | §3 |
| 22 | io_tables FR-4 | IFPRI paper: registry addition or `PUBLIC_PARTS` | CLOSED by D1-8 | no code change |
| 23 | union_fiscal FR-uf-1 | PPAC landing page with a sign-in widget | CLOSED by D1-5 | no code change |

## 2. What was done (DONE items)

**Units of measure (1, 2, 3).** `PJ`, `KToE`, `kg`, `gram`, `litre`, `metre`, `kWh` and `EUR_million` are in `pipeline/core/units.UNITS`. `tonnes` stays as it is (existing data use it; one spelling only). The runner now also refuses a rupee caption on `EUR_million` rows, and rupee rows whose provenance caption is in euro (there is no euro exchange-rate series to convert with). `inr_unit_from_label` refuses euro captions, which it used to read as rupees (`"EUR million"` matched `million`).

**Significant digits (5).** Opt-in per dataset: `Dataset(..., ratio_sig_digits=9)` rounds that dataset's `percent` and `ratio` rows to 9 significant digits, but never to fewer than the default 6 decimals and never beyond 15, so opting in can only add precision. Other rows and every other dataset are rounded exactly as before (6 decimals), so no existing output changed. The setting is written to `_datasets.json`.

**Survey years (6).** New period type `sy`: the survey window as first and last month, `YYYY-MM/YYYY-MM` (`2023-08/2024-07` for HCES 2023-24, `2023-07/2024-06` for a PLFS/SAS agricultural year, `2023-10/2024-09` for ASUSE 2023-24). Helpers: `units.survey_period(start_year, start_month, months=12)`, `units.agricultural_year(start_year)`, and a new `units.period_end()` for every type. The label is unambiguous by itself, so the start and end dates need no extra columns. A separate `ay` (agricultural year written `2023-24`) was **not** added: it would look exactly like a fiscal year, and `sy` already covers July-June. Existing labour and HCES rows still use `fy` plus a `dim_other` note. Moving them to `sy` is a unit change, left to their owners (see §4).

**State/UT codes (7, D1-9).** `pipeline/core/geo.py` holds the 36 current ISO 3166-2:IN codes: 28 States and 8 UTs, as they stand after ISO's change of 23 Nov 2023 (IN-CT to IN-CG Chhattisgarh, IN-OR to IN-OD Odisha, IN-TG to IN-TS Telangana, IN-UT to IN-UK Uttarakhand), with Ladakh IN-LA (ISO 2019-11-22; a UT from 2019-10-31) and the merged UT IN-DH (ISO 2020-11-11; a UT from 2020-01-26). **Verified live on 2026-09-29** against two independent copies of the ISO list: Wikipedia "ISO 3166-2:IN" (code table and change log; page last edited 2026-09-21) and Debian iso-codes `data/iso_3166-2.json` (maintained from ISO; file last updated 2025-10-13, sha256 `78c90ef7...`). Both list exactly these 36 codes. The ISO Online Browsing Platform itself returned HTTP 403 to a non-browser client, so it was not used.
- Historical territories get non-ISO project codes `IN-X..` (three letters, so they can never collide with an ISO code): `IN-XAP` undivided Andhra Pradesh (to 1 Jun 2014), `IN-XJK` the State of J&K including Ladakh (to 30 Oct 2019), `IN-XDN` and `IN-XDD` (to 25 Jan 2020), and `IN-XMP`, `IN-XUP`, `IN-XBR` (to Nov 2000).
- Superseded codes (`IN-CT`, `IN-OR`, `IN-TG`, `IN-UT`, `IN-UL`, `IN-DD`, `IN-DN`) are refused with a hint.
- `geo.state_code(name)` maps printed names and variants (Orissa, Uttaranchal, NCT of Delhi, J&K, DNH&DD, ...) and never guesses.
- **The schema now rejects any `IN-..` geography outside this set.** Two units used the superseded `IN-CT` for Chhattisgarh (`mospi_nas_2026` and `state_fiscal`; `external_sector` and `hces_consumption` already used `IN-CG`). Their name maps were changed to `IN-CG` (a one-token edit per map), as D1-9 requires. The state_fiscal verifier's own copy of the map (`tests/verify/test_state_fiscal_spotcheck.py`) was changed the same way.

**Fetch layer (8-12, 14-16).**
- Legacy TLS renegotiation (`ssl.OP_LEGACY_SERVER_CONNECT`) is set only for hosts in `fetch.LEGACY_RENEGOTIATION_HOSTS` = {`api.mospi.gov.in`}, per hop (a redirect to another host gets the normal context). Certificate and host-name checks stay on. **Verified live, 2026-09-29:** without the opt-in, `https://api.mospi.gov.in/` fails with `UNSAFE_LEGACY_RENEGOTIATION_DISABLED`; with it, the request returns HTTP 200. No unit data were fetched: using the eSankhyiki API is up to the unit owners.
- `fetch.HOST_MIN_INTERVAL_S` = {`rbidocs.rbi.org.in`: 10 s}, enforced through the machine-wide host lock. This supersedes ACCESS_PLAN §3's earlier "5 s".
- A bot challenge now raises `ChallengeServed`, a subclass of `AccessBlocked`, so existing `except AccessBlocked` code still works. `FetchContext` then refuses every later request to that host in the same run, including redirect hops, without contacting it. A plain 403 is not a challenge (MoSPI answers 403 for missing files).
- `ctx.is_pinned(source_id, name, url=None)` says whether a `ctx.fetch` would reuse the local pinned copy.
- `ctx.fetch(..., method="POST", form_body={...})` sends `application/x-www-form-urlencoded` with navigation headers. The pin records `body_type: form` and the body hash; JSON and bodiless pins keep their original three keys, so no existing pin changed. Field names that look like credentials, sessions or CSRF tokens are refused before any request (D1-7).
- `Partially Revised` is in `ESTIMATE_STAGES`. external_sector still records RBI's "PR" as `Revised` until its owner switches (see §4).
- **Pin/meta timestamp bug.** When `fetch_file` reused a raw path that already held the same bytes and sidecar (an earlier run crashed after writing them but before saving the pin), the new pin got the current time while the sidecar kept the original. The pin now takes `retrieved_at` from the existing sidecar, and a sidecar whose sha256 disagrees with the file is an error. `PinStore.save` retries up to 6 times on Windows `PermissionError`.
- **Repair of trade_satellites-14.** The pin for `un_comtrade/ct_m_ag2_p634_251_202402.json` was changed through the `PinStore` API: `retrieved_at` went from 10:47:31Z to the original sidecar's 10:47:03Z. The script checked first that the file, pin and sidecar sha256 (`ae5fc37a...`), byte count (273,243) and URL all agree. Nothing else in the pin changed, and the raw file and sidecar were not touched.

**Unit-scoped repro (17).** `data/manifest.json` keeps the full `code_hash` and adds `unit_code_hashes`: one hash per built unit over `pipeline/*.py`, `pipeline/core/**`, `pipeline/ingest/__init__.py`, the unit's own files (`<unit>.py` or `<unit>/**`, `_<unit>_*.py`, `<unit>_coverage.yaml`) and `uv.lock`. `repro UNIT` fails only if one of the rebuilt units' hashes (the unit and its DEPENDS) changes between the three builds. A change elsewhere is reported as a note. `repro` with no unit still compares the full hash.

**check_identity (18).** `missing_parts_as_zero=True` counts an absent part as 0; a missing total is still reported, and failing groups list the zero-filled parts. The default is unchanged.

**Pins no longer requested (20).** After a successful `fetch`, the log lists pins the run never requested. `fetch UNIT --prune` removes them, but refuses if the run had any warning, because a skipped or challenged file must keep its pin. Raw files are never deleted. Automatic pruning was rejected: a run that stops at a challenge would silently lose pins the build needs.

**Terms-blocked sources (19).** ACCESS_PLAN §5 classes `nsdl_fpi_monitor` and `amfi_monthly_quarterly` as blocked-terms, but the registry says `access.requires: none`, so the code policy would have let a unit fetch them. That matters more now that form POSTs exist, because NSDL's export is an ASP.NET postback. Both ids and their hosts (`fpi.nsdl.co.in`, `amfiindia.com`) are now refused in `pipeline/core/policy.py`. No unit used them. NSE, BSE and CCIL were not refused, because ACCESS_PLAN §5 does not assess their terms. **Orchestrator follow-up:** also set `access.requires` for the two sources in `data/registry.yaml`, which this role does not edit.

## 3. Not done, and why

- **(4) Other currency rate units: DEFERRED.** The requester said "if any unit needs them"; none does. Adding `INR_per_EUR` etc. is only useful together with a conversion helper and the runner's rate-series check, which exist for dollars only. Add them together when Phase 2 needs a non-dollar conversion.
- **(13) TradeStat CSRF/session POST: REJECTED.** D1-7 keeps flows that need a server session and CSRF token out of scope. The `_token` field is refused in code. Trade by partner comes from IMF IMTS and the UN Comtrade preview; DGCI&S permission is an owner item.
- **(21) Raw archive: REJECTED at framework level (owner decision).** Where to keep raw bytes (STACK_AND_REPO §9 Q3) is an open owner question (fw-3). Until then a fresh clone cannot restore PFRDA's regenerated files. That is logged (finsector_markets-14, fw-3), not worked around.
- **(22) IFPRI vehicle: CLOSED.** D1-8 keeps the data paper as a registry addition, so `PUBLIC_PARTS` is not needed.
- **(23) PPAC: CLOSED.** D1-5: the registry's direct XLS URL is fetched. The landing page, which has a password field, is still refused by the login detector, which is correct.

## 4. Follow-ups for unit owners (not done here: they change unit outputs or tests)

- **io_tables:** adding `PJ` switched on the dataset the unit had already built, parsed and tested. `io_tables_energy_psut` (324 rows, Energy Statistics 2026 Tables 9.2A/B and 9.3A/B) is now written, and `test_psut_not_emitted_until_unit_exists` passes in its "unit exists" branch. Gap map S6 is **not yet declared** in `io_tables_coverage.yaml`: the owner must choose the extent and list the series. COVERAGE.md still says S6 is missing.
- **state_fiscal:** (a) undivided AP is `IN-AP` + `dim_other boundary=undivided`; the project convention is now `IN-XAP`. (b) J&K rows for 2013-14 to 2018-19 (state accounts, local-body assistance) are the former State including Ladakh, so they should be `IN-XJK`. (c) `fc16_kfi` has residual-AP and Telangana rows for 4 periods from 2011-12, before both existed on 2 Jun 2014. Check whether these are notional successor figures and label them so. FY 2019-20 J&K rows straddle the 31 Oct 2019 change.
- **external_sector:** the remittance survey's 2016-17 `IN-JK` row is the former State (`IN-XJK`). Switch RBI "PR" rows from `Revised` to `Partially Revised`.
- **labour_enterprise_surveys, hces_consumption:** move July-June, October-September and August-July survey rows from `fy` + `dim_other survey_year=...` to `sy`. The eSankhyiki API is now reachable (D1-6); whether to use it is the owner's call. hces may opt in to `ratio_sig_digits` for weight shares.
- **mospi_nas_2026:** the NAS API (back series) is now reachable through `ctx.fetch`.
- **rbi_banking_corporate, rbi_financial_accounts, state_fiscal:** the per-unit rbidocs gates (own 10 s sleeps, reading `ctx.store.pins`) now duplicate the framework. They still work, and can be simplified to `ctx.is_pinned` plus the framework's gap and challenge stop.
- **union_fiscal:** PIB `allRel.aspx` can now be posted to (D1-7), so union_fiscal-1 (GST releases) can be retried.

## 5. Effect on existing outputs (full offline build, 11 units ok)

188 of the 201 files in the pre-change manifest are byte-identical. Every difference is intended and was checked row by row against the committed versions:

| Unit | Files | Change |
|---|---|---|
| io_tables | `io_tables_energy_psut.parquet` (new, 324 rows), `_provenance.parquet` (+4 records), `_datasets.json` | the `PJ` unit now exists; no existing record or dataset changed |
| mospi_nas_2026 | `mospi_nas_2026_s4_1.parquet` | 6 Chhattisgarh rows: geography `IN-CT` to `IN-CG` (series ids unchanged); nothing else |
| state_fiscal | 7 datasets (kfi, local_body_assistance, state_accounts, subsidies, rbi_municipal, rbi_sf_statements, ulb_cityfinance) | 4,284 Chhattisgarh rows: geography `IN-CT` to `IN-CG` and `.in-ct` to `.in-cg` in series ids; identical otherwise |
| trade_satellites | `_provenance.parquet`, `comtrade_monthly_2324`, `comtrade_fy_2324` | the repaired pin's `retrieved_at` changes one official provenance record and the derived record that cites it, and so their prov_ids; 277 monthly and 235 FY rows point to the new ids; all values unchanged |

`data/manifest.json` also gains the `unit_code_hashes` section.

## 6. Verification at close-out

- `build` (all units, offline): 11 ok, 0 failed. `fetch --offline` (all units): 11 ok; no unit has pins that its fetch() no longer requests.
- `test` (all offline tests, final run): 2,928 passed, 22 xfailed, 11 failed. The 11 failures are the tests/verify spot-checks for external_sector (6) and union_fiscal (5) that already failed before this work: they compare against unit outputs that changed after verification (fw-22). The baseline run had 12 failures; the 12th was `test_pinned_raw_file[trade_satellites:un_comtrade/ct_m_ag2_p634_251_202402.json]`, which now passes.
- New framework tests: `tests/core/test_geo.py`, `tests/core/test_closeout_vocabulary.py`, and close-out sections in `tests/core/test_fetch.py` and `tests/core/test_runner.py` (all of tests/core passes).
- `repro` (all units): REPRO OK, 202 files byte-identical across PYTHONHASHSEED 0/1 and 1/4 threads, matching `data/manifest.json`. `repro io_tables` (unit-scoped path): REPRO OK, 10 files. `manifest --check`: up to date. ruff: clean on pipeline/core, pipeline/cli.py and tests/core, tests/raw, tests/hygiene.
- Live check (not a unit fetch): api.mospi.gov.in handshake fails without the legacy-TLS opt-in and returns HTTP 200 with it.

## 7. Close-out review dispositions (2026-09-29)

An independent reviewer re-ran build, tests and repro, checked the TLS scoping live, the ISO codes against Debian iso-codes, the pin repair, the `sy` periods and every changed output (1,094 values checked, 0 mismatched). No blocker or major finding. Six minor issues, each fixed or routed:

| # | Review issue | Disposition | What was done / evidence |
|---|---|---|---|
| R1 | §2 said "Ladakh IN-LA (2020)"; ISO added IN-LA on 2019-11-22 | **FIXED** (text only) | §2 now reads "IN-LA (ISO 2019-11-22; a UT from 2019-10-31)" and "IN-DH (ISO 2020-11-11; a UT from 2020-01-26)". PIPELINE_GUIDE §5.3 and `geo.py` give no ISO date, so they needed no change. Code set unchanged. |
| R2 | `io_tables_energy_psut` (324 rows, new) has no independent `tests/verify` check; S6 undeclared | **ACCEPTED, ROUTED** (not fixable by this role) | The framework maintainer must not verify it either (SPEC §3 rule 3): the dataset only appeared because of this role's `PJ` change. Logged as **io_tables-16** (verifier: a spot-check of about 10% against `es2026_chapter_9.pdf` pp. 12-15; owner: declare S6, io_tables-7). The reviewer's ad-hoc check (324/324 found in the PDF) is recorded there as evidence, not as a verification. |
| R3 | `code_hash` and unit hashes skipped `pipeline/ingest/mospi_nas_2026/spec_*.json`, which the unit reads at build time | **FIXED** | `manifest.CODE_SUFFIXES` now includes `.json` (and `.csv`, `.tsv`, `.txt`, `.toml` for future spec files). New test `test_every_build_input_under_pipeline_is_hashed` fails if any other file type appears under `pipeline/` or `models/`, and checks that both spec files are in the mospi_nas_2026 scoped hash. `code_hash` and all unit hashes changed once; all 202 data files byte-identical to the pre-fix manifest. Logged as fw-23 (RESOLVED). |
| R4 | No committed test for the per-hop TLS choice across a redirect, or for `stop_hosts` blocking a redirect hop | **FIXED** | `tests/core/test_fetch.py`: new route `/to-localhost` (127.0.0.1 -> localhost, same test server); `test_legacy_tls_is_chosen_per_redirect_hop` asserts contexts `[True, False]` with 127.0.0.1 listed and `[False, True]` with localhost listed; `test_challenged_host_is_not_contacted_on_a_redirect_hop` asserts `ChallengeServed` and that only the first hop reached the server. |
| R5 | The framework maintainer edited the verifier-owned `tests/verify/test_state_fiscal_spotcheck.py` (IN-CT -> IN-CG) | **ACCEPTED, ROUTED** | The edit stays: without it the check would look up a code the schema now rejects. The state_fiscal verifier must acknowledge or re-sign it; logged as **state_fiscal-22** (OPEN, verifier). Until then that one-token change counts as unverified. |
| R6 | `period_sort_key` ties for periods starting in the same month (two `sy` windows; `sy` vs its start month) | **FIXED** (documented + total-order key) | `period_sort_key` keeps its 3-tuple start-of-period contract (`period_start` and `period_end` unpack it) and its docstring now says it is not a total order. New `units.period_order_key` = start, then end (shorter first), then label: no two different periods tie. `checks.check_continuity`, the only framework caller that orders periods, now uses it. No output changed (the writer sorts on CLEAN_KEY strings). Tests: equal `period_sort_key` for `2023-07/2023-12`, `2023-07/2024-06` and `2023-07`; `period_order_key` sorts `[2023-24 fy, 2023-07, 2023-07/2023-12, 2023-07/2024-06]` the same way from three input orders. PIPELINE_GUIDE §5.2 updated. |

Re-run after these fixes (offline):
- `build` (all units): 11 ok, 0 failed. Against the manifest taken just before the rebuild: all 202 data files and all pins identical; only `code_hash` and `unit_code_hashes` changed (R3 and the `pipeline/core` edits).
- `test` (all offline tests): 2,931 passed, 22 xfailed, 11 failed. The 3 extra passes are the new tests (R3, R4 x2; R6 extends an existing test). The 11 failures are the same fw-22 tests/verify spot-checks (external_sector 6, union_fiscal 5).
- `repro` (all units): REPRO OK, 202 files byte-identical across PYTHONHASHSEED 0/1 and 1/4 threads, matching `data/manifest.json`. `repro mospi_nas_2026` (scoped path, now hashing its JSON specs): REPRO OK, 83 files. `manifest --check`: up to date.
- ruff check and format: clean on pipeline/core, pipeline/cli.py, tests/core, tests/raw, tests/hygiene. (`ruff check pipeline tests` as a whole still reports E501 in unit-owned files this work did not touch, e.g. `pipeline/ingest/external_sector/*.py`; not a framework item.)
