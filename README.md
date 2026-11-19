# India's active case-finding figures and the 100-day TB Mukt Bharat Abhiyaan

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

## The four questions

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

## Pre-registration and deviations

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

## Repository layout

| Path | Contents |
|---|---|
| `docs/` | analysis plan (§13: deviations), study design, implementation plan, source-search note, journal rules, exhibit plan, registration event |
| `data/source_manifest.csv` | the 34 source files: path, URL or origin, size and SHA-256 |
| `data/search_log.csv` | the document search |
| `data/figures_inventory.csv` | every figure entered from the sources (Q1, Q2) |
| `data/source_choices.csv` | every source choice and extraction decision, with dated addenda |
| `data/extracted/` | tables extracted from the sources, and the exposure, denominator and guard files |
| `data/transcribed/` | web pages and study tables transcribed by hand |
| `data/lgd_evidence/` | official notices behind the reconstructed district denominator (SHA-256 pinned in `MANIFEST.txt`) |
| `src/extract/` | extraction scripts |
| `src/q1_consistency.py` ... `src/q4_dose_response.py` | the analyses |
| `outputs/` | results (CSV) and their README |
| `exhibits/` | builders of the tables and figures (written to `manuscript/exhibits/`, which is git-ignored) |
| `verification/` | checks of plan order, deviations, extraction totals, inventory and outputs |
| `tests/` | pytest suite |
| `tools/` | `fetch_sources.py`; the submission build (`build_submission.py`, `*.ps1`, Windows and Microsoft Word only) |

Source documents are not redistributed. They go in `data_raw/`, which is
git-ignored.

## Reproducing

Software versions are in [`ENVIRONMENT.md`](ENVIRONMENT.md). The analysis uses
the Python standard library, with pdfplumber for PDF extraction. Run every
command from the repository root with `python -I`.

### 1. Place the sources

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

### 2. Run the pipeline, in this order

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
- The exhibits are written to `manuscript/exhibits/`.

### 3. Verify

```
python -I verification/check_all.py
```

This runs the test suite and every check, and prints PASS, FAIL or SKIP for
each step. In a fresh clone the two manuscript checks are skipped, because the
manuscript is not in this repository.

## Status

A manuscript is under peer review; it is not included in this repository.

## Licences

- Code: MIT ([`LICENSE`](LICENSE)).
- Derived data and outputs: CC BY 4.0 ([`LICENSE-DATA`](LICENSE-DATA)).

`CITATION.cff` lists MIT only. The Citation File Format reads several listed
licences as alternatives, so the CC BY 4.0 licence of the derived data is
stated here and in `LICENSE-DATA` instead.

## Citation

See [`CITATION.cff`](CITATION.cff). The archived release's DOI will be added
there when the release is made.

## Author

Siddalingaiah H S, Department of Community Medicine, Shridevi Institute of
Medical Sciences and Research Hospital, Tumkur, Karnataka, India.
ORCID [0000-0002-4771-8285](https://orcid.org/0000-0002-4771-8285).
