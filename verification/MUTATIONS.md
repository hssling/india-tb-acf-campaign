# Mutation record

<!-- Adapted from hssling/india-state-tb-score (MIT), verification/MUTATIONS.md, commit 05bcaa7; modified: this repository's checks and mutations -->

Each check was shown to fail on a deliberate break. All breaks were made in a scratch
clone (`git clone <repo> <scratch>/mut`, with `verification/` and
`tests/test_verification.py` copied in), never in this repository or its history; the clone
was restored (`git checkout -- <path>` or `git reset --hard HEAD~1`) between runs. Run on
19 November 2026 against the tree of commit dab67e2 (mutations 6 to 9 against the same tree with the revised checks) (clone without `data_raw/`: none of
the checks reads it).

| # | Check | Break | Result |
|---|-------|-------|--------|
| 1 | check_extraction_totals | one extracted value edited (`pq_q1216.csv`, first 2023 State value 561 to 562) | caught (FAIL, exit 1) |
| 2 | check_plan_order | one line above section 13 of `docs/analysis_plan.md` edited and committed | caught (FAIL, exit 1) |
| 3 | check_deviations | the word "exploratory" added to a row of `outputs/q3_yield.csv` | caught (FAIL, exit 1) |
| 4 | pytest step of check_all | a failing test added (`tests/test_zz_mutant.py`) | caught (FAIL, exit 1) |
| 5 | check_inventory | one Q3 numerator edited in `outputs/q3_yield.csv` (47307 to 47308) | caught (FAIL, exit 1) |
| 6 | check_inventory, check_outputs | `q4_states.csv` `a` of Andaman and Nicobar Islands (full-year, R) changed from 534 to 561, a real figure of the same unit | caught by both (FAIL, exit 1) |
| 7 | check_outputs | `beta` edited in `q4_states.csv` (first row, +0.01) | caught (FAIL, exit 1) |
| 8 | check_outputs | `gamma1` edited in `q4_summary.csv` (primary, R, +0.01) | caught (FAIL, exit 1) |
| 9 | check_deviations | a new unlogged `exploratory` line appended to `outputs/q2_discrepancies.csv` (no question number) | caught (FAIL, exit 1) |
| 10 | check_ext_outputs | the `label` of the rho row in `outputs/ext/headline.csv` changed from "not established" to "supported" | caught (FAIL, exit 1) |
| 11 | check_ext_outputs | `estimate` of the main row of `outputs/ext/d3.csv` (theta) edited by +1e-4 | caught (FAIL, exit 1) |
| 12 | check_plan_order | one line above section 10 of `docs/extension_plan.md` edited and committed | caught (FAIL, exit 1) |
| 13 | check_plan_order | a commit adding a file under `outputs/ext/`, branched from the commit before the extension registration commit and merged | caught (FAIL, exit 1) |

Mutation 1 is also visible to check_extraction_totals through the recorded-versus-recomputed
sum; check_inventory does not flag it, because the unedited value is still held by the
inventory row with the same value (the trace requires a match in either place). The extracted
CSV and its recorded total check are what disagree, and that is the job of the totals check.

Mutation 2 leaves check_deviations and check_extraction_totals passing: only the plan order
check owns that failure.

## 1. Edited extracted value

```
sed -i '2s/,561,561,/,562,562,/' data/extracted/pq_q1216.csv
python -I verification/check_extraction_totals.py
```

```
FAIL: data_raw/pq/AU1216_WFw8li.pdf p2 'RS Unstarred Q. 1216 (10 Feb 2026), Annexure: 2023 (Jan-Dec)': recorded 36 rows, sum 2552257, printed total none is not reproduced by any extracted column
FAIL: pq_q1216.csv Annexure 2023_notified: 36 rows sum to 2552258 (printed total None) but no recorded check matches
exit 1
```

## 2. Plan edited above section 13 and committed

```
sed -i '30s/\([a-z]\) /\1  /' docs/analysis_plan.md      # a doubled space on line 30
git commit -am "mutation: edit above section 13"
python -I verification/check_plan_order.py
```

```
FAIL: docs/analysis_plan.md above section 13 differs from its content at the registration commit 2a422a2
exit 1
```

## 3. Unlogged exploratory label in an output

```
sed -i '2s/$/,exploratory/' outputs/q3_yield.csv
python -I verification/check_deviations.py
```

```
FAIL: outputs/q3_yield.csv: 1 line(s) labelled 'exploratory' with no dated section 13 entry that names the file or the question
exit 1
```

## 4. Failing test

```
printf 'def test_mutant():\n    assert 1 == 2\n' > tests/test_zz_mutant.py
python -I verification/check_all.py
```

```
[FAIL] pytest -q
    FAILED tests/test_zz_mutant.py::test_mutant - assert 1 == 2
    1 failed, 323 passed, 12 skipped in 30.64s
[PASS] check_plan_order: OK: ...
[PASS] check_deviations: OK: ...
[PASS] check_extraction_totals: OK: ...
[PASS] check_inventory: OK: ...

4/5 checks passed
exit 1
```

(12 tests skipped in the clone because it has no `data_raw/`.)

## 5. Q3 input that traces to no source value

```
sed -i '2s/,47307,/,47308,/' outputs/q3_yield.csv
python -I verification/check_inventory.py
```

```
FAIL: q3_yield India 2018 nns (ITR2019-A1.7): numerator '47308' matches no inventory or extracted row for this State
exit 1
```

## 6. A value that belongs to another figure of the same unit

```
# first data row: R,full-year 2025 vs 2024,Andaman and Nicobar Islands,534,522,...
sed -i '0,/^R,full-year 2025 vs 2024,Andaman and Nicobar Islands,534,/s//R,full-year 2025 vs 2024,Andaman and Nicobar Islands,561,/' outputs/q4_states.csv
python -I verification/check_inventory.py
python -I verification/check_outputs.py
```

```
FAIL: q4_states Andaman and Nicobar Islands (full-year 2025 vs 2024, R) a: 561 but pq_q1216.csv:2024_notified gives 534 for this unit
exit 1
FAIL: q4_states Andaman and Nicobar Islands (full-year 2025 vs 2024, R): y is -0.022728 but recomputed -0.072053
... (y_poisson_lo/hi, w, x, and the primary (R) model fit: gamma0, gamma1, se_gamma1, intervals, exp_gamma1)
exit 1
```

Under the earlier value-only trace this edit passed, because 561 is another figure of the
unit in the inventory; check_inventory now keys on unit, year and column.

## 7. beta edited in q4_states.csv

```
python -I verification/check_outputs.py     # beta of the first row 0.01 higher
```

```
FAIL: q4_states Andaman and Nicobar Islands (full-year 2025 vs 2024, R): beta is -0.006754 but recomputed -0.016754
exit 1
```

## 8. gamma1 edited in q4_summary.csv

```
python -I verification/check_outputs.py     # gamma1 of the primary (R) row 0.01 higher
```

```
FAIL: q4_summary primary (R): gamma1 is 0.064830 but recomputed 0.054830
exit 1
```

check_outputs re-derives the deterministic columns only (y and its Poisson interval, w, beta,
x, E; the WLS gamma0, gamma1, SE, t, model intervals and exp(gamma1) of the primary analysis,
S8 January-October and the placebo under both denominators; the Q3 values and Wilson
bounds). The bootstrap intervals are not re-derived by check_all; they are reproduced by
the seeded run, `python -I src/q4_dose_response.py --q4`.

## 9. New unlogged exploratory line in a Q2 output

```
printf 'g99,new check,exploratory\n' >> outputs/q2_discrepancies.csv
python -I verification/check_deviations.py
```

```
FAIL: outputs/q2_discrepancies.csv: 1 line(s) labelled 'exploratory' with no dated section 13 entry that names the file or the question
exit 1
```

## 10. Extension headline label edited

Added on 20 November 2026 (extension v1.1.0), in a scratch clone of this repository's
commit 445cd86 with the new check copied in.

```
sed -i 's/^rho,\(.*\),not established,/rho,\1,supported,/' outputs/ext/headline.csv
python -I verification/check_ext_outputs.py
```

```
FAIL: headline rho: label printed 'supported' but section 8 gives 'not established' (23/24 entries agree; interval [-0.930911, 0.022103], null 0.0)
exit 1
```

## 11. Extension theta edited

```
# main row of outputs/ext/d3.csv, estimate + 1e-4
python -I verification/check_ext_outputs.py
```

```
FAIL: d3 main theta: printed -0.17183620979274733 but recomputed -0.17193620979274732
exit 1
```

## 12. Extension plan edited above section 10 and committed

```
sed -i '3s/$/ x/' docs/extension_plan.md
git commit -am "mutation: edit above section 10"
python -I verification/check_plan_order.py
```

```
FAIL: commit 4876b88: docs/extension_plan.md above section 10 differs from its content at the extension registration commit 6a98549
exit 1
```

## 13. outputs/ext commit before the extension registration commit

```
git checkout -b early 6a98549~1; mkdir -p outputs/ext; echo a > outputs/ext/x.csv
git add -f outputs/ext/x.csv; git commit -m "early ext output"
git checkout main; git merge early
python -I verification/check_plan_order.py
```

```
FAIL: commit 78515c0 touches outputs/ext/ or a src/ext analysis module (d1_*, d2_*, d3_*, robustness) but is not a descendant of the extension registration commit 6a98549
FAIL: commit 78515c0: docs/extension_plan.md above section 10 differs from its content at the extension registration commit 6a98549
exit 1
```

Mutations 10 to 13 are also fixed in `tests/test_verification.py` (on temporary fixtures:
`test_mutated_headline_label_fails`, `test_mutated_theta_fails`,
`test_edit_above_section10_of_extension_plan_fails`,
`test_ext_output_before_ext_registration_fails`). `check_ext_outputs.py` does not
re-derive the bootstrap and permutation intervals of `outputs/ext/`; those are reproduced by
the seeded build, so an edit of an interval alone is caught by `tests/test_ext_*.py`
(`test_build_reproduces_committed_outputs`), not by this check.

## Not exercised on the real repository

- check_plan_order in a copy without `.git` prints `SKIPPED: not a git checkout ...` and exits
  0 (check_all reports SKIP); covered by `tests/test_verification.py::test_plan_order_skips_without_git`.
- The ordering rules (output or Q module before registration; outcome data before the LGD
  deviation commit 0ebcca1; CRLF conversion of the frozen text) are covered by temporary-git-repository
  tests in `tests/test_verification.py`, not by a scratch-clone rewrite of this history.

## Manuscript and submission files (check_manuscript_numbers, check_docx_tie; mutate_manuscript.py)

The manuscript (`manuscript/`, private and git-ignored) and the Public Health submission set
built from it (`manuscript/submission/`, by `tools/build_submission.py`) were mutated by
`python -I verification/mutate_manuscript.py --sweep` on 19 November 2026, against the working
tree that became the commit adding this section. Each named mutation is applied to a fresh
temporary copy of `manuscript/`; the real files are never written. Both checks are run on the
copy: check_manuscript_numbers on the copied Markdown (against the committed outputs) and
check_docx_tie on the copied Markdown and `.docx` files. The unmutated copy passes both (0
problems each). A mutation whose anchor text is missing counts as NOT APPLIED and fails the run.
Fixture tests: `tests/test_mutation_harness.py` and `tests/test_docx_tie.py`.

| # | Kind | Mutation | Caught by |
|---|------|----------|-----------|
| 1a | number, docx only | 02 Results: 2,401 figures to 2,402 | check_docx_tie |
| 1b | number, docx only | 01 title page: abstract word count 243 to 244 | check_docx_tie |
| 2a | number, Markdown only | manuscript_src.md Results: 6,174 people to 6,175 | check_manuscript_numbers and check_docx_tie |
| 2b | number, Markdown only | manuscript_src.md Abstract: 79 of 84 to 79 of 85 | check_manuscript_numbers and check_docx_tie |
| 3a | author name, blinded docx | 02 Discussion: the author's name inserted in the text | check_docx_tie |
| 3b | author name, blinded docx | 02 document properties: author (dc:creator) set to the author's name | check_docx_tie (BLINDING) |
| 3c | author e-mail, blinded docx | 05 note under Table S2: the author's e-mail inserted | check_docx_tie |
| 3d | repository URL, blinded docx | 02 Data availability: the blinding placeholder replaced by the repository URL | check_docx_tie |
| 4a | reference number, Markdown | manuscript_src.md: citation ^19^ to ^24^ | check_manuscript_numbers and check_docx_tie |
| 4b | reference number, docx only | 02: superscript citation 19 to 24 | check_docx_tie |
| 4c | reference number, docx only | 02 References: entries 2 and 3 renumbered 3 and 2 | check_docx_tie |
| 5a | table cell, docx only | 02 Table 3: 33.0 (32.7 to 33.2) to 33.1 | check_docx_tie |
| 5b | table cell, docx only | 05 Table S3: 191.3 (87.7 to 416.8) to 191.4 | check_docx_tie |
| 5c | table cell, Markdown only | tables.md Table 1: 2,401 to 2,402 | check_docx_tie |
| 6a | gamma sign, Markdown | manuscript_src.md Results: γ1 was 0.042 to −0.042 | check_manuscript_numbers and check_docx_tie |
| 6b | gamma sign, docx only | 02 Results: γ1 was 0.042 to −0.042 | check_docx_tie |
| 6c | gamma sign, docx only | 05 Table S4: placebo γ1 −0.119 to 0.119 | check_docx_tie |
| 7a | internal identifier, Markdown | manuscript_src.md Methods: "(RS Q1216)" inserted | check_manuscript_numbers and check_docx_tie |
| 7b | internal identifier, docx only | 02 Discussion: "(Task 7)" inserted | check_docx_tie |
| 7c | internal identifier, docx only | 05 note under Table S2: "ITR2024" inserted | check_docx_tie |

```
named mutations: 20 of 20 caught
sweep, manuscript_src.md number tokens (check_manuscript_numbers): caught 410 of 410
sweep, 02_manuscript_anonymised.docx number tokens (check_docx_tie): caught 942 of 942
```

The two sweeps change every number token, one at a time, by increasing its last digit (9
becomes 0): in manuscript_src.md (every section but the References), checked by
check_manuscript_numbers; and in the text of 02_manuscript_anonymised.docx (body, references
and tables), checked by check_docx_tie.

Mutation 5c (a table cell edited in tables.md only) is caught by the tie, not by
check_manuscript_numbers, which scans tables.md for wording and blinding only; the table values
themselves are traced to `outputs/` by `exhibits/make_tables.py` (`trace.json`) and its tests.
Building the set also exposed a defect the tie caught at once: a Table S1a/S1b cell holding two
printed forms ("73,772 | 73772") split into an extra column in tables.md, and pandoc dropped
the last cell of those two rows. `exhibits/make_tables.py` now escapes a `|` inside a cell.

### Supplementary data files and journal italics (19 November 2026, second run)

After the full discrepancy lists left the supplement for Supplementary data S1a and S1b (CSV and
XLSX; Table S1 now summarises the pairs by comparison group) and journal titles were set in
italics, `python -I verification/mutate_manuscript.py` was rerun on the rebuilt set: mutations
1a to 7c as above were again all caught (anchors in 05 now point to Tables S2 to S4), and four
were added:

| # | Kind | Mutation | Caught by |
|---|------|----------|-----------|
| 8a | supplementary data, CSV | 09 (S1a): first A value 347 to 348 | check_docx_tie (verbatim column and SHA-256 against outputs/) |
| 8b | supplementary data, CSV | 10 (S1b): last row deleted | check_docx_tie (973 rows against 974 in the output) |
| 8c | supplementary data, XLSX | 11, sheet S1b: cell K2 (A value, printed) set to 999 | check_docx_tie (XLSX differs from the CSV) |
| 9a | AMA italics, docx only | 02 References: italics removed from the first journal title | check_docx_tie (ITALICS) |

```
named mutations: 24 of 24 caught
```

The number-token sweeps were not rerun for this change.

### Extension paper, manuscript/ext (20 November 2026)

The harness now takes the folder's profile (`check_manuscript_numbers.profile_for`) and runs
that profile's set: `MUTATION_SETS["v1"]` (the 24 mutations above, unchanged, run with
`--manuscript-dir manuscript/v1_audit`) or `MUTATION_SETS["ext"]` (below, the default
`manuscript/ext`). The ext submission set is 01 title page, 02 anonymised manuscript, 03 to 06
Figures 1 to 4, 07 supplementary material (Tables S1 to S8), 08 cover letter, 09 RECORD
checklist and 10 declaration of interests; it has no data files, because check_docx_tie
requires each table of tables.md to equal its CSV row for row. Anchors are in the private
`manuscript/ext/section_phrases.json`; a label or caveat anchor is an [old, new] pair. Run with
`python -I verification/mutate_manuscript.py --sweep` against the working tree that became the
commit adding this section.

| # | Kind | Mutation | Caught by |
|---|------|----------|-----------|
| 1a | number, docx only | 02 Results: the pooled 2021-2023 mean yield, last digit changed | check_docx_tie |
| 1b | number, docx only | 01 title page: abstract word count increased by 1 | check_docx_tie |
| 2a | number, Markdown only | Results: the scenario's added diagnoses increased by 1 | check_manuscript_numbers and check_docx_tie |
| 2b | number, Markdown only | Abstract: the count of robustly above States increased by 1 | check_manuscript_numbers and check_docx_tie |
| 2c | number, Markdown only | Box 1: a count of printed totals increased by 1 | check_manuscript_numbers and check_docx_tie |
| 3a | author name, blinded docx | 02 Discussion: the author's name inserted | check_docx_tie |
| 3b | author name, blinded docx | 02 document properties: dc:creator set to the name | check_docx_tie (BLINDING) |
| 3c | author e-mail, blinded docx | 07 note under Table S2: the e-mail inserted | check_docx_tie |
| 3d | repository URL, blinded docx | 02 Methods: the blinding placeholder replaced by the URL | check_docx_tie |
| 3e | author name, blinded docx | 07 document properties: dc:creator set to the name | check_docx_tie (BLINDING) |
| 4a | reference number, Markdown | Methods: a citation number increased by 1 | check_manuscript_numbers and check_docx_tie |
| 4b | reference number, docx only | 02 Methods: a superscript citation increased by 1 | check_docx_tie |
| 4c | reference number, docx only | 02 References: entries 2 and 3 renumbered 3 and 2 | check_docx_tie |
| 5a | table cell, docx only | 02 Table 1: a sample size increased by 1 | check_docx_tie |
| 5b | table cell, docx only | 07 Table S2: a posterior yield, last digit changed | check_docx_tie |
| 5c | table cell, Markdown only | tables.md Table 1: a sample size increased by 1 | check_docx_tie |
| 6a | sign, Markdown | Results: the sign of the unweighted ρ reversed | check_manuscript_numbers and check_docx_tie |
| 6b | sign, docx only | 02 Results: the sign of the main θ reversed | check_docx_tie |
| 6c | sign, docx only | 07 Table S3: the sign of a decomposition interval limit reversed | check_docx_tie |
| 7a | internal identifier, Markdown | Methods: "(RS Q1216)" inserted | check_manuscript_numbers and check_docx_tie |
| 7b | internal identifier, docx only | 02 Discussion: "(Task 7)" inserted | check_docx_tie |
| 7c | internal identifier, docx only | 07 note under Table S2: "ITR2024" inserted | check_docx_tie |
| 8a | label, Markdown | Abstract: the elasticity's label "supported" to "not established" | check_manuscript_numbers and check_docx_tie |
| 8b | label, Markdown | Results: the correlation's label "not established" to "supported" | check_manuscript_numbers and check_docx_tie |
| 8c | label, docx only | 02 Discussion: the number of estimates meeting the criterion changed | check_docx_tie |
| 8d | label, docx only | 02 Table 1: the elasticity's label "Supported" to "Not established" | check_docx_tie |
| 9a | caveat, Markdown | Results: "(post hoc)" removed from the robust-tier scenario | check_manuscript_numbers and check_docx_tie |
| 9b | caveat, Markdown | Results: "an illustration, not a forecast" removed | check_manuscript_numbers and check_docx_tie |
| 9c | caveat, Markdown | Abstract: "post hoc" removed from the between-year analysis | check_manuscript_numbers and check_docx_tie |
| 9d | caveat, Markdown | Results: "this was not tested ..." removed | check_manuscript_numbers and check_docx_tie |
| 9e | caveat, Markdown | Figure 3 legend: "not a forecast" removed | check_manuscript_numbers and check_docx_tie |
| 9f | caveat, docx only | 02 Discussion: "it is not a forecast" removed | check_docx_tie |
| 9g | caveat, docx only | 07 Table S2 title: "(post hoc)" removed | check_docx_tie |
| 10a | AMA italics, docx only | 02 References: italics removed from the first journal title | check_docx_tie (ITALICS) |

```
named mutations [ext]: 34 of 34 caught
sweep, manuscript_src.md number tokens (check_manuscript_numbers): caught 368 of 368
sweep, 02_manuscript_anonymised.docx number tokens (check_docx_tie): caught 760 of 760
```

The same day, `python -I verification/mutate_manuscript.py --manuscript-dir manuscript/v1_audit`
gave `named mutations [v1]: 24 of 24 caught`, on the existing v1 set and on a copy rebuilt with
the revised builder. The harness now copies the folder under its own name, so a folder without a
"profile" key (v1_audit) keeps its profile in the copy.
