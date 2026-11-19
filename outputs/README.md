# outputs

Written by `python -I src/q1_consistency.py` (Q1) and `python -I src/q2_reconcile.py` (Q2; it
re-runs the Q1 checks in memory for class 1). Rules: analysis plan §6 (Q1) and §7 (Q2). All files
are UTF-8 CSV with LF line endings.

## q1_checks.csv — §6.2 checks, one row per check instance

| Column | Content |
|---|---|
| check | `1 cascade does not grow`, `2 percentage recomputes`, `3 total equals the sum of its parts`, `4 cumulative series never decreases` |
| inputs | `source: <source_file>`, then the cell, table, column or sentence, and the figures (fig_id, value as printed, qualifier). Stratified quality-study cells not in the inventory are named `QS:<study> <locator>` |
| expected | The condition tested, with the recomputed interval where there is one |
| observed | The §6.1 intervals of the inputs; for check 3 the sum of parts, the printed total and their difference |
| pass | `yes`, `no`, or `n/a` (not run; the note says why: a step with several definition classes, a percentage whose numerator or denominator is not printed with it, or no input for check 4) |
| note | Flags: a failure involving an unspecified class; an `other:` quantity; a stratified table |

## q2_discrepancies.csv — §7.1 reporting unit: one row per unordered pair of entries in a group

An entry is a distinct (document, value) pair within a comparison group; a pair is written when at
least one pair of their figures is related under §7.1.

| Column | Content |
|---|---|
| group_key | `quantity|geography|scope|gNN`: a connected set of related figures |
| quantity, geography, scope | Shared by the group |
| related_by | `windows overlap` (both stated, spans intersect) and/or `same window label` |
| periods_intersect | Descriptive, not a §7 rule: `yes`/`no` whether [window_start, window_end] (or [window_start, as_on]) intersect; blank if a start is blank. `no` marks a pair related only through a span that runs on to a late as-on date |
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
