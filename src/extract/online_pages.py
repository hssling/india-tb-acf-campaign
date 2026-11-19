"""Web pages read online (analysis plan §3.3 and §5.3; Part D).

The include = yes rows of data/search_log.csv that are HTML pages (PIB releases and press
note, the ntep.in chapter, two tbcindia report pages) and the pages that those pages cite
by name as the source of a figure (§5.3) were read online on 19 November 2026. Each page's
raw HTML was fetched with curl to standard output and its visible text extracted with
python -I and html.parser; nothing was saved to the repository. The sentences and table
cells that hold an in-scope figure were copied from that text into
data/transcribed/online_pages.csv, one row for each page and one for each sentence or cell,
with the URL, the access time (UTC), the method and a locator.

This module turns that file into figure-inventory rows (every §5.2 column, filled by the
rules of §6.1, §7.1 and §7.2 from the sentence alone, as clarified in §13 of 19 November
2026) and into inventory_scope_decisions.csv rows for what was left out. It computes
nothing else. Rows of the other extractors are kept by the merge on `source_file`.

Run: python -I src/extract/online_pages.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import csv
import re

from src import inventory_rules as R
from src import states
from src.extract import invrow
from src.extract.campaign import INVENTORY_COLUMNS

ROOT = Path(__file__).resolve().parents[2]
EXTRACTED = ROOT / "data/extracted"
INVENTORY = ROOT / "data/figures_inventory.csv"
TRANSCRIBED = ROOT / "data/transcribed/online_pages.csv"

TR_COLUMNS = ["page_key", "url", "accessed_utc", "method", "title", "pub_date_printed",
              "kind", "locator", "text", "table_title", "column_heading", "row_label",
              "availability", "cited_by", "note"]
SCOPE_COLUMNS = ["kind", "doc", "source_file", "page", "figures", "where", "category",
                 "decision", "reason"]
_MONTHS = {m: i for i, m in enumerate(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), start=1)}


def read_transcribed() -> list[dict]:
    with open(TRANSCRIBED, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _pages() -> dict[str, dict]:
    return {r["page_key"]: r for r in read_transcribed() if r["kind"] == "page"}


def doc_key(page_key: str) -> str:
    if page_key.isdigit():
        return "PIB" + page_key
    return {"note157923": "PIBN157923", "dghsntep": "DGHSNTEP"}[page_key]


def pub_iso(printed: str) -> str:
    """'06 DEC 2024 7:38PM by PIB Delhi' -> '2024-12-06'; '' where no date is printed."""
    m = re.match(r"(\d{2}) ([A-Z]{3}) (\d{4})\b", printed.strip())
    return f"{m.group(3)}-{_MONTHS[m.group(2)]:02d}-{m.group(1)}" if m else ""


def _urls() -> frozenset[str]:
    return frozenset(r["url"] for r in read_transcribed() if r["kind"] == "page")


OWN_FILES = _urls()

# ============================================================ figure specifications
# (page_key, sentence id, quantity, printed, unit, definition, options). The definition is
# the source's own words for the quantity, a substring of the sentence (or of the row
# label for a table cell). Options: period (window words as printed), wstart, wend,
# series, geography, notes, as_on.
SPECS: list[tuple] = []


def add(pk, sid, q, printed, unit, definition, **kw):
    SPECS.append((pk, sid, q, printed, unit, definition, kw))


NOUNIT = "no unit of the §5.2 vocabulary applies (a count of {})"
ST = "100-day campaign figure of phase 1 and its expansion"


def _build_specs() -> None:
    # ---- PIB 6 Dec 2024, India's 100-Day TB Elimination Campaign
    add("2081662", "s1", "districts_selected", "347", "districts", "347 districts")
    add("2081662", "s1", "other:states_uts_selected", "33", "", "states and union territories",
        notes=(NOUNIT.format("States/UTs"),))
    add("2085802", "s1", "districts_selected", "347", "districts", "347 priority districts")
    add("2085802", "s2", "other:parliamentarians_present", "250", "persons",
        "Members of Parliament were present at the event",
        notes=("sensitisation event for the campaign; the sentence names the campaign",))
    # ---- PIB 6 Jan 2025 (joint strategy meeting)
    add("2090668", "s1", "screened", "2 crore", "persons", "people have been screened",
        period="first 30 days")
    add("2090668", "s1", "tb_cases", "1.48 lakh", "cases", "new cases of TB have been identified",
        period="first 30 days")
    add("2090668", "s2", "other:line_ministries_involved", "21", "", "21 Line Ministries",
        notes=(NOUNIT.format("ministries"),))
    add("2090668", "s3", "other:anganwadi_workers_contributing", "14 lakh", "persons",
        "Anganwadi workers are contributing")
    # ---- PIB 22 Feb 2025
    add("2105575", "s1", "tb_cases", "5.1 lakh", "cases", "notifications have been recorded",
        wstart="2024-12-07", series="cumulative")
    add("2105575", "s2", "tb_cases", "3.5 lakh", "cases", "TB patients have been notified")
    add("2105575", "s2", "districts_selected", "455", "districts", "455 intervention districts",
        notes=("the campaign's later district count (347 at launch); printed as intervention "
               "districts",))
    add("2105575", "s2", "screened", "10 crore", "persons", "vulnerable individuals have been screened")
    add("2105575", "s3", "other:tb_cases_notified_public", "2.4 lakh", "cases",
        "patients have been notified from public health institutions",
        notes=("subset of the notified cases by sector (§5.1 rule 2: a subset enters as other)",))
    add("2105575", "s3", "other:tb_cases_identified_private", "1.1 lakh", "cases",
        "identified through private healthcare facilities",
        notes=("subset of the notified cases by sector",))
    add("2105575", "s4", "other:nikshay_shivirs_conducted", "10 lakh", "",
        "Ni-kshay Shivirs have been organized", notes=(NOUNIT.format("camps"),))
    add("2105575", "s4", "other:nikshay_vahans_deployed", "836", "",
        "Ni-kshay Vahans have been deployed", notes=(NOUNIT.format("vehicles"),))
    add("2105575", "s5", "screened", "38 lakh", "persons",
        "people have been screened using chest x-rays")
    add("2105575", "s6", "other:line_ministries_involved", "22", "", "22 ministries",
        notes=(NOUNIT.format("ministries"),))
    add("2105575", "s7", "other:parliamentarians_present", "250", "persons", "parliamentarians",
        notes=("sensitisation session for the campaign",))
    add("2105575", "s8", "other:nikshay_mitras_registered", "2.4 lakh", "persons",
        "Ni-kshay Mitras have registered")
    add("2105575", "s8", "other:food_baskets_provided", "2.3 lakh", "",
        "food baskets have been distributed", notes=(NOUNIT.format("food baskets"),))
    # ---- PIB 24 Mar 2025 backgrounder
    add("2114549", "s1", "tb_cases", "3 Lakh", "cases", "Additional Cases Found via House-to-House Screening",
        notes=("a case-finding result: house-to-house screening of high-risk groups is active "
               "case finding by definition, and the cited DGHS NTEP page files the same "
               "figure ('an additional ~3 lakh TB cases') under 'Active Case Finding'; the "
               "item names neither the campaign nor ACF, so scope is unspecified",))
    # ---- PIB 24 Mar 2025 summit
    add("2114554", "s1", "other:nikshay_shivirs_conducted", "13.46 lakh", "",
        "Nikshay Shivirs, or community screening and awareness camps were organised",
        notes=(NOUNIT.format("camps"), "paragraph on the 100 Days Intensified campaign"))
    add("2114554", "s2", "screened", "12.97 crore", "persons", "people were screened for TB",
        notes=("the release gives it as the 100-day campaign's result (headline bullet)",))
    add("2114554", "s2", "tb_cases", "7.19 lakh", "cases", "new cases detected",
        notes=("the release gives it as the 100-day campaign's result (headline bullet)",))
    add("2114554", "s3", "other:asymptomatic_tb_cases", "2.85 lakh", "cases", "asymptomatic cases")
    add("2114554", "s4", "other:mlas_participating", "5,000", "persons", "MLAs")
    add("2114554", "s4", "other:gram_panchayats_participating", "10,000", "",
        "Gram Panchayats participated", notes=(NOUNIT.format("Gram Panchayats"),))
    add("2114554", "s5", "other:line_ministries_involved", "22", "", "22 line ministries",
        notes=(NOUNIT.format("ministries"),))
    add("2114554", "s5", "other:elected_representatives_involved", "30,000", "persons",
        "elected representatives were mobilized")
    add("2114554", "s6", "other:nikshay_mitras_registered", "1,05,181", "persons",
        "new Ni-kshay Mitras have registered")
    add("2114554", "s6", "other:food_baskets_provided", "3,06,368", "", "food baskets",
        notes=(NOUNIT.format("food baskets"),))
    # ---- PIB 13 May 2025
    add("2128490", "s1", "screened", "12.97 crore", "persons", "vulnerable individuals were screened")
    add("2128490", "s1", "tb_cases", "7.19 lakh", "cases", "TB cases detected")
    add("2128490", "s1", "other:asymptomatic_tb_cases", "2.85 lakh", "cases", "asymptomatic TB cases")
    add("2128490", "s2", "other:nikshay_mitras_registered", "1 lakh", "persons",
        "new Ni-kshay Mitras joined the effort")
    # ---- PIB explainer 24 Mar 2026 (press note 157923 and Backgrounder 2244661: same text)
    for pk in ("note157923", "2244661"):
        add(pk, "b1", "screened", "20 crore", "persons", "vulnerable population is screened for TB",
            wstart="2024-12-07", series="cumulative")
        add(pk, "b1", "tb_cases", "28 lakh", "cases", "TB patients diagnosed",
            wstart="2024-12-07", series="cumulative")
        add(pk, "s2", "districts_selected", "347", "districts", "347 high-priority districts")
        add(pk, "s2", "other:states_uts_selected", "33", "", "States/UTs",
            notes=(NOUNIT.format("States/UTs"),))
        add(pk, "s4", "screened", "20 crore", "persons", "vulnerable population is screened for TB",
            wstart="2024-12-07", series="cumulative")
        add(pk, "s4", "tb_cases", "28 lakh", "cases", "TB patients are diagnosed",
            wstart="2024-12-07", series="cumulative")
        add(pk, "s4", "other:asymptomatic_tb_cases", "9 lakh", "cases", "asymptomatic cases",
            wstart="2024-12-07", series="cumulative")
        add(pk, "s6", "other:treatment_success_rate", "90%", "percent", "treatment success rate")
        add(pk, "s7", "screened", "1,250", "persons", "the team screened 1,250 people",
            geography="Jammu and Kashmir", period="three days",
            notes=("screening campaign of the NTEP Kashmir team in Gurez, not the national "
                   "campaign",))
        add(pk, "s7", "presumptive", "250", "persons", "potential TB cases for further testing",
            geography="Jammu and Kashmir", period="three days",
            notes=("screening campaign of the NTEP Kashmir team in Gurez, not the national "
                   "campaign",))
        add(pk, "c1", "screened", "1.62+ Lakh", "persons", "TB Screening",
            notes=("Cough Against TB (AI tool); the cell carries footnote marker [2], which "
                   "the PDF version resolves to PIB PRID 2199422 (a cited source, read in this "
                   "part)",))
        add(pk, "c1", "other:extra_yield_over_conventional", "12–16%", "percent",
            "extra yield in cases over conventional methods",
            notes=("printed as a range, value left blank; Cough Against TB (AI tool)",))
    # ---- PIB 24 Mar 2026 World TB Day launch
    add("2244703", "s1", "other:high_risk_villages_wards", "1.58 lakh", "", "villages and urban wards",
        notes=(NOUNIT.format("villages and wards"),))
    add("2244703", "s2", "districts_selected", "347", "districts", "347 districts")
    add("2244703", "s3", "screened", "20 crore", "persons", "vulnerable individuals have been screened",
        period="since the commencement of the campaign in december 2024",
        notes=("start stated as December 2024 (no day), so window_start is blank and the "
               "series is not cumulative",))
    add("2244703", "s3", "tb_cases", "32.65 lakh", "cases", "detection of 32.65 lakh TB patients",
        notes=("start stated as December 2024 (no day), so window_start is blank",))
    add("2244703", "s4", "other:asymptomatic_tb_cases", "10.9 lakh", "cases", "asymptomatic patients",
        notes=("the sentence refers to the cases of the previous sentence ('this included')",))
    add("2244703", "s5", "screened", "20 crore", "persons", "vulnerable individuals have been screened",
        period="since december 2024", notes=("start stated as December 2024 (no day)",))
    add("2244703", "s5", "tb_cases", "32.65 lakh", "cases", "detection of 32.65 lakh TB patients",
        period="since december 2024", notes=("start stated as December 2024 (no day)",))
    add("2244703", "s5", "other:asymptomatic_tb_cases", "10.9 lakh", "cases", "asymptomatic cases",
        period="since december 2024", notes=("start stated as December 2024 (no day)",))
    # ---- PIB 1 Jul 2026 (Delhi review)
    add("2279976", "s1", "other:high_risk_villages_wards", "1.58 lakh", "", "high-risk villages and wards",
        notes=(NOUNIT.format("villages and wards"), "national count, from AI vulnerability mapping"))
    add("2279976", "s1", "other:high_risk_wards_in_focus", "38", "", "38 wards", geography="Delhi",
        notes=(NOUNIT.format("wards"),))
    add("2279976", "s1", "other:districts_with_focus_wards", "11", "districts", "11 districts",
        geography="Delhi")
    add("2279976", "s1", "other:pct_high_risk_burden_in_focus_wards", "80%", "percent",
        "over 80% of the city’s high-risk burden", geography="Delhi")
    for q, p, u, d in (("screened", "28.83 lakh", "persons", "screened 28.83 lakh people"),
                       ("tested", "21.67 lakh", "tests", "chest X-rays"),
                       ("tested", "3.65 lakh", "tests", "molecular (NAAT) tests"),
                       ("tb_cases", "1.75 lakh", "cases", "notified 1.75 lakh TB patients")):
        add("2279976", "s2", q, p, u, d, geography="Delhi",
            notes=("the release's headline bullet gives the Delhi figures 'under the Abhiyaan'; "
                   "the sentence itself names no campaign",))
    # ---- PIB 29 Jul 2026 and 11 Aug 2026 (MPs)
    for pk in ("2291403", "2297901"):
        add(pk, "s1", "districts_selected", "347", "districts", "347 high-priority districts")
        add(pk, "s2", "other:high_risk_villages_wards", "1.58 lakh", "", "high-risk villages and urban wards",
            notes=(NOUNIT.format("villages and wards"),))
    add("2297901", "s4", "screened", "2.02 crore", "persons", "screened over 2.02 crore vulnerable individuals",
        wstart="2026-03-24", wend="2026-07-04",
        notes=("window from the preceding sentence (lead-in s3: 'which ran from March 24 to "
               "July 4, 2026')",))
    add("2297901", "s4", "tb_cases", "7 lakh", "cases", "detected over 7 lakh new TB cases",
        wstart="2026-03-24", wend="2026-07-04",
        notes=("window from the preceding sentence (lead-in s3)",))
    add("2297901", "s4", "other:asymptomatic_tb_cases", "1.97 lakh", "cases", "asymptomatic cases",
        wstart="2026-03-24", wend="2026-07-04",
        notes=("window from the preceding sentence (lead-in s3)",))
    add("2297901", "s5", "other:naat_machines", "11,000", "",
        "molecular testing from a few hundred machines a decade ago to over 11,000 today",
        notes=(NOUNIT.format("machines"), "the sentence states them as 'the technological "
               "foundation that has powered the campaign' (§5.1 rule 3)"))
    add("2297901", "s5", "other:xray_handheld_units", "3,000", "", "AI-enabled handheld X-ray units",
        notes=(NOUNIT.format("machines"), "the sentence states them as 'the technological "
               "foundation that has powered the campaign' (§5.1 rule 3)"))
    # ---- PIB Backgrounder 13 Oct 2026
    pk = "2322820"
    add(pk, "s1", "screened", "28.1 crore", "persons", "cumulative screenings",
        notes=("'crossed' is not a qualifier word of §6.1, so exact",))
    add(pk, "s1", "other:tpt_individuals_provided", "20 lakh", "persons",
        "individuals provided TB Preventive Treatment (TPT)")
    add(pk, "s1", "other:nikshay_mitras_registered", "5.7 lakh", "persons", "new Nikshay Mitras added")
    add(pk, "s1", "other:gram_panchayats_tb_free_certified", "46,118", "",
        "Gram Panchayats awarded TB-free certification", notes=(NOUNIT.format("Gram Panchayats"),))
    add(pk, "s2", "districts_selected", "347", "districts", "347 high-priority districts")
    add(pk, "s2", "other:states_uts_selected", "33", "", "States/UTs", notes=(NOUNIT.format("States/UTs"),))
    add(pk, "s4", "screened", "28.1 crore", "persons", "people screened",
        notes=("'As of June 2026' gives a month only: as_on left blank",))
    add(pk, "s4", "other:tpt_individuals_provided", "20 lakh", "persons",
        "individuals provided TB Preventive Treatment (TPT)",
        notes=("'As of June 2026' gives a month only: as_on left blank",))
    add(pk, "s4", "other:nikshay_mitras_registered", "5.7 lakh", "persons", "new Nikshay Mitras added",
        notes=("'As of June 2026' gives a month only: as_on left blank",))
    add(pk, "s5", "other:ayushman_arogya_shivirs_held", "1.7 lakh", "", "Ayushman Arogya Shivirs were held",
        period="second phase starting march 2026", notes=(NOUNIT.format("camps"),))
    add(pk, "s5", "other:high_risk_villages_wards", "1.2 lakh", "", "high-risk villages and wards",
        period="second phase starting march 2026", notes=(NOUNIT.format("villages and wards"),))
    add(pk, "s5", "other:students_participating", "32 lakh", "persons", "students",
        period="second phase starting march 2026")
    add(pk, "s5", "other:my_bharat_volunteers_participating", "1.9 lakh", "persons", "MY Bharat volunteers",
        period="second phase starting march 2026")
    add(pk, "s6", "other:treatment_success_rate", "90%", "percent", "treatment success rate")
    add(pk, "s7", "screened", "1,250", "persons", "the team screened 1,250 people",
        geography="Jammu and Kashmir", period="three days",
        notes=("screening campaign of the NTEP Kashmir team in Gurez, not the national campaign",))
    add(pk, "s7", "presumptive", "250", "persons", "potential TB cases for further testing",
        geography="Jammu and Kashmir", period="three days",
        notes=("screening campaign of the NTEP Kashmir team in Gurez, not the national campaign",))
    # ---- PIB 12 Nov 2026
    pk = "2335615"
    add(pk, "s1", "districts_selected", "347", "districts", "347 high-priority districts")
    add(pk, "s1", "other:states_uts_selected", "33", "", "States and Union Territories",
        notes=(NOUNIT.format("States/UTs"),))
    add(pk, "s2", "other:high_risk_villages_wards", "1.58 lakh", "", "high risk villages & wards",
        notes=(NOUNIT.format("villages and wards"), "scope '100 days' is read by rule (§7.2) "
               "from the words 'another intensified 100 Days campaign'; the sentence "
               "describes the campaign launched on 24 March 2026"))
    win = dict(wstart="2024-12-07", wend="2026-11-08", series="cumulative",
               notes=("window from the lead-in s3 ('Between 7 December 2024 and 8th November "
                      "2026, the Abhiyaan achieved significant progress:'); the window's end "
                      "is not taken as the cut-off (as_on_basis bounded)",))
    add(pk, "l1", "screened", "25 crore", "persons",
        "individuals identified and brought within the ambit of TB screening activities", **win)
    add(pk, "l2", "tested", "11 crore", "tests", "chest X-rays conducted", **win)
    add(pk, "l3", "tested", "3 crore", "tests", "nucleic acid amplification tests (NAAT) conducted", **win)
    add(pk, "l4", "tb_cases", "48.64 lakh", "cases", "new TB cases identified", **win)
    add(pk, "l4", "other:asymptomatic_tb_cases", "14.97 lakh", "cases", "asymptomatic cases", **win)
    add(pk, "s5", "other:asymptomatic_tb_cases", "15 lakh", "cases", "asymptomatic cases")
    # ---- year-end reviews of the Ministry (2023, 2022)
    add("1990674", "s1", "tb_cases", "3 lakh", "cases", "diagnosis of an additional ~3 lakh TB cases",
        period="since its inception")
    add("1990674", "s2", "other:ishth_camps", "3600", "", "conducted in 3600 camps",
        notes=(NOUNIT.format("camps"), "integrated campaign (ISHTH) among inmates, entered as "
               "the ISHTH rows of the 2024 year-end review are (Part A)"))
    add("1887285", "s1", "tb_cases", "2.52 lakhs", "cases", "diagnosis of an additional 2.52 lakhs TB cases",
        period="past 4 years")
    # ---- cited sources (§5.3)
    add("2199422", "s1", "screened", "1.62 lakh", "persons", "screen more than 1.62 lakh individuals",
        period="between march 2023 and 30th november 2025", wend="2025-11-30",
        notes=("start stated as March 2023 (no day), so window_start is blank; the window's "
               "end is not taken as the cut-off",))
    add("2199422", "s2", "other:extra_yield_over_conventional", "12-16%", "percent",
        "additional yield of 12-16% in TB reported", notes=("printed as a range, value left blank",))
    add("2113683", "s1", "other:extra_yield_over_conventional", "12-16%", "percent",
        "additional yield of 12-16% in TB reported", notes=("printed as a range, value left blank",))
    add("2275402", "s1", "screened", "28.1 crore", "persons", "people have already been screened",
        period="since december 2024", notes=("start stated as December 2024 (no day)",))
    add("2275402", "s1", "other:tpt_individuals_provided", "20 Lakh", "persons",
        "people given TB preventive treatment", period="since december 2024",
        notes=("start stated as December 2024 (no day)",))
    add("2275402", "s1", "other:nikshay_mitras_registered", "5.7 lakh", "persons", "new Nikshay Mitras",
        period="since december 2024", notes=("start stated as December 2024 (no day)",))
    add("2275402", "s2", "other:ayushman_arogya_shivirs_held", "1.7 lakh", "", "Ayushman Arogya Shivirs have been held",
        notes=(NOUNIT.format("camps"),))
    add("2275402", "s2", "other:high_risk_villages_wards", "1.20 lakh", "",
        "high-risk villages, wards and congregate settings", notes=(NOUNIT.format("villages and wards"),))
    add("2275402", "s3", "other:students_participating", "32 lakh", "persons", "youth from schools and colleges")
    add("2275402", "s3", "other:my_bharat_volunteers_participating", "1.9 lakh", "persons", "My Bharat volunteers")
    add("2275402", "s4", "other:xray_screening_fold_increase", "34", "", "X-ray screening has increased 34-fold",
        notes=("printed '34-fold'; the number is entered", "no unit of the §5.2 vocabulary applies (a ratio of counts)"))
    add("2189415", "s1", "screened", "19 crore", "persons", "screening over 19 crore vulnerable individuals for TB")
    add("2189415", "s1", "tb_cases", "24.5 lakh", "cases", "detection of over 24.5 lakh TB patients")
    add("2189415", "s1", "other:asymptomatic_tb_cases", "8.61 lakh", "cases", "asymptomatic TB cases")
    add("2189415", "s2", "other:treatment_success_rate", "90%", "percent", "Treatment success rate")
    add("2112158", "s1", "districts_selected", "455", "districts", "455 selected high priority districts",
        notes=("the campaign's district count as printed by this release (347 at launch in other "
               "documents)",))
    add("2081379", "s1", "districts_selected", "347", "districts", "347 districts")
    add("2081379", "s1", "other:states_uts_selected", "33", "", "States and Union Territories",
        notes=(NOUNIT.format("States/UTs"),))
    add("dghsntep", "s1", "tb_cases", "3 lakh", "cases", "diagnosis of an additional ~3 lakh TB cases",
        period="since its inception")

    # ---- highlight bullets (the figure's own prose unit, kept as printed; coordinator ruling)
    HB = ("highlight bullet, entered as printed (a bullet is the figure's own prose unit)",)
    add("2085802", "b1", "other:parliamentarians_present", "250", "persons",
        "Members of Parliament were present at the event", notes=HB)
    add("2090668", "b1", "screened", "2 crore", "persons", "people screened",
        period="first 30 days", notes=HB)
    add("2090668", "b1", "tb_cases", "1.48 lakh", "cases", "new TB cases identified",
        period="first 30 days", notes=HB)
    add("2105575", "b1", "tb_cases", "5.1 lakh", "cases", "TB patients notified", notes=HB)
    add("2105575", "b1", "districts_selected", "455", "districts", "455 campaign districts", notes=HB)
    add("2105575", "b1", "tb_cases", "3.57 lakh", "cases", "diagnosed over 3.57 lakh TB patients",
        notes=HB + ("the body sentence prints over 3.5 lakh for the same count",))
    add("2105575", "b2", "screened", "10 crore", "persons", "vulnerable population screened", notes=HB)
    add("2105575", "b2", "other:nikshay_shivirs_conducted", "10 lakh", "", "Ni-kshay Shivirs",
        notes=HB + (NOUNIT.format("camps"),))
    add("2114554", "b1", "other:nikshay_shivirs_conducted", "13.46 lakh", "",
        "Nikshay Shivirs, or community screening and awareness camps were organised",
        notes=HB + (NOUNIT.format("camps"),))
    add("2114554", "b2", "screened", "12.97 crore", "persons", "people were screened for TB", notes=HB)
    add("2114554", "b2", "tb_cases", "7.19 lakh", "cases", "TB patients notified", notes=HB)
    add("2114554", "b3", "other:asymptomatic_tb_cases", "2.85 lakh", "cases", "asymptomatic", notes=HB)
    add("2244703", "b1", "other:high_risk_villages_wards", "1.58 Lakh", "", "Villages and Urban Wards",
        notes=HB + (NOUNIT.format("villages and wards"),))
    add("2244703", "b2", "screened", "20 Crore", "persons", "Screened", notes=HB)
    add("2244703", "b2", "tb_cases", "32.65 Lakh", "cases", "TB Cases Detected", notes=HB)
    add("2244703", "b2", "other:asymptomatic_tb_cases", "10.9 Lakh", "cases", "Asymptomatic Patients", notes=HB)
    for q, p, u, d in (("screened", "28.83 lakh", "persons", "screened 28.83 lakh people"),
                       ("tested", "21.67 lakh", "tests", "chest X-rays"),
                       ("tested", "3.65 lakh", "tests", "molecular tests"),
                       ("tb_cases", "1.75 lakh", "cases", "notified 1.75 lakh TB patients")):
        add("2279976", "b1", q, p, u, d, geography="Delhi", notes=HB)
    add("2335615", "b1", "screened", "25 Crore", "persons", "People", notes=HB)
    add("2335615", "b1", "tested", "11 Crore", "tests", "Chest X-Rays", notes=HB)
    add("2335615", "b1", "tested", "3 Crore", "tests", "Molecular Tests Conducted", notes=HB)
    add("2335615", "b2", "tb_cases", "48.64 Lakh", "cases", "TB Cases Detected", notes=HB)
    add("2335615", "b2", "other:asymptomatic_tb_cases", "14.97 Lakh", "cases", "Asymptomatic Cases", notes=HB)
    add("2199422", "b1", "other:extra_yield_over_conventional", "12-16%", "percent",
        "additional case yield", notes=HB + ("printed as a range, value left blank",))
    add("2199422", "b1", "screened", "1.62 lakh", "persons", "screen over 1.62 lakh individuals",
        period="since march 2023", notes=HB + ("start stated as March 2023 (no day)",))
    sd = dict(period="since december 2024",
              notes=HB + ("start stated as December 2024 (no day)",))
    add("2275402", "b1", "screened", "28 Crore", "persons", "Screened", **sd)
    add("2275402", "b1", "other:tpt_individuals_provided", "20 Lakh", "persons",
        "Given TB Preventive Treatment", **sd)
    add("2275402", "b1", "other:nikshay_mitras_registered", "5.7 Lakh", "persons", "New Nikshay Mitra", **sd)
    add("2275402", "b2", "other:xray_screening_fold_increase", "34", "", "X-ray screening has increased 34-fold",
        notes=HB + ("printed '34-fold'; the number is entered",
                    "no unit of the §5.2 vocabulary applies (a ratio of counts)"))
    sp = dict(wstart="2026-03-24", series="cumulative",
              notes=HB + ("start stated in the bullet ('Since 24th March, 2026')",))
    add("2275402", "b3", "other:ayushman_arogya_shivirs_held", "1.7 lakh", "", "Ayushman Arogya Shivirs Held",
        **{**sp, "notes": sp["notes"] + (NOUNIT.format("camps"),)})
    add("2275402", "b3", "other:high_risk_villages_wards", "1.2 Lakh", "",
        "High-Risk Villages, Wards and Congregate Settings",
        **{**sp, "notes": sp["notes"] + (NOUNIT.format("villages and wards"),)})
    add("2189415", "b1", "other:treatment_success_rate", "90%", "percent", "Treatment success rate", notes=HB)
    add("2189415", "b2", "tb_cases", "24.5 lakh", "cases", "diagnosis of 24.5 lakh patients", notes=HB)
    add("2189415", "b2", "other:asymptomatic_tb_cases", "8.61 lakh", "cases", "asymptomatic TB cases", notes=HB)
    add("2081379", "b1", "districts_selected", "347", "districts", "347 districts", notes=HB)
    add("2081379", "b1", "other:states_uts_selected", "33", "", "States and UTs",
        notes=HB + (NOUNIT.format("States/UTs"),))


_build_specs()


# ============================================================ inventory rows

def _sentences() -> dict[tuple[str, str], dict]:
    out = {}
    for r in read_transcribed():
        if r["kind"] in ("sentence", "cell", "lead-in", "bullet"):
            out[(r["page_key"], r["locator"].split(";")[0])] = r
    return out


def _row(pages: dict, sents: dict, spec: tuple) -> dict:
    pk, sid, q, printed, unit, definition, kw = spec
    page, t = pages[pk], sents[(pk, spec[1])]
    pub = pub_iso(page["pub_date_printed"])
    geography = kw.get("geography", "India")
    if geography != "India":
        assert states.canonical(geography) == geography, geography
    notes = [f"read online {page['accessed_utc']} (URL, method and locator in "
             f"data/transcribed/online_pages.csv, {sid})"]
    if page["cited_by"]:
        notes.append("cited source (§5.3): " + page["cited_by"])
    if not pub:
        notes.append("bound unknown: no date printed on the page")
    notes.extend(kw.get("notes", ()))
    common = dict(doc=doc_key(pk), quantity=q, printed=printed, unit=unit,
                  definition=definition, source_file=page["url"], source_url=page["url"],
                  pub_date=pub, geography=geography, period=kw.get("period", ""),
                  wstart=kw.get("wstart", ""), wend=kw.get("wend", ""),
                  as_on=kw.get("as_on", ""), series=kw.get("series", "period"),
                  notes=tuple(notes))
    if t["kind"] == "cell":
        row = invrow.row(page=1, page_or_para=f"table 1 (no title), row '{t['row_label']}'",
                         col=t["column_heading"], rowlabel=t["row_label"],
                         table_id="AI-Led Initiatives", **common)
        qual = R.qualifier(t["text"], printed)
        row["qualifier"] = qual
        row["note"] = row["note"].replace(
            "no qualifier words in a cell, so exact",
            "qualifier read from the printed cell text (§6.1)")
        assert definition in t["row_label"] + " " + t["text"] + " " + t["column_heading"]
        return row
    m = re.search(r"(para|bullet) (\d+)", t["locator"])
    para, kind = int(m.group(2)), m.group(1)
    assert definition in t["text"], (pk, sid, definition)
    key = ""
    if sum(1 for x in SPECS if x[:3] == (pk, sid, q)) > 1:   # same quantity twice in a sentence
        key = ("s-" + "-".join(re.findall(r"[a-z0-9]+", t["text"].lower())[:6]) + "-"
               + invrow.slug(printed))
    return invrow.row(page=para, page_or_para=(f"para {para}; {sid}" if kind == "para"
                                    else f"bullet {para}; {sid} (highlight bullet)"),
                      sentence=t["text"],
                      key=key, **common)


def build_inventory() -> list[dict]:
    pages, sents = _pages(), _sentences()
    rows = [_row(pages, sents, s) for s in SPECS]
    check_ids(rows)
    return rows


check_ids = invrow.check_ids


def build() -> tuple[list[dict], list[dict]]:
    return build_inventory(), scope_decisions()


# ============================================================ scope decisions

SCOPE_RULE = (
    "Inventory scope of the web pages read online (§5.1, §5.3, §13 of 19 November 2026). "
    "Same rule as the campaign and press documents: (1) figures of the named quantities enter "
    "when the page gives them as figures of active case finding or of the campaign; "
    "(2) other campaign or ACF figures enter as `other:` (subsets, results, outputs, selection "
    "attributes, participation and inputs that the sentence names as campaign inputs); "
    "(3) national programme resources (machines, facilities, units) and targets enter only "
    "when the same sentence names the campaign (campaign, Abhiyan/Abhiyaan, 100 days) or "
    "active case finding as their user; (4) programme-wide figures not given as campaign or "
    "ACF figures, epidemiology, finance and the Ni-kshay Poshan and Ni-kshay Mitra schemes "
    "are not entered. The context is the figure's own sentence (a table cell: title | column "
    "heading | row label). A highlight bullet is the figure's own prose unit, so its figures "
    "are entered with the bullet text as printed, also where the body repeats them (a "
    "heading is not a sentence). Cited sources (§5.3) are the pages that an included "
    "page names as the source of a figure, by footnote or reference list; only their own "
    "in-scope figures enter, and their own references are not followed.")
R_BG = "epidemiology or treatment outcome of the national programme, not an ACF or campaign figure (rule 4)"
R_PW = "programme-wide figure not given as a campaign or ACF figure (rule 4)"
R_RES = ("national programme resource; the sentence does not name the campaign or active "
         "case finding (rule 3)")
R_SCH = "Ni-kshay Poshan Yojana or Ni-kshay Mitra scheme figure, not an ACF or campaign figure (rule 4)"
R_NONE = "no figure of a §5.1 quantity on the page that is a campaign or ACF figure"

# (page_key, figures, where, category, reason)
EXCLUSIONS: list[tuple] = [
    ("2081662", "17.7%; 237; 195; 21.4%; 28; 22", "para 3", "background", R_BG),
    ("2081662", "around 1.89 crore; 68.3 lakh; approximately 15 lakh", "2023 key achievements; TPT",
     "programme-wide", R_PW),
    ("2081662", "Rs. 2,781 crores; 1 crore; 1.5 lakh", "Financial Support and Community Engagement",
     "scheme", R_SCH),
    ("2081662", "notification chart '[1]'", "chart before 'Post-COVID-19'", "unreadable",
     "a data chart printed as an image: no text to read; the same chart in the PDF version of "
     "the backgrounder is recorded under PIBBG"),
    ("2080069", "17.7%; 237; 195; 21.4%; 28; 22", "headline bullets and para 1", "background", R_BG),
    ("2080069", "18,05,670; 21,35,830; 24,22,121; 25,52,257; 21,69,438; 18.05 Lakh; 25.52 Lakh", "table 'TB cases Notified' "
     "2020-2024*, 'as on 19th Nov 2024'", "programme-wide",
     "national notifications of a Rajya Sabha answer, not given as campaign or ACF figures (rule 4)"),
    ("2085802", "1.75 lakh", "Ayushman Arogya Mandirs", "resource", R_RES),
    ("2085802", "28% to 22%; 32%", "para 5", "background", R_BG),
    ("2090668", "156", "ESIC hospitals have started screening", "resource", R_RES),
    ("2090668", "17.7%; 53% to 85%; 21.4%; 28 to 22 lakhs", "para 3", "background", R_BG),
    ("2105575", "over 26 lakh; over 36%", "highlight bullet 5 and the body sentence 'In 2024, India notified over 26 lakh TB patients'",
     "programme-wide", "national notifications in 2024, not given as campaign figures (rule 4)"),
    ("2114205", "none", "whole page", "no figure", "the President's message prints no figure"),
    ("2114549", "17.7%; 237; 195; 28; 22; 15 lakh; 2.5 lakh; 83%; 68%; 75%; 80%", "NTEP achievements, "
     "missing cases, DR-TB", "background", R_BG),
    ("2114549", "25.5 lakh; 26.07 lakh; 560", "key achievements table", "programme-wide", R_PW),
    ("2114549", "Rs 500; 1,000; 3,000 to 6,000; 12 lakh; 3,202 crores; 1.13 crore; 1,040 crores; "
     "1.51 crore; 1.18 crore; 2.59 lakh", "Ni-kshay Poshan Yojana and Ni-kshay Mitra sections",
     "scheme", R_SCH),
    ("2114554", "59% to 85%; 32 tests in one go", "treatment coverage; ICMR kits", "background",
     R_BG),
    ("2115334", "none", "whole page (Gujarati)", "no figure",
     "no figure: the Prime Minister's message of thanks. The provisional row of §5.3 (PRID 2115334) "
     "is resolved here: an official PIB release dated 26 March 2025, but it reports no figure of a "
     "§5.1 quantity, so it is excluded (§5.3)"),
    ("2128490", "18%; 237; 195; 21%; 28; 22; 85%", "WHO Global TB Report paragraph", "background", R_BG),
    ("2128490", "8,540; 87; 26,700; 500; 1,000", "infrastructure paragraph", "resource", R_RES),
    ("2128490", "1.28 crore; 29.4 lakh; 2.55 lakh; Rs 1,000", "Ni-kshay Poshan and Mitra paragraph",
     "scheme", R_SCH),
    ("2198389", "21%; 90%; 88%", "paras 2-3", "background", R_BG),
    ("2198999", "21%; 90%", "para 4", "background", R_BG),
    ("2200559", "21%; 90%", "para 3", "background", R_BG),
    ("2203004", "21%; 237; 187; 53%; 92%", "paras 1-2", "background", R_BG),
    ("note157923", "21%; 28%; 88%", "Key Takeaways; Introduction; 100-Day section", "background", R_BG),
    ("note157923", "Rs. 1,000; Rs.4,454.68 crores; 1.38 crore; 6,77,541; 45 lakh; over 2 lakh",
     "Nikshay Poshan Yojana and Ni-kshay Mitra", "scheme", R_SCH),
    ("note157923", "1,84,726; more than 9800; 107; over 500; 1,500; more than 15,000",
     "Ayushman Arogya Mandirs; Technological Infrastructure; BPaLM", "resource", R_RES),
    ("note157923", "27%; 8 State/UTs", "table 'AI-Led Initiatives', rows TB Management and TB Triage",
     "other", "treatment-outcome and deployment figures, not ACF figures"),
    ("2244661", "same exclusions as press note 157923 (identical text)", "whole page", "background",
     "the page has the same text as the press note: " + R_BG + "; " + R_SCH + "; " + R_RES),
    ("2244703", "21%; 25%; 92%; over 10 lakhs to less than one lakh; nearly 50%; 20 months to six",
     "paras 5-9", "background", R_BG),
    ("2244703", "Rs 640 crore; Rs 6,356 crore; Rs 4,590 crore; 1.39 crore; 7.16 lakh", "funding; "
     "Nikshay Poshan Yojana and Ni-kshay Mitra", "scheme", R_SCH),
    ("2244703", "over 24-line ministries; over 30,000 elected representatives; 7.16 lakh Ni-kshay "
     "Mitras", "para on the national movement", "participation",
     "the sentence describes the national movement, not the campaign (rule 3: it does not name the "
     "campaign)"),
    ("2244703", "over 3,000; 9,800+; 1.8 lakh", "handheld X-ray units, NAAT laboratories, Ayushman "
     "Arogya Mandirs", "resource", R_RES),
    ("note157923", "over 30,000 elected representatives; 24-line ministries",
     "para 52, 'The Jan Andolan also led to active involvement of ...'", "participation",
     "the sentence does not name the campaign or active case finding, so the same-sentence rule (rule 3) does not admit it; the page-level campaign context is not used"),
    ("2244661", "over 30,000 elected representatives; 24-line ministries",
     "para 52, 'The Jan Andolan also led to active involvement of ...'", "participation",
     "the sentence does not name the campaign or active case finding, so the same-sentence rule (rule 3) does not admit it; the page-level campaign context is not used"),
    ("2322820", "over 30,000 elected representatives; 24 line ministries",
     "para 52, 'The Jan Andolan also led to active involvement of ...'", "participation",
     "the sentence does not name the campaign or active case finding, so the same-sentence rule (rule 3) does not admit it; the page-level campaign context is not used"),
    ("note157923", "46,118", "Key Takeaways item 'Over 46,118 Gram Panchayats ...' and the sentence "
     "'As a result of all-round targeted and collaborative efforts, ...'", "programme-wide",
     "TB-free certification of Gram Panchayats: neither sentence names the campaign or active case "
     "finding (rule 3)"),
    ("2244661", "46,118", "Key Takeaways item 'Over 46,118 Gram Panchayats ...' and the sentence "
     "'As a result of all-round targeted and collaborative efforts, ...'", "programme-wide",
     "TB-free certification of Gram Panchayats: neither sentence names the campaign or active case "
     "finding (rule 3)"),
    ("2335615", "67933", "'With these efforts, 67933 Panchayats have been declared TB Free in 2025.'",
     "programme-wide", "TB-free certification of Panchayats: the sentence names neither the campaign "
     "nor active case finding (rule 3)"),
    ("2275402", "1.9 Lakh", "highlight bullet 8 'More Than 1.9 Lakh MY Bharat Volunteers Join ...'",
     "participation", "the sentence does not name the campaign or active case finding, so the same-sentence rule (rule 3) does not admit it; the page-level campaign context is not used"),
    ("2279976", "30", "'more than 30 region-specific indicators'", "method parameter",
     "a parameter of the vulnerability-mapping method, not a campaign figure"),
    ("2291403", "21%; 12%; 92%; 78%", "para 5", "background", R_BG),
    ("2291403", "more than 9,000; nearly 3,000", "molecular machines, AI X-ray units", "resource", R_RES),
    ("2291403", "over 5 lakh Ni-kshay Mitras; Rs 1,000", "patient-centric initiatives", "scheme", R_SCH),
    ("2297901", "21%; 92%", "para 5", "background", R_BG),
    ("2322820", "21%; 12%; 92%; 78%; 28%", "summary and Introduction", "background", R_BG),
    ("2322820", "34-fold increase in X-ray screening", "summary para and 'Technological "
     "Infrastructure' bullet", "resource",
     "the sentences do not name the campaign or active case finding (rule 3)"),
    ("2322820", "11 states; 55 districts; five NCC cadets; five MY Bharat volunteers",
     "JOSH campaign", "other campaign",
     "the JOSH social-media awareness pilot is not the TB Mukt Bharat Abhiyaan or ACF (judgement)"),
    ("2322820", "Rs.4,454.68 crores; 1.38 crore; 6,77,541; 45 lakh; over 2 lakh; 1800-11-6666",
     "Nikshay Poshan Yojana; Ni-kshay Mitra; helpline", "scheme", R_SCH),
    ("2322820", "1,87,250; more than 9800; 107; over 500; 1,500; more than 15,000", "Ayushman Arogya "
     "Mandirs; Technological Infrastructure; BPaLM", "resource", R_RES),
    ("2322820", "1.62+ Lakh; 12-16%", "table 'AI-Led Initiatives', row TB Screening",
     "unreadable heading",
     "the HTML splits the column heading over three cells ('&', 'Clinical Impact', '/ Operational'), "
     "so the cell's heading cannot be quoted as printed; the same cell is entered from press note "
     "157923, Backgrounder 2244661 and the cited release 2199422"),
    ("2335615", "38%; 35%; 94%; 96%; 28 to 18 per lakh", "headline and body", "background", R_BG),
    ("2335615", "five NCC cadets; five MY Bharat volunteers", "JOSH Teams", "other campaign",
     "JOSH awareness initiative, not the campaign or ACF (judgement)"),
    ("1990674", "5,91,491; 47,189; 12,774; 18,24,582", "Viksit Bharat Sankalp Yatra health camps",
     "other campaign",
     "TB screening at the health camps of the multi-disease Viksit Bharat Sankalp Yatra, which is "
     "not the TB Mukt Bharat Abhiyaan or active case finding (judgement)"),
    ("1990674", "14.41 lakhs; 10.15 lakhs; 10.14 lakhs; 26 State/UTs; 17; 23", "Achievements under "
     "PMTBMBA", "scheme", R_SCH),
    ("1990674", "64%; 24.2 lakh; 22.31 lakh; 58%; 7 times; 7.33 lakh; 30,864; 27,431; 39,186; 84%; "
     "85.5%; 86.3%; Rs 2617.44 Cr; 993 lakh; 13583; 24449; 6196; 127; 792", "items on notifications, "
     "private sector, DR-TB, treatment success, NPY, infrastructure", "programme-wide", R_PW),
    ("1990674", "1,527; 1,105; 422; 10.8 lakh; 5,463; 797; 788", "NACP, HIV and TB services in prisons",
     "programme-wide", "the sentence names neither the campaign nor active case finding (rules 3, 4)"),
    ("1990674", "1500; 2700; 8700; 58%; 67%", "ISHTH and IHC results", "other disease",
     "HIV and hepatitis results of the integrated campaigns, not a §5.1 quantity"),
    ("1887285", "55%; 10 lakhs; 2.4 lakhs; 25%; 18%; 18.41 lakhs; 6 times; 1.06 lakh; 6.65 lakhs; "
     "5.57 lakhs; 16338; 25960; 84%; 84.2%; Rs 1899 Cr; 71.93 lakhs; 61%; 4720",
     "notifications, private sector, DR-TB, success, NPY, infrastructure", "programme-wide", R_PW),
    ("1887285", "13.30 lakhs; 10.28 lakhs; 10.22 lakhs", "PMTBMBA achievements", "scheme", R_SCH),
    ("1887285", "1538; 5.50 lakh; 2200; 400", "NACP, HIV and TB services in prisons",
     "programme-wide", "the sentence names neither the campaign nor active case finding (rules 3, 4)"),
    ("1884180", "18%; 256; 210; 20%; 1.49 lakh; 1.19 lakh; 4761; 79; 96; 162; 614",
     "answer text", "background", R_BG + "; machines and laboratories are resources (rule 3)"),
    ("2081483", "26%; 312 per lakh", "prevalence and burden", "background", R_BG),
    ("ntep2454", "none", "whole page", "no figure",
     "a training chapter outline: headings only; its interactive (H5P) content blocks are not text"),
    ("itr2019", "none", "whole page", "no figure", "landing page of the report PDF (already read as a PDF)"),
    ("itr2022", "none", "whole page", "no figure", "landing page of the report PDF (already read as a PDF)"),
    ("2199422", "38; 11; 14,000; 7,100; 282 million", "MadhuNetrAI; eSanjeevani CDSS", "other disease",
     "figures of AI tools for diabetic retinopathy and tele-consultation, not TB"),
    ("2113683", "other figures", "rest of the answer", "background",
     "figures of other AI tools; only the Cough Against TB yield is a screening figure"),
    ("2275402", "187; 243; 21; 34", "para 3", "background", R_BG),
    ("2275402", "13,702", "radiographer posts", "resource", R_RES),
    ("2189415", "21%; 237; 187; 12%; 92%; 53%; 26.18 lakh; 27 lakh; 15 lakhs; 28; 21; ten-fold",
     "incidence, coverage, notifications, mortality, funding", "background", R_BG),
    ("2189415", "9391; 107; over 500; 1,500; 1.78 lakh", "laboratories, X-ray units, Ayushman "
     "Arogya Mandirs", "resource", R_RES),
    ("2189415", "Rs 4,406 crores; 1.37 crore; 6,77,541; 45 lakh; 2 lakh", "Nikshay Poshan Yojana and "
     "Ni-kshay Mitra", "scheme", R_SCH),
    ("2112158", "15 lakh; 2.5 lakhs; 25.5 lakh; 26.07 lakh; 17.7%; 237; 195; 21.4%; 53%; 85%; 32%; 68%; "
     "75%; 80%", "NTEP achievements", "background", R_BG),
    ("2112158", "32 tests; 3300; 86%; 96%; over 200; 1,200; 30", "innovations and the summit",
     "background", "technology and event figures, not campaign or ACF figures"),
    ("2112158", "Rs 500; Rs 1,000", "Ni-kshay Poshan Yojana", "scheme", R_SCH),
    ("2081379", "none besides 347; 33", "whole page", "no other figure", R_NONE),
    ("dghsntep", "1.6 lakh; 11.4 lakh; 11.5 lakh; 18 lakh; 24.2 lakh; 25.5 lakh; 7.33; 8.44 lakh; "
     "1.89 crore; 68.3 lakh; Rs 2781 crores; 560 of 645", "Mitras, notifications, tests, NPY, "
     "medical colleges", "programme-wide", R_PW + "; " + R_SCH),
    ("2062928", "Rs 500; Rs 1,000; BMI<18.5", "whole page", "scheme", R_SCH),
    ("2070942", "over 1.5 lakh Ni-kshay Mitras", "PMTBMBA paragraph", "scheme", R_SCH),
    ("2184456", "none", "whole page", "no figure", R_NONE),
    ("1808582", "none", "whole page", "no figure", R_NONE),
    ("concept", "none", "whole page", "no figure", "landing page that links the concept note PDF"),
    ("nsp", "none", "whole page", "no figure", "landing page that links the plan PDF"),
    ("wadhwani", "122,000+; 289,777; 37,802; 16 and 17 states", "page of the tool's developer",
     "non-official page",
     "a non-governmental page cited by footnote 1 of the PIB note for the description of the tool, "
     "not as the source of a figure; press and web pages enter only where official (PIB or a "
     "Ministry), §5.1"),
    ("dash", "none", "whole page", "no figure", "live ticker page: its visible text has labels only"),
]
UNAVAILABLE = {
    "mohfw217": "served as an empty application shell: no page text without scripts",
    "mohfw7783": "served as an empty application shell: no page text without scripts",
    "faq": "served as an empty application shell: no page text without scripts",
    "aam": "no HTTP response (connection failed)",
    "myscheme": "the served text is a generic error message; the scheme text needs scripts",
}


def scope_decisions() -> list[dict]:
    pages = _pages()
    rows = [{"kind": "rule", "doc": "web pages read online", "source_file": pages["2081662"]["url"],
             "page": "", "figures": "", "where": "", "category": "", "decision": "",
             "reason": SCOPE_RULE}]
    for pk, figs, where, cat, why in EXCLUSIONS:
        rows.append({"kind": "exclusion", "doc": doc_key(pk) if pk in
                     ("note157923", "dghsntep") or pk.isdigit() else pk,
                     "source_file": pages[pk]["url"], "page": "", "figures": figs,
                     "where": where, "category": cat,
                     "decision": "not entered" if figs != "none" else "no figure",
                     "reason": why})
    for pk, why in UNAVAILABLE.items():
        rows.append({"kind": "unavailable", "doc": pk, "source_file": pages[pk]["url"],
                     "page": "", "figures": "", "where": "whole page", "category": "unavailable",
                     "decision": "not read", "reason": why})
    return rows


def page_summary() -> list[dict]:
    """One dict per page: key, url, access time, method, availability, number of inventory
    rows, cited-by text (for the source-choice addendum)."""
    n: dict[str, int] = {}
    for s in SPECS:
        n[s[0]] = n.get(s[0], 0) + 1
    return [dict(page_key=k, url=p["url"], accessed_utc=p["accessed_utc"], method=p["method"],
                 availability=p["availability"], title=p["title"], n_rows=n.get(k, 0),
                 cited_by=p["cited_by"]) for k, p in _pages().items()]


# ============================================================ main

def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _merge_inventory(own: list[dict]) -> list[dict]:
    kept = []
    if INVENTORY.exists():
        with open(INVENTORY, newline="", encoding="utf-8") as f:
            kept = [r for r in csv.DictReader(f) if r["source_file"] not in OWN_FILES]
    return kept + own


def _merge_scope(own: list[dict]) -> list[dict]:
    """Other extractors' rows are kept; this module's rows (a source_file of one of its pages,
    or its rule row) replace its own earlier rows."""
    path = EXTRACTED / "inventory_scope_decisions.csv"
    kept = []
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            kept = [r for r in csv.DictReader(f)
                    if r["source_file"] not in OWN_FILES]
    return kept + own


def main() -> int:
    inv, scope = build()
    _write(INVENTORY, INVENTORY_COLUMNS, _merge_inventory(inv))
    _write(EXTRACTED / "inventory_scope_decisions.csv", SCOPE_COLUMNS, _merge_scope(scope))
    print(f"online pages: {len(_pages())} pages; inventory rows: {len(inv)}; "
          f"scope decisions: {len(scope)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
