# Pre-registered analysis plan: India's active case-finding figures and the 100-day TB Mukt Bharat Abhiyaan

**Date of this plan:** 18 November 2026
**Author:** Siddalingaiah H S, MD, Professor, Department of Community Medicine, Shridevi Institute of Medical Sciences and Research Hospital, Tumkur, Karnataka, India. ORCID 0000-0002-4771-8285. Single author.
**Repository:** https://github.com/hssling/india-tb-acf-campaign
**Status:** registered before any figure was extracted from a source document and before any computation. The registration point (commit SHA and UTC time of the public push) is recorded in §13.
**Design:** `docs/superpowers/specs/2026-11-18-acf-campaign-design.md` (approved 18 November 2026). Where this plan and the design differ, this plan governs; the differences are listed in §1.3.
**Source search:** `docs/source_search.md` (the source-search note) and `data/search_log.csv`, both committed with this plan.

---

## 1. Background and scope

### 1.1 Background

Active case finding (ACF) is a pillar of India's National TB Elimination Programme (NTEP). The Central TB Division (CTD) of the Ministry of Health and Family Welfare ran a 100-day intensified campaign, the TB Mukt Bharat Abhiyaan, from 7 December 2024 in 347 districts (phase 1), and later extended it. Official statements give national totals of people screened and of TB cases found that differ between documents, and published estimates of ACF quality differ between studies. No peer-reviewed evaluation of the campaign was found by a novelty check on 18 November 2026.

### 1.2 Scope

The study uses published, aggregate, official data only. The unit of analysis for the state-level questions (Q3, Q4) is the State or Union Territory (UT), after the unit coarsening of §9.4. District-level analysis, cost-effectiveness, and causal claims beyond an ecological, state-level association are out of scope. The study concerns measurement and evidence. It does not judge whether screening is worthwhile, and it does not imply that any figure was falsified.

### 1.3 Refinements of the design fixed by this plan

These refinements were made before any figure was extracted. Each is stated where it applies.

1. **The primary Q4 contrast** is the full year 2025 against the full year 2024, both from one parliamentary answer with one source and one as-on date (Rajya Sabha Question 1216). It replaces the January–October contrast of design §2 and §6.4. The author decided this on 18 November 2026, before registration (§9.5.1).
   - For this contrast, condition (c) of design §9.2 becomes "one as-on date for both years, within 60 days after the end of the later window".
   - A pre-specified guard tests whether its counts are total notifications. If the guard fails, the January–October contrast becomes primary (§9.5.2). A failure of Question 1216's own extraction checks counts as a failed guard.
2. **The January–October contrast** becomes sensitivity analysis S8 (§9.5.3, §10.5).
   - Its 2024 table is Lok Sabha Starred Question 261, not Rajya Sabha Unstarred Question 2511 named in the source-search note, because the answer text of Question 2511 shows a different window.
   - Its comparability condition (a) of design §9.2 is fixed as "same quantity in the same words from the same source". Neither of its answers states its public and private coverage, and this is a stated limitation.
3. **The trend sources** of design §9.3 are fixed (§9.6). The points for 2019 and 2022 come from the India TB Report, and those for 2023 and 2024 from Rajya Sabha Question 1216, which shares the outcome's cut-off. The fallback sources are named.
4. **The exposure table** must pass pre-specified extraction checks. A State with more campaign districts than LGD districts is flagged and capped rather than rejected (§9.2, E5). The district denominator is reconstructed from the Local Government Directory (LGD) by a fixed rule (§9.2, §9.3).
5. **Sensitivity analyses are added:** the January–October contrast with its reporting-lag analyses (§10.5, S8), and two for the capped States: S6a excludes the States flagged under E5, and S6b excludes every State whose exposure share is 1 (§10.5).
6. **The population-share sensitivity analysis** of design §6.4 can be run only if a named list of campaign districts is obtained (§10.5, S7).
7. **The placebo** is 2023 (from the 2023 trend source) against 2022 (India TB Report). Its expected change uses only the trend points before the placebo window (§10.6).
8. **The rules for comparing figures in Q2** (comparison groups, keyword rules for definition classes, qualifiers such as "more than", and the reporting unit) are fixed in advance (§5, §7).

## 2. Questions

- **Q1. Consistency.** Do the published ACF and campaign figures agree across sources, documents and dates, and does each source's internal arithmetic hold? The checks are fixed in §6.
- **Q2. Definitions.** Where figures disagree, is the disagreement explained by an arithmetic error, a difference in definition, or a difference in window or cut-off date? The decision order is fixed in §7. Q2 includes the reconciliation of the ACF quality indicators of two published studies (Global Health Action 2023, doi 10.1080/16549716.2023.2256129; PLOS Global Public Health 2025, doi 10.1371/journal.pgph.0005103).
- **Q3. Yield.** Where a published table gives the numerator and denominator by State, what are the State-level ACF yields? The indicators are TB diagnosed per 100,000 people screened, the number needed to screen, and the ACF share of notifications (§8).
- **Q4. Dose-response.** Did TB notifications rise more, relative to each State's own trend, in States with a larger share of their districts in phase 1 of the campaign? The primary contrast is the full year 2025 against the full year 2024; the January–October contrast is a sensitivity analysis (§9, §10). Q4 is an ecological association, not an estimate of the campaign's causal effect.

## 3. Data sources

### 3.1 Files downloaded before this plan

The following files were downloaded on 18 November 2026 into `data_raw/`, which is excluded from the repository. They are not redistributed. A fetch script will download them from their official locations and verify each digest. Files the author downloaded personally through a CAPTCHA (the LGD reports, §3.1.3) are verified against the digests below but are not re-downloaded by the script.

#### 3.1.1 Programme, campaign and press documents (`data_raw/official/`)

| File | Content | Bytes | SHA-256 | URL |
|---|---|---|---|---|
| `100-days-campaign-Report-1-Complete-on-5-12-2024-New.pdf` | CTD, *100 Days Campaign* (48 pages; file name dated 5 December 2024). Exposure table (§9.2) | 15,715,802 | `e353293ae24c376200cf6fb8921f68b0acdabdae557b2c0bad36cf3e207e5bbb` | https://tbcindia.mohfw.gov.in/wp-content/uploads/2025/01/100-days-campaign-Report-1-Complete-on-5-12-2024-New.pdf |
| `TB-Mukt-Bharat-Abhiyan-Campaign-2026-v6.pdf` | CTD, TB Mukt Bharat Abhiyaan campaign document, version 6 (2026) | 1,036,945 | `2d107b1f8175ba3fdadd4e73f8860355cdb7496a26f727c87ffdd46d4a99f819` | https://tbcindia.mohfw.gov.in/wp-content/uploads/2026/03/TB-Mukt-Bharat-Abhiyan-Campaign-2026-v6.pdf |
| `Guidance-Document-on-TB-Mukt-Bharat-Abhiyan_0.pdf` | CTD, Guidance Document on TB Mukt Bharat Abhiyan (2025) | 3,584,607 | `f331a783dbfa792a078c45601d5e2ad92a9c6d34c8a0a9bd72f02b5856fb8838` | https://tbcindia.mohfw.gov.in/wp-content/uploads/2025/09/Guidance-Document-on-TB-Mukt-Bharat-Abhiyan_0.pdf |
| `doc2024127466601.pdf` | Press Information Bureau (PIB), *Synopsis of 100-Day Campaign* (7 December 2024) | 1,727,083 | `8de4fa8a3ee50973a4090c1e18c9ea28461e18e7b213825a698b0416726548ee` | https://static.pib.gov.in/WriteReadData/specificdocs/documents/2024/dec/doc2024127466601.pdf |
| `doc2024126465901.pdf` | PIB backgrounder, *India's 100-Day TB Elimination Campaign* (6 December 2024) | 806,043 | `bdc5b490f6296ec2b15eab05cfa9caa71254ec14f0aa566c0781a40ef1099537` | https://static.pib.gov.in/WriteReadData/specificdocs/documents/2024/dec/doc2024126465901.pdf |
| `doc2026324833001.pdf` | PIB press note, *India Speeding Towards TB Elimination* (24 March 2026) | 624,028 | `48f8d2ba95cba962e237c2fc2b9736fcc253573f3319fa48c917cf750e153efe` | https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/mar/doc2026324833001.pdf |
| `India-TB-Report-2019.pdf` | India TB Report 2019 (calendar-2018 data); ACF inventory only | 16,920,376 | `87e546751372ba157cb9eba1620173d54aad0fb99abc1b99f4302e9a2005c03b` | https://tbcindia.mohfw.gov.in/wp-content/uploads/2023/05/India-TB-Report-2019.pdf |
| `TBAnnaulReport2022.pdf` | India TB Report 2022 (calendar-2021 data); ACF inventory only | 50,821,996 | `dc9ff4a88a28eb87232770d0956fe92b2b266b15e5794f879a7335b7c083418b` | https://tbcindia.mohfw.gov.in/wp-content/uploads/2023/05/TBAnnaulReport2022.pdf |
| `TB_Elimination_Campaign.pdf` | Ministry of Health letter L-11012/2/2019-DCC with attachments (Kerala Medical Council copy) | 2,692,311 | `786ed1a5e4fde7cb79245df5a2f2f75ef8f8658b112896a755c627adb9133a6f` | https://medicalcouncil.kerala.gov.in/wp-content/uploads/2025/01/TB_Elimination_Campaign.pdf |

#### 3.1.2 Parliamentary answers (`data_raw/pq/`)

| File | Answer | Bytes | SHA-256 | Use |
|---|---|---|---|---|
| `AS261_lP7nYE.pdf` | Lok Sabha, Starred Question 261, "Eradication of TB by 2025", answered 13 December 2024. https://eparlib.sansad.in/bitstream/123456789/2985936/1/AS261_lP7nYE.pdf | 214,238 | `245a778539f40e7682aa69ff0e7e1d8c087d89243a6206931caddcf33f5c9fa4` | S8: January–October 2024 (§9.5.3); 2023 column for S8(b) (§10.5) |
| `AU1093_dH065I.pdf` | Rajya Sabha, Unstarred Question 1093, answered 9 December 2025 (Rajya Sabha question archive, sansad.in) | 117,980 | `349b4b48b1ce40247db84ea24cd989b35bd45d949487c87d08e81f797b531438` | S8: January–October 2025 (§9.5.3) |
| `AU2511_t81pFf.pdf` | Rajya Sabha, Unstarred Question 2511, answered 17 December 2024 (Rajya Sabha question archive, sansad.in) | 130,804 | `7c600909db309d072e28016f0232a6e4dd3ce07a31da7291cd5987443bae8d24` | Q1–Q2 only; **not used for Q4** (§9.5.5) |
| `AU1216_WFw8li.pdf` | Rajya Sabha, Unstarred Question 1216, answered 10 February 2026 (Rajya Sabha question archive, sansad.in) | 218,634 | `099d2f12e0ba26740dd37cede0baeef6c7edfde62ed28afcaf67529beb419780` | Q4 primary: full-year 2024 and 2025 (§9.5.1); trend points 2023 and 2024 (§9.6); placebo (§10.6) |
| `AU3467_mVGJLD.pdf` | Rajya Sabha, Unstarred Question 3467, answered 1 April 2025 (Rajya Sabha question archive, sansad.in) | 161,654 | `1c33f53107151fcc705b0a69c82c91e1a3bd06c44bf935d539e8ec0c3f53a925` | Guard (§9.5.2); fallback trend point 2024 (§9.6) |
| `AU3001_ZXEQ3g.pdf` | Rajya Sabha, Unstarred Question 3001 (drug-resistant TB) | 134,970 | `9f5dbd8be0fdb8914bc2adef8655c78471c2b4674895b85b184b161dd8ba332a` | Not used |
| `AU3477_SSspdQ.pdf` | Rajya Sabha, Unstarred Question 3477 (campaign activities), answered 1 April 2025 | 99,336 | `628c03cbb3951f20c97bb422849e70a34962b303f7c1977d4e81e1eb4cc1613a` | Q1–Q2: figure inventory (§5.3); not used for Q4 |

The download URLs of the Rajya Sabha answers are recorded in the source manifest when the fetch script is written.

#### 3.1.3 Local Government Directory (`data_raw/lgd/`)

Downloaded by the author on 18 November 2026 from https://lgdirectory.gov.in/downloadDirectory.do, which requires a CAPTCHA.

| File | Content | Bytes | SHA-256 |
|---|---|---|---|
| `All_Districtof_India_2026-11-18_21-18-59.xlsx` | "All Districts of India", the current list on 18 November 2026 | 35,051 | `19b0ac791a0cf763a4dd6d414be64c2ae3bacb8ba36fc12d9d7d8fca6b0b3ab6` |
| `alldistrictbyDate2026_11_18_21_20_13_069.xls` | District modifications, headed "Modification done between (From 07/12/2024 - TO 18/11/2026)" (SpreadsheetML) | 91,018 | `e00d438ca2d29cc183afcdd846164a443901cc27528f5e45e125686a3f8fdfe1` |

### 3.2 India TB Report editions used for annual State notifications

The author's earlier study (https://github.com/hssling/india-state-tb-score) holds these editions. This project re-fetches them from the same official URLs and verifies them against the same digests. The digests of the copies held were recomputed on 18 November 2026 and match.

| Edition (data year) | SHA-256 | URL | Use |
|---|---|---|---|
| 2020 (2019) | `63b9408015dae510858e0eef2711e809d398bfe3149dd21c94390b258c007e7e` | https://tbcindia.mohfw.gov.in/wp-content/uploads/2023/05/India-TB-Report-2020.pdf | Trend point 2019; placebo |
| 2023 (2022) | `0817ac3a1e7a03273438073d4e685f88aa93507ad115ec5c6588edfddc8f0b7b` | https://tbcindia.mohfw.gov.in/wp-content/uploads/2023/05/5646719104TB_AR_2023_04-04-2023_LRP_final.pdf | Trend point 2022; placebo |
| 2024 (2023) | `e37f9f406153b5e9a19726538c3f4d09dc4c470281c34fe511adaa56a0e22765` | https://tbcindia.mohfw.gov.in/wp-content/uploads/2024/10/TB-Report_for-Web_08_10-2024-1.pdf | Fallback trend point 2023 and placebo (§9.6, §10.6); S8(b); Q2 cross-check of Question 1216 (§7.4) |

The 2021 edition (calendar-2020 data) is a scan with no text layer and is not used; 2020 is in any case excluded from the trend (§9.6). No edition giving calendar-2024 State notifications was found on CTD's website on 18 November 2026.

### 3.3 Sources still to be obtained

Each needs the author's permission before download (file, source and size). The role of each is fixed in this plan. A source that cannot be obtained is reported as unavailable, and the analysis that needs it is reported as not run.

- **Parliamentary answer document:** Rajya Sabha Unstarred Question 1900 (16 December 2025), State/UT-wise TB cases "under TB Mukt Bharat Abhiyan", 2024 and 2025. Its role is fixed in §9.5.5.
- **Open Government Data (OGD) mirrors** of parliamentary tables, listed in `data/search_log.csv`.
- **Quality studies:** the Global Health Action 2023 supplement and its Figshare dataset (doi 10.6084/m9.figshare.23723748); the PLOS Global Public Health 2025 supporting files and Figshare collection (doi 10.6084/m9.figshare.c.7048385.v1).
- **The remaining documents** marked include = yes in `data/search_log.csv`. HTML pages (PIB releases, the two studies' full texts) are read online and cited with their URL and access date.

### 3.4 Rule for parliamentary tables

A parliamentary table enters Q3 or Q4 only from the answer document itself. OGD mirrors are used to locate answers and as cross-checks, because one mirror is already known to label a window differently from its answer (§7.4). A difference between an answer and its mirror is recorded in the inventory and classified under Q2.

## 4. Data seen before this plan

Before this plan was written, the following had been seen. Nothing else had been read for numeric content, and nothing has been computed.

1. **The source search.** Titles, URLs, dates, document types, table headings, stated windows and cut-off dates of the documents listed in `data/search_log.csv`, as recorded in the source-search note. No figure value was recorded.
2. **The CTD exposure table.** During the search, the *100 Days Campaign* document was displayed once in an online document viewer. The heading of the selection-criteria table (PDF page 6) and the heading and State/UT row labels of the per-State table (PDF page 7) were read, and the rows were counted from the State names.
   - No State-level campaign-district count was recorded, transcribed or used. The per-State table was displayed once, during the source search, and its values may have been visible.
   - Both tables will be read afresh from the downloaded, hashed copy (§9.2).
3. **The parliamentary answers.** The wording of seven answers was read with all counts masked: headings, column labels, footnotes, source lines, and the dates in the answer text.
   - Lok Sabha Starred Question 261, and Rajya Sabha Unstarred Questions 1093 and 2511.
   - Rajya Sabha Unstarred Questions 1216, 3467, 3001 and 3477, read for wording only. In Question 1216, the day of the as-on date was masked as well.
4. **The LGD files.** Only their headers (sheet name and report heading) were read. No district was counted.
5. **National figures quoted in the design.** The design (§1) quotes, from public summaries:
   - national campaign totals (for example 9.02 crore screened and 3.01 lakh cases);
   - national ACF shares of notifications (2.5% for 2022; 1.6% for 2023);
   - the headline indicators of the two quality studies;
   - the phase-1 count of 347 districts and the count of 33 States/UTs.

   These national figures motivated Q1 and Q2. They enter the inventory only from their source documents.
6. **The author's earlier study.** That study extracted State-level totals of TB patients notified in 2022 and 2023 from the 2023 and 2024 editions of the India TB Report (annexure 1.2 in each edition), and those values are public in its repository.
   - They were not consulted in preparing this plan.
   - The 2022 values are, however, an input to trend point 2022 and to the placebo (§9.6, §10.6). The 2023 values enter only as the fallback trend point and placebo value, the S8(b) proxy and a Q2 cross-check.
   - The annexure page locations given in §9.6 for the 2023 and 2024 editions were taken from that study's source-choice record, without its State values. The rows read for this purpose also show that study's comparison of two national notification-target figures; no State value and no notification count was read.
   - The exposure was not recorded, and nothing involving it was computed. No quantity that involves the exposure (the Q4 slope or the placebo slope) could therefore have been computed or anticipated.

In summary:

- No State-level campaign-district count was recorded, transcribed or used. The per-State table was displayed once, during the source search, and its values may have been visible (item 2).
- No State-level count from any parliamentary answer (full-year or January–October), and no State-level ACF figure, has been seen.

## 5. Figure inventory

### 5.1 Scope of the inventory

The inventory, `data/figures_inventory.csv`, holds one row for each published figure of the quantities below that appears in a document marked include = yes in `data/search_log.csv`.

- Every occurrence is entered, including figures repeated across documents.
- A figure printed more than once in the same document is entered once for each distinct table or paragraph.
- Figures are entered whether or not they agree with others; no figure is left out because it looks wrong.

Quantities (column `quantity`) come from a fixed vocabulary. The quantity records the step of the cascade; the sub-type within a step (for example, people tested or tests done) is the definition class of §7.2, so that figures differing only in definition are compared in Q2.

- `districts_selected`: campaign districts, national or by State;
- `population_targeted`: people identified as the campaign's target or vulnerable population;
- `screened`: people screened or reached;
- `presumptive`: people identified with presumptive TB;
- `tested`: people tested or tests performed (including chest X-ray and molecular tests);
- `tb_cases`: TB cases diagnosed, notified or reported;
- `acf_share_notifications`: the ACF share of notifications;
- `nns`: the number needed to screen;
- `yield`: TB diagnosed per stated number screened;
- `other:<name>`: any other ACF or campaign figure, entered for completeness but not used by the checks of §6 or the comparisons of §7.

Press releases enter only where they are official (PIB or a Ministry). News coverage is used only to locate official sources and never as a source.

### 5.2 Schema

| Column | Content |
|---|---|
| `fig_id` | Stable identifier |
| `quantity` | From the vocabulary of §5.1 |
| `value` | As a number. Indian magnitude words are converted (1 lakh = 100,000; 1 crore = 10,000,000) |
| `value_printed` | The figure exactly as printed, for example "9.02 crore" |
| `qualifier` | exact, at_least, about or at_most, by the rule of §6.1 |
| `unit` | persons, tests, cases, districts, percent, or ratio |
| `definition_verbatim` | The source's own words for the quantity, quoted |
| `context_verbatim` | The sentence, table heading or column heading in which the figure appears, quoted |
| `definition_class` | Assigned from `definition_verbatim` by the keyword rule of §7.2; "unspecified" where no rule matches |
| `scope` | Assigned from `context_verbatim` by the keyword rule of §7.2: phase 1, expanded campaign, programme-wide, or unspecified |
| `series_type` | cumulative (counted from a stated start date) or period |
| `window_label` | Assigned from `context_verbatim` by the rule of §7.1 |
| `window_start`, `window_end` | As stated; blank (unstated) if not stated |
| `as_on` | The stated "as on" date; blank if not stated |
| `as_on_basis` | stated; bounded (no date stated, so the answer or publication date is the latest possible); or window_end (the stated end of the data is taken as the cut-off) |
| `geography` | India, or a canonical State/UT name |
| `source_file`, `source_url` | The document |
| `page_or_para` | PDF page and table, or paragraph |
| `table_id` | The table heading or number, if any |
| `pub_date` | The document's date |
| `note` | Flags set by the rules of this plan (for example, a mixed-phase scope, §7.2), and any extraction remark |

Blanks stay blank. No field is filled by inference from another document.

### 5.3 Stopping rule

The search of design §9.6 was run on 18 November 2026 and is closed:

- sites: tbcindia.mohfw.gov.in, pib.gov.in, eparlib.sansad.in, rsdebate.nic.in, data.gov.in and ntep.in;
- terms: "active case finding", "ACF" and "TB Mukt Bharat Abhiyaan" (with the variant "Abhiyan");
- date window: 1 December 2022 to 18 November 2026;
- record: `data/search_log.csv`, 149 rows (56 include = yes, 1 provisional, 92 include = no, each with a reason).

The inventory is built from three sets of documents:

- the documents marked include = yes;
- documents that those documents cite by name as the source of a figure;
- Rajya Sabha Unstarred Question 3477 (1 April 2025, campaign activities; §3.1.2). It was obtained with the 2024 notification answers before registration, and it may contain national campaign figures. It is read at extraction like any other included document.

A document found after registration is added only as a dated deviation (§13).

**The provisional row** (a PIB release listed by CTD among campaign releases, PRID 2115334, whose page did not render) is resolved at extraction, before any figure is taken from it. It is included only if, on reading, it is an official PIB release dated within the search window that reports a figure of a quantity in §5.1. Otherwise it is excluded. Either way, the decision and its reason are recorded in the log. If the page still cannot be read, it is excluded with that reason.

### 5.4 Source-choice freeze

Before any Q1–Q4 computation, every source choice is recorded in `data/source_choices.csv` and committed. This includes:

- the exposure table's location, the result of each check in §9.2, and every label resolved under its label rule;
- the LGD date field used and the reconstruction log (§9.3);
- the unit coarsening (§9.4);
- the outcome tables, the comparability judgement at extraction, and the result of the guard (the State ratios, their medians and the decision) (§9.5);
- the source of each trend point, including any fallback used (§9.6);
- whether a named list of campaign districts was found (§9.2);
- whether Rajya Sabha Question 1900 was obtained (§9.5);
- each table used for Q3, and the table chosen for any single summary value (§8.4).

Any change to a recorded choice after that commit is a dated deviation (§13).

## 6. Q1: consistency checks

Every check is applied to every source in which its inputs appear. Its result is written to `outputs/q1_checks.csv`, with the columns check, inputs, expected, observed, pass and note. A failed check is reported with its source and is never corrected silently.

### 6.1 Rounding, qualifiers and the interval of a figure

Every figure is turned into an interval [lo, hi] before any check or comparison.

- **Half-unit.** h is half a unit in the last printed digit. A figure printed as an integer count has h = 0. "9.02 crore" has h = 0.005 crore, and "3.7%" has h = 0.05%.
- **Qualifier.** It is read from the one to three words directly before the figure, and from two symbols. Words match case-insensitively as whole words (§7.2). The figure is the number as printed, with its magnitude word if any ("25 crore").
  - **"+"** counts only when it follows the figure immediately, with no space, and is not followed by a digit (after any spaces). Regex: `\d[\d,.]*(?: ?(?:lakhs?|crores?))?\+(?!\s*\d)`. So "25 crore+" and "25+ crore" qualify, and "3+2", "3+ 2" and "3 + 2" do not.
  - **"~"** counts only when it precedes the figure immediately, with or without one space. Regex: `~ ?\d`.

  The first matching rule wins:
  - **at_least:** "more than", "over", "above", "exceeding", "at least", or "+" as above;
  - **at_most:** "up to", "less than", "under", "below", "at most";
  - **about:** "nearly", "around", "approximately", "about", "almost", "close to", or "~" as above;
  - **exact:** no qualifier word.
- **Interval.**
  - exact: [v − h, v + h];
  - about: [v − h, v + h], with h half a unit of the last stated digit (so "nearly 9 crore" is [8.5, 9.5] crore);
  - at_least: [v, ∞);
  - at_most: [0, v].

### 6.2 The checks

Checks 1–3 are within-source checks. Check 4 runs across documents.

1. **The cascade does not grow.** Within one source, for figures with identical `window_start`, `window_end`, `as_on` and `window_label` (a blank matching a blank) and the same geography and scope, the order is: screened ≥ presumptive ≥ tested ≥ TB cases diagnosed ≥ TB cases notified.
   - The check is applied to every pair of steps present, adjacent or not.
   - A `tested` figure enters only if its definition class is people tested or unspecified (§7.2). Tests done are not used, because one person may have several tests. A failure involving an unspecified class is noted as such.
   - A `tb_cases` figure of unspecified class is compared only with the steps before tested and with tested.
   - The check fails if the upper bound of the earlier step is below the lower bound of the later step.
2. **Percentages recompute.** A stated percentage p with numerator n and denominator d, all from the same source, passes if the interval of p overlaps [100 n_lo / d_hi, 100 n_hi / d_lo].
   - Example: 37 of 1,000 stated as 3.7% passes; stated as 4.0% it fails.
3. **Totals equal the sum of their parts.** The check passes if [Σ lo − 1, Σ hi + 1] over the parts overlaps the interval of the printed total. For exact counts this is |sum of parts − printed total| ≤ 1.
4. **A cumulative series never decreases.** Figures of the same quantity, definition class, scope and geography, counted from the same start date and with a non-blank `as_on`, are ordered by `as_on` across all documents.
   - The check fails if the upper bound of a later figure is below the lower bound of an earlier one.
   - A failure is not an arithmetic error within a source. It is passed to Q2 and enters the decision order at class 3 (§7.3).

## 7. Q2: discrepancies and definitions

### 7.1 Comparison groups and what counts as a discrepancy

**Stated window.** A figure's window is stated if `window_start` is non-blank and at least one of `window_end` and `as_on` is non-blank. Its span is [window_start, the later of window_end and as_on]. Otherwise its window is unstated. A blank field is never filled from another document.

**Window label.** `window_label` is assigned from `context_verbatim`, case-insensitive, by the first matching rule:

- "100 day", "100-day" or "100 days" → `100-day campaign`;
- a campaign name ("Abhiyan", "Abhiyaan" or "campaign") with "since" or "from", and no end date → `campaign to date`;
- otherwise, the period words as printed, lower-cased, with hyphens read as spaces and runs of spaces collapsed; blank if the context names no period.

**Comparison group.** Two figures are in the same group if all of these hold:

- they have the same quantity (§5.1, excluding `other:`);
- they have the same geography;
- they have the same scope (§7.2), with "unspecified" counting as a scope of its own;
- their windows overlap (both stated, and their spans intersect), or their window labels are identical and non-blank.

Figures of the same quantity and geography that differ only in scope are not compared. They are listed in a separate table as figures of different scope.

**Discrepancy.** Within a group, two figures form a discrepancy if their intervals (§6.1) do not overlap. Figures from a parliamentary answer and its OGD mirror (§3.4) are always compared, and a difference in value, window or label between them is a discrepancy.

**Reporting unit.**

- An entry is a distinct (document, value) pair. A value printed more than once in the same document is one entry.
- `outputs/q2_discrepancies.csv` has one row per unordered pair of entries within a group. Each row records whether the two agree and, if they do not, the class of §7.3 with its evidence.
- Group summaries are given over distinct values:
  - the number of distinct values;
  - their range;
  - the number of pairs of distinct values in each class.

  A pair of distinct values takes the lowest-numbered class among its entry pairs, and the other classes are noted. Repeated identical occurrences do not inflate any count.

### 7.2 Definition classes and scope

Classes are assigned by keyword rules, case-insensitive, applied in the order given; the first match wins, and "unspecified" is the default. Definition classes are read from `definition_verbatim`, and scope from `context_verbatim`.

Keywords match whole words (regex `\b…\b`), except the stems notif, diagnos, detect, symptom and radiograph, which match as word prefixes. A hyphen inside a keyword matches only a hyphen. Under this rule, "phase i" and "phase-i" do not match "phase ii" or "phase-ii", and "number of test" does not match "number of tested" or "number of tests". Plural forms are therefore listed where they are needed.

- **`screened`:**
  1. "x-ray", "x ray", "cxr" or "radiograph" → screened by chest X-ray;
  2. "symptom" → symptom-screened;
  3. "reached", "covered", "visited" or "contacted" → population reached;
  4. otherwise → unspecified.
- **`tested`:**
  1. "tests", "testing done", "investigations" or "number of test" → tests done. "investigations" counts only when none of "person", "persons", "patient", "patients", "individual", "individuals", "contact" or "contacts" appears in the same definition text;
  2. "tested" together with "person", "persons", "people", "individual", "individuals", "patient", "patients" or "presumptive" → people tested;
  3. otherwise → unspecified.
- **`tb_cases`:**
  1. "notif" → notified;
  2. "diagnos" or "detect" → diagnosed;
  3. otherwise (including "reported" alone) → unspecified.
- **Scope:**
  1. "100 day", "100-day", "100 days", "347" (as a number of districts), "phase 1", "phase i" or "phase-i" → phase 1. "347" matches only when it is not part of a longer number (digits joined by a comma or full stop) or a word. Regex: `(?<![\w,.])347(?![\d,.]*\d)`. It matches "347 districts" and "347." at the end of a sentence, but not "1,347", "2.347", "3470" or "347,000";
  2. "expanded", "extended", "expansion", "all districts", "phase 2", "phase ii", "phase-ii" or "second phase" → expanded campaign;
  3. "Abhiyan", "Abhiyaan", "campaign" or "campaigns" → unspecified;
  4. "active case finding" or "ACF" without any word of rules 1–3 → programme-wide;
  5. otherwise → unspecified.

  A figure whose text contains both a phase 1 and a phase 2 keyword (for example "Phase I/II" or "phase 1 and 2") takes the first class by rule order, and is flagged in its `note`. A combined phase also counts as both. It is detected by the regex `\bphase[\s-]*(?:i|1)\s*(?:/|&|-|and)\s*(?:ii|2)\b`, which matches "Phase I/II", "phase 1 and 2", "Phase-I & II" and "phase 1-2", but not "phase 12".

Other quantities have no definition classes. Each assignment is recorded with the keyword that matched.

### 7.3 Decision order

Each discrepancy is given the first class that applies, and the evidence for it is recorded in `outputs/q2_discrepancies.csv`:

1. **Arithmetic error within a source.** One of the figures fails a within-source check (§6.2, checks 1–3) that involves it. The failing check is cited. A failure of check 4 is never placed in this class.
2. **Definitional difference.** Both definition classes are stated (not unspecified) and differ. Both definitions are quoted.
3. **Window or cut-off difference.** Both windows are stated (§7.1), and they differ in start, end or cut-off. The row records whether the direction of the difference is consistent with the windows:
   - **3a, consistent:** for a cumulative series from the same start, or for nested windows, the later cut-off or the longer window gives the larger value; or the windows are neither nested nor from the same start, so no direction is implied;
   - **3b, inconsistent:** the later cut-off or longer window gives the smaller value. For a cumulative series this is a failure of check 4. It is reported as a window difference that does not explain the direction of the difference.

   Later or longer is judged on the span (§7.1); if the spans are equal, the row is 3a.

   A failure of check 4 enters here directly, without passing through classes 1 and 2.
4. **Unexplained.** None of the above applies. This includes every pair in which either window is unstated: such a pair is never placed in class 3. A failure of check 4 involving an unstated window is placed here.

"Unexplained" is a valid result. It records that the published documents do not explain a difference; it is not a finding of error or misconduct. Where more than one class applies, the first is assigned and the others are noted.

### 7.4 Pre-identified discrepancies

These are entered and classified under §7.3 like any other:

- **Rajya Sabha Question 2511.** The answer's table is headed "State/UT wise TB cases Notification and Death^ reported in 2024*", with the footnote "*As on 19th Nov 2024". Its window is therefore the year to date. Its OGD mirror labels the field "January to October".
- **Rajya Sabha Question 1900,** if obtained (§9.5): its January–October 2025 column against Question 1093, State by State.
- **The 2023 State counts** of Lok Sabha Question 261 against the India TB Report 2024, State by State.
- **Question 1216 against Question 3467**, for 2023 and 2024: every State whose ratio lies outside 0.95 to 1.05 (§9.5.2).
- **The 2023 State counts** of Question 1216 against the India TB Report 2024, State by State.

### 7.5 Reconciliation of the two quality studies

- **Studies.** Shewade HD et al., *Global Health Action* 2023 (national aggregates; PMC10515680), and Shewade HD et al., *PLOS Global Public Health* 2025 (field cohort; PMC12574901).
- **Common indicators.** Each is computed only where a study's published tables give its numerator and denominator:
  - C1, diagnosed among people tested;
  - C2, tested among people screened;
  - C3, tested among people with presumptive TB;
  - C4, the number needed to screen (people screened per person diagnosed).
- **Data.** The published tables are used first. The Figshare data are used only where a table gives a percentage without its counts, and only with the author's permission to download.
- **Output.** For each indicator and study:
  - the value as published;
  - the value recomputed on the common definition, with its Wilson interval (§8.2);
  - the stated denominator.

  Indicators that a study's tables cannot give are listed as not recomputable. What remains different after recomputation is reported as a difference in setting and denominator, not as an error by either study.

## 8. Q3: yield

### 8.1 Indicators

Each indicator is computed by State and year only where a published table gives both its numerator and its denominator:

- **Yield:** 100,000 × diagnosed ÷ screened. Where the table gives notified rather than diagnosed, the indicator is named accordingly.
- **Number needed to screen (NNS):** screened ÷ diagnosed.
- **ACF share of notifications:** TB patients found through ACF (diagnosed or notified, as the table states) ÷ all TB patients notified, for the same State and period.

### 8.2 Intervals

- **Proportions** use the Wilson score interval, with z = `statistics.NormalDist().inv_cdf(0.975)`. For x of n, with p̂ = x/n:
  - the centre is (p̂ + z²/2n) / (1 + z²/n);
  - the half-width is z √(p̂(1 − p̂)/n + z²/4n²) / (1 + z²/n).
- **Yield.** The interval is the Wilson interval of diagnosed ÷ screened, multiplied by 100,000.
- **NNS.** The interval is the reciprocal of the Wilson bounds of diagnosed ÷ screened: (1/upper, 1/lower).
- **Zero diagnosed.** The yield is 0, with its Wilson interval. The NNS is not computable, and its upper bound is reported as unbounded.

### 8.3 Missing data

There is no imputation. States and years without a published numerator and denominator are listed in `outputs/q3_yield.csv` as not available, with the reason.

### 8.4 Several tables for the same State and year

Where more than one published table gives an indicator's numerator and denominator for the same State and year, the indicator is computed from each table, and every result is reported with its source.

Where a single value is needed (a summary table or figure), the table is chosen by this precedence:

1. the India TB Report edition that reports that year;
2. a later India TB Report edition;
3. a CTD campaign or guidance document;
4. a parliamentary answer document, the latest answer first;
5. a PIB release, the latest first.

Ties within a level go to the later publication. The choice is recorded in `data/source_choices.csv` (§5.4).

## 9. Q4: data

### 9.1 Gate outcome

The source search found an official per-State count of phase-1 campaign districts, but no named list (source-search note, §1). The outcome is **GO with counts**: the exposure is each State's count of campaign districts over its district count, subject to the checks of §9.2. Phase 1 (347 districts) is the exposure; the later expansion is not used.

### 9.2 Exposure table and its checks

- **Source.** CTD, *100 Days Campaign*, PDF page 7 (printed page 5), under "Geographical prioritization". The table is headed "State | Total District". It is set in two column blocks, with 33 State/UT rows and a TOTAL row.
- **Reading.** The table is read from the downloaded copy whose SHA-256 is given in §3.1.1, not from any online viewer.
- **Checks.** All are applied at extraction:
  - **E1.** The TOTAL row equals 347.
  - **E2.** The State/UT rows sum exactly to the TOTAL row.
  - **E3.** There are 33 State/UT rows, each mapped to a canonical name by the label rule below.
  - **E4.** The column is not a count of all districts: after unit coarsening (§9.4), at least 5 States have a campaign count below their LGD count at the reference date (§9.3).
  - **E5.** In each State, after unit coarsening (§9.4), the campaign count is compared with the LGD count. A State whose campaign count exceeds its LGD count is **flagged**: its share is capped at 1 (§9.3), it is listed, and it is excluded in sensitivity analyses S6a and S6b (§10.5).
    - The reason is that NTEP programme districts can outnumber revenue districts in a few States (for example Delhi).
    - A small number of exceedances is therefore expected. It is handled by the cap and the sensitivity analyses, not by discarding the exposure.
    - More than 3 flagged States would suggest that the column is not a campaign count, and rejects the table (below).
  - **E6.** The selection-criteria table on PDF page 6 ("Sr. No. | Criteria | Number of districts") is read. If it, or the text with it, prints a number of districts selected, that number equals 347. The per-criterion counts are entered in the inventory but not otherwise tested, because the criteria may overlap.
  - **E7.** The sentence that accompanies the table states how many districts were selected across how many States/UTs. It must give 347 districts, and a number of States/UTs equal to the row count.
- **Rejection.** The table is rejected only if one of these holds:
  - E1 fails (TOTAL is not 347);
  - E2 fails (the rows do not sum to TOTAL);
  - E4 fails (fewer than 5 States have a campaign count below their LGD count, so the column may be a count of all districts);
  - more than 3 States are flagged under E5.

  A failure of E3, E6 or E7 does not reject the table. It is reported, and a failure of E6 or E7 is entered as a Q2 discrepancy.
- **Label rule (E3).** Each row label is mapped to a canonical State/UT name as follows:
  1. Match it to a canonical name or a listed alias in the canonical mapping (§11), ignoring case and punctuation, collapsing spaces, and reading "&" as "and".
  2. If there is no match, resolve it from name evidence only: the words of the label, an abbreviation whose expansion names exactly one State/UT (for example "DNH & DND" for Dadra and Nagar Haveli and Daman and Diu), or the name of a combined unit. The resolution and its evidence are logged in `data/source_choices.csv`. Row position and count values are never used as evidence.
  3. If the label fits more than one canonical name, or none, that row's State is not computable and is listed. Its count still enters E1 and E2.
- **If the table is rejected,** it is not used, and there is no repair by hand. The gate rule of design §9.1 is then applied again:
  - the exposure falls back to a named list of campaign districts (below), if its per-State counts pass the same rejection rules;
  - otherwise Q4 is not run, and the paper reports Q1–Q3.

  This consequence is pre-specified and is not a deviation.
- **Named list.** The Kerala copy of the Ministry letter (§3.1.1) is searched for a named list of phase-1 districts. If it holds one whose per-State counts equal the CTD table in every State:
  - the CTD counts remain the exposure;
  - the list serves as a cross-check, and makes the population-share sensitivity analysis possible (§10.5, S7).

  If its counts differ from the CTD table in any State, the difference is a Q2 discrepancy, and the CTD table remains the exposure.
- **States absent from the table.** A State/UT absent from the table has a campaign count of 0, provided E1 and E2 pass. These States are listed.

### 9.3 District denominator: LGD reconstruction at 7 December 2024

- **Reference date.** 7 December 2024, the campaign's start date. The district list in force at the end of that day is the denominator.
- **Rule.**
  - Start from the current list, "All Districts of India", downloaded on 18 November 2026.
  - Reverse every modification in the modification report dated on or after 8 December 2024, working backwards from the latest. Modifications dated 7 December 2024 were in force on the reference date and are kept.
  - The date is taken row by row: each modification row's effective date if that row gives one, and otherwise that row's modification date. The field used for each row is recorded in the reconstruction log.
- **Reversals.** A district created is removed; a district abolished is restored; a district renamed keeps its count; a district moved between States is moved back; a split or merger is undone.
- **Logging.** Every reversal is logged with its row in the report.
- **A State that cannot be reconstructed** is one where a modification cannot be reversed from the fields the report gives. The State is listed, and its exposure is not computable. There is no discretion beyond this rule.
- **Exposure share.** For State s, E_s = min(1, c_s / L_s). Here c_s is the campaign count and L_s the reconstructed LGD count, both after unit coarsening.
  - The capped States are those whose share is 1. They are either States flagged under E5 (campaign count above LGD count) or States with every district in the campaign. They are listed, with the flagged ones marked.
  - Sensitivity analysis S6a excludes the flagged States, and S6b excludes every capped State (§10.5).

### 9.4 Units

Units are combined to the coarser unit in every source and every year, before any join:

- Jammu and Kashmir with Ladakh;
- Dadra and Nagar Haveli with Daman and Diu;
- any other pair that one source reports separately and another combines, as found at extraction and recorded in `data/source_choices.csv`.

For a combined unit, the exposure is Σc ÷ ΣL over its members, and the counts are summed.

The union territories, for sensitivity analysis S5, are those that were union territories on 7 December 2024:

- Andaman and Nicobar Islands;
- Chandigarh;
- Dadra and Nagar Haveli and Daman and Diu;
- Delhi;
- Jammu and Kashmir (with Ladakh);
- Lakshadweep;
- Puducherry.

### 9.5 Outcome tables and their comparability

#### 9.5.1 Primary contrast: full-year 2025 against full-year 2024

The primary contrast is the full calendar year 2025 against the full calendar year 2024, both taken from one document. The author decided this on 18 November 2026, before registration. It replaces the January–October contrast of design §2 and §6.4, which becomes sensitivity analysis S8 (§9.5.3, §10.5).

- **Source.** Rajya Sabha Unstarred Question 1216, answered 10 February 2026.
  - The annexure is headed "State/UT wise Number of TB Case notified and Number of patients who have received the monthly nutritional assistance reported under TB Mukt Bharat Abhiyan, in Year 2023, 2024 and 2025".
  - Its columns are "2023 (Jan-Dec)", "2024 (Jan-Dec)" and "2025 (Jan-Dec)", each split into "No. of TB cases notified" and "Beneficiaries paid at least once".
  - The note reads "Data Source: Ni-kshay (As on [day] February 2026)". The day was masked in the reading of the wording, and the note is to be quoted in full at extraction.
- **Counts used.** The "No. of TB cases notified" columns for 2024 and 2025. The "Beneficiaries paid at least once" columns are not used.

**Comparability (design §9.2, applied to full years).**

- **(a) Same quantity.** Met trivially: both counts are in one table, with one column heading, one source and one as-on date.
- **(b) Same window.** Met trivially: both are full calendar years (1 January to 31 December).
- **(c) Cut-off.** The cut-off is the same February 2026 date for both years. It falls within 60 days after the end of the later window: any day in February 2026 is at most 59 days after 31 December 2025.

  Design §9.2 (c) asked for each year's cut-off to fall within 60 days of that year's window. That holds for 2025 but not for 2024, whose count was drawn about 13 months after its year ended. For this contrast, condition (c) is therefore replaced by a different rule: one as-on date for both years, within 60 days after the end of the later window. The difference in completeness that this leaves is a stated limitation (§10.9). The January–October sensitivity analysis, where both cut-offs are within 0–43 days of the window end, addresses it in part.

#### 9.5.2 Guard: does Question 1216 report total notifications?

Question 1216 reports cases notified in a table about the TB Mukt Bharat Abhiyan, so it must be confirmed that its counts are the State's total notifications. Rajya Sabha Unstarred Question 3467 (answered 1 April 2025) serves as the reference.

- **Reference table.** Its Annexure-I is headed "State-wise TB patients notified and treated successfully in 2023 and 2024". Its columns include "notified", with the footnote "*Treatment outcome will be due in 2025". It states no as-on date.
- **Comparison.** At extraction, and before any Q4 computation, each State's 2023 and 2024 counts in Question 1216 are divided by its "notified" counts in Question 3467, after unit coarsening (§9.4). States lacking either value are left out of the comparison and listed.
- **Lag between the two answers.** For 2023, both counts were drawn at least 15 months after the year ended: Question 3467 on or before 1 April 2025, and Question 1216 in February 2026. For 2024, Question 3467 was drawn about 3 months after the year ended and Question 1216 about 13 months after. Late reports alone can therefore raise the 2024 ratio above 1, so the 2024 bound is one-sided.
- **Rule.** The guard fails, and Question 1216 is judged not to report total notifications, if either of these holds:
  - the median 2023 ratio lies outside 0.95 to 1.05;
  - the median 2024 ratio is below 0.95.

  A median 2024 ratio above 1.05 does not fail the guard. It is expected from late reports and is reported descriptively.
- **If the guard fails.** The primary Q4 analysis is the January–October contrast (§9.5.3), with the fallback trend sources of §9.6. The full-year contrast is then reported descriptively only (§10.7). This consequence is pre-specified and is not a deviation.
- **State discrepancies.** Whatever the medians, any State whose ratio lies outside 0.95 to 1.05 in either year is recorded as a Q2 discrepancy (§7.4). 2024 rows above 1.05 are labelled late-report-consistent in the note column of `outputs/q2_discrepancies.csv`, but are still entered.
- **Failure of Question 1216's own extraction checks** (§9.6) counts as a failed guard for every purpose in this plan, whatever the state of Question 3467.
- **If the guard cannot be applied.** This is the case if Question 1216 passes its extraction checks but either Question 3467 fails its extraction checks (§9.6) or fewer than 10 States have both values for either year. The full-year contrast then remains primary, and the paper states that the guard could not be run.
- **Recording.** The ratios, the medians and the decision are recorded in `data/source_choices.csv` before the freeze (§5.4).

#### 9.5.3 Sensitivity contrast: January–October 2025 against January–October 2024

This pair is sensitivity analysis S8 (§10.5). It becomes the primary contrast if the guard of §9.5.2 fails, including when Question 1216 fails its own extraction checks.

- **January–October 2024:** Lok Sabha Starred Question 261, answered 13 December 2024.
  - Annexure-I, headed "State/UT wise TB cases reported since 2022 to 2024*", column "2024 (Jan- Oct)".
  - The answer text refers to the "current year (till 31.10.2024)".
  - The wording of the footnote marked by the asterisk was not recorded in the masked reading. It is to be quoted verbatim at extraction and judged under the re-check below.
  - Data source: Ni-kshay.
- **January–October 2025:** Rajya Sabha Unstarred Question 1093, answered 9 December 2025.
  - The table is headed "State/UT wise TB cases reported for 2025 (Jan–Oct, 2025)".
  - Data source: Ni-kshay portal.
  - No "as on" date is stated.

**Comparability (design §9.2, as refined here).** The pair qualifies for the regression only if all three conditions hold:

- **(a) Same quantity.** Both tables describe the same quantity in the same words ("TB cases reported") from the same source (Ni-kshay). This is met on the answers' wording.

  Neither answer states whether its counts cover both the public and private sectors. Coverage is assumed to be the same in both years, and this is stated as a limitation. Requiring the word "total", which neither source uses, would test the wording rather than the quantity.
- **(b) Same window.** Both cover 1 January to 31 October. This is met.
- **(c) Cut-off within 60 days after 31 October.**
  - **2024.** The answer states that the data run to 31 October 2024. Read as the cut-off date, the lag is 0 days. Read as the end of the window only, the cut-off is bounded by the answer date, 43 days after 31 October.
  - **2025.** No date is stated. The cut-off cannot be later than the answer date, 9 December 2025, which is 39 days after 31 October.

  The condition is met under either reading.

**Completeness lag.** Ni-kshay counts grow as records are updated. The two tables may have been drawn at different lags after 31 October: 0 to 43 days for 2024, and 0 to 39 days for 2025. S8(a) and S8(b) address this (§10.5).

#### 9.5.4 Re-check at extraction

For every outcome table, any note printed with the values, such as a footnote on a row or on the table, is read at extraction:

- if a note changes the window, cut-off or source for one State, that State is excluded from that contrast and listed;
- if a note changes it for the whole table, the comparability conditions for that contrast are judged again.

If they then fail for the contrast that is primary, Q4 is reported descriptively only (§10.7).

#### 9.5.5 Sources not used for Q4

- **Rajya Sabha Question 2511** (17 December 2024). Its window is the year to 19 November 2024, not January to October (§7.4).
- **Rajya Sabha Question 1900** (16 December 2025). Its heading qualifies the counts as cases "under TB Mukt Bharat Abhiyan". If obtained, its 2025 column is compared with Question 1093 State by State, and any disagreement is a Q2 discrepancy. This cross-check does not change Q4.
- **Rajya Sabha Question 3001** (§3.1.2), on drug-resistant TB, is not used.
- **Rajya Sabha Question 3477** (§3.1.2), on campaign activities, is not used for Q4. It enters the Q1 figure inventory (§5.3).

### 9.6 Annual State notifications for the trend benchmark

**Trend points.** Calendar years 2019, 2022, 2023 and 2024; the primary trend uses all four.

- 2020 and 2021 are excluded (COVID-19 disruption).
- Every point is a full calendar year. January–October counts are never used as annual points.

**Source of each year.** The values are re-extracted by this project's code from the hashed files.

| Year | Primary source | Fallback trend source (used if the guard of §9.5.2 fails, or Question 1216 fails extraction) |
|---|---|---|
| 2019 | India TB Report 2020: the State-wise annexure of total TB patients notified in 2019, located from its list of annexures | Same |
| 2022 | India TB Report 2023, annexure 1.2, "TB patients notified … Total" (PDF pages 213–214) | Same |
| 2023 | Rajya Sabha Question 1216, column "2023 (Jan-Dec)", "No. of TB cases notified" | India TB Report 2024, annexure 1.2, "TB patients notified … Total" (PDF pages 187–188) |
| 2024 | Rajya Sabha Question 1216, column "2024 (Jan-Dec)", "No. of TB cases notified" | Rajya Sabha Question 3467, Annexure-I, the 2024 "notified" column |

- **Why Question 1216 for 2023 and 2024.** It has the same cut-off as the outcome, so the latest trend points and the outcome are counted to the same date.
- **Fallback.** The fallback column replaces the primary sources for 2023 and 2024 together, never one year alone. It is used if the guard of §9.5.2 fails, including when Question 1216 fails its extraction checks. The replacement is recorded in `data/source_choices.csv`.
- **Extraction checks for every Q4 source.** Every Q4 source table fails extraction if its State rows do not sum to its printed total within ±1, or if a needed column cannot be read. This covers Question 1216, Question 3467, the India TB Reports 2020, 2023 and 2024, Lok Sabha Question 261 and Rajya Sabha Question 1093.
  - If no total is printed, the sum check is not applied, and this is reported.
  - A trend source in use (primary or fallback) that fails leaves that year missing for every State, with no further substitution. The trend then uses the remaining points (§9.6, Fit).
  - An outcome table that fails makes its contrast not computable. If that contrast is the primary one, Q4 is reported descriptively from the other contrast if it is computable (§10.7), and is otherwise not run, with the reason.
- **Cross-checks.**
  - The State-level 2022 values are compared with the earlier study's public extraction, and any difference is reported.
  - The 2023 State counts of Question 1216 are compared with the India TB Report 2024, State by State, and any difference is a Q2 discrepancy (§7.4).

**Fit.** For State s, the trend slope β_s is the ordinary least-squares slope of ln(N_s,t) on calendar year t over the State's available trend points. β_s is the State's fitted annual log growth.

- **Fallback for 2019.** A State with no 2019 value uses the points from 2022 onward.
- **Minimum.** At least two points are needed. A State with fewer is not computable and is listed.
- **A zero count** in any trend point makes the State not computable.
- **The 2024 point and the outcome.** In the primary analysis, the 2024 trend point and the outcome's 2024 count are the same number, from Question 1216.

## 10. Q4: analysis

### 10.1 Outcome and expected change

For State s:

- a_s and b_s are the counts for the two windows of the contrast:
  - **primary:** full-year 2024 and full-year 2025, from Question 1216 (§9.5.1);
  - **S8:** January–October 2024 and January–October 2025, from Lok Sabha Question 261 and Rajya Sabha Question 1093 (§9.5.3);
- y_s = ln(b_s / a_s) is the observed change. For the primary contrast this is ln(N_s,2025 / N_s,2024);
- β_s is the fitted annual log growth of §9.6, used as the expected change;
- the **excess change** is x_s = y_s − β_s.

For the primary contrast, the outcome and the trend are both counted over full calendar years. For S8, the expected change assumes that the State's growth over January–October equals its annual growth, which requires unchanged seasonality between the two years. This is stated as a limitation.

### 10.2 Model

- **Fit.** Weighted least squares of x_s on exposure E_s: x_s = γ0 + γ1 E_s + ε_s.
- **Weights.** w_s = 1/(1/a_s + 1/b_s), the inverse of the Poisson variance of y_s. For the primary contrast, w_s = 1/(1/N_s,2024 + 1/N_s,2025).
- **Primary estimand: γ1.** This is the difference in excess log change between a State with every district in the campaign and a State with none. It is also reported as exp(γ1), and per 10 percentage points of exposure as exp(0.1 γ1).
- **The intercept γ0** is reported, with a caveat: any difference in completeness between the two counts that is common to all States moves it (§10.9).
- **Model interval.** The weights set only the relative weighting; the residual variance is estimated:
  - s² = Σ w_s r_s² / (n − 2), where r_s are the residuals of the weighted fit;
  - SE(γ1) = √(s² / Σ w_s (E_s − Ē_w)²), with Ē_w the weighted mean exposure;
  - the 95% interval is γ1 ± t × SE(γ1), where t is the 0.975 quantile of Student's t distribution with n − 2 degrees of freedom. t is computed in code by numerical inversion of the t distribution function, and tested against tabulated values.
- **Minimum.** The regression needs at least 3 States and at least 2 distinct exposure values. Otherwise Q4 is descriptive (§10.7).
- **Reported with every estimate:**
  - the number of States, n;
  - the spread of exposure: sample SD, minimum and maximum, and the weighted and unweighted means.

  There is no power threshold. Q4 is reported with its interval whatever its width.

### 10.3 Bootstrap

- **Draws.** 10,000 resamples of States with replacement. Each resampled State carries its own x, E and w, and γ1 is refitted.
- **Order of States.** Before resampling, the computable States are sorted alphabetically by their coarsened canonical name (Python `sorted` on the name string). Index i in a draw refers to the i-th State in that order.
- **Generator.** `random.Random(20261118)`, reset to that seed before each analysis (the primary analysis, each sensitivity analysis and the placebo). Each draw is `rng.choices(range(n), k=n)`.
- **Degenerate draws.** A draw whose resampled exposures are all equal cannot be fitted. It is counted and excluded, and the count is reported. For a model with two covariates (S8(b)), the rule is given in §10.5.
- **Interval.** The percentile interval of the valid draws: the first and last cut points of `statistics.quantiles(draws, n=40, method="inclusive")`.
- **Role.** The model interval is primary. The bootstrap interval is reported beside it as a check.

### 10.4 States not computable

A State is not computable if:

- it is missing from either outcome column;
- either window count is zero;
- its exposure is not computable (§9.3);
- it has fewer than two trend points (§9.6).

Such States are listed with the reason. No value is imputed, and no count is set to zero.

### 10.5 Sensitivity analyses

Each sensitivity analysis uses the model of §10.2 with the primary contrast and reports both intervals, unless stated otherwise. If the guard of §9.5.2 fails (including when Question 1216 fails its extraction checks), S8 becomes the primary analysis. S1–S7 are then run on the January–October contrast instead, and S8(a) and S8(b) are then run on the primary analysis.

- **S1. Unweighted.** w_s = 1 for every State.
- **S2. Leave one State out.** The model is refitted n times. γ1 is reported for each omission, with the minimum, the maximum, and the State whose omission moves γ1 most. There is no bootstrap.
- **S3. Recent trend only.** Trend points 2022, 2023 and 2024.
- **S4. Three-point trend.** Trend points 2019, 2022 and 2023 only. This excludes the 2024 annual point, which includes December 2024, after the campaign began.
- **S5. States only.** Union territories (§9.4) are excluded.
- **S6a. Flagged States excluded.** The States flagged under E5 (campaign count above LGD count; §9.2) are excluded. If no State is flagged, S6a is reported as empty.
- **S6b. Partial exposure only.** Every capped State, whose exposure share is 1 (§9.3), is excluded. This includes the flagged States and the States with every district in the campaign.
- **S7. Population share as the exposure.** This is run only if a named list of campaign districts is obtained (§9.2).
  - The share is the Census 2011 population (Primary Census Abstract, Office of the Registrar General) of the State's campaign districts, over the State's Census 2011 population.
  - A State with a campaign district created after 2011 is not computable for S7, and is listed.
  - If no named list is obtained, S7 is not run, and the paper says so.
- **S8. January–October contrast.** The model of §10.2 is fitted to the January–October 2025 against January–October 2024 contrast (§9.5.3), with weights from the January–October counts and the trend of §9.6.
  - It is run only if the pair meets conditions (a)–(c) of §9.5.3. Otherwise it is reported descriptively (§10.7).
  - Its cut-offs are 0–43 days after the window end in both years, against 32 to 59 days (2025) and about 13 months (2024) in the primary contrast. It therefore addresses in part the difference in completeness of the primary counts (§10.9).
  - Two further analyses address the difference in reporting lag between its two tables:
  - **S8(a). Uniform lag.** The January–October 2025 counts are multiplied by 0.98 and by 0.95, representing a 2025 table 2% or 5% more complete than the 2024 table.
    - The weights w_s are held fixed at their values from the unscaled counts.
    - A uniform factor shifts every y_s by the same amount, so it changes γ0 but not γ1. The intercept is reported under each factor, and the invariance of γ1 is confirmed in code.
  - **S8(b). State-specific lag.** A State's tendency to late updating is measured by ln r_s. Here r_s is the ratio of the State's 2023 count in Lok Sabha Question 261 (drawn in December 2024) to its 2023 count in the India TB Report 2024.
    - **Model.** ln r_s is added to the S8 model as a second covariate: x_s = γ0 + γ1 E_s + γ2 ln r_s + ε_s, with the same weights. γ1 is reported with and without the covariate.
    - **Interval.** With X the design matrix (a column of ones, E and ln r) and W = diag(w), the covariance of the coefficients is s² (XᵀWX)⁻¹, with s² = Σ w_s r_s² / (n − 3) from the residuals of this fit. The 95% interval for γ1 uses Student's t with n − 3 degrees of freedom.
    - **Bootstrap.** As in §10.3. A draw is degenerate, counted and excluded if its matrix XᵀWX is singular: its determinant is at most 10⁻¹² times the product of its diagonal entries. This includes draws in which all resampled exposures, or all resampled ln r values, are equal.
    - **Exclusions.** States lacking either 2023 count are excluded from S8(b) and listed.
    - **Not computable.** If r_s is equal in every State, the covariate is collinear with the intercept, so S8(b) is not computable, and it is reported as such.

### 10.6 Placebo

No State-wise January–October 2023 table of TB notifications was found (source-search note, §4). The placebo therefore uses annual counts.

- **Observed:** y^P_s = ln(N_s,2023 / N_s,2022).
  - N_s,2023 comes from Question 1216, the 2023 trend source.
  - N_s,2022 comes from the India TB Report 2023.
  - If the trend falls back (§9.6), N_s,2023 comes from the India TB Report 2024 instead.
- **Expected:** β^P_s = ln(N_s,2022 / N_s,2019) / 3, from the India TB Reports 2023 and 2020. This is the State's annual log growth between its two trend points before the placebo window, 2020 and 2021 being excluded. A State with no 2019 value is not computable for the placebo.
- **Excess:** x^P_s = y^P_s − β^P_s.
- **Fit.** WLS of x^P_s on the same exposure E_s, with w_s = 1/(1/N_s,2022 + 1/N_s,2023), and the intervals of §10.2 and §10.3.
- **Expected result.** A campaign that began in December 2024 cannot affect 2022–2023, so the placebo slope should be close to 0.
- **Precision.** The placebo's expected change is a two-point slope across the COVID-19 gap (2019 to 2022). It is therefore noisier than the primary analysis's fitted trend, and the placebo interval is expected to be wider.
- **Source change.** In the primary case, the placebo's observed change crosses from the India TB Report (2022) to Question 1216 (2023). A level difference between the two sources that is common to all States moves only γ0. A difference that varies by State adds noise, and any part of it that varies with exposure would bias the placebo slope.

### 10.7 Descriptive fallback

Q4 is reported descriptively only, with the reason, in any of these cases:

- comparability fails for the contrast that is primary (§9.5);
- the minimum of §10.2 is not met;
- the full-year contrast after the guard of §9.5.2 has failed (including when Question 1216 fails its extraction checks). It is then reported descriptively beside the January–October primary, as far as its columns can be read.

The report is a State table of a_s, b_s, y_s (with its Poisson 95% interval y_s ± z √(1/a_s + 1/b_s), where z = `statistics.NormalDist().inv_cdf(0.975)`), β_s, x_s and E_s. There is no regression and no slope.

If the exposure table is rejected (§9.2) and no named list replaces it, Q4 is not run.

### 10.8 Interpretation, fixed in advance

No P values are reported.

- **Primary result.**
  - It is described as a positive association between exposure and excess notification growth only if both the model interval and the bootstrap interval for γ1 lie wholly above 0.
  - If both lie wholly below 0, it is described as a negative association.
  - Otherwise it is described as showing no clear association, with the interval stated.
- **Placebo.** If its model interval excludes 0, the paper states that the States more exposed to the campaign already differed in notification trend before it began. The primary result is then described as not separable from that difference.
- **Sensitivity analyses** are reported in full beside the primary result. They do not replace it.

### 10.9 Limitations stated in advance

- **Design.** Q4 is ecological, with few units (at most about 35 after coarsening).
- **Selection.** Campaign districts were selected on criteria related to TB burden and vulnerability. Exposure may therefore be associated with pre-existing trends or with regression to the mean. The placebo addresses part of this.
- **Concurrent changes.** Programme changes over the same period include ACF outside the campaign and the roll-out of chest X-ray and molecular testing.
- **Exposure measure.**
  - Exposure is measured as district membership, not as activity performed.
  - In every State, the numerator counts NTEP programme districts and the denominator counts LGD revenue districts. These are different units (§9.2, E5).
- **Completeness of the primary counts.** Both counts were drawn on the same February 2026 date. The 2025 count was therefore taken 32 to 59 days after its year ended, and late updates to it may be incomplete. The 2024 count, at about 13 months, is more complete.
  - This asymmetry understates 2025 relative to 2024. It biases the observed change y_s, and so the excess change, downward.
  - If the shortfall is the same proportion in every State, it moves only γ0. If it varies with exposure, it biases γ1.
  - The January–October sensitivity analysis (S8), whose two cut-offs are both 0–43 days after the window end, addresses this in part.
- **Trend sources.** The primary trend mixes two sources: the India TB Report for 2019 and 2022, and Question 1216 for 2023 and 2024.
  - A level difference between the sources, or a difference in completeness (the Question 1216 counts were drawn later after their years ended), alters β_s. If the later points are relatively more complete, β_s is overstated and the excess change understated.
  - S3 and S4 vary the trend points, and the cross-check of Question 1216 against the India TB Report 2024 for 2023 (§9.6) measures the level difference.
- **Total notifications.** Question 1216 reports cases notified in a table on the TB Mukt Bharat Abhiyan. The guard of §9.5.2 tests whether these are total notifications, at the median and not State by State.
  - Its 2024 test is one-sided. The 2024 counts of Question 3467 were drawn about 3 months after the year ended and those of Question 1216 about 13 months after, so late reports are expected to raise the 2024 ratio above 1.
  - A 2024 ratio above 1 therefore cannot distinguish late reports from a wider count, and only the 2023 test bounds it from above.
- **Lag proxy (S8(b)).**
  - The proxy measures late updating about a year after the data year, not the 0–43-day lag of the January–October tables.
  - Where the trend falls back to the India TB Report 2024 for 2023 (§9.6), ln r_s shares that value with β_s, so the two are not independent.
- **Timing.**
  - The 2025 window includes the rest of the 100-day campaign (to March 2025) and its later expansion. The expansion dilutes the phase-1 contrast.
  - The full-year 2024 count includes December 2024, after the campaign began on 7 December. Any early campaign effect therefore raises the 2024 baseline, which biases the contrast toward no effect. The same month is in the 2024 trend point (S4 omits that point).
- **Coverage (S8).** Neither January–October table states its public and private coverage (§9.5.3), and their completeness lags may differ (S8(a), S8(b)).
- **Seasonality (S8).** The January–October contrast assumes unchanged seasonality (§10.1).

## 11. Software and reproducibility

- **Software.** Python 3.14.0, with every script run as `python -I <script>`.
  - pdfplumber 0.11.8 is used for PDF table extraction only.
  - All analysis uses the Python standard library (`math`, `statistics`, `random`, `csv`).
  - The LGD files are read with `zipfile` and `xml.etree.ElementTree`, which handle the xlsx and SpreadsheetML formats.
- **Provenance.**
  - Every extracted value carries its source file, its PDF page or paragraph, and its table.
  - Every count carries its window start, window end and cut-off date, with the basis of the cut-off (§5.2).
  - In Q4, only counts with the same window are compared. Their cut-off rule is that of §9.5: one shared as-on date within 60 days after the end of the later window (primary), or each cut-off within 60 days after its own window end (S8).
- **State names.** These come from one canonical mapping. In every table, labels are mapped by the label rule of §9.2 (E3), and each resolution is logged. A label that stays unmapped or ambiguous makes its row not computable, and the row is listed.
- **Code reuse.** Code reused from the author's earlier study (State names, extraction primitives, the fetch script and the verification suite) is copied into this repository with attribution, not imported.
- **Numbers.** Every number in the manuscript is derived by code, and checked against the outputs by an automated check.
- **Source files.** These are fetched and verified against the digests in §3. They are not redistributed.

## 12. Reporting principles

- **Discrepancies.** These are reported as properties of the published record, with the evidence for each class. "Unexplained" is not an accusation.
- **Purpose.** The study evaluates the measurement and the evidence, not the value of ACF.
- **The quality studies.** Their reconciliation concerns definitions and denominators, not the authors.
- **Recommendations.** These are framed as programme actions:
  - which figure to quote for which purpose;
  - what to standardise in reporting: definitions, cut-off dates, and publishing the cascade with its denominators;
  - what the evidence says about the campaign and notifications.
- **Reporting guideline and ethics.** The reporting guideline is RECORD. Ethics approval is not required, because only published aggregate data are used.
- **Statistics.** No P values are reported. Every estimate has a 95% interval and its n.

## 13. Deviations

**Registration point.** To be recorded here after the public push of this plan.

Deviations from this plan are logged here, each with its date. Anything exploratory is labelled as such in code and output, and logged here.

**18 November 2026.** None.
