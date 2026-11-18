# Source search and the exposure gate for the dose-response question

Date of search: 18 November 2026.

This note records the source search carried out before the study was registered. It records titles, dates, document types, table headings, stated windows and cut-off dates. No figure values were recorded.

## 1. Gate outcome: GO with official per-state counts

**Outcome: GO-counts.** An official per-state count of phase-1 campaign districts exists. No official list naming the phase-1 districts was found in a document that could be read; two documents that may carry such a list are identified below.

**Evidence.**

- **Source.** Central TB Division (CTD), National TB Elimination Programme, Ministry of Health and Family Welfare: *100 Days Campaign*, a 48-page programme guidance document. The file name carries the date 5 December 2024, and it was posted on the CTD website in January 2025.
  - URL: https://tbcindia.mohfw.gov.in/wp-content/uploads/2025/01/100-days-campaign-Report-1-Complete-on-5-12-2024-New.pdf
  - An identical copy is on the National Health Mission site at https://www.nhm.gov.in/pdf/2024/ntep.pdf. It has the same title and the same byte size, and is not cited.
- **Location of the table.** The section "Geographical prioritization" begins on PDF page 6. It sets out the district-selection criteria in a table headed "Sr. No. | Criteria | Number of districts". The per-state table follows on PDF page 7 (printed page 5), set in two column blocks.
  - **Heading:** "State | Total District".
  - **Rows:** 33 State/UT rows, from Karnataka to Chandigarh, with the merged union territory shown as "DNH & DND", followed by a "TOTAL" row. The rows were counted from the state names alone.
  - **Accompanying text:** a sentence stating that, "following this process", a number of districts were selected across a number of States/UTs, including tribal, mining and aspirational districts.
  - **Consistency:** the 33 rows match the "33 States/UTs" stated in the official campaign synopsis.
- **Named lists.** The document contains no named list of districts. Its annexures are a flow chart for active case finding and TB preventive treatment, a monitoring matrix, and a micro-plan process.
- **Other official documents read.** None of these gives a district list or state counts:
  - the PIB backgrounder (6 December 2024);
  - the PIB *Synopsis of 100-Day Campaign* (7 December 2024, three pages, read in full);
  - every English-language PIB campaign release linked from the CTD website.

**Caveats.**

1. **The column heading "Total District" is terse.** Its placement and the accompanying sentence show that it gives the number of districts selected in each State/UT. The plan should still include a pre-specified check at extraction: the "TOTAL" row must equal the number of selected districts stated in the same document, and that number must equal the phase-1 figure stated by the Ministry. If either check fails, the table is not used as the exposure, and the plan's gate rule is re-applied.
2. **The numerator and the denominator may count different units.** Campaign districts are NTEP programme districts, and some of these differ from revenue districts. The exposure denominator is the LGD district count (section 2). The plan should therefore state what happens if a State's campaign-district count exceeds its LGD count: the share is capped at 1, and the cap is reported.
3. **Possible upgrade to a named list.** Two documents may carry named lists. They were located but could not be read here:
   - **A Ministry of Home Affairs advisory to State prison departments**, "100-Day Intensified Campaign on TB Elimination", dated 8 January 2025.
     - URL: https://www.mha.gov.in/sites/default/files/AdvisoryPR_08012025.pdf
     - Its indexed text shows a district-level table in an annexure.
     - The URL returned "not found" on 18 November 2026.
   - **The Ministry of Health letter L-11012/2/2019-DCC with its attachments**, as reproduced by the Kerala Medical Council.
     - URL: https://medicalcouncil.kerala.gov.in/wp-content/uploads/2025/01/TB_Elimination_Campaign.pdf

   If either contains a named list that agrees with the CTD per-state counts, the outcome can be upgraded to GO-list before registration. The study does not depend on it, because the design's exposure is the share of a State's districts, which the counts give directly.

## 2. Denominator: LGD district counts at December 2024

- **Source.** Local Government Directory (LGD), Ministry of Panchayati Raj: Download Directory at https://lgdirectory.gov.in/downloadDirectory.do.
- **How the count at December 2024 can be obtained.** LGD publishes the current list, not dated snapshots. Two of its reports together allow the count at a reference date to be reconstructed:
  - **"All Districts of India"** (under "Download All Entities of State" or "Download Directory") gives the current list. It is available as PDF, HTML, XLS or ODT.
  - **"Download Only Modifications"**, with the entity set to districts and "from" and "to" dates, lists every district created, renamed, merged or abolished in a date range.
  - **Reconstruction:** take the current list and reverse the modifications dated after the reference date. The proposed reference date is 7 December 2024, the campaign's start date.
- **Access.** Both reports sit behind a CAPTCHA, so the author must download them personally. The analyst will not attempt to bypass the CAPTCHA.
- **Cross-check source.** The Open Government Data platform carries "Local Government Directory (LGD) - Districts" at https://www.data.gov.in/resource/local-government-directory-lgd-districts. It is updated on the first day of every month and holds the current list only, so it can confirm the LGD download but cannot replace the dated reconstruction.
- **Known risk.** At least one State reorganised its districts around December 2024, according to secondary sources. The plan should fix the reference date in advance and apply the reconstruction rule without discretion.

## 3. January–October state tables and the comparability judgement

### 3.1 Metadata of candidate tables

The Rajya Sabha answer PDFs could not be opened from this environment, for three reasons:
- the legacy archive rsdebate.nic.in now redirects to the Rajya Sabha homepage on sansad.in;
- the Lok Sabha archive eparlib.sansad.in did not respond;
- the Rajya Sabha question search on sansad.in returned no results.

The Rajya Sabha tables are, however, reproduced on the Open Government Data platform (data.gov.in), whose notes quote the source question. The metadata below are transcribed from those notes and field names.

| Window | House, question, date | Title (OGD) | Field heading (verbatim) | Total or public only | Stated window | "As on" date |
|---|---|---|---|---|---|---|
| Jan–Oct 2024 | Rajya Sabha, Session 266, Unstarred Q. 2511, answered 17 Dec 2024 | State/UT-wise Number of Tuberculosis (TB) Cases Notification and Death Reported in during 2024 | "TB Cases Notification in 2024 (January to October)" | Not stated | January to October 2024 | "Data for 2024 As on (19-11-2024)"; source Ni-kshay |
| Jan–Oct 2025 | Rajya Sabha, Session 269, Unstarred Q. 1093, answered 9 Dec 2025 | State/UT-wise Number of Tuberculosis (TB) Cases Reported during 2025 | "TB Cases Reported" | Not stated | "Data for 2025 (January to October 2025)" | Not stated; source "Ni-kshay portal" |
| Jan–Oct 2025 (alternative) | Rajya Sabha, Session 269, Unstarred Q. 1900, answered 16 Dec 2025 | State/UT wise Number of Tuberculosis (TB) Cases under TB Mukt Bharat Abhiyan from 2024 to 2025 | "2024 (January to December)"; "2025 (January to October)" | Not stated | "Data for 2025 till October 2025" | Not stated; source "Ni-kshay portal" |
| Jan–Oct 2024 (alternative) | Lok Sabha, Starred Q. 261, "Eradication of TB by 2025", answered 13 Dec 2024 (search-engine index; not opened) | — | Annexure-I "State/UT wise TB cases reported since 2022 to 2024" | Not established | 2024 "till 31.10.2024" | Not established |

Leads not confirmed:
- **Lok Sabha Unstarred Q. 802 (eparlib AU802)** is indexed as an answer of 7 February 2025. Its tables give district-level figures for two States for 2022–2024. It is not a January–October 2025 state table.
- **The leads described as state-wise ACF tables** were Lok Sabha AU3772 (11 August 2023) and Rajya Sabha Unstarred Q. 414 (6 February 2024). On their indexed text:
  - AU3772 is a Ni-kshay Mitra answer, with state TB counts to 30 June 2023;
  - Q. 414 gives state-wise TB tests, diagnoses, treatment and deaths for 2019–2023.

  Neither shows a dedicated ACF table. Both remain in the log for checking at extraction.

### 3.2 Judgement against the comparability rule (design section 9.2), from headings only

The primary pair is Rajya Sabha Q. 2511 (2024) and Rajya Sabha Q. 1093 (2025).

- **(b) Both cover 1 January to 31 October: met.** Both headings or notes state "January to October".
- **(c) Both "as on" dates fall within 60 days after 31 October: met for 2024; met for 2025 by bound.**
  - 2024: the date is 19 November 2024, 19 days after 31 October.
  - 2025: the OGD note states no "as on" date. The data cannot be dated later than the answer (9 December 2025, 39 days after 31 October), so the condition holds whatever the exact date. The plan should state this bounding rule explicitly.
  - **Limitation: the completeness lags differ.** Ni-kshay counts grow as records are updated. The 2024 table was drawn 19 days after the window closed; the 2025 table up to 39 days after. If the 2025 lag is longer, the 2025 counts are more complete, which inflates the observed 2024-to-2025 change in every State. Exposure-related differences in reporting lag would also bias the gradient. The plan will pre-specify a sensitivity analysis for this difference, for example rescaling the 2025 counts by a completeness factor fixed in the plan or re-running Q4 with an alternative 2024 table of later cut-off. The design of that analysis is left to the plan.
- **(a) Both report total (public plus private) notifications, as stated in the answer: not established.** Neither field heading nor note says "total" or "public and private". The two headings also differ in wording: "Notification" in 2024 and "Reported" in 2025.

**Judgement: the January–October pair does not yet pass the rule.** Conditions (b) and (c) are met, but (a) cannot be confirmed from the metadata available here. Under the design, a failed condition means Q4 is reported descriptively only.

**Recommended resolution before registration.** The author downloads the two Rajya Sabha answer PDFs, two short documents, from the sansad.in question archive. Only the answer text and table headings, and not the values, are then read for two things:
- a statement that the counts are total notifications, or that they include private-sector notifications;
- the 2025 "as on" date.

The plan should record the outcome, and record it as a fail if the text is silent on (a).

### 3.3 Status of Q4

Exposure is GO-counts, conditional on the extraction test in section 1. Comparability under design section 9.2 is pending until the answer text is read. Q4's status is therefore pending.

## 4. Placebo choice

**Choice: annual 2023 against 2022 (the design's fallback).** No state-wise January–October 2023 table of total TB notifications was found.

The closest candidates fail on window or measure:
- **Rajya Sabha Q. 618 (25 July 2023):** 2023 data run only to 31 May 2023.
- **Lok Sabha Q. 2277 (15 December 2023, "Cases of TB"):** gives notification rates per 100,000, with 2023 data to November 2023 and annualised.
- **PIB annexure of 19 December 2023:** covers drug-resistant TB only, to 31 October 2023.

The annual 2023 and 2022 state counts come from the India TB Reports already held, as fixed in design section 9.3.

## 5. Availability of the Global Health Action 2023 full text

**Available: the full text and both tables are open on PubMed Central.**

- **Article:** Shewade HD et al., "Quality of active case-finding for tuberculosis in India: a national level secondary data analysis", *Global Health Action* 2023. Published online 21 September 2023.
- **Identifiers and licence:** doi 10.1080/16549716.2023.2256129; PMID 37732993; PMCID PMC10515680; CC BY 4.0.
- **Full text:** https://pmc.ncbi.nlm.nih.gov/articles/PMC10515680/
- **Tables, in HTML:**
  - Table 1, "State-wise TB ACF quality indicators derived for TB ACF cycle (first cycle)", reporting percentage screened among population, percentage tested among screened, percentage diagnosed among tested, and NNS;
  - Table 2, "TB ACF quality indicators derived for each high-risk population", reporting numbers screened, tested and diagnosed with percentages and NNS.
- **Supplementary material:** one Word file.
- **Data availability:** the underlying data are on Figshare at https://doi.org/10.6084/m9.figshare.23723748.
- **Publisher page:** Taylor & Francis is behind bot protection, which was not bypassed. The PMC copy is the one to cite for reading.

The companion study, Shewade HD et al., *PLOS Global Public Health* 2025 (doi 10.1371/journal.pgph.0005103; PMC12574901; CC BY), is also open. It has Tables 1–3 in HTML, four supporting files and a Figshare data collection.

Because both studies publish data on Figshare, the design's reconciliation on common definitions can be run from the published data rather than from the abstracts. The GHA fallback in design section 9.7 should not be needed.

## 6. Download list

Each file needs the author's permission before download. File sizes come from HTTP HEAD requests made on 18 November 2026, except where noted.

| # | File | URL | Size (bytes) | Purpose |
|---|---|---|---|---|
| 1 | 100-days-campaign-Report-1-Complete-on-5-12-2024-New.pdf | https://tbcindia.mohfw.gov.in/wp-content/uploads/2025/01/100-days-campaign-Report-1-Complete-on-5-12-2024-New.pdf | 15,715,802 | Exposure (per-state campaign districts); campaign definitions |
| 2 | TB-Mukt-Bharat-Abhiyan-Campaign-2026-v6.pdf | https://tbcindia.mohfw.gov.in/wp-content/uploads/2026/03/TB-Mukt-Bharat-Abhiyan-Campaign-2026-v6.pdf | 1,036,945 | Campaign progress figures (Q1, Q2) |
| 3 | Guidance-Document-on-TB-Mukt-Bharat-Abhiyan_0.pdf | https://tbcindia.mohfw.gov.in/wp-content/uploads/2025/09/Guidance-Document-on-TB-Mukt-Bharat-Abhiyan_0.pdf | 3,584,607 | Definitions for the expanded campaign (Q2) |
| 4 | doc2024127466601.pdf (PIB synopsis) | https://static.pib.gov.in/WriteReadData/specificdocs/documents/2024/dec/doc2024127466601.pdf | 1,727,083 | Selection criteria and scope as stated (Q2) |
| 5 | doc2024126465901.pdf (PIB backgrounder) | https://static.pib.gov.in/WriteReadData/specificdocs/documents/2024/dec/doc2024126465901.pdf | 806,043 | Campaign scope as stated (Q2) |
| 6 | doc2026324833001.pdf (PIB press note, March 2026) | https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/mar/doc2026324833001.pdf | 624,028 | Cumulative campaign figures (Q1) |
| 7 | India-TB-Report-2019.pdf | https://tbcindia.mohfw.gov.in/wp-content/uploads/2023/05/India-TB-Report-2019.pdf | 16,920,376 | ACF tables (Q1, Q3); see note A |
| 8 | TBAnnaulReport2022.pdf (India TB Report 2022) | https://tbcindia.mohfw.gov.in/wp-content/uploads/2023/05/TBAnnaulReport2022.pdf | 50,821,996 | ACF tables (Q1, Q3) |
| 9 | TB_Elimination_Campaign.pdf (MoHFW letter, Kerala copy) | https://medicalcouncil.kerala.gov.in/wp-content/uploads/2025/01/TB_Elimination_Campaign.pdf | 2,692,311 | Check for a named district list (gate upgrade) |
| 10 | Rajya Sabha Session 266, Unstarred Q. 2511 (17 Dec 2024), answer PDF | sansad.in Rajya Sabha question archive; direct link not resolvable here | not available | Q4 2024 window; confirm condition (a) |
| 11 | Rajya Sabha Session 269, Unstarred Q. 1093 (9 Dec 2025), answer PDF | as above | not available | Q4 2025 window; confirm condition (a) and the "as on" date |
| 12 | Rajya Sabha Session 269, Unstarred Q. 1900 (16 Dec 2025), answer PDF | as above | not available | Alternative 2025 window; definition check |
| 13 | OGD CSV mirrors of items 10–12 and of Rajya Sabha Q. 420 (2026), Q. 1216 (2026) and Q. 3467 (2025) | data.gov.in resource pages listed in data/search_log.csv | about 1,000 each (as stated on the pages: 1,012; 791; 1.0 KB; 826; 2.0 KB; 1.2 KB) | Machine-readable copies; 2024 annual counts (note B) |
| 14 | LGD "All Districts of India" and "Download Only Modifications" (districts, from 7 Dec 2024) | https://lgdirectory.gov.in/downloadDirectory.do | generated on request | Exposure denominator; author downloads personally (CAPTCHA) |
| 15 | GHA 2023 supplementary file ZGHA_A_2256129_SM2351.docx | https://pmc.ncbi.nlm.nih.gov/articles/instance/10515680/bin/ZGHA_A_2256129_SM2351.docx | not available (HEAD returns an interstitial page) | Q2 reconciliation |
| 16 | GHA 2023 Figshare dataset (file dataset_v2.xlsx) | https://doi.org/10.6084/m9.figshare.23723748 | about 89,520 (89.52 kB as stated on the Figshare page; HEAD returns a challenge page) | Q2 recomputation on common definitions |
| 17 | doc20241228477601.pdf (PIB year-end review 2024) | https://static.pib.gov.in/WriteReadData/specificdocs/documents/2024/dec/doc20241228477601.pdf | 2,241,823 | ACF figure to a stated 2024 cut-off (Q1) |
| 18 | PGPH 2025 S1 File (ACF data collection tool, PDF) | https://journals.plos.org/globalpublichealth/article/file?type=supplementary&id=10.1371/journal.pgph.0005103.s001 | not available (HEAD refused, 403) | Q2 definitions |
| 19 | PGPH 2025 S1 Fig (district map, DOCX) | https://journals.plos.org/globalpublichealth/article/file?type=supplementary&id=10.1371/journal.pgph.0005103.s002 | not available (HEAD refused, 403) | Q2 context; optional |
| 20 | PGPH 2025 S1 Table (revised indicators, DOCX) | https://journals.plos.org/globalpublichealth/article/file?type=supplementary&id=10.1371/journal.pgph.0005103.s003 | not available (HEAD refused, 403) | Q2 indicator definitions |
| 21 | PGPH 2025 S2 Table (time taken in the care cascade, DOCX) | https://journals.plos.org/globalpublichealth/article/file?type=supplementary&id=10.1371/journal.pgph.0005103.s004 | not available (HEAD refused, 403) | Q2; optional |
| 22 | PGPH 2025 Figshare collection, data item (annexs3.rec, EpiData) | https://figshare.com/articles/dataset/Shewade_HD_et_al_TB_ACF_phase_III_project_obj_1_and_2_data/25106060 (collection doi 10.6084/m9.figshare.c.7048385.v1) | about 47,150,000 (47.15 MB as stated on the Figshare page; HEAD returns a challenge page) | Q2 recomputation on common definitions |
| 23 | PGPH 2025 Figshare collection, codebook (Codebook.xlsx) | https://figshare.com/articles/online_resource/Shewade_HD_et_al_TB_ACF_phase_III_project_obj_1_and_2_codebook_of_the_REC_file_/25106084 | about 17,730 (17.73 kB as stated on the Figshare page) | Variable definitions for item 22 |
| 24 | PGPH 2025 Figshare collection, programme file (annexs3.pgm) | https://figshare.com/articles/software/Shewade_HD_et_al_TB_ACF_phase_III_project_obj_1_and_2_programme_file_EpiData_PGM_file_for_the_data_EpiData_REC_format_/25106096 | about 7,510 (7.51 kB as stated on the Figshare page) | Authors' analysis code; documents their indicator definitions |

The ten files with HEAD-verified sizes (items 1–9 and 17) total 96,171,014 bytes, about 96 MB. The Figshare items with page-stated sizes (items 16 and 22–24) add about 47.3 MB, almost all of it the PGPH record-level data file (item 22). That file is needed only if the reconciliation recomputes the PGPH indicators from individual records; if the published tables suffice, it can be dropped. Items 10–15 and 18–21 add a few megabytes at most.

The PIB release pages marked include = yes in data/search_log.csv are HTML pages. They are read online and their text is quoted with the page URL and access date, so they need no download. The same applies to the HTML full texts of the two quality studies on PMC and PLOS.

The GHA 2023 PDF on PMC (stated on the page as 3.3 MB) is not needed, because the HTML full text is open. The Lok Sabha answers (Starred Q. 261 of 13 December 2024 and Starred Q. 79 of 7 February 2025) and the Rajya Sabha campaign answers of February and March 2025 are logged for the inventory. Their archives could not be reached, so no size is given; they should be requested in a later batch once a working link is confirmed.

**Note A.** The 2019 edition of the India TB Report gives calendar-2018 data. The 2019 point of the trend benchmark (design section 9.3) comes from the 2020 edition, which the author already holds. The 2019 edition is needed only for the ACF inventory, and the author may defer it.

**Note B.** No India TB Report edition giving calendar-2024 state notifications was found on the CTD website. Until one is published, the 2024 annual state counts for the trend benchmark must come from a parliamentary answer. Candidates are Rajya Sabha Q. 3467 (1 April 2025), Q. 1900 (16 December 2025) and Q. 1216 (10 February 2026). These have different cut-off dates, so the plan should fix which one is used.

## 7. What was searched and what was found

- **Sites and terms.** The six sites in design section 9.6 were searched for "active case finding", "ACF" and "TB Mukt Bharat Abhiyaan" (and the variant "Abhiyan"), with the date window 1 December 2022 to 18 November 2026:
  - tbcindia.mohfw.gov.in;
  - pib.gov.in, including static.pib.gov.in;
  - eparlib.sansad.in;
  - rsdebate.nic.in;
  - data.gov.in;
  - ntep.in.
- **Methods.**
  - **Site search:** each site's own search, used for tbcindia.mohfw.gov.in and data.gov.in.
  - **Web search restricted to each domain:** used for all six sites.
  - **Link pages:** pages that list campaign documents were followed, such as CTD's index of PIB releases.
- **Supporting searches** were run to locate the phase-1 district list, the January–October tables, the LGD source and the GHA 2023 full text. News coverage was used only to locate official documents and is not logged as a source.

**Coverage by site and term.** Each cell gives the method and the number of relevant documents (rows marked include = yes) located by that search. Counts of all logged rows are in brackets. The last column counts relevant documents on the same site located by supporting searches or link following, which the three term searches did not return.

| Site | "active case finding" | "ACF" | "TB Mukt Bharat Abhiyaan" | Located by supporting searches |
|---|---|---|---|---|
| tbcindia.mohfw.gov.in | Site search: none relevant (6 rows) | Site search: no results (1 row) | Site search, both spellings: none relevant (6 rows; the hits were a similarly named programme, Ni-kshay Mitra guidance and photo pages) | 7 (campaign document, 2026 campaign document, 2025 guidance, India TB Report 2019 and 2022 pages and PDFs) |
| pib.gov.in | Domain-restricted web search: 4 relevant (10 rows) | Domain-restricted web search: plain term returned no on-domain results (1 row); a query with campaign qualifiers gave 6 relevant (9 rows) | Domain-restricted web search: 10 relevant (10 rows) | 8 relevant and 1 provisional, from CTD's index of PIB releases and other searches (26 rows, including 15 translations) |
| eparlib.sansad.in | Domain-restricted web search: none relevant (1 row); host unreachable | Domain-restricted web search: none relevant (1 row); host unreachable | Domain-restricted web search: none relevant (1 row); host unreachable | 2, from open web search (indexed text only; 12 rows) |
| rsdebate.nic.in | Domain-restricted web search: none relevant within the window (2 rows, both from 2021); host redirects | Domain-restricted web search: no on-domain results (1 row) | Domain-restricted web search: none relevant (1 row) | 4, from open web search (indexed text only; 5 rows) |
| data.gov.in | Site search: none relevant (4 rows, all intensified case finding among people with HIV or duplicates of the India TB Report) | Site search: none relevant (1 row) | Site search ("TB Mukt Bharat"): 3 relevant (4 rows) | 4 (both January–October tables, the 2023–2024 notification table and the LGD feed; 10 rows) |
| ntep.in | Domain-restricted web search: 1 relevant (10 rows) | Domain-restricted web search: no on-domain results (1 row) | Domain-restricted web search: none relevant (1 grouped row, 10 pages, all on the similarly named community-support programme) | none |

- **Search log.** data/search_log.csv has 149 rows: 56 marked include = yes, 1 provisional and 92 marked include = no, each with a reason.
  - **Search rows:** 10 rows record a search or portal that returned nothing usable rather than a document.
  - **Grouped rows:** four rows group navigation or module pages that are not documents (8, 8, 4 and 10 pages). Each states the count in its title.
  - **All other rows** are single documents.

  | Site | Rows |
  |---|---|
  | pib.gov.in | 56 |
  | tbcindia.mohfw.gov.in | 23 |
  | data.gov.in | 19 |
  | eparlib.sansad.in | 15 |
  | ntep.in | 12 |
  | rsdebate.nic.in | 9 |
  | other official or journal hosts, used to verify leads (including the sansad.in portal) | 15 |

- **Access limits during the search.** These limits narrow what could be verified from headings:
  - eparlib.sansad.in and eparlib.nic.in could not be reached;
  - rsdebate.nic.in redirects to sansad.in;
  - the sansad.in question search returned no results;
  - several Ministry of Health and Ministry of Home Affairs file links returned "not found";
  - the Taylor & Francis article page is behind bot protection.

  Metadata for the parliamentary answers therefore come from the Open Government Data mirrors and from search-engine indexes of the PDFs, and the log marks which is which.

## 8. Document added after the search

Added on 18 November 2026, before registration: Rajya Sabha Unstarred Question 3477, answered 1 April 2025, on the activities of the TB Mukt Bharat Abhiyaan campaign.

- It was obtained by the author together with the parliamentary answers that give 2024 State notifications (Rajya Sabha Unstarred Questions 1216 and 3467).
- Only its wording was read, with all counts masked.
- It may contain national campaign figures, so it is included in the figure inventory for Q1 and Q2 and read at extraction. It is not used for the dose-response question.
