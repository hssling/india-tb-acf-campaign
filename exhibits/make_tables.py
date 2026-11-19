# Adapted from hssling/india-state-tb-score (MIT), exhibits/make_tables.py, commit 05bcaa7; modified: rewritten for the ACF campaign study (tables of Q1-Q4 read from outputs/ and data/; every cell is traced to its source file and column); only the layout idea (a render function, Markdown output, no typed numbers) is kept
"""Render every manuscript table from outputs/ and data/ to manuscript/exhibits/.

Run as: python -I exhibits/make_tables.py   (from the repository root)

manuscript/ is git-ignored and local. Standard library only. Output:
- tables.md                      main-text Tables 1-3 and the supplementary tables, as Markdown
                                 (tables without vertical rules; footnotes as superscript
                                 lowercase letters, Public Health);
- <table id>.csv                 each table as CSV (LF line endings);
- trace.json                     every numeric cell with its source file, row, column and
                                 the formatter, so a test can re-derive it from outputs/.

No number is typed here. Every numeric cell is read from outputs/ or data/ (or is a count of
rows of one of those files, with the filter recorded) and formatted by the helpers below.
"""
from __future__ import annotations

import csv
import json
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
        return s.replace("-", MINUS)
    fmt.__name__ = f"dec{d}"
    return fmt


FORMATTERS = {"int": f_int, "dec0": f_dec(0), "dec1": f_dec(1), "dec2": f_dec(2), "dec3": f_dec(3), "raw": lambda s: s}


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


def md_table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
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
# Table 1: inventory and Q1 consistency checks
# --------------------------------------------------------------------------------------
NAMED = [("tb_cases", "TB cases (notified or diagnosed)"), ("screened", "Screened"), ("tested", "Tested"),
         ("nns", "Number needed to screen"), ("districts_selected", "Districts selected"),
         ("population_targeted", "Population targeted")]
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
    notes = [f"{SUP[0]} Figures of quantities other than the named quantities listed above; their sums and percentages are described in the supplement, not tested.",
             f"{SUP[1]} Post hoc correction of the registered rules (analysis plan section 13); the registered rules are shown first."]
    return header, rows, notes


# --------------------------------------------------------------------------------------
# Table 2: Q2 discrepancy classes, registered vs corrected, and the class 1 and 2 pairs
# --------------------------------------------------------------------------------------
Q2S = "outputs/q2_summary_registered_vs_corrected.csv"
CLASS_KEYS = ["1", "2", "3a", "3b", "4"]  # labels are read from the class_label column of the output


def table2(tr: Trace):
    s = read(Q2S)
    header = ["Class of entry pair", "Registered, all", "Registered, pre-specified", "Corrected, all", "Corrected, pre-specified"]
    rows = []

    def cells(metric_all, metric_pre):
        out = []
        for metric in (metric_all, metric_pre):
            i = row_index(s, metric=metric)
            out.append(tr.value(Q2S, s, i, "registered", "int"))
            out.append(tr.value(Q2S, s, i, "corrected", "int"))
        return [out[0], out[2], out[1], out[3]]  # reg all, reg pre, corr all, corr pre

    rows.append(["Entry pairs compared"] + cells("Q2 entry pairs (all)", "Q2 entry pairs (pre-specified)"))
    rows.append(["Agree"] + cells("Q2 all: agree", "Q2 pre-specified: agree"))
    lab = {r["class"]: r["class_label"] for r in read("outputs/q2_discrepancies_corrected.csv") if r["class"]}
    for k in CLASS_KEYS:
        label = f"{k} {lab[k][0].upper()}{lab[k][1:]}"
        rows.append([label] + cells(f"Q2 all: class {k}", f"Q2 pre-specified: class {k}"))
    rows.append(["Comparison groups formed"] + [
        tr.value(Q2S, s, row_index(s, metric="Q2 comparison groups formed (§7.1)"), "registered", "int"), "",
        tr.value(Q2S, s, row_index(s, metric="Q2 comparison groups formed (§7.1)"), "corrected", "int"), ""])
    notesA = [f"{SUP[0]} Entry pairs are pairs of distinct (document, value) entries within a comparison group; the corrected set applies three post hoc corrections (analysis plan section 13)."]

    f = "outputs/q2_discrepancies_corrected.csv"
    d = read(f)
    headerB = ["Class", "Quantity and scope", "Value in A (as printed)", "Value in B (as printed)", "Evidence"]
    rowsB = []
    for i, r in enumerate(d):
        if r["class"] in ("1", "2"):
            rowsB.append([r["class"], f"{r['quantity']}, {r['geography']}, {r['scope']}",
                          tr.value(f, d, i, "a_value_printed", "raw"), tr.value(f, d, i, "b_value_printed", "raw"),
                          r["evidence"].split(" (source:")[0].split(" | ")[0][:160].replace("|", ";")])
    return header, rows, notesA, headerB, rowsB


# --------------------------------------------------------------------------------------
# Table 3: Q3 national yield and NNS by data year
# --------------------------------------------------------------------------------------
Q3S = "outputs/q3_yield_summary.csv"
Q3 = "outputs/q3_yield.csv"


def table3(tr: Trace):
    s = read(Q3S)
    full = read(Q3)
    header = ["Data year", "Source table", "Screened (n)", "Diagnosed (n)", "Yield per 100,000 screened (95% CI)", "Number needed to screen (95% CI)"]
    years = sorted({r["year"] for r in full})
    rows, notes = [], []
    for y in years:
        i_y = [i for i, r in enumerate(s) if r["state"] == "India" and r["year"] == y and r["indicator"] == "yield_diagnosed_per_100000"]
        i_n = [i for i, r in enumerate(s) if r["state"] == "India" and r["year"] == y and r["indicator"] == "nns"]
        if not i_y:
            rows.append([y, "No table published", "", "", "", ""])
            continue
        iy, inn = i_y[0], i_n[0]
        rows.append([y, s[iy]["chosen_source"], tr.value(Q3S, s, iy, "denominator", "int"),
                     tr.value(Q3S, s, iy, "numerator", "int"),
                     tr.interval(Q3S, s, iy, "value", "lower", "upper", "dec1"),
                     tr.interval(Q3S, s, inn, "value", "lower", "upper", "dec1")])
    i = row_index(s, state="India", year="2021", indicator="acf_share_of_public_sector_notifications_pct")
    share = tr.interval(Q3S, s, i, "value", "lower", "upper", "dec2")
    notes.append(f"{SUP[0]} Printed national rows. The ITR2023 annexure State rows do not sum to its India row (checks TOT-012 to TOT-014); the India row is used as printed.")
    notes.append(f"{SUP[1]} For 2021, the share of ACF-diagnosed among public-sector notifications was {share} per cent; its denominator is public-sector notifications only, so it is not a national share of all notifications.")
    notes.append(f"{SUP[2]} Yield is diagnosed per 100,000 screened with a Wilson interval; the number needed to screen is the reciprocal, with the reciprocal Wilson bounds.")
    return header, rows, notes


# --------------------------------------------------------------------------------------
# Supplementary tables
# --------------------------------------------------------------------------------------
Q4 = "outputs/q4_summary.csv"


def supp_q4(tr: Trace):
    s = read(Q4)
    header = ["Analysis", "Denominator", "Status", "n", "gamma1 (95% model interval)", "Bootstrap 95% interval", "exp(0.1 x gamma1)", "Label"]
    rows = []
    for i, r in enumerate(s):
        if r["status"] == "fitted":
            g = tr.interval(Q4, s, i, "gamma1", "gamma1_model_lo", "gamma1_model_hi", "dec3")
            bs = (f"{tr.value(Q4, s, i, 'gamma1_boot_lo', 'dec3')} to {tr.value(Q4, s, i, 'gamma1_boot_hi', 'dec3')}"
                  if r["gamma1_boot_lo"] else "")
            e = tr.interval(Q4, s, i, "exp_0_1_gamma1", "exp_0_1_gamma1_model_lo", "exp_0_1_gamma1_model_hi", "dec3")
            rows.append([r["analysis"], r["denominator_set"], r["status"], tr.value(Q4, s, i, "n", "int"), g, bs, e, r["label"]])
        else:
            rows.append([r["analysis"], r["denominator_set"], r["status"][:120], r["n"], "", "", "", ""])
    return header, rows, ["Denominator R is the registered district count; D is the count reconstructed from official notices (deviation, analysis plan section 13). No P values are reported."]


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
            rows.append([st, y, r["chosen_source"], "", "", r["status"], ""])
            continue
        nn = (tr.interval(Q3S, s, inn, "value", "lower", "upper", "dec0") if s[inn]["status"] == "computed" else s[inn]["status"])
        rows.append([st, y, r["chosen_source"], tr.value(Q3S, s, iy, "denominator", "int"),
                     tr.value(Q3S, s, iy, "numerator", "int"),
                     tr.interval(Q3S, s, iy, "value", "lower", "upper", "dec1"), nn])
    return header, rows, []


def supp_q2_full(tr: Trace, f: str):
    d = read(f)
    header = ["Quantity", "Geography", "Scope", "Class", "Analysis", "A value (printed)", "B value (printed)", "A source", "B source"]
    rows = []
    for i, r in enumerate(d):
        if r["class"]:
            rows.append([r["quantity"], r["geography"], r["scope"], r["class"], r["analysis"],
                         tr.value(f, d, i, "a_value_printed", "raw"), tr.value(f, d, i, "b_value_printed", "raw"),
                         Path(r["a_source"]).name, Path(r["b_source"]).name])
    return header, rows, []


def supp_quality(tr: Trace):
    f = "outputs/q2_quality_studies.csv"
    d = read(f)
    header = ["Study", "Indicator", "Published", "Recomputed (95% CI)", "Recomputable", "Within rounding"]
    rows = []
    for i, r in enumerate(d):
        rc = (tr.interval(f, d, i, "recomputed", "ci95_low", "ci95_high", "dec2") if r["recomputed"] else "")
        rows.append([r["study"], r["indicator"], r["published_value"], rc, r["recomputable"], r["published_within_rounding"]])
    return header, rows, []


def build() -> tuple[dict, Trace]:
    tr = Trace()
    ex: dict[str, dict] = {}
    h, r, n = table1(tr)
    ex["Table 1"] = {"title": "Inventory of published campaign figures and Q1 consistency checks", "panels": [(h, r)], "notes": n, "main": True}
    h, r, n, hb, rb = table2(tr)
    ex["Table 2"] = {"title": "Discrepancy classes among published figures, registered and corrected rules, with the class 1 and 2 pairs (corrected set)",
                     "panels": [(h, r), (hb, rb)], "notes": n, "main": True}
    h, r, n = table3(tr)
    ex["Table 3"] = {"title": "National yield and number needed to screen by data year", "panels": [(h, r)], "notes": n, "main": True}
    h, r, n = supp_q4(tr)
    ex["Table S1"] = {"title": "Q4 dose-response: primary analysis and sensitivity analyses under both denominators", "panels": [(h, r)], "notes": n, "main": False}
    h, r, n = supp_q3_states(tr)
    ex["Table S2"] = {"title": "State-level yield and number needed to screen by data year", "panels": [(h, r)], "notes": n, "main": False}
    h, r, n = supp_q2_full(tr, "outputs/q2_discrepancies.csv")
    ex["Table S3a"] = {"title": "Full list of discrepancies, registered rules", "panels": [(h, r)], "notes": n, "main": False}
    h, r, n = supp_q2_full(tr, "outputs/q2_discrepancies_corrected.csv")
    ex["Table S3b"] = {"title": "Full list of discrepancies, corrected rules (post hoc)", "panels": [(h, r)], "notes": n, "main": False}
    h, r, n = supp_quality(tr)
    ex["Table S4"] = {"title": "Reconciliation of the two quality studies", "panels": [(h, r)], "notes": n, "main": False}
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
    (OUT / "tables.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
    (OUT / "trace.json").write_text(json.dumps(tr.entries, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(ex)} tables, {len(tr.entries)} traced cells)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
