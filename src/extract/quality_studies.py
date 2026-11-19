"""The two quality studies of analysis plan §7.5: published indicators with their stated
denominators, for the reconciliation of Task 5 (nothing is computed here).

- Shewade HD et al., *Global Health Action* 2023 (PMC10515680): Tables 1 and 2 of the
  full text (read online 19 Nov 2026; transcribed by hand into
  data/transcribed/quality_studies_tables.csv) and the supplement S1/S2 annexes
  (data_raw/studies/ZGHA_A_2256129_SM2351.docx, SHA-256 verified, read with zipfile and
  xml.etree). S1 gives the national counts behind Table 1's percentages, so the Figshare
  dataset is not used.
- Shewade HD et al., *PLOS Global Public Health* 2025 (PMC12574901): Tables 2 and 3 of
  the full text, transcribed likewise. The supporting files S1-S2 and the record-level
  file were not downloaded (author decision).

Outputs: data/extracted/quality_studies.csv (every cell) and the studies' headline
figures in data/figures_inventory.csv (other extractors' rows are kept; only the rows
whose source_file is one of this module's three sources are replaced).

Run: python -I src/extract/quality_studies.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import csv
import functools
import re
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal

from src import inventory_rules as R
from src import states
from src.extract import invrow, labels
from src.extract.campaign import INVENTORY_COLUMNS

ROOT = Path(__file__).resolve().parents[2]
EXTRACTED = ROOT / "data/extracted"
INVENTORY = ROOT / "data/figures_inventory.csv"
TRANSCRIBED = ROOT / "data/transcribed/quality_studies_tables.csv"
ACCESSED = "2026-11-19"

GHA_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC10515680/"
PG_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC12574901/"
SUPP = "data_raw/studies/ZGHA_A_2256129_SM2351.docx"
OWN_FILES = frozenset({GHA_URL, PG_URL, SUPP})
GHA_PUB, PG_PUB = "2023-09-21", "2025-10-30"

QS_COLUMNS = [
    "study", "table_id", "table_title", "row_group", "row_label", "geography",
    "quantity", "column_label", "printed_value", "value", "unit",
    "denominator_stated", "denominator_methods", "source", "locator", "accessed",
    "derivation", "note"]

GHA_T1 = "State-wise TB ACF quality indicators derived for TB ACF cycle (first cycle)* in 2021, India."
GHA_T2 = ("TB ACF quality indicators derived for each high-risk population during TB ACF "
          "cycle (first cycle)* in 2021, India.")
S1_TITLE = ("S1 Annex: State wise total population screened, tested and diagnosed during "
            "TB ACF cycle (first cycle)* in 2021, India")
S2_TITLE = ("S2 Annex: State wise total public notified TB cases and the TB ACF-detected "
            "cases in 2021, India.")
PG_T2 = ("Quality indicators in the TB ACF cycle conducted from January to September 2023 "
         "in 30 randomly sampled NTEP districts of India, overall and stratified by gender, "
         "age, residence, and type of high-risk groups (broad categories).")
PG_T3 = ("Use of rapid molecular diagnostic test among ACF-detected presumptive TB who "
         "were tested in 30 randomly sampled NTEP districts of India, January to September "
         "2023, overall and stratified by gender, age, residence and type of high-risk "
         "groups (broad categories).")
TITLES = {("GHA2023", "Table 1"): GHA_T1, ("GHA2023", "Table 2"): GHA_T2,
          ("PGPH2025", "Table 2"): PG_T2, ("PGPH2025", "Table 3"): PG_T3,
          ("GHA2023SM", "S1 Annex"): S1_TITLE, ("GHA2023SM", "S2 Annex"): S2_TITLE}

# Methods wording of each study, quoted (GHA: Methods, "Statistical analysis"; PGPH:
# Methods, "Data management and analysis").
GHA_M = {
    "pct_screened": "Percentage screened among district’s population – at least 10%",
    "pct_tested": "Percentage tested among screened – at least 4.75%",
    "pct_diagnosed": "Percentage diagnosed (microbiologically/clinically) among tested – "
                     "at least 5%",
    "nns": "It is the number of persons who must undergo screening to diagnose one person "
           "with active TB",
    "acf_share": "of the 1.44 million TB notified from the public sector were reported as "
                 "ACF-detected",
}
PG_M = {
    "pct_screened": "percentage of mapped population screened in the ACF cycle (≥90%)",
    "pct_presumptive": "percentage of screened identified as presumptive TB (≥5%)",
    "pct_tested": "percentage of presumptive TB tested (≥95%)",
    "pct_diagnosed": "percentage of tested diagnosed as TB (test positivity ≥5%)",
    "nns": "NNS (number screened divided by number diagnosed)",
}

# (study, table, column label) -> (quantity, kind, unit, methods key)
COLS = {
    ("GHA2023", "Table 1", "% Screened among population** (at least 10%)"):
        ("pct_screened", "pct", "percent", GHA_M["pct_screened"]),
    ("GHA2023", "Table 1", "% Tested among screened (at least 4.75%)"):
        ("pct_tested", "pct", "percent", GHA_M["pct_tested"]),
    ("GHA2023", "Table 1", "% Diagnosed among tested (at least 5%)"):
        ("pct_diagnosed", "pct", "percent", GHA_M["pct_diagnosed"]),
    ("GHA2023", "Table 1", "NNS (max. 1538)"): ("nns", "num", "ratio", GHA_M["nns"]),
    ("GHA2023", "Table 2", "Number screened"): ("screened", "num", "persons", ""),
    ("GHA2023", "Table 2", "Number tested"): ("tested", "num", "persons", ""),
    ("GHA2023", "Table 2", "% Tested"): ("pct_tested", "pct", "percent", GHA_M["pct_tested"]),
    ("GHA2023", "Table 2", "Number diagnosed"): ("diagnosed", "num", "persons", ""),
    ("GHA2023", "Table 2", "% Diagnosed"):
        ("pct_diagnosed", "pct", "percent", GHA_M["pct_diagnosed"]),
    ("GHA2023", "Table 2", "NNS"): ("nns", "num", "ratio", GHA_M["nns"]),
    ("PGPH2025", "Table 2", "Screened n (%)col"): ("screened", "npct", "persons", ""),
    ("PGPH2025", "Table 2", "Presumptive TB n (%)row"):
        ("presumptive", "npct", "persons", PG_M["pct_presumptive"]),
    ("PGPH2025", "Table 2", "Tested n (%)row"):
        ("tested", "npct", "persons", PG_M["pct_tested"]),
    ("PGPH2025", "Table 2", "Diagnoseda n (%)row"):
        ("diagnosed", "npct", "persons", PG_M["pct_diagnosed"]),
    ("PGPH2025", "Table 2", "NNS"): ("nns", "num", "ratio", PG_M["nns"]),
    ("PGPH2025", "Table 3", "Tested N"): ("tested", "num", "persons", ""),
    ("PGPH2025", "Table 3", "Rapid molecular diagnostic test n (%)row"):
        ("rapid_test", "npct", "tests", ""),
}
PCT_NAME = {"screened": "pct_screened_col", "presumptive": "pct_presumptive",
            "tested": "pct_tested", "diagnosed": "pct_diagnosed",
            "rapid_test": "pct_rapid_test"}
FOOTNOTE = {"col": "col column percentage", "row": "row row percentage"}


# ============================================================ transcription and cells

def read_transcribed() -> list[dict]:
    with open(TRANSCRIBED, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


_CELL = re.compile(r"^\s*(\d[\d ]*?)\s*(?:[a-z]\s*)?\(\s*(<?\d+(?:\.\d+)?)\s*\)\s*[a-z]*\s*$")


def parse_cell(cell: str) -> tuple[str, str]:
    """(number as printed, percentage as printed): '117 a (1.6)' -> ('117', '1.6');
    '4971' -> ('4971', ''). Footnote letters are dropped; ValueError for a blank or an
    unreadable cell."""
    c = cell.strip()
    if not c:
        raise ValueError("blank cell")
    if "(" not in c:
        return c, ""
    m = _CELL.match(c)
    if not m:
        raise ValueError(f"unreadable cell: {cell!r}")
    return m.group(1), m.group(2)


def _value(printed: str) -> str:
    """The figure as a number (string); blank for '<0.1' and dashes (§5.2)."""
    t = printed.strip().rstrip("%").lstrip("≈~").strip()
    if not re.fullmatch(r"\d[\d ,]*(?:\.\d+)?(?: (?:million|lakh|crore))?", t):
        return ""
    mult = {"million": 10**6, "lakh": 10**5, "crore": 10**7}
    m = re.fullmatch(r"([\d ,.]+?)(?: (million|lakh|crore))?", t)
    num = Decimal(m.group(1).replace(" ", "").replace(",", ""))
    if m.group(2):
        return str(int(num * mult[m.group(2)]))
    return str(int(num)) if "." not in m.group(1) else str(num)


# ============================================================ supplement (docx)

@functools.cache
def _manifest() -> dict[str, dict]:
    sys.path.insert(0, str(ROOT))
    from tools.fetch_sources import read_manifest
    return {r["file"]: r for r in read_manifest()}


def verify_inputs() -> None:
    sys.path.insert(0, str(ROOT))
    from tools.fetch_sources import verify
    verify(ROOT / SUPP, _manifest()[SUPP]["sha256"])


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def read_supplement() -> tuple[list[list[str]], list[list[str]]]:
    """Rows (header excluded) of the S1 and S2 annex tables of the GHA supplement."""
    verify_inputs()
    with zipfile.ZipFile(ROOT / SUPP) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    tables = []
    for tb in root.iter(_W + "tbl"):
        tables.append([[re.sub(r"\s+", " ", "".join(x.text or "" for x in tc.iter(_W + "t"))
                               ).strip() for tc in tr.findall(_W + "tc")]
                       for tr in tb.iter(_W + "tr")])
    s1, s2 = tables[0], tables[1]
    assert s1[0][:3] == ["State", "Total population**", "Number screened"], s1[0]
    assert s2[0][:2] == ["State", "Public notified TB (from 2022 India TB report)"], s2[0]
    return s1[1:], s2[1:]


S1_COLS = [("Total population**", "population", "persons"),
           ("Number screened", "screened", "persons"),
           ("Number tested among screened", "tested", "persons"),
           ("Number diagnosed among tested", "diagnosed", "persons")]
S2_COLS = [("Public notified TB (from 2022 India TB report)", "public_notified", "cases"),
           ("TB ACF cases diagnosed among tested (reported as ACF-detected)", "diagnosed",
            "cases"),
           ("%", "acf_share", "percent")]


# ============================================================ quality_studies.csv

def _geo(label: str) -> tuple[str, str]:
    """(geography, note) by the label rule of §9.2: step 2 resolutions are noted with
    their evidence; step 3 gives a blank geography, a note, and the row is listed as
    not computable (same behaviour as the campaign extractor)."""
    if label == "INDIA":
        return "India", ""
    r = labels.resolve_or_list(label)
    if r.step == 1:
        return r.canonical, ""
    if r.step == 2:
        return r.canonical, (f"State label printed as '{label}'; label rule step 2: "
                             f"{r.evidence}")
    return "", f"State not computable (label rule step 3): {r.evidence}"


def _qrow(**kw) -> dict:
    r = dict.fromkeys(QS_COLUMNS, "")
    r.update(kw)
    r["accessed"] = ACCESSED
    return r


def build_quality() -> list[dict]:
    rows: list[dict] = []
    # ---- full-text tables (transcribed)
    for t in read_transcribed():
        study, table, col, cell = t["study"], t["table_id"], t["column_label"], t["printed_cell"]
        quantity, kind, unit, meth = COLS[(study, table, col)]
        title = TITLES[(study, table)]
        grp, lab = t["row_group"], t["row_label"]
        row_txt = lab if lab else grp
        loc = f"{table}, row '{row_txt}'" + (f" (group '{grp}')" if grp and lab else "") \
            + f", column '{col}'"
        geo, gnote = (_geo(lab) if (table == "Table 1" and lab) else ("India", ""))
        base = dict(study=study, table_id=table, table_title=title, row_group=grp,
                    row_label=lab, geography=geo, column_label=col, source=t["url"],
                    locator=loc)
        n, pct = parse_cell(cell)
        if kind == "pct":
            stated = col if " among " in col else ""
            notes = []
            rows.append(_qrow(**base, quantity=quantity, printed_value=cell,
                              value=_value(cell), unit=unit,
                              denominator_stated=stated, denominator_methods=meth,
                              derivation="printed", note="; ".join(
                                  notes + ([] if stated else
                                           ["the table's column heading states no denominator"]))))
            continue
        notes = []
        dstate = ""
        if kind == "npct":
            m = re.search(r"\)(col|row)$", col)
            dstate = f"{col}; {FOOTNOTE[m.group(1)]}"
        if quantity == "nns" and cell.strip() == "0":
            notes.append("printed 0 where no one was diagnosed (NNS undefined)")
        if quantity == "nns" and cell.strip() == "–":
            notes.append("printed as a dash")
        if "<" in pct:
            notes.append(f"percentage printed '{pct}'; no parsed value")
        if "Diagnoseda" in col:
            notes.append("column heading prints 'Diagnoseda': heading 'Diagnosed' with "
                         "footnote a (all ACF-detected TB were initiated on treatment)")
        rows.append(_qrow(**base, quantity=quantity, printed_value=n if kind == "npct" else cell,
                          value=_value(n), unit=unit, denominator_stated="" if kind == "num"
                          else (dstate if quantity != "screened" else ""),
                          denominator_methods="" if kind == "num" else
                          (meth if quantity != "screened" else ""),
                          derivation="printed" if kind == "num" else "parsed from printed cell",
                          note="; ".join(notes)))
        if kind == "npct":
            pq = PCT_NAME[quantity]
            pnotes = [f"printed together with the count in one cell: '{cell}'"]
            if "<" in pct:
                pnotes.append("printed '<0.1': no parsed value")
            rows.append(_qrow(**base, quantity=pq, printed_value=pct, value=_value(pct),
                              unit="percent", denominator_stated=dstate,
                              denominator_methods=meth if quantity != "screened" else "",
                              derivation="parsed from printed cell", note="; ".join(pnotes)))
    for r in rows:
        if r["table_id"] == "Table 1" and r["study"] == "GHA2023" and r["row_label"] != "INDIA":
            extra = [_geo(r["row_label"])[1]]
            if not re.search(r"\d", r["printed_value"]):
                extra.append("no value printed")
            r["note"] = "; ".join(x for x in [r["note"]] + extra if x)
    # ---- supplement S1, S2 (docx)
    s1, s2 = read_supplement()
    for table, data, cols in (("S1 Annex", s1, S1_COLS), ("S2 Annex", s2, S2_COLS)):
        for r in data:
            geo, gnote = _geo(r[0])
            for i, (col, quantity, unit) in enumerate(cols, start=1):
                if i >= len(r) or not re.fullmatch(r"\d[\d.]*", r[i]):
                    if i == 1 and len(r) >= 2 and not re.fullmatch(r"\d[\d.]*", r[1]):
                        rows.append(_qrow(
                            study="GHA2023SM", table_id=table,
                            table_title=TITLES[("GHA2023SM", table)], row_label=r[0],
                            geography=geo, quantity=quantity, column_label=col,
                            printed_value=r[-1], value="", unit=unit, source=SUPP,
                            locator=f"{table} table, row '{r[0]}', column '{col}'",
                            derivation="printed",
                            note="; ".join(x for x in (gnote, "no value printed") if x)))
                    continue
                stated = col if " among " in col else ""
                meth = GHA_M["acf_share"] if quantity == "acf_share" else ""
                qn = "pct_acf_share" if quantity == "acf_share" else quantity
                note = gnote
                if quantity == "acf_share":
                    note = "; ".join(x for x in (gnote, "the column heading is '%'; "
                                                 "no denominator stated in the table") if x)
                rows.append(_qrow(
                    study="GHA2023SM", table_id=table,
                    table_title=TITLES[("GHA2023SM", table)], row_label=r[0],
                    geography=geo, quantity=qn, column_label=col, printed_value=r[i],
                    value=_value(r[i]), unit=unit, denominator_stated=stated,
                    denominator_methods=meth, source=SUPP,
                    locator=f"{table} table, row '{r[0]}', column '{col}'",
                    derivation="printed", note=note))
    return rows


# ============================================================ inventory rows

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _ctx_cell(title: str, col: str, row: str) -> str:
    return " | ".join((title, col, row))


def _inv(*, doc, loc, row, col, quantity, printed, unit, definition, context, source_file,
         page, table_id="", period="", wstart="", wend="", pub, note="", prose=False,
         occurrence=1, geography="India", value=None) -> dict:
    man = _manifest() if source_file == SUPP else None
    url = man[source_file]["url"] if man else source_file
    qual = R.qualifier(context, printed, occurrence) if prose else "exact"
    dcls, dkw = R.definition_class(quantity, definition)
    scope, skw, snote = R.scope(context)
    notes = []
    if dcls:
        notes.append(f"definition_class keyword: '{dkw}'" if dkw
                     else "definition_class: no keyword matched")
    notes.append(f"scope keyword: '{skw}'" if skw else "scope: no keyword matched")
    if snote:
        notes.append(snote)
    if not prose:
        notes.append("table cell: no qualifier words, so exact; context is table title | "
                     "column heading | row label (§5.2)")
    if note:
        notes.append(note)
    basis = invrow.as_on_basis("")
    key = ".".join(x for x in (doc, _slug(loc), _slug(row), _slug(col),
                               quantity.replace(":", "_")) if x)
    return {
        "fig_id": key, "quantity": quantity,
        "value": _value(printed) if value is None else value,
        "value_printed": printed, "qualifier": qual, "unit": unit,
        "definition_verbatim": definition, "context_verbatim": context,
        "definition_class": dcls, "scope": scope, "series_type": "period",
        "window_label": R.window_label(context, period, bool(wend)),
        "window_start": wstart, "window_end": wend, "as_on": "", "as_on_basis": basis,
        "geography": geography, "source_file": source_file, "source_url": url,
        "page_or_para": page, "table_id": table_id, "pub_date": pub,
        "note": "; ".join(notes)}


READ = ("table cell transcribed from the HTML full text read online on 2026-11-19 (nothing "
        "saved; data/transcribed/quality_studies_tables.csv)")
PROSE = ("sentence copied verbatim from the PMC BioC JSON text of the article "
         "(https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json/{pmc}"
         "/unicode, read 2026-11-19), thin and no-break spaces read as spaces")
FIRST = "first cycle in 2021"
PGW = dict(wstart="2023-01-01", wend="2023-09-30")
PGNOTE = ("the study period (January-September 2023) is stated in the paper's abstract "
          "and table captions, not in this sentence")


def _pnote(pmc: str, extra: str = "") -> str:
    return PROSE.format(pmc=pmc) + ("; " + extra if extra else "")


def _gha_specs() -> list[dict]:
    S = []
    T = read_transcribed()
    # Table 1: INDIA row (all four columns) and State NNS
    for t in T:
        if t["study"] != "GHA2023" or t["table_id"] != "Table 1":
            continue
        col, row = t["column_label"], t["row_label"]
        if not re.fullmatch(r"\d+(?:\.\d+)?", t["printed_cell"]):
            continue                      # Puducherry: "No ACF Data Available"
        q, unit = {"% Screened among population** (at least 10%)":
                   ("other:pct_population_screened", "percent"),
                   "% Tested among screened (at least 4.75%)":
                   ("other:pct_tested_among_screened", "percent"),
                   "% Diagnosed among tested (at least 5%)":
                   ("other:pct_diagnosed_among_tested", "percent"),
                   "NNS (max. 1538)": ("nns", "ratio")}[col]
        geo, gnote = _geo(row)
        S.append(dict(doc="GHA2023", loc="T1", row=row, col=col, quantity=q,
                      printed=t["printed_cell"], unit=unit, definition=col,
                      context=_ctx_cell(GHA_T1, col, row), source_file=GHA_URL,
                      page=f"Table 1, row {row}", table_id="Table 1", period=FIRST,
                      pub=GHA_PUB, geography=geo,
                      note="; ".join(x for x in (READ, gnote) if x)))
    # prose: Abstract, Results, Frequency
    pm = "PMC10515680"
    prose = [
        ("abs", "Abstract, Results", "first ACF cycle",
         "At the national level, for the first ACF cycle, 9.3% of the population were "
         "screened, 1% of the screened were tested and 3.7% of the tested were diagnosed.",
         [("other:pct_population_screened", "9.3%", "percent",
           "of the population were screened"),
          ("other:pct_tested_among_screened", "1%", "percent",
           "of the screened were tested"),
          ("other:pct_diagnosed_among_tested", "3.7%", "percent",
           "of the tested were diagnosed")]),
        ("abs", "Abstract, Results", "",
         "The NNS was 2824: acceptable (≤1538) in institutional facilities and poor for "
         "population-based groups.", [("nns", "2824", "ratio", "NNS")]),
        ("res", "Results, 'ACF quality indicators: national and state level'", "",
         "At the national level, 9.3% of the population got screened, 1% screened got "
         "tested, and 3.7% of those tested got diagnosed with TB.",
         [("other:pct_population_screened", "9.3%", "percent",
           "of the population got screened"),
          ("other:pct_tested_among_screened", "1%", "percent", "screened got tested"),
          ("other:pct_diagnosed_among_tested", "3.7%", "percent",
           "of those tested got diagnosed with TB")]),
        ("res", "Results, 'ACF quality indicators: national and state level'", "",
         "The NNS was 2824.", [("nns", "2824", "ratio", "NNS")]),
        ("freq", "Results, 'Frequency of ACF'", "",
         "2.9% (n = 41 306) of the 1.44 million TB notified from the public sector were "
         "reported as ACF-detected (see S1 and S2 Annex).",
         [("acf_share_notifications", "2.9%", "percent",
           "of the 1.44 million TB notified from the public sector were reported as "
           "ACF-detected"),
          ("tb_cases", "41 306", "cases", "reported as ACF-detected"),
          ("other:public_sector_tb_notified", "1.44 million", "cases",
           "TB notified from the public sector")]),
    ]
    for loc, page, period, sent, items in prose:
        for q, printed, unit, defn in items:
            S.append(dict(doc="GHA2023", loc=loc, row="", col="sentence", quantity=q,
                          printed=printed, unit=unit, definition=defn, context=sent,
                          source_file=GHA_URL, page=page, pub=GHA_PUB, prose=True,
                          period=period, note=_pnote(
                              pm, "no cycle dates stated in the sentence")))
    # supplement S1 and S2: INDIA and State rows
    s1, s2 = read_supplement()
    snote = ("read from the supplement (docx, SHA-256 verified); the supplement has no "
             "printed date, so pub_date is the article's")
    for r in s1:
        if not re.fullmatch(r"\d+", r[1] if len(r) > 1 else ""):
            continue
        geo, gnote = _geo(r[0])
        for i, (col, qn, unit) in enumerate((
                ("Total population**", "other:population_in_districts_with_acf_data",
                 "persons"),
                ("Number screened", "screened", "persons"),
                ("Number tested among screened", "tested", "persons"),
                ("Number diagnosed among tested", "tb_cases", "cases")), start=1):
            S.append(dict(doc="GHA2023SM", loc="S1", row=r[0], col=col, quantity=qn,
                          printed=r[i], unit=unit, definition=col,
                          context=_ctx_cell(S1_TITLE, col, r[0]), source_file=SUPP,
                          page=f"S1 Annex table, row {r[0]}", table_id="S1 Annex",
                          period=FIRST, pub=GHA_PUB, geography=geo,
                          note="; ".join(x for x in (snote, gnote) if x)))
    for r in s2:
        if not re.fullmatch(r"\d+", r[1] if len(r) > 1 else ""):
            continue
        geo, gnote = _geo(r[0])
        for i, (col, qn, unit) in enumerate((
                ("Public notified TB (from 2022 India TB report)",
                 "other:public_sector_tb_notified", "cases"),
                ("TB ACF cases diagnosed among tested (reported as ACF-detected)",
                 "tb_cases", "cases"),
                ("%", "acf_share_notifications", "percent")), start=1):
            S.append(dict(doc="GHA2023SM", loc="S2", row=r[0], col=col, quantity=qn,
                          printed=r[i], unit=unit, definition=col,
                          context=_ctx_cell(S2_TITLE, col, r[0]), source_file=SUPP,
                          page=f"S2 Annex table, row {r[0]}", table_id="S2 Annex",
                          period="2021", pub=GHA_PUB, geography=geo,
                          note="; ".join(x for x in (snote, gnote) if x)))
    return S


def _pg_specs() -> list[dict]:
    S = []
    T = {(t["table_id"], t["row_label"] or t["row_group"], t["column_label"]):
         t["printed_cell"] for t in read_transcribed() if t["study"] == "PGPH2025"}
    per = "january to september 2023"
    t2 = [("Screened n (%)col", "screened", "persons", "Screened n (%)col", None),
          ("Presumptive TB n (%)row", "presumptive", "persons", "Presumptive TB n (%)row",
           "other:pct_presumptive_among_screened"),
          ("Tested n (%)row", "tested", "persons", "Tested n (%)row",
           "other:pct_tested_among_presumptive"),
          ("Diagnoseda n (%)row", "tb_cases", "cases", "Diagnosed n (%)row",
           "other:pct_diagnosed_among_tested")]
    for col, q, unit, defn, pq in t2:
        n, pct = parse_cell(T[("Table 2", "Total", col)])
        ctx = _ctx_cell(PG_T2, col, "Total")
        S.append(dict(doc="PGPH2025", loc="T2", row="Total", col=col, quantity=q,
                      printed=n, unit=unit, definition=defn, context=ctx,
                      source_file=PG_URL, page="Table 2, row Total", table_id="Table 2",
                      period=per, pub=PG_PUB, note=READ, **PGW))
        if pq:
            S.append(dict(doc="PGPH2025", loc="T2", row="Total", col=col, quantity=pq,
                          printed=pct, unit="percent", definition=defn, context=ctx,
                          source_file=PG_URL, page="Table 2, row Total", table_id="Table 2",
                          period=per, pub=PG_PUB, note=READ + "; percentage printed "
                          "in the same cell as the count", **PGW))
    S.append(dict(doc="PGPH2025", loc="T2", row="Total", col="NNS", quantity="nns",
                  printed=T[("Table 2", "Total", "NNS")], unit="ratio", definition="NNS",
                  context=_ctx_cell(PG_T2, "NNS", "Total"), source_file=PG_URL,
                  page="Table 2, row Total", table_id="Table 2", period=per, pub=PG_PUB,
                  note=READ, **PGW))
    rc = "Rapid molecular diagnostic test n (%)row"
    n, pct = parse_cell(T[("Table 3", "Total", rc)])
    for q, p, unit in (("other:rapid_molecular_tests_used", n, "tests"),
                       ("other:pct_rapid_molecular_among_tested", pct, "percent")):
        S.append(dict(doc="PGPH2025", loc="T3", row="Total", col=rc, quantity=q, printed=p,
                      unit=unit, definition="Rapid molecular diagnostic test n (%)row",
                      context=_ctx_cell(PG_T3, rc, "Total"), source_file=PG_URL,
                      page="Table 3, row Total", table_id="Table 3", period=per,
                      pub=PG_PUB, note=READ, **PGW))
    pm = "PMC12574901"
    note = _pnote(pm, PGNOTE)

    def prose(loc, page, sent, items):
        for q, p, unit, defn in items:
            S.append(dict(doc="PGPH2025", loc=loc, row="", col="sentence", quantity=q,
                          printed=p, unit=unit, definition=defn, context=sent,
                          source_file=PG_URL, page=page, pub=PG_PUB, prose=True,
                          note=note, **PGW))

    def restate(loc, page, sent, items, cites, period=""):
        """Figures of this paper that restate another study's results (no cycle dates)."""
        for q, p, unit, defn, val in items:
            S.append(dict(doc="PGPH2025", loc=loc, row="", col="sentence", quantity=q,
                          printed=p, unit=unit, definition=defn, context=sent,
                          source_file=PG_URL, page=page, pub=PG_PUB, prose=True,
                          period=period, value=val,
                          note=_pnote(pm, f"restates {cites}; the sentence does not give "
                                      "the cycle dates")))

    gha = "Shewade et al. GHA 2023 (S1 Table of this paper)"
    restate("intro-2021", "Introduction",
            "Though ≈9% (revised target 10% for scale) of district population was reported "
            "to be screened, we were not sure whether these were high-risk populations.",
            [("other:pct_population_screened", "≈9%", "percent",
              "of district population was reported to be screened", None)], gha)
    restate("disc-2021-screened", "Discussion, 'Comparison with previous evidence'",
            "First, in 2021, based on secondary aggregate Ni-kshay data, nearly nine percent "
            "(cut-off 10%) of the population was reported to be screened indicating "
            "acceptable scale (S1 Table).",
            [("other:pct_population_screened", "nine percent", "percent",
              "of the population was reported to be screened", "9")], gha, "2021")
    restate("disc-2021-tested", "Discussion, 'Comparison with previous evidence'",
            "Second, in 2021, 1% of screened were tested against the target of 4.75% "
            "(S1 Table).",
            [("other:pct_tested_among_screened", "1%", "percent",
              "of screened were tested", None)], gha, "2021")
    prose("disc-mapped-observed", "Discussion, 'Comparison with previous evidence'",
          "Even if we assume that the ACF tool was used in all ACF days and the mapped "
          "high-risk population was reduced to 11% (instead of 18.3% observed), the "
          "estimated scale of ACF will increase only to 17.5%, still way lower than the "
          "target of 90%.",
          [("other:pct_population_mapped_high_risk", "18.3%", "percent",
            "instead of 18.3% observed")])

    # Abstract
    prose("abs-screened", "Abstract",
          "581 633 high-risk individuals were screened by the program utilizing existing "
          "workforce and resources.",
          [("screened", "581 633", "persons", "high-risk individuals were screened")])
    prose("abs-scale", "Abstract",
          "The two scale indicators (target, observed) were: percentage of i) population "
          "mapped as high-risk (≥11%, 18.3%) and ii) mapped population screened "
          "(≥90%, 7.4%).",
          [("other:pct_population_mapped_high_risk", "18.3%", "percent",
            "population mapped as high-risk"),
           ("other:pct_mapped_population_screened", "7.4%", "percent",
            "mapped population screened")])
    prose("abs-quality", "Abstract",
          "The four quality indicators (target, observed) were: percentage of i) screened "
          "identified as presumptive TB (≥5%, 2%) ii) presumptive TB tested (≥95%, 66.3%) "
          "iii) tested diagnosed as TB (≥5%, 1.6%) and iv) diagnosed put on treatment "
          "(≥95%, 100%).",
          [("other:pct_presumptive_among_screened", "2%", "percent",
            "screened identified as presumptive TB"),
           ("other:pct_tested_among_presumptive", "66.3%", "percent",
            "presumptive TB tested"),
           ("other:pct_diagnosed_among_tested", "1.6%", "percent",
            "tested diagnosed as TB"),
           ("other:pct_diagnosed_put_on_treatment", "100%", "percent",
            "diagnosed put on treatment")])
    prose("abs-nns", "Abstract",
          "The number needed to screen (target ≤1538 considering the algorithm) to detect "
          "one person with TB was 4971.",
          [("nns", "4971", "ratio", "number needed to screen")])
    prose("abs-rapid", "Abstract",
          "The extent of using rapid molecular diagnostic tests was 26.4% and the median "
          "time taken from screening to sputum collection and testing was one day.",
          [("other:pct_rapid_molecular_among_tested", "26.4%", "percent",
            "extent of using rapid molecular diagnostic tests")])
    # Results
    res = "Results, first paragraph of 'Scale and quality indicators'"
    prose("res-population", res,
          "The total population of 30 districts was 57 211 032.",
          [("other:population_30_districts", "57 211 032", "persons",
            "total population of 30 districts")])
    prose("res-mapped", res,
          "A total of 10 449 555 (18.3%) were mapped as high-risk, 75% of which "
          "(n = 7 837 170) were considered as denominator for further analysis.",
          [("other:high_risk_population_mapped", "10 449 555", "persons",
            "were mapped as high-risk"),
           ("other:pct_population_mapped_high_risk", "18.3%", "percent",
            "were mapped as high-risk")])
    s3 = ("During the 1031 ACF activity days considered in the analysis, of the 7 837 170 "
          "high-risk population, 581 633 (7.4%, 95% CI: 7.42. 7.44) were screened (an "
          "average of 565 people screened per district per ACF activity day).")
    prose("res-screened", res, s3,
          [("other:high_risk_population_denominator", "7 837 170", "persons",
            "high-risk population"),
           ("screened", "581 633", "persons", "were screened"),
           ("other:pct_mapped_population_screened", "7.4%", "percent", "were screened"),
           ("other:screened_per_district_per_activity_day", "565", "persons",
            "people screened per district per ACF activity day")])
    prose("res-days", res, "There were a total of 1467 ACF activity days.",
          [("other:acf_activity_days", "1467", "", "ACF activity days")])
    prose("res-days-tool", res,
          "ACF tool was used in the field in 1031 (70.3%) days.",
          [("other:acf_activity_days_with_tool", "1031", "",
            "ACF tool was used in the field"),
           ("other:pct_acf_activity_days_with_tool", "70.3%", "percent",
            "ACF tool was used in the field")])
    prose("res-presumptive", res,
          "Of these, 11 357 (1.95%, 95% CI: 1.92, 1.99) were identified as presumptive TB.",
          [("presumptive", "11 357", "persons", "were identified as presumptive TB"),
           ("other:pct_presumptive_among_screened", "1.95%", "percent",
            "were identified as presumptive TB")])
    s4 = ("Of 11 357, sputum specimen was collected for 8541 (75.2%) and 7527 (66.3%, "
          "95% CI: 65.4, 67.2) were tested, of which 117 (1.6%, 95% CI: 1.3, 1.9) were "
          "diagnosed with TB.")
    prose("res-tested", res, s4,
          [("other:sputum_specimens_collected", "8541", "persons",
            "sputum specimen was collected"),
           ("other:pct_sputum_collected_among_presumptive", "75.2%", "percent",
            "sputum specimen was collected"),
           ("tested", "7527", "persons", "were tested"),
           ("other:pct_tested_among_presumptive", "66.3%", "percent", "were tested"),
           ("tb_cases", "117", "cases", "were diagnosed with TB"),
           ("other:pct_diagnosed_among_tested", "1.6%", "percent",
            "were diagnosed with TB")])
    prose("res-nns", res, "The NNS was 4971.", [("nns", "4971", "ratio", "NNS")])
    prose("res-xray", "Results, chest radiograph paragraph",
          "Of the high-risk population screened, a total of 9321 (1.6%) underwent upfront "
          "chest radiograph as a screening test and most of these people (n = 8854, 95%) "
          "were from two districts of a state.",
          [("screened", "9321", "persons",
            "underwent upfront chest radiograph as a screening test"),
           ("other:pct_screened_by_chest_radiograph", "1.6%", "percent",
            "underwent upfront chest radiograph as a screening test"),
           ("other:screened_by_chest_radiograph_two_districts", "8854", "persons",
            "most of these people were from two districts of a state"),
           ("other:pct_screened_by_chest_radiograph_two_districts", "95%", "percent",
            "most of these people were from two districts of a state")])
    prose("res-xray-abn", "Results, chest radiograph paragraph",
          "Of these 9321, a total of 1087 (11.7%) had an abnormality in chest radiograph, "
          "of whom 679 (62.5%) did not have any symptoms.",
          [("other:chest_radiograph_abnormal", "1087", "persons",
            "had an abnormality in chest radiograph"),
           ("other:pct_chest_radiograph_abnormal", "11.7%", "percent",
            "had an abnormality in chest radiograph"),
           ("other:chest_radiograph_abnormal_asymptomatic", "679", "persons",
            "did not have any symptoms"),
           ("other:pct_chest_radiograph_abnormal_asymptomatic", "62.5%", "percent",
            "did not have any symptoms")])
    # Discussion: the study's own figures restated
    disc = "Discussion"
    prose("disc-summary", disc,
          "During the ACF cycle, less than 10% of high-risk population was screened with "
          "an NNS of ≈5000.",
          [("other:pct_high_risk_population_screened", "10%", "percent",
            "of high-risk population was screened"),
           ("nns", "≈5000", "ratio", "NNS")])
    prose("disc-seven", disc,
          "Our estimates from this study, which are more reliable, suggest that only 7% of "
          "mapped high-risk population were screened (cut-off 90%).",
          [("other:pct_mapped_population_screened", "7%", "percent",
            "of mapped high-risk population were screened")])
    prose("disc-rapid", disc,
          "The extent of use of rapid molecular diagnostic tests among ACF- and "
          "PCF-detected presumptive TB was similar (26% versus 23%).",
          [("other:pct_rapid_molecular_among_tested", "26%", "percent",
            "extent of use of rapid molecular diagnostic tests among ACF- and PCF-detected "
            "presumptive TB")])
    prose("disc-days", disc,
          "First, we captured the extent of use of ACF tool by ACF activity days (1031 of "
          "1467 ACF activity days) and not based on what proportion of Ni-kshay reported "
          "ACF care cascade data were captured by the ACF tool.",
          [("other:acf_activity_days_with_tool", "1031", "",
            "extent of use of ACF tool by ACF activity days"),
           ("other:acf_activity_days", "1467", "", "ACF activity days")])
    prose("disc-565", disc,
          "There is scope to screen a larger number than the current average of 565 per "
          "ACF activity day per district.",
          [("other:screened_per_district_per_activity_day", "565", "persons",
            "average of 565 per ACF activity day per district")])
    prose("res-rapid", "Results, rapid molecular diagnostic test",
          "Of 7527 presumptive tested, 1989 (26.4%, 95% CI: 25.4, 27.4) underwent rapid "
          "molecular diagnostic test.",
          [("other:rapid_molecular_tests_used", "1989", "tests",
            "underwent rapid molecular diagnostic test"),
           ("other:pct_rapid_molecular_among_tested", "26.4%", "percent",
            "underwent rapid molecular diagnostic test")])
    return S


# ----------------------------------------------------------- inventory scope decisions

SCOPE_COLUMNS = ["kind", "doc", "source_file", "page", "figures", "where", "category",
                 "decision", "reason"]
SUBGROUP_REASON = ("non-geographic subgroup stratum: the §5.2 schema has no subgroup "
                   "field, so a stratum row cannot be told from the study total; kept in "
                   "data/extracted/quality_studies.csv for the §7.5 reconciliation")
SCOPE_RULE_QS = ("Inventory scope of the two quality studies (§5.1). Each study's national "
                 "(INDIA or Total) figures, its State rows (geography is a schema field) "
                 "and its Abstract and Results figures of the named quantities enter; "
                 "derived indicators enter as `other:`. Non-geographic subgroup strata do "
                 "not enter.")


def scope_decisions() -> list[dict]:
    T = read_transcribed()

    def n(study, table, grouped=None):
        return len({(t["row_group"], t["row_label"]) for t in T
                    if t["study"] == study and t["table_id"] == table
                    and (grouped is None or bool(t["row_group"]) == grouped)})

    rows = [{"kind": "rule", "doc": "", "source_file": GHA_URL, "page": "", "figures": "",
             "where": "", "category": "", "decision": "", "reason": SCOPE_RULE_QS}]
    for doc, f, page, figs, where, cat in (
            ("GHA2023", GHA_URL, "", f"{n('GHA2023', 'Table 2')} rows x 6 columns",
             "Table 2, all rows (high-risk groups)", "subgroup strata"),
            ("PGPH2025", PG_URL, "", f"{n('PGPH2025', 'Table 2') - 1} rows x 5 columns",
             "Table 2, rows under Gender, Elderly, Residence, Type of high-risk "
             "population, Facility-based high-risk group", "subgroup strata"),
            ("PGPH2025", PG_URL, "", f"{n('PGPH2025', 'Table 3') - 1} rows x 2 columns",
             "Table 3, rows under Gender, Elderly, Residence, Type of high-risk "
             "population, Facility-based high-risk group", "subgroup strata")):
        rows.append({"kind": "exclusion", "doc": doc, "source_file": f, "page": page,
                     "figures": figs, "where": where, "category": cat,
                     "decision": "not entered", "reason": SUBGROUP_REASON})
    for doc, f, figs, where, cat, why in (
            ("PGPH2025", PG_URL, "70.3%, 28.7%, 8%, 2.7%, 9.2%; medians of 9, 5 days",
             "Results, symptoms among presumptive TB", "clinical detail",
             "prevalence of symptoms among presumptive TB: clinical description, not a "
             "step of the cascade"),
            ("PGPH2025", PG_URL, "34.1%, 20.6%, 9.5%, 8.6%, 6.9%, 2.9%, 2.7%, 75.3%; NNS "
             "2495, 882, 1583, 1288", "Results, distribution of specific high-risk "
             "populations; Table 3 text", "subgroup strata", SUBGROUP_REASON),
            ("PGPH2025", PG_URL, "75%", "Methods, denominator; Figure 2 legend",
             "analysis assumption",
             "the 75% of the mapped high-risk population taken as the denominator is an "
             "analysis parameter, not a figure of the cascade; its product, 7 837 170, is "
             "entered"),
            ("PGPH2025", PG_URL, "11%, 90%, 5%, 95%, 5%, 95%, 1538",
             "PGPH Abstract and Methods, indicator targets", "benchmark targets",
             "evaluation thresholds of the national ACF guidance, not campaign or ACF "
             "inputs or outputs (as the KPI target columns of the campaign documents are "
             "not entered); they stay in the column headings and denominator_methods of "
             "data/extracted/quality_studies.csv"),
            ("GHA2023", GHA_URL, "10%, 4.75%, 5%, 1538",
             "GHA Methods and Table 1 column headings, indicator targets",
             "benchmark targets",
             "evaluation thresholds of the national ACF guidance, not campaign or ACF "
             "inputs or outputs (as the KPI target columns of the campaign documents are "
             "not entered); they stay in the column headings and denominator_methods of "
             "data/extracted/quality_studies.csv"),
            ("PGPH2025", PG_URL, "11%, 17.5%, 90%",
             "Discussion, scenario of a reduced mapped population",
             "hypothetical scenario",
             "an assumed mapped share and the scale it would give: a projection, not a "
             "reported figure; the observed 18.3% in the same sentence is entered"),
            ("PGPH2025", PG_URL, "35",
             "Discussion, systematic review of contact screening", "other literature",
             "NNS of a systematic review of low- and middle-income countries, not a figure "
             "of either study or of Indian programme data"),
    ):
        rows.append({"kind": "exclusion", "doc": doc, "source_file": f, "page": "",
                     "figures": figs, "where": where, "category": cat,
                     "decision": "not entered", "reason": why})
    return rows


def build_inventory() -> list[dict]:
    rows = [_inv(**s) for s in _gha_specs() + _pg_specs()]
    ids = [r["fig_id"] for r in rows]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise ValueError(f"fig_id collisions: {sorted(dup)}")
    return rows


def build() -> tuple[list[dict], list[dict]]:
    return build_quality(), build_inventory()


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
    """Rows of the campaign extractor are kept; this extractor's rows (source_file one of
    its sources) replace its own earlier rows."""
    path = EXTRACTED / "inventory_scope_decisions.csv"
    kept = []
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            kept = [r for r in csv.DictReader(f) if r["source_file"] not in OWN_FILES]
    return kept + own


def main() -> int:
    verify_inputs()
    quality, inv = build()
    _write(EXTRACTED / "quality_studies.csv", QS_COLUMNS, quality)
    _write(INVENTORY, INVENTORY_COLUMNS, _merge_inventory(inv))
    _write(EXTRACTED / "inventory_scope_decisions.csv", SCOPE_COLUMNS,
           _merge_scope(scope_decisions()))
    print(f"quality_studies.csv rows: {len(quality)}; inventory rows: {len(inv)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
