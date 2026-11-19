# Where Active Case Finding Still Pays — Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register and run three policy-guiding analyses (D1 yield/saturation/cascade, D2 targeting, D3 additionality) on the verified State panel, with robustness, verification, a reframed Public Health manuscript and release v1.1.0.

**Architecture:** A State × year panel builder feeds three analysis modules and one robustness module under `src/ext/`, writing to `outputs/ext/`. Verification gains an independent recomputation of the headline estimates and a registration-order check for the extension. The manuscript is rebuilt locally under `manuscript/ext/` with the existing build and check tooling made path-configurable.

**Tech Stack:** Python 3.14; numpy 2.3.5 and scipy 1.16.3 (extension only); pytest 9; existing tools (python-docx, matplotlib, openpyxl, PyMuPDF, Pillow, Word via PowerShell).

**Spec:** `docs/superpowers/specs/2026-11-19-acf-extension-design.md` (§9 holds the settled calls).

## Global Constraints

- Run every script as `python -I <script>`; LF line endings; seeds fixed; outputs byte-reproducible.
- numpy/scipy only under `src/ext/` and `verification/check_ext_outputs.py`; the v1.0.0 pipeline stays standard-library only and must still reproduce byte-identically.
- Units: §9.4 coarsened units of `docs/analysis_plan.md` in every year; merged units summed.
- NA cells listed, never imputed. Zero diagnoses excluded from log-scale analyses and listed (main); +0.5 continuity correction is a specification-curve axis only.
- Seed `20261119` for every random procedure in the extension; 10,000 bootstrap draws, 10,000 parametric rank draws, 10,000 permutations; `numpy.random.default_rng(20261119)` reset before each analysis.
- Every estimate has a 95% interval; no P values; no causal wording in outputs or prose.
- Main exposure: reconstructed denominator (`data/extracted/exposure_share_reconstructed.csv`); registered denominator descriptive and a specification axis.
- Small UTs (for exclusion axes): Andaman and Nicobar Islands; Chandigarh; Dadra and Nagar Haveli and Daman and Diu; Lakshadweep; Puducherry.
- Hard gate: no §4 estimate is computed before `docs/extension_plan.md` is pushed and `docs/registration_event_ext.json` records it (controller step, Task 1).
- `manuscript/` is git-ignored and never committed; no manuscript sentence in a tracked file; private check phrases live in `manuscript/ext/section_phrases.json`.
- Journal: Public Health (Elsevier) — ≤3,000 words, ≤5 display items, ≤50 references, structured abstract ≤250 words (Objectives, Study design, Methods, Results, Conclusions), AMA, British English, double-blind.
- Release v1.1.0 under concept DOI 10.5281/zenodo.24371584; the manuscript cites the v1.1.0 version DOI.
- No downloads; no new data.

## Review Focus

1. A State present in some years and absent in others (unbalanced panel): fixed-effects and pooling code must use the available years, not silently drop the State — `test_unbalanced_panel_kept` (Task 2) and `test_fe_unbalanced` (Task 4).
2. Zero or NA diagnoses in a year (2023: Andaman and Nicobar, Goa, Lakshadweep; Manipur NA): excluded from log models and listed with reason — `test_zero_and_na_listed` (Task 2).
3. The 2022 "tested" column is "symptomatic identified and examined": never pooled with "tested" in the main decomposition — `test_decomposition_excludes_2022_main` (Task 4).
4. Extreme between-State heterogeneity (τ² large): tiers must still be computed against the pooled mean, and the tier call must use the State's own interval — `test_tier_rule_uses_state_interval` (Task 3).
5. Degenerate bootstrap draws (all resampled States identical in a covariate, singular design): counted, excluded and reported — `test_degenerate_draws_counted` (Task 6).

---

### Task 1: Extension analysis plan and registration gate

**Files:**
- Create: `docs/extension_plan.md`; `docs/registration_event_ext.json` (controller, after push)
- Modify: `docs/superpowers/specs/2026-11-19-acf-extension-design.md` (none, read only)

**Interfaces:**
- Produces: the binding choices every later task reads (sections named below).

- [ ] **Step 1:** Write `docs/extension_plan.md` with these sections, values verbatim from the spec §4 and §9 and these Global Constraints: 1 Questions (D1–D3); 2 What had been seen (State diagnosed/screened by year in `outputs/q3_yield.csv`; no §4 estimate); 3 Data and units; 4 D1 estimators (DL random effects on log-yield with binomial variance `1/D − 1/S`; empirical-Bayes shrinkage; tiers; elasticity with State and year fixed effects, weights `D`; cascade decomposition, years 2018, 2019, 2021, 2023, 2022 as sensitivity, covariance split equally); 5 D2 (Spearman of exposure vs pooled 2021–2023 shrunken yield; tier shares; 10% marginal shift from the "below" tier to the "above" tier in proportion to 2023 volume, expected change `Σ D_s[(1+r_s)^ε − 1]`); 6 D3 (public notifications on ACF diagnoses, State and year fixed effects, years 2019, 2022, 2023, absolute and log scales); 7 Robustness (the three specification grids in Task 6, nulls 1/0/0, LOO, permutation); 8 Interpretation rules (an estimate is "supported" only if its 95% interval excludes its null in the main specification AND ≥80% of its specification-curve entries agree in sign; otherwise "not established"); 9 Seeds and reproducibility; 10 Deviations (dated, appended only).
- [ ] **Step 2:** Run `python -I verification/check_all.py`; expected: all PASS (the plan changes no code).
- [ ] **Step 3:** Commit `docs/extension_plan.md` ("docs: extension analysis plan (registered before any extension estimate)").
- [ ] **Step 4 (controller):** push; read `pushed_at` from the GitHub API; write `docs/registration_event_ext.json` {repository, registered_document, registered_commit, pushed_at, figures_computed_before: false}; commit and push.

### Task 2: State × year panel

**Files:**
- Create: `src/ext/__init__.py`, `src/ext/panel.py`, `data/ext/panel.csv`, `data/ext/panel_exclusions.csv`
- Test: `tests/test_ext_panel.py`

**Interfaces:**
- Consumes: `data/extracted/itr2019_a1_7_acf.csv`, `itr2020_a6_acf.csv`, `itr2022_a6_acf.csv`, `itr2023_a6_acf.csv`, `itr2024_a6_acf.csv`, `itr2020_a1_2.csv`, `itr2023_a1_2.csv`, `itr2024_a1_2.csv`, `pq_q1216.csv`, both exposure-share files; `src/states.py` coarsening.
- Produces: `load_panel() -> list[dict]` with keys `unit, year, screened, tested, tested_definition ('tested'|'examined'), diagnosed, notified_public, notified_private, notified_total, est_population, exposure_reconstructed, exposure_registered, small_ut (bool), flags (str)`; `exclusions() -> list[dict]` (`unit, year, field, reason`).

- [ ] **Step 1:** Tests:
  - `test_units_coarsened` (no row named Ladakh, Daman and Diu, or Dadra and Nagar Haveli alone; merged values equal the sum of the parts in the source CSVs);
  - `test_year_sources` (2018←ITR2019, 2019←ITR2020, 2021←ITR2022, 2022←ITR2023 with `tested_definition == 'examined'`, 2023←ITR2024);
  - `test_unbalanced_panel_kept` (a unit missing in one year keeps its other years);
  - `test_zero_and_na_listed` (2023 Andaman and Nicobar, Goa, Lakshadweep zeros and Manipur NA appear in `exclusions()` with reasons; their rows keep the printed values);
  - `test_national_totals` (summing units reproduces the national diagnosed and screened used in `outputs/q3_yield_summary.csv` for each year, within the known ITR2023 gap noted in its flags).
- [ ] **Step 2:** Run `python -I -m pytest tests/test_ext_panel.py -q`; expected FAIL (module missing).
- [ ] **Step 3:** Implement `src/ext/panel.py`; write both CSVs with `python -I src/ext/panel.py`.
- [ ] **Step 4:** Rerun the tests; expected PASS.
- [ ] **Step 5:** Commit.

### Task 3: D1 pooled yield, shrinkage and tiers

**Files:**
- Create: `src/ext/d1_yield.py`, `outputs/ext/d1_pooled.csv`, `outputs/ext/d1_states.csv`
- Test: `tests/test_ext_d1_yield.py`

**Interfaces:**
- Consumes: `panel.load_panel()`.
- Produces: `dl_pool(y: np.ndarray, v: np.ndarray) -> dict` (mu, se, ci, tau2, i2, pi); `eb_shrink(y, v, mu, tau2) -> (post_mean, post_sd)`; `rank_intervals(post_mean, post_sd, rng, draws=10000) -> (lo, hi)`; `tier(lo_ci: float, hi_ci: float, mu: float) -> 'above'|'overlaps'|'below'`; `pooled_state_yield(unit) -> (log_yield, se)` for 2021–2023 (used by Task 5).

- [ ] **Step 1:** Tests:
  - `test_dl_known_values` (a published three-study example: assert μ, τ² and I² to 4 decimals against hand computation in the test);
  - `test_eb_shrinks_small_states_more` (larger v ⇒ posterior closer to μ);
  - `test_rank_intervals_reproducible` (same seed ⇒ identical output);
  - `test_tier_rule_uses_state_interval` (interval wholly above μ ⇒ 'above'; straddling ⇒ 'overlaps'; with τ² = 10 the rule still uses the State's own interval);
  - `test_outputs_have_intervals` (every row of both outputs has lower and upper bounds).
- [ ] **Step 2:** Run, expect FAIL.
- [ ] **Step 3:** Implement; log-yield `ln(D/S)` with variance `1/D − 1/S`; run to write outputs.
- [ ] **Step 4:** Run, expect PASS.
- [ ] **Step 5:** Commit.

### Task 4: D1 saturation (elasticity) and cascade decomposition

**Files:**
- Create: `src/ext/d1_saturation.py`, `outputs/ext/d1_elasticity.csv`, `outputs/ext/d1_decomposition.csv`
- Test: `tests/test_ext_d1_saturation.py`

**Interfaces:**
- Consumes: `panel.load_panel()`.
- Produces: `fe_wls(y, x, unit, year, w) -> (beta, n)`; `elasticity(rows, weights='D', zero='exclude', years=None, units=None, stratum=None) -> dict` (beta, model CI, cluster-bootstrap CI, n_units, n_obs, degenerate); `intensity_strata(rows) -> dict[unit, 'high'|'low']` (screened per estimated population, 2019/2021 populations carried forward, split at the median; used for the stratified elasticity and tier sensitivity); `poisson_fe_elasticity(rows) -> dict`; `decompose_change(rows, y0=2021, y1=2023) -> dict` (dln_yield, testing_part, positivity_part); `decompose_variance(rows, year) -> dict` (var_total, testing_share, positivity_share).

- [ ] **Step 1:** Tests:
  - `test_fe_recovers_known_slope` (synthetic panel with slope 0.7 ⇒ 0.7 ± 1e-9);
  - `test_fe_unbalanced` (one unit missing a year still estimates);
  - `test_decomposition_adds_up` (testing + positivity parts equal the change to 1e-12; variance shares sum to 1);
  - `test_decomposition_excludes_2022_main` (main output has no 2022 row; the sensitivity file marks 2022 'examined');
  - `test_cluster_bootstrap_resamples_units`.
- [ ] **Step 2–4:** FAIL, implement, PASS; write outputs (main and sensitivity rows labelled).
- [ ] **Step 5:** Commit.

### Task 5: D2 targeting alignment and marginal-shift scenario

**Files:**
- Create: `src/ext/d2_targeting.py`, `outputs/ext/d2_alignment.csv`, `outputs/ext/d2_scenario.csv`
- Test: `tests/test_ext_d2.py`

**Interfaces:**
- Consumes: `d1_yield.pooled_state_yield`, `d1_yield.tier`, `d1_saturation.elasticity` (bootstrap draws), panel exposure.
- Produces: `alignment(measure='pooled_eb', denominator='reconstructed', weights=None, units=None) -> dict` (rho, bootstrap CI, permutation band, n); `tier_shares() -> list[dict]`; `marginal_shift(share=0.10, elasticity_draws) -> dict` (expected additional diagnoses, CI, gainers, losers).

- [ ] **Step 1:** Tests:
  - `test_spearman_known` (hand example with ties);
  - `test_permutation_reproducible`;
  - `test_shift_conserves_volume` (Σ screening after = Σ before);
  - `test_shift_zero_when_elasticity_zero`;
  - `test_shift_linear_case` (ε = 1 ⇒ change equals Σ r_s·D_s).
- [ ] **Step 2–4:** FAIL, implement, PASS; write outputs.
- [ ] **Step 5:** Commit.

### Task 6: D3 additionality and robustness

**Files:**
- Create: `src/ext/d3_additionality.py`, `src/ext/robustness.py`, `outputs/ext/d3.csv`, `outputs/ext/spec_curve.csv`, `outputs/ext/leave_one_out.csv`, `outputs/ext/headline.csv`, `outputs/ext/crosscheck.csv` (descriptive side-by-side of the 2021 panel values with GHA 2023 S1/S2 State rows and of the national cascade with the PGPH 2025 cascade; no agreement metric)
- Test: `tests/test_ext_d3_robust.py`

**Interfaces:**
- Consumes: Tasks 2–5.
- Produces: `additionality(outcome='public', scale='absolute', weights=None, units=None) -> dict` (theta, model CI, cluster CI, n); `spec_grid(estimate: str) -> list[dict]`; `run_spec_curve() -> rows`; `leave_one_out() -> rows`; `headline() -> rows` (estimate, main value, CI, null, share of specifications agreeing, label 'supported'|'not established').

Specification grids (exact):
- **D1 elasticity:** weights {D, none} × zero {exclude, +0.5} × years {all five, excl. 2022, 2021–2023} × units {all, excl. small UTs} = 24; null 1.
- **D2 correlation:** measure {pooled EB 2021–23, 2023 yield, 2023 NNS (sign reversed)} × denominator {reconstructed, registered} × weights {none, 2023 screened} × units {all, excl. small UTs} = 24; null 0.
- **D3 θ:** outcome {public, total} × scale {absolute, log} × weights {none, 1/N} × units {all, excl. small UTs} = 16; null 0.

- [ ] **Step 1:** Tests:
  - `test_additionality_synthetic` (θ = 1 recovered);
  - `test_grid_sizes` (24, 24, 16);
  - `test_degenerate_draws_counted`;
  - `test_headline_label_rule` (the §8 rule of the extension plan: interval excludes null AND ≥80% agreement ⇒ 'supported');
  - `test_outputs_reproducible` (two runs byte-identical).
- [ ] **Step 2–4:** FAIL, implement, PASS; write outputs.
- [ ] **Step 5:** Commit.

### Task 7: Verification, documentation and run order

**Files:**
- Create: `verification/check_ext_outputs.py`, `outputs/ext/README.md`
- Modify: `verification/check_all.py`, `verification/check_plan_order.py`, `README.md`, `CITATION.cff`, `ENVIRONMENT.md`
- Test: `tests/test_verification.py`

**Interfaces:**
- Produces: `check_ext_outputs.main() -> int` recomputing, with its own code, the panel national totals, the DL pooled means, the main elasticity point estimate, the Spearman ρ, θ and the headline labels to 1e-6; plan-order check that the extension registration commit precedes every commit touching `outputs/ext/` or `src/ext/d*`/`robustness.py`.

- [ ] **Step 1:** Tests for both checks on fixtures (a mutated `outputs/ext/headline.csv` value fails; an `outputs/ext` commit before the registration commit fails).
- [ ] **Step 2–4:** FAIL, implement, PASS; `python -I verification/check_all.py` → all PASS.
- [ ] **Step 5:** README leads with the three policy questions and the run order (append `src/ext/panel.py`, `d1_yield.py`, `d1_saturation.py`, `d2_targeting.py`, `d3_additionality.py`, `robustness.py` after the v1.0.0 order); CITATION title "Where does active case finding for TB still pay in India? Code, data and pre-registered plans", version 1.1.0, date-released set at release; ENVIRONMENT adds numpy/scipy for `src/ext/`.
- [ ] **Step 6:** Commit.

### Task 8: Manuscript (local) — exhibits, prose, build

**Files:**
- Create: `exhibits/make_ext_tables.py`, `exhibits/make_ext_figures.py`, `exhibits/EXT_EXHIBIT_SOURCES.md`; local `manuscript/ext/` (sources, `section_phrases.json`, `number_skeleton.json`, submission set); move the current local manuscript to `manuscript/v1_audit/` (not deleted).
- Modify: `tools/build_submission.py`, `verification/check_manuscript_numbers.py`, `verification/check_docx_tie.py` to take `--manuscript-dir` (default `manuscript/ext`), keeping v1 behaviour available.
- Test: `tests/test_ext_exhibits.py`, existing manuscript/docx tests updated.

Three reviewed parts, as in v1.0.0:
- [ ] **8a Exhibits:**
  - Five display items as in the spec §6:
    1. national yield and cascade decomposition;
    2. State tiers with intervals;
    3. alignment and scenario;
    4. additionality and specification curve;
    5. headline table.
  - The supplement holds everything else.
  - Every cell is traced to `outputs/ext/` or `outputs/`.
  - No internal identifiers.
- [ ] **8b Prose:**
  - Title, abstract and text framed as programme guidance.
  - Methods disclose: the original registration; the extension registration and its date; what had been seen; and all v1.0.0 deviations, briefly, with a pointer.
  - The "How to read official ACF figures" box is drawn from v1.0.0 Q1/Q2.
  - Interpretation follows the extension plan §8 labels.
  - The AI declaration follows the Elsevier template and stays truthful.
  - References are Crossref-verified and cited in first-citation order.
- [ ] **8c Build and QA:**
  - Build the submission set 01–11 as before, with `--doi` for v1.1.0.
  - Run the Word render QA and Word word counts.
  - Run the docx tie check and the mutation harness.
  - Expected result: `python -I verification/check_all.py` all PASS.
- [ ] Commit only tooling and tests after each part.

### Task 9: Final review and release (controller)

- [ ] **Step 1:** Whole-branch review from `dca2bf7` to HEAD (most capable model), with the deferred minors from the ledger; one fix wave; one scoped re-review.
- [ ] **Step 2:** Push; create release v1.1.0 (tag on the reviewed commit) with notes; read the version DOI from Zenodo (`q=title:"…"`); verify it resolves.
- [ ] **Step 3:** Rebuild the submission set with `--doi <v1.1.0 DOI>`; rerun `check_all`; update memory and the ledger.
