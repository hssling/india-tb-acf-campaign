# Exhibit plan (Public Health: at most 5 tables and figures in the main text)

Built by `exhibits/make_tables.py` and `exhibits/make_figures.py` from `outputs/` and `data/` only. Output is local, in `manuscript/exhibits/` (git-ignored). Source map: `exhibits/EXHIBIT_SOURCES.md`.

## Main text (5)

| Item | Content | Why it is in the main text |
|---|---|---|
| Table 1 | Inventory of figures (by named quantity, with the count of documents) and the Q1 checks, registered and corrected | The base of every later result; shows that the cascade and sum checks mostly pass and where they fail |
| Table 2 | Q2 entry pairs by class, registered and corrected, all and pre-specified; below it the class 1 and class 2 pairs of the corrected set | Q2 is the central finding; the registered/corrected contrast must be visible, and the class 1 and 2 pairs are the headline discrepancies |
| Table 3 | National yield and number needed to screen by data year, with Wilson intervals; 2020 and 2024 shown as having no table | The only quantitative Q3 result at national level |
| Figure 1 | National campaign claims of people screened and TB cases diagnosed or notified, by date of the claim; marker by definition and by lower-bound status | Shows the definitions drifting between notified and diagnosed across sources |
| Figure 2 | Q4 scatter of excess change x against exposure E under the reconstructed denominator (main analysis), with the WLS fit; the placebo as panel B | The Q4 result and its placebo in one view |

The Q4 estimates themselves (gamma1 with intervals) go in the text and Table S1; the figure carries no numbers.

## Figure 1 selection rule

- Population: national (India) claims of people screened and of TB cases (diagnosed or notified), from `data/figures_inventory.csv`, dated on or after 7 December 2024.
- Linkage to the campaign: at least one of three tests: a stated window start of 7 December 2024; scope phase 1 or expanded campaign; a window label among "100-day campaign", "campaign to date", "since december 2024", "first 30 days".
- Claim date: `pub_date`, else `window_end`, else `as_on`.
- De-duplication: a claim repeated with the same document, quantity, value, qualifier, definition class and date is plotted once.
- Excluded: interval claims that start after 7 December 2024 (for example 24 March to 4 July 2026) and claims not tied to the campaign by the three tests.
- Marker: shape by the definition printed with the figure (notified, diagnosed, not stated); hollow when the qualifier is not exact.
- Figure 2, panel A: the y-axis is clipped to -0.15 to 0.35; the one unit above the edge is marked with an arrow and named in the figure notes; the fit is on all units.

## Supplement

| Item | Content |
|---|---|
| Table S1 | Q4 summary: primary and S1 to S8 sensitivity analyses and the placebo, both denominators (R and D) |
| Table S2 | State-level yield and number needed to screen, all data years |
| Table S3a, S3b | Full discrepancy list, registered and corrected rules |
| Table S4 | Reconciliation of the two quality studies |

Main-text count: 3 tables + 2 figures = 5.
