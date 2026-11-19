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

## D1 part 2: elasticity, Poisson sensitivity, intensity strata and cascade decomposition

Written by `python -I src/ext/d1_saturation.py` (plan §3.3, §4.2 last bullet, §4.3, §4.4, §4.5).
The generator `default_rng(20261119)` is reset before each bootstrap:

- each elasticity (main, each stratum, Poisson);
- each decomposition quantity: the national change, each year's national level, each year's
  variance split, and each 2022 sensitivity.

Draw b resamples units: `rng.integers(0, G, size=G)` over the sorted units. Each drawn unit
brings all its rows, and each copy is its own cluster with its own dummy. Unit-years are
listed in the `excluded` columns as `unit year code`. The codes are:

- `D=0`: zero diagnoses;
- `D NA` or `S NA`: not printed;
- `S=0`: zero screened;
- `T=0` or `T NA`: tested zero or not printed;
- `D>=S`: an inconsistent row;
- `no row`: the unit is absent from that year's table.

Several codes are joined by `/`.

### d1_elasticity.csv (one row per model)

Rows:

- `main`: WLS, weights D, zeros excluded, all five years, all units;
- `stratum high` and `stratum low`: the main model within each intensity stratum (§4.5);
- `poisson`: Poisson fixed effects, zeros kept.

Leave-one-out and the specification curve are written by a later script, not here.

| Column | Meaning |
|---|---|
| analysis | `main`, `stratum high`, `stratum low` or `poisson` |
| model | `fe_wls`: ln D = α_unit + λ_year + ε ln S, by WLS; `poisson_fe`: D ~ Poisson(exp(α_unit + λ_year + ε ln S)), by IRLS |
| weights | `D` (WLS weights D) or `none` |
| zero | `exclude` (D = 0 unit-years left out, §3.3) or `kept` (Poisson) |
| years | data years in the estimation sample |
| units | `all`, `high intensity` or `low intensity` |
| estimate | the elasticity ε. Below 1, diagnoses rose less than proportionally with screening within States |
| null | 1 |
| se_cr1 | CR1 cluster-robust SE by unit. WLS: c = G/(G−1)·(n−1)/(n−p). Poisson: c = G/(G−1), bread XᵀWX with W = diag(μ̂) |
| df | G − 1, the degrees of freedom of the t quantile |
| model_ci_lo, model_ci_hi | model interval, ε ± t_{G−1}·se_cr1 |
| boot_lo, boot_hi | cluster-bootstrap percentile interval (the main interval, §4.3) |
| draws | bootstrap draws (10,000) |
| n_valid | draws used |
| degenerate | draws that were rank-deficient, or (Poisson) did not converge in 100 iterations; counted and excluded |
| n_units | G, units in the estimation sample |
| n_obs | n, unit-years in the estimation sample |
| p | columns of the design: ln S, one dummy per unit, one per year except the earliest |
| n_singletons, singletons | units with one row in the sample, listed and dropped before fitting and resampling |
| n_excluded, excluded | unit-years of the analysis's units and years that were left out (§3.3) |
| n_all_zero_units, all_zero_units | Poisson only: units with D = 0 in every year, listed and excluded |
| converged, iterations | Poisson only: IRLS convergence (maximum coefficient change < 10⁻¹⁰) and the iterations used |

### d1_decomposition.csv (one row per quantity)

The identity is ln(D/S) = ln(T/S) + ln(D/T): the testing rate plus the positivity.

- **Main rows** use the years 2018, 2019, 2021 and 2023.
- **Sensitivity rows** are the rows that involve 2022, whose "tested" column counts people
  examined. Their `testing_definition` contains `examined`.

| Column | Meaning |
|---|---|
| analysis | `change` (national change between two years), `level` (national level in one year) or `variance` (between-State variance split in one year) |
| status | `main` or `sensitivity` (2022) |
| testing_definition | `tested`, `examined`, `tested->examined` or `examined->tested` |
| years | `2021->2023` (a change), or the data year |
| quantity | see below |
| estimate | the point estimate |
| boot_lo, boot_hi | cluster-bootstrap percentile interval (units resampled) |
| draws | bootstrap draws (10,000) |
| n_valid | draws used |
| degenerate | variance only: draws with var(y) = 0 (every resampled y identical), counted and excluded |
| n_units | units with S, T and D present and positive (in both years for a change) |
| n_excluded, excluded | unit-years left out (codes above) |

Quantities:

- **change.** On the units of both years, from the sums ΣS, ΣT and ΣD:
  - `dln_yield` = Δ ln(ΣD/ΣS);
  - `testing_part` = Δ ln(ΣT/ΣS);
  - `positivity_part` = Δ ln(ΣD/ΣT).

  The two parts add up to `dln_yield` exactly.
- **level.** `ln_yield`, `ln_testing` and `ln_positivity`: the same three logs in one year.
- **variance.** Per unit, a = ln(T/S) and b = ln(D/T), with y = a + b. Variances are unweighted,
  with ddof = 1:
  - `var_total` is var(y);
  - `var_testing` is var(a);
  - `var_positivity` is var(b);
  - `cov` is cov(a, b);
  - `testing_share` = (var a + cov)/var y;
  - `positivity_share` = (var b + cov)/var y.

  The covariance is split equally, so the two shares sum to 1.

### d1_intensity_strata.csv (one row per unit; the §4.5 listing)

The intensity is screened per estimated population.

- **Dated entry.** This file follows a dated entry in plan §10 (19 November 2026): the ITR 2020
  population column, which §4.5 registered as the 2019 population, is misaligned with its
  State rows as printed.
- **Main rule.** The main intensity therefore uses the ITR 2022 population for 2021–2023 only.
- **Registered rule.** It is shown beside the main rule.

| Column | Meaning |
|---|---|
| unit, small_ut | as above |
| intensity | the mean of S_t / P_2021 over `intensity_years` (main rule) |
| intensity_years | the years with both values present (S = 0 counts as a printed value) |
| stratum | `high` if the intensity is above `median`; `low` otherwise; `unclassified` if the unit has no intensity |
| median | `numpy.median` of the intensity over the classified units |
| intensity_registered_rule, intensity_registered_years | the registered §4.5 rule: 2019 with the ITR 2020 population; 2021–2023 with the ITR 2022 population, or the 2019 value carried forward |
| stratum_registered_rule, median_registered_rule | the stratum and the median under the registered rule |
| note | why a unit is unclassified, or why it is absent from the tier sensitivity |

### d1_tiers_by_intensity.csv (one row per unit per stratum)

This is the §4.2 intensity sensitivity.

- **Method.** The 2021–2023 pooling, shrinkage, ranks and tiers of `d1_states.csv` are rerun
  within each stratum, against that stratum's own μ. The generator is reset for each
  stratum's rank draws.
- **Columns.** The columns from `analysis` to `tier` are those of the `2021-2023` rows of
  `d1_states.csv`, with two differences:
  - `analysis` is `2021-2023 high intensity` or `2021-2023 low intensity`;
  - `n_ranked` counts the units ranked within the stratum.

Added columns:

| Column | Meaning |
|---|---|
| stratum | `high` or `low` |
| intensity | the unit's intensity (main rule) |
| stratum_k | units pooled in the stratum |
| stratum_mu_log, stratum_mu_per_100k | the stratum's DerSimonian–Laird mean, as a log and per 100,000 |
| stratum_ci_lo_per_100k, stratum_ci_hi_per_100k | its confidence interval |
| stratum_tau2, stratum_i2 | the stratum's τ² and I² (per cent) |
| tier_all_units | the unit's registered pooled 2021–2023 tier, against the all-unit μ |
| tier_agrees | `yes` if the stratum tier equals `tier_all_units` |

## D2: targeting alignment, tier shares and the marginal-shift scenario

Written by `python -I src/ext/d2_targeting.py` (plan §3.3, §5.1, §5.2, §9). Exposure is
E_s = min(1, c_s/L_s), the State's share of districts in phase 1 of the campaign, computed from
the counts. The main denominator is the reconstructed one; the registered denominator (16
computable units) is a variant. The generator `default_rng(20261119)` is reset before each
bootstrap and before each permutation.

- **Reading.** These are observational State-level associations. Low or negative alignment is
  described as campaign districts not being concentrated in States of higher prior yield. This
  is consistent with selection on the published criteria (burden, vulnerability, mortality)
  rather than on yield; that is not tested, and it is not read as a targeting failure. No
  conditioning model is fitted. The §8 label of ρ needs the specification curve and is given
  by a later script, not here.

### d2_alignment.csv (one row per specification)

Rows:

- `main`: pooled 2021–2023 empirical-Bayes posterior mean (`d1_states.csv`), reconstructed
  denominator, weighted by 2023 screened, all units;
- `unweighted`, `registered denominator`, `2023 yield` and `2023 empirical Bayes`: the main
  specification with one axis changed.

The full 24-entry grid of §7.1 (including the small-UT axis) is written later, with the
robustness analyses.

| Column | Meaning |
|---|---|
| analysis | as above |
| measure | `pooled_eb` (pooled 2021–2023 posterior mean, §4.2), `yield_2023` (D/S in 2023; a zero yield is kept and takes the lowest rank) or `eb_2023` (single-year 2023 posterior mean, §4.2; zero-diagnosed units excluded) |
| denominator | `reconstructed` or `registered` |
| weights | `screened_2023` (w_s = S_s,2023) or `none` (w_s = 1) |
| units | `all` |
| estimate | ρ: average ranks (`scipy.stats.rankdata`, unweighted), then the weighted Pearson correlation of the ranks, Σw(x − x̄_w)(y − ȳ_w)/√(Σw(x − x̄_w)²·Σw(y − ȳ_w)²) |
| null | 0 |
| boot_lo, boot_hi | bootstrap of units (`rng.integers(0, n, size=n)`; ranks recomputed in each draw), percentile interval (`numpy.quantile`, linear). The yield measure is held fixed (not re-estimated) in the bootstrap |
| draws, n_valid, degenerate | bootstrap draws (10,000), draws used, and draws in which either variable was constant (counted and excluded) |
| perm_lo, perm_hi | null band: 2.5th and 97.5th percentiles (linear) of ρ over 10,000 permutations (`rng.permutation(n)`) of the exposure ranks over units; the yield ranks and the weights stay with their units. No P value is computed |
| permutations | 10,000 |
| outside_band | `yes` if the observed ρ lies outside the null band |
| n | units in the correlation |
| n_listed, listed | units lacking an exposure, a measure value or a weight, with the reason |

With weights S_s,2023, a few States with very large screening volumes carry most of the weight.
The unweighted row shows the correlation with every State counted once.

### d2_tier_shares.csv (one row per tier)

These are descriptive counts (§5.1).

| Column | Meaning |
|---|---|
| classification | `registered pooled 2021-2023` (the tiers of `d1_states.csv`), or `robust (post hoc)`: the registered tier where it agrees with the between-year tier of `d1_states_betweenyear.csv` (plan §10, 19 November 2026), otherwise `not robust` |
| tier | `above`, `overlaps`, `below`, `not robust` (post hoc only) or `no tier` (no pooled value) |
| n_units, units | units in the tier |
| campaign_districts | phase-1 campaign districts (`campaign_count`) in those units |
| total_campaign_districts | all phase-1 campaign districts in the exposure file |
| share | campaign_districts ÷ total_campaign_districts |

### d2_scenario.csv (one row per scenario)

The scenario is an illustration, not a forecast. It assumes the within-State association ε
(§4.3) would hold under reallocation.

- **The shift.** B is the `below` units and A the `above` units, each with 2023 screened and
  diagnosed present (a printed zero is kept). Each B unit loses 10% of its 2023 screening
  (r = −0.10). The moved volume M = 0.10·Σ_B S goes to A in proportion to 2023 volume
  (r = M/Σ_A S for every A unit). Total screening is unchanged.
- **Expected change.** ΔD = Σ_{A∪B} D_2023[(1 + r)^ε − 1], with D_2023 held fixed. The
  interval applies the formula to each valid bootstrap draw of ε from `d1_elasticity.csv` (the
  same draws, in the same order) and takes the percentile interval (linear).

Rows:

- `main`: the registered pooled 2021–2023 tiers and the main ε;
- `stratum elasticity` (registered sensitivity, §5.2): each unit takes the ε of its intensity
  stratum (`d1_intensity_strata.csv`); stratum draws are paired by draw index, and a pair with a
  degenerate draw in either stratum is excluded;
- `robust tiers (post hoc)`: A and B are the units whose tier is `above` or `below` under both
  the registered and the between-year analysis, with the main ε.

| Column | Meaning |
|---|---|
| analysis, status | as above; `main`, `sensitivity` or `post hoc sensitivity` |
| tiers | the tier classification used |
| elasticity, epsilon | `main` or `intensity stratum`, and the point ε (per stratum for the stratum row) |
| share | the share of B's 2023 screening moved (0.1) |
| computable | `no` if A or B is empty (then `reason` says which) |
| n_gainers, gainers | A: units that gain screening |
| n_losers, losers | B: units that lose screening |
| screened_before, screened_after | Σ_{A∪B} 2023 screened before and after the shift (equal up to rounding) |
| moved | M |
| r_gain, r_loss | the proportional change in screening for A and for B units |
| diagnosed_2023 | Σ_{A∪B} D_2023 |
| delta | ΔD, the expected change in diagnoses at the point ε |
| ci_lo, ci_hi | percentile interval of ΔD over the valid ε draws |
| pct, pct_lo, pct_hi | ΔD and its interval as a percentage of Σ_{A∪B} D_2023 |
| draws, n_valid, degenerate | ε draws (10,000), draws used, and degenerate draws excluded |
| n_excluded, excluded | `above` or `below` units left out for lack of 2023 screened or diagnosed |
| reason | why a scenario is not computable (blank otherwise) |

### d2_scenario_units.csv (one row per gaining or losing unit per scenario)

| Column | Meaning |
|---|---|
| analysis | the scenario row of `d2_scenario.csv` |
| unit, tier | the unit and its tier in that classification |
| side | `gains` (A) or `loses` (B) |
| screened_2023, diagnosed_2023 | the unit's 2023 S and D |
| r | its proportional change in screening |
| screened_after | S·(1 + r) |
| epsilon | the ε applied to the unit |
| delta | D·[(1 + r)^ε − 1] at the point ε |
