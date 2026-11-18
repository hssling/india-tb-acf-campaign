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
import re
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal

from src import inventory_rules as R
from src import states
from src.extract import labels
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
    "pct_screened": "Percentage screened among district's population – at least 10%",
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
    t = printed.strip().rstrip("%").strip()
    if not re.fullmatch(r"\d[\d ,]*(?:\.\d+)?(?: (?:million|lakh|crore))?", t):
        return ""
    mult = {"million": 10**6, "lakh": 10**5, "crore": 10**7}
    m = re.fullmatch(r"([\d ,.]+?)(?: (million|lakh|crore))?", t)
    num = Decimal(m.group(1).replace(" ", "").replace(",", ""))
    if m.group(2):
        return str(int(num * mult[m.group(2)]))
    return str(int(num)) if "." not in m.group(1) else str(num)


# ============================================================ supplement (docx)

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
    if label == "INDIA":
        return "India", ""
    try:
        return labels.resolve(label).canonical, ""
    except labels.UnmappedLabel:
        return "", "State label not mappable by the label rule (§9.2); row kept as printed"


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
        base = dict(study=study, table_id=table, table_title=title, row_group=grp,
                    row_label=lab, geography="India", column_label=col, source=t["url"],
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
         occurrence=1, geography="India") -> dict:
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
    basis = "window_end" if wend else "bounded"
    key = ".".join(x for x in (doc, _slug(loc), _slug(row), _slug(col),
                               quantity.replace(":", "_")) if x)
    return {
        "fig_id": key, "quantity": quantity, "value": _value(printed),
        "value_printed": printed, "qualifier": qual, "unit": unit,
        "definition_verbatim": definition, "context_verbatim": context,
        "definition_class": dcls, "scope": scope, "series_type": "period",
        "window_label": R.window_label(context, period, bool(wend)),
        "window_start": wstart, "window_end": wend, "as_on": "", "as_on_basis": basis,
        "geography": geography, "source_file": source_file, "source_url": url,
        "page_or_para": page, "table_id": table_id, "pub_date": pub,
        "note": "; ".join(notes)}


READ = ("read online on 2026-11-19 (HTML full text, not saved); context and figure "
        "transcribed by hand")
FIRST = "first cycle in 2021"
PGW = dict(wstart="2023-01-01", wend="2023-09-30")


def _gha_specs() -> list[dict]:
    S = []
    # Table 1, INDIA row
    for col, q, unit, defn in (
            ("% Screened among population** (at least 10%)", "other:pct_population_screened",
             "percent", "% Screened among population** (at least 10%)"),
            ("% Tested among screened (at least 4.75%)", "other:pct_tested_among_screened",
             "percent", "% Tested among screened (at least 4.75%)"),
            ("% Diagnosed among tested (at least 5%)", "other:pct_diagnosed_among_tested",
             "percent", "% Diagnosed among tested (at least 5%)"),
            ("NNS (max. 1538)", "nns", "ratio", "NNS (max. 1538)")):
        printed = next(t["printed_cell"] for t in read_transcribed()
                       if t["study"] == "GHA2023" and t["table_id"] == "Table 1"
                       and t["column_label"] == col)
        S.append(dict(doc="GHA2023", loc="T1", row="INDIA", col=col, quantity=q,
                      printed=printed, unit=unit, definition=defn,
                      context=_ctx_cell(GHA_T1, col, "INDIA"), source_file=GHA_URL,
                      page="Table 1, row INDIA", table_id="Table 1", period=FIRST,
                      pub=GHA_PUB, note=READ))
    # prose: Abstract, Results, Frequency
    prose = [
        ("abs", "Abstract, Results",
         "9.3% of the population were screened, 1% of the screened were tested and 3.7% of "
         "the tested were diagnosed.",
         [("other:pct_population_screened", "9.3%", "percent", "of the population were screened"),
          ("other:pct_tested_among_screened", "1%", "percent", "of the screened were tested"),
          ("other:pct_diagnosed_among_tested", "3.7%", "percent",
           "of the tested were diagnosed")]),
        ("abs", "Abstract, Results",
         "The NNS was 2824: acceptable (≤1538) in institutional facilities and poor for "
         "population-based groups.", [("nns", "2824", "ratio", "NNS")]),
        ("res", "Results, 'ACF quality indicators: national and state level'",
         "9.3% of the population got screened, 1% screened got tested, and 3.7% of those "
         "tested got diagnosed with TB.",
         [("other:pct_population_screened", "9.3%", "percent", "of the population got screened"),
          ("other:pct_tested_among_screened", "1%", "percent", "screened got tested"),
          ("other:pct_diagnosed_among_tested", "3.7%", "percent",
           "of those tested got diagnosed with TB")]),
        ("res", "Results, 'ACF quality indicators: national and state level'",
         "The NNS was 2824.", [("nns", "2824", "ratio", "NNS")]),
        ("freq", "Results, 'Frequency of ACF'",
         "2.9% (n = 41 306) of the 1.44 million TB notified from the public sector were "
         "reported as ACF-detected (see S1 and S2 Annex).",
         [("acf_share_notifications", "2.9%", "percent",
           "of the 1.44 million TB notified from the public sector were reported as "
           "ACF-detected"),
          ("tb_cases", "41 306", "cases", "reported as ACF-detected"),
          ("other:public_sector_tb_notified", "1.44 million", "cases",
           "TB notified from the public sector")]),
    ]
    for loc, page, sent, items in prose:
        for q, printed, unit, defn in items:
            S.append(dict(doc="GHA2023", loc=loc, row="", col="sentence", quantity=q,
                          printed=printed, unit=unit, definition=defn, context=sent,
                          source_file=GHA_URL, page=page, pub=GHA_PUB, prose=True,
                          note=READ + "; the sentence is quoted from the page text as read "
                          "and not machine-verified; no cycle dates in the sentence"))
    # supplement S1 and S2, INDIA rows
    s1, s2 = read_supplement()
    s1i = next(r for r in s1 if r[0] == "INDIA")
    s2i = next(r for r in s2 if r[0] == "INDIA")
    snote = ("read from the supplement (docx, SHA-256 verified); the supplement has no "
             "printed date, so pub_date is the article's")
    for i, (col, q, unit, defn, qn) in enumerate((
            ("Total population**", "population", "persons", "Total population**",
             "other:population_in_districts_with_acf_data"),
            ("Number screened", "screened", "persons", "Number screened", "screened"),
            ("Number tested among screened", "tested", "persons",
             "Number tested among screened", "tested"),
            ("Number diagnosed among tested", "tb_cases", "cases",
             "Number diagnosed among tested", "tb_cases")), start=1):
        S.append(dict(doc="GHA2023SM", loc="S1", row="INDIA", col=col, quantity=qn,
                      printed=s1i[i], unit=unit, definition=defn,
                      context=_ctx_cell(S1_TITLE, col, "INDIA"), source_file=SUPP,
                      page="S1 Annex table, row INDIA", table_id="S1 Annex", period=FIRST,
                      pub=GHA_PUB, note=snote))
    for i, (col, qn, unit, defn) in enumerate((
            ("Public notified TB (from 2022 India TB report)",
             "other:public_sector_tb_notified", "cases",
             "Public notified TB (from 2022 India TB report)"),
            ("TB ACF cases diagnosed among tested (reported as ACF-detected)", "tb_cases",
             "cases", "TB ACF cases diagnosed among tested (reported as ACF-detected)"),
            ("%", "acf_share_notifications", "percent", "%")), start=1):
        S.append(dict(doc="GHA2023SM", loc="S2", row="INDIA", col=col, quantity=qn,
                      printed=s2i[i], unit=unit, definition=defn,
                      context=_ctx_cell(S2_TITLE, col, "INDIA"), source_file=SUPP,
                      page="S2 Annex table, row INDIA", table_id="S2 Annex", period="2021",
                      pub=GHA_PUB, note=snote))
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
    pnote = (READ + "; the sentence is quoted from the page text as read and not "
             "machine-verified; the study period (January to September 2023) is stated in "
             "the paper's tables and abstract, not in this sentence")
    res = "Results, first paragraph"
    S += [
        dict(doc="PGPH2025", loc="res", row="", col="sentence-screened", quantity="screened",
             printed="581 633", unit="persons", definition="were screened",
             context="581 633 (7.4%, 95% CI: 7.42. 7.44) were screened", source_file=PG_URL,
             page=res, pub=PG_PUB, prose=True, **PGW,
             note=pnote + "; only the fragment of the sentence read is quoted"),
        dict(doc="PGPH2025", loc="res", row="", col="sentence-presumptive",
             quantity="presumptive", printed="11 357", unit="persons",
             definition="were identified as presumptive TB",
             context="Of these, 11 357 (1.95%, 95% CI: 1.92, 1.99) were identified as "
                     "presumptive TB.", source_file=PG_URL, page=res, pub=PG_PUB,
             prose=True, note=pnote, **PGW),
        dict(doc="PGPH2025", loc="res", row="", col="sentence-presumptive",
             quantity="other:pct_presumptive_among_screened", printed="1.95%",
             unit="percent", definition="were identified as presumptive TB",
             context="Of these, 11 357 (1.95%, 95% CI: 1.92, 1.99) were identified as "
                     "presumptive TB.", source_file=PG_URL, page=res, pub=PG_PUB,
             prose=True, note=pnote, **PGW),
    ]
    sent = ("7527 (66.3%, 95% CI: 65.4, 67.2) were tested, of which 117 (1.6%, 95% CI: "
            "1.3, 1.9) were diagnosed with TB.")
    for q, p, unit, defn in (
            ("tested", "7527", "persons", "were tested"),
            ("other:pct_tested_among_presumptive", "66.3%", "percent", "were tested"),
            ("tb_cases", "117", "cases", "were diagnosed with TB"),
            ("other:pct_diagnosed_among_tested", "1.6%", "percent",
             "were diagnosed with TB")):
        S.append(dict(doc="PGPH2025", loc="res", row="", col="sentence-tested-diagnosed",
                      quantity=q, printed=p, unit=unit, definition=defn, context=sent,
                      source_file=PG_URL, page=res, pub=PG_PUB, prose=True,
                      note=pnote + "; only the fragment of the sentence read is quoted",
                      **PGW))
    S.append(dict(doc="PGPH2025", loc="res", row="", col="sentence-nns", quantity="nns",
                  printed="4971", unit="ratio", definition="NNS",
                  context="The NNS was 4971.", source_file=PG_URL, page=res,
                  pub=PG_PUB, prose=True, note=pnote, **PGW))
    ab = "Abstract"
    S += [
        dict(doc="PGPH2025", loc="abs", row="", col="sentence-mapped-screened",
             quantity="other:pct_mapped_population_screened", printed="7.4%",
             unit="percent", definition="mapped population screened",
             context="ii) mapped population screened (≥90%, 7.4%)", source_file=PG_URL,
             page=ab, pub=PG_PUB, prose=True, **PGW,
             note=pnote + "; list item of the abstract, quoted as a fragment"),
        dict(doc="PGPH2025", loc="abs", row="", col="sentence-nns", quantity="nns",
             printed="4971", unit="ratio", definition="number needed to screen",
             context="The number needed to screen (target ≤1538 considering the "
                     "algorithm) to detect one person with TB was 4971.",
             source_file=PG_URL, page=ab, pub=PG_PUB, prose=True, note=pnote, **PGW),
    ]
    return S


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


def main() -> int:
    verify_inputs()
    quality, inv = build()
    _write(EXTRACTED / "quality_studies.csv", QS_COLUMNS, quality)
    _write(INVENTORY, INVENTORY_COLUMNS, _merge_inventory(inv))
    print(f"quality_studies.csv rows: {len(quality)}; inventory rows: {len(inv)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
