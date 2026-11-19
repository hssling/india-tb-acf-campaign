# Where does active case finding still pay? Extension design

Date: 19 November 2026. Author's request: turn the completed study (v1.0.0, Zenodo 10.5281/zenodo.24371585) into a novel paper that guides policy and practice, using advanced analytics on data already extracted, rather than a critique of published figures. Approved scope: all three dimensions below.

## 1. Intent

Programme managers in India scale up active case finding (ACF) — screening high-risk people to find TB earlier — through the 100-day TB Mukt Bharat Abhiyaan and its expansion. The published State tables of the India TB Reports (2018–2023) have never been analysed as one panel. This paper uses them to answer three questions a manager can act on:

- **D1. Where does screening still pay, and why is yield falling?** Robust State yields over time, how quickly extra screening stops finding extra cases, and whether the national fall in yield comes from fewer screened people being tested or fewer tests being positive.
- **D2. Was campaign screening aimed where yield was highest?** Alignment between each State's campaign district share and its prior yield, and an illustrative reallocation scenario.
- **D3. Does more ACF raise notifications, or shift cases from routine diagnosis?** The association between State ACF diagnoses and State notifications.

The consistency and discrepancy results of v1.0.0 become one short "how to read these figures" box in the paper and a supplement; they are no longer the headline.

## 2. Goals, non-goals, anti-goals

- **Goals:** findings that hold under reasonable alternative choices; uncertainty on every estimate; plain policy implications tied to specific results; full reproducibility from the public repository.
- **Non-goals:** district-level analysis (no published district series); causal effect estimates of the campaign; new data collection or new downloads (the data are already held and verified).
- **Anti-goals (failure even if it runs):** causal language the design cannot support; league-table "good/bad State" rankings without uncertainty; results that depend on one specification, one State or one year without saying so; dropping the honest record of what was registered and what was post hoc.

## 3. Data (all already extracted, digests in data/source_manifest.csv)

- **ACF State panel** (India TB Report annexures; coarsened units as in §9.4 of the registered plan): screened, tested, diagnosed for data years 2018 (ITR 2019), 2019 (ITR 2020), 2021 (ITR 2022), 2022 (ITR 2023: the "tested" column is printed as "symptomatic identified and examined"), 2023 (ITR 2024). No 2020 table. Population mapped (2018, 2019, 2021) and estimated population (2019, 2021).
- **Notifications by State:** public, private and total for 2019, 2022, 2023 (India TB Reports); total for 2023, 2024, 2025 (Rajya Sabha Q1216).
- **Campaign exposure:** phase-1 district share, reconstructed denominator (main) and registered denominator (sensitivity).
- **Quality studies:** GHA 2023 State rows (2021 first cycle; includes ACF share of public notifications) and the PGPH 2025 cascade, used as external cross-checks of D1 and D3.
- Known data notes carried forward: ITR 2023 ACF annexure rows do not sum to its India row; 2022 "tested" is a different definition; Puducherry and a few units have NA cells (listed, never imputed).

## 4. Analyses (my calls as the analyst, to be registered before any is computed)

All estimates have 95% intervals; no P values. Weights, seeds and orderings fixed in the extension plan.

**D1. Yield, saturation and the cascade**
1. *Pooled yield per year:* random-effects meta-analysis of State log-yield (diagnosed/screened) with binomial within-State variance and DerSimonian–Laird between-State variance; pooled mean, 95% CI and 95% prediction interval per year. Shows both the typical State and the spread.
2. *Shrunken State yields and rank uncertainty:* empirical-Bayes State yields per year and pooled over 2021–2023; rank intervals from 10,000 parametric draws. Output is a tiered map (States whose yield interval lies above / overlaps / below the national pooled value), not a league table.
3. *Diminishing returns:* within-State elasticity of diagnoses to screening volume, ln(diagnosed) on ln(screened) with State and year fixed effects; elasticity < 1 means extra screening finds proportionally fewer cases. Cluster bootstrap by State.
4. *Cascade decomposition:* ln(yield) = ln(tested/screened) + ln(diagnosed/tested). (a) National change 2021→2023 split into testing-rate and positivity contributions; (b) between-State variance of ln(yield) each year split into the two components (variance–covariance decomposition). 2022 is excluded from the main decomposition (different "tested" definition) and shown as a sensitivity.

**D2. Targeting**
5. *Alignment:* weighted Spearman correlation between campaign district share and the State's pooled 2021–2023 shrunken yield (and NNS), with bootstrap intervals; plus the share of campaign districts falling in States of each yield tier.
6. *Illustrative reallocation:* holding total screening fixed at its 2023 level, expected cases if screening were distributed in proportion to shrunken yield versus as observed, using the D1 elasticity so that returns diminish (no linear extrapolation). Reported as a scenario with bootstrap intervals and explicitly not as a forecast.

**D3. Additionality**
7. *Panel association:* State public-sector notifications on ACF diagnoses for 2019, 2022, 2023, with State and year fixed effects, absolute scale (slope θ: additional notified cases per additional ACF diagnosis; θ≈1 additive, θ≈0 substitution) and log scale; weighted; cluster bootstrap. Total notifications as a secondary outcome. GHA 2021 State ACF share as an external check of magnitude.

**Robustness across all three**
8. *Specification curve:* for the headline estimates of D1-3, D2-5 and D3-7, every combination of a small, pre-listed set of reasonable choices (weights, units excluded — small UTs, the ITR 2023 sum-gap rows —, denominators, year sets, outcome scale); report the full distribution and the share of specifications agreeing in sign and excluding zero.
9. Leave-one-State-out and leave-one-year-out for each headline estimate; permutation (10,000) for the D2 correlation.

## 5. Registration and honesty

- An extension analysis plan (`docs/extension_plan.md`) fixes the analyses above, their choices and the specification-curve grid, and is pushed to the public repository before any of them is computed. It records what had already been seen: State yields were computed in the v1.0.0 Q3 outputs; nothing in §4 was.
- The paper labels these as pre-specified extension analyses registered after the original plan; the v1.0.0 results keep their registered and post hoc labels.
- Causal wording is excluded: D2 and D3 are associations at State level (ecological).

## 6. Paper and delivery

- **Journal:** Public Health (Elsevier, hybrid; my call — scope covers programme evaluation and practice; limits ≤3,000 words, ≤5 display items, ≤50 references, structured abstract). The current audit-framed manuscript is kept locally as `manuscript_v1_audit/` and is not submitted.
- **Structure:** Introduction (the policy problem) → Methods (data, D1–D3, robustness, registration) → Results by dimension → Discussion as programme actions (where to screen, fixing the testing step, targeting the campaign, what notification data can and cannot show) → a box "How to read official ACF figures" drawn from v1.0.0.
- **Display items (≤5):** 1 national yield and cascade decomposition over time; 2 State yield tiers with uncertainty; 3 targeting alignment and reallocation scenario; 4 additionality estimate with specification curve; 5 table of headline estimates with robustness summary. Everything else in the supplement.
- **Repository:** new modules under `src/ext/`, tests, outputs under `outputs/ext/`, verification extended; release v1.1.0 (new Zenodo version DOI) before submission.

## 7. Constraints

- Python 3.14; numpy 2.3.5 and scipy 1.16.3 are installed and may be used for the extension analyses (my call: matrix algebra and distributions); the v1.0.0 pipeline stays standard-library only.
- `python -I`; LF; seeds fixed; byte-reproducible outputs; manuscript never committed; no new downloads without asking.
- Single author; AI use disclosed as before.

## 8. Approaches considered

- **A. Reframe only** (same analyses, new framing): fastest, but no new insight — rejected by the author's request for novel, advanced analysis.
- **B. Three-dimension extension on the existing panel (chosen):** novel (first panel analysis of the published State ACF tables), actionable, and uses only verified data.
- **C. Fully Bayesian hierarchical model of the whole cascade:** most elegant, but harder to verify and explain to programme readers; the random-effects, empirical-Bayes and fixed-effects estimators in B give the same policy answers with transparent, testable code. Kept as a possible sensitivity, not the main method.

## 9. Settled after the builder check (19 November 2026)

Answered by the conversation:
- **Deliverables** include the manuscript (Public Health), its exhibits, supplement and checks, built as in v1.0.0: tooling committed, manuscript files local and never committed.
- **Registration and release.** Following the v1.0.0 precedent, the analyst (controller) pushes `docs/extension_plan.md` to the public repository before any §4 analysis is computed, and records the push in `docs/registration_event_ext.json` (commit, pushed_at from the GitHub API). The author approved pushing code and outputs and asked for a Zenodo DOI; release v1.1.0 is created by the analyst once the extension is complete and reviewed, before submission. There is a hard gate in the plan between writing the extension plan and computing anything.
- **Units** are the §9.4 coarsened units in every year, with merged units summed (about 33–36 units; five ACF years; three overlap years for D3, which is thin and reported as such).

My calls (marked as such in the extension plan):
- **Zeros and NA.** NA cells are listed and never imputed. Zero diagnoses (2023: Andaman and Nicobar, Goa, Lakshadweep) are excluded from log-scale analyses (pooling, shrinkage, elasticity, decomposition) and listed; a +0.5 continuity correction is one axis of the specification curve; a Poisson fixed-effects count model of diagnoses with ln(screened) as a covariate is a sensitivity for the elasticity.
- **Heterogeneous screening.** Large between-State heterogeneity is a finding to report, not a defect: the paper reports τ² and I² per year and the prediction interval. Tiers compare each State's shrunken yield interval with the national pooled mean (not the prediction interval). A pre-specified stratification by screening intensity (screened per estimated population, using the 2019/2021 population columns carried forward) is a sensitivity.
- **Reallocation scenario.** A marginal-shift scenario rather than a full redistribution: move 10% of the 2023 screening volume from the lowest-yield tier to the highest-yield tier, in proportion to current volume, applying the pooled D1 elasticity (with a by-intensity-stratum elasticity as a sensitivity). This avoids domination by small units and is reported as an illustration with bootstrap intervals.
- **Targeting interpretation.** The paper states the published district-selection criteria (burden, vulnerability, mortality). Alignment with prior yield is descriptive; low alignment is read as "selection followed burden criteria rather than ACF yield", not as a targeting failure. No conditioning model. The registered (16-unit) denominator is reported descriptively and as one axis of the specification curve; the reconstructed denominator is the main exposure.
- **Specification-curve criterion.** "Agreement" is judged against each estimate's own null: 1 for the elasticity, 0 for the correlation and for θ.
- **Cross-checks.** GHA 2021 State rows and the PGPH cascade are compared descriptively, side by side; no formal agreement metric.
- **Disclosure wording.** The extension plan states that State diagnosed/screened ratios by year were computed in v1.0.0 (outputs/q3_yield.csv); no estimate in §4 had been computed.

## 10. Left to the builder

Module layout, exact column mappings per edition, the parametric-draw implementation, figure styling within the journal's rules, and test design.
