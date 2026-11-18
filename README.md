# India's active case-finding figures and the 100-day TB Mukt Bharat Abhiyaan

Active case finding (ACF) is a pillar of India's National TB Elimination
Programme. From 7 December 2024 the Central TB Division ran a 100-day
intensified campaign, the TB Mukt Bharat Abhiyaan, first in 347 districts and
later more widely. Official documents report national campaign totals that
differ from one another, and two published studies of ACF quality report
indicators that do not match.

This repository holds a study of those figures:

- **Q1. Consistency.** Do the published ACF and campaign figures agree across
  sources and dates, and does each source's own arithmetic hold?
- **Q2. Definitions.** Where figures disagree, is the difference explained by
  an arithmetic error, a difference in definition, or a difference in window
  or cut-off date?
- **Q3. Yield.** Where published by State, what are the State-level ACF yields?
- **Q4. Dose-response.** Did TB notifications rise more, against each State's
  own trend, in States with a larger share of their districts in phase 1 of
  the campaign? This is an ecological association, not a causal estimate.

The study is about measurement and evidence. It does not question the value
of screening, and a discrepancy it cannot explain is reported as unexplained,
not as an error by anyone.

## Pre-registration

The analysis plan, [`docs/analysis_plan.md`](docs/analysis_plan.md), is dated
18 November 2026. It was committed and pushed to this public repository
**before any figure was extracted from a source document and before any
computation**. The commit history and GitHub's timestamps are the record of
that order. Any later change to the plan is logged, with its date, in the
plan's Deviations section (§13). Any analysis not in the plan is labelled
exploratory.

Committed with the plan:

- the study design:
  [`docs/superpowers/specs/2026-11-18-acf-campaign-design.md`](docs/superpowers/specs/2026-11-18-acf-campaign-design.md);
- the implementation plan:
  [`docs/superpowers/plans/2026-11-18-acf-campaign.md`](docs/superpowers/plans/2026-11-18-acf-campaign.md);
- the source-search note, which records document titles, headings, windows and
  cut-off dates but no figure values: [`docs/source_search.md`](docs/source_search.md);
- the search log: [`data/search_log.csv`](data/search_log.csv).

## Data

All inputs are published, aggregate, official data of the Government of India:

- documents of the Central TB Division, Ministry of Health and Family Welfare;
- releases of the Press Information Bureau;
- answers to questions in the Lok Sabha and Rajya Sabha;
- editions of the *India TB Report*;
- the Local Government Directory.

Two peer-reviewed studies of ACF quality are also used. The source files are
not redistributed. A fetch script will download them from their official
URLs and verify each against the SHA-256 digest recorded in the plan (§3).

## Reproducing the analysis

The commands to reproduce the analysis will follow when the code is written.
The software versions are pinned in [`ENVIRONMENT.md`](ENVIRONMENT.md).
Analysis code uses the Python standard library only; `pdfplumber` is used for
PDF extraction only.

## Licence

- Code: MIT ([`LICENSE`](LICENSE)).
- Derived data and outputs: CC BY 4.0 ([`LICENSE-DATA`](LICENSE-DATA)).

`CITATION.cff` lists MIT only. The Citation File Format reads several listed
licences as alternatives, so the CC BY 4.0 licence of the derived data is
stated here and in `LICENSE-DATA` instead.

## Citation

See [`CITATION.cff`](CITATION.cff).

## Author

Siddalingaiah H S, Department of Community Medicine, Shridevi Institute of
Medical Sciences and Research Hospital, Tumkur, Karnataka, India.
ORCID [0000-0002-4771-8285](https://orcid.org/0000-0002-4771-8285).
