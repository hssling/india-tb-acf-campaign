# Adapted from hssling/india-state-tb-score (MIT), exhibits/make_tables.py, commit 05bcaa7; modified: rewritten for the ACF campaign study (tables of Q1-Q4 read from outputs/ and data/; every cell is traced to its source file and column); only the layout idea (a render function, Markdown output, no typed numbers) is kept
"""Render every manuscript table from outputs/ and data/ to manuscript/exhibits/.

Run as: python -I exhibits/make_tables.py   (from the repository root)

manuscript/ is git-ignored and local. Standard library only. Output:
- tables.md                      main-text Tables 1-3 and the supplementary tables, as Markdown
                                 (tables without vertical rules; footnotes as superscript
                                 lowercase letters, Public Health);
- <table id>.csv                 each table as CSV (LF line endings);
- supplementary_data_S1a_registered.csv, supplementary_data_S1b_corrected.csv
                                 every Q2 entry pair, one row each (Supplementary data S1a, S1b;
                                 their column dictionary closes tables.md);
- trace.json                     every numeric cell with its source file, row, column and
                                 the formatter, so a test can re-derive it from outputs/.

No number is typed here. Every numeric cell is read from outputs/ or data/ (or is a count of
rows of one of those files, with the filter recorded) and formatted by the helpers below.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "manuscript" / "exhibits"

MAIN_TABLES = ["Table 1", "Table 2", "Table 3"]  # main-text tables; the figures are Figures 1 and 2
SUP = "ᵃᵇᶜᵈᵉᶠ"
MINUS = "−"


def read(rel: str) -> list[dict]:
    with open(ROOT / rel, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------------------
# formatters (applied to the raw string read from the file)
# --------------------------------------------------------------------------------------
def f_int(raw: str) -> str:
    return f"{int(float(raw)):,}"


def f_dec(d: int):
    def fmt(raw: str) -> str:
        s = f"{float(raw):,.{d}f}"
        if d == 3 and float(raw) != 0 and float(s.replace(",", "")) == 0:
            s = f"{float(raw):,.4f}"  # a non-zero value never prints as 0.000 ("−0.0004")
        return s.replace("-", MINUS)
    fmt.__name__ = f"dec{d}"
    return fmt


def f_printed(raw: str) -> str:
    """A figure as printed: a plain number (digits, spaces or commas) gets thousands separators; else as is."""
    t = raw.replace(" ", "").replace(",", "")
    return f"{int(t):,}" if t.isdigit() else raw


FORMATTERS = {"printed": f_printed, "int": f_int, "dec0": f_dec(0), "dec1": f_dec(1), "dec2": f_dec(2), "dec3": f_dec(3), "raw": lambda s: s}


class Trace:
    """Records where each numeric cell comes from."""

    def __init__(self) -> None:
        self.entries: list[dict] = []

    def value(self, file: str, rows: list[dict], row_i: int, column: str, fmt: str) -> str:
        raw = rows[row_i][column]
        text = FORMATTERS[fmt](raw)
        self.entries.append({"kind": "value", "file": file, "row": row_i, "column": column,
                             "raw": raw, "fmt": fmt, "text": text})
        return text

    def count(self, file: str, rows: list[dict], filters: dict, distinct: str | None = None) -> str:
        sel = [r for r in rows if all(r[k] == v for k, v in filters.items())]
        n = len({r[distinct] for r in sel}) if distinct else len(sel)
        self.entries.append({"kind": "count", "file": file, "filters": filters, "distinct": distinct,
                             "text": f"{n:,}"})
        return f"{n:,}"

    def interval(self, file: str, rows: list[dict], row_i: int, col: str, lo: str, hi: str, fmt: str) -> str:
        a = self.value(file, rows, row_i, col, fmt)
        b = self.value(file, rows, row_i, lo, fmt)
        c = self.value(file, rows, row_i, hi, fmt)
        return f"{a} ({b} to {c})"


def md_cell(s: str) -> str:
    """A cell for a Markdown pipe table: a literal '|' (two printed forms of one value, as in
    '73,772 | 73772') is escaped, so it does not open a new column."""
    return s.replace("|", "\\|")


def md_table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(md_cell(h) for h in header) + " |",
           "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(md_cell(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def write_csv(name: str, header: list[str], rows: list[list[str]]) -> None:
    with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def row_index(rows: list[dict], **kv) -> int:
    hits = [i for i, r in enumerate(rows) if all(r[k] == v for k, v in kv.items())]
    if len(hits) != 1:
        raise ValueError(f"expected one row for {kv}, found {len(hits)}")
    return hits[0]


# --------------------------------------------------------------------------------------
# Plain names: no variable names, file names or internal identifiers reach a table
# --------------------------------------------------------------------------------------
MONTHS = ("January February March April May June July August September October November "
          "December").split()
QUANTITY = {"districts_selected": "Districts selected", "nns": "Number needed to screen",
            "presumptive": "People with presumptive TB", "screened": "People screened",
            "tb_cases": "TB cases", "tested": "People tested", "population_targeted": "Population targeted"}
SCOPE = {"phase 1": "first phase", "expanded campaign": "expanded campaign",
         "programme-wide": "programme-wide", "unspecified": "scope not stated"}
STATUS = {"computed": "computed", "not_available": "not available", "not_computable": "not computable"}
OFFICIAL = {
    "100-days-campaign-Report-1-Complete-on-5-12-2024-New.pdf": "CTD, 100 Days Campaign (2024)",
    "Guidance-Document-on-TB-Mukt-Bharat-Abhiyan_0.pdf": "CTD, Guidance Document on TB Mukt Bharat Abhiyan (2025)",
    "TB-Mukt-Bharat-Abhiyan-Campaign-2026-v6.pdf": "CTD, TB Mukt Bharat Abhiyaan Campaign 2026",
    "TB_Elimination_Campaign.pdf": "Ministry of Health letter on the campaign (Kerala copy)",
    "doc2024127466601.pdf": "PIB, Synopsis of 100-Day Campaign (7 December 2024)",
    "doc2024126465901.pdf": "PIB backgrounder (6 December 2024)",
    "doc2026324833001.pdf": "PIB press note, 24 March 2026 (PDF)",
    "doc20241228477601.pdf": "PIB, year-end review 2024",
    "India-TB-Report-2019.pdf": "India TB Report 2019",
    "TBAnnaulReport2022.pdf": "India TB Report 2022",
    "ZGHA_A_2256129_SM2351.docx": "Shewade et al. 2023 (supplement)",
}
_PUB: dict[str, str] = {}


def long_date(iso: str) -> str:
    y, m, d = iso[:10].split("-")
    return f"{int(d)} {MONTHS[int(m) - 1]} {y}"


def doc_name(source: str) -> str:
    """A reader's name for a source document (never a file name, URL or identifier)."""
    if not _PUB:
        for r in read(INV):
            _PUB.setdefault(r["source_file"], r["pub_date"])
    name = Path(source).name
    if name in OFFICIAL:
        return OFFICIAL[name]
    if name.startswith("ITR20"):
        return f"India TB Report {name[3:7]}"
    if source.startswith("data_raw/pq/"):
        house, kind = ("Lok Sabha", "Starred") if name.startswith("AS") else ("Rajya Sabha", "Unstarred")
        qn = "".join(ch for ch in name[2:].split("_")[0].split(".")[0] if ch.isdigit())
        when = _PUB.get(source, "")
        return f"{house} {kind} Question {qn}" + (f" ({long_date(when)})" if when else "")
    if "PMC12574901" in source or "pgph.0005103" in source:
        return "Shewade et al. 2025"
    if "PMC10515680" in source:
        return "Shewade et al. 2023"
    if "pib.gov.in/PressNoteDetails" in source:
        return f"PIB press note, {long_date(_PUB[source])}"
    if "pib.gov.in/PressReleasePage" in source:
        return f"PIB release, {long_date(_PUB[source])}"
    if "dghs.mohfw.gov.in/national-tuberculosis-elimination-programme" in source:
        return "DGHS, National Tuberculosis Elimination Programme web page"
    raise ValueError(f"no reader's name for source {source!r}")


def itr_table(code: str) -> str:
    """'ITR2019-A1.7' -> 'India TB Report 2019, Annexure 1.7'; the quality study's table by author and year."""
    if code.startswith("ITR"):
        ed, ann = code[3:].split("-A")
        return f"India TB Report {ed}, Annexure {ann}"
    if code == "GHA2023-S2":
        return "Shewade et al. 2023, supplementary table 2"
    raise ValueError(f"no reader's name for table {code!r}")


# --------------------------------------------------------------------------------------
# Table 1: inventory and Q1 consistency checks
# --------------------------------------------------------------------------------------
NAMED = [("tb_cases", "TB cases (notified or diagnosed)"), ("screened", "Screened"),
         ("presumptive", "People with presumptive TB"), ("tested", "Tested"),
         ("nns", "Number needed to screen"), ("acf_share_notifications", "ACF share of notifications"),
         ("districts_selected", "Districts selected"), ("population_targeted", "Population targeted")]
INV = "data/figures_inventory.csv"


def table1(tr: Trace):
    inv = read(INV)
    header = ["Row", "Figures or checks (n)", "Documents (n)", "Pass (n)", "Fail (n)", "Not run (n)"]
    rows = [["Inventory of figures", tr.count(INV, inv, {}), tr.count(INV, inv, {}, "source_file"),
             "", "", ""]]
    for q, label in NAMED:
        rows.append([f"  {label}", tr.count(INV, inv, {"quantity": q}),
                     tr.count(INV, inv, {"quantity": q}, "source_file"), "", "", ""])
    n_other = sum(1 for r in inv if r["quantity"].startswith("other:"))
    # "other:" figures: one count over the prefix; recorded as a prefix count
    tr.entries.append({"kind": "prefix_count", "file": INV, "column": "quantity", "prefix": "other:",
                       "text": f"{n_other:,}"})
    n_other_docs = len({r["source_file"] for r in inv if r["quantity"].startswith("other:")})
    tr.entries.append({"kind": "prefix_count_distinct", "file": INV, "column": "quantity",
                       "prefix": "other:", "distinct": "source_file", "text": f"{n_other_docs:,}"})
    rows.append(["  Other campaign figures (kept out of the checks)ᵃ", f"{n_other:,}", f"{n_other_docs:,}", "", "", ""])
    if sum(len([r for r in inv if r["quantity"] == q]) for q, _ in NAMED) + n_other != len(inv):
        raise ValueError("Table 1: the named quantities and the other figures do not sum to the inventory")
    for label, f in (("Registered rules", "outputs/q1_checks.csv"), ("Corrected rules (post hoc)ᵇ", "outputs/q1_checks_corrected.csv")):
        q1 = read(f)
        rows.append([f"Q1 consistency checks: {label}", "", "", "", "", ""])
        for chk in ("1 cascade does not grow", "2 percentage recomputes",
                    "3 total equals the sum of its parts", "4 cumulative series never decreases"):
            tot = tr.count(f, q1, {"check": chk})
            rows.append([f"  Check {chk}", tot, "",
                         tr.count(f, q1, {"check": chk, "pass": "yes"}),
                         tr.count(f, q1, {"check": chk, "pass": "no"}),
                         tr.count(f, q1, {"check": chk, "pass": "n/a"})])
    notes = [f"{SUP[0]} Figures of quantities other than the named quantities listed above; their sums and percentages are described, not tested.",
             f"{SUP[1]} Post hoc correction of the registered rules, disclosed as a deviation from the registered plan; the registered rules are shown first."]
    return header, rows, notes


# --------------------------------------------------------------------------------------
# Table 2: Q2 discrepancy classes, registered vs corrected, and the class 1 and 2 pairs
# --------------------------------------------------------------------------------------
Q2S = "outputs/q2_summary_registered_vs_corrected.csv"
CLASS_KEYS = ["1", "2", "3a", "3b", "4"]  # labels are read from the class_label column of the output


def evidence(r: dict) -> str:
    """A short phrase for a class 1 or class 2 pair (the quoted wording and the full evidence
    are in Supplementary data S1b)."""
    if r["class"] == "1":
        side = "B" if ("PMC12574901" in r["b_source"]) else "A"
        return f"{side}'s table: parts do not sum to total"
    ev = r["evidence"].split(" | ")[0]
    m = re.fullmatch(r"class 2: definitions: '.*' \(([^()]+)\) vs '.*' \(([^()]+)\)", ev)
    if m:
        return f"A {m.group(1)}, B {m.group(2)}"
    raise ValueError(f"unexpected evidence for class {r['class']}: {ev[:60]!r}")


SPAN_T2 = "Class 1 and 2 entry pairs (corrected set)"


def table2(tr: Trace):
    s = read(Q2S)
    header = ["Class of entry pair", "Registered, pre-specified", "Registered, all", "Corrected, pre-specified", "Corrected, all"]
    rows = []

    def cells(metric_all, metric_pre):
        out = []
        for metric in (metric_pre, metric_all):
            i = row_index(s, metric=metric)
            out.append(tr.value(Q2S, s, i, "registered", "int"))
            out.append(tr.value(Q2S, s, i, "corrected", "int"))
        return [out[0], out[2], out[1], out[3]]  # reg pre, reg all, corr pre, corr all

    rows.append(["Entry pairs comparedᵃ"] + cells("Q2 entry pairs (all)", "Q2 entry pairs (pre-specified)"))
    rows.append(["Agree"] + cells("Q2 all: agree", "Q2 pre-specified: agree"))
    lab = {r["class"]: r["class_label"] for r in read("outputs/q2_discrepancies_corrected.csv") if r["class"]}
    for k in CLASS_KEYS:
        label = f"{k} {lab[k][0].upper()}{lab[k][1:]}"
        rows.append([label] + cells(f"Q2 all: class {k}", f"Q2 pre-specified: class {k}"))
    ig = row_index(s, metric="Q2 comparison groups formed (§7.1)")
    rows.append(["Comparison groups formed", "", tr.value(Q2S, s, ig, "registered", "int"), "",
                 tr.value(Q2S, s, ig, "corrected", "int")])
    ie = row_index(s, metric="Q2 entry pairs (exploratory)")
    notesA = [f"{SUP[0]} Entry pairs are pairs of distinct (document, value) entries within a comparison group. "
              f"Pre-specified pairs lead; the difference from all pairs is the exploratory pairs "
              f"({tr.value(Q2S, s, ie, 'registered', 'int')} registered, {tr.value(Q2S, s, ie, 'corrected', 'int')} corrected), "
              "from two parliamentary answers added after registration as exploratory cross-checks. "
              "The corrected set applies three post hoc corrections, disclosed as deviations from the registered plan. "
              "The quoted definitions and the full evidence for every pair are in Supplementary data S1b."]

    f = "outputs/q2_discrepancies_corrected.csv"
    d = read(f)
    headerB = ["Class", "Quantity, geography and scope", "Value in A (as printed)" + SUP[1], "Source of A",
               "Value in B (as printed)" + SUP[1], "Source of B", "Evidence"]
    rowsB = []
    for i, r in enumerate(d):
        if r["class"] in ("1", "2"):
            rowsB.append([r["class"] + (SUP[2] if r["class"] == "1" else ""),
                          f"{QUANTITY[r['quantity']]}, {r['geography']}, {SCOPE[r['scope']]}",
                          tr.value(f, d, i, "a_value_printed", "printed"), doc_name(r["a_source"]),
                          tr.value(f, d, i, "b_value_printed", "printed"), doc_name(r["b_source"]),
                          evidence(r).replace("|", ";")])
    notesA.append(f"{SUP[1]} Values as printed; 1 lakh = 100,000 and 1 crore = 10,000,000.")
    notesA.append(f"{SUP[2]} Both class 1 rows pair national India TB Report 2024 counts of people screened (20.5 crore; 205,331,541) "
                  "with the total of the 2025 quality study (581,633) for 30 sampled districts, January to September 2023. "
                  "The class reflects a failed sum check within that study's total (parts 579,073; difference −2,560), "
                  "not a difference in national totals; the difference in scope is not tested in this class.")
    # one grid: the class-count rows padded to the pair columns, a spanning row, the pairs' heading row
    width = len(headerB)
    grid = [r + [""] * (width - len(r)) for r in rows]
    grid.append([f"**{SPAN_T2}**"] + [""] * (width - 1))
    grid.append([f"**{h}**" for h in headerB])
    grid += rowsB
    return header + [""] * (width - len(header)), grid, notesA


# --------------------------------------------------------------------------------------
# Table 3: Q3 national yield and NNS by data year
# --------------------------------------------------------------------------------------
Q3S = "outputs/q3_yield_summary.csv"
Q3 = "outputs/q3_yield.csv"


def table3(tr: Trace):
    s = read(Q3S)
    full = read(Q3)
    header = ["Data year", "Source table", "Screened (n)", "Diagnosed (n)", "Yield per 100,000 screened (95% CI)" + SUP[0], "Number needed to screen (95% CI)" + SUP[0]]
    years = sorted({r["year"] for r in full})
    rows, notes = [], []
    for y in years:
        i_y = [i for i, r in enumerate(s) if r["state"] == "India" and r["year"] == y and r["indicator"] == "yield_diagnosed_per_100000"]
        i_n = [i for i, r in enumerate(s) if r["state"] == "India" and r["year"] == y and r["indicator"] == "nns"]
        if not i_y:
            rows.append([y, "No table published", "", "", "", ""])
            continue
        iy, inn = i_y[0], i_n[0]
        mark = SUP[2] if y == "2022" else (SUP[1] if y == "2021" else "")
        rows.append([y, itr_table(s[iy]["chosen_source"]) + mark, tr.value(Q3S, s, iy, "denominator", "int"),
                     tr.value(Q3S, s, iy, "numerator", "int"),
                     tr.interval(Q3S, s, iy, "value", "lower", "upper", "dec1"),
                     tr.interval(Q3S, s, inn, "value", "lower", "upper", "dec0")])
    i = row_index(s, state="India", year="2021", indicator="acf_share_of_public_sector_notifications_pct")
    share = (f"{tr.value(Q3S, s, i, 'value', 'dec2')}% (95% CI {tr.value(Q3S, s, i, 'lower', 'dec2')} to "
             f"{tr.value(Q3S, s, i, 'upper', 'dec2')})")
    notes.append(f"{SUP[0]} Yield is diagnosed per 100,000 screened with a Wilson interval; the number needed to screen is the reciprocal, with the reciprocal Wilson bounds.")
    notes.append(f"{SUP[1]} For 2021, ACF diagnoses were {share} of public-sector notifications "
                 f"({itr_table(s[i]['chosen_source'])}); the denominator is public-sector notifications only, "
                 "so this is not a share of all notifications.")
    notes.append(f"{SUP[2]} Printed national row. In this annexure the State rows do not sum to the India row "
                 "(people screened, examined and diagnosed); the India row is used as printed.")
    return header, rows, notes


# --------------------------------------------------------------------------------------
# Supplementary tables (numbered in order of first citation in the text)
# --------------------------------------------------------------------------------------
Q4 = "outputs/q4_summary.csv"


def q4_status(r: dict) -> str:
    st = r["status"]
    if st == "fitted":
        return "fitted"
    if st.startswith("empty"):
        return "empty: no State has more campaign districts than districts"
    if st.startswith("not run") and "named list" in st:
        return "not run: the named list of campaign districts differs from CTD's table in four States"
    if st.startswith("not computable"):
        return "not computable: the lag proxy is equal in every State"
    if "refits" in st:
        return "refitted leaving out each unit in turn; no bootstrap"
    raise ValueError(f"unexpected Q4 status {st!r}")


def q4_label(r: dict) -> str:
    lab = r["label"].split(" (§")[0]
    if lab.startswith("not applicable"):
        return f"largest change on leaving out {r['loo_most_influential_unit']}"
    return lab


def supp_q4(tr: Trace):
    s = read(Q4)
    header = ["Analysis", "Denominator", "Status", "n", "γ1 (95% model interval)", "Bootstrap 95% interval", "exp(0.1γ1) (95% model interval)", "Label"]
    rows = []
    for i, r in enumerate(s):
        name = (r["analysis"].replace(" x0.", " ×0.").replace("with ln r", "with lag proxy")
                .replace("without ln r", "without lag proxy").replace("2022-2024", "2022–2024")
                .replace("January-October", "January to October"))
        if r["status"] == "fitted":
            g = tr.interval(Q4, s, i, "gamma1", "gamma1_model_lo", "gamma1_model_hi", "dec3")
            bs = (f"{tr.value(Q4, s, i, 'gamma1_boot_lo', 'dec3')} to {tr.value(Q4, s, i, 'gamma1_boot_hi', 'dec3')}"
                  if r["gamma1_boot_lo"] else "")
            e = tr.interval(Q4, s, i, "exp_0_1_gamma1", "exp_0_1_gamma1_model_lo", "exp_0_1_gamma1_model_hi", "dec3")
            rows.append([name, r["denominator_set"], q4_status(r), tr.value(Q4, s, i, "n", "int"), g, bs, e, q4_label(r)])
        elif r["loo_gamma1_min"]:
            rng_ = f"{tr.value(Q4, s, i, 'loo_gamma1_min', 'dec3')} to {tr.value(Q4, s, i, 'loo_gamma1_max', 'dec3')}"
            rows.append([name, r["denominator_set"], q4_status(r), tr.value(Q4, s, i, "n", "int"), rng_, "", "", q4_label(r)])
        else:
            rows.append([name, r["denominator_set"], q4_status(r), r["n"], "", "", "", ""])
    return header, rows, [
        "Denominator R is the registered district count; D is the count reconstructed from official notices "
        "(the main analysis, a deviation from the registered plan). For leaving out one unit at a time (S2), "
        "n is the number of units in each refit and the γ1 column gives the range over the refits. "
        "S8(a) multiplies the January to October 2025 counts by 0.98 or 0.95; S8(b) adds a State lag proxy, "
        "the log ratio of two 2023 counts. No P values are reported."]


def supp_q3_states(tr: Trace):
    s = read(Q3S)
    header = ["State", "Data year", "Source", "Screened (n)", "Diagnosed (n)", "Yield per 100,000 (95% CI)", "NNS (95% CI)"]
    rows = []
    by = {}
    for i, r in enumerate(s):
        by.setdefault((r["state"], r["year"], r["indicator"]), i)
    for (st, y, ind), iy in sorted(by.items()):
        if ind != "yield_diagnosed_per_100000":
            continue
        r = s[iy]
        inn = by[(st, y, "nns")]
        if r["status"] != "computed":
            rows.append([st, y, itr_table(r["chosen_source"]), "", "", STATUS[r["status"]], ""])
            continue
        nn = (tr.interval(Q3S, s, inn, "value", "lower", "upper", "dec0") if s[inn]["status"] == "computed"
              else STATUS[s[inn]["status"]])
        rows.append([st, y, itr_table(r["chosen_source"]), tr.value(Q3S, s, iy, "denominator", "int"),
                     tr.value(Q3S, s, iy, "numerator", "int"),
                     tr.interval(Q3S, s, iy, "value", "lower", "upper", "dec1"), nn])
    return header, rows, ["Not computable: no TB patient diagnosed, so the number needed to screen has no value "
                          "(the yield of 0 is shown with its Wilson interval). Not available: no value printed."]


Q2_SETS = [("Registered", "outputs/q2_discrepancies.csv", "S1a", "registered"),
           ("Corrected (post hoc)", "outputs/q2_discrepancies_corrected.csv", "S1b", "corrected")]


def group_parts(key: str) -> tuple[str, str, str]:
    """(quantity, geography, group) of a comparison group key: 'tb_cases|India|programme-wide|g01'
    -> ('TB cases', 'India', '1'); the named-list check 'named-list|districts_selected|Delhi' ->
    ('Districts selected', 'Delhi', 'named list')."""
    parts = key.split("|")
    if parts[0] == "named-list" and len(parts) == 3:
        return QUANTITY[parts[1]], parts[2], "named list"
    if len(parts) == 4 and re.fullmatch(r"g\d+", parts[3]):
        return QUANTITY[parts[0]], parts[1], str(int(parts[3][1:]))
    raise ValueError(f"unexpected comparison group key {key!r}")


def supp_q2_groups(tr: Trace):
    """Table S1: entry pairs and their classes by comparison group, both rule sets (all pairs,
    pre-specified and exploratory); a total row per set equals Table 2's 'all' columns."""
    header = ["Rules", "Quantity", "Geography", "Scope", "Group", "Pairs", "Agree", "1", "2", "3a", "3b", "4"]
    rows = []
    for label, f, _, _ in Q2_SETS:
        d = read(f)
        first = {}
        for r in d:
            first.setdefault(r["group_key"], r)
        for k, r0 in first.items():
            q, geo, g = group_parts(k)
            rows.append([label, q, geo, SCOPE[r0["scope"]], g, tr.count(f, d, {"group_key": k}),
                         tr.count(f, d, {"group_key": k, "agree": "yes"})]
                        + [tr.count(f, d, {"group_key": k, "class": c}) for c in CLASS_KEYS])
        rows.append([label, "All groups", "", "", "", tr.count(f, d, {}), tr.count(f, d, {"agree": "yes"})]
                    + [tr.count(f, d, {"class": c}) for c in CLASS_KEYS])
    return header, rows, [
        "Counts of entry pairs (pre-specified and exploratory) by comparison group. A comparison group holds "
        "figures of the same quantity, geography and scope with overlapping windows or identical window labels; "
        "groups are numbered within each quantity, geography and scope, and the two rule sets form different groups. "
        "Classes: 1, arithmetic error within a source; 2, definitional difference; 3a, window or cut-off difference, "
        "direction consistent with the windows; 3b, window or cut-off difference that does not explain the direction; "
        "4, unexplained. The 'All groups' rows equal the 'all' columns of Table 2. Every pair, with its values, "
        "sources, definitions, windows and the evidence for its class, is listed in Supplementary data S1a "
        "(registered rules) and S1b (corrected rules)."]


# --------------------------------------------------------------------------------------
# Supplementary data S1a and S1b: every entry pair, one row each (CSV; an XLSX copy is made
# by tools/build_submission.py). Columns marked verbatim are copied from outputs/ unchanged.
# --------------------------------------------------------------------------------------
DATA_COLUMNS: list[tuple[str, str, str]] = [  # (header, output column or derivation, description)
    ("Pair", "=row", "Running number of the pair in this file (the row order of the analysis output)."),
    ("Quantity", "=quantity", "Quantity compared (people screened, people tested, TB cases, districts selected, and so on)."),
    ("Geography", "geography", "India or the State or Union Territory (verbatim)."),
    ("Scope", "=scope", "First phase, expanded campaign, programme-wide, or scope not stated."),
    ("Comparison group", "=group", "Group number within the quantity, geography and scope, or 'named list' for the check of the named list of campaign districts against CTD's table (as in Table S1)."),
    ("Analysis", "analysis", "Pre-specified, or exploratory (cross-checks added after registration) (verbatim)."),
    ("Agree", "agree", "yes if the two figures' intervals overlap (verbatim)."),
    ("Class", "class", "Class of a pair that does not agree: 1, 2, 3a, 3b or 4, as in Table 2 (verbatim)."),
    ("Class label", "class_label", "The class in words (verbatim)."),
    ("A document", "=a_doc", "The document that prints figure A."),
    ("A value (printed)", "a_value_printed", "Figure A as printed (verbatim; two printings of one value are joined by ' | ')."),
    ("A qualifier", "a_qualifier", "exact, about or at_least, from the wording of figure A (verbatim)."),
    ("A interval", "a_interval", "The interval figure A stands for, after rounding and qualifier (verbatim)."),
    ("A definition", "a_definition_class", "The definition printed with figure A, for example notified or diagnosed (verbatim)."),
    ("A window", "a_window", "Start..end of figure A's window, its cut-off date (as_on) and window label (verbatim)."),
    ("B document", "=b_doc", "As for A, for figure B."),
    ("B value (printed)", "b_value_printed", "As for A (verbatim)."),
    ("B qualifier", "b_qualifier", "As for A (verbatim)."),
    ("B interval", "b_interval", "As for A (verbatim)."),
    ("B definition", "b_definition_class", "As for A (verbatim)."),
    ("B window", "b_window", "As for A (verbatim)."),
    ("Same document", "same_document", "yes if A and B come from one document (verbatim)."),
    ("Evidence", "evidence", "The record of the decision order that gave the class (verbatim). Numbers after the "
                             "section sign are sections of the registered analysis plan; a dotted code names a "
                             "figure of the deposited inventory."),
]


def supplementary_data(f: str) -> tuple[list[str], list[list[str]]]:
    """Every entry pair of one Q2 output, with the DATA_COLUMNS."""
    d = read(f)
    rows = []
    for i, r in enumerate(d, 1):
        q, _, g = group_parts(r["group_key"])
        derived = {"=row": str(i), "=quantity": q, "=scope": SCOPE[r["scope"]], "=group": g,
                   "=a_doc": doc_name(r["a_source"]), "=b_doc": doc_name(r["b_source"])}
        rows.append([derived[c] if c.startswith("=") else r[c] for _, c, _ in DATA_COLUMNS])
    return [h for h, _, _ in DATA_COLUMNS], rows


def supplementary_data_bytes(f: str) -> bytes:
    """The CSV file of one Q2 output, exactly as written (UTF-8, LF)."""
    header, rows = supplementary_data(f)
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def data_file_name(tag: str, kind: str) -> str:
    return f"supplementary_data_{tag}_{kind}.csv"


def data_dictionary_md() -> str:
    lines = ["## Supplementary data S1a and S1b. Column dictionary\n",
             md_table(["Column", "Content"], [[h, desc] for h, _, desc in DATA_COLUMNS]) + "\n",
             "Supplementary data S1a lists every entry pair under the registered rules and S1b under the "
             "corrected (post hoc) rules, one row per pair, agreeing pairs included, as CSV (UTF-8) files and as "
             "one workbook with a sheet for each. Columns marked verbatim are copied unchanged from the deposited "
             "analysis outputs.\n"]
    return "\n".join(lines)


STUDY = {"GHA2023": "Shewade et al. 2023 (national, first ACF cycle of 2021)",
         "PGPH2025": "Shewade et al. 2025 (30 districts, January to September 2023)"}


def supp_quality(tr: Trace):
    f = "outputs/q2_quality_studies.csv"
    d = read(f)
    header = ["Study", "Indicator", "Published", "Recomputed (95% CI)", "Recomputable", "Within rounding"]
    rows = []
    for i, r in enumerate(d):
        # C4 (people) in whole numbers; a percentage below 1 to three decimals, else two
        fmt = "dec0" if r["indicator"] == "C4" else ("dec3" if r["recomputed"] and float(r["recomputed"]) < 1 else "dec2")
        rc = (tr.interval(f, d, i, "recomputed", "ci95_low", "ci95_high", fmt) if r["recomputed"] else "")
        rows.append([STUDY[r["study"]], r["indicator"], f_printed(r["published_value"]), rc, r["recomputable"],
                     r["published_within_rounding"]])
    return header, rows, [
        "C1, people diagnosed among people tested (%); C2, people tested among people screened (%); "
        "C3, people tested among people with presumptive TB (%); C4, number needed to screen (people screened "
        "per person diagnosed). Intervals are Wilson intervals; for C4, the reciprocals of the Wilson bounds."]


def build() -> tuple[dict, Trace]:
    tr = Trace()
    ex: dict[str, dict] = {}
    h, r, n = table1(tr)
    ex["Table 1"] = {"title": "Inventory of published campaign figures and Q1 consistency checks", "panels": [(h, r)], "notes": n, "main": True}
    h, r, n = table2(tr)
    ex["Table 2"] = {"title": "Discrepancy classes among published figures, registered and corrected rules, with the class 1 and 2 pairs (corrected set)",
                     "panels": [(h, r)], "notes": n, "main": True}
    h, r, n = table3(tr)
    ex["Table 3"] = {"title": "National yield and number needed to screen by data year", "panels": [(h, r)], "notes": n, "main": True}
    h, r, n = supp_q2_groups(tr)
    ex["Table S1"] = {"title": "Entry pairs and their classes by comparison group, registered and corrected rules",
                      "panels": [(h, r)], "notes": n, "main": False}
    h, r, n = supp_quality(tr)
    ex["Table S2"] = {"title": "Reconciliation of the two quality studies", "panels": [(h, r)], "notes": n, "main": False}
    h, r, n = supp_q3_states(tr)
    ex["Table S3"] = {"title": "State-level yield and number needed to screen by data year", "panels": [(h, r)], "notes": n, "main": False}
    h, r, n = supp_q4(tr)
    ex["Table S4"] = {"title": "Dose–response analysis: primary analysis, sensitivity analyses and placebo under both district denominators", "panels": [(h, r)], "notes": n, "main": False}
    return ex, tr

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ex, tr = build()
    md = ["# Tables (generated from outputs/ by exhibits/make_tables.py)\n"]
    for name, e in ex.items():
        md.append(f"## {name}. {e['title']}\n")
        for k, (h, r) in enumerate(e["panels"]):
            md.append(md_table(h, r) + "\n")
            write_csv(name.replace(" ", "").lower() + ("" if len(e["panels"]) == 1 else "_" + "ab"[k]), h, r)
        for n in e["notes"]:
            md.append(n + "\n")
    md.append(data_dictionary_md())
    for _, f, tag, kind in Q2_SETS:
        (OUT / data_file_name(tag, kind)).write_bytes(supplementary_data_bytes(f))
    (OUT / "tables.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
    (OUT / "trace.json").write_text(json.dumps(tr.entries, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(ex)} tables, {len(tr.entries)} traced cells)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
