# Mutation record

<!-- Adapted from hssling/india-state-tb-score (MIT), verification/MUTATIONS.md, commit 05bcaa7; modified: this repository's checks and mutations -->

Each check was shown to fail on a deliberate break. All breaks were made in a scratch
clone (`git clone <repo> <scratch>/mut`, with `verification/` and
`tests/test_verification.py` copied in), never in this repository or its history; the clone
was restored (`git checkout -- <path>` or `git reset --hard HEAD~1`) between runs. Run on
19 November 2026 against the tree of commit dab67e2 (clone without `data_raw/`: none of
the checks reads it).

| # | Check | Break | Result |
|---|-------|-------|--------|
| 1 | check_extraction_totals | one extracted value edited (`pq_q1216.csv`, first 2023 State value 561 to 562) | caught (FAIL, exit 1) |
| 2 | check_plan_order | one line above section 13 of `docs/analysis_plan.md` edited and committed | caught (FAIL, exit 1) |
| 3 | check_deviations | the word "exploratory" added to a row of `outputs/q3_yield.csv` | caught (FAIL, exit 1) |
| 4 | pytest step of check_all | a failing test added (`tests/test_zz_mutant.py`) | caught (FAIL, exit 1) |
| 5 | check_inventory | one Q3 numerator edited in `outputs/q3_yield.csv` (47307 to 47308) | caught (FAIL, exit 1) |

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

## Not exercised on the real repository

- check_plan_order in a copy without `.git` prints `SKIPPED: not a git checkout ...` and exits
  0 (check_all reports SKIP); covered by `tests/test_verification.py::test_plan_order_skips_without_git`.
- The ordering rules (output or Q module before registration; outcome data before the LGD
  deviation commit 0ebcca1; CRLF conversion of the frozen text) are covered by temporary-git-repository
  tests in `tests/test_verification.py`, not by a scratch-clone rewrite of this history.
