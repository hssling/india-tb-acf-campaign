# Design: do India's active case-finding and TB Mukt Bharat campaign figures add up, and did the campaign find more TB?

Date: 18 November 2026. Single author: Siddalingaiah H S.
Status: design, awaiting the author's approval. Nothing has been extracted or computed.

## 1. Intent

The author wants work the National TB Elimination Programme (NTEP) and the Central TB Division (CTD) can act on: policy- and operations-relevant, and novel. Active case finding (ACF) is a pillar of NTEP. The 100-day TB Mukt Bharat Abhiyaan (from 7 December 2024; 347 districts first, later expanded) is the programme's flagship intensified-ACF campaign. Government statements credit it with screening tens of crores of people.

Three facts motivate the study:

- **Official campaign totals disagree with each other.** Reported national totals for the 100-day phase include 9.02 crore screened and 3.01 lakh cases, 12.97 crore and 7.19 lakh, and an interim 5.63 crore and 1.59 lakh. A later figure of more than 25 crore screened (December 2024 to November 2026) also appears.
- **ACF's share of notifications varies by source:** 2.5% in 2022 (India TB Report) and 1.6% in 2023 (a parliamentary answer).
- **Two peer-reviewed ACF quality studies by the same group disagree.** One uses national aggregates (Global Health Action 2023) and finds 1.0% of screened people tested and 3.7% of tested people diagnosed. The other uses a field cohort (PLOS Global Public Health 2025) and finds 66.3% of presumptive cases tested and 1.6% diagnosed. Their denominators may not match.

No peer-reviewed evaluation of the campaign exists, as found by the novelty check of 18 November 2026. The study does two things:
- (A) it reconciles the published figures, so programme managers know which numbers mean what;
- (B) it tests, with public data, whether states exposed to more of the campaign increased notifications more than their own trends predict.

## 2. Questions (fixed in a dated analysis plan before any computing)

- **Q1. Consistency.** Do the published ACF and campaign figures agree across sources, documents and dates, and does each source's internal arithmetic hold?
  - The cascade must not grow from step to step: screened ≥ presumptive ≥ tested ≥ diagnosed ≥ notified.
  - Percentages must equal their stated numerators over their stated denominators.
  - Totals must equal the sum of their parts.
- **Q2. Definitions.** Where figures disagree, is the disagreement explained by different definitions? Examples:
  - "screened" as population reached versus people symptom-screened;
  - "tested" as all tests or as people tested;
  - "cases" as diagnosed or as notified;
  - different reporting windows or cut-off dates;
  - phase 1 (347 districts) versus the expanded campaign.

  The reconciliation of the GHA 2023 and PGPH 2025 quality indicators is part of Q2.
- **Q3. Yield.** What do state-level ACF yields look like, where published by state? The measures are diagnosed per 100,000 screened, the number needed to screen, and the ACF share of notifications.
- **Q4. Impact (dose-response).** Did notifications rise more in states with a larger share of districts in the campaign?
  - **Primary contrast:** the state-wise change in notifications from January–October 2024 to January–October 2025, comparing the same windows at the same cut-off.
  - **Benchmark:** each state's own 2019–2024 annual trend.
  - **Exposure:** the share of the state's districts, or of its population, in phase 1 of the campaign.

## 3. What is known now (recon on 18 November 2026)

**Public sources identified.** Each needs downloading with the author's permission. Every one is an official government publication.
- India TB Reports, editions 2019–2024. The 2020, 2021, 2023 and 2024 editions are already held in the State TB Score project. The 2019 and 2022 editions have pages on CTD's site. The 2021 edition is a scan with no text layer, so its tables are unusable.
- Parliamentary answers (Lok Sabha and Rajya Sabha) carry state-wise TB notifications for January–October 2024 (also on data.gov.in) and January–October 2025 (e.g. eparlib AU802). Other answers give state-wise ACF tables (AU3772, Rajya Sabha PQ 263 of 6 February 2024).
- The CTD campaign document, TB-Mukt-Bharat-Abhiyan-Campaign-2026-v6.pdf on tbcindia.mohfw.gov.in, reports progress to 30 December 2025. The list of campaign districts is to be located, likely in CTD or Ministry documents or press releases.
- CTD's "Active Case Finding" web page, which may hold ACF tables.
- The two quality studies: GHA 2023 (doi 10.1080/16549716.2023.2256129) and PGPH 2025 (doi 10.1371/journal.pgph.0005103). The second was read directly; the first was seen only through summaries.

**Not available.**
- Monthly state-wise notifications. The public Ni-kshay report page fails to load and its download needs a CAPTCHA; Ni-kshay dashboards need an official login. The author may add monthly files later by downloading them personally (§8).
- District-level ACF or notification data in public form.

**Reuse from the State TB Score project** (public repo hssling/india-state-tb-score, v1.0.0 doi 10.5281/zenodo.24323627):
- canonical state names;
- PDF table extraction (rotation-aware, with checks against printed totals);
- the fetch script with SHA-256 manifest;
- the verification suite pattern (byte reproduction, plan order, logged deviations, manuscript number checks with a golden skeleton);
- the build pipeline for the docx manuscript.

## 4. Goals, non-goals, anti-goals

**Goals**
- A complete, sourced inventory of published ACF and campaign figures. Each entry records its value, definition, window, cut-off date and source page.
- A consistency audit (Q1) and a definitional reconciliation (Q2), with every discrepancy classified as: arithmetic error, definitional difference, window or cut-off difference, or unexplained.
- State-level yield where published (Q3), and a pre-specified dose-response estimate with uncertainty (Q4).
- Findings stated as programme actions: which figure to quote for what purpose; what to standardise in reporting (definitions, cut-off dates, publishing the cascade with denominators); and what the evidence says about the campaign's effect on notifications.
- Every number derived by code from extracted tables. Checks mutation-tested.

**Non-goals**
- Causal claims beyond what an ecological, state-level dose-response design can support. Q4 is reported as an association with stated assumptions, not as the campaign's causal effect.
- District-level analysis, because the data are not public.
- Cost-effectiveness.

**Anti-goals: a failure even if every number is right**
- Implying that figures were falsified. Discrepancies are classified with explicit evidence. "Unexplained" is a valid class, not an accusation.
- Discrediting ACF itself. The study is about measurement and evidence, not about whether screening is worthwhile.
- Attacking the authors of the quality studies. The reconciliation is about definitions.

## 5. Approaches considered

- **A1. Reconciliation audit only (Q1–Q3).** Fully feasible, but silent on impact.
- **A2. Audit plus a public-data dose-response (Q1–Q4). Chosen by the author on 18 November 2026.** Monthly interrupted time series, not possible with public data, is replaced by a same-window state comparison and a state-trend benchmark.
- **A3. Impact only.** Rejected: it drops the reconciliation, which holds the clearest findings.
- **The author's request for workarounds to obtain Ni-kshay data.** Legitimate routes were tried (the public report, dashboards, CTD's real-time page, data.gov.in). CAPTCHA and bot-protection circumvention were declined. Monthly data stays an optional extension, using files the author downloads personally.

## 6. The design

### 6.1 Data
- The fetch-and-verify pattern from the State TB Score project: a manifest with URL, date and SHA-256; source PDFs kept git-ignored; extracted CSVs carrying their source page.
- Parliamentary-answer tables are extracted with each answer's number, date, house and cut-off date. Ni-kshay counts accumulate as records are updated, so every count carries its cut-off date. Only counts with the same cut-off are compared.
- A figure inventory (data/figures_inventory.csv) holds one row per published figure:
  - quantity, value and unit;
  - definition as stated, verbatim;
  - window and cut-off;
  - geography;
  - source, page or paragraph, and the publication date.

  Press releases enter only where they are official (PIB or Ministry). News coverage is used only to locate official sources, never as a source itself.

### 6.2 Q1–Q2: consistency and reconciliation
- **Checks applied to every source:**
  - the cascade does not grow;
  - percentages recompute within the source's own rounding;
  - totals equal the sum of their parts;
  - a cumulative series does not fall over time.
- **Classification of each cross-source discrepancy,** using a pre-specified decision order: (1) arithmetic error within a source; (2) definitional difference (documented by quoting both definitions); (3) window or cut-off difference; (4) unexplained.
- **The quality-study reconciliation:** recompute both papers' indicators on common definitions where their published tables allow it, and report what remains different.

### 6.3 Q3: yield
- The indicators are diagnosed per 100,000 screened, the number needed to screen, and the ACF share of notifications. They are computed by state and year where a published table gives numerator and denominator, each with a 95% interval (binomial or Poisson).
- No imputation. Years or states without published data are listed.

### 6.4 Q4: dose-response
- **Outcome:** the state's log ratio of notifications, January–October 2025 over January–October 2024, both counted to the same cut-off.
- **Exposure:** the share of the state's districts in phase 1 of the campaign. The share of population is a sensitivity analysis.
- **Benchmark:** the state's expected change from its own 2019–2024 log-linear trend in annual notifications, taken from the India TB Reports. The main estimate is the excess change, observed minus expected, regressed on exposure.
- **Method:** weighted least squares across states, with weights fixed in the plan. The 95% interval comes from the model and is checked with a bootstrap over states. No P values. COVID years are handled as fixed in the plan, for example excluding 2020–2021 from the trend.
- **Sensitivity analyses** (pre-specified list): the unweighted fit; leave one state out; the trend from 2022–2024 only; excluding union territories; population share as the exposure.
- **Falsification check:** the same model fitted to January–October 2023 against 2024 (a pre-campaign placebo) should show no exposure gradient.
- **Limits stated up front:** ecological; few units; concurrent programme changes (for example ACF outside the campaign, X-ray roll-out); exposure measured at district-membership level.

### 6.5 Products
- **New folder `tb_acf_campaign/`, laid out like `tb_state_score/`:**
  - docs/ (design, dated plan, §Deviations);
  - src/;
  - verification/;
  - outputs/ (tracked);
  - data_raw/ (git-ignored);
  - manuscript/ (git-ignored until a decision).
- **Public repository** created at registration, before extraction.
- **Target journal:** to be decided by the author. Candidates must be hybrid or APC-free and suit programme readers: Indian Journal of Tuberculosis (hybrid), Indian Journal of Public Health, Indian Journal of Community Medicine, Public Health Action (verify its APC), IJTLD (hybrid). The manuscript must cite the State TB Score paper under review (IJMR_4457_2026) only if relevant, and must not overlap it.

## 7. Constraints
- Single author. Journals must be hybrid or APC-free.
- Every download needs the author's explicit permission, stating file, source and size.
- No CAPTCHA or bot-protection circumvention, and no logged-in data.
- The plan is dated and committed before any figure is extracted or compared; deviations are logged with dates.
- No drafting-history language in manuscript text. Python standard library for the analysis; pdfplumber for extraction only.

## 8. Optional extension (not required for the paper)
If the Ni-kshay public report works in the author's own browser, the author downloads monthly state-wise notification files personally, CAPTCHA included. Adding a monthly interrupted time series would then need a dated §13 deviation that specifies it before those files are opened.

## 9. Decisions after the builder check (18 November 2026; the analyst's calls, for the author to check)

1. **District exposure: a go/no-go gate, Task 0, before registration.**
   - Locate an official list of phase-1 campaign districts. Sources: CTD or Ministry documents, PIB releases, or state government orders.
   - The denominator is the number of districts in each state at December 2024, from the Local Government Directory (LGD).
   - If no official list exists but official counts of campaign districts by state do, those counts serve as the exposure.
   - If neither exists, Q4 is dropped, the paper is Q1–Q3, and the plan records this before registration.
   - Phase 1 (the 347 districts) is the exposure. The later expansion is not used.
2. **Comparability of the January–October windows, fixed in the plan.**
   - The two state tables qualify for Q4 only if all three hold:
     - (a) both report total (public plus private) notifications, as stated in the answer;
     - (b) both cover 1 January to 31 October;
     - (c) both "as on" dates fall within 60 days after 31 October of their year.
   - Bifurcated or merged units (for example Jammu and Kashmir and Ladakh; Dadra and Nagar Haveli and Daman and Diu) are combined to the coarser unit in both years.
   - If (a)–(c) fail, Q4 is reported descriptively only, without the regression, and the plan says so.
   - There is no power gate. Q4 is reported with its interval whatever its width, and the number of states and the spread of exposure (SD and range) are stated.
3. **Trend benchmark.**
   - Annual state notifications for each year come from the latest available edition reporting that year.
   - The trend uses 2019, 2022, 2023 and 2024. 2020 and 2021 are excluded (COVID). If 2019 is unavailable for a state, its trend uses 2022–2024.
   - The expected January–October log ratio equals the state's fitted annual log growth, which assumes unchanged seasonality between the two years. That assumption is stated as a limitation.
   - 2021 counts are not needed.
4. **Weights:** inverse variance of the observed log ratio under a Poisson model, w = 1/(1/a + 1/b), where a and b are the two window counts.
5. **Placebo.**
   - January–October 2023 against January–October 2024, if a 2023 window table at the same cut-off exists.
   - Otherwise annual 2023 against 2022, with excess change regressed on exposure.
   - The choice is recorded in the source-choice file before Q4 is computed.
6. **Inventory stopping rule.**
   - Search tbcindia.mohfw.gov.in, pib.gov.in, eparlib.sansad.in, rsdebate.nic.in, data.gov.in and ntep.in for "active case finding", "ACF" and "TB Mukt Bharat Abhiyaan".
   - Date window: 1 December 2022 to 18 November 2026.
   - Every located document is listed in data/search_log.csv, including those excluded and why. Reading and searching are free; each download is batched and approved by the author.
7. **GHA 2023.** Global Health Action is open access, so its full text is read online. If its tables are not accessible, the reconciliation is limited to what its abstract and text report, and the paper says so.
8. **Registration.**
   - A public GitHub repository, hssling/india-tb-acf-campaign, created by the analyst once the author approves this design. The plan's push timestamp is the registration.
   - Release and DOI come at submission, as before.
   - No OSF registration.
9. **Code reuse.** Code from tb_state_score (state names, extraction primitives, fetch, verification skeleton) is copied into the new repository with attribution, so that it is self-contained. It is not imported across repositories.

## 10. Left to the builder
- Extraction methods for parliamentary-answer PDFs.
- Code layout.
- Figure design.
- The order of extraction tasks.
- Exact column names.
