# outputs/ext

Extension outputs (pre-specified extension analyses, `docs/extension_plan.md`, registered at
commit 6a98549). All files are UTF-8 CSV with LF line endings, byte-reproducible on rerun
(seed 20261119, `numpy.random.default_rng` reset before each analysis, plan §9). Floats are
written with Python `repr`. Log values are natural logs of diagnosed ÷ screened; the
`_per_100k` columns are 100,000 × exp(log value). Every interval is 95%.

## D1 part 1: pooled yield, shrinkage, ranks and tiers

Written by `python -I src/ext/d1_yield.py` (plan §3.3, §4.1, §4.2). Analyses: each data year
(2018, 2019, 2021, 2022, 2023) and the pooled 2021–2023 yield ln(ΣD/ΣS), summed over the
unit-years of 2021, 2022 and 2023 that pass §3.3.

### d1_pooled.csv (one row per analysis)

| Column | Meaning |
|---|---|
| analysis | data year, or `2021-2023` for the pooled yield |
| k | units pooled |
| n_units_without_value | panel units not in the pooling (zero, NA, inconsistent, or no row) |
| n_listed | rows of `d1_excluded.csv` for this analysis |
| mu_log, se_log | DerSimonian–Laird random-effects mean of the log-yield and its SE |
| ci_lo_log, ci_hi_log | confidence interval, μ ± z·SE |
| pi_lo_log, pi_hi_log | prediction interval, μ ± t_{k−2}·√(τ² + SE²) |
| yield_per_100k, ci_*_per_100k, pi_*_per_100k | the same on the yield scale |
| tau2 | between-State variance τ² (DL) |
| i2 | I², per cent |
| q | Cochran's Q |
| n_above, n_overlaps, n_below | tier counts |

The pooled value describes the typical State, not the national ratio.

### d1_states.csv (one row per unit per analysis)

| Column | Meaning |
|---|---|
| analysis | as above |
| unit | coarsened unit (§3.2) |
| small_ut | `yes` for the small UTs of §3.2 |
| years | contributing data years, `;`-separated |
| n_years | number of contributing years |
| diagnosed, screened | D and S (sums over `years` for `2021-2023`) |
| y_log, v_log | ln(D/S) and its variance 1/D − 1/S |
| post_mean_log, post_sd_log | plug-in empirical-Bayes posterior mean and SD |
| post_lo_log, post_hi_log | posterior interval, mean ± z·SD |
| post_per_100k, post_lo_per_100k, post_hi_per_100k | the same on the yield scale |
| rank_lo, rank_hi | rank interval (rank 1 = highest yield), 10,000 parametric draws |
| n_ranked | units ranked in the analysis |
| tier | `above`, `below` or `overlaps`: the posterior interval against the analysis μ |

The tiers form a tiered map with intervals, not a league table.

### d1_excluded.csv (unit-years left out, with the reason)

| Column | Meaning |
|---|---|
| analysis | as above |
| unit | coarsened unit |
| year | the data year left out; blank for a unit with no pooled value at all |
| reason | zero diagnoses, NA, zero screened, D ≥ S, or no row in that year's table |
