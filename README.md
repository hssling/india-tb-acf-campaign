# Where does active case finding for TB still pay in India?

Code, data and two pre-registered plans for a study of India's published active
case-finding (ACF) figures for tuberculosis. It uses only published, aggregate
data. The repository has two parts. Part 1 is the extension (release v1.1.0),
which asks three policy questions of State-level data. Part 2 is the v1.0.0
audit of the published figures, which the extension builds on.

## Part 1: the extension (v1.1.0)

### Three policy questions and what the analysis shows

The three questions are in [`docs/extension_plan.md`](docs/extension_plan.md),
which was registered before any extension estimate was computed (commit
6a98549, 19 November 2026; [`docs/registration_event_ext.json`](docs/registration_event_ext.json)).
All results are observational associations between States. None is a causal
estimate. A headline is labelled "supported" only if its 95% interval excludes
its null and at least 80% of its specification-curve entries lie on the same
side of the null (plan §8); otherwise it is labelled "not established".

| Question | Headline estimate (95% bootstrap interval) | Label |
|---|---|---|
| **D1. Where does screening still pay?** Within a State, how do ACF diagnoses scale with the number screened? | Elasticity 0.24 (0.02 to 0.51); null 1. Within States, diagnoses rose less than proportionally with screening volume, consistent with diminishing returns | **Supported** |
| **D2. Was campaign screening aimed where yield was highest?** | Spearman correlation of a State's phase-1 district share with its pooled 2021-2023 yield -0.82 (-0.93 to 0.02); null 0 | **Not established** |
| **D3. Do notifications move with ACF diagnoses within a State?** | Difference in public notifications per additional ACF diagnosis -0.17 (-2.20 to 1.80); null 0; reference values 0 and 1 | **Not established** |

- The D1 label is "supported" and the other two are "not established". The D1
  cluster-robust model interval is -0.08 to 0.56; both D1 intervals exclude 1.
  Leave-one-out and specification-curve results are beside each estimate in
  `outputs/ext/headline.csv`.
- The ITR 2023 State rows do not sum to that table's India row; they are used
  as printed and flagged.
- D1 also gives pooled State yields with tiers, a screening-intensity
  stratification and a decomposition of the yield fall into testing and
  positivity. D2 gives a marginal-shift illustration. These carry no label.
- The extension's outputs, columns and limitations are in
  [`outputs/ext/README.md`](outputs/ext/README.md).

### Deviations

Each is a dated entry in §10 of the extension plan (the text above §10 is
frozen):

- **Post hoc between-year tier sensitivity.** The registered State tiers use
  binomial variance only. A sensitivity that includes between-year variation
  within a State was added after the registered tiers were seen. A tier is
  called robust only if it agrees under both.
- **2019 population misprint.** The ITR 2020 estimated-population column is
  misaligned with its State rows as printed. It is not used, and screening
  intensity uses the ITR 2022 population. The registered rule is still
  computed beside it.
- **Post hoc same-definition elasticity.** The printed screened heading
  differs between editions. State-specific shifts in the screened count would
  most likely bias the elasticity towards 0. After every registered estimate
  was seen, the main elasticity was refitted on the two data years whose
  screened heading is the same, 2019 and 2021
  (`outputs/ext/d1_elasticity_samedef.csv`). It changes no registered estimate
  or label.

`verification/check_plan_order.py` checks that the extension registration commit
precedes every commit touching `outputs/ext/` or the D1, D2, D3 and robustness
modules, and that the extension plan text above §10 is byte-identical at every
later commit. `verification/check_ext_outputs.py` recomputes the panel totals,
the pooled yields, the main elasticity, correlation and notification
association, and the three labels with its own code. It does not re-derive
bootstrap or permutation intervals; the seeded build reproduces them.

### Reproducing the extension

The panel reads the committed tables in `data/extracted/`, so the v1.0.0
pipeline of Part 2 and the source documents are not needed. Run from the
repository root, in this order. Software versions are in
[`ENVIRONMENT.md`](ENVIRONMENT.md); the extension needs numpy and scipy.

```
python -I src/ext/panel.py
python -I src/ext/d1_yield.py
python -I src/ext/d1_saturation.py
python -I src/ext/d2_targeting.py
python -I src/ext/d3_additionality.py
python -I src/ext/robustness.py
```

None of these scripts takes arguments. `panel.py` writes `data/ext/`; the others
write `outputs/ext/`. The seeded bootstraps make the full extension build take
several minutes, and the full test suite about six. `python -I
verification/check_all.py` (Part 2, step 3) then checks everything.

The extension's tables and figures are built from `outputs/ext/` (the figures
need matplotlib) and written to `manuscript/ext/exhibits/`, which is git-ignored:

```
python -I exhibits/make_ext_tables.py
python -I exhibits/make_ext_figures.py
```

## Part 2: the v1.0.0 audit (India's active case-finding figures and the 100-day TB Mukt Bharat Abhiyaan)


India's National TB Elimination Programme publishes active case-finding (ACF)
figures in its annual India TB Reports, in parliamentary answers and in press
releases. From 7 December 2024 the Central TB Division ran a 100-day intensified
TB campaign, the TB Mukt Bharat Abhiyaan, first in 347 districts and then more
widely, and official documents give national totals for it. This repository
holds a pre-registered study of those published figures. It uses only
published, aggregate data.

The study is about measurement. It checks whether the published figures agree
with each other and with their own arithmetic, explains the disagreements where
the documents allow, computes State ACF yields, and asks whether State TB
notifications rose more where more of a State's districts were in the
campaign's first phase. It does not question the value of screening. A
difference that the documents do not explain is reported as unexplained, not
as anyone's error. The Q4 association is ecological, not causal.

### The four questions

- **Q1. Consistency.** Do the published ACF and campaign figures agree across
  sources and dates, and does each source's own arithmetic hold?
- **Q2. Definitions.** Where figures disagree, is the difference explained by
  arithmetic, by a difference in definition, or by a difference in window or
  cut-off date?
- **Q3. Yield.** Where a table gives them by State, what are the State ACF
  yields?
- **Q4. Dose-response.** Did TB notifications rise more, against each State's
  own trend, in States with a larger share of their districts in phase 1 of
  the campaign?

### Pre-registration and deviations

The analysis plan, [`docs/analysis_plan.md`](docs/analysis_plan.md), was
committed and pushed to this public repository on 18 November 2026 (commit
2a422a2; [`docs/registration_event.json`](docs/registration_event.json)). This
was before any figure was extracted from a source document. The text above its
§13 is frozen, and `verification/check_plan_order.py` checks that it is
byte-identical at every later commit. Every later change is a dated entry in
§13 (Deviations). [`outputs/README.md`](outputs/README.md) explains the output
files and their labels.

Two deviations change what is reported:

- **Q4 denominator.** The registered rule for the district denominator (§9.3)
  could rebuild the number of districts at 7 December 2024 for only 16 units.
  The main Q4 analysis therefore uses a district denominator reconstructed
  from official notices, which is a deviation (§13). It covers 35 units. The
  registered 16-unit analysis is also reported, in the same output files.
- **Q1 and Q2 rules.** Q1 and Q2 are reported twice. One set uses the rules as
  registered. The other set (`*_corrected` files) uses corrected rules, which
  are post hoc because they were set after the registered output was seen.

### Repository layout

| Path | Contents |
|---|---|
| `docs/` | analysis plan (§13: deviations), extension plan (`extension_plan.md`, §10: deviations), study designs, implementation plans, source-search note, journal rules, exhibit plan, registration events |
| `data/source_manifest.csv` | the 34 source files: path, URL or origin, size and SHA-256 |
| `data/search_log.csv` | the document search |
| `data/figures_inventory.csv` | every figure entered from the sources (Q1, Q2) |
| `data/source_choices.csv` | every source choice and extraction decision, with dated addenda |
| `data/extracted/` | tables extracted from the sources, and the exposure, denominator and guard files |
| `data/transcribed/` | web pages and study tables transcribed by hand |
| `data/lgd_evidence/` | official notices behind the reconstructed district denominator (SHA-256 pinned in `MANIFEST.txt`) |
| `src/extract/` | extraction scripts |
| `src/q1_consistency.py` ... `src/q4_dose_response.py` | the v1.0.0 analyses |
| `src/ext/` | the extension: panel, D1 yield and saturation, D2 targeting, D3 additionality, robustness (numpy and scipy) |
| `data/ext/` | the State-by-year panel built from `data/extracted/` by `src/ext/panel.py` |
| `outputs/ext/` | extension results (CSV) and their README |
| `outputs/` | results (CSV) and their README |
| `exhibits/` | builders of the tables and figures (written to the git-ignored `manuscript/v1_audit/exhibits/` for v1.0.0 and `manuscript/ext/exhibits/` for the extension) |
| `verification/` | checks of plan order (both registrations), deviations, extraction totals, inventory, outputs and the extension's headline values and labels |
| `tests/` | pytest suite |
| `tools/` | `fetch_sources.py`; the submission build (`build_submission.py`, `*.ps1`, Windows and Microsoft Word only) |

Source documents are not redistributed. They go in `data_raw/`, which is
git-ignored.

### Reproducing

Software versions are in [`ENVIRONMENT.md`](ENVIRONMENT.md). The analysis uses
the Python standard library, with pdfplumber for PDF extraction. Run every
command from the repository root with `python -I`.

#### 1. Place the sources

```
python -I tools/fetch_sources.py
```

This downloads the sources that have a public URL: the Central TB Division and
PIB documents, the India TB Reports and the PMC supplement. Then it verifies
all 34 files in `data/source_manifest.csv` against their SHA-256 digests. It
fails if a file is missing or differs.

The author-supplied files cannot be fetched by script. Place each one by hand
at the path given in the manifest, whose `url` column starts
`author-supplied:`:

- 14 parliamentary answers from the sansad.in archives, in `data_raw/pq/`;
- 3 Local Government Directory reports, in `data_raw/lgd/`;
- 3 Figshare files, in `data_raw/studies/`: the Global Health Action 2023
  dataset (doi 10.6084/m9.figshare.23723748) and the PLOS Global Public Health
  2025 codebook and programme file (Figshare items 25106084 and 25106096).

PMC usually refuses the scripted download of the Global Health Action 2023
supplement (it serves a web page, which the content check rejects). In that
case save `data_raw/studies/ZGHA_A_2256129_SM2351.docx` by hand from a browser.
Then run `python -I tools/fetch_sources.py` again to verify all 34 files.

#### 2. Run the pipeline, in this order

```
python -I src/extract/lgd.py
python -I src/extract/campaign.py
python -I src/extract/quality_studies.py
python -I src/extract/pq.py
python -I src/extract/itr.py
python -I src/extract/online_pages.py
python -I src/extract/pq_more.py
python -I src/extract/source_choices.py
python -I src/q4_dose_response.py --guard
python -I src/extract/source_choices.py
python -I src/q1_consistency.py
python -I src/q2_reconcile.py
python -I src/q3_yield.py
python -I src/q4_dose_response.py --q4
python -I exhibits/make_tables.py
python -I exhibits/make_figures.py
```

- The second `source_choices.py` run records the guard result in
  `data/source_choices.csv`.
- `online_pages.py` reads web pages that were transcribed into
  `data/transcribed/online_pages.csv`, not live pages.
- `make_figures.py` needs matplotlib.
- The exhibits are written to `manuscript/v1_audit/exhibits/`, which is
  git-ignored.

#### 3. Verify

```
python -I verification/check_all.py
```

This runs the test suite and every check, and prints PASS, FAIL or SKIP for
each step. In a fresh clone the two manuscript checks are skipped, because the
manuscript is not in this repository.

### Status

A manuscript based on the extension is being submitted; the v1.0.0 audit has
not been published as an article. The manuscript is not included in this
repository.

### Licences

- Code: MIT ([`LICENSE`](LICENSE)).
- Derived data and outputs: CC BY 4.0 ([`LICENSE-DATA`](LICENSE-DATA)).

`CITATION.cff` lists MIT only. The Citation File Format reads several listed
licences as alternatives, so the CC BY 4.0 licence of the derived data is
stated here and in `LICENSE-DATA` instead.

### Citation

See [`CITATION.cff`](CITATION.cff). The releases are archived on Zenodo. The
concept DOI [10.5281/zenodo.24371584](https://doi.org/10.5281/zenodo.24371584)
always resolves to the latest version. Each release also has its own version
DOI; that of v1.0.0 is
[10.5281/zenodo.24371585](https://doi.org/10.5281/zenodo.24371585).

### Author

Siddalingaiah H S, Department of Community Medicine, Shridevi Institute of
Medical Sciences and Research Hospital, Tumkur, Karnataka, India.
ORCID [0000-0002-4771-8285](https://orcid.org/0000-0002-4771-8285).
