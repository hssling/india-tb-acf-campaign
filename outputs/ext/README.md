# outputs/ext

Extension outputs (pre-specified extension analyses, `docs/extension_plan.md`, registered at
commit 6a98549). All files are UTF-8 CSV with LF line endings, byte-reproducible on rerun
(seed 20261119, `numpy.random.default_rng` reset before each analysis, plan §9). Floats are
written with Python `repr`. Log values are natural logs of diagnosed ÷ screened; the
`_per_100k` columns are 100,000 × exp(log value). Every interval is 95%.

Posterior and rank intervals reflect binomial sampling variance only, conditional on the estimated
μ and τ² (plug-in); they omit between-year variation within a State and are therefore narrower
than the true uncertainty.

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
| post_mean_log, post_sd_log | plug-in empirical-Bayes posterior mean and SD (plug-in; binomial variance only) |
| post_lo_log, post_hi_log | posterior interval, mean ± z·SD |
| post_per_100k, post_lo_per_100k, post_hi_per_100k | the same on the yield scale |
| rank_lo, rank_hi | rank interval (rank 1 = highest yield), 10,000 parametric draws (plug-in; binomial variance only) |
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

## POST HOC: between-year tier sensitivity

Added 19 November 2026, after registration and after the registered tier results were seen
(extension plan §10). Label it post hoc. Written by the same script.

- **Method.** For each unit, the usable 2021–2023 unit-years (the same ones as the registered
  pooled yield, §3.3) are combined by a within-State DerSimonian–Laird random-effects mean of the
  yearly log-yields, each with variance 1/D − 1/S. The resulting SE includes the between-year
  variation. A unit with one usable year keeps that year's log-yield and binomial variance, and is
  flagged. The §4.2 cross-State procedure is then applied unchanged: DL across States, the
  plug-in posterior, the tier rule, and rank intervals (seed reset, 10,000 draws).
- **Reading.** A tier is described as robust only if it agrees under both the registered and
  the between-year analysis.

### d1_states_betweenyear.csv

It has the same columns as the `2021-2023` rows of `d1_states.csv`, with these differences:

- `analysis` is `2021-2023 between-year (post hoc)`;
- `y_log` is the within-State random-effects mean;
- `v_log` is its SE².

Added columns:

| Column | Meaning |
|---|---|
| tier_registered | the registered pooled 2021–2023 tier of the unit |
| tier_agrees | `yes` if the two tiers are equal |
| single_year | `yes` if the unit has one usable year (binomial variance only) |
| within_tau2 | the within-State between-year τ² (blank for a single year) |

### d1_pooled_betweenyear.csv (one summary row)

It has the columns of `d1_pooled.csv`, plus these:

| Column | Meaning |
|---|---|
| n_single_year | units flagged `single_year` |
| n_tier_agrees | units whose tier agrees with the registered tier |
| robust_above, robust_overlaps, robust_below | agreeing units by tier |
