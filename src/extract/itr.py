"""India TB Reports: annual State notifications (analysis plan §3.2, §9.6) and active
case finding (ACF) figures (§3.1.1, §5, §8).

Tables (each read from the hashed copy; pages located from each edition's list of
annexures; every table checked against its printed national row):

- Q4 trend sources (§9.6): the State-wise "TB patients notified ... Total" columns of
  the India TB Report 2020 (Annexure 1.2, data year 2019), 2023 (Annexure 1.2, 2022) and
  2024 (Annexure 1.2, 2023; fallback trend point 2023, S8(b), §7.4 cross-checks).
- Q3 tables (§8): the State-wise "Active Case Finding" annexures of the 2019, 2020,
  2022, 2023 and 2024 editions (data years 2018, 2019, 2021, 2022, 2023).

The inventory (§5.1) takes every cell of the ACF annexures, the ACF figures of the text
(chapter, executive summary, messages, boxes) and, because §7.4 enters and classifies
them, the State notification counts of the 2024 edition. The 2020 and 2023 notification
annexures are outcome data only (data/extracted): they are not ACF or campaign figures
and §7.4 does not name them (§5.1; inventory scope rule of the campaign documents, 4).

Text layers: the 2023 edition prints many text pages as images (no text layer); those
pages were rendered and read, and recognised by OCR only to find ACF passages. Figures
read from a page image are marked so in the provenance.

Run: python -I src/extract/itr.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import re
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache

from src import source_checks as sc
from src import states
from src.extract import annex, invrow, labels, pdftext
from src.extract.cells import parse_int
from src.extract.pq import (CHECK_COLUMNS, SCOPE_COLUMNS, merge_by_source, write_csv)

ROOT = Path(__file__).resolve().parents[2]
EXTRACTED = ROOT / "data/extracted"
INVENTORY = ROOT / "data/figures_inventory.csv"

# edition -> (file, data year, pub_date, note on the date)
EDITIONS: dict[str, tuple[str, int, str, str]] = {
    "ITR2019": ("data_raw/official/India-TB-Report-2019.pdf", 2018, "2019-05-13",
                "pub_date: no publication date printed; the Additional Secretary's "
                "message (PDF page 9) is dated 13 May 2019"),
    "ITR2020": ("data_raw/india_tb_report/ITR2020.pdf", 2019, "2020-03-13",
                "pub_date: no publication date printed; the message on PDF page 11 is "
                "dated 13 March 2020"),
    "ITR2022": ("data_raw/official/TBAnnaulReport2022.pdf", 2021, "",
                "no publication date printed in the document"),
    "ITR2023": ("data_raw/india_tb_report/ITR2023.pdf", 2022, "2023-03-20",
                "pub_date: no publication date printed; the Joint Secretary's message "
                "(PDF page 13) is dated 20 March 2023"),
    "ITR2024": ("data_raw/india_tb_report/ITR2024.pdf", 2023, "2024-03-19",
                "pub_date: no publication date printed; the message on PDF page 7 is "
                "dated 19 March 2024"),
}
OWN_FILES = frozenset(f for f, _, _, _ in EDITIONS.values())
YEAR_BASIS = ("the edition's data year as fixed in the analysis plan (§3.1.1, §3.2, "
              "§9.6); the table states no year")


@dataclass(frozen=True)
class Col:
    key: str
    index: int
    heading: str            # verbatim heading (levels joined by ": ")
    definition: str
    quantity: str
    unit: str
    kind: str = "count"     # count | lakhs (decimal, persons in lakhs)
    pct_quantity: str = ""  # quantity of the "(pct)" printed with the count
    pct_definition: str = ""
    needed: bool = False    # a needed Q4 column (§9.6)
    inventory: bool = True


@dataclass(frozen=True)
class Table:
    key: str
    edition: str
    pages: tuple[int, ...]
    printed_pages: str
    title: str
    table_id: str
    ncells: int
    national: str
    columns: tuple[Col, ...]
    kind: str               # "notification" | "acf"
    source: str = ""        # source_checks constant for a Q4 source
    inventory: bool = True
    title_from_image: bool = False
    notes: tuple[str, ...] = ()       # notes printed with the table, verbatim
    window_stated: str = ""           # where the document states the table's window
    absent_note: str = ""
    q4_role: str = ""
    image_pieces: tuple[str, ...] = ()  # headings read from the page image only

    @property
    def file(self) -> str:
        return EDITIONS[self.edition][0]

    @property
    def csv_name(self) -> str:
        return f"{self.key.lower()}.csv"

    def check_name(self, col: Col) -> str:
        return f"India TB Report {self.edition[3:]}, {self.table_id}: {col.heading}"

    def count_columns(self) -> list[Col]:
        return [c for c in self.columns if c.kind == "count"]


def _notified(prefix: str, idx: tuple[int, int, int], needed_inventory: bool):
    return tuple(Col(f"notified_{s.lower()}", i, f"{prefix}: {s}", prefix, "tb_cases",
                     "cases", needed=(s == "Total"), inventory=needed_inventory)
                 for s, i in zip(("Public", "Private", "Total"), idx))


_PCT_SCR = "other:pct_mapped_population_screened"
TABLES: tuple[Table, ...] = (
    Table("ITR2020_A1_2", "ITR2020", (204,), "180",
          "1.2 TB Cases & Paediatric cases notification", "Annexure 1.2", 9, "India",
          _notified("TB patients notified", (0, 1, 2), False), "notification",
          source=sc.ITR2020, inventory=False,
          notes=("TB Patients Notification is based on notification by diagnosing PHI.",),
          q4_role="trend point 2019 (primary and fallback); placebo expected change"),
    Table("ITR2023_A1_2", "ITR2023", (213, 214), "183-184", "1.2 TB case notification",
          "Annexure 1.2", 9, "India",
          _notified("TB patients notified, n (% achievement against target)",
                    (3, 4, 5), False), "notification",
          source=sc.ITR2023, inventory=False, title_from_image=True,
          q4_role="trend point 2022 (primary and fallback); placebo 2022"),
    Table("ITR2024_A1_2", "ITR2024", (187, 188), "157-158", "1.2. TB case notification",
          "Annexure 1.2", 9, "INDIA",
          _notified("TB patients notified, n(% of achievement against target)",
                    (3, 4, 5), True), "notification",
          source=sc.ITR2024,
          notes=("TB patient's notification is based on notification by diagnosing "
                 "PHI.",),
          q4_role="fallback trend point 2023; fallback placebo 2023; S8(b) 2023 count; "
                  "Q2 cross-checks (§7.4)"),
    Table("ITR2019_A1_7_ACF", "ITR2019", (178,), "156", "1.7 Active Case Finding",
          "Annexure 1.7", 4, "India",
          (Col("target_population_mapped", 0, "Target population mapped",
               "Target population mapped", "population_targeted", "persons"),
           Col("screened", 1, "Persons screened out of the mapped population",
               "Persons screened out of the mapped population", "screened", "persons"),
           Col("tested", 2, "Presumptive TB cases tested out of the persons screened",
               "Presumptive TB cases tested out of the persons screened", "tested",
               "persons"),
           Col("diagnosed", 3, "Total TB patients diagnosed in the ACF activity among "
               "tested", "Total TB patients diagnosed in the ACF activity among tested",
               "tb_cases", "cases")),
          "acf",
          notes=("Madhya Pradesh has merged ACF activity with Nirogi Kaya Abhiyaan (A "
                 "State initiative to club TB Leprosy and NCD) in which house to house "
                 "survey were being conducted in 2 blocks of every district twice a "
                 "year.", "Manipur & Tripura has NOT conducted ACF activity"),
          absent_note="no row printed for Madhya Pradesh, Manipur and Tripura (the "
                      "table's notes say they did not report separate ACF figures)",
          image_pieces=("Presumptive TB cases tested out of the persons screened",)),
    Table("ITR2020_A6_ACF", "ITR2020", (255,), "231", "6 Active Case Finding",
          "Annexure 6", 5, "India",
          (Col("estimated_population_lakhs", 0, "Estimated Population (Lakhs)",
               "Estimated Population (Lakhs)", "other:estimated_population", "persons",
               kind="lakhs"),
           Col("population_mapped", 1, "Vulnerable Population Mapped (%)",
               "Vulnerable Population Mapped", "population_targeted", "persons",
               pct_quantity="other:pct_population_mapped_high_risk",
               pct_definition="Vulnerable Population Mapped (%)"),
           Col("screened", 2, "Population screened amongst mapped vulnerable "
               "population (%)", "Population screened amongst mapped vulnerable "
               "population", "screened", "persons", pct_quantity=_PCT_SCR,
               pct_definition="Population screened amongst mapped vulnerable "
                              "population (%)"),
           Col("tested", 3, "Presumptive TB cases tested out of those screened (%)",
               "Presumptive TB cases tested out of those screened", "tested", "persons",
               pct_quantity="other:pct_tested_among_screened",
               pct_definition="Presumptive TB cases tested out of those screened (%)"),
           Col("diagnosed", 4, "TB cases diagnosed among tested (%)",
               "TB cases diagnosed among tested", "tb_cases", "cases",
               pct_quantity="other:pct_diagnosed_among_tested",
               pct_definition="TB cases diagnosed among tested (%)")),
          "acf",
          notes=("The States/ UT of Chandigarh, Madhya Pradesh & Manipur have not "
                 "conducted separate ACF activity",),
          absent_note="no row printed for Chandigarh, Madhya Pradesh and Manipur"),
    Table("ITR2022_A6_ACF", "ITR2022", (131,), "237", "6 Active Case Finding",
          "Annexure 6", 5, "India",
          (Col("estimated_population_lakhs", 0, "Estimated Population (Lakhs)",
               "Estimated Population (Lakhs)", "other:estimated_population", "persons",
               kind="lakhs"),
           Col("population_mapped", 1, "Vulnerable Population Mapped (%)",
               "Vulnerable Population Mapped", "population_targeted", "persons",
               pct_quantity="other:pct_population_mapped_high_risk",
               pct_definition="Vulnerable Population Mapped (%)"),
           Col("screened", 2, "Population screened amongst mapped vulnerable "
               "population (%)", "Population screened amongst mapped vulnerable "
               "population", "screened", "persons", pct_quantity=_PCT_SCR,
               pct_definition="Population screened amongst mapped vulnerable "
                              "population (%)"),
           Col("tested", 3, "Presumptive TB cases tested out of those screened (%)",
               "Presumptive TB cases tested out of those screened", "tested", "persons",
               pct_quantity="other:pct_tested_among_screened",
               pct_definition="Presumptive TB cases tested out of those screened (%)"),
           Col("diagnosed", 4, "TB cases diagnosed among tested (%)",
               "TB cases diagnosed among tested", "tb_cases", "cases",
               pct_quantity="other:pct_diagnosed_among_tested",
               pct_definition="TB cases diagnosed among tested (%)")),
          "acf",
          window_stated="State wise details of ACF conducted in 2021 are provided in "
                        "Annexure."),
    Table("ITR2023_A6_ACF", "ITR2023", (299, 300), "269-270", "6 ACTIVE CASE FINDING",
          "Annexure 6", 3, "India",
          (Col("screened", 0, "Vulnerable individuals screened for symptoms",
               "Vulnerable individuals screened for symptoms", "screened", "persons"),
           Col("symptomatic_examined", 1, "TB symptomatic identified and examined, "
               "n (%)", "TB symptomatic identified and examined", "tested", "persons",
               pct_quantity="other:pct_examined_among_screened",
               pct_definition="TB symptomatic identified and examined, n (%)"),
           Col("diagnosed", 2, "TB patients diagnosed, n (%)", "TB patients diagnosed",
               "tb_cases", "cases", pct_quantity="other:pct_diagnosed_among_examined",
               pct_definition="TB patients diagnosed, n (%)")),
          "acf"),
    Table("ITR2024_A6_ACF", "ITR2024", (279,), "248", "6. Active case finding",
          "Annexure 6", 3, "INDIA",
          (Col("screened", 0, "Total population screened for presumptive TB",
               "Total population screened for presumptive TB", "screened", "persons"),
           Col("tested", 1, "Presumptive TB cases tested out of those screened, n(%)",
               "Presumptive TB cases tested out of those screened", "tested", "persons",
               pct_quantity="other:pct_tested_among_screened",
               pct_definition="Presumptive TB cases tested out of those screened, n(%)"),
           Col("diagnosed", 2, "TB cases diagnosed among tested, n(%)",
               "TB cases diagnosed among tested", "tb_cases", "cases",
               pct_quantity="other:pct_diagnosed_among_tested",
               pct_definition="TB cases diagnosed among tested, n(%)")),
          "acf"),
)


# ================================================================== reading

@lru_cache(maxsize=None)
def page_lines(file: str, page: int) -> tuple[str, ...]:
    return tuple(pdftext.page_lines(ROOT / file, page))


def page_text(file: str, page: int) -> str:
    t = "\n".join(page_lines(file, page))
    # the 2023 edition's text layer splits the "fi" ligature ("notif ied")
    return re.sub(r"(?<=[a-z])f (?=i[a-z])", "f", t)


@dataclass
class PRow:
    label: str
    page: int
    cells: list[annex.Cell]
    positioned: bool = False


def read_table(t: Table) -> list[PRow]:
    out: list[PRow] = []
    for p in t.pages:
        rows = annex.assemble_rows(list(page_lines(t.file, p)), t.ncells, t.national)
        full = [r.label for r in rows if len(r.cells) == t.ncells]
        for r in rows:
            cells, pos = r.cells, False
            if len(cells) != t.ncells:
                cells = annex.positioned_cells(ROOT / t.file, p, r.label, t.ncells, full)
                pos = True
            out.append(PRow(r.label, p, cells, pos))
    nat = [r for r in out if r.label == t.national]
    if len(nat) != 1:
        raise ValueError(f"{t.key}: {len(nat)} national rows")
    return out


def _value(cell: annex.Cell, col: Col) -> str:
    if cell.n is None:
        return ""
    if col.kind == "lakhs":
        v = Decimal(cell.n.replace(",", "")) * 100000
        if v != v.to_integral_value():
            raise ValueError(f"lakh value not whole in persons: {cell.n}")
        return str(int(v))
    return str(parse_int(cell.n))


def _pct(cell: annex.Cell) -> tuple[str, str]:
    """(printed percentage without parentheses, value); blank for '(NA)'."""
    if cell.pct is None:
        return "", ""
    s = cell.pct.strip("() ").strip()
    if s == "NA":
        return "", ""
    v = s.rstrip("%").strip()
    return s, str(Decimal(v))


EXTRACT_COLUMNS = [
    "table_key", "edition", "table_id", "table_title", "source_file", "pdf_page",
    "printed_page", "row_order", "label_printed", "canonical", "coarse_unit",
    "label_rule_step", "label_evidence", "is_total", "column", "column_heading",
    "value_printed", "value", "data_year", "window_start", "window_end", "window_basis",
    "as_on", "as_on_basis", "pub_date", "q4_role", "note"]


def extracted_rows(t: Table, rows: list[PRow] | None = None) -> list[dict]:
    rows = rows if rows is not None else read_table(t)
    year = EDITIONS[t.edition][1]
    basis = (f"stated in the report: '{t.window_stated}'" if t.window_stated
             else YEAR_BASIS)
    out = []
    for k, r in enumerate(rows, start=1):
        is_total = r.label == t.national
        res = None if is_total else labels.resolve_or_list(r.label)
        base = {"table_key": t.key, "edition": t.edition, "table_id": t.table_id,
                "table_title": t.title, "source_file": t.file, "pdf_page": r.page,
                "printed_page": t.printed_pages, "row_order": k,
                "label_printed": r.label,
                "canonical": "India" if is_total else res.canonical,
                "coarse_unit": "India" if is_total else (
                    states.coarsen(res.canonical) if res.canonical else ""),
                "label_rule_step": "" if is_total else res.step,
                "label_evidence": "" if is_total else res.evidence,
                "is_total": "yes" if is_total else "no", "data_year": year,
                "window_start": f"{year}-01-01", "window_end": f"{year}-12-31",
                "window_basis": basis, "as_on": "", "as_on_basis": "bounded",
                "pub_date": EDITIONS[t.edition][2], "q4_role": t.q4_role}
        for c in t.columns:
            cell = r.cells[c.index]
            note = []
            if r.positioned:
                note.append("the row prints fewer cells than the header; cells placed "
                            "by their x position on the page")
            if cell.n is None:
                note.append(f"printed '{cell.raw}': blank, kept blank")
            if c.kind == "lakhs":
                note.append("printed in lakhs (column heading); value in persons")
            out.append(base | {"column": c.key, "column_heading": c.heading,
                               "value_printed": cell.n or "", "value": _value(cell, c),
                               "note": "; ".join(note)})
            if c.pct_quantity:
                pp, pv = _pct(cell)
                out.append(base | {"column": c.key + "_pct",
                                   "column_heading": c.heading + " [percentage]",
                                   "value_printed": pp, "value": pv,
                                   "q4_role": "",
                                   "note": "" if pp else f"no percentage printed "
                                                         f"('{cell.raw}')"})
    return out


# ================================================================== checks

def _interval_check(vals: list[str], tot: str, printed: list[str], ptot: str) -> dict:
    """§6.2 check 3 for figures printed with a decimal (in lakhs): the parts' interval
    [Σlo − 1, Σhi + 1] must overlap the total's [T − h, T + h], h half a unit of the last
    printed digit, in persons."""
    def h(p: str) -> Decimal:
        d = len(p.split(".")[1]) if "." in p else 0
        return Decimal(100000) * Decimal(5) / (Decimal(10) ** (d + 1))
    lo = sum(Decimal(v) - h(p) for v, p in zip(vals, printed)) - 1
    hi = sum(Decimal(v) + h(p) for v, p in zip(vals, printed)) + 1
    T, hT = Decimal(tot), h(ptot)
    ok = not (hi < T - hT or lo > T + hT)
    s = sum(int(v) for v in vals)
    return {"sum_of_rows": s, "printed_total": int(T), "difference": s - int(T),
            "pass": "yes" if ok else "no",
            "note": "figures printed in lakhs with one decimal: interval rule of §6.2 "
                    "check 3 (half a unit of the last printed digit per figure, ±1)"}


def table_checks(t: Table, ext: list[dict]) -> list[dict]:
    out = []
    for c in t.columns:
        rows = [r for r in ext if r["column"] == c.key]
        states_ = [r for r in rows if r["is_total"] == "no"]
        vals = [r["value"] for r in states_ if r["value"] != ""]
        blanks = len(states_) - len(vals)
        tot = [r for r in rows if r["is_total"] == "yes"][0]
        if c.kind == "lakhs":
            rec = _interval_check(vals, tot["value"],
                                  [r["value_printed"] for r in states_
                                   if r["value"] != ""], tot["value_printed"])
        else:
            rec = sc.total_check([int(v) for v in vals],
                                 int(tot["value"]) if tot["value"] != "" else None)
            rec["note"] = "values kept exactly as printed"
        if blanks:
            rec["note"] += f"; {blanks} blank State cell(s) left out of the sum"
        if t.absent_note:
            rec["note"] += "; " + t.absent_note
        out.append({"table": t.check_name(c), "source_file": t.file,
                    "page": ";".join(str(p) for p in t.pages), "rows": len(states_),
                    **rec})
    return out


RECHECK: dict[str, str] = {
    "ITR2020_A1_2": (
        "Trend source. Notes printed with the table: 'TB Patients Notification is based "
        "on notification by diagnosing PHI.' (a whole-table note on the basis of "
        "counting, the same in every State; it changes no window, cut-off or source). "
        "No note on a row. The table title and the annexure list ('1.2 TB Cases & "
        "Paediatric cases notification', printed page 180) state no year; the year 2019 "
        "is the edition's data year fixed in §3.2 and §9.6. No as-on date is stated."),
    "ITR2023_A1_2": (
        "Trend source. No note is printed with the table on PDF pages 213-214 (text "
        "layer and page image); the title '1.2 TB CASE NOTIFICATION' is printed "
        "vertically and is read from the page image. The year 2022 is the edition's "
        "data year fixed in §3.2 and §9.6. No as-on date is stated."),
    "ITR2024_A1_2": (
        "Fallback trend source. Note printed with the table: 'TB patient's notification "
        "is based on notification by diagnosing PHI.' (whole-table basis of counting; "
        "changes no window, cut-off or source). No note on a row. The year 2023 is the "
        "edition's data year fixed in §3.2 and §9.6. No as-on date is stated."),
}


def q4_checks(exts: dict[str, list[dict]]) -> list[dict]:
    out = []
    for t in TABLES:
        if not t.source:
            continue
        ext = exts[t.key]
        cols, tots = {}, {}
        for c in t.columns:
            if not c.needed:
                continue
            rows = [r for r in ext if r["column"] == c.key]
            cols[c.key] = [int(r["value"]) if r["value"] != "" else None
                           for r in rows if r["is_total"] == "no"]
            tot = [r["value"] for r in rows if r["is_total"] == "yes"]
            tots[c.key] = int(tot[0]) if tot and tot[0] != "" else None
        rec = sc.q4_extraction_check(t.source, cols, tots, tuple(cols))
        out.append({**rec, "source_file": t.file,
                    "locator": f"{t.table_id}, PDF page(s) "
                               + ", ".join(str(p) for p in t.pages)
                               + f" (printed {t.printed_pages})",
                    "role": t.q4_role, "recheck_954": RECHECK[t.key]})
    return out


# ================================================================== prose figures

@dataclass(frozen=True)
class Prose:
    edition: str
    page: int
    quantity: str
    printed: str
    unit: str
    definition: str
    sentence: str
    where: str
    period: str = ""
    wstart: str = ""
    wend: str = ""
    geography: str = "India"
    image: bool = False
    occurrence: int = 1
    note: str = ""
    title: str = ""        # table cell: title | column | row
    col: str = ""
    row: str = ""


_VAN = "unit (vans) not in the §5.2 unit vocabulary"
_SU = "unit (States/UTs) not in the §5.2 unit vocabulary"
_A17 = ("window stated in the preceding sentence of the same paragraph ('{}'; ruling "
        "A17)")
_SEC = "the figure's section is headed '{}' (inventory scope rule of the reports, 1)"
_GHA = ("restatement of the findings of Shewade HD et al., Global Health Action 2023 "
        "(the study is not named in the sentence; the list item is headed 'Evaluation "
        "of active case finding')")


def _prose_specs() -> list[Prose]:
    P: list[Prose] = []
    # ---------------- India TB Report 2019 (data year 2018)
    s = ("With Active Case Finding, 14.4 crore vulnerable people were screened, "
         "resulting in reporting of an additional 49,733 cases.")
    P += [Prose("ITR2019", 9, "screened", "14.4 crore", "persons",
                "vulnerable people were screened", s, "Message of the Additional "
                "Secretary & DG (NACO & RNTCP), dated 13 May 2019", image=True,
                note="the page has no text layer; sentence read from the page image"),
          Prose("ITR2019", 9, "tb_cases", "49,733", "cases",
                "reporting of an additional 49,733 cases", s, "Message of the "
                "Additional Secretary & DG (NACO & RNTCP), dated 13 May 2019",
                image=True, note="the page has no text layer; sentence read from the "
                                 "page image")]
    s = ("Under active case finding activities nearly 19 crore population have been "
         "screened, yielding an additional notification of 47,307.")
    P += [Prose("ITR2019", 20, "screened", "19 crore", "persons",
                "population have been screened", s, "Foreword and Executive Summary"),
          Prose("ITR2019", 20, "tb_cases", "47,307", "cases",
                "an additional notification", s, "Foreword and Executive Summary")]
    s = ("In 2018, a total of 18.93 crore population has been screened yielding 47,307 "
         "additional TB cases.")
    w18 = dict(period="2018", wstart="2018-01-01", wend="2018-12-31")
    P += [Prose("ITR2019", 49, "screened", "18.93 crore", "persons",
                "population has been screened", s, "Chapter 4 Active Case Finding",
                note=_SEC.format("Active Case Finding"), **w18),
          Prose("ITR2019", 49, "tb_cases", "47,307", "cases", "additional TB cases", s,
                "Chapter 4 Active Case Finding",
                note=_SEC.format("Active Case Finding"), **w18)]
    P.append(Prose("ITR2019", 49, "other:mobile_tb_diagnostic_vans", "45", "",
                   "Mobile TB Diagnostic Van", "Mobile TB Diagnostic Van (45) has been "
                   "provided to each State for active TB case finding which enables "
                   "reaching the hard to reach areas for early detection of TB.",
                   "Chapter 4 Active Case Finding",
                   note=_VAN + "; resource whose sentence names active case finding "
                               "(rule 3)"))
    P.append(Prose("ITR2019", 95, "other:medical_mobile_vans_procured", "45", "",
                   "Medical Mobile Vans", "Programme has procured 45 Medical Mobile "
                   "Vans and distributed the same to states in the year 2018 to support "
                   "diagnosis of MDR-TB and TB in high risk population through Active "
                   "Case Finding.", "Procurement, item 10 'Mobile Diagnostic Vans'",
                   period="in the year 2018", wstart="2018-01-01", wend="2018-12-31",
                   note=_VAN + "; resource whose sentence names active case finding "
                               "(rule 3)"))
    # ---------------- India TB Report 2020 (data year 2019)
    s = ("In 2019 a total of about 27.74 crore population has been screened yielding "
         "62,958 additional TB cases were diagnosed.")
    w19 = dict(period="2019", wstart="2019-01-01", wend="2019-12-31")
    P += [Prose("ITR2020", 57, "screened", "27.74 crore", "persons",
                "population has been screened", s, "Chapter 4 Active Case Finding",
                note=_SEC.format("Active Case Finding"), **w19),
          Prose("ITR2020", 57, "tb_cases", "62,958", "cases",
                "additional TB cases were diagnosed", s, "Chapter 4 Active Case Finding",
                note=_SEC.format("Active Case Finding"), **w19)]
    P.append(Prose("ITR2020", 57, "other:mobile_tb_diagnostic_vans", "80", "",
                   "Mobile TB Diagnostic Van", "Mobile TB Diagnostic Van (80) has been "
                   "provided to each State for active TB case finding which enables "
                   "reaching the hard to reach areas for early detection of TB.",
                   "Chapter 4 Active Case Finding",
                   note=_VAN + "; resource whose sentence names active case finding "
                               "(rule 3)"))
    P.append(Prose("ITR2020", 57, "other:states_uts_conducting_acf", "32", "",
                   "State/UTs have carried out ACF activities", "During Jan – Dec 2019, "
                   "32 State/UTs have carried out ACF activities at different time "
                   "periods in the districts level.", "Chapter 4 Active Case Finding",
                   period="Jan – Dec 2019", wstart="2019-01-01", wend="2019-12-31",
                   note=_SU))
    P.append(Prose("ITR2020", 112, "other:medical_mobile_vans_procured", "45", "",
                   "Medical Mobile Vans", "The programme has procured 45 Medical Mobile "
                   "Vans and distributed the same to states in the year 2018 to support "
                   "the diagnosis of TB and MDR-TB in the high risk population through "
                   "Active Case Finding.", "Procurement, 'Mobile Diagnostic Vans'",
                   period="in the year 2018", wstart="2018-01-01", wend="2018-12-31",
                   note=_VAN + "; resource whose sentence names active case finding "
                               "(rule 3)"))
    # ---------------- India TB Report 2022 (data year 2021)
    w21 = dict(period="2021", wstart="2021-01-01", wend="2021-12-31")
    s = ("Accordingly, in 2021, 34 States/UTs have conducted ACF activities/ campaigns "
         "at the state and district level, leading to the screening of 2.23 crore "
         "people, out of which 17,52,903 samples were tested for TB, and 73,772 "
         "additional TB patients were identified.")
    ES = "Executive Summary, 'TB Diagnostic Services and Active Case Finding'"
    P += [Prose("ITR2022", 9, "other:states_uts_conducting_acf", "34", "",
                "States/UTs have conducted ACF activities/ campaigns", s, ES, note=_SU,
                **w21),
          Prose("ITR2022", 9, "screened", "2.23 crore", "persons",
                "the screening of 2.23 crore people", s, ES, **w21),
          Prose("ITR2022", 9, "tested", "17,52,903", "persons",
                "samples were tested for TB", s, ES, **w21),
          Prose("ITR2022", 9, "tb_cases", "73,772", "cases",
                "additional TB patients were identified", s, ES, **w21),
          Prose("ITR2022", 9, "other:mobile_tb_diagnostic_vans", "81", "",
                "Mobile TB Diagnostic Vans", "The NTEP has made 81 Mobile TB Diagnostic "
                "Vans available to the States for conducting ACF in remote and "
                "hard-to-reach areas.", ES,
                note=_VAN + "; resource whose sentence names ACF (rule 3)")]
    s = ("In 2021, a total of 2.23 crore persons were screened, 17,52,903 samples tested "
         "for TB and 73,772 additional TB patients identified through Active Case "
         "Finding.")
    CH = "Chapter 2, section 'Active Case Finding'"
    P += [Prose("ITR2022", 22, "screened", "2.23 crore", "persons",
                "persons were screened", s, CH, **w21),
          Prose("ITR2022", 22, "tested", "17,52,903", "persons",
                "samples tested for TB", s, CH, **w21),
          Prose("ITR2022", 22, "tb_cases", "73,772", "cases",
                "additional TB patients identified through Active Case Finding", s, CH,
                **w21),
          Prose("ITR2022", 22, "other:mobile_tb_diagnostic_vans", "81", "",
                "Mobile TB Diagnostic Vans", "A total of 81 Mobile TB Diagnostic Vans "
                "has been provided to the states for conducting ACF in remote, "
                "hard-to-reach areas.", CH,
                note=_VAN + "; resource whose sentence names ACF (rule 3)"),
          Prose("ITR2022", 22, "other:states_uts_conducting_acf", "34", "",
                "states/UTs have conducted ACF activities/campaigns", "From January to "
                "December 2021, 34 states/UTs have conducted ACF activities/campaigns at "
                "state and district levels, at different time-periods.", CH,
                period="January to December 2021", wstart="2021-01-01",
                wend="2021-12-31", note=_SU)]
    s = ("In this Marathon exercise, 1809 TB cases were diagnosed while 1791 patients "
         "were initiated with treatment and introduced to Nikshay.")
    UP = "Box 'Examples of Best Practices in Uttar Pradesh: Inclusion of ACF in Dastak " \
         "Abhiyan'"
    P += [Prose("ITR2022", 76, "tb_cases", "1809", "cases", "TB cases were diagnosed",
                s, UP, geography="Uttar Pradesh",
                note=_SEC.format("Inclusion of ACF in Dastak Abhiyan")),
          Prose("ITR2022", 76, "other:tb_patients_initiated_on_treatment", "1791",
                "persons", "patients were initiated with treatment", s, UP,
                geography="Uttar Pradesh",
                note=_SEC.format("Inclusion of ACF in Dastak Abhiyan"))]
    # ---------------- India TB Report 2023 (data year 2022)
    w22 = dict(period="", wstart="2022-01-01", wend="2022-12-31")
    s1 = ("In 2022, across the country a total of 22.1 crore individuals were screened "
          "for presumptive TB symptoms/signs as part of active case-finding efforts.")
    s2 = ("Of the screened, 0.9% (19.5 lakhs) were examined and tested for TB diagnosis "
          "and of which 48,329 (2.5%) were diagnosed.")
    CH3 = "Chapter 3B TB Case Finding, section 'Active case finding'"
    a17 = _A17.format("In 2022, across the country ...")
    P += [Prose("ITR2023", 63, "screened", "22.1 crore", "persons",
                "individuals were screened for presumptive TB symptoms/signs", s1, CH3,
                period="2022", wstart="2022-01-01", wend="2022-12-31"),
          Prose("ITR2023", 63, "other:pct_tested_among_screened", "0.9%", "percent",
                "were examined and tested for TB diagnosis", s2, CH3, note=a17, **w22),
          Prose("ITR2023", 63, "tested", "19.5 lakhs", "persons",
                "were examined and tested for TB diagnosis", s2, CH3, note=a17, **w22),
          Prose("ITR2023", 63, "tb_cases", "48,329", "cases", "were diagnosed", s2, CH3,
                note=a17, **w22),
          Prose("ITR2023", 63, "other:pct_diagnosed_among_tested", "2.5%", "percent",
                "were diagnosed", s2, CH3, note=a17, **w22)]
    # ---------------- India TB Report 2024 (data year 2023)
    s = ("Alongside, door-to-door active case finding campaigns have resulted in 20.5 "
         "crore people being screened for TB and 35,438 patients being diagnosed and "
         "initiated on treatment.")
    FW = "Foreword of the Additional Secretary & Mission Director (NHM)"
    P += [Prose("ITR2024", 9, "screened", "20.5 crore", "persons",
                "people being screened for TB", s, FW, image=True,
                note="the page has no text layer; sentence read from the page image"),
          Prose("ITR2024", 9, "tb_cases", "35,438", "cases",
                "patients being diagnosed and initiated on treatment", s, FW, image=True,
                note="the page has no text layer; sentence read from the page image")]
    s1 = ("In 2023, a total of more than 20.5 crore individuals were screened for "
          "signs/symptoms suggestive of TB as a part of active case finding efforts "
          "(Box 4.1).")
    s2 = ("Of the screened, 1.1% (21.8 lakhs) were examined and tested for TB diagnosis "
          "and 35,438 TB cases (1.6% out of those tested) were diagnosed.")
    CH4 = "Chapter 4 TB Case Finding, section 'Active Case Finding'"
    a17 = _A17.format("In 2023, a total of more than 20.5 crore individuals ...")
    w23 = dict(period="", wstart="2023-01-01", wend="2023-12-31")
    P += [Prose("ITR2024", 54, "screened", "20.5 crore", "persons",
                "individuals were screened for signs/symptoms suggestive of TB", s1, CH4,
                period="2023", wstart="2023-01-01", wend="2023-12-31"),
          Prose("ITR2024", 54, "other:pct_tested_among_screened", "1.1%", "percent",
                "were examined and tested for TB diagnosis", s2, CH4, note=a17, **w23),
          Prose("ITR2024", 54, "tested", "21.8 lakhs", "persons",
                "were examined and tested for TB diagnosis", s2, CH4, note=a17, **w23),
          Prose("ITR2024", 54, "tb_cases", "35,438", "cases", "TB cases (1.6% out of "
                "those tested) were diagnosed", s2, CH4, note=a17, **w23),
          Prose("ITR2024", 54, "other:pct_diagnosed_among_tested", "1.6%", "percent",
                "out of those tested", s2, CH4, note=a17, **w23)]
    T11 = "Table 1.1: NSP indicators and progress"
    row8 = ("Proportion of identified targeted key affected population undergoing "
            "active case finding")
    P += [Prose("ITR2024", 32, "other:pct_key_population_undergoing_acf", "0%",
                "percent", row8, "", "Table 1.1, outcome indicator 8", title=T11,
                col="Baseline 2015", row=row8, period="Baseline 2015",
                wstart="2015-01-01", wend="2015-12-31",
                note="the Achievement 2023 cell is printed 'NA' (not entered)"),
          Prose("ITR2024", 32, "other:target_pct_key_population_undergoing_acf", "100%",
                "percent", row8, "", "Table 1.1, outcome indicator 8", title=T11,
                col="Target 2023", row=row8, period="Target 2023",
                wstart="2023-01-01", wend="2023-12-31",
                note="NSP target whose row names active case finding (rule 3)")]
    G = "Chapter 'TB Research', 'Other Research Studies Undertaken by Partners', item 1"
    s1 = ("Findings showed that out of 768 TB districts, data for 111 were unavailable in "
          "the ACF records.")
    s2 = ("Among the remaining 657 districts, 642 (98%) were carried out one ACF cycle, "
          "while 15 districts implemented 2–3 cycles.")
    s3 = ("Nationally, during the initial ACF cycle, 9.3% of the population underwent "
          "screening, with 1% of those screened undergoing testing, and 3.7% of those "
          "tested being diagnosed.")
    s4 = ("The NNS was 2,824 which are considered acceptable (≤1,538) in institutional "
          "facilities but poor for population-based groups.")
    P += [Prose("ITR2024", 144, "other:tb_districts", "768", "districts",
                "TB districts", s1, G, note=_GHA),
          Prose("ITR2024", 144, "other:districts_acf_data_unavailable", "111",
                "districts", "data for 111 were unavailable in the ACF records", s1, G,
                note=_GHA),
          Prose("ITR2024", 144, "other:districts_with_acf_data", "657", "districts",
                "the remaining 657 districts", s2, G, note=_GHA),
          Prose("ITR2024", 144, "other:districts_one_acf_cycle", "642", "districts",
                "were carried out one ACF cycle", s2, G, note=_GHA),
          Prose("ITR2024", 144, "other:pct_districts_one_acf_cycle", "98%", "percent",
                "were carried out one ACF cycle", s2, G, note=_GHA),
          Prose("ITR2024", 144, "other:districts_two_to_three_acf_cycles", "15",
                "districts", "districts implemented 2–3 cycles", s2, G, note=_GHA),
          Prose("ITR2024", 144, "other:pct_population_screened", "9.3%", "percent",
                "of the population underwent screening", s3, G,
                period="the initial ACF cycle", note=_GHA),
          Prose("ITR2024", 144, "other:pct_tested_among_screened", "1%", "percent",
                "of those screened undergoing testing", s3, G,
                period="the initial ACF cycle", note=_GHA),
          Prose("ITR2024", 144, "other:pct_diagnosed_among_tested", "3.7%", "percent",
                "of those tested being diagnosed", s3, G,
                period="the initial ACF cycle", note=_GHA),
          Prose("ITR2024", 144, "nns", "2,824", "ratio", "The NNS", s4, G,
                note=_GHA + "; the benchmark '≤1,538' is not entered (ruling A20)")]
    return P


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


def _table_method(t: Table) -> str:
    text = "\n".join(page_text(t.file, p) for p in t.pages)
    pieces = [h for c in t.columns for h in c.heading.split(": ")
              if h not in t.image_pieces] + list(t.notes)
    if not t.title_from_image:
        pieces.append(t.title)
    m = invrow.verify_pieces(pieces, text)
    if t.title_from_image:
        m += ("; title read from the page image (printed vertically, not in the text "
              "layer)")
    if t.image_pieces:
        m += ("; column heading(s) " + ", ".join(f"'{x}'" for x in t.image_pieces)
              + " read from the page image (multi-line header cells whose word "
                "fragments are not adjacent in the text layer)")
    return m


def _window_note(t: Table) -> str:
    return (f"window stated in the report's chapter: '{t.window_stated}' (ruling A17)"
            if t.window_stated else "")


def table_inventory(t: Table, ext: list[dict], url: str) -> tuple[list[dict], list[dict]]:
    rows, prov = [], []
    year = EDITIONS[t.edition][1]
    method = _table_method(t)
    for r in ext:
        base_col = r["column"].removesuffix("_pct")
        col = next(c for c in t.columns if c.key == base_col)
        if not col.inventory or r["value"] == "":
            continue
        is_pct = r["column"].endswith("_pct")
        quantity = col.pct_quantity if is_pct else col.quantity
        definition = col.pct_definition if is_pct else col.definition
        step = r["label_rule_step"]
        notes = [f"State label printed as '{r['label_printed']}'; label rule step "
                 f"{step}: {r['label_evidence']}" if step not in ("", "1", 1) else "",
                 _window_note(t), r["note"], EDITIONS[t.edition][3],
                 "percentage printed with the count in the same cell" if is_pct else ""]
        wstart = wend = ""
        if t.window_stated:
            wstart, wend = f"{year}-01-01", f"{year}-12-31"
        inv = invrow.row(
            doc=t.edition, page=int(r["pdf_page"]), quantity=quantity,
            printed=r["value_printed"], unit="percent" if is_pct else col.unit,
            definition=definition, source_file=t.file, source_url=url,
            page_or_para=f"PDF page {r['pdf_page']}; {t.table_id} (printed page "
                         f"{t.printed_pages})",
            pub_date=EDITIONS[t.edition][2], title=t.title,
            col=col.heading, rowlabel=r["label_printed"], geography=r["canonical"],
            table_id=f"{t.table_id}: {t.title}", wstart=wstart, wend=wend,
            notes=tuple(notes), value=r["value"])
        rows.append(inv)
        invrow.verify([r["label_printed"]], r["value_printed"],
                      page_text(t.file, int(r["pdf_page"])))
        prov.append({"kind": "figure", "fig_id": inv["fig_id"], "source_file": t.file,
                     "page": r["pdf_page"], "method": method.split(";")[0],
                     "figures_found": method if ";" in method else ""})
    return rows, prov


def prose_inventory(man: dict) -> tuple[list[dict], list[dict]]:
    rows, prov = [], []
    for s in _prose_specs():
        file, _, pub, pub_note = EDITIONS[s.edition]
        is_table = bool(s.col)
        inv = invrow.row(
            doc=s.edition, page=s.page, quantity=s.quantity, printed=s.printed,
            unit=s.unit, definition=s.definition, source_file=file,
            source_url=man[file]["url"], page_or_para=f"PDF page {s.page}; {s.where}",
            pub_date=pub, sentence=s.sentence, title=s.title, col=s.col,
            rowlabel=s.row, geography=s.geography, period=s.period, wstart=s.wstart,
            wend=s.wend, table_id=s.title if is_table else "",
            notes=(s.note, pub_note), occurrence=s.occurrence)
        rows.append(inv)
        if s.image:
            method = "page image"
        else:
            pieces = [s.title, s.col, s.row] if is_table else [s.sentence]
            method = invrow.verify([p for p in pieces if p], s.printed,
                                   page_text(file, s.page) + "\n" + _cols_text(file,
                                                                               s.page))
        prov.append({"kind": "figure", "fig_id": inv["fig_id"], "source_file": file,
                     "page": s.page, "method": method, "figures_found": ""})
    return rows, prov


@lru_cache(maxsize=None)
def _cols_text(file: str, page: int) -> str:
    """The page's text read column by column (two or four columns), for checking a
    sentence that the full-width text layer interleaves."""
    import pdfplumber
    with pdfplumber.open(ROOT / file) as pdf:
        pg = pdf.pages[page - 1]
        w = pg.width
        n = 4 if w > 900 else 2
        parts = [pg.crop((w * k / n, 0, w * (k + 1) / n, pg.height)).extract_text() or ""
                 for k in range(n)]
        parts += [pg.crop((w * k / 2, 0, w * (k + 1) / 2, pg.height)).extract_text()
                  or "" for k in range(2)]
    return re.sub(r"(?<=[a-z])f (?=i[a-z])", "f", "\n".join(parts))


def build_inventory(exts: dict[str, list[dict]] | None = None
                    ) -> tuple[list[dict], list[dict]]:
    man = _manifest()
    rows, prov = [], []
    for t in TABLES:
        if not t.inventory:
            continue
        ext = exts[t.key] if exts else extracted_rows(t)
        r, p = table_inventory(t, ext, man[t.file]["url"])
        rows += r
        prov += p
    r, p = prose_inventory(man)
    rows += r
    prov += p
    invrow.check_ids(rows)
    return rows, prov


# ================================================================== scope decisions

SCOPE_RULE_ITR = (
    "Inventory scope of the India TB Reports (§5.1, §4 item 5, §7.4). (1) Figures of the "
    "named quantities, and other ACF figures as `other:`, enter when their sentence, "
    "list item or table (title, column heading or row label), or the heading of their "
    "chapter, section or box, names active case finding (ACF) or the TB Mukt Bharat "
    "Abhiyaan campaign. (2) Resources and targets enter only when their own sentence or "
    "table row names ACF or the campaign (campaign documents' rule 3). (3) A figure for "
    "a district, block, city or project population is not entered: the §5.2 geography "
    "field takes India or a State/UT. (4) The State notification counts of the 2024 "
    "edition enter because §7.4 enters and classifies them; the notification annexures "
    "of the 2020 and 2023 editions are outcome data only (not ACF or campaign figures, "
    "not named in §7.4). (5) Media, IEC, nutrition-support and Ni-kshay Mitra campaigns "
    "are not TB case-finding campaigns; their figures are programme-wide and not "
    "entered. (6) Benchmark thresholds of the ACF guidance are not entered (ruling "
    "A20). (7) Pictures of social-media posts reproduced as illustrations are not "
    "figures published by the report and are not entered.")

SCOPE_EXCLUSIONS: list[tuple[str, int, str, str, str, str]] = [
    ("ITR2019", 20, "80", "Executive Summary, Mobile TB Diagnostic Vans", "resource",
     "the sentence names 'the active search', not active case finding (rule 2)"),
    ("ITR2019", 77, "about 20 Lakh; about 3.48 Crore", "Chapter 8, Kerala survey",
     "surveillance", "population surveillance survey of one State, presented as 'a more "
     "intensive level of surveillance', not as ACF (rule 1)"),
    ("ITR2019", 89, "USD 0.33 Million; USD 0.37 Million; 19 Blocks",
     "Global Fund grantees TVHA and SHIS", "project", "project allocations and blocks "
     "of sub-national ACF projects (rule 3)"),
    ("ITR2019", 103, "90%; 5%; 29 (4%); 24; 17,634; 952 (5%); 26 DS-TB & 3 DR-TB",
     "picture of a tweet of the State TB Team, Chhattisgarh", "illustration",
     "a social-media post reproduced as a picture (rule 7)"),
    ("ITR2019", 128, "14,20,800; 10,58,902; 75%", "Project Axshya (The Union), "
     "households covered through active case finding, Jan-Sep 2018", "project",
     "figures of a project covering selected districts of several States (rule 3)"),
    ("ITR2019", 178, "2 blocks", "Annexure 1.7, note on Madhya Pradesh", "survey design",
     "not a figure of a §5.1 quantity"),
    ("ITR2020", 105, "19 Blocks", "Global Fund grantee SHIS", "project",
     "sub-State area (rule 3)"),
    ("ITR2020", 112, "395; about 10,000", "Procurement (digital X-ray; tablet "
     "computers)", "resource", "the sentences do not name ACF (rule 2)"),
    ("ITR2020", 168, "seven; More than 80,000; ~13 per 100,000; >500 per 100,000; nine; "
     "~85,000", "CHAI, Greater Chennai Corporation", "sub-State",
     "city figures (rule 3)"),
    ("ITR2020", 169, "22", "TVHA, ACF in schools and monasteries", "project",
     "project figure (rule 3)"),
    ("ITR2020", 255, "all cells", "Annexure 6, 'Estimated Population (Lakhs)' column",
     "entered", "entered as printed; several rows' populations look shifted between "
                "States in the printed column (e.g. the India row prints 2287.7); no "
                "value is corrected (§5.1)"),
    ("ITR2022", 7, "8.37 lakh; 35,519", "Message of the DDG (TB)", "not given as ACF",
     "the sentence refers to 'these efforts' (door-to-door ACF campaigns and "
     "bi-directional TB-COVID-19 screening together) and names neither; no heading "
     "(rule 1)"),
    ("ITR2022", 22, "2238.8", "Chapter 2, page footer area", "artefact",
     "a stray chart label in the text layer, not a figure of the ACF section"),
    ("ITR2022", 57, "over 600; 100; 100 days", "Joint campaign 'Aashwasan'", "target",
     "planned reach of a joint COVID-19 awareness and TB ACF campaign; the sentence "
     "names neither ACF nor the TB Mukt Bharat Abhiyaan (rule 2)"),
    ("ITR2022", 61, "500; 273; 169; 5; 352/355; 84 (24%); 19", "End DR-TB Dharavi "
     "Project and household-contact project", "sub-State", "Mumbai slum and project "
     "figures (rule 3)"),
    ("ITR2022", 75, "124 (34%); 126 (35%); 135 (38%) and the box's other counts",
     "Tamil Nadu post-COVID catch-up campaign box", "not given as ACF",
     "a post-COVID screening drive headed 'Post-COVID catch-up campaign for augmenting "
     "case-finding activities under NTEP'; neither the heading nor the figures' "
     "sentences name active case finding (rule 1)"),
    ("ITR2023", 63, "around 80", "Chapter 3B, mobile diagnostic units", "resource",
     "the sentence does not name ACF (rule 2)"),
    ("ITR2023", 65, "0.5 million; 350; 20 days; 2436; 72; 4", "Himachal Pradesh, Una "
     "district handheld X-ray", "sub-State", "district figures (rule 3)"),
    ("ITR2023", 159, "31,030", "Rajasthan, Integrated Ni-kshay Diwas", "not given as ACF",
     "outcome of Ni-kshay Diwas, not named ACF (rule 1)"),
    ("ITR2023", 61, "none", "PDF pages 61-62 (no text layer)", "page image",
     "rendered and read: notification characteristics and the automated case-finding "
     "report; no ACF figure"),
    ("ITR2024", 55, "1,250; 3 days; More than 250; 2,400 metres",
     "Box 4.1 Active case finding in Kashmir region of Himalayas (Gurez valley)",
     "sub-State", "valley figures (rule 3)"),
    ("ITR2024", 144, "36 states; 768 district-level; ≥10%; ≥4.8%; ≥5%; ≤1,538",
     "Evaluation of active case finding, aim sentence and indicator thresholds",
     "study design and benchmarks", "the aim sentence's scope and the benchmark "
     "thresholds (rule 6); the findings are entered"),
    ("ITR2024", 160, "89,973; 32; 5.29 crores (3.7%); 2.86 crores; 5.23 lakh (1.8%); "
     "4.39 lakh; 11,806; 58,986; 4.37 lakh; 81,424; 5.91 lakh; 91,689; 85,384; 57,611 "
     "(64%)", "National-level campaign in 2023 ('TB Mukt Bharat@AB-HWCs through Jan "
     "Arogya Samitis', 24 March-13 April 2023)", "not given as ACF",
     "the section is headed 'National-level campaign in 2023' and the figures' list "
     "items name neither ACF nor the TB Mukt Bharat Abhiyaan; ACF is one of the "
     "campaign's listed focus areas, but no figure is given as an ACF figure (rule 1)"),
    ("ITR2024", 111, "89,973; 33; 58,986; 4.37 lakh; 81,424; 5.91 lakh; 91,689; 4.68 "
     "lakh; 85,384", "the same 21-day campaign (Chapter 10)", "not given as ACF",
     "orientation, Gram Sabha and TB-champion counts (rule 1)"),
    ("ITR2024", 279, "#DIV/0!", "Annexure 6, Manipur, TB cases diagnosed among tested",
     "blank", "printed as a spreadsheet error: blank, kept blank"),
]


def scope_decisions() -> list[dict]:
    out = [{"kind": "rule", "doc": "India TB Reports", "source_file":
            "data_raw/india_tb_report/", "page": "", "figures": "", "where": "",
            "category": "", "decision": "", "reason": SCOPE_RULE_ITR}]
    for doc, p, figs, where, cat, why in SCOPE_EXCLUSIONS:
        out.append({"kind": "exclusion" if cat != "entered" else "note", "doc": doc,
                    "source_file": EDITIONS[doc][0], "page": p, "figures": figs,
                    "where": where, "category": cat,
                    "decision": "entered" if cat == "entered" else "not entered",
                    "reason": why})
    out.append({"kind": "note", "doc": "India TB Reports", "source_file":
                "data_raw/india_tb_report/", "page": "", "figures": "",
                "where": "pages without a text layer", "category": "page image",
                "decision": "read",
                "reason": "every page without a text layer in the five editions (2019: "
                          "50, 2020: 47, 2022: 5, 2023: 77, 2024: 39) was rendered, and "
                          "OCR was used only to find passages naming ACF or the "
                          "campaign; figures entered from such pages were read from the "
                          "rendered page (ITR2019 p9, ITR2024 p9)"})
    return out


# ================================================================== main

def run() -> dict[str, list[dict]]:
    exts = {t.key: extracted_rows(t) for t in TABLES}
    for t in TABLES:
        write_csv(EXTRACTED / t.csv_name, EXTRACT_COLUMNS, exts[t.key])
    return exts


def main() -> int:
    from src.extract import pq
    from src.extract.campaign import INVENTORY_COLUMNS
    verify_inputs()
    exts = run()
    checks = [c for t in TABLES for c in table_checks(t, exts[t.key])]
    path = EXTRACTED / "table_total_checks.csv"
    write_csv(path, CHECK_COLUMNS,
              merge_by_source(path, checks, set(OWN_FILES), CHECK_COLUMNS))
    inv, prov = build_inventory(exts)
    write_csv(INVENTORY, INVENTORY_COLUMNS,
              merge_by_source(INVENTORY, inv, set(OWN_FILES), INVENTORY_COLUMNS))
    write_csv(EXTRACTED / "itr_inventory_provenance.csv",
              ["kind", "fig_id", "source_file", "page", "method", "figures_found"], prov)
    sp = EXTRACTED / "inventory_scope_decisions.csv"
    own = scope_decisions()
    write_csv(sp, SCOPE_COLUMNS,
              merge_by_source(sp, own, {r["source_file"] for r in own}, SCOPE_COLUMNS))
    # the §9.6 extraction checks of all Q4 sources, with the parliamentary answers
    reads = {t.key: pq.extracted_rows(t) for t in pq.TABLES}
    q4 = pq.q4_checks(reads) + q4_checks(exts)
    write_csv(EXTRACTED / "q4_source_checks.csv", pq.Q4_COLUMNS, q4)
    results = {r["source"]: r["result"] for r in q4}
    write_csv(EXTRACTED / "q4_consequences.csv", ["item", "outcome", "rule"],
              sc.consequences(results))
    for c in checks:
        print("total check:", c["table"], c["pass"], c["sum_of_rows"], c["printed_total"])
    for r in q4:
        print("Q4 check:", r["source"], r["result"], "|", r["sum_check"])
    print(f"inventory rows from the India TB Reports: {len(inv)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
