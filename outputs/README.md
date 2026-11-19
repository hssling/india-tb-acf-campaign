# outputs

Written by `python -I src/q1_consistency.py` (Q1) and `python -I src/q2_reconcile.py` (Q2; it
re-runs the Q1 checks in memory for class 1). Rules: analysis plan §6 (Q1) and §7 (Q2). All files
are UTF-8 CSV with LF line endings.

## Two sets: registered and corrected

- **Registered** (files without a suffix): the rules as registered. Report these as registered.
- **Corrected** (files ending `_corrected`): a post-hoc deviation, made after the registered output
  was seen (analysis plan §13, 19 November 2026). Label it post hoc. It applies three corrections:
  - **D1:** a figure's span is [window_start, window_end] where window_end is printed. as_on extends
    the span only where window_end is blank; the registered span paired different calendar years.
    Where two spans are then equal, the row is 3a, as §7.3's tie rule states. The corrected set
    differs from the registered rules by D1-D3 only. The order of two stated cut-offs is reported
    in the descriptive `later_cutoff` column, which changes no class.
  - **D2:** a printed sector part is not grouped with totals and enters only Q1 check 3, as a part of
    its total. A sector part is a table cell whose column heading names `public` or `private`, or
    whose table title states a public/private split. The parts and the keywords that matched are in
    `q2_sector_parts_corrected.csv`.
  - **D3:** Q1 check 1 compares only figures from one printed cascade, meaning the same table
    (table_id) or the same paragraph (page_or_para). Q2 class 1 follows the corrected check 1.
- **Both sets:** `other:` figures stay out of the §6 checks (§5.1). Every Q1 row with an `other:`
  input goes to `q1_other_descriptive.csv` instead, and never feeds Q2 class 1. So does a stratum
  percentage, which is a derived quantity.
- **Side by side:** `q2_summary_registered_vs_corrected.csv` (columns metric, registered, corrected)
  gives the Q1 counts by check, the Q2 counts by class (all, pre-specified, exploratory), the groups
  formed, and the sector parts left out.

Corrected files have the same columns as their registered counterparts:

- `q1_checks_corrected.csv`
- `q2_discrepancies_corrected.csv`
- `q2_groups_corrected.csv`
- `q2_different_scope_corrected.csv`
- `q2_pre_identified_corrected.csv`

In `q2_discrepancies_corrected.csv`, `sector_part` is always `no`, because sector parts are not
grouped.

## q1_other_descriptive.csv — `other:` figures, outside the §6 checks (§5.1); descriptive

Columns: `label` (always "outside the §6 checks (§5.1); descriptive"), then the columns of
q1_checks.csv.

Rows: the sum and percentage results that involve an `other:` figure, computed under the registered
rules. They include the 2026 campaign document's Annexure IV (difference −21), every stated
percentage of the inventory, and the stratum percentages of the quality studies.

This file uses the registered rules only. D1-D3 are corrections to the §6 checks and the §7
grouping, and do not apply here. For example, D2 would treat GHA S2's "Public notified" column as a
sector part and remove the denominator of its ACF-share percentages.

## q2_not_formed.csv — candidate pairs the §7.1 rules do not group (descriptive)

Columns:

| Column | Content |
|---|---|
| candidate | The candidate pair |
| a_fig_id, a_value_printed, b_fig_id, b_value_printed | The two figures |
| formed_registered, formed_corrected | `yes` or `no`: whether each set groups the pair |
| reason | Computed from the inventory fields |

The last row records that 9.02 crore / 3.01 lakh was not found in any include = yes official
source.

## q1_checks.csv — §6.2 checks, one row per check instance

| Column | Content |
|---|---|
| check | `1 cascade does not grow`, `2 percentage recomputes`, `3 total equals the sum of its parts`, `4 cumulative series never decreases` |
| inputs | `source: <source_file>`, then the cell, table, column or sentence, and the figures (fig_id, value as printed, qualifier). Stratified quality-study cells not in the inventory are named `QS:<study> <locator>` |
| expected | The condition tested, with the recomputed interval where there is one |
| observed | The §6.1 intervals of the inputs; for check 3 the sum of parts, the printed total and their difference |
| pass | `yes`, `no`, or `n/a` (not run; the note says why: a step with several definition classes, a percentage whose numerator or denominator is not printed with it, no stated percentage left once `other:` figures are kept out, or no input for check 4) |
| note | Flags: a failure involving an unspecified class; a stratified table |

## q2_discrepancies.csv — §7.1 reporting unit: one row per unordered pair of entries in a group

An entry is a distinct (document, value) pair within a comparison group; a pair is written when at
least one pair of their figures is related under §7.1.

| Column | Content |
|---|---|
| group_key | `quantity|geography|scope|gNN`: a connected set of related figures |
| quantity, geography, scope | Shared by the group |
| related_by | `windows overlap` (both stated, spans intersect) and/or `same window label` |
| periods_intersect | Descriptive, not a §7 rule: `yes`/`no` whether [window_start, window_end] (or [window_start, as_on]) intersect; blank if a start is blank. `no` marks a pair related only through a span that runs on to a late as-on date |
| later_cutoff | Descriptive, changes no class: `a` or `b`, the entry with the later stated cut-off (as_on); blank if either cut-off is unstated or both are equal |
| a_*, b_* | Each entry: source, value, value as printed, fig_ids, qualifier, §6.1 interval, definition class, window (start..end; as_on; label; stated/unstated) |
| same_document | `yes` if both entries come from one document |
| agree | `yes` if the intervals of a related pair of their figures overlap |
| class, class_label, rule | §7.3 class of a disagreeing pair (1, 2, 3a, 3b, 4), its name, and the rule that fired. Class 4 ("unexplained") records that the published documents do not explain the difference; it is not a finding of error |
| other_classes | Further classes that also apply (noted, not assigned) |
| evidence | The failed check (class 1), both definitions quoted (class 2), the spans and the direction (class 3), or why none applies (class 4) |
| analysis, analysis_reason | `pre-specified` or `exploratory` (RS Q420; RS Q1900's 2024 column; §13, 18 November 2026) |
| pre_identified | The §7.4 or §9.2 item the pair belongs to, if any |
| sector_part | `yes` if a figure is a Public or Private column of a total in its own table (check 3, row layout) |
| origin | `§7.1 comparison group`, or `§9.2 named list` (a count of list rows, not a printed figure) |
| note | The guard ratio (§9.5.2) for Q1216-Q3467 pairs, with `late-report-consistent` where it applies; the sector-part flag |

## q2_groups.csv — group summaries over distinct values (§7.1)

group_key; quantity, geography, scope; the windows or labels of its figures; counts of figures,
entries, documents and distinct values; the range (min, max); entry pairs written and those that
disagree; pairs of distinct values by class (each takes the lowest-numbered class among its entry
pairs; `agree` if none disagrees), for all pairs and for pre-specified pairs only; and the number of
exploratory entry pairs.

## q2_different_scope.csv — figures that differ only in scope (§7.1)

Pairs of figures with the same quantity and geography, related windows, and different scope: listed,
not compared. Columns: quantity, geography, each figure's scope, source, value and fig_id,
related_by, and whether the intervals overlap.

## q2_pre_identified.csv — the §7.4 items and the §9.2 named list

item; plan clause; whether it was run; the number of entry pairs, how many disagree, and their
classes; note (for example, RS Q2511 against its OGD mirror is not run because the mirror was not
obtained).

## q2_quality_studies.csv — §7.5 reconciliation of the two quality studies

One row per study (GHA2023, PGPH2025) and common indicator (C1 diagnosed among tested; C2 tested
among screened; C3 tested among presumptive; C4 number needed to screen). Columns: the value as
published and where, the study's stated denominator, the numerator and denominator counts and where
they are printed, whether the indicator is recomputable, the recomputed value with its 95% Wilson
interval (§8.2; C1-C3 in percent; C4 as the reciprocals of the Wilson bounds of diagnosed/screened),
whether the published value lies within its own rounding of the recomputation, the reason (or why
it is not recomputable), and the setting. Differences that remain are differences of setting and
denominator, not errors (§7.5, §12).

## Q3: yield, NNS and ACF share of public-sector notifications (analysis plan §8)

Written by `python -I src/q3_yield.py`. Wilson intervals, z = `statistics.NormalDist().inv_cdf(0.975)`.

### q3_yield.csv

One row per State x data year x source table x indicator, for every table that gives the figures
(§8.4 first paragraph), plus not-available rows. Columns: state, year, indicator, source_id,
source_table, pdf_page, printed_page, numerator, denominator, value, lower, upper, unit, status,
reason, note.

- Indicators: `yield_diagnosed_per_100000` (100,000 x diagnosed / screened; the tables print
  "diagnosed", so the name says so), `nns` (screened / diagnosed; interval = 1/upper, 1/lower of
  the Wilson bounds of diagnosed/screened), `acf_share_of_public_sector_notifications_pct`
  (ACF-diagnosed / public-sector notified, in percent).
- Status: `computed`; `not_computable` (zero diagnosed: NNS has no value and its upper bound is
  `unbounded`; the yield of 0 is computed with its Wilson interval); `not_available` (listed with
  the reason, never imputed: no row printed, value printed as NA or #DIV/0!, or a year without a
  table).
- Tables: ITR2019-A1.7 (data year 2018), ITR2020-A6 (2019), ITR2022-A6 (2021), ITR2023-A6 (2022),
  ITR2024-A6 (2023); GHA2023-S1 (2021, first ACF cycle only) beside ITR2022-A6; GHA2023-S2 (ACF
  share, 2021). Data years 2020 and 2024 have no table (one `(all States)` row each).
- India rows are the printed national rows (note: "India row as printed"). The ITR2023 annexure's
  State rows do not sum to its India row (checks TOT-012 to TOT-014); each row is computed as
  printed and the note is carried on every ITR2023 row.
- ACF share of public-sector notifications: the India TB Report ACF annexures print no notification count, and §8.1 requires one
  published table to give numerator and denominator, so no ACF annexure is combined with a
  notification annexure. The only table that prints both is GHA S2 (2021); its denominator is
  public-sector notifications only. Its India value (2.9%) is that table's, not a national share
  of all notifications.

### q3_yield_summary.csv

One row per State, year and indicator: the single value by the §8.4 precedence (India TB Report
edition for the year, level 1; the quality study is none of the five levels). Columns add
chosen_source, precedence_level and sources_computed. The choices are recorded in
data/source_choices.csv (Q3T-2018 to Q3T-2023, Q3T-2021-GHA, and the addenda Q3T-SHARE-2021 and
Q3T-NOTAB). The 2021 GHA yield is reported in q3_yield.csv only: it covers the first ACF cycle,
the ITR2022 table the year.

## Q4: dose-response (analysis plan §9-§10)

Written by `python -I src/q4_dose_response.py --q4`. The guard (§9.5.2) passed (data/source_choices.csv
OUT-08, GRD-01 to GRD-06), so the full-year contrast (RS Q1216, 2025 against 2024) is primary and the
trend uses the primary sources: 2019 ITR2020, 2022 ITR2023, 2023 and 2024 RS Q1216.

**Two denominators.** Every analysis is run under both district denominators:

- `R` (registered): `data/extracted/exposure_share.csv`, the LGD count under §9.3 as written. 16 units
  are computable.
- `D` (deviation): `data/extracted/exposure_share_reconstructed.csv`, the count reconstructed from
  official notices (§13, 19 November 2026). 35 units are computable. The paper presents this as the
  main Q4 analysis and labels it a deviation.

No State is flagged under E5 in either set. The capped States are Chandigarh and Kerala under `R`, and
Chandigarh, Delhi, Goa, Karnataka and Kerala under `D`.

**Method.**

- **Excess change.** x = ln(b/a) − β. β is the OLS slope of ln N on calendar year over the trend points.
- **Model.** WLS of x on the exposure share E, with weights w = 1/(1/a + 1/b).
- **Model interval.** γ1 ± t × SE(γ1), with s² = Σ w r²/(n − 2). t is the 0.975 quantile of Student's t
  with n − 2 degrees of freedom, computed by numerical inversion.
- **γ0 interval.** γ0 carries a model interval using SE(γ0) = √(s² (1/Σw + Ē_w²/Σw(E − Ē_w)²)), so that
  every estimate has an interval (§12).
- **Bootstrap.** 10,000 draws. The States are sorted by coarsened name, and the generator is
  `random.Random(20261118)`, reset before each analysis. The interval is the first and last cut of
  `statistics.quantiles(draws, n=40, method="inclusive")`.
- **No P values.**

### q4_summary.csv

One row per analysis × denominator set (`R`, `D`).

**Analyses:**

- `primary`;
- `S1 unweighted`;
- `S2 leave one out`: the min, max and most influential omission; per-omission values are in
  `q4_s2_leave_one_out.csv`;
- `S3 trend 2022-2024`;
- `S4 trend 2019, 2022, 2023`;
- `S5 States only`;
- `S6a flagged excluded`: reported as empty, because no State is flagged;
- `S6b capped excluded`;
- `S7 population share`: not run, with the reason;
- `S8 January-October`;
- `S8(a) x0.98` and `S8(a) x0.95`: 2025 January–October counts scaled, weights fixed. `gamma1_invariant`
  confirms that γ1 equals the S8 γ1;
- `S8(b) with ln r`;
- `S8(b) without ln r (same States)`;
- `placebo`.

**Columns:**

| Column | Content |
|---|---|
| status | `fitted`, or why there is no fit (descriptive only, §10.7; not run; not computable; empty) |
| n | States in the fit (for S2, n − 1 per refit) |
| units_excluded_by_rule | The units S5, S6a/S6b or S8(b) leave out |
| gamma0, gamma0_model_lo/hi | Intercept, with its model interval |
| gamma1, se_gamma1, t_df, t_0975, gamma1_model_lo/hi | γ1, its SE, the t quantile and the model 95% interval |
| gamma1_boot_lo/hi, boot_draws_valid, boot_draws_degenerate | The bootstrap 95% interval and its draw counts |
| exp_gamma1, exp_0_1_gamma1 (and _model_lo/hi) | exp(γ1) and exp(0.1 γ1), with the model interval transformed |
| gamma2_ln_r, gamma2_model_lo/hi | S8(b) only |
| loo_* | S2 only |
| exposure_sd, exposure_min, exposure_max, exposure_mean_weighted, exposure_mean_unweighted | The spread of exposure in the fitted sample (sample SD) |
| label | The §10.8 rule. For γ1: positive or negative only if both intervals lie wholly on one side of 0, otherwise no clear association. For the placebo: whether its model interval excludes 0 |
| label_note | On the primary row: the placebo consequence of §10.8, if its model interval excludes 0 |
| note | Trend sources, scaling factor, placebo sources |

**S8(b) is not computable under either denominator.**

- **Why.** In every State, the 2023 count in LS Q261 equals the India TB Report 2024 count. So r = 1 and
  ln r = 0 everywhere, and ln r is collinear with the intercept (§10.5). The `without ln r` row is
  therefore the S8 fit.
- **What the equality means.** RS Q1216's 2023 column (as on 6 February 2026) also equals the India TB
  Report 2024 in every State, so the published annual 2023 figure appears frozen. Equal counts show
  that the ln r proxy cannot measure late updating. They do not show that no late updating occurred.
- **The §9.6 cross-check.** Q1216's 2023 counts against the India TB Report 2024 give zero differences
  in all 35 units. The 2023 level difference between the trend sources named in §10.9 is therefore
  nil.

The S2 row gives the exposure spread of the full sample from which the omissions are taken (§10.2).

The exposure share is computed exactly as E = min(1, c/L) from the counts (§9.3). The `share` column of
the exposure files is rounded to 6 decimals, and is not used.

### q4_states.csv

One row per denominator set × contrast × unit. The contrasts are `full-year 2025 vs 2024`,
`January-October 2025 vs 2024` and `placebo 2023 vs 2022`.

| Column | Content |
|---|---|
| a, b | The two window counts (placebo: N2022 and N2023) |
| y, y_poisson_lo/hi | y = ln(b/a), with its Poisson 95% interval y ± z√(1/a + 1/b) (§10.7) |
| trend_points_used, n2019, n2022, n2023, n2024 | The trend points (placebo: 2019 and 2022, two-point benchmark) |
| beta, x, E, w | The trend slope, the excess change, the exposure share and the weight |
| capped, flagged_e5, union_territory | Exposure flags and the S5 set |
| q261_2023, itr2024_2023, ln_r | The S8(b) lag proxy (January–October rows) |
| computable, reason | Whether the unit enters the fit, and if not, why (§10.4) |

### q4_s2_leave_one_out.csv

One row per denominator set × omitted unit, giving n, γ1, the change from the full-sample γ1, and the
status.

