# Extension analysis plan: where does active case finding still pay?

**Date of this plan:** 19 November 2026
**Author:** Siddalingaiah H S, MD, Professor, Department of Community Medicine, Shridevi Institute of Medical Sciences and Research Hospital, Tumkur, Karnataka, India. ORCID 0000-0002-4771-8285. Single author.
**Repository:** https://github.com/hssling/india-tb-acf-campaign
**Status:** registered before any estimate of §4–§7 was computed. The registration point (commit SHA and UTC time of the public push) is recorded in `docs/registration_event_ext.json` and in §10.
**Design:** the extension design of 19 November 2026 (`docs/superpowers/specs/2026-11-19-acf-extension-design.md`). Where this plan and the design differ, this plan governs.
**Relation to the original plan:** `docs/analysis_plan.md` was registered at commit 2a422a2 (pushed 2026-11-18T17:59:29Z), and its deviations are logged in its §13. This extension is registered after that plan and after the v1.0.0 results (Zenodo 10.5281/zenodo.24371585). It does not edit the original plan, which stays frozen above its §13. The v1.0.0 results keep their registered and post hoc labels. The analyses below are reported as pre-specified extension analyses, registered after the original plan.

**Refinements fixed here.** These close choices that the design left open:

- the zero rule also applies where unit-years are summed before a logarithm (§3.3);
- the posterior SD is the plug-in value (§4.2);
- the main D2 correlation is weighted by 2023 screened (§5.1);
- the main D3 weights are the inverse Poisson variance of the outcome (§6, §7.1);
- the continuity correction adds 0.5 to every diagnosed count (§7.1);
- the agreement share has the whole grid as its denominator (§8).

---

## 1. Questions

- **D1. Where does screening still pay, and why is yield falling?** Robust State yields over time; how diagnoses scale with screening volume within States; and whether the fall in yield is accounted for by fewer screened people being tested or by fewer tests being positive.
- **D2. Was campaign screening aimed where yield was highest?** Alignment between each State's campaign district share and its prior yield, and an illustrative marginal-shift scenario.
- **D3. Do State notifications move with State ACF diagnoses?** The within-State association between ACF diagnoses and notifications, read against the reference values of full addition and full substitution.

The elasticity (D1), D2 and D3 are observational State-level associations. No result is described in causal terms.

## 2. What had been seen before this plan

- **Data.** Every value used below had already been extracted and checked (`data/extracted/`, digests in `data/source_manifest.csv`). The State ACF and notification tables had therefore been read.
- **v1.0.0 outputs.**
  - `outputs/q3_yield.csv` and `outputs/q3_yield_summary.csv` give each State's diagnosed ÷ screened (yield per 100,000, and NNS, with Wilson intervals) for data years 2018, 2019, 2021, 2022 and 2023. They also give the GHA 2023 State rows for 2021. The national yield series in `outputs/q3_yield_summary.csv`, whose decline motivates D1, had been seen.
  - Q1 check 1 tested, State by State, that each printed cascade does not grow (pass or fail; no ratio reported).
  - Q4 (`outputs/q4_*.csv`) used the campaign exposure shares under both denominators and State total notifications for 2019 and 2022–2025.
  - `outputs/q2_quality_studies.csv` recomputed the GHA 2023 and PGPH 2025 cascades.
- **Not computed.** No estimate of §4–§7 had been computed. This includes any pooled or shrunken yield, τ², rank, tier, elasticity or decomposition; the State testing and positivity ratios; any correlation of exposure with yield; the scenario; and any model of notifications on ACF diagnoses.

## 3. Data and units

### 3.1 Panel

One row per unit × data year. Values are taken from the `value` column of the extracted files.

| Data year | ACF table (screened, tested, diagnosed) | Notifications (public, private, total) | Estimated population |
|---|---|---|---|
| 2018 | ITR 2019 Annexure 1.7 | none | none |
| 2019 | ITR 2020 Annexure 6 | ITR 2020 Annexure 1.2 | ITR 2020 Annexure 6 |
| 2021 | ITR 2022 Annexure 6 | none | ITR 2022 Annexure 6 |
| 2022 | ITR 2023 Annexure 6 (the "tested" column is "TB symptomatic identified and examined") | ITR 2023 Annexure 1.2 | none |
| 2023 | ITR 2024 Annexure 6 | ITR 2024 Annexure 1.2 | none |

- **Missing years.** There is no table for 2020.
- **The screened column.** The printed screened heading differs in every edition (mapped population, 2018; mapped vulnerable population, 2019 and 2021; vulnerable individuals screened for symptoms, 2022; total population screened, 2023). Year effects absorb common shifts; State-specific differences are a stated limitation.
- **The 2022 testing column.** It is a different definition and is labelled `examined`. Its use is limited as stated in §4.4.
- **ITR 2023 State rows.** They do not sum to that table's India row. They are used as printed and flagged.
- **Exposure.** E_s = min(1, c_s / L_s), computed exactly from the counts.
  - Main: the reconstructed denominator (`data/extracted/exposure_share_reconstructed.csv`).
  - Registered denominator (`data/extracted/exposure_share.csv`, 16 computable units): reported descriptively, and one axis of the specification curve.
  - The rounded `share` column is not used.
- **Notation.** S, T and D are screened, tested and diagnosed; N is notifications.

### 3.2 Units

- **Coarsened units.** The units are those of §9.4 of the original plan in every year. Merged units are summed: Jammu and Kashmir with Ladakh; Dadra and Nagar Haveli with Daman and Diu; including any further pair recorded under the original §9.4 in `data/source_choices.csv`. A merged unit-year is NA if any member is NA. This gives 32 units in 2018 and 2019 and 35 in 2021–2023.
- **Unbalanced panel.** A unit missing in one year keeps its other years.
- **Small UTs.** For the exclusion axes, these are Andaman and Nicobar Islands; Chandigarh; Dadra and Nagar Haveli and Daman and Diu; Lakshadweep; and Puducherry. This list is not the union-territory set of the original sensitivity analysis S5, which also includes Delhi and Jammu and Kashmir.
- **Unit order.** Wherever an order matters, units are sorted by coarsened canonical name (Python `sorted`).

### 3.3 Zeros and NA

- **NA.** NA cells are listed with the reason and never imputed. A unit-year with NA in a quantity a model needs is left out of that model.
- **Zero diagnoses (as printed).** 2018 Puducherry; 2021 Lakshadweep and Puducherry (and Ladakh, inside Jammu and Kashmir's sum); 2022 Arunachal Pradesh and Lakshadweep; 2023 Andaman and Nicobar Islands, Goa and Lakshadweep.
- **NA or zero screened.** 2019 Lakshadweep (S = 0; T and D blank); 2022 Puducherry (S = 0; examined and D blank); 2023 Manipur (T = 0; D blank).
- **Rules for zero diagnoses.**
  - A unit-year with D = 0 is excluded from every log-scale analysis and listed: pooling, shrinkage, ranks, tiers, the elasticity and the decomposition. This includes sums taken before a logarithm (the 2021–2023 pooled yield, the national decomposition).
  - Analyses on the count or rank scale keep it: the Poisson sensitivity, the D2 2023 yield measure, the scenario, and D3 on the absolute scale.
  - +0.5 is a specification-curve axis only (§7.1).
- **Inconsistent rows.** A unit-year with S = 0 or D ≥ S (log-yield variance undefined or ≤ 0) is listed and excluded from log-scale analyses.
- **Zero notifications.** A unit-year with N = 0 is excluded from the 1/N-weighted and log-scale D3 entries and listed. (No State notification count in the sources is zero.)

## 4. D1: yield, saturation and the cascade

z = `scipy.stats.norm.ppf(0.975)`.

### 4.1 Pooled yield per year (DerSimonian–Laird)

For each year t and each unit s with D, S > 0:

- **Log-yield.** y_s = ln(D_s/S_s), with variance v_s = 1/D_s − 1/S_s, and w_s = 1/v_s.
- **Fixed-effect mean.** μ_F = Σw y / Σw.
- **Heterogeneity.** Q = Σw (y − μ_F)², with k units and C = Σw − Σw²/Σw.
- **Between-State variance.** τ² = max(0, (Q − (k − 1)) / C).
- **I².** I² = max(0, (Q − (k − 1)) / Q) × 100, and 0 if Q = 0.
- **Random-effects weights.** w*_s = 1/(v_s + τ²).
- **Pooled mean.** μ = Σw* y / Σw*, with SE(μ) = √(1/Σw*).
- **Confidence interval.** μ ± z SE(μ).
- **Prediction interval.** μ ± t_{k−2} √(τ² + SE(μ)²), where t_{k−2} = `scipy.stats.t.ppf(0.975, k − 2)`. It requires k ≥ 3.

Reported per year: μ, the CI and the PI on the yield scale (100,000 × exp(·)), with τ², I² and k. The pooled value describes the typical State, not the national ratio.

### 4.2 Empirical-Bayes State yields, ranks and tiers

- **Posterior.** With the year's μ and τ²:
  - B_s = v_s / (v_s + τ²);
  - posterior mean m_s = B_s μ + (1 − B_s) y_s;
  - posterior variance v_s τ² / (v_s + τ²).

  This is the plug-in posterior: the uncertainty in μ and τ² is not propagated, and this is stated as a limitation. If τ² = 0, every m_s = μ with SD 0.
- **Pooled 2021–2023.** For each unit, y_s = ln(ΣD/ΣS) and v_s = 1/ΣD − 1/ΣS, with sums over its 2021, 2022 and 2023 unit-years that pass §3.3. §4.1 and the posterior above are then applied across units. The number of years each unit contributes is reported. This posterior is the D2 measure (§5).
- **Rank intervals.**
  - Z = `rng.standard_normal((10000, n))` in one call, and θ = m + sd·Z.
  - The rank of a unit in a draw is 1 + the number of units with a strictly greater draw (rank 1 is the highest yield).
  - The interval is `numpy.quantile(ranks, [0.025, 0.975], axis=0, method="inverted_cdf")`. If τ² = 0, every rank is 1 and is reported as such.
  - Ranks are computed per year and for the pooled 2021–2023 posterior.
- **Tiers.** The tiers compare each State's own posterior interval m_s ± z·sd_s with the pooled mean μ of the same year (or of the 2021–2023 pooling), not with the prediction interval:
  - **above**, if the lower bound is greater than μ;
  - **below**, if the upper bound is less than μ;
  - **overlaps**, otherwise.

  The output is a tiered map with intervals, not a league table.
- **Intensity sensitivity.** The 2021–2023 pooling, shrinkage and tiers are repeated within each intensity stratum (§4.5), against that stratum's own μ.

### 4.3 Screening volume and diagnoses (elasticity)

- **Model.** ln D_st = α_s + λ_t + ε ln S_st + e_st. It is fitted by weighted least squares with weights w_st = D_st (main).
  - The design is a column ln S, one dummy per unit, and one dummy per year except the earliest year in the sample.
  - It is solved with `numpy.linalg.lstsq` on √w-scaled X and y.
  - Units with one row in the estimation sample are listed and dropped before fitting and before resampling; G, n and p count the remaining units and rows.
- **Main sample.** All five years, all units, and zeros excluded (§3.3).
- **Interpretation.** ε < 1 means that, within States, diagnoses rose less than proportionally with screening volume. The null is 1.
- **Model interval.** The CR1 cluster-robust covariance by unit:
  - V = c (XᵀWX)⁻¹ [Σ_g X_gᵀW_g r_g r_gᵀW_g X_g] (XᵀWX)⁻¹;
  - c = G/(G − 1) × (n − 1)/(n − p), where G is the number of units, n the number of observations and p the number of columns;
  - ε ± t_{G−1} √V_εε.
- **Cluster bootstrap (main interval).**
  - 10,000 draws. Draw b is `rng.integers(0, G, size=G)` over the sorted units.
  - Each drawn unit brings all its rows, and each copy is a separate cluster with its own unit dummy. The model is then refitted.
  - Before the rank check, columns that are all zero in a draw are dropped. A draw is degenerate if √W X is rank-deficient (`numpy.linalg.matrix_rank` less than the number of columns); degenerate draws are counted, excluded and reported.
  - The interval is `numpy.quantile(valid, [0.025, 0.975])` (linear).
- **Reported.** ε, both intervals, the number of units and observations, and the degenerate-draw count.
- **Poisson fixed-effects sensitivity.** D_st ~ Poisson(exp(α_s + λ_t + ε ln S_st)), unweighted, with zeros kept.
  - It is fitted by IRLS, starting from the unweighted least-squares fit of ln(D + 0.5) on the same design, until the maximum absolute coefficient change is less than 10⁻¹⁰, with at most 100 iterations.
  - Units with D = 0 in every year are listed and excluded.
  - Intervals: the CR1 sandwich and the cluster bootstrap above. Its CR1 sandwich uses bread XᵀWX with W = diag(μ̂) and meat Σ_g X_gᵀ(y_g − μ̂_g)(y_g − μ̂_g)ᵀX_g, with c = G/(G − 1) and t_{G−1}. A bootstrap draw that is rank-deficient or does not converge within 100 iterations is degenerate, counted and excluded.
- **Stratified sensitivity.** The main model is fitted separately in each intensity stratum.

### 4.4 Cascade decomposition

**Identity.** ln(D/S) = ln(T/S) + ln(D/T): the testing rate plus the positivity.

- **Main years and the 2022 sensitivity.** The main years are 2018, 2019, 2021 and 2023. 2022 (`examined`) never enters a main row. It is shown as a labelled sensitivity: the variance split for 2022, and the national changes 2021→2022 and 2022→2023.
- **(a) National change, 2021→2023.**
  - The sample is the units with S, T and D present and positive in both years.
  - The sums are ΣS, ΣT and ΣD in each year.
  - Δ ln Y = Δ ln(ΣT/ΣS) + Δ ln(ΣD/ΣT): the change in yield is the testing part plus the positivity part, and the split is exact.
  - The national level of each component is also reported for each main year, on the units present and positive in that year.
- **(b) Between-State variance, each main year.**
  - For each unit, a_s = ln(T/S) and b_s = ln(D/T).
  - var(y) = var(a) + var(b) + 2 cov(a, b), unweighted, with ddof = 1.
  - The covariance is split equally:
    - testing share = (var(a) + cov(a, b)) / var(y);
    - positivity share = (var(b) + cov(a, b)) / var(y).
  - The two shares sum to 1.
- **Intervals.** The cluster bootstrap of §4.3 (10,000 draws, units resampled), percentile intervals for every quantity. The generator is reset before each quantity's bootstrap (the national change, each year's variance split, each 2022 sensitivity). A draw with var(y) = 0 is degenerate, counted and excluded.
- **Cross-check.** The national components are set side by side with the PGPH 2025 cascade, descriptively, with no agreement metric.

### 4.5 Screening intensity strata

- **Population for year t.**
  - P_s,t is the ITR 2020 estimated population for t = 2019.
  - It is the ITR 2022 estimated population for t ∈ {2021, 2022, 2023}, or the 2019 value carried forward if that is missing.
  - 2018 has no earlier population and is not used.
- **Intensity.** intensity_s is the mean of S_s,t / P_s,t over the years in which both are present.
- **Strata.** Units are split at the median (`numpy.median`) over units with an intensity: **high** if the intensity is above the median, otherwise **low**.
- **Unclassified units.** Units without an intensity are listed and left out of the stratified analyses.

## 5. D2: targeting

### 5.1 Alignment

- **Measure.** ρ is the Spearman correlation between E_s and the pooled 2021–2023 posterior mean m_s (§4.2).
- **Spearman.** Average ranks (`scipy.stats.rankdata`, method "average") are taken unweighted. ρ is then the Pearson correlation of the ranks:
  - **weighted:** r_w = Σw(x − x̄_w)(y − ȳ_w) / √(Σw(x − x̄_w)² Σw(y − ȳ_w)²), with weights w_s = S_s,2023;
  - **unweighted:** w_s = 1.
- **Main specification.** Weighted by 2023 screened, reconstructed denominator, all units. Units lacking a value or weight are listed.
- **Interval.** A bootstrap of units: 10,000 draws, `rng.integers(0, n, size=n)`, with ranks recomputed in each draw. A draw in which either variable is constant is degenerate, counted and excluded. The interval is the percentile interval, as in §4.3. m_s is held fixed in the bootstrap; this is a stated limitation.
- **Permutation band.** Exposure is permuted over units 10,000 times (`rng.permutation(n)`) and ρ is recomputed. The exposure ranks are permuted; the yield ranks and the weights stay with their units. Percentiles use `numpy.quantile` (linear). The 2.5th and 97.5th percentiles are reported as a null band, together with whether the observed ρ lies outside it. No P value is reported.
- **Tier shares.** For each pooled 2021–2023 tier, and for "no tier", the report gives:
  - the number of units;
  - the number of phase-1 campaign districts (`campaign_count`);
  - the share of all campaign districts.

  These are descriptive counts.
- **Interpretation.** Low alignment is reported as campaign districts not being concentrated in States of higher prior yield. This is consistent with selection on the published criteria (burden, vulnerability, mortality) rather than on yield, which is not tested, and is not read as a targeting failure. No conditioning model is fitted.

### 5.2 Marginal-shift scenario

- **The shift.** With the pooled 2021–2023 tiers, B is the "below" units and A the "above" units, each with S and D present for 2023.
  - Each unit in B loses 10% of its 2023 screening: r_s = −0.10.
  - The moved volume is M = 0.10 Σ_B S_s,2023. It goes to A in proportion to 2023 volume, so for every unit in A, r_s = M / Σ_A S_s,2023.
  - Total screening is unchanged.
- **Expected change in diagnoses.** ΔD = Σ_{s∈A∪B} D_s,2023 [(1 + r_s)^ε − 1], with the main elasticity ε of §4.3.
- **Interval.** The formula is applied to each valid bootstrap draw of ε, and the percentile interval is taken; D_s,2023 is held fixed.
- **Sensitivity.** Each unit takes the ε of its intensity stratum. Stratum draws are paired by draw index, and a pair with a degenerate draw in either stratum is excluded.
- **Reported.** ΔD and its interval, ΔD as a percentage of Σ_{A∪B} D_s,2023, and the gaining and losing units. If A or B is empty, the scenario is not computable and is reported as such.
- **Status.** It is an illustration, not a forecast; it assumes the within-State association ε would hold under reallocation.

## 6. D3: additionality

- **Absolute scale (main).** N_st = α_s + λ_t + θ A_st + e_st, where:
  - N is public-sector notifications (ITR Annexure 1.2);
  - A is ACF diagnosed (§3.1);
  - t ∈ {2019, 2022, 2023}, all units;
  - the weights are 1/N_st, the inverse Poisson variance of N_st;
  - the design, model interval and cluster bootstrap are those of §4.3;
  - units with one row in the estimation sample are listed and dropped before fitting and before resampling; G, n and p count the remaining units and rows.

  θ is the within-State difference in public notifications associated with one more ACF diagnosis. If the association were causal, θ = 1 would correspond to full addition and θ = 0 to full substitution; these are reference values only. The null is 0.
- **Log scale.** ln N_st = α_s + λ_t + θ_log ln A_st + e_st, with weights N_st (the inverse Poisson variance of ln N_st) and unit-years where A = 0 excluded (§3.3). The null is 0.
- **Secondary outcome.** Total notifications (ITR Annexure 1.2 totals).
- **Thin data.** Only three years overlap, so θ rests on within-State change across three years. This is reported as a limitation.
- **Cross-check.** The GHA 2023 State ACF share of public notifications (2021) is set beside the panel, descriptively.

## 7. Robustness

### 7.1 Specification curves

Each grid is the full crossing below. The first level of each axis is the main specification, except where a different main level is named. Every entry reports its point estimate and cluster-bootstrap interval (§4.3, §5.1), with the random-number generator reset before each entry.

| Estimate | Axes | Entries | Null |
|---|---|---|---|
| D1 elasticity ε | weights {D, none} × zero {exclude, +0.5} × years {all five, excluding 2022, 2021–2023} × units {all, excluding small UTs} | 24 | 1 |
| D2 correlation ρ | measure {pooled EB 2021–2023, 2023 yield, 2023 empirical-Bayes posterior mean (§4.2, single year)} × denominator {reconstructed, registered} × weights {none, 2023 screened} × units {all, excluding small UTs} | 24 | 0 |
| D3 θ | outcome {public, total} × scale {absolute, log} × weights {none, inverse Poisson variance (1/N absolute, N log)} × units {all, excluding small UTs} | 16 | 0 |

- **The +0.5 axis.** 0.5 is added to D in every unit-year, so zeros enter; the weight D becomes D + 0.5.
- **D2.**
  - The main level of the weights axis is 2023 screened (§5.1).
  - The 2023 yield is D/S. A zero yield is kept and takes the lowest rank.
  - The 2023 empirical-Bayes measure is the 2023 posterior mean of §4.2; zero-diagnosed units are excluded from it (§3.3) and listed.
  - The small-UT axis restricts the correlation sample only. The pooled measure is not recomputed.
- **D3.** The weighted level is the inverse Poisson variance of the outcome: 1/N_st on the absolute scale and N_st on the log scale, where N is that entry's outcome. It is the main level.
- **Limitation.** The weights D, 1/N and N are functions of the outcome; the unweighted entries (and, for ε, the Poisson model) address this.

### 7.2 Leave one out

These use the main specification, with point estimates only and no bootstrap. The minimum, the maximum and the most influential omission are reported. The most influential omission is the one with the largest absolute difference from the main estimate (ties: first in sorted order).

- **Leave one State out.** ε, ρ and θ are refitted omitting each unit in turn. For ρ, the unit is omitted from the correlation sample only; the pooled measure is not recomputed.
- **Leave one year out.**
  - ε: each of the five years.
  - θ: each of 2019, 2022 and 2023.
  - ρ: each of 2021, 2022 and 2023, with the pooling and shrinkage of §4.2 rerun on the remaining two years.

## 8. Interpretation rules, fixed in advance

- **Supported.** A headline estimate (ε, ρ, θ) is "supported" only if both of these hold:
  - its main 95% interval (the cluster-bootstrap interval for ε and θ; the bootstrap interval for ρ) excludes its null (1, 0, 0);
  - at least 80% of its specification-curve entries lie on the same side of the null as the main estimate.

  Otherwise it is "not established", and its interval is stated.
- **The agreement share.** Its denominator is the whole grid (24, 24, 16). An entry that cannot be computed counts as not agreeing and is listed. An entry exactly at the null does not agree. The share whose interval also excludes the null is reported beside it.
- **Wording.**
  - A supported ε < 1 is described as diagnoses rising less than proportionally with screening within States, consistent with diminishing returns.
  - A supported ρ is described as alignment (positive) or misalignment (negative) with prior yield.
  - A supported θ is described as an association, with 1 and 0 as the reference values. No causal wording is used.
- **Other results.** Pooled yields, tiers, the decomposition and the scenario are reported with their intervals and carry no label. Leave-one-out results and the permutation band are reported beside the headline; they do not change its label.
- **ITR 2023 sum gap.** The ITR 2023 sum-gap rows (data year 2022) are covered by the 'excluding 2022' level for ε and by leaving out 2022 for θ and ρ (§7.2).
- **Statistics.** No P values are reported.

## 9. Seeds and reproducibility

- **Software.** Python 3.14, run as `python -I`. numpy 2.3.5 and scipy 1.16.3 are used for the extension only; the v1.0.0 pipeline stays standard-library only and byte-reproducible.
- **Seed.** `rng = numpy.random.default_rng(20261119)` is reset before each analysis. An analysis is one of the following:
  - one year's rank draws, or the pooled rank draws;
  - one bootstrap (each main estimate, each stratum, the Poisson model, each decomposition quantity, each specification-curve entry);
  - the permutation.

  The scenario reuses the elasticity draws.
- **Draw counts.** 10,000 bootstrap draws, 10,000 parametric rank draws and 10,000 permutations.
- **Outputs.** UTF-8 CSV with LF endings, byte-reproducible. Every estimate carries its 95% interval and n.
- **Order of work.** No estimate of §4–§7 is computed before this plan is pushed and its push is recorded.

## 10. Deviations

The registration point (commit and UTC time of the public push) is recorded in `docs/registration_event_ext.json`. The text above this section is frozen at that commit. Later changes are logged below as dated entries, appended only. Anything exploratory is labelled as such in code and output.

**19 November 2026.** None.
