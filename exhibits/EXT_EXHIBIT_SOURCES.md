# Extension exhibit sources

The extension paper (Public Health; "Where does active case finding for TB still pay in India?") has five main display items: Figures 1-4 (`exhibits/make_ext_figures.py`) and Table 1 (`exhibits/make_ext_tables.py`). Everything else is in Tables S1-S8. Both builders read `outputs/ext/` and `outputs/` only and write to `manuscript/ext/exhibits/` (git-ignored); `--out DIR` writes elsewhere.

Nothing is typed in the scripts. Every numeric table cell is recorded in `trace.json`, and every plotted value and every number written on a figure in `figure_trace.json`: exhibit, file, row, column, raw value and formatter. `tests/test_ext_exhibits.py` re-derives each entry from the outputs and checks that every number in a table cell is traced.

| Exhibit | Content | File | Columns or rule |
|---|---|---|---|
| Figure 1A | Pooled yield per data year, CI and PI | outputs/ext/d1_pooled.csv | `yield_per_100k`, `ci_*_per_100k`, `pi_*_per_100k` (rows other than `2021-2023`) |
| Figure 1A | National yield | outputs/q3_yield_summary.csv | `value` (India, `yield_diagnosed_per_100000`) |
| Figure 1B | 2021 to 2023 change and its testing and positivity parts | outputs/ext/d1_decomposition.csv | `estimate`, `boot_lo`, `boot_hi` (`change`, `main`) |
| Figure 1C | Testing share of the between-State variance | outputs/ext/d1_decomposition.csv | `estimate`, `boot_lo`, `boot_hi` (`variance`, `testing_share`; 2022 is the `examined` sensitivity) |
| Figure 2 | Registered posterior yields and intervals, tiers | outputs/ext/d1_states.csv | `post_per_100k`, `post_lo_per_100k`, `post_hi_per_100k`, `tier` (`2021-2023`) |
| Figure 2 | Between-year intervals; robust marking | outputs/ext/d1_states_betweenyear.csv | `post_lo_per_100k`, `post_hi_per_100k`; filled marker if `tier_agrees` = yes |
| Figure 2 | Pooled mean and CI | outputs/ext/d1_pooled.csv | `yield_per_100k`, `ci_*_per_100k` (`2021-2023`) |
| Figure 3A | Campaign district share | outputs/q4_states.csv | `E` (denominator set D, the reconstructed district count, which is the extension's main exposure) |
| Figure 3A | Pooled yield | outputs/ext/d1_states.csv | `post_per_100k` (`2021-2023`) |
| Figure 3A | Circle area: 2023 screened | outputs/ext/d1_states.csv | `screened` (`2023`); for a unit without a 2023 row there, outputs/q3_yield_summary.csv `denominator` (2023) |
| Figure 3A | Weighted and unweighted ρ | outputs/ext/headline.csv; outputs/ext/d2_alignment.csv | `main_value`, `ci_lo`, `ci_hi` (rho); `estimate`, `boot_lo`, `boot_hi` (`unweighted`) |
| Figure 3B | Scenario, registered and robust tiers | outputs/ext/d2_scenario.csv | `delta`, `ci_lo`, `ci_hi` (`main`, `robust tiers (post hoc)`) |
| Figure 4 | Every grid entry | outputs/ext/spec_curve.csv | `value`, `ci_lo`, `ci_hi`, `null`, `main`, `interval_excludes_null` |
| Figure 4 | Agreement and label per estimate | outputs/ext/headline.csv | `n_agree`, `n_entries`, `agreement_share`, `label` |
| Table 1 | Headline rows | outputs/ext/headline.csv | `main_value`, `ci_lo`, `ci_hi`, `null`, `n`, `n_units`, `n_agree`, `n_entries`, `agreement_share`, `n_agree_and_interval_excludes`, `loo_state_*`, `loo_year_*`, `label` |
| Table 1 | Poisson and intensity-stratum ε | outputs/ext/d1_elasticity.csv | `estimate`, `boot_lo`, `boot_hi`, `null`, `n_obs`, `n_units` |
| Table 1 | Unweighted ρ | outputs/ext/d2_alignment.csv | `estimate`, `boot_lo`, `boot_hi`, `null`, `n` |
| Table 1 | θ log scale; total notifications | outputs/ext/d3.csv | `estimate`, `boot_lo`, `boot_hi`, `null`, `n_obs`, `n_units` |
| Table S1 | Pooled yield by year; between-year row | outputs/ext/d1_pooled.csv; outputs/ext/d1_pooled_betweenyear.csv | `k`, yields and intervals, `tau2`, `i2`, `n_above`, `n_overlaps`, `n_below` |
| Table S1 | National yield | outputs/q3_yield_summary.csv | `value`, `lower`, `upper` (India) |
| Table S2 | State tiers | outputs/ext/d1_states.csv; outputs/ext/d1_states_betweenyear.csv; outputs/ext/d1_tiers_by_intensity.csv; outputs/ext/d1_excluded.csv | `years`, posterior and interval, `rank_lo`, `rank_hi`, `tier`, `tier_agrees`, `single_year`, `stratum`; the unit with no pooled value |
| Table S3 | Elasticity variants; decomposition | outputs/ext/d1_elasticity.csv; outputs/ext/d1_decomposition.csv | `estimate`, `boot_*`, `model_ci_*`, `n_obs`, `n_units` |
| Table S4 | Alignment variants; tier shares; scenario; scenario by State | outputs/ext/d2_alignment.csv; d2_tier_shares.csv; d2_scenario.csv; d2_scenario_units.csv | every reported column |
| Table S5 | θ specifications; leave one out | outputs/ext/d3.csv; outputs/ext/leave_one_out.csv | `estimate`, `boot_*`, `model_ci_*`, `n_obs`, `n_units`; `value`, `diff`, `same_side_as_main`, `n`, `note` |
| Table S6 | The full specification grid | outputs/ext/spec_curve.csv | every entry |
| Table S7 | Cross-check with the two quality studies | outputs/ext/crosscheck.csv | `panel_value`, `study_value` |
| Table S8 | How to read official ACF figures (v1.0.0 consistency checks and reconciliation) | outputs/q2_summary_registered_vs_corrected.csv; outputs/q2_discrepancies_corrected.csv | `registered`, `corrected` by `metric`; `class_label` |

Labels are plain language: no file names, section signs, variable names or internal identifiers appear in an exhibit (tested). Figures are greyscale, use U+2212 minus signs, and carry no creation dates, so rebuilding is byte-identical (tested).
