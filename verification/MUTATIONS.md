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

## Not exercised on the real repository

- check_plan_order in a copy without `.git` prints `SKIPPED: not a git checkout ...` and exits
  0 (check_all reports SKIP); covered by `tests/test_verification.py::test_plan_order_skips_without_git`.
- The ordering rules (output or Q module before registration; outcome data before the LGD
  deviation commit 0ebcca1; CRLF conversion of the frozen text) are covered by temporary-git-repository
  tests in `tests/test_verification.py`, not by a scratch-clone rewrite of this history.
