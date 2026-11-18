# ACF and TB Mukt Bharat Campaign Study: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a pre-registered public study answering four questions:
- **Q1.** Are India's published active case-finding (ACF) and TB Mukt Bharat campaign figures internally and mutually consistent?
- **Q2.** Do definitions, windows or cut-off dates explain the disagreements?
- **Q3.** What is the state-level ACF yield?
- **Q4.** Did notifications rise more in states with more phase-1 campaign districts?

**Architecture:**
1. Task 0 locates the sources and decides the go/no-go for Q4 before registration. No figure values are extracted at this stage.
2. The dated analysis plan is pushed to a public repository; that push is the registration.
3. Official PDFs are fetched and verified by SHA-256, then extracted into sourced CSVs, with checks against printed totals.
4. A figure inventory and the source choices are frozen.
5. Q1–Q4 are computed and written to tracked outputs.
6. A verification suite runs.
7. A private manuscript is written.

**Tech stack:**
- Python 3.14 standard library for all analysis. pdfplumber is used for extraction only.
- pytest.
- pandoc and Word COM for the docx build.

**Spec:** `docs/superpowers/specs/2026-11-18-acf-campaign-design.md`. Its §9 holds binding decisions, so read it before any task.

## Global Constraints

**Data handling**
- Run every script as `python -I <script>`.
- Import pdfplumber only under `src/extract/`. Analysis modules must import without it.
- `data_raw/` and `manuscript/` are git-ignored. `outputs/` is tracked. Only `outputs/scratch/` is ignored. Write every CSV and JSON with LF line endings (`newline="\n"`, `lineterminator="\n"`). The repository has `.gitattributes` with `* text=auto eol=lf`.
- Every extracted row carries `source_file`, `pdf_page` (or paragraph) and `table_id`.
- Every count carries its `window_start`, `window_end` and `as_on` date. Only counts with the same window may be compared, under one of two cut-off rules (analysis plan §9.5):
  - two tables: each `as_on` within 60 days after its own window end;
  - a single-document contrast: one shared `as_on` within 60 days after the end of the later window.

**State names and code reuse**
- Canonical state names come from `src/states.py`, copied from tb_state_score with attribution. Unknown names raise an error.
- Bifurcated or merged units are combined to the coarser unit in every year compared. For example, Jammu and Kashmir is combined with Ladakh, and Dadra and Nagar Haveli with Daman and Diu.

**Downloads and website access**
- No download happens without the author's explicit permission, which states the file, source and size.
- The controller asks the author; implementers stop and report the list.
- No CAPTCHA or bot-protection circumvention, and no logged-in data.

**Pre-registration and numbers**
- The analysis plan is committed and pushed before any figure value is extracted.
- Any later change is a dated entry in plan §13 Deviations.
- Anything exploratory is labelled `exploratory` and logged in §13.
- No number may be typed into the manuscript. Every number is checked by `verification/check_manuscript_numbers.py`, which is mutation-tested.

**Statistics and language**
- Report no P values. Every estimate has a 95% interval and its n.
- No manuscript or committed text may narrate its drafting history or carry internal process IDs.

**Q4 fixed values (analysis plan §9–§10, which governs where it differs from spec §9)**
- **Primary outcome:** ln(N2025 / N2024), the full calendar years, from the "No. of TB cases notified" columns of RS Unstarred Q. 1216 (10 Feb 2026). It is one document with one shared cut-off.
- **Weights:** w = 1/(1/N2024 + 1/N2025).
- **Trend points:** 2019, 2022, 2023 and 2024; 2020 and 2021 are excluded.
  - 2019 comes from the India TB Report 2020, and 2022 from the India TB Report 2023.
  - 2023 and 2024 come from Q1216.
  - Fallback, for 2023 and 2024 together, used if the guard fails (a failure of Q1216's own extraction checks counts as a failed guard): 2023 from the India TB Report 2024, and 2024 from RS Q. 3467 (1 Apr 2025).
  - A state with no 2019 value uses the points from 2022 onward.
- **Guard:** each state's Q1216 2023 and 2024 counts are divided by its Q3467 "notified" counts.
  - The guard fails if the median 2023 ratio lies outside [0.95, 1.05], or the median 2024 ratio is below 0.95. A 2024 median above 1.05 is expected from late reports (Q3467 drawn about 3 months after 2024, Q1216 about 13 months after), does not fail the guard, and is reported descriptively.
  - A failure of Q1216's own extraction checks counts as a failed guard for every purpose.
  - On failure, Q1216 is judged not to be total notifications. The January–October pair (S8) then becomes primary, with the fallback trend; S8(a) and S8(b) run on it; and the full-year contrast is reported descriptively.
  - Any state outside [0.95, 1.05] in either year is a Q2 discrepancy.
  - If Q1216 passes extraction but either Q3467 fails extraction or fewer than 10 states have both values for either year, the guard is not run, and the full-year contrast stays primary; the paper says so.
- **Extraction checks for every Q4 source** (Q1216, Q3467, India TB Reports 2020/2023/2024, LS Q261, RS Q1093):
  - a table fails if its state rows do not sum to its printed total within ±1, or a needed column cannot be read; if no total is printed, the sum check is skipped and reported;
  - a trend source in use that fails leaves that year missing for every state, with no further substitution;
  - an outcome table that fails makes its contrast not computable.
- **S8, the January–October pair:** LS Starred Q. 261 (2024 Jan–Oct) against RS Q. 1093 (2025 Jan–Oct). It carries the lag analyses S8(a), a uniform scaling of the 2025 counts with weights fixed, and S8(b), the ln r covariate.
- **Placebo:** 2023 (Q1216, or the India TB Report 2024 under the fallback) against 2022 (India TB Report 2023), with the benchmark ln(N2022/N2019)/3.
- **Exposure:** the phase-1 district share, with the state denominator as the LGD count reconstructed at 7 Dec 2024. States with more campaign districts than LGD districts are capped at 1 and flagged (E5).
- **Bootstrap:** 10,000 draws over states sorted alphabetically by coarsened canonical name, seed 20261118.

## Review Focus

1. **Window or cut-off mismatch passed off as a change.** Two tables with different `as_on` dates or windows must never be compared silently. → Task 4 test `test_window_mismatch_refused`.
2. **Cumulative "screened" figures that shrink, or a percentage that does not recompute.** Each must be flagged as an arithmetic inconsistency with its source, never corrected silently. → Task 5 tests `test_cascade_monotonicity_flag` and `test_percentage_recompute_flag`.
3. **Indian number words.** "9.02 crore" and "3.01 lakh" in text sources must parse to 90,200,000 and 301,000, and "lakh" and "crore" spelling variants must be handled. → Task 3 test `test_parse_indian_magnitudes`.
4. **State splits and mergers across years.** Telangana is fine from 2014. Jammu and Kashmir with Ladakh, and Dadra and Nagar Haveli with Daman and Diu, must be combined before any join. → Task 3 test `test_coarsen_units`.
5. **A state with zero or very small counts in one window.** Its log ratio is undefined, or its weight extreme. A zero count makes the state not computable; it is listed, never set to 0. → Task 7 test `test_zero_count_not_computable`.

---

### Task 0: Source search and Q4 go/no-go (before registration)

**Files:**
- Create: `data/search_log.csv` with columns `site, query, date_searched, title, url, doc_date, doc_type, relevance, include, reason`.
- Create: `docs/source_search.md`.

**Rules:**
- Read and search only. Do not download. Do not record any figure value.
- Run the searches in spec §9.6 (sites, terms, 1 December 2022 to 18 November 2026).
- Locate:
  - the official phase-1 district list, or official per-state counts of campaign districts;
  - the LGD district counts at December 2024;
  - the parliamentary answers with state January–October tables for 2024, 2025 and, if any, 2023;
  - the India TB Report 2019 and 2022 pages;
  - CTD's "Active Case Finding" page;
  - the full text of the Global Health Action (GHA) 2023 quality study.
- `docs/source_search.md` records:
  - the Q4 gate outcome (GO with a list, GO with counts, or NO-GO), with sources;
  - the placebo choice (spec §9.5);
  - whether the January–October tables satisfy spec §9.2 (a)–(c), judged from document metadata and stated headings only, never from values;
  - the download list (file, URL, size from a HEAD request) for the controller to put to the author.

- [ ] **Step 1:** Search and fill `data/search_log.csv`.
- [ ] **Step 2:** Write `docs/source_search.md`.
- [ ] **Step 3:** Commit locally (`git init` happens in Task 1; until then the files stay unstaged). Report the gate outcome and the download list.

### Task 1: Repository, analysis plan and registration

**Files:**
- Create: `README.md`, `LICENSE` (MIT), `LICENSE-DATA` (CC BY 4.0), `.gitignore`, `.gitattributes`, `CITATION.cff`, `ENVIRONMENT.md`.
- Create: `docs/analysis_plan.md`.

**What `docs/analysis_plan.md` must fix, in numbered sections:**
- Q1–Q4, as in spec §2 and §6.
- The gate outcome and placebo from Task 0.
- The figure-inventory schema and the stopping rule.
- The consistency checks:
  - the cascade is monotone (screened ≥ presumptive ≥ tested ≥ diagnosed ≥ notified);
  - each percentage recomputes within its source's own rounding, which is half a unit in the last printed digit;
  - each total equals the sum of its parts within ±1;
  - a cumulative series never decreases.
- The discrepancy classes and their decision order (spec §6.2).
- The yield indicators and their intervals:
  - binomial Wilson intervals for proportions;
  - for the number needed to screen, the reciprocal of the Wilson bounds.
- The Q4 model:
  - the excess change, defined as the observed log ratio minus the state's fitted annual log growth over the trend points;
  - weighted least squares of the excess on exposure, with w as above;
  - intervals from the model and from the bootstrap;
  - the sensitivity list (spec §6.4);
  - the placebo;
  - the descriptive fallback if spec §9.2 (a)–(c) fail.
- §13 Deviations, empty and dated.

**Data seen before the plan:** document titles and metadata only, as recorded in `docs/source_search.md`.

- [ ] **Step 1:** `git init -b main`. Write the files. Commit "docs: pre-registered analysis plan, before any figure was extracted", together with the design, this plan, `search_log.csv` and `source_search.md`.
- [ ] **Step 2 (controller):** run `gh repo create hssling/india-tb-acf-campaign --public --source . --push`. Record the push time from the GitHub API (`pushed_at`). Save the registration event to `docs/registration_event.json`, and record the registration point in §13.

### Task 2: Fetch, manifest and copied primitives

**Files:**
- Create:
  - `tools/fetch_sources.py`;
  - `data/source_manifest.csv` with columns `file, url, bytes, sha256, retrieved_utc`;
  - `src/states.py`, `src/extract/pdftext.py`, `src/extract/cells.py`, each copied from tb_state_score with an attribution header;
  - `pytest.ini`;
  - tests.

**Interfaces:**
- Produces:
  - `fetch_sources.verify(path, sha256) -> None` and `main() -> int`;
  - `states.canonical(name) -> str`;
  - `states.coarsen(name) -> str`, which maps Ladakh to "Jammu and Kashmir (incl. Ladakh)", and so on;
  - `cells.parse_int`, `parse_count` and `parse_n_pct`;
  - `cells.parse_magnitude(text) -> int`, for crore and lakh.

- [ ] **Step 1:** Write the tests:
  - `test_verify_rejects_tampered_file`;
  - `test_coarsen_units`;
  - `test_parse_indian_magnitudes`: `parse_magnitude("9.02 crore") == 90_200_000`, `parse_magnitude("3.01 lakh") == 301_000`, `parse_magnitude("12.97 Crore") == 129_700_000`;
  - `test_canonical_rejects_unknown`.
- [ ] **Step 2:** Run them and see RED.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run them and see GREEN.
- [ ] **Step 5 (controller):** get the author's permission for the Task 0 download list. Download with `fetch_sources`. Commit the manifest and code.

### Task 3: Extraction to the figure inventory and source choices

**Files:**
- Create:
  - `src/extract/itr.py`, which reads ACF tables and annual state notifications from India TB Reports 2019–2024;
  - `src/extract/pq.py`, which reads parliamentary-answer tables: the full-year Q1216 and Q3467 tables, the state January–October windows, and state ACF tables. RS Q. 3477 (1 Apr 2025, campaign activities) is read for the figure inventory;
  - `src/extract/campaign.py`, which reads the CTD campaign PDF and official PIB figures;
  - `src/extract/quality_studies.py`, which reads the published GHA 2023 and PGPH 2025 indicators with their stated denominators;
  - `data/extracted/*.csv`;
  - `data/figures_inventory.csv`;
  - `data/source_choices.csv`;
  - tests.

**`figures_inventory.csv` columns** (analysis plan §5.2): `fig_id, quantity, value, value_printed, qualifier, unit, definition_verbatim, context_verbatim, definition_class, scope, series_type, window_label, window_start, window_end, as_on, as_on_basis, geography, source_file, source_url, page_or_para, table_id, pub_date, note`.

**Rules:**
- Check every table against its printed national total. For the Q4 source tables, apply the extraction checks of analysis plan §9.6 and record each pass or failure in `source_choices.csv`.
- Keep blanks blank.
- Name every state through `canonical`.
- Commit `source_choices.csv` before any Q computation (the freeze rule).

- [ ] **Step 1:** Write the tests:
  - for each extractor, a printed-total check;
  - `test_q4_source_extraction_checks`:
    - a Q4 table whose state rows differ from its printed total by 2 fails, and one that differs by 1 passes;
    - a missing needed column fails;
    - a table with no printed total skips the sum check and reports it;
    - a failed trend source gives a missing year for every state and no substitute;
    - a failed outcome table gives contrast not computable;
  - `test_inventory_rows_sourced`: no empty `source_file` or `page_or_para`;
  - `test_window_fields_present`.
- [ ] **Step 2:** RED, implement, GREEN.
- [ ] **Step 3:** Commit the CSVs and code. Make no comparisons.

### Task 4: Comparability layer

**Files:**
- Create: `src/compare.py` and its tests.

**Interfaces:**
- Produces:
  - `comparable(a: dict, b: dict) -> tuple[bool, str]`. It requires all of these:
    - the same quantity in the same words from the same source (analysis plan §9.5);
    - windows of the same length and calendar span;
    - either each `as_on` within 60 days of its own window end, or, for a single-document contrast, one shared `as_on` within 60 days after the end of the later window;
  - `full_year_pairs(rows) -> dict[state, (N2024, N2025)]` for the primary contrast, and `jan_oct_pairs(rows) -> dict[state, (a, b)]` for S8.

- [ ] **Step 1:** Write the tests:
  - `test_window_mismatch_refused`;
  - `test_asof_beyond_60_days_refused`;
  - `test_different_wording_or_source_refused`;
  - `test_single_document_shared_cutoff_accepted`: two columns of one document with one shared `as_on` 40 days after the end of the later window are accepted. The same columns with a shared `as_on` 70 days after it are refused.
- [ ] **Step 2:** RED, implement, GREEN.
- [ ] **Step 3:** Commit.

### Task 5: Q1 consistency and Q2 reconciliation

**Files:**
- Create:
  - `src/q1_consistency.py`;
  - `src/q2_reconcile.py`;
  - `outputs/q1_checks.csv` (one row per check per source: check, inputs, expected, observed, pass, note);
  - `outputs/q2_discrepancies.csv` (one row per cross-source discrepancy, with its class in decision order and the evidence);
  - `outputs/q2_quality_studies.csv` (the two studies' indicators recomputed on common definitions where their tables allow);
  - tests.

- [ ] **Step 1:** Write the tests:
  - `test_cascade_monotonicity_flag`;
  - `test_percentage_recompute_flag`: 3.7% stated where 37/1000 gives 3.7% passes; 4.0% stated fails;
  - `test_sum_of_parts_tolerance`;
  - `test_decision_order` (arithmetic before definition before window before unexplained);
  - `test_unexplained_is_a_class_not_an_error`.
- [ ] **Step 2:** RED, implement, GREEN.
- [ ] **Step 3:** Run both scripts and commit the outputs.

### Task 6: Q3 yield

**Files:**
- Create: `src/q3_yield.py`, `outputs/q3_yield.csv` and tests.

- [ ] **Step 1:** Write the tests:
  - `test_wilson_interval_known_values`;
  - `test_nns_reciprocal_bounds`;
  - `test_missing_state_listed_not_imputed`.
- [ ] **Step 2:** RED, implement, GREEN.
- [ ] **Step 3:** Run, then commit.

### Task 7: Q4 dose-response (only if the gate is GO)

**Files:**
- Create: `src/q4_dose_response.py`, `outputs/q4_states.csv`, `outputs/q4_summary.csv` and tests.

**Interfaces:**
- Consumes: `compare.full_year_pairs`, `compare.jan_oct_pairs`, the extracted annual notifications, the Q3467 table for the guard, and the exposure from the `source_search.md` sources.
- Produces:
  - `excess(state) -> float | None`;
  - `wls(x, y, w) -> (slope, se, n)`;
  - `guard(q1216, q3467, q1216_extraction_ok, q3467_extraction_ok) -> (status, medians, flagged_states)`, where status is pass, fail or not_run. It returns fail whenever Q1216's extraction checks failed;
  - `bootstrap_ci(...)`.

**Order of analyses:**
1. The guard.
2. The primary analysis: the full-year contrast, or the January–October contrast if the guard fails (including a failure of Q1216's extraction checks), with the fallback trend.
3. S1–S7.
4. S8 (the January–October contrast, if it is not already primary) with its lag analyses S8(a) and S8(b). If S8 is primary, S8(a) and S8(b) are then run on the primary analysis.
5. The placebo.

**Rules:** state the spread of exposure (SD and range) and n. If the comparability conditions of analysis plan §9.5 fail for the primary contrast, write only the descriptive table and the reason.

- [ ] **Step 1:** Write the tests:
  - `test_zero_count_not_computable`;
  - `test_trend_points_exclude_2020_2021`;
  - `test_trend_fallback_2022_2024` (a state with no 2019 value uses the points from 2022 onward);
  - `test_guard_median_ratio_bounds`:
    - a 2023 median of 1.00 with a 2024 median of 1.00 passes;
    - a 2023 median of 0.94 fails;
    - a 2024 median of 1.08 passes (with 2023 at 1.00), and is reported descriptively;
    - a 2024 median of 0.94 fails;
    - a failure of Q1216's extraction checks gives fail, whatever the medians;
    - a failed guard switches the primary to the January–October contrast and the trend to the fallback sources;
    - fewer than 10 states with both values for either year gives not_run, with the full-year contrast still primary;
  - `test_wls_known_values`;
  - `test_bootstrap_seeded_reproducible`;
  - `test_placebo_uses_gate_choice`.
- [ ] **Step 2:** RED, implement, GREEN.
- [ ] **Step 3:** Run the primary analysis, the sensitivities and the placebo. Commit.

### Task 8: Verification suite

**Files:**
- Copy and adapt from tb_state_score:
  - `verification/check_all.py`;
  - `check_plan_order.py` (git-less archive gives SKIP);
  - `check_deviations.py`;
  - `check_extraction_totals.py`;
  - `MUTATIONS.md`.
- Add `verification/check_inventory.py`: every inventory row resolves to a source file in the manifest, and every analysis input row is in the inventory or the extracted CSVs.

- [ ] **Step 1:** Write the checks and their tests.
- [ ] **Step 2:** Run each mutation (an edited value, a pre-§13 plan edit in a scratch clone, an unlogged exploratory label, a failing test) and confirm it is caught. Record the result in `MUTATIONS.md`.
- [ ] **Step 3:** Commit. The controller asks the author before pushing.

### Task 9: Manuscript

The controller first asks the author to choose the journal from spec §6.5's candidates, then confirms the journal's no-APC model and its rules from the journal's own guidelines.

**Parts:**
- (a) Journal rules, plus `exhibits/make_tables.py` and `make_figures.py`, both committed. Within the journal's limits, the exhibits cover:
  - the inventory and consistency summary;
  - the discrepancy classes;
  - the yield;
  - the Q4 result;
  - a figure of the official figures by source and date;
  - a Q4 scatter plot with the fit.
- (b) Prose. The manuscript is private and blinded if the journal requires it. It comes with the first-page file and the reporting checklist (RECORD), and references verified through Crossref. `check_manuscript_numbers.py` uses section-scoped phrases and a golden numeric skeleton.
- (c) The docx build, Word render QA, a docx-to-markdown tie check, and a mutation harness in which every change must be caught.

Each part is reviewed before the next.
