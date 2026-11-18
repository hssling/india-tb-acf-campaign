"""Parliamentary answers (analysis plan §3.1.2, §3.4, §7.4, §9.5, §9.6, §13).

Each State table is read from the answer document itself (§3.4), page by page, with
its title, column headings and notes quoted as printed. Every row keeps its printed
label; the label rule of §9.2 maps it to a canonical State/UT and the unit is coarsened
(§9.4). No answer prints a total row, so the sum check of §9.6 is not applied to any of
them, and every record says so.

Roles (§3.1.2, §9.5, §13):
- RS Q1216 (10 Feb 2026): Q4 primary, full years 2023, 2024, 2025; trend points 2023 and
  2024; placebo.
- RS Q3467 (1 Apr 2025): guard reference; fallback trend point 2024.
- LS Q261 (13 Dec 2024): S8, January-October 2024; 2023 column for S8(b).
- RS Q1093 (9 Dec 2025): S8, January-October 2025.
- RS Q2511 (17 Dec 2024): Q1-Q2 only, not Q4 (§9.5.5).
- RS Q1900 (16 Dec 2025): Q2 cross-check of its 2025 column (§9.5.5); its 2024 column is
  exploratory (§13, 18 November 2026).
- RS Q420 (3 Feb 2026): exploratory Q2 cross-check only (§13, 18 November 2026).
- RS Q3477 (1 Apr 2025): read for the inventory (§5.3); it prints no figure of a §5.1
  quantity. RS Q3001: not used (§3.1.2); not read beyond its digest.

The Q4 extraction checks (§9.6) and the re-check at extraction (§9.5.4) are written to
data/extracted/q4_source_checks.csv by this module together with the India TB Report
extractor (src/extract/itr.py). No comparison between sources is made here.

Run: python -I src/extract/pq.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import csv
import re
from dataclasses import dataclass, field
from functools import lru_cache

import pdfplumber

from src import source_checks as sc
from src import states
from src.extract import annex, invrow, labels
from src.extract.cells import parse_int

ROOT = Path(__file__).resolve().parents[2]
EXTRACTED = ROOT / "data/extracted"
INVENTORY = ROOT / "data/figures_inventory.csv"
PQ = "data_raw/pq/"
TOL = 1   # text_x_tolerance: keeps the spaces between the words of a label


@dataclass(frozen=True)
class Col:
    key: str
    index: int            # 0-based cell index after the label
    heading: str          # verbatim column heading (levels joined by ": ")
    definition: str       # the answer's own words for the quantity
    quantity: str
    unit: str
    period: str           # the period words as printed
    wstart: str = ""
    wend: str = ""
    inventory: bool = True
    q4: str = ""          # Q4 role of the column, blank if none
    note: str = ""


@dataclass(frozen=True)
class Table:
    key: str              # "Q1216"
    doc: str              # fig_id prefix
    file: str
    pages: tuple[int, ...]
    title: str            # verbatim table title
    table_id: str         # "Annexure", "Annexure-I"
    columns: tuple[Col, ...]
    answer_date: str
    question: str         # how the answer is cited
    notes: tuple[str, ...]          # notes printed with the table, verbatim
    answer_text: str                # the answer's sentence that places the table
    answer_text_page: int
    as_on: str = ""
    role: str = ""
    source: str = ""      # source_checks constant for a Q4 source; blank otherwise
    exploratory: str = ""
    reader: str = "table"  # "table" (ruled cells) or "lines" (text lines)
    n_rows: int = 36
    other_columns: tuple[str, ...] = ()   # printed columns not extracted, with reason

    @property
    def csv_name(self) -> str:
        return f"pq_{self.key.lower()}.csv"

    def check_name(self, col: Col) -> str:
        return f"{self.question}, {self.table_id}: {col.heading}"


_NI = "TB cases notified"
_EXPL = ("exploratory (analysis plan §13, 18 November 2026): Q2 cross-check only; does "
         "not change Q4")

TABLES: tuple[Table, ...] = (
    Table(
        "Q1216", "RSQ1216", PQ + "AU1216_WFw8li.pdf", (2,),
        "State/UT wise Number of TB Case notified and Number of patients who have "
        "received the monthly nutritional assistance reported under TB Mukt Bharat "
        "Abhiyan, in Year 2023, 2024 and 2025",
        "Annexure",
        tuple(
            c for y, i in ((2023, 0), (2024, 2), (2025, 4)) for c in (
                Col(f"{y}_notified", i, f"{y} (Jan-Dec): Number of TB cases notified",
                    "Number of TB cases notified", "tb_cases", "cases", f"{y} (Jan-Dec)",
                    f"{y}-01-01", f"{y}-12-31",
                    q4={2023: "trend point 2023 (primary); placebo observed 2023",
                        2024: "outcome a (primary contrast); trend point 2024 (primary)",
                        2025: "outcome b (primary contrast)"}[y]),
                Col(f"{y}_paid_once", i + 1,
                    f"{y} (Jan-Dec): Number of Beneficiaries paid at least once",
                    "Number of Beneficiaries paid at least once",
                    "other:npy_beneficiaries_paid_at_least_once", "persons",
                    f"{y} (Jan-Dec)", f"{y}-01-01", f"{y}-12-31",
                    note="not used for Q4 (§9.5.1); entered because the table title "
                         "names the TB Mukt Bharat Abhiyan (inventory scope rule 2)"))),
        "2026-02-10", "RS Unstarred Q. 1216 (10 Feb 2026)",
        ("Data Source: Ni-kshay (As on 06th February 2026)",),
        "The State-wise details of TB cases notified and the number of patients who have "
        "received the NPY in the last three years, State-wise, as per reported in "
        "Ni-kshay portal by the State/UTs is placed as Annexure.", 1,
        as_on="2026-02-06", role="Q4 primary (§9.5.1); trend points 2023, 2024 (§9.6)",
        source=sc.Q1216),
    Table(
        "Q3467", "RSQ3467", PQ + "AU3467_mVGJLD.pdf", (3,),
        "State-wise TB patients notified and treated successfully in 2023 and 2024",
        "Annexure-I",
        (Col("2023_notified", 0, "2023: TB patients notified", "TB patients notified",
             "tb_cases", "cases", "2023", "2023-01-01", "2023-12-31",
             q4="guard reference 2023 (§9.5.2)"),
         Col("2024_notified", 2, "2024*: TB patients notified", "TB patients notified",
             "tb_cases", "cases", "2024", "2024-01-01", "2024-12-31",
             q4="guard reference 2024 (§9.5.2); fallback trend point 2024 (§9.6)",
             note="the column heading '2024*' carries the footnote '*Treatment outcome "
                  "will be due in 2025'")),
        "2025-04-01", "RS Unstarred Q. 3467 (1 Apr 2025)",
        ("*Treatment outcome will be due in 2025",),
        "The details of TB cases notified and treated successfully in year 2023 and "
        "2024, is placed at Annexure-I.", 1,
        role="guard reference (§9.5.2); fallback trend point 2024 (§9.6)",
        source=sc.Q3467,
        other_columns=("2023: Treated Successfully (treatment outcome; not a §5.1 "
                       "quantity, not an ACF or campaign figure: not extracted)",)),
    Table(
        "Q261", "LSQ261", PQ + "AS261_lP7nYE.pdf", (4, 5),
        "State/UT wise TB cases reported since 2022 to 2024*", "Annexure-I",
        (Col("2023_reported", 0, "2023", "TB cases reported", "tb_cases", "cases",
             "2023", "2023-01-01", "2023-12-31",
             q4="S8(b): 2023 count of the lag proxy (§10.5)",
             note="definition from the table title (the column heading is the year)"),
         Col("2024_jan_oct_reported", 1, "2024 (Jan- Oct)", "TB cases reported",
             "tb_cases", "cases", "2024 (Jan- Oct)", "2024-01-01", "2024-10-31",
             q4="S8: outcome a, January-October 2024 (§9.5.3)",
             note="definition from the table title (the column heading is the period); "
                  "the answer text gives the window as 'current year (till "
                  "31.10.2024)'")),
        "2024-12-13", "LS Starred Q. 261 (13 Dec 2024)",
        ("Data source: Ni-kshay",),
        "State/UT-wise details of number of reported TB cases in 2023 & current year "
        "(till 31.10.2024) is placed at Annexure-I.", 3,
        role="S8 January-October 2024 (§9.5.3); 2023 column for S8(b) (§10.5)",
        source=sc.LS261, reader="lines"),
    Table(
        "Q1093", "RSQ1093", PQ + "AU1093_dH065I.pdf", (2,),
        "State/UT wise TB cases reported for 2025 (Jan – Oct, 2025)", "Annexure",
        (Col("2025_jan_oct_reported", 0, "TB Cases reported", "TB Cases reported",
             "tb_cases", "cases", "2025 (Jan – Oct, 2025)", "2025-01-01", "2025-10-31",
             q4="S8: outcome b, January-October 2025 (§9.5.3)",
             note="window from the table title '2025 (Jan – Oct, 2025)'"),),
        "2025-12-09", "RS Unstarred Q. 1093 (9 Dec 2025)",
        ("Data source: Ni-kshay portal",),
        "The details of cases of TB reported by the State/UTs across the country in "
        "Ni-kshay portal during 2025 (Jan –Oct) is placed as Annexure.", 1,
        role="S8 January-October 2025 (§9.5.3)", source=sc.Q1093),
    Table(
        "Q2511", "RSQ2511", PQ + "AU2511_t81pFf.pdf", (2,),
        "State/UT wise TB cases Notification and Death^ reported in 2024*", "Annexure",
        (Col("2024_jan_oct_notification", 0,
             "State/UT wise TB cases Notification in 2024 (Jan- Oct)",
             "State/UT wise TB cases Notification", "tb_cases", "cases",
             "2024 (Jan- Oct)", "2024-01-01", "2024-10-31",
             note="Q1-Q2 only, not used for Q4 (§9.5.5); the column heading prints "
                  "'(Jan- Oct)' and the table note '*As on 19th Nov 2024'"),),
        "2024-12-17", "RS Unstarred Q. 2511 (17 Dec 2024)",
        ("*As on 19th Nov 2024",
         "^Year in column heading reflects treatment outcome of patients notified in "
         "the previous year.", "Data source: Ni-kshay"),
        "The State/UTs wise details of cases and deaths of tuberculosis reported during "
        "2024, is at Annexure.", 1,
        as_on="2024-11-19", role="Q1-Q2 only; not used for Q4 (§9.5.5)",
        other_columns=("State/UT wise TB deaths^ in 2024 (Jan- Oct) (deaths: not a §5.1 "
                       "quantity, not an ACF or campaign figure: not extracted)",)),
    Table(
        "Q1900", "RSQ1900", PQ + "AU1900_PxKD5V.pdf", (3,),
        "State/UT wise TB Cases Notification under TB Mukt Bharat Abhiyan", "Annexure",
        (Col("2024_jan_dec_notification", 0, "2024 (Jan to Dec)",
             "TB Cases Notification", "tb_cases", "cases", "2024 (Jan to Dec)",
             "2024-01-01", "2024-12-31", note=_EXPL),
         Col("2025_jan_oct_notification", 1, "2025 (Jan to Oct)",
             "TB Cases Notification", "tb_cases", "cases", "2025 (Jan to Oct)",
             "2025-01-01", "2025-10-31",
             note="pre-specified Q2 cross-check with Question 1093 (§7.4, §9.5.5); "
                  "does not change Q4")),
        "2025-12-16", "RS Unstarred Q. 1900 (16 Dec 2025)",
        ("Data Source: Ni-kshay portal",),
        "The State/UT wise details of notified TB cases under TB Mukt Bharat Abhiyan "
        "(National TB Elimination Programme) in 2024 and 2025 (Jan-Oct), is placed as "
        "Annexure.", 1,
        role="Q2 cross-check (§9.5.5); 2024 column exploratory (§13)"),
    Table(
        "Q420", "RSQ420", PQ + "AU420_ulGhhr.pdf", (3,),
        "State/UT wise TB Case Notification, reported under TB Mukt Bharat Abhiyan, for "
        "2025", "Annexure-I",
        (Col("2025_notified", 0, "2025 (Jan-Dec): Number of TB cases notified",
             "Number of TB cases notified", "tb_cases", "cases", "2025 (Jan-Dec)",
             "2025-01-01", "2025-12-31", note=_EXPL),),
        "2026-02-03", "RS Unstarred Q. 420 (3 Feb 2026)",
        ("Data Source: Ni-kshay (As on 21st January 2026)",),
        "The State-wise details of TB cases notified in 2025, as reported by the "
        "State/UTs in Ni-kshay portal is placed as Annexure-I.", 1,
        as_on="2026-01-21", role="exploratory Q2 cross-check only (§13)",
        exploratory=_EXPL,
        other_columns=("Annexure-II (parts A, B) and Annexure-III: grants and "
                       "Ni-kshay Poshan Yojana expenditure (finance: not a §5.1 "
                       "quantity, not an ACF figure; not extracted)",)),
)

OWN_FILES = frozenset(t.file for t in TABLES) | {PQ + "AU3477_SSspdQ.pdf"}
ANSWERS_READ = {PQ + "AU3477_SSspdQ.pdf": ("RS Unstarred Q. 3477 (1 Apr 2025)",
                                           "2025-04-01")}


# ================================================================== reading

@lru_cache(maxsize=None)
def page_text(file: str, page: int) -> str:
    with pdfplumber.open(ROOT / file) as pdf:
        return pdf.pages[page - 1].extract_text(x_tolerance=TOL) or ""


@lru_cache(maxsize=None)
def _ruled(file: str, page: int) -> list[list[str | None]]:
    with pdfplumber.open(ROOT / file) as pdf:
        ts = pdf.pages[page - 1].extract_tables(table_settings={"text_x_tolerance": TOL})
    if len(ts) != 1:
        raise ValueError(f"{file} p{page}: {len(ts)} tables, expected 1")
    return ts[0]


def _flat(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\n", " ")).strip()


_VAL = re.compile(r"^\d[\d,]*$")


@dataclass
class Read:
    rows: list[tuple[str, int, list[str]]] = field(default_factory=list)
    # (printed label, page, printed cells)


def read_table(t: Table) -> Read:
    """State rows as printed: (label, page, cells). Raises if a row does not have one
    cell per column, or a cell is not a count."""
    out = Read()
    for p in t.pages:
        if t.reader == "lines":
            lines = page_text(t.file, p).splitlines()
            for r in annex.assemble_rows(lines, 0, "India"):
                out.rows.append((r.label, p, [c.raw for c in r.cells]))
            continue
        for cells in _ruled(t.file, p):
            lab = _flat(cells[0])
            vals = [_flat(c) for c in cells[1:]]
            if not lab or not vals or not all(_VAL.match(v) for v in vals):
                continue
            out.rows.append((lab, p, vals))
    for lab, p, vals in out.rows:
        if len(vals) < max(c.index for c in t.columns) + 1:
            raise ValueError(f"{t.key} {lab}: {len(vals)} cells")
        for v in vals:
            parse_int(v)
    if len(out.rows) != t.n_rows:
        raise ValueError(f"{t.key}: {len(out.rows)} State rows, expected {t.n_rows}")
    return out


def _check_wording(t: Table) -> list[str]:
    """Title, notes, column headings and the answer's sentence must all be on the page
    as quoted (whitespace normalised). Returns the verification method per piece."""
    text = "\n".join(page_text(t.file, p) for p in t.pages)
    pieces = [t.title, *t.notes]
    for c in t.columns:
        pieces += [x for x in c.heading.split(": ")]
    methods = []
    for piece in pieces:
        if invrow.norm(piece) in invrow.norm(text):
            methods.append("text")
        elif all(tok.strip(".,;:()") in invrow.norm(text) for tok in invrow.tokens(piece)):
            methods.append("text (loose)")
        else:
            raise ValueError(f"{t.key}: not on the page as quoted: {piece!r}")
    ans = page_text(t.file, t.answer_text_page)
    if invrow.norm(t.answer_text) not in invrow.norm(ans):
        if not all(tok.strip(".,;:()") in invrow.norm(ans)
                   for tok in invrow.tokens(t.answer_text)):
            raise ValueError(f"{t.key}: answer sentence not found: {t.answer_text!r}")
    return methods


# ================================================================== extracted CSVs

EXTRACT_COLUMNS = [
    "question", "table_id", "table_title", "source_file", "pdf_page", "row_order",
    "label_printed", "canonical", "coarse_unit", "label_rule_step", "label_evidence",
    "is_total", "column", "column_heading", "value_printed", "value", "window_start",
    "window_end", "as_on", "as_on_basis", "answer_date", "q4_role", "note"]


def extracted_rows(t: Table, read: Read | None = None) -> list[dict]:
    read = read or read_table(t)
    out = []
    for k, (lab, p, vals) in enumerate(read.rows, start=1):
        res = labels.resolve_or_list(lab)
        for c in t.columns:
            pv = vals[c.index]
            basis = "stated" if t.as_on else ("window_end" if c.wend else "bounded")
            out.append({
                "question": t.question, "table_id": t.table_id, "table_title": t.title,
                "source_file": t.file, "pdf_page": p, "row_order": k,
                "label_printed": lab, "canonical": res.canonical,
                "coarse_unit": states.coarsen(res.canonical) if res.canonical else "",
                "label_rule_step": res.step, "label_evidence": res.evidence,
                "is_total": "no", "column": c.key, "column_heading": c.heading,
                "value_printed": pv, "value": parse_int(pv),
                "window_start": c.wstart, "window_end": c.wend, "as_on": t.as_on,
                "as_on_basis": basis, "answer_date": t.answer_date, "q4_role": c.q4,
                "note": "; ".join([c.note] + ([t.exploratory] if t.exploratory
                                              and t.exploratory != c.note else []))})
    units = [r["canonical"] for r in out if r["column"] == t.columns[0].key]
    if len(set(units)) != len(units):
        raise ValueError(f"{t.key}: a State/UT appears twice")
    return out


def table_checks(t: Table, rows: list[dict]) -> list[dict]:
    """Printed-total check of every extracted column (none prints a total)."""
    out = []
    for c in t.columns:
        vals = [r["value"] for r in rows if r["column"] == c.key]
        rec = sc.total_check(vals, None)
        out.append({"table": t.check_name(c), "source_file": t.file,
                    "page": ";".join(str(p) for p in t.pages), "rows": len(vals),
                    **rec, "note": rec["note"] + "; the answer prints no total row "
                                                 "(text layer and page image)"})
    return out


# ================================================================== §9.6, §9.5.4

RECHECK: dict[str, str] = {
    "Q1216": (
        "Re-check at extraction (§9.5.4): the title, the column headings '2023 "
        "(Jan-Dec)', '2024 (Jan-Dec)', '2025 (Jan-Dec)' and 'Number of TB cases "
        "notified' are as in the masked reading (§9.5.1); the only note is 'Data Source: "
        "Ni-kshay (As on 06th February 2026)' (the masked day is the 6th). No note on a "
        "row; no note changes the window, cut-off or source of one State or of the whole "
        "table. Comparability (§9.5.1): (a) one table, one heading, one source and one "
        "as-on date; (b) full calendar years; (c) one as-on date for both years, 6 "
        "February 2026, 37 days after 31 December 2025 (within 60): holds as assumed. "
        "The answer text reads 'The Government has implemented TB Mukt Bharat Abhiyan "
        "(National TB Elimination Programme, under the aegis of National Health Mission "
        "(NHM) across the country.' (quoted for the guard of §9.5.2; nothing computed)"),
    "Q3467": (
        "Re-check at extraction (§9.5.4): the title and the 'TB patients notified' "
        "columns under '2023' and '2024*' are as in the masked reading (§9.5.2); no as-on "
        "date is stated. The only note, '*Treatment outcome will be due in 2025', marks "
        "the 2024 heading and concerns treatment outcome, not the notified count: it "
        "changes no window, cut-off or source. No note on a row."),
    "Q261": (
        "Re-check at extraction (§9.5.4): the title 'State/UT wise TB cases reported "
        "since 2022 to 2024*' carries an asterisk, but no footnote marked by it is "
        "printed on PDF pages 4-5 (text layer and page image both checked); the only "
        "note is 'Data source: Ni-kshay'. The table prints columns '2023' and '2024 (Jan- "
        "Oct)' only (no 2022 column). The answer text gives the window as 'current year "
        "(till 31.10.2024)'. No note changes the window, cut-off or source of one State "
        "or of the whole table: the S8 comparability conditions (§9.5.3: same quantity "
        "'TB cases reported' from Ni-kshay; 1 January-31 October; cut-off 0-43 days "
        "after 31 October) hold as assumed."),
    "Q1093": (
        "Re-check at extraction (§9.5.4): the title 'State/UT wise TB cases reported for "
        "2025 (Jan – Oct, 2025)', the column 'TB Cases reported' and the note 'Data "
        "source: Ni-kshay portal' are as in the masked reading; no as-on date is stated; "
        "no note on a row. The S8 comparability conditions (§9.5.3) hold as assumed "
        "(cut-off bounded by the answer date, 9 December 2025, 39 days after 31 October)."),
}


def q4_checks(reads: dict[str, list[dict]]) -> list[dict]:
    out = []
    for t in TABLES:
        if not t.source:
            continue
        rows = reads[t.key]
        cols = {c.key: [r["value"] for r in rows if r["column"] == c.key]
                for c in t.columns if c.q4}
        rec = sc.q4_extraction_check(t.source, cols, {k: None for k in cols},
                                     tuple(cols))
        out.append({**rec, "source_file": t.file,
                    "locator": f"{t.table_id}, PDF page(s) "
                               + ", ".join(str(p) for p in t.pages),
                    "role": t.role, "recheck_954": RECHECK[t.key]})
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


def build_inventory(reads: dict[str, list[dict]] | None = None
                    ) -> tuple[list[dict], list[dict]]:
    man = _manifest()
    rows, prov = [], []
    for t in TABLES:
        ext = reads[t.key] if reads else extracted_rows(t)
        _check_wording(t)
        url = man[t.file]["url"]
        for r in ext:
            col = next(c for c in t.columns if c.key == r["column"])
            if not col.inventory:
                continue
            step = int(r["label_rule_step"])
            notes = [f"State label printed as '{r['label_printed']}'; label rule step "
                     f"{step}: {r['label_evidence']}" if step > 1 else "",
                     col.note, t.exploratory if col.note != t.exploratory else "",
                     f"Q4 role: {col.q4}" if col.q4 else ""]
            inv = invrow.row(
                doc=t.doc, page=int(r["pdf_page"]), quantity=col.quantity,
                printed=r["value_printed"], unit=col.unit, definition=col.definition,
                source_file=t.file, source_url=url,
                page_or_para=f"PDF page {r['pdf_page']}; {t.table_id}",
                pub_date=t.answer_date, title=t.title, col=col.heading,
                rowlabel=r["label_printed"], geography=r["canonical"],
                table_id=f"{t.table_id}: {t.title}", period=col.period,
                wstart=col.wstart, wend=col.wend, as_on=t.as_on, notes=tuple(notes))
            rows.append(inv)
            prov.append({"kind": "figure", "fig_id": inv["fig_id"], "source_file": t.file,
                         "page": r["pdf_page"],
                         "method": invrow.verify([t.title, *col.heading.split(": "),
                                                  r["label_printed"]], r["value_printed"],
                                                 "\n".join(page_text(t.file, p)
                                                           for p in t.pages)),
                         "figures_found": ""})
    invrow.check_ids(rows)
    return rows, prov


SCOPE_RULE_PQ = (
    "Inventory scope of the parliamentary answers (§5.1, §5.3, §7.4). (1) The State "
    "tables of tb_cases that §7.4 names as pre-identified discrepancies (Questions 2511, "
    "1900, 1093, Lok Sabha 261, 1216, 3467) enter cell by cell, whether or not their "
    "titles name the campaign, because §7.4 enters and classifies them; Question 420 "
    "enters as the exploratory cross-check of §13 (18 November 2026). (2) Other columns "
    "of those tables enter as `other:` only when the table title names the campaign "
    "(TB Mukt Bharat Abhiyan), as in the campaign documents' rule 2. (3) Programme-wide "
    "figures in the answer text (WHO estimates, national notifications, incidence, "
    "deaths, finance, Ni-kshay Mitra) are not entered (campaign documents' rule 4). "
    "(4) A figure for a district or other sub-State area is not entered: the §5.2 "
    "geography field takes India or a State/UT.")

SCOPE_EXCLUSIONS: list[tuple[str, int, str, str, str, str]] = [
    ("Q3467", 3, "2023 Treated Successfully (36 cells)", "Annexure-I", "treatment outcome",
     "not a §5.1 quantity; not an ACF or campaign figure (rule 3)"),
    ("Q3467", 1, "17.7%; 237; 195; 21.4%; 28; 22; 2,90,887; 28.17 lakh; 11.93 lakh",
     "answer (a), (b)", "programme-wide", "epidemiology and Ni-kshay Mitra (rule 3)"),
    ("Q3467", 2, "1 per 1 lakh; 1 per 2 lakhs; 1 per 50,000; Rs. 750; Rs. 1,000",
     "answer (d)", "norm", "programme norms (rule 3)"),
    ("Q3467", 4, "Annexure-II (allocation and expenditure 2020-21 to 2024-25)",
     "Annexure-II", "finance", "not a §5.1 quantity (rule 3)"),
    ("Q2511", 2, "State/UT wise TB deaths^ in 2024 (Jan- Oct) (36 cells)", "Annexure",
     "deaths", "not a §5.1 quantity; not an ACF or campaign figure (rule 3)"),
    ("Q2511", 1, "200; 199; 195", "answer (a)-(c)", "background", "incidence (rule 3)"),
    ("Q261", 2, "17.7%; 237; 195; 21.4%; 28; 22", "statement", "background",
     "epidemiology (rule 3)"),
    ("Q261", 3, "3,574; 3,498", "statement, Amroha district", "sub-State",
     "district figures (rule 4)"),
    ("Q261", 3, "68%; 75%", "statement, DR-TB treatment success", "programme-wide",
     "treatment outcome (rule 3)"),
    ("Q1093", 1, "27.1 lakh; 21.7 lakh; 3 lakh", "question and answer (a)-(c)",
     "background", "WHO estimates (rule 3)"),
    ("Q1900", 1, "21%; 237; 187; 53%; 92%; 16.07 lakh; 26.18 lakh", "answer (a)-(c)",
     "programme-wide", "WHO estimates and national notifications not given as campaign "
     "or ACF figures (rule 3)"),
    ("Q1216", 1, "₹1000; 3 months", "answer (a)-(c)", "norm", "benefit norms (rule 3)"),
    ("Q420", 1, "21%; 237; 187; Rs 1,000", "answer (a)-(e)", "background",
     "incidence and benefit norm (rule 3)"),
    ("Q420", 4, "Annexure-II parts A and B; Annexure-III", "Annexures II-III", "finance",
     "grants and Ni-kshay Poshan Yojana expenditure: not §5.1 quantities (rule 3)"),
    ("Q3477", 1, "none", "whole answer (pages 1-2)", "no figure",
     "the answer describes MSME roles in the campaign and prints no figure of a §5.1 "
     "quantity; read for the inventory as §5.3 requires"),
]


def scope_decisions() -> list[dict]:
    files = {t.key: t.file for t in TABLES} | {"Q3477": PQ + "AU3477_SSspdQ.pdf"}
    out = [{"kind": "rule", "doc": "parliamentary answers", "source_file": PQ,
            "page": "", "figures": "", "where": "", "category": "", "decision": "",
            "reason": SCOPE_RULE_PQ}]
    for doc, p, figs, where, cat, why in SCOPE_EXCLUSIONS:
        out.append({"kind": "exclusion", "doc": doc, "source_file": files[doc],
                    "page": p, "figures": figs, "where": where, "category": cat,
                    "decision": "not entered", "reason": why})
    out.append({"kind": "not used", "doc": "Q3001", "source_file": PQ + "AU3001_ZXEQ3g.pdf",
                "page": "", "figures": "", "where": "", "category": "",
                "decision": "not read",
                "reason": "Not used (§3.1.2, §9.5.5): drug-resistant TB; digest verified "
                          "only"})
    return out


# ================================================================== write

def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def merge_by_source(path: Path, own: list[dict], own_files: set[str],
                    fields: list[str]) -> list[dict]:
    """Rows of other extractors are kept as they are; this extractor's rows (by
    source_file) replace its own earlier rows."""
    kept = []
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            kept = [r for r in csv.DictReader(f) if r["source_file"] not in own_files]
    return kept + [{k: r.get(k, "") for k in fields} for r in own]


CHECK_COLUMNS = ["table", "source_file", "page", "rows", "sum_of_rows", "printed_total",
                 "difference", "pass", "note"]
SCOPE_COLUMNS = ["kind", "doc", "source_file", "page", "figures", "where", "category",
                 "decision", "reason"]
Q4_COLUMNS = ["source", "source_file", "locator", "role", "needed_columns",
              "column_check", "sum_check", "result", "note", "recheck_954"]


def run() -> dict[str, list[dict]]:
    reads = {t.key: extracted_rows(t) for t in TABLES}
    for t in TABLES:
        write_csv(EXTRACTED / t.csv_name, EXTRACT_COLUMNS, reads[t.key])
    return reads


def main() -> int:
    from src.extract.campaign import INVENTORY_COLUMNS
    verify_inputs()
    reads = run()
    checks = [c for t in TABLES for c in table_checks(t, reads[t.key])]
    path = EXTRACTED / "table_total_checks.csv"
    write_csv(path, CHECK_COLUMNS,
              merge_by_source(path, checks, {t.file for t in TABLES}, CHECK_COLUMNS))
    inv, prov = build_inventory(reads)
    write_csv(INVENTORY, INVENTORY_COLUMNS,
              merge_by_source(INVENTORY, inv, set(OWN_FILES), INVENTORY_COLUMNS))
    write_csv(EXTRACTED / "pq_inventory_provenance.csv",
              ["kind", "fig_id", "source_file", "page", "method", "figures_found"], prov)
    sp = EXTRACTED / "inventory_scope_decisions.csv"
    own_scope = scope_decisions()
    write_csv(sp, SCOPE_COLUMNS,
              merge_by_source(sp, own_scope, {r["source_file"] for r in own_scope},
                              SCOPE_COLUMNS))
    q4 = q4_checks(reads)
    print(f"parliamentary tables: {len(TABLES)}; inventory rows: {len(inv)}")
    for r in q4:
        print("Q4 check:", r["source"], r["result"], "|", r["sum_check"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
