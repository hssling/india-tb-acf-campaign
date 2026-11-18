"""Campaign documents: the phase-1 exposure table (analysis plan §9.2), the named-list
cross-check (§9.2), and the campaign and press figures for the figure inventory (§5).

Exposure: CTD, *100 Days Campaign*, PDF page 7, table "State | Total District" in two
column blocks (33 State/UT rows and TOTAL), with checks E1-E7. Labels follow the label
rule of §9.2: a label that stays unmapped makes that row's State not computable (it
is listed; its count still enters E1 and E2).

Inventory: the figures of the §5.1 quantities in the official campaign and press
documents of data_raw/official/ (other than the India TB Reports). Each figure was
located by reading the document; the specification below records where. The context
is read literally from §5.2 as clarified in §13 (19 November 2026): a figure in prose
has its own sentence; a figure in a table cell has "table title | column heading |
row label". No lead-in or section heading is added. Value, qualifier (§6.1),
definition class and scope (§7.2) and window label (§7.1) then follow by rule, and
every quoted context is checked against the PDF text of its page (or recorded as read
from the page image where the page has no usable text layer).

Scope rule for `other:` items, and every figure considered and left out, are written to
data/extracted/inventory_scope_decisions.csv.

Run: python -I src/extract/campaign.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import csv
import re
from collections import Counter
from dataclasses import dataclass, field

from src import inventory_rules as R
from src import states
from src.extract import labels
from src.extract.cells import parse_int
from src.extract.pdftext import page_lines

ROOT = Path(__file__).resolve().parents[2]
OFF = "data_raw/official/"
EXTRACTED = ROOT / "data/extracted"
INVENTORY = ROOT / "data/figures_inventory.csv"

CTD_FILE = OFF + "100-days-campaign-Report-1-Complete-on-5-12-2024-New.pdf"
CTD_PAGE = 7          # PDF page of the exposure table (printed page 5)
CRITERIA_PAGE = 6     # selection-criteria table (E6)
KERALA_FILE = OFF + "TB_Elimination_Campaign.pdf"
NAMED_LIST_PAGES = range(12, 29)   # Annexure-I of the D.O. letter (PDF pp. 12-28)

# document key -> (file, pub_date, remark on the date)
SOURCES: dict[str, tuple[str, str, str]] = {
    "CTD100": (CTD_FILE, "2024-12-05", "pub_date from the file name; no date printed"),
    "TMBA26": (OFF + "TB-Mukt-Bharat-Abhiyan-Campaign-2026-v6.pdf", "",
               "no date printed in the document"),
    "GUIDE": (OFF + "Guidance-Document-on-TB-Mukt-Bharat-Abhiyan_0.pdf", "",
              "no date printed in the document"),
    "PIBSYN": (OFF + "doc2024127466601.pdf", "2024-12-07",
               "pub_date from the file name; no date printed"),
    "PIBBG": (OFF + "doc2024126465901.pdf", "2024-12-06", ""),
    "PIB26": (OFF + "doc2026324833001.pdf", "2026-03-24", ""),
    "PIBYER": (OFF + "doc20241228477601.pdf", "2024-12-28",
               "pub_date from the file name; no date printed"),
    "KERALA": (KERALA_FILE, "2024-12-06", "pub_date of the covering letter (PDF page 1)"),
}
OWN_FILES = frozenset(f for f, _, _ in SOURCES.values())

INVENTORY_COLUMNS = [
    "fig_id", "quantity", "value", "value_printed", "qualifier", "unit",
    "definition_verbatim", "context_verbatim", "definition_class", "scope",
    "series_type", "window_label", "window_start", "window_end", "as_on",
    "as_on_basis", "geography", "source_file", "source_url", "page_or_para",
    "table_id", "pub_date", "note"]

CELL = " | "   # joins table title | column heading | row label


# =================================================================== exposure table

_PAIR = re.compile(r"([^\d]+?)\s+(\d+)(?=\s|$)")


def parse_exposure_lines(lines: list[str]) -> tuple[list[tuple[str, int]], int | None]:
    """Rows (label, count) of the two-block table, left block first, and the TOTAL
    (None if no TOTAL row is printed)."""
    start = next(i for i, ln in enumerate(lines)
                 if re.fullmatch(r"State Total District State Total District", ln.strip()))
    left: list[tuple[str, int]] = []
    right: list[tuple[str, int]] = []
    total = None
    for ln in lines[start + 1:]:
        pairs = [(m.group(1).strip(), int(m.group(2))) for m in _PAIR.finditer(ln.strip())]
        if not pairs:
            break
        for k, (label, n) in enumerate(pairs):
            if label.upper() == "TOTAL":
                total = n
            else:
                (left if k == 0 else right).append((label, n))
        if total is not None:
            break
    return left + right, total


def read_exposure_table(pdf: Path, page: int = CTD_PAGE):
    return parse_exposure_lines(page_lines(pdf, page))


def map_rows(rows: list[tuple[str, int]]) -> list[tuple[str, str, int]]:
    """(label, canonical, count). An unmapped label gives a blank canonical name
    (§9.2 step 3): the row is listed as not computable and still counts in E1/E2."""
    return [(lab, labels.resolve_or_list(lab).canonical, n) for lab, n in rows]


@dataclass
class ExposureResult:
    checks: list[dict]
    units: list[dict]
    rejected: bool
    reject_reasons: list[str] = field(default_factory=list)
    not_computable_rows: list[str] = field(default_factory=list)


def _fmt(x: float) -> str:
    return f"{x:.6f}".rstrip("0").rstrip(".")


def _yn(ok: bool) -> str:
    return "yes" if ok else "no"


def coarse_lgd(counts: dict[str, int | None]) -> dict[str, int | None]:
    """LGD count per coarsened unit (§9.4): the sum over its members, None if any
    member is not computable."""
    out: dict[str, int | None] = {}
    for s, n in counts.items():
        u = states.coarsen(s)
        if u in out and out[u] is None:
            continue
        out[u] = None if n is None else out.get(u, 0) + n
    return out


def check_exposure(rows: list[tuple[str, str, int]], total: int | None,
                   lgd: dict[str, int | None], e6_number: int | None = None,
                   e7: tuple[int | None, int | None] = (None, None)) -> ExposureResult:
    """Checks E1-E7 of §9.2 and the exposure share of §9.3, per coarsened unit.

    rows: (label, canonical or "" if unmapped, count); lgd: coarse unit ->
    reconstructed LGD count at 7 December 2024 (None where not computable)."""
    checks: list[dict] = []
    s = sum(c for _, _, c in rows)

    def add(check, inputs, expected, observed, ok, note=""):
        checks.append({"check": check, "inputs": inputs, "expected": expected,
                       "observed": observed, "pass": ok, "note": note})

    e1 = total == 347
    add("E1", "TOTAL row", "347", "" if total is None else str(total), _yn(e1),
        "" if total is not None else "no TOTAL row printed")
    e2 = total is not None and s == total
    add("E2", "sum of State/UT rows (mapped or not); TOTAL row",
        "" if total is None else str(total), str(s), _yn(e2))
    unmapped = [lab for lab, canon, _ in rows if not canon]
    add("E3", "State/UT rows mapped by the label rule", "33 rows, each mapped",
        f"{len(rows)} rows, {len(rows) - len(unmapped)} mapped",
        _yn(len(rows) == 33 and not unmapped),
        ("not computable (label rule step 3): " + "; ".join(unmapped)) if unmapped
        else "step-2 resolutions are logged in exposure_campaign.csv")

    by_unit: dict[str, int] = {}
    for _, canon, c in rows:
        if canon:
            u = states.coarsen(canon)
            by_unit[u] = by_unit.get(u, 0) + c
    units = []
    for u in sorted({states.coarsen(x) for x in states.ALL}):
        c = by_unit.get(u, 0)
        L = lgd.get(u)
        rec = {"unit": u, "in_table": _yn(u in by_unit), "campaign_count": c,
               "lgd_count": "" if L is None else L, "share": "", "capped": "",
               "flagged_e5": "", "computable": "yes", "reason": ""}
        if L is None or L <= 0:
            rec["computable"] = "no"
            rec["reason"] = ("LGD district count at 7 December 2024 not computable "
                             "(analysis plan §9.3)")
        else:
            share = min(1.0, c / L)
            rec["share"] = "1" if share == 1.0 else _fmt(share)
            rec["capped"] = _yn(share == 1.0)
            rec["flagged_e5"] = _yn(c > L)
            if c > L:
                rec["reason"] = "campaign count above LGD count: flagged and capped (E5)"
            elif share == 1.0:
                rec["reason"] = "every district in the campaign: capped"
        units.append(rec)

    evaluable = [u for u in units if u["computable"] == "yes"]
    n_not = len(units) - len(evaluable)
    in_table = [u for u in evaluable if u["in_table"] == "yes"]
    below_in_table = [u for u in in_table if u["campaign_count"] < u["lgd_count"]]
    below_all = [u for u in evaluable if u["campaign_count"] < u["lgd_count"]]
    e4 = len(below_in_table) >= 5
    add("E4", "units in the table with a computable LGD count",
        "at least 5 with campaign count below LGD count",
        f"{len(below_in_table)} of {len(in_table)}", _yn(e4),
        "counted over the units in the table only (the column is what E4 tests); "
        f"counting also the units absent from the table (campaign count 0): "
        f"{len(below_all)}, which {'also passes' if len(below_all) >= 5 else 'fails'}; "
        f"units not evaluated because their LGD count is not computable: {n_not}")
    flagged = [u["unit"] for u in units if u["flagged_e5"] == "yes"]
    e5 = len(flagged) <= 3
    add("E5", "units with a computable LGD count", "at most 3 flagged",
        f"{len(flagged)} flagged", _yn(e5),
        (("flagged: " + "; ".join(flagged)) if flagged else "none flagged") +
        f"; units not evaluated because their LGD count is not computable (§9.3): "
        f"{n_not}")
    if e6_number is None:
        add("E6", "criteria table (PDF page 6) and the text with it",
            "347 if a number selected is printed", "no number printed", "n/a",
            "report only")
    else:
        add("E6", "criteria table (PDF page 6) and the text with it", "347",
            str(e6_number), _yn(e6_number == 347),
            "report only; per-criterion counts are entered in the inventory, not tested")
    d, n = e7
    add("E7", "sentence with the table", f"347 districts; {len(rows)} States/UTs",
        f"{d} districts; {n} States/UTs" if d is not None else "no sentence found",
        _yn(d == 347 and n == len(rows)), "report only")

    reasons = []
    if not e1:
        reasons.append("E1 failed")
    if not e2:
        reasons.append("E2 failed")
    if not e4:
        reasons.append("E4 failed")
    if not e5:
        reasons.append("more than 3 States flagged under E5")
    return ExposureResult(checks, units, bool(reasons), reasons, unmapped)


# =================================================================== printed totals

def total_check(name: str, file: str, page: int, values: list[int],
                printed_total: int | None) -> dict:
    """Printed-total check of a State table: rows sum to the printed total within
    ±1 (§6.2 check 3; §9.6). No total printed: the check is not applied, and said so."""
    s = sum(values)
    rec = {"table": name, "source_file": file, "page": page, "rows": len(values),
           "sum_of_rows": s, "printed_total": "" if printed_total is None else printed_total,
           "difference": "" if printed_total is None else s - printed_total,
           "pass": "", "note": ""}
    if printed_total is None:
        rec["pass"] = "n/a"
        rec["note"] = "no total printed: sum check not applied"
    else:
        rec["pass"] = _yn(abs(s - printed_total) <= 1)
        rec["note"] = "values kept exactly as printed"
    return rec


def parse_village_table(lines: list[str]) -> tuple[list[tuple[str, str]], str | None]:
    """Annexure IV of the 2026 campaign document: (label, printed figure) rows and the
    printed Total."""
    start = next(i for i, ln in enumerate(lines)
                 if ln.startswith("States and UT No. of High Risk Villages and Wards"))
    rows, total = [], None
    for ln in lines[start + 1:]:
        m = re.fullmatch(r"(.+?) (\d[\d,]*)", ln.strip())
        if not m:
            break
        if m.group(1) == "Total":
            total = m.group(2)
            break
        rows.append((m.group(1), m.group(2)))
    return rows, total


# =================================================================== named list (§9.2)

def named_list_state_labels(pdf: Path, pages=NAMED_LIST_PAGES) -> list[tuple[int, str]]:
    """(page, State label) for each row of Annexure-I of the Kerala copy of the
    Ministry letter, read from the State column only.

    Rows are the bands between the table's horizontal rules; only characters whose
    centre lies inside the first column (between the first two vertical rules) are
    read, so no other column (names, e-mail addresses, telephone numbers) is ever
    read. A row cut by a page break (first band of a page whose State text is blank or
    not a State name on its own) is joined to the last row of the previous page."""
    import pdfplumber

    bands: list[list] = []   # [page, text, first_on_page]
    with pdfplumber.open(pdf) as doc:
        for p in pages:
            pg = doc.pages[p - 1]
            vs = sorted({round(ln["x0"], 1) for ln in pg.lines
                         if abs(ln["x0"] - ln["x1"]) < 1})
            hs = sorted({round(ln["top"], 1) for ln in pg.lines
                         if abs(ln["top"] - ln["bottom"]) < 1})
            x0, x1 = vs[0], vs[1]
            chars = [c for c in pg.chars if x0 <= (c["x0"] + c["x1"]) / 2 <= x1]
            first = True
            for a, b in zip(hs, hs[1:]):
                cs = [c for c in chars if a < (c["top"] + c["bottom"]) / 2 < b]
                lines: dict[int, list] = {}
                for c in cs:
                    lines.setdefault(round(c["top"]), []).append(c)
                text = " ".join("".join(ch["text"] for ch in sorted(ln, key=lambda c: c["x0"]))
                                for _, ln in sorted(lines.items()))
                text = " ".join(text.split())
                if text == "State":
                    continue        # header row
                bands.append([p, text, first])
                first = False
    out: list[list] = []
    for p, text, first in bands:
        alone = labels.resolve_or_list(text).step < 3 if text else False
        if first and out and not alone:
            out[-1][1] = (out[-1][1] + " " + text).strip()
            continue
        out.append([p, text])
    return [(p, t) for p, t in out]


def named_list_check(list_labels: list[tuple[int, str]],
                     ctd_rows: list[tuple[str, str, int]]) -> list[dict]:
    """Per State: CTD count against the number of rows of the named list."""
    res = [labels.resolve_or_list(t) for _, t in list_labels]
    counts = Counter(r.canonical for r in res)
    forms: dict[str, set] = {}
    steps: dict[str, set] = {}
    for r in res:
        forms.setdefault(r.canonical, set()).add(r.label)
        steps.setdefault(r.canonical, set()).add(str(r.step))
    ctd = {canon: n for _, canon, n in ctd_rows if canon}
    out = []
    for s in sorted(set(ctd) | set(counts)):
        a, b = ctd.get(s, 0), counts.get(s, 0)
        out.append({"state": s or "(label not mappable)", "ctd_count": a,
                    "named_list_rows": b, "match": _yn(a == b),
                    "named_list_labels": "; ".join(sorted(forms.get(s, ()))),
                    "label_rule_step": "; ".join(sorted(steps.get(s, ()))),
                    "note": "" if a == b else "Q2 discrepancy candidate (§9.2 named list)"})
    tot_a = sum(ctd.values())
    tot_b = len(res)
    out.append({"state": "TOTAL", "ctd_count": tot_a, "named_list_rows": tot_b,
                "match": _yn(tot_a == tot_b), "named_list_labels": "",
                "label_rule_step": "",
                "note": "CTD: sum of State rows; named list: all rows"})
    return out


# =================================================================== inventory specs

@dataclass
class Spec:
    doc: str
    page: int
    quantity: str
    printed: str
    unit: str
    definition: str
    sentence: str = ""         # prose: the figure's own sentence
    title: str = ""            # table cell: table title (blank if the table has none)
    col: str = ""              # table cell: column heading
    row: str = ""              # table cell: row label
    cell: str = ""             # table cell: the cell text (qualifier read from it)
    occurrence: int = 1
    period: str = ""
    series: str = ""
    wstart: str = ""
    wend: str = ""
    as_on: str = ""
    geography: str = "India"
    table_id: str = ""
    para: str = ""
    note: str = ""
    image: bool = False            # read from the page image (no usable text layer)
    pub_date: str | None = None    # overrides the document's date for this page
    basis: str = ""                # for resources and targets: why it is in scope
    key: str = ""                  # locator for fig_id where the label is not unique

    @property
    def is_table(self) -> bool:
        return bool(self.col or self.row)

    @property
    def context(self) -> str:
        if self.is_table:
            return CELL.join(x for x in (self.title, self.col, self.row) if x)
        return self.sentence


_PROG_W = dict(period="", wstart="2024-12-07", wend="2025-12-30", series="period")
_PROG_NOTE = ("window stated in the list heading 'Progress made under TB Mukt Bharat "
              "Abhiyaan (07th December 2024 to 30th December 2025):'")
_G10_W = dict(wstart="2024-12-07", wend="2025-03-24", series="period")
_G10_NOTE = ("window stated in the preceding sentence of the same paragraph ('launched "
             "on 7th December 2024 and culminated on 24th March 2025')")
_NO_UNIT = "unit ({}) not in the §5.2 unit vocabulary"
_TARGET_CTD = ("campaign target: the list's lead-in reads 'Specific Outputs expected "
               "from the Campaign are as under:'")


def _district_table_specs(doc: str, page: int, lines: list[str], para: str,
                          total_note: str) -> list[Spec]:
    rows, total = parse_exposure_lines(lines)
    out = []
    for label, n in rows + [("TOTAL", total)]:
        if label == "TOTAL":
            geo, note = "India", total_note
        else:
            r = labels.resolve_or_list(label)
            geo = r.canonical
            note = "" if r.step == 1 else (
                f"State label printed as '{label}'; label rule step {r.step}: {r.evidence}")
        out.append(Spec(doc, page, "districts_selected", str(n), "districts",
                        "Total District", col="Total District", row=label, cell=str(n),
                        geography=geo, table_id="State | Total District", para=para,
                        note=note))
    return out


def _village_table_specs(lines: list[str], total_note: str) -> list[Spec]:
    rows, total = parse_village_table(lines)
    title = "Annexure IV : High Risk Villages and Wards - State-wise"
    col = "No. of High Risk Villages and Wards"
    out = []
    for label, printed in rows + [("Total", total)]:
        geo = "India" if label == "Total" else labels.resolve_or_list(label).canonical
        note = _NO_UNIT.format("villages and wards")
        if label == "Total":
            note += "; " + total_note
        out.append(Spec("TMBA26", 59, "other:high_risk_villages_wards", printed, "", col,
                        title=title, col=col, row=label, cell=printed, geography=geo,
                        table_id=title, para="Annexure IV", note=note))
    return out


def _criteria_specs(doc: str, page: int, para: str, amp: str) -> list[Spec]:
    crit = [(f"Death rate >=3.6% {amp} presumptive TB examination rate (testing rate) "
             "<1700/lakh population", "195"),
            (f"Death rate >=3.6% {amp} presumptive TB examination rate (testing rate) "
             ">=1700", "119"),
            ("Incidence rate >=200/lakh population", "21"),
            ("TB Prevalence > 400/lakh population", "12")]
    return [Spec(doc, page, "other:districts_by_selection_criterion", n, "districts",
                 "Number of districts", col="Number of districts", row=c, cell=n,
                 key=f"number-of-districts.criterion-{k}",
                 table_id="Sr. No. | Criteria* | Number of districts", para=para,
                 note="per-criterion count; criteria may overlap (§9.2, E6); the table "
                      "has no title")
            for k, (c, n) in enumerate(crit, start=1)]


def _selection_specs(doc: str, page: int, s1: str, s2: str, para: str) -> list[Spec]:
    return [
        Spec(doc, page, "districts_selected", "347", "districts",
             "districts have been selected" if "have been" in s1
             else "districts were selected", s1, para=para),
        Spec(doc, page, "other:states_uts_selected", "33", "", "State/UTs", s1, para=para,
             note=_NO_UNIT.format("States/UTs")),
        Spec(doc, page, "other:tribal_districts_selected", "38", "districts",
             "tribal districts", s2, para=para),
        Spec(doc, page, "other:mining_districts_selected", "27", "districts",
             "mining districts", s2, para=para),
        Spec(doc, page, "other:aspirational_districts_selected", "46", "districts",
             "aspirational districts", s2, para=para),
    ]


def _states_spec(doc, page, sentence, para="", **kw) -> Spec:
    return Spec(doc, page, "other:states_uts_selected", "33", "", "States/UTs", sentence,
                para=para, note=_NO_UNIT.format("States/UTs"), **kw)


def _fixed_specs() -> list[Spec]:
    S: list[Spec] = []

    # ---------------- CTD, 100 Days Campaign -------------------------------------------
    S += _criteria_specs("CTD100", 6, "Geographical prioritization, criteria table", "&")
    S += _selection_specs(
        "CTD100", 7,
        "Following this process, 347 districts have been selected across 33 State/UTs.",
        "These districts include 38 tribal districts, 27 mining districts, and 46 "
        "aspirational districts among others.",
        "Geographical prioritization, sentence before the table")
    S.append(Spec(
        "CTD100", 7, "other:target_screen_line_listed_vulnerable_acf", "100%", "percent",
        "Screen 100% of line-listed vulnerable populations through active case finding",
        "a) Screen 100% of line-listed vulnerable populations through active case "
        "finding in the community", para="Key strategies to reduce TB Incidence, item a)",
        image=True, basis="target stated as one of active case finding in the same "
        "sentence",
        note="target; the line 'populations through active case finding in the' is "
             "absent from the PDF text layer (lines with the fi ligature are not "
             "encoded) and was read from the page image"))
    S.append(Spec("CTD100", 9, "districts_selected", "347", "districts", "Districts",
                  col="Activities", row="7 December 2024",
                  cell="Launch of campaign in all State/UTs & 347 Districts",
                  table_id="Timelines | Activities", para="timelines table",
                  note="the table has no title; the figure is in the Activities cell "
                       "'Launch of campaign in all State/UTs & 347 Districts'"))
    eo = "Expected outputs, item {}"
    it2 = ("At least 90% screening by X-Ray of line-listed vulnerable individuals and 90% "
           "testing by NAAT")
    it3 = ("Increase upfront NAAT for diagnosis of TB/MDR-TB from existing 30% to 70% "
           "testing of patients with presumptive TB.")
    S += [
        Spec("CTD100", 9, "other:target_additional_tb_cases", "2 lakh", "cases",
             "Detect additional 2 lakh cases", "Detect additional 2 lakh cases",
             para=eo.format(1), basis=_TARGET_CTD, note="campaign target"),
        Spec("CTD100", 9, "other:target_xray_screening_line_listed", "90%", "percent",
             "screening by X-Ray of line-listed vulnerable individuals", it2,
             para=eo.format(2), basis=_TARGET_CTD, note="campaign target"),
        Spec("CTD100", 9, "other:target_naat_testing", "90%", "percent", "testing by NAAT",
             it2, occurrence=2, para=eo.format(2), basis=_TARGET_CTD,
             note="campaign target"),
        Spec("CTD100", 9, "other:upfront_naat_share_existing", "30%", "percent",
             "upfront NAAT for diagnosis of TB/MDR-TB", it3, para=eo.format(3),
             basis=_TARGET_CTD, note="baseline stated in a campaign target"),
        Spec("CTD100", 9, "other:target_upfront_naat_share", "70%", "percent",
             "testing of patients with presumptive TB", it3, para=eo.format(3),
             basis=_TARGET_CTD, note="campaign target"),
        Spec("CTD100", 9, "other:target_npy_nikshay_mitra_coverage", "100%", "percent",
             "coverage by Ni-kshay Poshan Yojana & Ni-kshay Mitra",
             "100% coverage by Ni-kshay Poshan Yojana & Ni-kshay Mitra.",
             para=eo.format(4), basis=_TARGET_CTD, note="campaign target"),
        Spec("CTD100", 9, "other:target_panchayats_tb_free_certification", "50,000", "",
             "Panchayats prepared for TB free certification",
             "50,000 Panchayats prepared for TB free certification",
             para=eo.format(5), image=True, basis=_TARGET_CTD,
             note="campaign target; item 5 and the list's lead-in are absent from the PDF "
                  "text layer (lines with the fi ligature are not encoded) and were read "
                  "from the page image; " + _NO_UNIT.format("Panchayats")),
    ]

    # ---------------- CTD, Guidance Document (2025) ---------------------------------
    S += _criteria_specs("GUIDE", 8, "100 Days Campaign-Geographical prioritization, "
                         "criteria table", "and")
    S += _selection_specs(
        "GUIDE", 8,
        "Following this process, 347 districts were selected across 33 State/UTs.",
        "These districts include 38 tribal districts, 27 mining districts, and 46 "
        "aspirational districts among others.",
        "100 Days Campaign-Geographical prioritization, sentence")
    S.append(Spec(
        "GUIDE", 9, "other:target_screen_line_listed_vulnerable_acf", "100%", "percent",
        "Screen 100% of line-listed vulnerable. population through active case finding",
        "a) Screen 100% of line-listed vulnerable. population through active case finding "
        "in the community.", para="Key strategies to reduce TB Incidence, item a)",
        basis="target stated as one of active case finding in the same sentence",
        note="target"))
    g10 = ("As part of the campaign, over 13.4 lakh Nikshay Shivirs were conducted "
           "nationwide, leading to the screening of 12.97 crore vulnerable individuals and "
           "the detection of over 7.19 lakh TB cases.")
    p10 = "100-Day Campaign Outcome"
    S += [
        Spec("GUIDE", 10, "other:nikshay_shivirs_conducted", "13.4 lakh", "",
             "Nikshay Shivirs were conducted", g10, para=p10,
             note=_G10_NOTE + "; " + _NO_UNIT.format("camps"), **_G10_W),
        Spec("GUIDE", 10, "screened", "12.97 crore", "persons",
             "screening of 12.97 crore vulnerable individuals", g10, para=p10,
             note=_G10_NOTE, **_G10_W),
        Spec("GUIDE", 10, "tb_cases", "7.19 lakh", "cases",
             "detection of over 7.19 lakh TB cases", g10, para=p10, note=_G10_NOTE,
             **_G10_W),
        Spec("GUIDE", 10, "other:asymptomatic_tb_cases", "2.85 lakh", "cases",
             "asymptomatic individuals",
             "This data includes 2.85 lakh asymptomatic individuals, underscoring the "
             "effectiveness of proactive community engagement and targeted screening.",
             para=p10, note=_G10_NOTE, **_G10_W),
        Spec("GUIDE", 31, "other:asymptomatic_tb_cases", "2.85 lakh", "cases",
             "asymptomatic TB cases identified",
             "The total number of asymptomatic TB cases identified during these rounds "
             "exceeded 2.85 lakh, indicating that these cases could have continued to "
             "spread the infection in the community had they not been detected through "
             "the intensive screening strategy.",
             para="Annexure 1, para 1.1.7",
             note="'exceeded' is not a qualifier word of §6.1, so the qualifier is exact"),
    ]
    g48a = ("Through concerted efforts, the NTEP successfully screened 12.97 crore "
            "vulnerable individuals by organizing more than 13.46 lakh Ni-kshay Shivirs "
            "(screening camps) across States and Union Territories, during the 100-day "
            "intensive TB case finding campaign under the TB Mukt Bharat Abhiyaan.")
    g48b = ("This initiative enabled identification of 7.19 lakh TB cases, including 2.85 "
            "lakh asymptomatic cases that might have otherwise remained undiagnosed.")
    g48c = ("Further, community engagement efforts led to registration of 1.05 lakh new "
            "Ni-kshay Mitras who provided over 3 lakh nutrition food baskets to TB "
            "patients, ensuring comprehensive care and much needed nutritional support.")
    p48 = "Operationalization of TB Mukt Bharat Abhiyaan"
    S += [
        Spec("GUIDE", 48, "screened", "12.97 crore", "persons",
             "screened 12.97 crore vulnerable individuals", g48a, para=p48),
        Spec("GUIDE", 48, "other:nikshay_shivirs_conducted", "13.46 lakh", "",
             "Ni-kshay Shivirs (screening camps)", g48a, para=p48,
             note=_NO_UNIT.format("camps")),
        Spec("GUIDE", 48, "tb_cases", "7.19 lakh", "cases",
             "identification of 7.19 lakh TB cases", g48b, para=p48),
        Spec("GUIDE", 48, "other:asymptomatic_tb_cases", "2.85 lakh", "cases",
             "asymptomatic cases", g48b, para=p48),
        Spec("GUIDE", 48, "other:nikshay_mitras_registered", "1.05 lakh", "",
             "registration of 1.05 lakh new Ni-kshay Mitras", g48c, para=p48,
             note="Ni-kshay Mitras include organisations; unit left blank"),
        Spec("GUIDE", 48, "other:food_baskets_provided", "3 lakh", "",
             "nutrition food baskets", g48c, para=p48, note=_NO_UNIT.format("baskets")),
        Spec("GUIDE", 48, "other:gram_panchayats_tb_free_certified", "46,118", "",
             "TB-free certification by 46,118 Gram Panchayats",
             "The achievement of TB-free certification by 46,118 Gram Panchayats also "
             "marks a significant milestone in our journey towards TB elimination.",
             para=p48, note=_NO_UNIT.format("Gram Panchayats")),
    ]

    # ---------------- CTD, TB Mukt Bharat Abhiyaan campaign document v6 (2026) ------------
    intro = "1. Introduction and Background"
    t3 = ("To accelerate the progress towards TB elimination, the Government launched a "
          "100 Days TB Mukt Bharat Abhiyaan on 7th December 2024 in 347 high priority "
          "districts across 33 States/UTs.")
    S += [Spec("TMBA26", 3, "districts_selected", "347", "districts",
               "high priority districts", t3, para=intro),
          _states_spec("TMBA26", 3, t3, para=intro)]
    jb = ("Jan Bhagidari as the central strategy also led to active involvement of over "
          "35,000 elected representatives (MPs/MLAs/MLCs/PRIs/ULBs), over 73,000 "
          "activities through PRIs, > 1 lakh activities with Youth, Schools & Colleges, "
          ">58,000 activities through 23-line ministries and community support through "
          "more than 5 lakh Ni-kshay Mitras including 2 lakh MY Bharat volunteers, "
          "exhibiting a ‘Whole-of-Society and ‘Whole-of-Government’ approach to TB "
          "elimination.")
    gt = "'>' printed before the figure; not a qualifier symbol of §6.1"
    S += [
        Spec("TMBA26", 3, "other:elected_representatives_involved", "35,000", "persons",
             "elected representatives (MPs/MLAs/MLCs/PRIs/ULBs)", jb, para=intro),
        Spec("TMBA26", 3, "other:jan_bhagidari_activities_pris", "73,000", "",
             "activities through PRIs", jb, para=intro, note=_NO_UNIT.format("activities")),
        Spec("TMBA26", 3, "other:jan_bhagidari_activities_youth", "1 lakh", "",
             "activities with Youth, Schools & Colleges", jb, para=intro,
             note=gt + "; " + _NO_UNIT.format("activities")),
        Spec("TMBA26", 3, "other:jan_bhagidari_activities_line_ministries", "58,000", "",
             "activities through 23-line ministries", jb, para=intro,
             note=gt + "; " + _NO_UNIT.format("activities")),
        Spec("TMBA26", 3, "other:line_ministries_involved", "23", "",
             "23-line ministries", jb, para=intro, note=_NO_UNIT.format("ministries")),
        Spec("TMBA26", 3, "other:nikshay_mitras_community_support", "5 lakh", "",
             "community support through more than 5 lakh Ni-kshay Mitras", jb, para=intro,
             note="Ni-kshay Mitras include organisations; unit left blank"),
        Spec("TMBA26", 3, "other:my_bharat_volunteers_nikshay_mitra", "2 lakh", "persons",
             "MY Bharat volunteers", jb, para=intro),
    ]
    b1 = "22.42 Cr vulnerable population identified with 12.46 crore line listed in Ni-kshay"
    b2 = "4.75 Cr X-rays by more than 6000 fixed facility & 510 hand-held X-rays"
    b3 = "1.56 Cr NAAT tests through more than 9,300 NAAT machines"
    lst = "list 'Progress made under TB Mukt Bharat Abhiyaan'"
    cr = "'Cr' read as crore"
    res = "resource in the list headed 'Progress made under TB Mukt Bharat Abhiyaan'"
    S += [
        Spec("TMBA26", 3, "population_targeted", "22.42 Cr", "persons",
             "vulnerable population identified", b1, para=lst,
             note=cr + "; " + _PROG_NOTE, **_PROG_W),
        Spec("TMBA26", 3, "other:vulnerable_line_listed_nikshay", "12.46 crore",
             "persons", "line listed in Ni-kshay", b1, para=lst, note=_PROG_NOTE,
             **_PROG_W),
        Spec("TMBA26", 3, "tested", "4.75 Cr", "tests", "X-rays", b2, para=lst,
             note=cr + "; " + _PROG_NOTE, **_PROG_W),
        Spec("TMBA26", 3, "other:xray_fixed_facilities", "6000", "", "fixed facility", b2,
             para=lst, basis=res,
             note=_PROG_NOTE + "; " + _NO_UNIT.format("facilities"), **_PROG_W),
        Spec("TMBA26", 3, "other:xray_handheld_units", "510", "", "hand-held X-rays", b2,
             para=lst, basis=res,
             note=_PROG_NOTE + "; " + _NO_UNIT.format("machines"), **_PROG_W),
        Spec("TMBA26", 3, "tested", "1.56 Cr", "tests", "NAAT tests", b3, para=lst,
             note=cr + "; " + _PROG_NOTE, **_PROG_W),
        Spec("TMBA26", 3, "other:naat_machines", "9,300", "", "NAAT machines", b3,
             para=lst, basis=res,
             note=_PROG_NOTE + "; " + _NO_UNIT.format("machines"), **_PROG_W),
    ]
    b4 = ("27.28 lakh new TB cases identified of which, 9.48 lakh were asymptomatic TB "
          "cases")
    b7 = ("5.17 lakh new Ni-kshay Mitras registered and 25.59 lakh poshan kits "
          "distributed.")
    lst4 = lst + " (headed on PDF page 3)"
    S += [
        Spec("TMBA26", 4, "tb_cases", "27.28 lakh", "cases", "new TB cases identified",
             b4, para=lst4, note=_PROG_NOTE, **_PROG_W),
        Spec("TMBA26", 4, "other:asymptomatic_tb_cases", "9.48 lakh", "cases",
             "asymptomatic TB cases", b4, para=lst4, note=_PROG_NOTE, **_PROG_W),
        Spec("TMBA26", 4, "other:treated_successfully", "23.99 lakh", "persons",
             "treated successfully", "23.99 lakh treated successfully", para=lst4,
             note=_PROG_NOTE, **_PROG_W),
        Spec("TMBA26", 4, "other:assessed_differentiated_tb_care", "7.91 lakh", "persons",
             "TB patients assessed for Differentiated TB Care",
             "7.91 lakh TB patients assessed for Differentiated TB Care", para=lst4,
             note=_PROG_NOTE, **_PROG_W),
        Spec("TMBA26", 4, "other:nikshay_mitras_registered", "5.17 lakh", "",
             "new Ni-kshay Mitras registered", b7, para=lst4,
             note=_PROG_NOTE + "; Ni-kshay Mitras include organisations; unit left blank",
             **_PROG_W),
        Spec("TMBA26", 4, "other:poshan_kits_distributed", "25.59 lakh", "",
             "poshan kits distributed", b7, para=lst4,
             note=_PROG_NOTE + "; " + _NO_UNIT.format("kits"), **_PROG_W),
        Spec("TMBA26", 4, "other:my_bharat_volunteers_nikshay_mitra", "2 lakh", "persons",
             "MY Bharat Volunteers registered as Ni-kshay Mitra",
             "More than 2 lakh MY Bharat Volunteers registered as Ni-kshay Mitra for "
             "providing psycho-social support to TB patients.", para=lst4,
             note=_PROG_NOTE, **_PROG_W),
        Spec("TMBA26", 4, "other:gram_panchayats_tb_free_certified", "46,118", "",
             "Gram Panchayats have been awarded TB-free certification",
             "As a result of all-round targeted and collaborative efforts, over 46,118 Gram "
             "Panchayats have been awarded TB-free certification for the year 2024.",
             para="paragraph after the progress list", period="the year 2024",
             wstart="2024-01-01", wend="2024-12-31", series="period",
             note=_NO_UNIT.format("Gram Panchayats")),
    ]
    nxt = ("resource in the list introduced by 'The TB Mukt Bharat Abhiyaan now is being "
           "re-inforced with another 100 Days Abhiyaan ... addressing the challenges with'")
    S += [
        Spec("TMBA26", 4, "other:handheld_xray_introduction", "2,000", "",
             "AI enabled hand-held X-rays",
             "Introduction of more than 2,000 AI enabled hand-held X-rays with indigenously "
             "developed AI tool (DEEPCXR) for automated reading of X-ray images,",
             para="list of the further 100 Days Abhiyaan", basis=nxt,
             note=_NO_UNIT.format("machines")),
        Spec("TMBA26", 4, "other:high_risk_villages_wards", "1.58 lakh", "",
             "high risk villages / wards identified",
             "1.58 lakh high risk villages / wards identified using AI based assessment of "
             "30+ indicators", para="list of the further 100 Days Abhiyaan",
             note=_NO_UNIT.format("villages and wards")),
        Spec("TMBA26", 6, "other:high_risk_villages_wards", "1.58 lakh", "",
             "TB vulnerable villages and wards",
             "i. TB Vulnerable Villages and Wards - Screening all individuals (above 14 "
             "years of age), irrespective of vulnerability, in the 1.58 lakh TB vulnerable "
             "villages and wards identified by an Vulnerability Mapping for TB (VMTB) AI "
             "tool based on 30+ region specific indicators like high TB incidence & TB "
             "related pre-disposing factors, anaemia, tobacco use, population density, "
             "child malnutrition, occupation, use of clean cooking fuel etc.",
             para="section 1, Target Population / Geography, a.i",
             note=_NO_UNIT.format("villages and wards")),
        Spec("TMBA26", 9, "other:mmus_utilized", "2,750", "", "MMUs",
             "b. Existing 2,750 MMUs registered under the MMU portal, will be utilized for "
             "this campaign.", para="section 3, Ayushman Arogya Shivir, item b",
             basis="resource stated as used for the campaign in the same sentence",
             note=_NO_UNIT.format("vehicles")),
        Spec("TMBA26", 9, "other:high_risk_villages_wards", "1.58 lakh", "",
             "high risk villages & wards",
             "c. Route map to be prepared for all 1.58 lakh high risk villages & wards "
             "identified though AI (as per Annexure-1) - target to cover at least 100 "
             "X-rays per Shivir & offer X-ray to all individuals (beyond vulnerable "
             "population) in the high risk village & wards",
             para="section 3, Ayushman Arogya Shivir, item c",
             note=_NO_UNIT.format("villages and wards")),
        Spec("TMBA26", 10, "other:high_risk_villages_wards", "1.58 lakh", "",
             "high risk villages & wards",
             "b. High Risk Villages & Wards - Screening all individuals in 1.58 lakh high "
             "risk villages & wards using hand-held X-rays following a pre-defined route "
             "map for Ayushman Arogya Shivir", para="item b, High Risk Villages & Wards",
             note=_NO_UNIT.format("villages and wards")),
    ]

    # ---------------- PIB synopsis (7 December 2024) ---------------------------------
    syn1 = ("In what promises to be a transformative moment in India’s tuberculosis "
            "elimination efforts, the National TB Elimination Programme (NTEP), Ministry "
            "of Health and Family Welfare is launching a novel campaign, over the next 100 "
            "days, in 347 districts across the country.")
    syn2 = ("The 347 districts across 33 States/UTs have been selected based on indicators "
            "such as death rate, presumptive TB examination rate, and incidence rate as "
            "compared to the national average.")
    S += [Spec("PIBSYN", 2, "districts_selected", "347", "districts", "districts", syn1,
               para="opening panel"),
          Spec("PIBSYN", 2, "districts_selected", "347", "districts", "districts", syn2,
               para="panel on the stratified approach"),
          _states_spec("PIBSYN", 2, syn2, para="panel on the stratified approach")]

    # ---------------- PIB backgrounder (6 December 2024) -----------------------------
    bg = ("Spanning 347 districts across 33 states and union territories, the campaign "
          "represents a critical component of India’s strategy to eliminate TB and build a "
          "TB-free nation.")
    S += [Spec("PIBBG", 1, "districts_selected", "347", "districts", "districts", bg,
               para="para 1"),
          _states_spec("PIBBG", 1, bg, para="para 1")]

    # ---------------- PIB press note (24 March 2026) ---------------------------------
    kt = ("Under TB Mukt Bharat Abhiyaan, since 7th December 2024, over 20 crore "
          "vulnerable population is screened for TB, more than 28 lakh TB patients "
          "diagnosed.")
    gp = ("Over 46,118 Gram Panchayats have been awarded TB-free certification for the "
          "year 2024.")
    since = dict(wstart="2024-12-07", series="cumulative")
    yr = dict(period="the year 2024", wstart="2024-01-01", wend="2024-12-31",
              series="period")
    S += [
        Spec("PIB26", 1, "screened", "20 crore", "persons",
             "vulnerable population is screened for TB", kt, para="Key Takeaways",
             **since),
        Spec("PIB26", 1, "tb_cases", "28 lakh", "cases", "TB patients diagnosed", kt,
             para="Key Takeaways", **since),
        Spec("PIB26", 1, "other:gram_panchayats_tb_free_certified", "46,118", "",
             "Gram Panchayats have been awarded TB-free certification", gp,
             para="Key Takeaways", note=_NO_UNIT.format("Gram Panchayats"), **yr),
    ]
    p7h = "section '100-Day TB Mukt Bharat Abhiyaan'"
    p7a = ("The Ministry of Health and Family Welfare launched one of India’s most "
           "intensive TB elimination drives called the 100-Day TB Mukt Bharat Abhiyan on "
           "7th December 2024 in 347 high-priority districts across 33 States/UTs.")
    p7b = ("The Jan Andolan also led to active involvement of over 30,000 elected "
           "representatives and 24-line ministries and support of Ni-kshay Mitras "
           "exhibiting a whole-of-society and whole-of-government approach to TB "
           "elimination.")
    S += [
        Spec("PIB26", 7, "districts_selected", "347", "districts",
             "high-priority districts", p7a, para=p7h),
        _states_spec("PIB26", 7, p7a, para=p7h),
        Spec("PIB26", 7, "other:elected_representatives_involved", "30,000", "persons",
             "elected representatives", p7b, para=p7h),
        Spec("PIB26", 7, "other:line_ministries_involved", "24", "", "24-line ministries",
             p7b, para=p7h, note=_NO_UNIT.format("ministries")),
    ]
    p8 = ("Under TB Mukt Bharat Abhiyaan, since 7th December 2024, over 20 crore "
          "vulnerable population is screened for TB, more than 28 lakh TB patients are "
          "diagnosed including 9 lakh asymptomatic cases, which could have missed "
          "otherwise.")
    S += [
        Spec("PIB26", 8, "screened", "20 crore", "persons",
             "vulnerable population is screened for TB", p8, para=p7h, **since),
        Spec("PIB26", 8, "tb_cases", "28 lakh", "cases", "TB patients are diagnosed", p8,
             para=p7h, **since),
        Spec("PIB26", 8, "other:asymptomatic_tb_cases", "9 lakh", "cases",
             "asymptomatic cases", p8, para=p7h, **since),
        Spec("PIB26", 8, "other:gram_panchayats_tb_free_certified", "46,118", "",
             "Gram Panchayats have been awarded TB-free certification",
             "As a result of all-round targeted and collaborative efforts, over 46,118 Gram "
             "Panchayats have been awarded TB-free certification for the year 2024.",
             para=p7h, note=_NO_UNIT.format("Gram Panchayats"), **yr),
        Spec("PIB26", 8, "other:treatment_success_rate", "90%", "percent",
             "treatment success rate",
             "The treatment success rate under the TB Mukt Bharat Abhiyan has risen to 90%, "
             "surpassing the global average of 88%.", para=p7h),
    ]
    gz = ("Using mobile testing vans equipped with advanced diagnostic machines and "
          "portable X-ray equipment, the team screened 1,250 people over three days and "
          "identified over 250 potential TB cases for further testing.")
    gzn = "sub-State figure (Gurez valley, Bandipora district)"
    box = "box 'Finding TB Cases in Remote Kashmir'"
    S += [
        Spec("PIB26", 10, "screened", "1,250", "persons", "the team screened 1,250 people",
             gz, geography="Jammu and Kashmir", para=box, period="three days",
             series="period", note=gzn),
        Spec("PIB26", 10, "presumptive", "250", "persons",
             "potential TB cases for further testing", gz, geography="Jammu and Kashmir",
             para=box, period="three days", series="period", note=gzn),
    ]
    ai_cell = ("1.62+ Lakh screened; 12–16% extra yield in cases over conventional "
               "methods.")
    ai = "table 'AI-Led Initiatives', row TB Screening (Cough Against TB)"
    S += [
        Spec("PIB26", 11, "screened", "1.62+ Lakh", "persons", "TB Screening",
             col="Clinical / Operational Impact", row="TB Screening", cell=ai_cell,
             table_id="AI-Led Initiatives", para=ai,
             note="the table has no title; Cough Against TB (AI tool); the source cites "
                  "footnote 2 (PIB, PRID 2199422) for this row"),
        Spec("PIB26", 11, "other:extra_yield_over_conventional", "12–16%", "percent",
             "extra yield in cases over conventional methods",
             col="Clinical / Operational Impact", row="TB Screening", cell=ai_cell,
             table_id="AI-Led Initiatives", para=ai,
             note="the table has no title; printed as a range, value left blank; Cough "
                  "Against TB (AI tool)"),
    ]

    # ---------------- PIB year-end review 2024 ---------------------------------------
    ye = ("The campaign will cover 347 selected high priority districts across 33 "
          "States/UTs and will involve a comprehensive strategy to mobilise resources, "
          "raise awareness and intensify actions against TB across all prioritized "
          "districts.")
    ysec = "section 3, 'TB Mukt Bharat – 100 Days Intensified Campaign'"
    S += [Spec("PIBYER", 6, "districts_selected", "347", "districts",
               "selected high priority districts", ye, para=ysec),
          _states_spec("PIBYER", 6, ye, para=ysec)]
    S.append(Spec("PIBYER", 8, "tb_cases", "3 lakh", "cases",
                  "diagnosis of an additional 3 lakh TB cases",
                  "This activity has resulted in the diagnosis of an additional 3 lakh TB "
                  "cases over past 6 years.",
                  para="section 3, item 6 'Active Case Finding'", period="past 6 years",
                  series="period"))
    S.append(Spec("PIBYER", 9, "tb_cases", "50,620", "cases",
                  "Active Case Finding (Additional Cases diagnosed)",
                  title="Achievements 2024", col="2024 (Jan-Oct)",
                  row="Active Case Finding (Additional Cases diagnosed)", cell="50,620",
                  table_id="Achievements 2024", para="table 'Achievements 2024'",
                  period="2024 (Jan-Oct)", wstart="2024-01-01", wend="2024-10-31",
                  series="period",
                  note="footnote '*-Till Oct 2024' printed under the table"))
    ish = ("Through ISHTH campaign, around 4.14 lakh inmates were reached out through 2290 "
           "P&OCS institutions.")
    ihc = ("IHC covered 73 districts in 12 states, and around 1,650 HIV positive cases, "
           "1,802 TB cases, 2,813 Hepatitis-C cases, 700 Hepatitis-B cases, and 641 "
           "syphilis cases have been identified through this Campaign.")
    multi = "integrated multi-disease campaign (STI, HIV, TB, hepatitis)"
    S += [
        Spec("PIBYER", 11, "screened", "4.14 lakh", "persons",
             "inmates were reached out", ish, para="section 4 (NACP), ISHTH campaign",
             note=multi + " among prison inmates; concluded in March 2024"),
        Spec("PIBYER", 11, "other:ishth_institutions", "2290", "",
             "P&OCS institutions", ish, para="section 4 (NACP), ISHTH campaign",
             note=multi + "; " + _NO_UNIT.format("institutions")),
        Spec("PIBYER", 11, "tb_cases", "1,802", "cases", "1,802 TB cases", ihc,
             para="section 4 (NACP), Integrated Health Campaign", note=multi),
        Spec("PIBYER", 11, "other:ihc_districts", "73", "districts", "districts", ihc,
             para="section 4 (NACP), Integrated Health Campaign", note=multi),
        Spec("PIBYER", 11, "other:ihc_states", "12", "", "states", ihc,
             para="section 4 (NACP), Integrated Health Campaign",
             note=multi + "; " + _NO_UNIT.format("States")),
    ]

    # ---------------- Ministry letter with attachments (Kerala Medical Council copy) ----
    k1 = ("This campaign will cover 347 selected high priority districts across 33 "
          "state/UTs (copy enclosed) and the campaign plan along with guidelines are also "
          "enclosed.")
    k2 = ("This 100 days' intensified campaign will cover 347 selected high priority "
          "districts across 33 States/UTs (Annexure-I) and will involve a comprehensive "
          "strategy to mobilize resources, raise awareness and intensify actions against "
          "TB across all prioritized States/Districts.")
    img = ("read from the page image (the page has no usable text layer: page 1 text is "
           "not decodable, page 2 is a scanned image)")
    do = "D.O. letter Z-28015/191/2024-TB dated 21 November 2024, enclosed; " + img
    S += [
        Spec("KERALA", 1, "districts_selected", "347", "districts",
             "selected high priority districts", k1,
             para="Ministry of Ayush letter L-11012/2/2019-DCC, para 2", image=True,
             note=img),
        _states_spec("KERALA", 1, k1,
                     para="Ministry of Ayush letter L-11012/2/2019-DCC, para 2", image=True),
        Spec("KERALA", 2, "districts_selected", "347", "districts",
             "selected high priority districts", k2,
             para="MoHFW D.O. letter Z-28015/191/2024-TB, para 2", image=True,
             pub_date="2024-11-21", note=do),
        _states_spec("KERALA", 2, k2, para="MoHFW D.O. letter Z-28015/191/2024-TB, para 2",
                     image=True, pub_date="2024-11-21"),
    ]
    kc = ("The campaign targets 347 districts across 33 states/UTs, "
          "including high-burden of TB disease and mortality due to TB, tribal, mining, "
          "and aspirational districts.")
    cn = "Concept Note: 100 Days Campaign, section 4 'Geographical Focus'"
    S += [Spec("KERALA", 5, "districts_selected", "347", "districts", "districts", kc,
               para=cn),
          _states_spec("KERALA", 5, kc, para=cn)]
    return S


# =================================================================== scope decisions

SCOPE_RULE = (
    "Inventory scope of the campaign and press documents (§5.1). (1) Figures of the named "
    "quantities enter when the document gives them as figures of active case finding or "
    "of the campaign. (2) Other campaign or ACF figures enter as `other:` (subsets of a "
    "named quantity, reported results, outputs and selection attributes such as "
    "districts by criterion and high-risk villages). (3) National programme resources "
    "(machines, facilities, vehicles, health centres) and targets, norms and KPI target "
    "values enter only when the same sentence states them as inputs, outputs or targets "
    "of the campaign or of active case finding: the sentence names the campaign "
    "(campaign, Abhiyan/Abhiyaan, 100 days) or active case finding. A list item is read "
    "with the lead-in sentence that it completes; a table cell with its table title, "
    "column heading and row label. A heading is not a sentence. (4) Programme-wide "
    "figures not given as campaign or ACF figures, background epidemiology and "
    "eligibility criteria are not entered.")

# (doc, page, figures as printed, where, category, reason)
EXCLUSIONS: list[tuple[str, int, str, str, str, str]] = [
    ("CTD100", 5, "80%; 90%; 18%; 22%; 237; 195; 28; 22", "Overview, NTEP Goal",
     "background", "national targets and epidemiology; not a campaign or ACF figure"),
    ("CTD100", 6, "more than 70%; almost 60%; Almost 46%; 12 to 595",
     "Key Challenges; Rationale", "background",
     "programme-wide or epidemiological figures"),
    ("CTD100", 7, "100% (item b)", "Key strategies, item b)", "norm",
     "screening norm whose sentence does not name the campaign or ACF (rule 3)"),
    ("CTD100", 8, "at least 10%; 5% (item c)", "Key strategies, item c)", "norm",
     "screening norms whose sentence does not name the campaign or ACF (rule 3)"),
    ("CTD100", 8, "Rs 1,000; 18.5; two months", "Key strategies to reduce TB deaths",
     "norm", "benefit and eligibility norms"),
    ("CTD100", 22, "10-12", "Editorial Media Engagement, item a", "norm",
     "operational instruction (cadre of journalists)"),
    ("CTD100", 27, "About 1000", "Ni-kshay Vahan", "resource",
     "Mobile Medical Units: the sentence with the figure does not name the campaign or "
     "ACF (the preceding sentence does) (rule 3)"),
    ("CTD100", 27, "80%; 6 groups", "Field Activities 1.1.1", "background",
     "prevalence-survey background"),
    ("CTD100", 28, "at least 5%; 100%", "1.2 At health facility", "norm",
     "facility screening norms without campaign or ACF in the sentence (rule 3)"),
    ("CTD100", 32, "56.62%; 40%; Rs. 1,080; Rs. 1000", "5. Nutrition interventions",
     "background", "nutrition evidence and benefit amounts"),
    ("CTD100", 34, "100%", "6.2 Action", "norm", "recording and reporting norm"),
    ("CTD100", 44, "Target column (>3000 per lakh population; 100%; 90%; 70%; ...)",
     "Annexure 2: Monitoring Matrix", "KPI target",
     "KPI target column; the table title, column heading and row labels do not name the "
     "campaign or ACF (rule 3)"),
    ("GUIDE", 7, "80%; 90%; 18%; 22%; 237; 195; 28; 22; 60%; 46%; 21 to 540",
     "Goal; Key challenges; Rationale", "background", "national targets and epidemiology"),
    ("GUIDE", 9, "100% (b); at least 10%; 5%; ~80%", "Key strategies, items b) and c)",
     "norm", "screening norms without campaign or ACF in the sentence; burden share is "
     "background"),
    ("GUIDE", 10, "Rs 1,000; 18.5", "Key strategies to reduce TB deaths", "norm",
     "benefit and eligibility norms"),
    ("GUIDE", 34, "100%; 100%; 10%; 5%", "2.2.1 Intensified case finding", "norm",
     "facility screening targets; 'intensified case finding' is not a campaign or ACF "
     "keyword (rule 3)"),
    ("GUIDE", 35, "100%", "presumptive TB to undergo NAAT upfront", "norm",
     "testing norm"),
    ("GUIDE", 42, "18 States", "research study implementation", "other",
     "not a campaign or ACF figure"),
    ("GUIDE", 46, "2.8 million; 237; 195; 312", "TB Mukt City, TB burden", "background",
     "epidemiology"),
    ("GUIDE", 48, "more than 1.7 lakh", "Ayushman Aarogya Mandirs", "resource",
     "health centres; the sentence does not name the campaign or ACF (rule 3)"),
    ("GUIDE", 57, "80%; 90%", "Microplanning", "background", "SDG targets"),
    ("GUIDE", 60, "50 lakhs; 2 lakhs", "sub-national certification", "norm",
     "eligibility thresholds"),
    ("GUIDE", 62, "100% (indicators 1-11)", "Annexure 2: Monitoring Matrix", "KPI target",
     "KPI target values; the table does not name the campaign or ACF (rule 3)"),
    ("TMBA26", 3, "Rs 1000", "Introduction", "norm", "benefit amount"),
    ("TMBA26", 4, "30+", "list of the further 100 Days Abhiyaan", "other",
     "number of indicators of the mapping tool (method detail)"),
    ("TMBA26", 6, "14 years; 2 years", "Target Population", "norm", "eligibility"),
    ("TMBA26", 8, "at least 5% to 10%", "Intensified Screening at general OPDs", "norm",
     "facility norm without campaign or ACF in the sentence (rule 3)"),
    ("TMBA26", 9, "at least 100", "Ayushman Arogya Shivir, item c", "norm",
     "X-rays per Shivir: target whose sentence does not name the campaign or ACF "
     "(rule 3); the 1.58 lakh villages of the same sentence are entered"),
    ("TMBA26", 17, "534 per 100,000; 1 at every 1 lakh", "Urban areas", "background",
     "prevalence and staffing norm"),
    ("TMBA26", 24, "Existing 2,750; ~100", "Operational Strategies (MMU vehicle; Ni-kshay "
     "Vahan)", "resource",
     "MMU vehicles and X-rays per day: the sentences do not name the campaign or ACF "
     "(rule 3)"),
    ("TMBA26", 28, "About 2,750", "Ni-kshay Vahan", "resource",
     "Mobile Medical Units: the sentence with the figure does not name the campaign or "
     "ACF (the preceding sentence does) (rule 3)"),
    ("PIBBG", 2, "18,05,670; 21,35,830; 24,22,121; 25,52,257; 23,94,292",
     "chart 'TB CASES NOTIFIED' 2020-2024", "programme-wide",
     "national notifications, not given as campaign or ACF figures (rule 4)"),
    ("PIBBG", 1, "17.7%; 237; 195; 21.4%; 28; 22", "para 3", "background",
     "epidemiology"),
    ("PIBBG", 2, "around 1.89 crore; 68.3 lakh; approximately 15 lakh",
     "2023 key achievements; TPT", "programme-wide",
     "national tests and TPT, not given as campaign or ACF figures (rule 4)"),
    ("PIBBG", 4, "Rs. 2,781 crores; 1 crore; 1.5 lakh",
     "Financial Support and Community Engagement", "programme-wide",
     "Ni-kshay Poshan Yojana and PMTBMBA (rule 4)"),
    ("PIB26", 1, "21%; 28%", "Key Takeaways", "background", "incidence and mortality"),
    ("PIB26", 6, "Rs. 1,000; Rs.4,454.68 crores; 1.38 crore", "Nikshay Poshan Yojana",
     "programme-wide", "benefit programme (rule 4)"),
    ("PIB26", 7, "6,77,541; 45 lakh; Over 2 lakh", "Ni-kshay Mitra (as on 12 Nov 2025)",
     "programme-wide", "Ni-kshay Mitra programme figures (rule 4)"),
    ("PIB26", 8, "88%; More than 15,000", "global average; BPaLM", "programme-wide",
     "not campaign or ACF figures"),
    ("PIB26", 10, "1,84,726", "Ayushman Arogya Mandirs", "resource",
     "health centres (rule 3)"),
    ("PIB26", 10, "More than 9800; 107", "Technological Infrastructure", "resource",
     "testing facilities; the sentence does not name the campaign or ACF (rule 3)"),
    ("PIB26", 10, "Over 500; 1,500", "Technological Infrastructure, AI-enabled hand-held "
     "chest X-ray units", "resource",
     "'for community screening' does not name the campaign or active case finding "
     "(rule 3)"),
    ("PIB26", 11, "27%; 8 State/UTs", "AI-Led Initiatives, other rows", "other",
     "treatment-outcome and deployment figures, not ACF figures"),
    ("PIB26", 12, "21%; 237; 187", "references", "background", "incidence"),
    ("PIBYER", 6, "17.7%; 237; 21.4%; 28; 22; 32%; 53%; 85%", "section 3", "background",
     "epidemiology and treatment coverage"),
    ("PIBYER", 7, "64%; 10 lakhs; 2.5 lakhs; 24.2 lakh; 25.52 lakh; 21.69 lakh",
     "item 1 TB Notifications", "programme-wide",
     "national notifications and missing cases (rule 4)"),
    ("PIBYER", 7, "7 times; 7.33 lakh; 8.44 lakh; 30%; 33%; 7.91 lakh; 36%",
     "item 2 Private Sector Notification", "programme-wide", "rule 4"),
    ("PIBYER", 7, "63,929; 58,527; 20,566; 74%; 68%; 75%", "item 3 drug-resistant TB",
     "programme-wide", "not ACF figures"),
    ("PIBYER", 8, "Rs 500; Rs 1000; Rs 3286.40 Cr; 1.16 Cr; 13583; 25530; 8293; 127; 826",
     "items 4, 5, 7", "programme-wide", "treatment, benefits and infrastructure"),
    ("PIBYER", 9, "1.79,677; 15.76 lakhs; 11.97 lakhs; 11.95 lakhs",
     "item 9 Ni-kshay Mitra Initiative", "programme-wide", "rule 4"),
    ("PIBYER", 9, "21.69; 7.91; 88.3%; 13.84",
     "table 'Achievements 2024', other rows", "programme-wide",
     "notifications, treatment success and benefits (rule 4)"),
    ("KERALA", 4, "80%; 90%", "Concept Note, Background", "background", "SDG targets"),
    ("KERALA", 5, "Rs 1,000; 18.5", "Concept Note, Key Strategies", "norm", "benefits"),
    ("KERALA", 5, "2,00,000; 90%; 100%; 50,000", "Concept Note, section 5 'Expected "
     "Outputs'", "target",
     "the items stand under a heading, not a lead-in sentence, and do not name the "
     "campaign or ACF (rule 3)"),
    ("KERALA", 8, "About 1000; 10-12", "Ni-kshay Vahan; media engagement", "resource",
     "Mobile Medical Units: the sentence with the figure does not name the campaign or "
     "ACF (rule 3); cadre of journalists is an instruction"),
    ("KERALA", 9, "At least 5%; 10%", "Health Facilities", "norm",
     "screening norm without campaign or ACF in the sentence (rule 3)"),
]

# What the full-page check of the CTD 100 Days Campaign document found, page by page.
CTD_PAGE_NOTES: dict[int, str] = {
    1: "cover", 2: "blank", 3: "contents", 4: "contents", 46: "blank (tinted)",
    47: "blank", 48: "back cover", 43: "Annexure 1 flow chart", 45: "Annexure 3",
}


# =================================================================== building rows

def _manifest() -> dict[str, dict]:
    sys.path.insert(0, str(ROOT))
    from tools.fetch_sources import read_manifest
    return {r["file"]: r for r in read_manifest()}


def verify_inputs() -> None:
    """SHA-256 of every input against data/source_manifest.csv; ValueError on mismatch."""
    sys.path.insert(0, str(ROOT))
    from tools.fetch_sources import verify
    man = _manifest()
    for f in sorted(OWN_FILES):
        verify(ROOT / f, man[f]["sha256"])


def _norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'")
    s = re.sub(r"-\s+", "-", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s: str) -> list[str]:
    return re.findall(r"[\w%.,/&>+*'-]+", _norm(s))


def _page_text(file: str, page: int, cache: dict) -> str:
    key = (file, page)
    if key not in cache:
        cache[key] = "\n".join(page_lines(ROOT / file, page))
    return cache[key]


def _verify(spec: Spec, file: str, cache: dict) -> str:
    if spec.image:
        return "page image"
    text = _norm(_page_text(file, spec.page, cache))
    pieces = ([x for x in (spec.title, spec.col, spec.row) if x] if spec.is_table
              else [spec.sentence])
    R.find_figure(text, _norm(spec.printed))     # ValueError if the figure is absent
    if all(_norm(p) in text for p in pieces):
        return "text"
    if all(t.strip(".,;:") in text for p in pieces for t in _tokens(p)):
        return "text (loose)"
    raise ValueError(f"context not found on {file} page {spec.page}: {spec.context!r}")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def fig_key(spec: Spec) -> str:
    """Stable content key: source . page . table cell or sentence . quantity."""
    if spec.key:
        loc = spec.key
    elif spec.is_table:
        loc = ".".join(x for x in (_slug(spec.col)[:40], _slug(spec.row)[:40]) if x)
    else:
        loc = "s-" + "-".join(re.findall(r"[a-z0-9]+", spec.sentence.lower())[:6])
    key = ".".join((spec.doc, f"p{spec.page:03d}", loc, spec.quantity.replace(":", "_")))
    return key + (f".{spec.occurrence}" if spec.occurrence > 1 else "")


def _row(spec: Spec, man: dict) -> dict:
    file, pub, pub_note = SOURCES[spec.doc]
    q = spec.quantity
    ctx = spec.context
    if spec.is_table:
        qual = R.qualifier(spec.cell or spec.printed, spec.printed, spec.occurrence)
    else:
        qual = R.qualifier(ctx, spec.printed, spec.occurrence)
    dcls, dkw = R.definition_class(q, spec.definition)
    scope, skw, snote = R.scope(ctx)
    has_end = bool(spec.wend or spec.as_on)
    basis = "stated" if spec.as_on else ("window_end" if spec.wend else "bounded")
    notes = []
    if dcls:
        notes.append(f"definition_class keyword: '{dkw}'" if dkw
                     else "definition_class: no keyword matched")
    notes.append(f"scope keyword: '{skw}'" if skw else "scope: no keyword matched")
    if snote:
        notes.append(snote)
    if spec.is_table:
        notes.append("table cell: context is table title | column heading | row label "
                     "(§5.2, §13); qualifier read from the cell")
    if spec.note:
        notes.append(spec.note)
    if pub_note and spec.pub_date is None:
        notes.append(pub_note)
    page_or_para = f"PDF page {spec.page}" + (f"; {spec.para}" if spec.para else "")
    return {
        "fig_id": fig_key(spec), "quantity": q, "value": R.value_of(spec.printed),
        "value_printed": spec.printed, "qualifier": qual, "unit": spec.unit,
        "definition_verbatim": spec.definition, "context_verbatim": ctx,
        "definition_class": dcls, "scope": scope, "series_type": spec.series,
        "window_label": R.window_label(ctx, spec.period, has_end),
        "window_start": spec.wstart, "window_end": spec.wend, "as_on": spec.as_on,
        "as_on_basis": basis, "geography": spec.geography, "source_file": file,
        "source_url": man[file]["url"], "page_or_para": page_or_para,
        "table_id": spec.table_id,
        "pub_date": spec.pub_date if spec.pub_date is not None else pub,
        "note": "; ".join(notes),
    }


def table_checks() -> list[dict]:
    """Printed-total checks of every extracted table that prints a total."""
    out = []
    rows, total = read_exposure_table(ROOT / CTD_FILE)
    out.append(total_check("CTD 100 Days Campaign, State | Total District", CTD_FILE,
                           CTD_PAGE, [n for _, n in rows], total))
    g = SOURCES["GUIDE"][0]
    rows, total = parse_exposure_lines(page_lines(ROOT / g, 8))
    out.append(total_check("Guidance Document, State | Total District", g, 8,
                           [n for _, n in rows], total))
    t = SOURCES["TMBA26"][0]
    vrows, vtotal = parse_village_table(page_lines(ROOT / t, 59))
    out.append(total_check("Campaign 2026 v6, Annexure IV High Risk Villages and Wards",
                           t, 59, [parse_int(v) for _, v in vrows],
                           None if vtotal is None else parse_int(vtotal)))
    for name, f, p in (
            ("CTD 100 Days Campaign, criteria table", CTD_FILE, 6),
            ("Guidance Document, criteria table", g, 8)):
        out.append(total_check(name, f, p, [195, 119, 21, 12], None)
                   | {"sum_of_rows": "",
                      "note": "no total printed: sum check not applied; the per-criterion "
                              "counts are not summed (criteria may overlap; §9.2 E6)"})
    return out


def _total_note(check: dict) -> str:
    if check["pass"] == "yes":
        return (f"printed-total check passed: {check['rows']} State/UT rows sum to "
                f"{check['sum_of_rows']}, printed total {check['printed_total']}")
    return (f"printed-total check FAILED: the {check['rows']} State/UT rows sum to "
            f"{check['sum_of_rows']:,} against a printed total of "
            f"{check['printed_total']:,} (difference {check['difference']}); no row is "
            "missing; values kept exactly as printed")


def all_specs(checks: list[dict] | None = None) -> list[Spec]:
    checks = checks if checks is not None else table_checks()
    S = _fixed_specs()
    S += _district_table_specs("CTD100", CTD_PAGE, page_lines(ROOT / CTD_FILE, CTD_PAGE),
                               "Geographical prioritization, table", _total_note(checks[0]))
    S += _district_table_specs("GUIDE", 8, page_lines(ROOT / SOURCES["GUIDE"][0], 8),
                               "100 Days Campaign-Geographical prioritization, table",
                               _total_note(checks[1]))
    S += _village_table_specs(page_lines(ROOT / SOURCES["TMBA26"][0], 59),
                              _total_note(checks[2]))
    order = list(SOURCES)
    return sorted(S, key=lambda s: (order.index(s.doc), s.page))


def build_inventory(checks: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    """Inventory rows of the campaign documents and their provenance check."""
    man = _manifest()
    cache: dict = {}
    rows, prov = [], []
    for spec in all_specs(checks):
        file = SOURCES[spec.doc][0]
        row = _row(spec, man)
        rows.append(row)
        prov.append({"kind": "figure", "fig_id": row["fig_id"], "source_file": file,
                     "page": spec.page, "method": _verify(spec, file, cache),
                     "figures_found": ""})
    ids = [r["fig_id"] for r in rows]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise ValueError(f"fig_id collisions: {sorted(dup)}")
    return rows, prov


def ctd_page_checks(rows: list[dict]) -> list[dict]:
    """One record per page of the CTD 100 Days Campaign document (all 48 pages
    rendered and inspected, because its text layer drops lines with 'fi')."""
    by_page: dict[int, list[str]] = {}
    for r in rows:
        if r["source_file"] == CTD_FILE:
            p = int(re.match(r"PDF page (\d+)", r["page_or_para"]).group(1))
            by_page.setdefault(p, []).append(r["fig_id"])
    excl: dict[int, list[str]] = {}
    for doc, p, figs, where, cat, _ in EXCLUSIONS:
        if doc == "CTD100":
            excl.setdefault(p, []).append(f"{figs} ({where}; {cat})")
    out = []
    for p in range(1, 49):
        first = 6 <= p <= 11 or p == 44
        method = ("text layer and rendered page image, inspected "
                  + ("in the first round" if first else "in the full-page check"))
        found = by_page.get(p, [])
        parts = [f"in inventory: {'; '.join(found)}" if found else "no figure in scope"]
        if p in excl:
            parts.append("considered and left out: " + " | ".join(excl[p]))
        if p in CTD_PAGE_NOTES:
            parts.append(CTD_PAGE_NOTES[p])
        out.append({"kind": "page_check", "fig_id": "", "source_file": CTD_FILE,
                    "page": p, "method": method, "figures_found": "; ".join(parts)})
    return out


def scope_decisions(rows: list[dict], specs: list[Spec]) -> list[dict]:
    out = [{"kind": "rule", "doc": "campaign and press documents", "source_file": OFF,
            "page": "", "figures": "", "where": "", "category": "", "decision": "",
            "reason": SCOPE_RULE}]
    for s in specs:
        if s.basis:
            out.append({"kind": "included by rule 3", "doc": s.doc,
                        "source_file": SOURCES[s.doc][0], "page": s.page,
                        "figures": s.printed, "where": s.para, "category": s.quantity,
                        "decision": "entered", "reason": s.basis})
    for doc, p, figs, where, cat, why in EXCLUSIONS:
        out.append({"kind": "exclusion", "doc": doc, "source_file": SOURCES[doc][0],
                    "page": p, "figures": figs, "where": where, "category": cat,
                    "decision": "not entered", "reason": why})
    return out


# =================================================================== main

def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _merge_inventory(own: list[dict]) -> list[dict]:
    """Rows of other extractors are kept as they are; this extractor's rows replace
    its own earlier rows."""
    kept = []
    if INVENTORY.exists():
        with open(INVENTORY, newline="", encoding="utf-8") as f:
            kept = [r for r in csv.DictReader(f) if r["source_file"] not in OWN_FILES]
    return own + kept


SCOPE_DECISIONS = EXTRACTED / "inventory_scope_decisions.csv"
SCOPE_COLUMNS = ["kind", "doc", "source_file", "page", "figures", "where", "category",
                 "decision", "reason"]


def _own_scope_row(r: dict) -> bool:
    """A row written by this extractor: one of its documents, its rule row (source
    'data_raw/official/'), or its rule row as first written (blank source)."""
    return (r["source_file"] in OWN_FILES or r["source_file"] == OFF
            or (r["source_file"] == "" and r["reason"].startswith(SCOPE_RULE[:60])))


def _merge_scope(own: list[dict], path: Path = SCOPE_DECISIONS) -> list[dict]:
    """Rows of other extractors are kept as they are; this extractor's rows replace
    its own earlier rows (merged on source_file)."""
    kept = []
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            kept = [r for r in csv.DictReader(f) if not _own_scope_row(r)]
    return own + kept


def _e7_numbers(lines: list[str]) -> tuple[int | None, int | None]:
    m = re.search(r"(\d+) districts have been selected across (\d+) State/UTs",
                  " ".join(lines))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def _e6_number(criteria_lines: list[str], table_lines: list[str]) -> int | None:
    """A number of districts selected printed by the criteria table or the text with
    it: the criteria page has no total row; the sentence that follows the table and
    its footnote (top of PDF page 7) begins 'Following this process, N districts'."""
    text = " ".join(criteria_lines)
    m = re.search(r"(\d+) districts (?:have been|were) selected", text)
    if m:
        return int(m.group(1))
    head = " ".join(table_lines[:2])
    m = re.match(r"Following this process, (\d+) districts", head)
    return int(m.group(1)) if m else None


def main() -> int:
    verify_inputs()
    from src.extract import lgd as lgd_mod
    lgd_out, _, _, _ = lgd_mod.run()
    lgd_units = coarse_lgd({s: st["count"] for s, st in lgd_out.items()})
    rec_out, _ = lgd_mod.run_reconstructed()
    lgd_units_rec = coarse_lgd({s: st["count"] for s, st in rec_out.items()})

    ctd = ROOT / CTD_FILE
    lines = page_lines(ctd, CTD_PAGE)
    raw_rows, total = parse_exposure_lines(lines)
    resolutions = [labels.resolve_or_list(lab) for lab, _ in raw_rows]
    rows = [(lab, r.canonical, n) for (lab, n), r in zip(raw_rows, resolutions)]
    e6 = _e6_number(page_lines(ctd, CRITERIA_PAGE), lines)
    e7 = _e7_numbers(lines)
    res = check_exposure(rows, total, lgd_units, e6_number=e6, e7=e7)
    res_rec = check_exposure(rows, total, lgd_units_rec, e6_number=e6, e7=e7)

    n_left = (len(raw_rows) + 1) // 2
    _write(EXTRACTED / "exposure_campaign.csv",
           ["row", "block", "label_printed", "canonical", "coarse_unit", "label_rule_step",
            "label_evidence", "campaign_count", "computable", "source_file", "pdf_page",
            "printed_page", "table_id"],
           [{"row": i + 1, "block": "left" if i < n_left else "right",
             "label_printed": lab, "canonical": r.canonical,
             "coarse_unit": states.coarsen(r.canonical) if r.canonical else "",
             "label_rule_step": r.step, "label_evidence": r.evidence,
             "campaign_count": n, "computable": _yn(bool(r.canonical)),
             "source_file": CTD_FILE, "pdf_page": CTD_PAGE, "printed_page": 5,
             "table_id": "State | Total District (Geographical prioritization)"}
            for i, ((lab, n), r) in enumerate(zip(raw_rows, resolutions))])
    for r, suffix in ((res, ""), (res_rec, "_reconstructed")):
        _write(EXTRACTED / f"exposure_checks{suffix}.csv",
               ["check", "inputs", "expected", "observed", "pass", "note"],
               r.checks + [{"check": "decision", "inputs": "E1, E2, E4, E5",
                            "expected": "table not rejected",
                            "observed": "rejected" if r.rejected else "not rejected",
                            "pass": "no" if r.rejected else "yes",
                            "note": "; ".join(r.reject_reasons) + (
                                "" if not suffix else
                                ("; " if r.reject_reasons else "") +
                                "denominator: LGD count reconstructed from official "
                                "notices (§13 deviation, 19 November 2026)")}])
        _write(EXTRACTED / f"exposure_share{suffix}.csv",
               ["unit", "in_table", "campaign_count", "lgd_count", "share", "capped",
                "flagged_e5", "computable", "reason"], r.units)

    checks = table_checks()
    _write(EXTRACTED / "table_total_checks.csv",
           ["table", "source_file", "page", "rows", "sum_of_rows", "printed_total",
            "difference", "pass", "note"], checks)

    named = named_list_check(named_list_state_labels(ROOT / KERALA_FILE), rows)
    _write(EXTRACTED / "named_list_check.csv",
           ["state", "ctd_count", "named_list_rows", "match", "named_list_labels",
            "label_rule_step", "note"], named)

    specs = all_specs(checks)
    inv, prov = build_inventory(checks)
    _write(INVENTORY, INVENTORY_COLUMNS, _merge_inventory(inv))
    _write(EXTRACTED / "campaign_inventory_provenance.csv",
           ["kind", "fig_id", "source_file", "page", "method", "figures_found"],
           prov + ctd_page_checks(inv))
    _write(SCOPE_DECISIONS, SCOPE_COLUMNS, _merge_scope(scope_decisions(inv, specs)))

    for label, r in (("registered §9.3", res), ("reconstructed (§13)", res_rec)):
        print(f"-- exposure checks, denominator {label}")
        for c in r.checks:
            print(c["check"], c["pass"], "|", c["observed"])
        print("exposure table", "REJECTED: " + "; ".join(r.reject_reasons)
              if r.rejected else "not rejected")
    for c in checks:
        print("total check:", c["table"], c["pass"], c["sum_of_rows"], c["printed_total"])
    mism = [r["state"] for r in named if r["match"] == "no" and r["state"] != "TOTAL"]
    print(f"named list: {named[-1]['named_list_rows']} rows; States not matching the CTD "
          f"table: {len(mism)}")
    print(f"inventory rows from campaign documents: {len(inv)}")
    return 1 if res.rejected or res_rec.rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())
