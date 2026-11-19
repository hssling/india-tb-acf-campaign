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
