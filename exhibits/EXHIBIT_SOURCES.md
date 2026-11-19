# Exhibit sources

Every number in an exhibit is read from the files below (or is a count of their rows, with the filter recorded in `manuscript/v1_audit/exhibits/trace.json` (the v1.0.0 manuscript; the extension exhibits are in EXT_EXHIBIT_SOURCES.md)). Nothing is typed in the scripts. `tests/test_exhibits.py` re-derives the traced cells.

| Exhibit | Cell group | File | Column or rule |
|---|---|---|---|
| Table 1 | Figures and documents by quantity | data/figures_inventory.csv | count of rows by `quantity`; distinct `source_file` |
| Table 1 | Other campaign figures | data/figures_inventory.csv | rows whose `quantity` starts with `other:` |
| Table 1 | Q1 checks (registered) | outputs/q1_checks.csv | count of rows by `check` and `pass` |
| Table 1 | Q1 checks (corrected) | outputs/q1_checks_corrected.csv | count of rows by `check` and `pass` |
| Table 2 | Class counts, all and pre-specified | outputs/q2_summary_registered_vs_corrected.csv | `registered`, `corrected` by `metric` |
| Table 2 | Class labels | outputs/q2_discrepancies_corrected.csv | `class_label` |
| Table 2 | Class 1 and 2 pairs | outputs/q2_discrepancies_corrected.csv | `a_value_printed`, `b_value_printed`, `evidence` |
| Table 3 | Screened, diagnosed | outputs/q3_yield_summary.csv | `denominator`, `numerator` (India, yield rows) |
| Table 3 | Yield with interval | outputs/q3_yield_summary.csv | `value`, `lower`, `upper` (yield_diagnosed_per_100000) |
| Table 3 | NNS with interval | outputs/q3_yield_summary.csv | `value`, `lower`, `upper` (nns) |
| Table 3 | Years without a table | outputs/q3_yield.csv | years listed with `state` = (all States) |
| Table 3 | ACF share note | outputs/q3_yield_summary.csv | `value`, `lower`, `upper` (acf_share..., 2021) |
| Figure 1 | Plotted claims | data/figures_inventory.csv | `value`, `qualifier`, `definition_class`, `pub_date` / `window_end` / `as_on`; selection rule in make_figures.py |
| Figure 2 | Points | outputs/q4_states.csv | `E`, `x`, `w` (set D, computable, full-year and placebo contrasts) |
| Figure 2 | Fit lines | outputs/q4_summary.csv | `gamma0`, `gamma1` (set D, `primary` and `placebo`) |
| Table S1 | Pairs and classes by comparison group | outputs/q2_discrepancies.csv, outputs/q2_discrepancies_corrected.csv | row counts by `group_key`, `agree`, `class` |
| Supplementary data S1a, S1b | Every entry pair | outputs/q2_discrepancies.csv, outputs/q2_discrepancies_corrected.csv | one row per output row; columns in make_tables.DATA_COLUMNS (verbatim, or reader names of `quantity`, `scope`, `group_key`, `a_source`, `b_source`) |
| Table S2 | Quality studies | outputs/q2_quality_studies.csv | `published_value`, `recomputed`, `ci95_low`, `ci95_high` |
| Table S3 | State-level yield | outputs/q3_yield_summary.csv | as Table 3, all States |
| Table S4 | Q4 summary | outputs/q4_summary.csv | `gamma1`, intervals, `exp_0_1_gamma1`, `n`, `label`; S2 row `loo_gamma1_min`, `loo_gamma1_max` |
