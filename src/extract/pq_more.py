"""Part E: five further include = yes parliamentary answers supplied by the author,
entered as a dated addendum after the source-choice freeze and before any Q1-Q3
computation (§13, 19 November 2026).

- RS Unstarred Q. 278 (4 Feb 2025), "Campaign for equitable access to TB-related
  services"; RS Unstarred Q. 279 (4 Feb 2025), "100-day TB elimination campaign";
  RS Unstarred Q. 2051 (18 Mar 2025), "TB-Mukt Bharat Abhiyan": answer text only.
- LS Starred Q. 79 (7 Feb 2025), "TB Elimination Campaign": a Word file, read with
  zipfile and xml.etree (§11).
- RS Unstarred Q. 414 (6 Feb 2024), "Revised National TB Control Programme": State-wise,
  gender-wise and year-wise tables 2019-2023 (Annexures I and II) are extracted to
  data/extracted/ with their printed-total checks; Annexure III (finance) is not.

None is a Q4 source (§9.5), so no §9.6 check applies. The inventory scope rule is that
of the campaign and press documents and of the parliamentary answers (§5.1; rules 3-4 as
applied strictly: resources, targets and participation enter only when the same
sentence, or the lead-in sentence that a list item completes, names the campaign or
active case finding). Context is plan-literal (§13, 19 November 2026); as_on_basis is
"bounded" unless an as-on date is stated.

Run: python -I src/extract/pq_more.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache

import pdfplumber

from src import source_checks as sc
from src import states
from src.extract import annex, invrow, labels
from src.extract.cells import parse_int
from src.extract.pq import (CHECK_COLUMNS, SCOPE_COLUMNS, merge_by_source, write_csv)

ROOT = Path(__file__).resolve().parents[2]
EXTRACTED = ROOT / "data/extracted"
INVENTORY = ROOT / "data/figures_inventory.csv"
PQ = "data_raw/pq/"

# key -> (file, question as cited, answer date)
ANSWERS: dict[str, tuple[str, str, str]] = {
    "Q278": (PQ + "AU278_alnANG.pdf", "RS Unstarred Q. 278 (4 Feb 2025)", "2025-02-04"),
    "Q279": (PQ + "AU279_lXzMCu.pdf", "RS Unstarred Q. 279 (4 Feb 2025)", "2025-02-04"),
    "Q2051": (PQ + "AU2051_PXcr4v.pdf", "RS Unstarred Q. 2051 (18 Mar 2025)",
              "2025-03-18"),
    "Q414": (PQ + "AU414.pdf", "RS Unstarred Q. 414 (6 Feb 2024)", "2024-02-06"),
    "LSQ79": (PQ + "AS79_mh2ZZK.docx", "LS Starred Q. 79 (7 Feb 2025)", "2025-02-07"),
}
OWN_FILES = frozenset(f for f, _, _ in ANSWERS.values())
DOC = {"Q278": "RSQ278", "Q279": "RSQ279", "Q2051": "RSQ2051", "Q414": "RSQ414",
       "LSQ79": "LSQ79"}


# ================================================================== reading

@lru_cache(maxsize=None)
def pdf_text(file: str, page: int) -> str:
    with pdfplumber.open(ROOT / file) as pdf:
        return pdf.pages[page - 1].extract_text(x_tolerance=1) or ""


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@lru_cache(maxsize=None)
def docx_paragraphs(file: str) -> tuple[str, ...]:
    """Non-empty paragraphs of the document body, in order (tables: none here)."""
    with zipfile.ZipFile(ROOT / file) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out = []
    for p in root.find(_W + "body").iter(_W + "p"):
        t = "".join(x.text or "" for x in p.iter(_W + "t")).strip()
        if t:
            out.append(t)
    return tuple(out)


def _para_of(file: str, sentence: str) -> int:
    """1-based index of the body paragraph that holds the sentence."""
    paras = docx_paragraphs(file)
    hits = [k for k, p in enumerate(paras, start=1)
            if invrow.norm(sentence) in invrow.norm(p)]
    if len(hits) != 1:
        raise ValueError(f"sentence found in {len(hits)} paragraphs: {sentence!r}")
    return hits[0]


# ================================================================== prose figures

@dataclass(frozen=True)
class Prose:
    key: str
    page: int                 # PDF page; 0 for the Word file (paragraph located)
    quantity: str
    printed: str
    unit: str
    definition: str
    sentence: str
    where: str
    geography: str = "India"
    wstart: str = ""
    wend: str = ""
    series: str = "period"
    period: str = ""
    note: str = ""
    lead_in: str = ""         # the lead-in sentence a list item completes
    idkey: str = ""           # fig_id locator where the sentence is not unique


_SU = "unit (States/UTs) not in the §5.2 unit vocabulary"
_ACT = "unit ({}) not in the §5.2 unit vocabulary"
def _selection(key, page, s_main, where, **kw) -> list[Prose]:
    return [
        Prose(key, page, "districts_selected", "347", "districts", "priority districts",
              s_main, where, **kw),
        Prose(key, page, "other:states_uts_selected", "33", "", "States/UTs" if
              "States/UTs" in s_main else "State/UTs", s_main, where, note=_SU, **kw),
    ]


LAUNCH = ("Since the launch of the campaign on 7th December, 2024, as per available "
          "information, the details of communication activities and efforts made to "
          "educate the public, are as under:")


def _prose_specs() -> list[Prose]:
    P: list[Prose] = []
    s = ("To accelerate the progress to achieve Sustainable Development Goals towards TB, "
         "the government has identified 347 priority districts spread across 33 "
         "States/UTs for a “100 Days intensified Campaign” based on TB burden and "
         "mortality.")
    P += _selection("Q278", 1, s, "answer (a) to (c), paragraph 1")
    s = ("To accelerate the progress to achieve Sustainable Development Goals (SDGs) "
         "towards TB, the government has identified 347 priority districts spread across "
         "33 States/UTs for a “100 Days intensified TB Campaign” based on burden and "
         "mortality.")
    P += _selection("Q279", 1, s, "answer (a) to (f), paragraph 1")
    s = ("Further, the Government has launched a 100 days intensified TB Mukt Bharat "
         "Abhiyan in identified 347 priority districts across 33 State/UTs, to accelerate "
         "the endeavour to achieve Sustainable Development Goals related to TB, wherein "
         "Jan Bhaghidari activities are implemented with involvement of elected "
         "representatives, line ministries, schools, panchayati raj institutions, self "
         "help groups, anganwadis, local non-government organisations (NGOs) and civil "
         "society organizations to increase awareness on TB to combat stigma and to "
         "encourage early health seeking behaviour among the citizen.")
    P += _selection("Q2051", 2, s, "answer (b)")
    # ---------------- Lok Sabha Q. 79 (Statement)
    s = ("The Government has launched a 100 days intensified TB mukt bharat abhiyan in "
         "identified 347 priority districts across 33 State/UTs, including 8 districts of "
         "Himachal Pradesh, to accelerate the endeavour to achieve Sustainable "
         "Development Goals related to TB.")
    st = "Statement, (a) to (d)"
    P += _selection("LSQ79", 0, s, st)
    P.append(Prose("LSQ79", 0, "districts_selected", "8", "districts",
                   "districts of Himachal Pradesh", s, st, geography="Himachal Pradesh",
                   idkey="s-the-government-has-launched-a-100.himachal-pradesh"))
    s = "Out of the total campaign districts, 38 are tribal, 27 are mining and 46 are " \
        "aspirational districts."
    P += [Prose("LSQ79", 0, f"other:{n}_districts_selected", v, "districts", n, s, st)
          for n, v in (("tribal", "38"), ("mining", "27"), ("aspirational", "46"))]
    s = ("22 line departments have been sensitized to actively support implementation of "
         "campaign activities.")
    P.append(Prose("LSQ79", 0, "other:line_departments_sensitized", "22", "",
                   "line departments have been sensitized", s, st,
                   note=_ACT.format("departments") + "; participation whose sentence "
                        "names the campaign (rule 3)"))
    s = ("From the launch of the 100 days intensified TB elimination campaign in 347 "
         "districts, 4.94 lakh Ni-kshay shivirs have been held, 5.63 crore vulnerable "
         "individuals have been screened and 1.59 lakh new TB patients have been "
         "notified.")
    wl = dict(wstart="2024-12-07", series="cumulative",
              note="window start: the sentence counts 'From the launch of the 100 days "
                   "intensified TB elimination campaign'; the launch date is stated in "
                   "the next paragraph of the same Statement ('Since the launch of the "
                   "campaign on 7th December, 2024'); no end or as-on date is stated")
    P += [Prose("LSQ79", 0, "districts_selected", "347", "districts", "districts", s, st,
                **wl),
          Prose("LSQ79", 0, "other:nikshay_shivirs_conducted", "4.94 lakh", "",
                "Ni-kshay shivirs have been held", s, st,
                **(wl | {"note": wl["note"] + "; " + _ACT.format("camps")})),
          Prose("LSQ79", 0, "screened", "5.63 crore", "persons",
                "vulnerable individuals have been screened", s, st, **wl),
          Prose("LSQ79", 0, "tb_cases", "1.59 lakh", "cases",
                "new TB patients have been notified", s, st, **wl)]
    items = [
        ("110 MPs, 426 Members of Legislative Assembly (MLAs) and 27,949 Members of "
         "Legislative Councils (MLCs) and elected Panchayati Raj representatives have "
         "participated in the campaign.",
         [("other:mps_participating", "110", "persons", "MPs"),
          ("other:mlas_participating", "426", "persons",
           "Members of Legislative Assembly (MLAs)"),
          ("other:mlcs_and_pri_representatives_participating", "27,949", "persons",
           "Members of Legislative Councils (MLCs) and elected Panchayati Raj "
           "representatives")]),
        ("4,173 schools have conducted sensitization sessions with students and teachers.",
         [("other:schools_conducting_sensitization_sessions", "4,173", "",
           "schools have conducted sensitization sessions")]),
        ("12,402 awareness activities have been conducted with line Ministries and other "
         "Government Departments.",
         [("other:awareness_activities_line_ministries", "12,402", "",
           "awareness activities have been conducted with line Ministries and other "
           "Government Departments")]),
        ("13,972 activities were held with Public Sector Undertakings (PSUs), Trade "
         "Associations & Business Associations.",
         [("other:activities_psus_trade_business_associations", "13,972", "",
           "activities were held with Public Sector Undertakings (PSUs), Trade "
           "Associations & Business Associations")]),
        ("1,722 Continued Medical Education (CMEs) sessions were conducted for private "
         "health practitioners.",
         [("other:cme_sessions_private_practitioners", "1,722", "",
           "Continued Medical Education (CMEs) sessions")]),
        ("Screening & testing activities have been conducted in 17,956 congregate "
         "settings like prisons, mines, tea gardens, industries, orphanages, old age "
         "homes, etc.",
         [("other:congregate_settings_screening_testing", "17,956", "",
           "congregate settings")]),
        ("15,382 awareness activities were held by opinion leaders, community "
         "influencers, religious organizations and faith-based organizations",
         [("other:awareness_activities_opinion_leaders", "15,382", "",
           "awareness activities were held by opinion leaders, community influencers, "
           "religious organizations and faith-based organizations")]),
    ]
    li = ("list item completing the lead-in sentence '" + LAUNCH + "', which names the "
          "campaign (rule 3: a list item is read with the lead-in sentence that it "
          "completes); window start from that lead-in (ruling A17); no end or as-on "
          "date is stated")
    for sent, figs in items:
        for q, v, unit, d in figs:
            unit_note = "" if unit else "; " + _ACT.format("activities, sessions, "
                                                           "schools or settings")
            P.append(Prose("LSQ79", 0, q, v, unit, d, sent, st + ", list of "
                           "communication activities", wstart="2024-12-07",
                           series="cumulative", note=li + unit_note, lead_in=LAUNCH))
    return P


# ================================================================== Q414 tables

@dataclass(frozen=True)
class QCol:
    key: str
    index: int
    heading: str


@dataclass(frozen=True)
class QTable:
    key: str
    annex: str
    number: int
    pages: tuple[int, ...]
    title: str
    year: int
    columns: tuple[QCol, ...]
    notes: tuple[str, ...]

    @property
    def csv_name(self) -> str:
        return f"pq_q414_{self.annex.lower().replace('-', '')}_{self.year}.csv"

    def check_name(self, c: QCol) -> str:
        return (f"RS Unstarred Q. 414 (6 Feb 2024), {self.annex} table {self.number} "
                f"({self.year}): {c.heading}")


_A1_COLS = (QCol("presumptive_tb_tests", 0, "Presumptive TB tests*"),
            QCol("notified_female", 1, "TB notified: Female"),
            QCol("notified_male", 2, "TB notified: Male"),
            QCol("initiated_female", 3, "Initiated on treatment**: Female"),
            QCol("initiated_male", 4, "Initiated on treatment**: Male"),
            QCol("deaths_female", 5, "Deaths: Female"),
            QCol("deaths_male", 6, "Deaths: Male"))
_A1_NOTES = ("Data source: India TB Reports",
             "* Data collected from States/UTs in Excel sheets and compiled at CTD",
             "**The difference between notified and initiated on treatment may be due to "
             "(a) time lag between TB notification and treatment offered, and (b) death "
             "or discontinuity in availing treatment")


def _a2_cols(year: int) -> tuple[QCol, ...]:
    test = "No. of test done (Till September)" if year == 2023 else "No. of test done"
    return (QCol("tests_done", 0, test),
            QCol("drtb_diagnosed_male", 1, "DRTB patient diagnosed: Male"),
            QCol("drtb_diagnosed_female", 2, "DRTB patient diagnosed: Female"),
            QCol("initiated_male", 3, "Initiated on treatment: Male"),
            QCol("initiated_female", 4, "Initiated on treatment: Female"))


_A1_T = ("State/UT-wise, gender-wise and year-wise -TB tests, TB patients diagnosed, "
         "treatment initiated and deaths in {} (Jan-Dec)")
_A2_T = ("State/UT-wise, gender-wise and year-wise –tests conducted, diagnosed and "
         "treatment initiated for Drug Resistant TB in {} (Jan-Dec)")
Q414_TABLES: tuple[QTable, ...] = tuple(
    [QTable("Q414_A1", "Annexure-I", k + 1, pp, _A1_T.format(y), y, _A1_COLS, _A1_NOTES)
     for k, (y, pp) in enumerate(((2019, (2,)), (2020, (3, 4)), (2021, (4, 5)),
                                  (2022, (5, 6)), (2023, (6, 7))))]
    + [QTable("Q414_A2", "Annexure-II", k + 1, (p,), _A2_T.format(y), y, _a2_cols(y),
              ("Data Source : NAAT Laboratory reports and Ni-kshay",))
       for k, (y, p) in enumerate(((2019, 8), (2020, 9), (2021, 10), (2022, 11),
                                   (2023, 12)))])
Q414_FILE = ANSWERS["Q414"][0]
_TITLE_LINE = re.compile(r"^(\d)\. State/UT-wise")


def _segment(t: QTable) -> list[str]:
    """The lines of one table: from its numbered title to the next numbered title or the
    end of its pages."""
    lines = [ln for p in t.pages for ln in pdf_text(Q414_FILE, p).splitlines()]
    starts = [k for k, ln in enumerate(lines)
              if (m := _TITLE_LINE.match(ln)) and int(m.group(1)) == t.number]
    if len(starts) != 1:
        raise ValueError(f"{t.csv_name}: title found {len(starts)} times")
    seg = lines[starts[0]:]
    nxt = [k for k, ln in enumerate(seg[1:], start=1) if _TITLE_LINE.match(ln)]
    return seg[:nxt[0]] if nxt else seg


def _check_wording(t: QTable) -> str:
    text = "\n".join(pdf_text(Q414_FILE, p) for p in t.pages)
    pieces = [t.title, *t.notes] + [h for c in t.columns for h in c.heading.split(": ")]
    return invrow.verify_pieces(pieces, text)


Q414_COLUMNS = [
    "question", "table_id", "table_title", "source_file", "pdf_pages", "row_order",
    "label_printed", "canonical", "coarse_unit", "label_rule_step", "label_evidence",
    "is_total", "column", "column_heading", "value_printed", "value", "window_start",
    "window_end", "as_on", "as_on_basis", "answer_date", "note"]


def q414_rows(t: QTable) -> list[dict]:
    rows = annex.assemble_rows(_segment(t), len(t.columns), "India")
    out = []
    for k, r in enumerate(rows, start=1):
        if len(r.cells) != len(t.columns):
            raise ValueError(f"{t.csv_name} {r.label}: {len(r.cells)} cells")
        res = labels.resolve_or_list(r.label)
        for c in t.columns:
            cell = r.cells[c.index]
            out.append({
                "question": ANSWERS["Q414"][1],
                "table_id": f"{t.annex}, table {t.number}", "table_title": t.title,
                "source_file": Q414_FILE,
                "pdf_pages": ";".join(str(p) for p in t.pages), "row_order": k,
                "label_printed": r.label, "canonical": res.canonical,
                "coarse_unit": states.coarsen(res.canonical) if res.canonical else "",
                "label_rule_step": res.step, "label_evidence": res.evidence,
                "is_total": "no", "column": c.key, "column_heading": c.heading,
                "value_printed": cell.n or "",
                "value": "" if cell.n is None else parse_int(cell.n),
                "window_start": f"{t.year}-01-01",
                "window_end": f"{t.year}-09-30" if (t.year == 2023 and
                                                    c.key == "tests_done")
                else f"{t.year}-12-31",
                "as_on": "", "as_on_basis": invrow.as_on_basis(""),
                "answer_date": ANSWERS["Q414"][2],
                "note": ("window from the table title; the column heading reads '(Till "
                         "September)'" if (t.year == 2023 and c.key == "tests_done")
                         else "window from the table title")
                        + ("; blank cell, kept blank" if cell.n is None else "")})
    units = [r["canonical"] for r in out if r["column"] == t.columns[0].key]
    if len(set(units)) != len(units):
        raise ValueError(f"{t.csv_name}: a State/UT appears twice")
    return out


def q414_checks(t: QTable, rows: list[dict]) -> list[dict]:
    out = []
    for c in t.columns:
        vals = [int(r["value"]) for r in rows if r["column"] == c.key and r["value"] != ""]
        rec = sc.total_check(vals, None)
        out.append({"table": t.check_name(c), "source_file": Q414_FILE,
                    "page": ";".join(str(p) for p in t.pages), "rows": len(vals), **rec,
                    "note": rec["note"] + "; the table prints no Total or India row "
                                          "(text layer and page image)"})
    return out


# ================================================================== inventory

def _manifest() -> dict[str, dict]:
    sys.path.insert(0, str(ROOT))
    from tools.fetch_sources import read_manifest
    return {r["file"]: r for r in read_manifest()}


def verify_inputs() -> None:
    sys.path.insert(0, str(ROOT))
    from tools.fetch_sources import verify
    man = _manifest()
    for f in sorted(OWN_FILES):
        verify(ROOT / f, man[f]["sha256"])


def build_inventory() -> tuple[list[dict], list[dict]]:
    man = _manifest()
    rows, prov = [], []
    for s in _prose_specs():
        file, _, date = ANSWERS[s.key]
        if file.endswith(".docx"):
            para = _para_of(file, s.sentence)
            loc = f"Statement paragraph {para}; {s.where}"
            text = "\n".join(docx_paragraphs(file))
            page = para
            if s.lead_in:
                _para_of(file, s.lead_in)
        else:
            loc = f"PDF page {s.page}; {s.where}"
            text = pdf_text(file, s.page)
            page = s.page
        inv = invrow.row(
            doc=DOC[s.key], page=page, quantity=s.quantity, printed=s.printed,
            unit=s.unit, definition=s.definition, source_file=file,
            source_url=man[file]["url"], page_or_para=loc, pub_date=date,
            sentence=s.sentence, geography=s.geography, period=s.period,
            wstart=s.wstart, wend=s.wend, series=s.series, notes=(s.note,), key=s.idkey)
        if s.definition not in s.sentence:
            raise ValueError(f"definition not in its sentence: {s.definition!r}")
        rows.append(inv)
        prov.append({"kind": "figure", "fig_id": inv["fig_id"], "source_file": file,
                     "page": page, "method": invrow.verify([s.sentence], s.printed, text),
                     "figures_found": ""})
    invrow.check_ids(rows)
    return rows, prov


SCOPE_RULE_E = (
    "Inventory scope of the five further parliamentary answers (Part E; §5.1, §5.3, §7.4, "
    "§13 of 19 November 2026). Same rules as the campaign documents and the parliamentary "
    "answers: cascade and selection figures of the campaign or of ACF enter when their own "
    "sentence names the campaign or ACF (§5.1; rules 1-2; the same-sentence rule applies "
    "strictly, controller ruling of 19 November 2026); resources, targets and participation enter only when their own sentence, or "
    "the lead-in sentence that a list item completes, names the campaign or active case "
    "finding (rule 3); programme-wide figures, epidemiology, finance and the Ni-kshay "
    "Poshan and Ni-kshay Mitra schemes do not enter (rule 4). State tables of "
    "programme-wide tests, notifications, treatment and deaths (Q414) are outcome-type "
    "data: they enter data/extracted only, because they are neither ACF nor campaign "
    "figures and §7.4 does not name them (SRC-04).")

SCOPE_EXCLUSIONS: list[tuple[str, int | str, str, str, str, str]] = [
    ("Q278", 1, "100", "“100 Days intensified Campaign” (campaign name)", "name",
     "the campaign's name, not a count of a §5.1 quantity"),
    ("Q279", 1, "100", "“100 Days intensified TB Campaign” (campaign name)", "name",
     "the campaign's name, not a count of a §5.1 quantity"),
    ("Q279", 2, "17.7%; 237; 195; 8.3%; 21.4%; 28; 22", "answer, Global TB Report 2024",
     "background", "epidemiology (rule 4)"),
    ("Q279", 2, "Rs 1000/-", "answer, Ni-kshay Poshan Yojana", "scheme",
     "benefit norm of the Ni-kshay Poshan Yojana (rule 4)"),
    ("Q278", 1, "38; 27; 46", "answer (a) to (c), 'This includes 38 tribal districts, "
     "27 mining districts and 46 aspirational districts.'", "composition",
     "the sentence names no campaign: 'This' refers back to the preceding sentence, and "
     "the same-sentence rule applies strictly (controller ruling, 19 November 2026); "
     "the same composition figures are entered from CTD 100 Days Campaign, the Guidance "
     "Document and LS Q. 79, whose sentences name the campaign districts"),
    ("Q2051", 1, "826", "answer (a), Drug Resistant TB treatment centres", "resource",
     "programme resource; the sentence does not name the campaign or ACF (rule 3)"),
    ("Q2051", 2, "100", "answer (b), '100 days intensified TB Mukt Bharat Abhiyan'",
     "name", "the campaign's name, not a count of a §5.1 quantity"),
    ("LSQ79", "", "100 (three times)", "Statement, '100 days intensified ...'", "name",
     "the campaign's name, not a count of a §5.1 quantity"),
    ("LSQ79", "", "86,748; 1.12 lakh", "Statement, 'Further, 86,748 new Ni-kshay Mitras "
     "have been registered and 1.12 lakh food baskets have been disbursed ...'",
     "scheme / participation", "the sentence names neither the campaign nor active case "
     "finding (same-sentence rule 3), and the figures are of the Ni-kshay Mitra scheme "
     "(rule 4); the preceding sentence's campaign context is not used"),
    ("LSQ79", "", "7th December, 2024", "Statement, lead-in of the activity list", "date",
     "a date, used as the window start of the list items"),
    ("Q414", 1, "2019-2023; 2012-13 to 2023-24", "answer (a)-(d)", "years",
     "periods, not figures"),
    ("Q414", "2-7", "all cells (5 tables, 2019-2023)", "Annexure-I: presumptive TB tests, "
     "TB notified, initiated on treatment and deaths, by State, sex and year",
     "data/extracted only", "programme-wide State tables, not ACF or campaign figures and "
     "not named in §7.4 (§5.1; SRC-04); extracted to data/extracted/pq_q414_annexurei_"
     "<year>.csv with printed-total checks"),
    ("Q414", "8-12", "all cells (5 tables, 2019-2023)", "Annexure-II: drug-resistant TB "
     "tests, diagnosed and initiated on treatment, by State, sex and year",
     "data/extracted only", "programme-wide State tables, not ACF or campaign figures "
     "(§5.1; SRC-04); extracted to data/extracted/pq_q414_annexureii_<year>.csv"),
    ("Q414", "13-17", "all cells", "Annexure-III: allocation, releases and utilisation "
     "2012-13 to 2023-24", "finance", "not a §5.1 quantity (rule 4); not extracted"),
]


def scope_decisions() -> list[dict]:
    out = [{"kind": "rule", "doc": "parliamentary answers, Part E",
            "source_file": "data_raw/pq/ (Part E)", "page": "", "figures": "",
            "where": "", "category": "", "decision": "", "reason": SCOPE_RULE_E}]
    for key, p, figs, where, cat, why in SCOPE_EXCLUSIONS:
        out.append({"kind": "exclusion", "doc": key, "source_file": ANSWERS[key][0],
                    "page": p, "figures": figs, "where": where, "category": cat,
                    "decision": "extracted, not in the inventory"
                    if cat == "data/extracted only" else "not entered", "reason": why})
    return out


# ================================================================== main

def main() -> int:
    from src.extract.campaign import INVENTORY_COLUMNS
    verify_inputs()
    checks = []
    for t in Q414_TABLES:
        _check_wording(t)
        rows = q414_rows(t)
        write_csv(EXTRACTED / t.csv_name, Q414_COLUMNS, rows)
        checks += q414_checks(t, rows)
    path = EXTRACTED / "table_total_checks.csv"
    write_csv(path, CHECK_COLUMNS, merge_by_source(path, checks, {Q414_FILE},
                                                   CHECK_COLUMNS))
    inv, prov = build_inventory()
    write_csv(INVENTORY, INVENTORY_COLUMNS,
              merge_by_source(INVENTORY, inv, set(OWN_FILES), INVENTORY_COLUMNS))
    write_csv(EXTRACTED / "pq_more_inventory_provenance.csv",
              ["kind", "fig_id", "source_file", "page", "method", "figures_found"], prov)
    sp = EXTRACTED / "inventory_scope_decisions.csv"
    own = scope_decisions()
    write_csv(sp, SCOPE_COLUMNS,
              merge_by_source(sp, own, {r["source_file"] for r in own}, SCOPE_COLUMNS))
    print(f"Part E inventory rows: {len(inv)}; Q414 tables: {len(Q414_TABLES)}; "
          f"total checks: {len(checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
